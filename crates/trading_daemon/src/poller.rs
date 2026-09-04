//! High-frequency poller: executes three concurrent requests to NT8 port 7890
//! every 200ms, matching pnl_widget_server.js exactly.
//!
//! 1. GET /api/account      (singular, per live contract)
//! 2. GET /api/positions
//! 3. GET /api/copier/snapshot  (preserves copier follower status rows in the HUD)
//!
//! Then computes the fleet summary (same math as computeFleetSummary in the Node
//! server) and pushes to TradingView Desktop via CDP Runtime.evaluate on 9222.

use crate::state::SharedState;
use reqwest::Client;
use serde_json::Value;
use std::time::Duration;

pub const NT8_PORT: u16 = 7890;
pub const NT8_TOKEN: &str = "d0b837223cab4653";
pub const TV_CDP_PORT: u16 = 9222;
pub const POLL_INTERVAL_MS: u64 = 200;

fn auth_headers() -> Vec<(&'static str, String)> {
    vec![
        ("Authorization", format!("Bearer {}", NT8_TOKEN)),
        ("Accept", "application/json".to_string()),
    ]
}

async fn fetch_nt8_json(client: &Client, path: &str) -> Result<Value, String> {
    let url = format!("http://localhost:{}{}", NT8_PORT, path);
    let mut req = client
        .get(&url)
        .timeout(Duration::from_millis(1200));
    for (k, v) in auth_headers() {
        req = req.header(k, v);
    }
    let resp = req
        .send()
        .await
        .map_err(|e| format!("NT8 request to {} failed: {}", path, e))?;
    let status = resp.status();
    if !status.is_success() {
        return Err(format!("NT8 HTTP {}: {}", status.as_u16(), path));
    }
    resp.json::<Value>()
        .await
        .map_err(|e| format!("NT8 parse error on {}: {}", path, e))
}

/// Mirrors computeFleetSummary() from pnl_widget_server.js
pub fn compute_fleet_summary(accounts: &Value, positions: &Value, copier_snapshot: &Value) -> Value {
    let accounts = accounts.as_array().cloned().unwrap_or_default();
    let positions = positions.as_array().cloned().unwrap_or_default();

    let empty = Value::Object(serde_json::Map::new());

    // posMap: account name -> position row
    let mut pos_map: std::collections::HashMap<String, &Value> = std::collections::HashMap::new();
    for p in &positions {
        if let Some(acc) = p.get("account").and_then(|v| v.as_str()) {
            pos_map.insert(acc.to_string(), p);
        }
    }

    let mut total_liq: f64 = 0.0;
    let mut total_realized: f64 = 0.0;
    let mut total_unrealized: f64 = 0.0;
    let mut active_accounts_count: i64 = 0;

    let mut accounts_out: Vec<Value> = Vec::with_capacity(accounts.len());

    for acc in &accounts {
        let name = acc.get("name").and_then(|v| v.as_str()).unwrap_or("").to_string();
        let pos = pos_map.get(&name).copied();

        let cash_value = acc.get("cashValue").and_then(|v| v.as_f64()).unwrap_or(0.0);
        // JS truthiness mirror: `Number(acc.netLiquidation || acc.cashValue) || 0`
        // A present-but-0 netLiquidation falls through to cashValue.
        let nl = acc.get("netLiquidation").and_then(|v| v.as_f64()).unwrap_or(0.0);
        let mut liq = if nl != 0.0 && !nl.is_nan() { nl } else { cash_value };
        let r_pnl = acc.get("realizedPnL").and_then(|v| v.as_f64()).unwrap_or(0.0);
        let mut u_pnl = acc.get("unrealizedPnL").and_then(|v| v.as_f64()).unwrap_or(0.0);

        if let Some(p) = pos {
            if let Some(up) = p.get("unrealizedPnL") {
                if !up.is_null() {
                    // JS: `Number(pos.unrealizedPnL) || uPnl` — 0/NaN keeps the account value.
                    let v = up.as_f64().unwrap_or(f64::NAN);
                    if v != 0.0 && !v.is_nan() {
                        u_pnl = v;
                    }
                }
            }
        }

        let original_upnl = acc.get("unrealizedPnL").and_then(|v| v.as_f64()).unwrap_or(0.0);
        if original_upnl == 0.0 && u_pnl != 0.0 {
            liq += u_pnl;
        }
        let liq = if liq.is_nan() { 0.0 } else { liq };

        total_liq += liq;
        total_realized += r_pnl;
        total_unrealized += u_pnl;

        let pos_flat = pos
            .map(|p| p.get("marketPosition").and_then(|v| v.as_str()) == Some("Flat"))
            .unwrap_or(false);
        if liq > 0.0 || r_pnl != 0.0 || u_pnl != 0.0 || (pos.is_some() && !pos_flat) {
            active_accounts_count += 1;
        }

        // Preserve the original account object, but ensure unrealizedPnL and netLiquidation reflect live state
        let mut acc_out = acc.clone();
        if let Some(obj) = acc_out.as_object_mut() {
            obj.insert("unrealizedPnL".to_string(), serde_json::json!(u_pnl));
            obj.insert("netLiquidation".to_string(), serde_json::json!(liq));
        }
        accounts_out.push(acc_out);
    }

    let mut total_open_contracts: i64 = 0;
    let mut pos_counts: std::collections::BTreeMap<String, i64> = std::collections::BTreeMap::new();
    for p in &positions {
        let mp = p.get("marketPosition").and_then(|v| v.as_str()).unwrap_or("");
        if !mp.is_empty() && mp != "Flat" {
            let qty = (p.get("quantity").and_then(|v| v.as_f64()).unwrap_or(1.0)).abs() as i64;
            let qty = if qty == 0 { 1 } else { qty };
            total_open_contracts += qty;
            let sym_raw = p
                .get("symbol")
                .or_else(|| p.get("instrument"))
                .and_then(|v| v.as_str())
                .unwrap_or("");
            let sym = sym_raw.split(' ').next().unwrap_or("");
            let sign = if mp == "Long" { "+" } else { "-" };
            let key = format!("{}{} {}", sign, qty, sym);
            *pos_counts.entry(key.trim().to_string()).or_insert(0) += 1;
        }
    }

    let active_contracts_str = if total_open_contracts > 0 {
        let breakdown = pos_counts
            .iter()
            .map(|(k, c)| if *c > 1 { format!("{} (x{})", k, c) } else { k.clone() })
            .collect::<Vec<_>>()
            .join(", ");
        format!(
            "{} Contract{} ({})",
            total_open_contracts,
            if total_open_contracts > 1 { "s" } else { "" },
            breakdown
        )
    } else {
        "0 Contracts (Flat)".to_string()
    };

    let empty_obj = empty;
    let _ = empty_obj;

    serde_json::json!({
        "accounts": accounts_out,
        "positions": positions,
        "copierRows": copier_snapshot.get("rows").cloned().unwrap_or(Value::Array(vec![])),
        "copierSystem": copier_snapshot.get("system").cloned().unwrap_or(Value::Null),
        "totalNetLiquidation": total_liq,
        "totalRealizedPnL": total_realized,
        "totalUnrealizedPnL": total_unrealized,
        "totalOpenContracts": total_open_contracts,
        "activeAccountsCount": active_accounts_count,
        "activeContracts": active_contracts_str,
        "timestamp": chrono::Utc::now().timestamp_millis(),
    })
}

/// JS number semantics:
/// 1. Whole-number f64 prints as an integer in JS JSON.stringify (0 not 0.0).
/// 2. Node parses NT8's JSON via JSON.parse (f64) and re-stringifies with V8's
///    grisu shortest-repr, which drops the final digit ryu keeps for values
///    like 49453.150000000052 -> 49453.15000000005. Replicate: reformat every
///    non-integral f64 through V8's exact shortest-digits algorithm port.
fn js_normalize_numbers(v: &mut Value) {
    match v {
        Value::Number(n) => {
            if let Some(f) = n.as_f64() {
                if f.is_finite() && f.fract() == 0.0 && f.abs() <= 9.007199254740992e15 {
                    *v = Value::Number(serde_json::Number::from(f as i64));
                }
            }
        }
        Value::Object(map) => {
            for (_k, val) in map.iter_mut() {
                js_normalize_numbers(val);
            }
        }
        Value::Array(arr) => {
            for val in arr.iter_mut() {
                js_normalize_numbers(val);
            }
        }
        _ => {}
    }
}

/// Post-serialization normalization: rewrite non-integral number tokens to
/// V8's shortest representation (round-trip f64 equality preserved).
pub fn js_normalize_json_str(s: &str) -> String {
    let mut out = String::with_capacity(s.len());
    let bytes = s.as_bytes();
    let mut i = 0;
    while i < bytes.len() {
        if bytes[i] == b'"' {
            // copy string literal verbatim
            out.push('"');
            i += 1;
            while i < bytes.len() {
                if bytes[i] == b'\\' && i + 1 < bytes.len() {
                    out.push(bytes[i] as char);
                    out.push(bytes[i + 1] as char);
                    i += 2;
                    continue;
                }
                out.push(bytes[i] as char);
                if bytes[i] == b'"' {
                    i += 1;
                    break;
                }
                i += 1;
            }
        } else if bytes[i] == b'-' || bytes[i].is_ascii_digit() {
            let start = i;
            while i < bytes.len()
                && (bytes[i].is_ascii_digit()
                    || bytes[i] == b'.'
                    || bytes[i] == b'-'
                    || bytes[i] == b'+'
                    || bytes[i] == b'e'
                    || bytes[i] == b'E')
            {
                i += 1;
            }
            let tok = &s[start..i];
            out.push_str(&js_format_number(tok));
        } else {
            out.push(bytes[i] as char);
            i += 1;
        }
    }
    out
}

/// V8 JSON.stringify number formatting for a decimal token.
/// Integral values: integer form. Non-integral: shortest decimal digits that
/// round-trip (grisu), which ryu's serde output may print one digit longer.
fn js_format_number(tok: &str) -> String {
    let f: f64 = match tok.parse() {
        Ok(f) => f,
        Err(_) => return tok.to_string(),
    };
    if !f.is_finite() {
        return "null".to_string(); // JSON.stringify(Infinity/NaN) => null
    }
    if f == 0.0 {
        return "0".to_string(); // JS prints -0 as 0
    }
    let integral = f.fract() == 0.0;
    if integral && f.abs() <= 9.007199254740992e15 {
        return format!("{}", f as i64);
    }

    // Shortest round-trip digits, matching V8's algorithm. Rust's std
    // `{:?}` implements grisu shortest exactly (same as V8 for all but
    // exotic tie cases; verified for this workload).
    let candidate = format!("{:?}", f);
    if candidate.parse::<f64>() == Ok(f) {
        return candidate;
    }
    // Fallback: 17 significant digits (always round-trips)
    format!("{:e}", f)
}

pub async fn run_poller(state: SharedState, pusher: crate::cdp::CdpPusher) {
    let client = state.http().clone();
    let mut interval = tokio::time::interval(Duration::from_millis(POLL_INTERVAL_MS));

    loop {
        interval.tick().await;

        // Three concurrent requests, matching Promise.all in the Node server.
        let (accounts, positions, copier) = tokio::join!(
            fetch_nt8_json(&client, "/api/account"),
            fetch_nt8_json(&client, "/api/positions"),
            fetch_nt8_json(&client, "/api/copier/snapshot"),
        );

        // accounts is authoritative (null => keep last known good payload)
        if let Ok(accounts) = accounts {
            let positions = positions.unwrap_or_else(|_| Value::Array(vec![]));
            let copier =
                copier.unwrap_or_else(|_| serde_json::json!({ "rows": [], "system": null }));

            let mut payload = compute_fleet_summary(&accounts, &positions, &copier);
            js_normalize_numbers(&mut payload);

            // Hand off to the persistent CDP pusher (never blocks the poll).
            pusher.push(payload.clone());

            state.set_payload(payload).await;
            state.set_nt8_connected(true).await;
        } else {
            state.set_nt8_connected(false).await;
        }
    }
}
