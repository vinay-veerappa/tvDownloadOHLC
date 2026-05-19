import json
import logging
from dataclasses import dataclass
from datetime import datetime, timezone, timedelta
from typing import List, Optional

from prisma import Prisma

logger = logging.getLogger(__name__)

INDEX_STALENESS_SEC = 300.0   # 5 minutes for index tickers
DEFAULT_STALENESS_SEC = 1800.0  # 30 minutes for stocks


@dataclass
class GexRegime:
    """Current GEX regime state for a ticker. Spec §4.2"""
    ticker: str
    snapshot_at: datetime
    spot_price: float

    total_gex: float
    gex_regime: str                          # "POSITIVE" | "NEGATIVE" | "TRANSITION"
    regime_label: Optional[str]
    zero_gamma: Optional[float]
    distance_to_zero_gamma_pct: Optional[float]  # (spot - zg) / zg * 100

    # Walls from MacroSnapshot
    macro_call_wall: Optional[float]
    macro_put_wall: Optional[float]

    # Second-order greeks from GexSnapshot
    net_vanna_exposure: Optional[float]
    net_speed_exposure: Optional[float]
    volatility_skew_premium: Optional[float]
    put_25d_iv: Optional[float]
    call_25d_iv: Optional[float]

    # Centroids / magnets
    call_volume_centroid: Optional[float]
    put_volume_centroid: Optional[float]
    gamma_magnet: Optional[float]
    pin_strike: Optional[float]

    is_stale: bool = False
    age_seconds: float = 0.0


@dataclass
class RegimeHistory:
    """Trajectory of regime over a time window."""
    snapshots: List[GexRegime]
    minutes_in_current_regime: float
    spot_drift_pct: float


class RegimeService:
    """
    Reads GEX regime data from Prisma. Provides the full spec §4.2 interface.
    Caches latest snapshot per ticker for 30s.
    """

    INDEX_TICKERS = {"SPX", "SPY", "QQQ", "IWM"}

    def __init__(self, db: Prisma, cache_ttl_sec: int = 30):
        self.db = db
        self._cache: dict = {}
        self._cache_ttl = cache_ttl_sec

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _cache_key(self, ticker: str) -> str:
        return ticker.upper()

    def _is_cache_valid(self, key: str) -> bool:
        entry = self._cache.get(key)
        if not entry:
            return False
        return (datetime.now(timezone.utc) - entry["at"]).total_seconds() < self._cache_ttl

    def _cache_put(self, key: str, regime: GexRegime):
        self._cache[key] = {"at": datetime.now(timezone.utc), "regime": regime}

    def _cache_get(self, key: str) -> Optional[GexRegime]:
        entry = self._cache.get(key)
        return entry["regime"] if entry else None

    async def _build_gex_regime(self, ticker: str) -> Optional[GexRegime]:
        """Fetches the latest GexSnapshot + MacroSnapshot and builds a GexRegime dataclass."""
        ticker = ticker.upper()
        try:
            snapshot = await self.db.gexsnapshot.find_first(
                where={"ticker": ticker},
                order={"timestamp": "desc"}
            )
            if not snapshot:
                return None

            # Staleness check
            now = datetime.now(timezone.utc)
            ts = snapshot.timestamp
            if ts.tzinfo is None:
                ts = ts.replace(tzinfo=timezone.utc)
            age_seconds = (now - ts).total_seconds()

            staleness_threshold = (
                INDEX_STALENESS_SEC if ticker in self.INDEX_TICKERS else DEFAULT_STALENESS_SEC
            )
            is_stale = age_seconds > staleness_threshold

            # Fetch MacroSnapshot for wall data
            macro = await self.db.macrosnapshot.find_first(
                where={"ticker": ticker},
                order={"timestamp": "desc"}
            )

            spot = snapshot.spotPrice or 0.0
            zero_gamma = macro.zeroGamma if macro else None
            dist_pct = None
            if zero_gamma and zero_gamma > 0:
                dist_pct = (spot - zero_gamma) / zero_gamma * 100.0

            return GexRegime(
                ticker=ticker,
                snapshot_at=snapshot.timestamp,
                spot_price=spot,
                total_gex=snapshot.totalGex or 0.0,
                gex_regime=snapshot.gexRegime or "UNKNOWN",
                regime_label=snapshot.regimeLabel,
                zero_gamma=zero_gamma,
                distance_to_zero_gamma_pct=dist_pct,
                macro_call_wall=macro.macroCallWall if macro else None,
                macro_put_wall=macro.macroPutWall if macro else None,
                net_vanna_exposure=getattr(snapshot, "netVannaExposure", None),
                net_speed_exposure=getattr(snapshot, "netSpeedExposure", None),
                volatility_skew_premium=getattr(snapshot, "volatilitySkewPremium", None),
                put_25d_iv=getattr(snapshot, "put25dIv", None),
                call_25d_iv=getattr(snapshot, "call25dIv", None),
                call_volume_centroid=getattr(snapshot, "callVolumeCentroid", None),
                put_volume_centroid=getattr(snapshot, "putVolumeCentroid", None),
                gamma_magnet=snapshot.gammaMagnet if hasattr(snapshot, "gammaMagnet") else None,
                pin_strike=snapshot.pinStrike if hasattr(snapshot, "pinStrike") else None,
                is_stale=is_stale,
                age_seconds=age_seconds,
            )
        except Exception as e:
            logger.error(f"RegimeService: Error building GexRegime for {ticker}: {e}", exc_info=True)
            return None

    # ------------------------------------------------------------------
    # Public spec-compliant API
    # ------------------------------------------------------------------

    async def get_current_regime(self, ticker: str) -> Optional[GexRegime]:
        """
        Latest GEX regime snapshot for ticker.
        Returns None if stale (>5 min for indices, >30 min for stocks).
        Spec §4.2
        """
        ticker = ticker.upper()
        key = self._cache_key(ticker)

        if self._is_cache_valid(key):
            regime = self._cache_get(key)
            if regime and not regime.is_stale:
                return regime

        regime = await self._build_gex_regime(ticker)
        if regime:
            self._cache_put(key, regime)
            if regime.is_stale:
                logger.warning(f"RegimeService: Stale data for {ticker} ({regime.age_seconds:.0f}s old). Returning None.")
                return None
        return regime

    async def get_regime_history(
        self,
        ticker: str,
        lookback_minutes: int = 30,
    ) -> RegimeHistory:
        """
        Trajectory of regime snapshots over the lookback window.
        Spec §4.2
        """
        ticker = ticker.upper()
        cutoff = datetime.now(timezone.utc) - timedelta(minutes=lookback_minutes)

        snapshots_raw = []
        try:
            snapshots_raw = await self.db.gexsnapshot.find_many(
                where={"ticker": ticker, "timestamp": {"gte": cutoff}},
                order={"timestamp": "asc"}
            )
        except Exception as e:
            logger.error(f"RegimeService: Error fetching regime history for {ticker}: {e}")

        macro = None
        try:
            macro = await self.db.macrosnapshot.find_first(
                where={"ticker": ticker},
                order={"timestamp": "desc"}
            )
        except Exception:
            pass

        regimes: List[GexRegime] = []
        for s in snapshots_raw:
            spot = s.spotPrice or 0.0
            zero_gamma = macro.zeroGamma if macro else None
            dist_pct = None
            if zero_gamma and zero_gamma > 0:
                dist_pct = (spot - zero_gamma) / zero_gamma * 100.0

            ts = s.timestamp
            if ts.tzinfo is None:
                ts = ts.replace(tzinfo=timezone.utc)

            regimes.append(GexRegime(
                ticker=ticker,
                snapshot_at=s.timestamp,
                spot_price=spot,
                total_gex=s.totalGex or 0.0,
                gex_regime=s.gexRegime or "UNKNOWN",
                regime_label=s.regimeLabel,
                zero_gamma=zero_gamma,
                distance_to_zero_gamma_pct=dist_pct,
                macro_call_wall=macro.macroCallWall if macro else None,
                macro_put_wall=macro.macroPutWall if macro else None,
                net_vanna_exposure=getattr(s, "netVannaExposure", None),
                net_speed_exposure=getattr(s, "netSpeedExposure", None),
                volatility_skew_premium=getattr(s, "volatilitySkewPremium", None),
                put_25d_iv=getattr(s, "put25dIv", None),
                call_25d_iv=getattr(s, "call25dIv", None),
                call_volume_centroid=getattr(s, "callVolumeCentroid", None),
                put_volume_centroid=getattr(s, "putVolumeCentroid", None),
                gamma_magnet=s.gammaMagnet if hasattr(s, "gammaMagnet") else None,
                pin_strike=s.pinStrike if hasattr(s, "pinStrike") else None,
                is_stale=False,
                age_seconds=0.0,
            ))

        # Compute how long we've been in the current regime
        minutes_in_current = 0.0
        spot_drift_pct = 0.0
        if regimes:
            current_label = regimes[-1].gex_regime
            i = len(regimes) - 1
            while i >= 0 and regimes[i].gex_regime == current_label:
                i -= 1
            first_in_regime = regimes[i + 1] if i + 1 < len(regimes) else regimes[0]
            t_start = first_in_regime.snapshot_at
            t_end = regimes[-1].snapshot_at
            if t_start.tzinfo is None:
                t_start = t_start.replace(tzinfo=timezone.utc)
            if t_end.tzinfo is None:
                t_end = t_end.replace(tzinfo=timezone.utc)
            minutes_in_current = (t_end - t_start).total_seconds() / 60.0

            if regimes[0].spot_price > 0:
                spot_drift_pct = (regimes[-1].spot_price - regimes[0].spot_price) / regimes[0].spot_price * 100.0

        return RegimeHistory(
            snapshots=regimes,
            minutes_in_current_regime=minutes_in_current,
            spot_drift_pct=spot_drift_pct,
        )

    async def is_in_positive_gamma(self, ticker: str, stable_for_min: int = 30) -> bool:
        """
        True if spot has been continuously above zero-gamma for stable_for_min minutes.
        Spec §4.2
        """
        try:
            history = await self.get_regime_history(ticker, lookback_minutes=stable_for_min)
            if not history.snapshots:
                return False
            # All snapshots in the window must be POSITIVE
            return (
                all(s.gex_regime == "POSITIVE" for s in history.snapshots)
                and history.minutes_in_current_regime >= stable_for_min
            )
        except Exception as e:
            logger.error(f"RegimeService: Error in is_in_positive_gamma for {ticker}: {e}")
            return False

    async def get_nearest_walls(
        self,
        ticker: str,
        above_spot: bool = True,
        n: int = 3,
    ) -> List[float]:
        """
        Returns the n nearest call walls above spot (above_spot=True) or put walls below.
        Reads from MacroSnapshot.dominantNodes JSON. Spec §4.2
        """
        ticker = ticker.upper()
        try:
            macro = await self.db.macrosnapshot.find_first(
                where={"ticker": ticker},
                order={"timestamp": "desc"}
            )
            if not macro:
                return []

            spot = macro.spotPrice or 0.0
            dominant_nodes_raw = getattr(macro, "dominantNodes", None)
            if not dominant_nodes_raw:
                # Fall back to explicit wall fields
                call_wall = macro.macroCallWall or 0.0
                put_wall = macro.macroPutWall or 0.0
                if above_spot and call_wall > spot:
                    return [call_wall]
                if not above_spot and put_wall < spot:
                    return [put_wall]
                return []

            # Parse dominantNodes JSON — expected format: list of {"strike": float, "gex": float}
            try:
                nodes = json.loads(dominant_nodes_raw) if isinstance(dominant_nodes_raw, str) else dominant_nodes_raw
            except (json.JSONDecodeError, TypeError):
                logger.warning(f"RegimeService: Could not parse dominantNodes for {ticker}")
                return []

            strikes = [float(node.get("strike", 0)) for node in nodes if node.get("strike")]

            if above_spot:
                candidates = sorted([s for s in strikes if s > spot])
            else:
                candidates = sorted([s for s in strikes if s < spot], reverse=True)

            return candidates[:n]

        except Exception as e:
            logger.error(f"RegimeService: Error fetching nearest walls for {ticker}: {e}")
            return []

    async def get_distance_to_em_boundary(
        self,
        ticker: str,
        side: str,
        spot: Optional[float] = None,
    ) -> Optional[float]:
        """
        Distance from spot to today's expected move boundary, in dollars.
        Negative if spot has already crossed the boundary.
        Spec §4.2
        """
        ticker = ticker.upper()
        try:
            em_rec = await self.db.expectedmove.find_first(
                where={"ticker": ticker},
                order={"calculationDate": "desc"}
            )
            if not em_rec:
                return None

            basis = em_rec.price or 0.0
            adj_em = em_rec.adjEm or em_rec.straddle or 0.0
            if adj_em <= 0:
                return None

            current_spot = spot
            if current_spot is None:
                gex = await self.db.gexsnapshot.find_first(
                    where={"ticker": ticker},
                    order={"timestamp": "desc"}
                )
                current_spot = gex.spotPrice if gex else basis

            if side.upper() == "UPPER":
                boundary = basis + adj_em
                return current_spot - boundary   # negative means already crossed above
            else:
                boundary = basis - adj_em
                return current_spot - boundary   # negative means already crossed below

        except Exception as e:
            logger.error(f"RegimeService: Error getting EM distance for {ticker}: {e}")
            return None

    # ------------------------------------------------------------------
    # Legacy dict-returning methods (kept for backward compat)
    # ------------------------------------------------------------------

    async def get_gex_regime(self, ticker: str) -> Optional[dict]:
        """Legacy dict API — delegates to get_current_regime."""
        regime = await self._build_gex_regime(ticker.upper())
        if not regime:
            return None
        return {
            "gexRegime": regime.gex_regime,
            "regimeLabel": regime.regime_label or "",
            "totalGex": regime.total_gex,
            "spotPrice": regime.spot_price,
            "gammaMagnet": regime.gamma_magnet or 0.0,
            "pinStrike": regime.pin_strike or 0.0,
            "timestamp": regime.snapshot_at,
            "is_stale": regime.is_stale,
            "age_seconds": regime.age_seconds,
        }

    async def get_macro_regime(self, ticker: str) -> Optional[dict]:
        """Legacy dict API for MacroSnapshot fields."""
        ticker = ticker.upper()
        try:
            snapshot = await self.db.macrosnapshot.find_first(
                where={"ticker": ticker},
                order={"timestamp": "desc"}
            )
            if not snapshot:
                return None
            return {
                "spotPrice": snapshot.spotPrice,
                "macroCallWall": snapshot.macroCallWall or 0.0,
                "macroPutWall": snapshot.macroPutWall or 0.0,
                "zeroGamma": snapshot.zeroGamma or 0.0,
                "timestamp": snapshot.timestamp
            }
        except Exception as e:
            logger.error(f"RegimeService: Error fetching macro regime for {ticker}: {e}")
            return None
