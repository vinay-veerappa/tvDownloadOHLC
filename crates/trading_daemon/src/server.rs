//! Complete HTTP route surface â€” drop-in replacement for pnl_widget_server.js
//! on port 8635 (and shadow port 8637 during verification).
//!
//! Routes:
//!   GET  /health              -> status/port/nt8Connected
//!   GET  /api/data            -> cached 200ms snapshot
//!   POST /api/order/atm       -> proxy to NT8 7890 (confirmLive=true injection)
//!   POST /api/position/close  -> proxy to NT8 7890
//!   POST /api/flatten         -> proxy to NT8 7890 /api/emergency-flatten
//!   GET  /api/lockouts        -> cached lockout statuses
//!   GET  /api/guard/config    -> RiskGuard config.json (cached, 30s reload)
//!   GET  /, /pnl-widget, /index -> HTML widget page

use crate::poller::{NT8_PORT, NT8_TOKEN};
use crate::state::{trigger_emergency_flatten, SharedState};
use http_body_util::combinators::BoxBody;
use http_body_util::{BodyExt, Full};
use hyper::body::{Bytes, Incoming};
use hyper::server::conn::http1;
use hyper::service::service_fn;
use hyper_util::rt::TokioIo;
use hyper::{Request, Response, StatusCode};
use serde_json::{json, Value};
use std::convert::Infallible;



fn full_body<T: Into<Bytes>>(chunk: T) -> BoxBody<Bytes, Infallible> {
    Full::new(chunk.into())
        .map_err(|never| match never {})
        .boxed()
}

fn json_response(status: StatusCode, v: &Value) -> Response<BoxBody<Bytes, Infallible>> {
    let body = crate::poller::js_normalize_json_str(&serde_json::to_string(v).unwrap_or_default());
    Response::builder()
        .status(status)
        .header("Content-Type", "application/json")
        .header("Access-Control-Allow-Origin", "*")
        .header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        .header("Access-Control-Allow-Headers", "Content-Type, Authorization")
        .body(full_body(body))
        .unwrap()
}

async fn proxy_to_nt8(state: &SharedState, endpoint_path: &str, body_json: &str) -> (u16, Value) {
    let client = state.http().clone();
    let res = client
        .post(&format!("http://localhost:{}{}", NT8_PORT, endpoint_path))
        .header("Authorization", format!("Bearer {}", NT8_TOKEN))
        .header("Content-Type", "application/json")
        .timeout(std::time::Duration::from_secs(5))
        .body(body_json.to_string())
        .send()
        .await;

    match res {
        Ok(resp) => {
            let status = resp.status().as_u16();
            let txt = resp.text().await.unwrap_or_default();
            match serde_json::from_str::<Value>(&txt) {
                Ok(v) => (status, v),
                Err(_) => (status, json!({ "error": truncate(&txt, 300) })),
            }
        }
        Err(e) => (502, json!({ "error": format!("NT8 bridge: {}", e) })),
    }
}

fn truncate(s: &str, n: usize) -> String {
    if s.len() > n {
        s[..n].to_string()
    } else {
        s.to_string()
    }
}

async fn read_body(req: Request<Incoming>) -> String {
    let mut body = String::new();
    if let Ok(bytes) = req.into_body().collect().await {
        body.push_str(&String::from_utf8_lossy(&bytes.to_bytes()));
    }
    // Node destroyed bodies > 10000 bytes; mirror the cap.
    if body.len() > 10000 {
        body.truncate(10000);
    }
    body
}

async fn handle(
    req: Request<Incoming>,
    state: SharedState,
    port: u16,
) -> Result<Response<BoxBody<Bytes, Infallible>>, Infallible> {
    let method = req.method().clone();
    let path = req.uri().path().to_string();

    // CORS + OPTIONS preflight (mirrors Node server)
    if method == hyper::Method::OPTIONS {
        return Ok(Response::builder()
            .status(StatusCode::NO_CONTENT)
            .header("Access-Control-Allow-Origin", "*")
            .header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
            .header("Access-Control-Allow-Headers", "Content-Type, Authorization")
            .body(full_body(""))
            .unwrap());
    }

    match (&method, path.as_str()) {
        (&hyper::Method::GET, "/health") => {
            let payload = state.payload().await;
            let connected = state.nt8_connected().await;
            let accounts_count = payload
                .as_ref()
                .and_then(|p| p.get("accounts"))
                .and_then(|a| a.as_array())
                .map(|a| a.len())
                .unwrap_or(0);
            let active = payload
                .as_ref()
                .and_then(|p| p.get("activeContracts"))
                .and_then(|v| v.as_str())
                .unwrap_or("Flat");
            Ok(json_response(
                StatusCode::OK,
                &json!({
                    "status": "ok",
                    "port": port,
                    "nt8Connected": connected || payload.is_some(),
                    "accountsCount": accounts_count,
                    "activePositions": active,
                }),
            ))
        }
        (&hyper::Method::GET, "/api/data") => match state.payload().await {
            Some(p) => Ok(json_response(StatusCode::OK, &p)),
            None => Ok(json_response(
                StatusCode::SERVICE_UNAVAILABLE,
                &json!({ "error": "NT8 bridge connecting or offline" }),
            )),
        },
        (&hyper::Method::POST, "/api/flatten") => {
            let result = trigger_emergency_flatten("Standalone Desktop Widget".to_string()).await;
            Ok(json_response(StatusCode::OK, &result))
        }
        (&hyper::Method::POST, "/api/order/atm") => {
            let body = read_body(req).await;
            let body = inject_confirm_live(&body);
            println!("[ORDER ATM REQ] {}", body);
            let (status, resp) = proxy_to_nt8(&state, "/api/order/atm", &body).await;
            println!("[ORDER ATM RESP] {} {}", status, resp);
            Ok(json_response(StatusCode::from_u16(status).unwrap_or(StatusCode::BAD_GATEWAY), &resp))
        }
        (&hyper::Method::POST, "/api/position/close") => {
            let body = read_body(req).await;
            println!("[POSITION CLOSE REQ] {}", body);
            let (status, resp) = proxy_to_nt8(&state, "/api/position/close", &body).await;
            println!("[POSITION CLOSE RESP] {} {}", status, resp);
            Ok(json_response(StatusCode::from_u16(status).unwrap_or(StatusCode::BAD_GATEWAY), &resp))
        }
        (&hyper::Method::GET, "/api/guard/config") => {
            Ok(json_response(StatusCode::OK, &state.guard_config().await))
        }
        (&hyper::Method::GET, "/api/lockouts") => {
            let cache = state.lockouts().await;
            let mut out = serde_json::Map::new();
            for (k, v) in cache {
                out.insert(k, json!(v.is_locked_out));
            }
            Ok(json_response(StatusCode::OK, &Value::Object(out)))
        }
        _ if method == hyper::Method::GET
            && (path == "/" || path.starts_with("/pnl-widget") || path.starts_with("/index")) =>
        {
            Ok(Response::builder()
                .status(StatusCode::OK)
                .header("Content-Type", "text/html; charset=utf-8")
                .header("Access-Control-Allow-Origin", "*")
                .body(full_body(crate::WIDGET_HTML.as_bytes()))
                .unwrap())
        }
        _ => Ok(Response::builder()
            .status(StatusCode::NOT_FOUND)
            .body(full_body("Not Found"))
            .unwrap()),
    }
}

fn inject_confirm_live(body: &str) -> String {
    // Mirror Node: inject confirmLive=true only when the key is absent.
    match serde_json::from_str::<Value>(body) {
        Ok(Value::Object(mut map)) => {
            if !map.contains_key("confirmLive") {
                map.insert("confirmLive".to_string(), json!(true));
            }
            serde_json::to_string(&Value::Object(map)).unwrap_or_else(|_| body.to_string())
        }
        _ => body.to_string(),
    }
}

pub async fn serve(port: u16, state: SharedState) -> std::io::Result<()> {
    let addr: std::net::SocketAddr = format!("127.0.0.1:{}", port).parse().unwrap();
    let listener = tokio::net::TcpListener::bind(addr).await?;

    println!("[+] Unified Real-time P&L Engine running at http://127.0.0.1:{}", port);

    loop {
        let (stream, _) = listener.accept().await?;
        let state = state.clone();
        tokio::spawn(async move {
            let service = service_fn(move |req| handle(req, state.clone(), port));
            let _ = http1::Builder::new()
                .serve_connection(TokioIo::new(stream), service)
                .await;
        });
    }
}
