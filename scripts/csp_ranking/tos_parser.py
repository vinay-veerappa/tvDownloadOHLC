"""
ThinkorSwim (TOS) Option Scanner CSV Parser
Extracts option contracts, underlying tickers, strikes, expirations, Greeks, and liquidity metrics.
"""

import re
import csv
from datetime import datetime, date
from typing import List, Dict, Any, Optional
from pathlib import Path


class TOSOptionContract:
    def __init__(self, raw_row: Dict[str, Any], scan_date: Optional[date] = None):
        self.raw_row = raw_row
        self.scan_date = scan_date or date.today()
        
        self.symbol: str = str(raw_row.get("Symbol", "")).strip()
        self.description: str = str(raw_row.get("Description", "")).strip()
        
        # Parsed elements
        self.ticker: str = ""
        self.expiry_date: Optional[date] = None
        self.strike: float = 0.0
        self.option_type: str = "PUT"
        
        # Numerical fields
        self.last: float = self._parse_float(raw_row.get("Last"))
        self.net_change: float = self._parse_float(raw_row.get("Net Chng"))
        self.pct_change: float = self._parse_pct(raw_row.get("%Change"))
        self.volume: int = self._parse_int(raw_row.get("Volume"))
        self.bid: float = self._parse_float(raw_row.get("Bid"))
        self.ask: float = self._parse_float(raw_row.get("Ask"))
        self.high: float = self._parse_float(raw_row.get("High"))
        self.low: float = self._parse_float(raw_row.get("Low"))
        
        # Greeks
        self.delta: float = self._parse_float(raw_row.get("Delta"))
        self.gamma: float = self._parse_float(raw_row.get("Gamma"))
        self.theta: float = self._parse_float(raw_row.get("Theta"))
        self.vega: float = self._parse_float(raw_row.get("Vega"))
        
        self._parse_symbol_and_description()
        
        # Computed Option Metrics
        self.mid_price: float = round((self.bid + self.ask) / 2.0, 2) if (self.bid + self.ask) > 0 else self.last
        self.spread: float = round(max(0.0, self.ask - self.bid), 2)
        self.spread_pct: float = round((self.spread / self.mid_price), 4) if self.mid_price > 0 else 1.0
        
        if self.expiry_date:
            self.dte: int = max(1, (self.expiry_date - self.scan_date).days)
        else:
            self.dte: int = 30
            
        self.collateral: float = self.strike * 100.0
        self.premium: float = self.bid * 100.0
        self.ror_pct: float = (self.bid / self.strike * 100.0) if self.strike > 0 else 0.0
        self.annualized_ror_pct: float = (self.ror_pct * (365.0 / self.dte)) if self.dte > 0 else 0.0

    def _parse_float(self, val: Any) -> float:
        if val is None:
            return 0.0
        s = str(val).strip().replace("$", "").replace(",", "")
        if s == "" or s.lower() == "<empty>" or s == "--":
            return 0.0
        try:
            return float(s)
        except ValueError:
            return 0.0

    def _parse_int(self, val: Any) -> int:
        if val is None:
            return 0
        s = str(val).strip().replace(",", "")
        if s == "" or s.lower() == "<empty>" or s == "--":
            return 0
        try:
            return int(float(s))
        except ValueError:
            return 0

    def _parse_pct(self, val: Any) -> float:
        if val is None:
            return 0.0
        s = str(val).strip().replace("%", "").replace("+", "")
        try:
            return float(s)
        except ValueError:
            return 0.0

    def _parse_symbol_and_description(self):
        # Format 1: .CRCL260925P79 -> Ticker CRCL, Expiry 260925 (YYMMDD), Put, Strike 79
        match = re.match(r"^\.?([A-Za-z]+)(\d{6})([CP])(\d+(?:\.\d+)?)$", self.symbol)
        if match:
            self.ticker = match.group(1).upper()
            yymmdd = match.group(2)
            self.option_type = "PUT" if match.group(3).upper() == "P" else "CALL"
            self.strike = float(match.group(4))
            try:
                # YYMMDD -> 20YY-MM-DD
                year = 2000 + int(yymmdd[0:2])
                month = int(yymmdd[2:4])
                day = int(yymmdd[4:6])
                self.expiry_date = date(year, month, day)
            except Exception:
                pass
            return

        # Fallback format: Description e.g. "CRCL 100 (Weeklys) 25 SEP 26 79 PUT"
        desc_match = re.search(r"^([A-Za-z]+).*?(\d{1,2}\s+[A-Za-z]{3}\s+\d{2})\s+(\d+(?:\.\d+)?)\s+(PUT|CALL)", self.description, re.IGNORECASE)
        if desc_match:
            self.ticker = desc_match.group(1).upper()
            date_str = desc_match.group(2)
            self.strike = float(desc_match.group(3))
            self.option_type = desc_match.group(4).upper()
            try:
                # e.g. 25 SEP 26
                dt = datetime.strptime(date_str, "%d %b %y")
                self.expiry_date = dt.date()
            except Exception:
                pass
            return
            
        # Generic fallback
        if not self.ticker and self.symbol:
            clean = self.symbol.lstrip(".")
            m = re.match(r"^([A-Za-z]+)", clean)
            if m:
                self.ticker = m.group(1).upper()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "symbol": self.symbol,
            "ticker": self.ticker,
            "description": self.description,
            "expiry_date": self.expiry_date.isoformat() if self.expiry_date else "",
            "dte": self.dte,
            "strike": self.strike,
            "option_type": self.option_type,
            "last": self.last,
            "net_change": self.net_change,
            "pct_change": self.pct_change,
            "volume": self.volume,
            "bid": self.bid,
            "ask": self.ask,
            "mid_price": round(self.mid_price, 2),
            "spread": round(self.spread, 2),
            "spread_pct": round(self.spread_pct * 100.0, 2),
            "delta": self.delta,
            "gamma": self.gamma,
            "theta": self.theta,
            "vega": self.vega,
            "collateral": self.collateral,
            "premium": self.premium,
            "ror_pct": round(self.ror_pct, 2),
            "annualized_ror_pct": round(self.annualized_ror_pct, 2),
        }


def parse_tos_scanner_csv(file_path: str | Path, scan_date: Optional[date] = None) -> List[TOSOptionContract]:
    """
    Parses a ThinkorSwim Option Scanner CSV file.
    Skips preamble rows (e.g. 'Watchlist Scanner', 'Results') and finds the column headers.
    """
    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"TOS CSV file not found: {file_path}")

    contracts = []
    with open(path, mode="r", encoding="utf-8", errors="ignore") as f:
        lines = f.readlines()

    header_index = -1
    for i, line in enumerate(lines):
        line_clean = line.strip()
        if line_clean.startswith("Symbol,") or "Symbol,Description" in line_clean:
            header_index = i
            break

    if header_index == -1:
        # Try standard DictReader
        reader = csv.DictReader(lines)
    else:
        reader = csv.DictReader(lines[header_index:])

    for row in reader:
        sym = row.get("Symbol")
        if not sym or sym.strip() == "" or sym.strip() == "Symbol":
            continue
        contract = TOSOptionContract(row, scan_date=scan_date)
        if contract.ticker and contract.strike > 0:
            contracts.append(contract)

    return contracts
