//! Persistent CDP connection manager for the TradingView in-chart HUD push.
//!
//! Design (replaces the per-push connect/disconnect churn):
//! - One WebSocket to the TV chart target, held open for the process lifetime.
//! - Auto-reconnect with backoff when the socket drops (TV restart / CDP port
//!   gone). Target discovery only runs on (re)connect, not per push.
//! - Pushes are sequential over the single socket (Runtime.evaluate with
//!   incrementing msg ids), driven by a dedicated task fed via an mpsc channel
//!   so the 200ms poller never blocks on TV.
//! - Panic-hook response read stays: each push awaits its own response id.

use crate::poller::{TV_CDP_PORT, js_normalize_json_str};
use futures_util::{SinkExt, StreamExt};
use serde_json::Value;
use std::time::Duration;
use tokio_tungstenite::tungstenite::Message;

pub struct CdpPusher {
    tx: tokio::sync::mpsc::Sender<Value>,
}

impl Clone for CdpPusher {
    fn clone(&self) -> Self {
        Self { tx: self.tx.clone() }
    }
}

impl CdpPusher {
    pub fn spawn() -> Self {
        // Bounded channel: if TV is slow, drop oldest is wrong â€” block the
        // poller is also wrong. Overflow drops NEWEST (the stale tick is
        // superseded anyway); capacity 4 covers bursts.
        let (tx, rx) = tokio::sync::mpsc::channel::<Value>(4);
        tokio::spawn(cdp_loop(rx));
        Self { tx }
    }

    /// Fire-and-forget push; errors (channel closed) ignored â€” the manager
    /// owns recovery.
    pub fn push(&self, payload: Value) {
        let _ = self.tx.try_send(payload);
    }
}

struct CdpConn {
    tx: futures_util::stream::SplitSink<
        tokio_tungstenite::WebSocketStream<
            tokio_tungstenite::MaybeTlsStream<tokio::net::TcpStream>,
        >,
        Message,
    >,
    rx: futures_util::stream::SplitStream<
        tokio_tungstenite::WebSocketStream<
            tokio_tungstenite::MaybeTlsStream<tokio::net::TcpStream>,
        >,
    >,
    next_id: u64,
}

impl CdpConn {
    async fn connect(client: &reqwest::Client) -> Option<CdpConn> {
        // Discover the chart target once per connection.
        let targets: Value = client
            .get(&format!("http://127.0.0.1:{}/json", TV_CDP_PORT))
            .timeout(Duration::from_millis(2000))
            .send()
            .await
            .ok()?
            .json()
            .await
            .ok()?;

        let arr = targets.as_array()?;
        let chart = arr
            .iter()
            .find(|t| {
                t.get("type").and_then(|v| v.as_str()) == Some("page")
                    && t.get("url")
                        .and_then(|v| v.as_str())
                        .map(|u| u.contains("tradingview.com/chart"))
                        .unwrap_or(false)
            })
            .or_else(|| {
                arr.iter()
                    .find(|t| t.get("type").and_then(|v| v.as_str()) == Some("page"))
            })?;

        let ws_url = chart
            .get("webSocketDebuggerUrl")
            .and_then(|v| v.as_str())?
            .to_string();

        let (ws, _) = tokio_tungstenite::connect_async(&ws_url).await.ok()?;
        let (tx, rx) = ws.split();
        Some(CdpConn { tx, rx, next_id: 1 })
    }


    /// One Runtime.evaluate; returns panicRequested from the response.
    async fn evaluate(&mut self, expression: &str) -> Option<bool> {
        use tokio_tungstenite::tungstenite::Message;
        let id = self.next_id;
        self.next_id += 1;
        let call = serde_json::json!({
            "id": id,
            "method": "Runtime.evaluate",
            "params": { "expression": expression, "returnByValue": true }
        });
        if self.tx.send(Message::Text(call.to_string())).await.is_err() {
            return None; // send failed = socket dead
        }
        // Read until OUR id's response arrives (skipping unsolicited events).
        loop {
            match tokio::time::timeout(Duration::from_millis(2000), self.rx.next()).await {
                Ok(Some(Ok(Message::Text(txt)))) => {
                    if let Ok(v) = serde_json::from_str::<Value>(&txt) {
                        if v.get("id").and_then(|i| i.as_u64()) == Some(id) {
                            return Some(
                                v.pointer("/result/value/panicRequested")
                                    .and_then(|p| p.as_bool())
                                    .unwrap_or(false),
                            );
                        }
                        // not our response (an event) â€” keep reading
                    }
                }
                Ok(Some(Ok(_))) => continue, // pong / other frames
                Ok(Some(Err(_))) | Ok(None) => return None, // socket dead
                // TV busy (page loading, heavy chart): response > 2s. The socket
                // itself is fine - keep it, skip this push; the next 200ms poll
                // carries a fresher payload anyway.
                Err(_) => return Some(false),
            }
        }
    }
}

fn build_push_script(payload_str: &str) -> String {
    format!(
        r#"(function() {{
          const panel = document.getElementById('ws-pnl-panel');
          const isPanicRequested = panel && panel.getAttribute('data-panic-flatten');
          if (isPanicRequested) {{
            panel.removeAttribute('data-panic-flatten');
          }}
          if (window.__TV_HUDS__ && typeof window.__TV_HUDS__.update === 'function') {{
            window.__TV_HUDS__.update('account_pnl', {payload});
          }}
          return {{ panicRequested: !!isPanicRequested }};
        }})()"#,
        payload = payload_str
    )
}

async fn cdp_loop(mut rx: tokio::sync::mpsc::Receiver<Value>) {
    let client = crate::state::shared_http();
    let mut conn: Option<CdpConn> = None;
    // Reconnect backoff
    let mut backoff = Duration::from_secs(1);

    loop {
        // Establish connection if needed.
        if conn.is_none() {
            match CdpConn::connect(&client).await {
                Some(c) => {
                    conn = Some(c);
                    backoff = Duration::from_secs(1);
                    println!("[+] CDP pusher connected to TradingView");
                }
                None => {
                    // TV not reachable â€” wait, then retry. Drain pending pushes
                    // so the channel doesn't fill with stale payloads while we
                    // wait; the freshest payload arrives with the next poll.
                    let _ = tokio::time::timeout(backoff, rx.recv()).await;
                    backoff = (backoff * 2).min(Duration::from_secs(15));
                    continue;
                }
            }
        }

        let Some(conn_ref) = conn.as_mut() else { unreachable!() };

        // Wait for the next payload to push.
        let Some(payload) = rx.recv().await else {
            break; // channel closed â€” daemon shutting down
        };

        let payload_str = js_normalize_json_str(
            &serde_json::to_string(&payload).unwrap_or_else(|_| "{}".into()),
        );
        let script = build_push_script(&payload_str);

        match conn_ref.evaluate(&script).await {
            Some(panic_requested) => {
                if panic_requested {
                    crate::state::trigger_emergency_flatten(
                        "TradingView In-Chart HUD".to_string(),
                    )
                    .await;
                }
            }
            None => {
                // Socket died mid-push â€” drop and reconnect next loop.
                println!("[!] CDP socket lost; will reconnect");
                conn = None;
            }
        }
    }
}
