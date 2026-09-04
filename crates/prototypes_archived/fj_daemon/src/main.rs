//! FinancialJuice widget server — Rust replacement for fj_widget_server.js.
//!
//! Same contract on port 8636:
//!   GET /            -> the FJ widget page (embedded HTML asset)
//!   GET /health      -> { status, widget, port }
//!   ANY /fjcal/*     -> reverse proxy to feed.financialjuice.com with CSS
//!                       injection (dark theme + full-width calendar)
//!   everything else  -> proxy upstream unchanged (relative assets/signalr)
//!
//! The widget content is FinancialJuice's own embed (iframes + SignalR),
//! rendered in the browser App-Mode window; only the SERVER moved to Rust.

use http_body_util::combinators::BoxBody;
use http_body_util::{BodyExt, Full};
use hyper::body::{Bytes, Incoming};
use hyper::server::conn::http1;
use hyper::service::service_fn;
use hyper::{Request, Response, StatusCode};
use hyper_util::rt::TokioIo;
use once_cell::sync::Lazy;
use std::convert::Infallible;

const UPSTREAM: &str = "feed.financialjuice.com";

static WIDGET_HTML: Lazy<String> = Lazy::new(|| {
    std::fs::read_to_string(concat!(env!("CARGO_MANIFEST_DIR"), "/assets/fj_widget.html"))
        .unwrap_or_else(|_| {
            "<html><body><h1>fj_daemon: fj_widget.html missing</h1></body></html>".to_string()
        })
});

/// CSS injected into the proxied econ calendar page (dark theme + full width),
/// identical to CAL_OVERRIDE_CSS in fj_widget_server.js.
const CAL_OVERRIDE_CSS: &str = r#"
    <style id="ws-fj-cal-override">
    body { background: #131722 !important; color: #c9cfdb !important; }
    #comingUp, #comingUp-parent, #my-cal-data, .calendar-header,
    #calendar, #calendar-history, #calendar-filters-container {
      width: 100% !important;
      max-width: 100% !important;
      background-color: #131722 !important;
    }
    .div-table-col, .div-table-colspan, .event-title, .event-title a,
    .event-time, .event-actual, .event-forcast, .event-previous,
    .event-strong-data, .event-weak-data, .cal-event-date {
      color: #c9cfdb !important;
    }
    .event-title a:hover { color: #f0f3fa !important; }
    .calendar-header { background-color: #1e222d !important; }
    .calendar-header .div-table-col { color: #f0f3fa !important; font-weight: 700; }
    .event-flag { width: 24px !important; }
    .event-flag img, .event-flag svg { max-width: 100%; }
    .event-history a, .event-history i { color: #5d606b !important; }
    </style>"#;

fn full<T: Into<Bytes>>(b: T) -> BoxBody<Bytes, Infallible> {
    Full::new(b.into()).map_err(|never| match never {}).boxed()
}

fn inject_css(body: String) -> String {
    // Node: replace(/<head([^>]*)>/i, `<head$1>${CSS}`)
    let lower = body.to_lowercase();
    if let Some(pos) = lower.find("<head") {
        let gt = body[pos..].find('>').map(|i| pos + i).unwrap_or(pos + 5);
        let mut out = String::with_capacity(body.len() + CAL_OVERRIDE_CSS.len());
        out.push_str(&body[..=gt]);
        out.push_str(CAL_OVERRIDE_CSS);
        out.push_str(&body[gt + 1..]);
        // fix postback action targets
        return out.replace(
            "action=\"./ecocal.aspx\"",
            "action=\"/fjcal/widgets/ecocal.aspx\"",
        );
    }
    body
}

async fn proxy_upstream(req: Request<Incoming>) -> Result<Response<BoxBody<Bytes, Infallible>>, Infallible> {
    let upstream_path = req.uri().path().replacen("/fjcal", "", 1);
    let upstream_path = if upstream_path.is_empty() { "/".to_string() } else { upstream_path };

    let client = hyper_util::client::legacy::Client::builder(TokioExecutor)
        .build_http();
    // Build upstream request: copy method + a few headers, set host/referer/origin.
    let uri: hyper::Uri = format!("https://{}{}", UPSTREAM, upstream_path)
        .parse()
        .unwrap();
    let mut builder = hyper::Request::builder()
        .method(req.method().clone())
        .uri(uri);
    builder = builder
        .header("host", UPSTREAM)
        .header("referer", format!("https://{}/", UPSTREAM))
        .header("origin", format!("https://{}", UPSTREAM))
        .header("accept-encoding", "identity");
    for name in ["user-agent", "accept", "accept-language", "cookie"] {
        if let Some(v) = req.headers().get(name) {
            builder = builder.header(name, v.clone());
        }
    }

    let upstream_req = match builder.body(empty_body()) {
        Ok(r) => r,
        Err(_) => return Ok(err_502("bad request")),
    };

    match client.request(upstream_req).await {
        Ok(up) => {
            let status = up.status();
            let headers = up.headers().clone();
            let ctype = headers
                .get("content-type")
                .and_then(|v| v.to_str().ok())
                .unwrap_or("")
                .to_string();
            let body_bytes = http_body_util::BodyExt::collect(up)
                .await
                .map(|c| c.to_bytes())
                .unwrap_or_default();

            let is_html = ctype.contains("text/html");
            let (out_body, out_len) = if is_html {
                let injected = inject_css(String::from_utf8_lossy(&body_bytes).to_string());
                let len = injected.len();
                (Bytes::from(injected), Some(len))
            } else {
                (body_bytes.clone(), Some(body_bytes.len()))
            };

            let mut resp = Response::builder().status(status);
            for h in ["content-type", "cache-control", "expires", "date", "last-modified", "etag"] {
                if let Some(v) = headers.get(h) {
                    resp = resp.header(h, v);
                }
            }
            if let Some(l) = out_len {
                resp = resp.header("content-length", l.to_string());
            }
            // strip x-frame-options / CSP so the embed works same-origin
            Ok(resp.body(full(out_body)).unwrap())
        }
        Err(e) => Ok(err_502(&e.to_string())),
    }
}

fn empty_body() -> BoxBody<Bytes, Infallible> {
    Full::new(Bytes::new()).map_err(|never| match never {}).boxed()
}

fn err_502(msg: &str) -> Response<BoxBody<Bytes, Infallible>> {
    Response::builder()
        .status(StatusCode::BAD_GATEWAY)
        .header("Content-Type", "text/plain")
        .body(full(format!("Proxy error: {}", msg)))
        .unwrap()
}

#[derive(Clone)]
struct TokioExecutor;

impl<F> hyper::rt::Executor<F> for TokioExecutor
where
    F: std::future::Future + Send + 'static,
    F::Output: Send + 'static,
{
    fn execute(&self, fut: F) {
        tokio::spawn(fut);
    }
}

async fn handle(req: Request<Incoming>) -> Result<Response<BoxBody<Bytes, Infallible>>, Infallible> {
    let path = req.uri().path().to_string();

    // CORS preflight
    if req.method() == hyper::Method::OPTIONS {
        return Ok(Response::builder()
            .status(StatusCode::NO_CONTENT)
            .header("Access-Control-Allow-Origin", "*")
            .header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
            .header("Access-Control-Allow-Headers", "Content-Type")
            .body(full(""))
            .unwrap());
    }

    if path == "/" || path.starts_with("/fj-widget") || path.starts_with("/index") {
        return Ok(Response::builder()
            .status(StatusCode::OK)
            .header("Content-Type", "text/html; charset=utf-8")
            .header("Access-Control-Allow-Origin", "*")
            .body(full(WIDGET_HTML.as_bytes()))
            .unwrap());
    }
    if path == "/health" {
        return Ok(Response::builder()
            .status(StatusCode::OK)
            .header("Content-Type", "application/json")
            .body(full(r#"{"status":"ok","widget":"financialjuice","port":8636}"#))
            .unwrap());
    }
    // everything else -> upstream (root paths proxy too, matching Node)
    proxy_upstream(req).await
}

#[tokio::main]
async fn main() {
    let addr: std::net::SocketAddr = "127.0.0.1:8636".parse().unwrap();
    let listener = tokio::net::TcpListener::bind(addr).await.expect("bind 8636");
    println!("[+] FinancialJuice widget (Rust) running at http://127.0.0.1:8636/fj-widget");
    println!("[+] Econ Calendar proxied same-origin at http://127.0.0.1:8636/fjcal/widgets/ecocal.aspx");
    loop {
        let (stream, _) = listener.accept().await.unwrap();
        tokio::spawn(async move {
            let service = service_fn(handle);
            let _ = http1::Builder::new()
                .serve_connection(TokioIo::new(stream), service)
                .await;
        });
    }
}