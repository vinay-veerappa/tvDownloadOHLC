//! Shared state: the cached 200ms snapshot, lockout cache, guard config, and
//! background-task wiring (2.5s lockout sweep, 30s config reload).

use serde_json::{json, Value};
use std::sync::Arc;
use tokio::sync::RwLock;

pub const NT8_PORT: u16 = 7890;
pub const NT8_TOKEN: &str = "d0b837223cab4653";

#[derive(Clone)]
pub struct SharedState(Arc<Inner>);

struct Inner {
    payload: RwLock<Option<Value>>,
    nt8_connected: RwLock<bool>,
    lockouts: RwLock<std::collections::HashMap<String, LockoutEntry>>,
    guard_config: RwLock<Value>,
    guard_config_path: RwLock<String>,
}

#[derive(Clone)]
pub struct LockoutEntry {
    pub is_locked_out: bool,
    pub checked_at: i64,
}

impl SharedState {
    pub fn new() -> Self {
        Self(Arc::new(Inner {
            payload: RwLock::new(None),
            nt8_connected: RwLock::new(false),
            lockouts: RwLock::new(std::collections::HashMap::new()),
            guard_config: RwLock::new(json!({
                "mode": "unknown", "allowedRoots": [], "blockedRoots": [],
                "instrumentLimits": {}, "maxPerAccount": null,
                "loaded": false, "error": null, "loadedAt": null
            })),
            guard_config_path: RwLock::new(default_guard_config_path()),
        }))
    }

    pub async fn set_payload(&self, v: Value) {
        *self.0.payload.write().await = Some(v);
    }

    pub async fn payload(&self) -> Option<Value> {
        self.0.payload.read().await.clone()
    }

    pub async fn set_nt8_connected(&self, v: bool) {
        *self.0.nt8_connected.write().await = v;
    }

    pub async fn nt8_connected(&self) -> bool {
        *self.0.nt8_connected.read().await
    }

    pub async fn set_lockout(&self, account: String, entry: LockoutEntry) {
        self.0.lockouts.write().await.insert(account, entry);
    }

    pub async fn lockouts(&self) -> std::collections::HashMap<String, LockoutEntry> {
        self.0.lockouts.read().await.clone()
    }

    pub async fn set_guard_config(&self, v: Value) {
        *self.0.guard_config.write().await = v;
    }

    pub async fn guard_config(&self) -> Value {
        self.0.guard_config.read().await.clone()
    }

    pub async fn set_guard_config_path(&self, p: String) {
        *self.0.guard_config_path.write().await = p;
    }

    async fn guard_config_path(&self) -> String {
        self.0.guard_config_path.read().await.clone()
    }
}

pub fn default_guard_config_path() -> String {
    let userprofile = std::env::var("USERPROFILE").unwrap_or_default();
    std::path::Path::new(&userprofile)
        .join("Documents")
        .join("NinjaTrader 8")
        .join("RiskGuard")
        .join("config.json")
        .to_string_lossy()
        .to_string()
}

/// 30s interval reload: refreshes RiskGuard config.json
pub async fn run_guard_config_reload(state: SharedState) {
    let mut interval = tokio::time::interval(std::time::Duration::from_secs(30));
    loop {
        interval.tick().await;
        let path = state.guard_config_path().await;
        match tokio::fs::read_to_string(&path).await {
            Ok(raw) => match serde_json::from_str::<Value>(&raw) {
                Ok(cfg) => {
                    let out = json!({
                        "mode": cfg.get("Mode").and_then(|m| m.as_str()).unwrap_or("unknown"),
                        "allowedRoots": cfg.get("AllowedInstruments").cloned().unwrap_or(json!([])),
                        "blockedRoots": cfg.get("BlockedInstruments").cloned().unwrap_or(json!([])),
                        "instrumentLimits": cfg.get("InstrumentLimits").cloned().unwrap_or(json!({})),
                        "maxPerAccount": cfg.pointer("/Sizing/MaxContractsPerAccount").cloned().unwrap_or(Value::Null),
                        "loaded": true,
                        "error": Value::Null,
                        "loadedAt": chrono::Utc::now().timestamp_millis(),
                    });
                    state.set_guard_config(out).await;
                }
                Err(e) => {
                    let mut cur = state.guard_config().await;
                    cur["loaded"] = json!(false);
                    cur["error"] = json!(e.to_string());
                    cur["loadedAt"] = json!(chrono::Utc::now().timestamp_millis());
                    state.set_guard_config(cur).await;
                }
            },
            Err(e) => {
                let mut cur = state.guard_config().await;
                cur["loaded"] = json!(false);
                cur["error"] = json!(e.to_string());
                cur["loadedAt"] = json!(chrono::Utc::now().timestamp_millis());
                state.set_guard_config(cur).await;
            }
        }
    }
}

/// 2.5s interval sweep: evaluates account lockouts, POSTs to /api/lockout.
/// Caps at 30 accounts, refreshes entries older than 10s — mirrors Node.
pub async fn run_lockout_sweep(state: SharedState) {
    let client = reqwest::Client::new();
    let mut interval = tokio::time::interval(std::time::Duration::from_millis(2500));
    loop {
        interval.tick().await;
        let payload = state.payload().await;
        let Some(payload) = payload else { continue };
        let Some(accounts) = payload.get("accounts").and_then(|a| a.as_array()) else {
            continue;
        };

        let names: Vec<String> = accounts
            .iter()
            .take(30)
            .filter_map(|a| a.get("name").and_then(|n| n.as_str()).map(|s| s.to_string()))
            .collect();

        let now_ms = chrono::Utc::now().timestamp_millis();
        let cache = state.lockouts().await;
        let stale: Vec<String> = names
            .into_iter()
            .filter(|a| {
                cache
                    .get(a)
                    .map(|c| now_ms - c.checked_at > 10_000)
                    .unwrap_or(true)
            })
            .collect();

        let mut futs = Vec::with_capacity(stale.len());
        for account in stale {
            let state = state.clone();
            let client = client.clone();
            futs.push(tokio::spawn(async move {
                let body = json!({ "action": "status", "account": account });
                let res = client
                    .post(&format!("http://localhost:{}/api/lockout", NT8_PORT))
                    .header("Authorization", format!("Bearer {}", NT8_TOKEN))
                    .header("Content-Type", "application/json")
                    .timeout(std::time::Duration::from_millis(2000))
                    .json(&body)
                    .send()
                    .await;
                if let Ok(resp) = res {
                    if let Ok(v) = resp.json::<Value>().await {
                        let locked = v.get("isLockedOut").and_then(|l| l.as_bool());
                        if let Some(locked) = locked {
                            state
                                .set_lockout(
                                    account.clone(),
                                    LockoutEntry {
                                        is_locked_out: locked,
                                        checked_at: chrono::Utc::now().timestamp_millis(),
                                    },
                                )
                                .await;
                        }
                    }
                }
            }));
        }
        for f in futs {
            let _ = f.await;
        }
    }
}

/// Fire the NT8 emergency flatten endpoint (panic hook from HUD / widget).
pub async fn trigger_emergency_flatten(source: String) -> Value {
    let client = reqwest::Client::new();
    let body = json!({ "reason": format!("Operator Panic Flatten ({})", source) });
    let res = client
        .post(&format!("http://localhost:{}/api/emergency-flatten", NT8_PORT))
        .header("Authorization", format!("Bearer {}", NT8_TOKEN))
        .header("Content-Type", "application/json")
        .timeout(std::time::Duration::from_secs(3))
        .json(&body)
        .send()
        .await;
    match res {
        Ok(resp) => {
            let status = resp.status().as_u16();
            match resp.json::<Value>().await {
                Ok(v) => json!({ "status": "ok", "statusCode": status, "body": v }),
                Err(_) => json!({ "status": "sent", "statusCode": status }),
            }
        }
        Err(e) => json!({ "error": e.to_string() }),
    }
}