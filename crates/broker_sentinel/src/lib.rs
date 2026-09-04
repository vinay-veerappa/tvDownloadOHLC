//! broker_sentinel — True independent broker killswitch.
//!
//! Watchdog logic (Step 3.1):
//! - Polls NT8 port 7890 /api/positions every 500ms.
//! - If active positions exist and port 7890 fails to respond for > 3000 ms:
//!   trigger direct broker API flatten (Tradovate REST API).
//!
//! Corrected cushion formula:
//!   Cushion = Current Net Liq - (Peak Net Liq - Trailing Limit)
//! Breach when cushion <= 0. Peak Net Liq ratchets up over the session.

use serde::{Deserialize, Serialize};
use std::collections::HashMap;
use std::sync::{Arc, Mutex};
use std::time::{Duration, Instant, SystemTime, UNIX_EPOCH};

const NT8_PORT: u16 = 7890;
const NT8_TOKEN: &str = "d0b837223cab4653";
pub const POLL_MS: u64 = 500;
pub const DEAD_AFTER_MS: u64 = 3_000;

fn nt8_port() -> u16 {
    std::env::var("SENTINEL_TEST_PORT")
        .ok()
        .and_then(|p| p.parse().ok())
        .unwrap_or(NT8_PORT)
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct SentinelConfig {
    /// Tradovate REST API base (demo by default — verification gate uses Demo/Sim).
    pub tradovate_base: String,
    pub tradovate_api_key: String,
    pub tradovate_api_secret: String,
    /// Trailing drawdown limit in USD (from the firm ruleset).
    pub trailing_limit: f64,
    /// Arm the real broker killswitch. When false the watchdog only LOGS what
    /// it would do (safe default for the simulated Gate 3 test without creds).
    pub arm_live_flatten: bool,
}

impl Default for SentinelConfig {
    fn default() -> Self {
        Self {
            tradovate_base: "https://demo-api.tradovate.com".to_string(),
            tradovate_api_key: String::new(),
            tradovate_api_secret: String::new(),
            trailing_limit: 1000.0,
            arm_live_flatten: false,
        }
    }
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Position {
    pub account: String,
    pub symbol: String,
    pub market_position: String,
    pub quantity: f64,
    pub unrealized_pnl: f64,
}

#[derive(Debug)]
pub struct SentinelState {
    pub last_ok: Option<Instant>,
    pub dead_since: Option<Instant>,
    pub peak_net_liq: f64,
    pub cur_net_liq: f64,
    pub cushion: f64,
    pub last_positions: Vec<Position>,
    pub flatten_fired: Option<String>,
    pub kills: u64,
}

impl Default for SentinelState {
    fn default() -> Self {
        Self {
            last_ok: None,
            dead_since: None,
            peak_net_liq: 0.0,
            cur_net_liq: 0.0,
            cushion: 0.0,
            last_positions: Vec::new(),
            flatten_fired: None,
            kills: 0,
        }
    }
}

#[derive(Clone)]
pub struct Sentinel {
    pub config: Arc<SentinelConfig>,
    pub state: Arc<Mutex<SentinelState>>,
    pub event_log: Arc<Mutex<Vec<String>>>,
}

fn now_ms() -> u128 {
    SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .map(|d| d.as_millis())
        .unwrap_or(0)
}

/// Cushion = Current Net Liq - (Peak Net Liq - Trailing Limit). Breach when <= 0.
///
/// ONE function because the expression was written out at two call sites (the watchdog
/// tick and the net-liq tracker). Two copies of a safety formula drift the moment one is
/// edited, and the survivor still looks right in isolation.
pub fn compute_cushion(cur_net_liq: f64, peak_net_liq: f64, trailing_limit: f64) -> f64 {
    cur_net_liq - (peak_net_liq - trailing_limit)
}

/// Peak ratchet. Rises only, and refuses jumps >= 50k, which are a full-account-replace
/// artifact rather than real equity: a bogus peak permanently deflates every later
/// cushion, so this fails toward the smaller peak.
pub fn ratchet_peak(peak_net_liq: f64, total: f64) -> f64 {
    if peak_net_liq == 0.0 {
        total
    } else if total > peak_net_liq && total - peak_net_liq < 50_000.0 {
        total
    } else {
        peak_net_liq
    }
}

fn log_event(s: &Sentinel, line: String) {
    println!("[sentinel] {}", line);
    let mut lg = s.event_log.lock().unwrap();
    lg.push(format!(
        "[{}] {}",
        chrono::Local::now().format("%H:%M:%S%.3f"),
        line
    ));
    if lg.len() > 1000 {
        lg.drain(0..500);
    }
}

fn count_positions(s: &Sentinel) -> usize {
    s.state.lock().unwrap().last_positions.len()
}

impl Sentinel {
    pub fn new(config: SentinelConfig) -> Self {
        Self {
            config: Arc::new(config),
            state: Arc::new(Mutex::new(SentinelState::default())),
            event_log: Arc::new(Mutex::new(Vec::new())),
        }
    }

    async fn fetch_positions(&self) -> Result<Vec<Position>, String> {
        let client = reqwest::Client::new();
        let res = client
            .get(&format!("http://localhost:{}/api/positions", nt8_port()))
            .header("Authorization", format!("Bearer {}", NT8_TOKEN))
            .timeout(Duration::from_millis(1000))
            .send()
            .await
            .map_err(|e| e.to_string())?;
        let v: serde_json::Value = res.json().await.map_err(|e| e.to_string())?;
        let arr = v.as_array().cloned().unwrap_or_default();
        let mut out = Vec::new();
        for p in arr {
            let mp = p.get("marketPosition").and_then(|x| x.as_str()).unwrap_or("Flat");
            if mp != "Flat" {
                out.push(Position {
                    account: p.get("account").and_then(|x| x.as_str()).unwrap_or("").to_string(),
                    symbol: p.get("symbol").and_then(|x| x.as_str()).unwrap_or("").to_string(),
                    market_position: mp.to_string(),
                    quantity: p.get("quantity").and_then(|x| x.as_f64()).unwrap_or(1.0),
                    unrealized_pnl: p.get("unrealizedPnL").and_then(|x| x.as_f64()).unwrap_or(0.0),
                });
            }
        }
        Ok(out)
    }

    async fn fetch_net_liq(&self) -> Result<f64, String> {
        let client = reqwest::Client::new();
        let res = client
            .get(&format!("http://localhost:{}/api/account", nt8_port()))
            .header("Authorization", format!("Bearer {}", NT8_TOKEN))
            .timeout(Duration::from_millis(1000))
            .send()
            .await
            .map_err(|e| e.to_string())?;
        let v: serde_json::Value = res.json().await.map_err(|e| e.to_string())?;
        let arr = v.as_array().cloned().unwrap_or_default();
        let mut total = 0.0;
        for a in arr {
            let nl = a.get("netLiquidation").and_then(|x| x.as_f64()).unwrap_or(0.0);
            let liq = if nl != 0.0 {
                nl
            } else {
                a.get("cashValue").and_then(|x| x.as_f64()).unwrap_or(0.0)
            };
            total += liq;
        }
        Ok(total)
    }

    /// Direct broker API flatten via Tradovate REST (demo or live base URL).
    pub async fn tradovate_flatten_all(&self) -> Result<String, String> {
        if self.config.tradovate_api_key.is_empty() {
            return Err("no tradovate credentials configured".to_string());
        }
        let client = reqwest::Client::new();
        // 1. Auth
        let auth = client
            .post(format!("{}/v1/auth/accesstokenRequest", self.config.tradovate_base))
            .json(&serde_json::json!({
                "name": self.config.tradovate_api_key,
                "password": self.config.tradovate_api_secret,
                "appId": "broker_sentinel",
                "appVersion": "1.0",
                "cid": 1
            }))
            .timeout(Duration::from_secs(10))
            .send()
            .await
            .map_err(|e| format!("auth request failed: {}", e))?;
        let auth_v: serde_json::Value = auth.json().await.map_err(|e| e.to_string())?;
        let token = auth_v
            .get("accessToken")
            .and_then(|t| t.as_str())
            .ok_or_else(|| format!("auth rejected: {}", auth_v))?;

        // 2. Open positions
        let pos = client
            .get(format!("{}/v1/position/list", self.config.tradovate_base))
            .header("Authorization", format!("Bearer {}", token))
            .timeout(Duration::from_secs(10))
            .send()
            .await
            .map_err(|e| format!("position fetch failed: {}", e))?;
        let pos_v: serde_json::Value = pos.json().await.map_err(|e| e.to_string())?;
        let mut flattened: Vec<String> = Vec::new();
        if let Some(rows) = pos_v.as_array() {
            for p in rows {
                let qty = p.get("qty").and_then(|q| q.as_i64()).unwrap_or(0);
                if qty == 0 {
                    continue;
                }
                let id = p.get("id").and_then(|i| i.as_i64()).unwrap_or(0);
                let contract_id = p.get("contractId").and_then(|c| c.as_i64()).unwrap_or(0);
                let account_id = p.get("accountId").cloned().unwrap_or(serde_json::json!(0));
                let account_spec = p.get("accountSpec").cloned().unwrap_or(serde_json::json!(0));
                // 3. Offsetting market order
                let side = if qty > 0 { "Sell" } else { "Buy" };
                let order = client
                    .post(format!("{}/v1/order/placeorder", self.config.tradovate_base))
                    .header("Authorization", format!("Bearer {}", token))
                    .json(&serde_json::json!({
                        "accountSpec": account_spec,
                        "accountId": account_id,
                        "action": side,
                        "symbol": contract_id,
                        "orderQty": qty.abs(),
                        "orderType": "Market",
                        "isAutomated": true
                    }))
                    .timeout(Duration::from_secs(10))
                    .send()
                    .await
                    .map_err(|e| format!("flatten order failed: {}", e))?;
                let status = order.status().as_u16();
                flattened.push(format!("pos{} contract{} {} {}", id, contract_id, side, status));
            }
        }
        Ok(format!(
            "flattened {} position(s): {}",
            flattened.len(),
            flattened.join("; ")
        ))
    }

    /// One watchdog tick: poll positions, track heartbeat, fire killswitch.
    pub async fn tick(&self) {
        match self.fetch_positions().await {
            Ok(positions) => {
                let mut st = self.state.lock().unwrap();
                st.last_ok = Some(Instant::now());
                st.dead_since = None;
                st.last_positions = positions;
                // Cushion = Current Net Liq - (Peak Net Liq - Trailing Limit)
                if st.peak_net_liq > 0.0 {
                    st.cushion = compute_cushion(
                        st.cur_net_liq, st.peak_net_liq, self.config.trailing_limit);
                }
            }
            Err(_) => {
                let (dead_ms, has_positions, pos_desc) = {
                    let mut st = self.state.lock().unwrap();
                    if st.dead_since.is_none() {
                        st.dead_since = Some(Instant::now());
                        log_event(
                            self,
                            "NT8 7890 unresponsive — dead timer started".to_string(),
                        );
                    }
                    let dead_ms = st
                        .dead_since
                        .map(|d| d.elapsed().as_millis() as u64)
                        .unwrap_or(0);
                    let has_positions = !st.last_positions.is_empty();
                    let pos_desc = st
                        .last_positions
                        .iter()
                        .map(|p| format!("{} {} {}", p.account, p.symbol, p.market_position))
                        .collect::<Vec<_>>()
                        .join(", ");
                    (dead_ms, has_positions, pos_desc)
                }; // guard dropped here
                if has_positions && dead_ms > DEAD_AFTER_MS {
                    let reason = format!(
                        "port 7890 dead > {}ms with {} open position(s): {}",
                        DEAD_AFTER_MS,
                        0usize + count_positions(self),
                        pos_desc
                    );
                    log_event(self, format!("KILLSWITCH TRIGGER: {}", reason));
                    let fire_stamp = format!("{} at {}", reason, now_ms());
                    {
                        let mut st = self.state.lock().unwrap();
                        st.flatten_fired = Some(fire_stamp);
                        st.kills += 1;
                    }
                    let arm_live = self.config.arm_live_flatten;

                    if arm_live {
                        match self.tradovate_flatten_all().await {
                            Ok(r) => log_event(self, format!("BROKER FLATTEN OK: {}", r)),
                            Err(e) => log_event(self, format!("BROKER FLATTEN FAILED: {}", e)),
                        }
                    } else {
                        log_event(
                            self,
                            "DRY-RUN: arm_live_flatten=false — would call Tradovate /v1/order/placeorder to offset all positions".to_string(),
                        );
                    }
                }
            }
        }
    }

    /// Net-liq tracker tick for the cushion formula.
    pub async fn track_net_liq_tick(&self) {
        if let Ok(total) = self.fetch_net_liq().await {
            let mut st = self.state.lock().unwrap();
            st.cur_net_liq = total;
            // Peak ratchet (guard against full-account-replace spikes > 50k jump)
            st.peak_net_liq = ratchet_peak(st.peak_net_liq, total);
            if st.peak_net_liq > 0.0 {
                st.cushion = compute_cushion(
                    st.cur_net_liq, st.peak_net_liq, self.config.trailing_limit);
            }
        }
    }

    pub async fn run(&self) {
        log_event(
            self,
            format!(
                "broker_sentinel armed: poll={}ms dead_after={}ms arm_live={} base={} trailing_limit={}",
                POLL_MS,
                DEAD_AFTER_MS,
                self.config.arm_live_flatten,
                self.config.tradovate_base,
                self.config.trailing_limit
            ),
        );
        let watchdog = self.clone();
        let tracker = self.clone();
        let w = tokio::spawn(async move {
            let mut interval = tokio::time::interval(Duration::from_millis(POLL_MS));
            loop {
                interval.tick().await;
                watchdog.tick().await;
            }
        });
        let t = tokio::spawn(async move {
            let mut interval = tokio::time::interval(Duration::from_millis(POLL_MS));
            loop {
                interval.tick().await;
                tracker.track_net_liq_tick().await;
            }
        });
        let _ = tokio::join!(w, t);
    }

    /// Run for a bounded number of polls, then return (for the Gate 3 test).
    pub async fn run_for(&self, polls: u64) {
        for _ in 0..polls {
            self.tick().await;
            self.track_net_liq_tick().await;
            tokio::time::sleep(Duration::from_millis(POLL_MS)).await;
        }
    }

    pub fn snapshot(&self) -> SentinelSnapshot {
        let st = self.state.lock().unwrap();
        SentinelSnapshot {
            dead_ms: st.dead_since.map(|d| d.elapsed().as_millis() as u64).unwrap_or(0),
            open_positions: st.last_positions.len(),
            cushion: st.cushion,
            peak_net_liq: st.peak_net_liq,
            cur_net_liq: st.cur_net_liq,
            kills: st.kills,
            flatten_fired: st.flatten_fired.clone().unwrap_or_default(),
        }
    }
}

#[derive(Debug, Clone, Serialize)]
pub struct SentinelSnapshot {
    pub dead_ms: u64,
    pub open_positions: usize,
    pub cushion: f64,
    pub peak_net_liq: f64,
    pub cur_net_liq: f64,
    pub kills: u64,
    pub flatten_fired: String,
}

pub fn default_positions_cache() -> HashMap<String, Position> {
    HashMap::new()
}

pub async fn run_main() {
    let config = load_config();
    let sentinel = Sentinel::new(config);
    sentinel.run().await;
}

fn load_config() -> SentinelConfig {
    let path = std::path::Path::new(
        &std::env::var("USERPROFILE").unwrap_or_default(),
    )
    .join("Documents")
    .join("NinjaTrader 8")
    .join("RiskGuard")
    .join("sentinel.json");
    if let Ok(raw) = std::fs::read_to_string(&path) {
        if let Ok(cfg) = serde_json::from_str(&raw) {
            return cfg;
        }
    }
    SentinelConfig::default()
}
#[cfg(test)]
mod tests {
    use super::*;

    // ---- cushion formula -------------------------------------------------------------
    // The playbook's worked example, kept as the anchor case: the original playbook
    // shipped `Peak - Limit - Current`, which grows MORE positive as you lose money and
    // would therefore never breach. These tests pin the corrected direction.

    #[test]
    fn cushion_matches_the_hand_computed_gate3_case() {
        assert_eq!(compute_cushion(104_000.0, 105_000.0, 3_000.0), 2_000.0);
    }

    #[test]
    fn cushion_shrinks_as_equity_falls() {
        let a = compute_cushion(104_000.0, 105_000.0, 3_000.0);
        let b = compute_cushion(103_000.0, 105_000.0, 3_000.0);
        assert!(b < a, "losing money must REDUCE cushion (a={a}, b={b})");
    }

    #[test]
    fn cushion_breaches_at_or_below_zero() {
        // Floor is peak - limit = 102_000. At exactly the floor, cushion is 0 => breach.
        assert_eq!(compute_cushion(102_000.0, 105_000.0, 3_000.0), 0.0);
        assert!(compute_cushion(101_999.0, 105_000.0, 3_000.0) < 0.0);
    }

    #[test]
    fn a_larger_trailing_limit_gives_more_room() {
        let tight = compute_cushion(104_000.0, 105_000.0, 1_000.0);
        let loose = compute_cushion(104_000.0, 105_000.0, 5_000.0);
        assert!(loose > tight);
    }

    // ---- peak ratchet ----------------------------------------------------------------

    #[test]
    fn peak_seeds_from_zero() {
        assert_eq!(ratchet_peak(0.0, 104_000.0), 104_000.0);
    }

    #[test]
    fn peak_rises_on_a_new_high() {
        assert_eq!(ratchet_peak(104_000.0, 104_500.0), 104_500.0);
    }

    #[test]
    fn peak_never_falls() {
        // The whole point of a ratchet: a drawdown must not quietly reset the high-water
        // mark, or the trailing limit follows you down and never breaches.
        assert_eq!(ratchet_peak(105_000.0, 90_000.0), 105_000.0);
    }

    #[test]
    fn peak_refuses_a_jump_of_50k_or_more() {
        // Account-list replacement looks like a sudden +50k. Accepting it would inflate
        // the peak permanently and deflate every later cushion.
        assert_eq!(ratchet_peak(100_000.0, 150_000.0), 100_000.0);
        assert_eq!(ratchet_peak(100_000.0, 149_999.0), 149_999.0); // just under: accepted
    }

    #[test]
    fn peak_jump_guard_boundary_is_exclusive() {
        // `total - peak < 50_000` - exactly 50k is REJECTED. Pinned because a mutant
        // flipping `<` to `<=` is otherwise invisible.
        assert_eq!(ratchet_peak(100_000.0, 150_000.0), 100_000.0);
    }

    // ---- config ----------------------------------------------------------------------

    #[test]
    fn live_flatten_is_disarmed_by_default() {
        // A default that silently arms a real broker flatten is the one default that
        // must never regress.
        assert!(!SentinelConfig::default().arm_live_flatten);
    }
}
