//! FinancialJuice reverse proxy server with dark-theme injection.
//!
//! Provides same-origin endpoints:
//!   GET /             -> embedded widget HTML
//!   GET /health       -> JSON status
//!   ANY /fjcal/*      -> reverse proxy to feed.financialjuice.com with CSS overrides
//!                        (brightened dark theme + full-width calendar table)

use http_body_util::combinators::BoxBody;
use http_body_util::{BodyExt, Full};
use hyper::body::{Bytes, Incoming};
use hyper::server::conn::http1;
use hyper::service::service_fn;
use hyper::{Request, Response, StatusCode};
use hyper_util::rt::TokioIo;
use once_cell::sync::Lazy;
use std::convert::Infallible;
use std::sync::Arc;

const UPSTREAM: &str = "feed.financialjuice.com";

static WIDGET_HTML: Lazy<String> = Lazy::new(|| {
    include_str!("../assets/fj_widget.html").to_string()
});

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
    let lower = body.to_lowercase();
    if let Some(pos) = lower.find("<head") {
        let gt = body[pos..].find('>').map(|i| pos + i).unwrap_or(pos + 5);
        let mut out = String::with_capacity(body.len() + CAL_OVERRIDE_CSS.len());
        out.push_str(&body[..=gt]);
        out.push_str(CAL_OVERRIDE_CSS);
        out.push_str(&body[gt + 1..]);
        return out.replace(
            "action=\"./ecocal.aspx\"",
            "action=\"/fjcal/widgets/ecocal.aspx\"",
        );
    }
    body
}

async fn proxy_upstream(
    client: Arc<reqwest::Client>,
    req: Request<Incoming>,
) -> Result<Response<BoxBody<Bytes, Infallible>>, Infallible> {
    let upstream_path = req.uri().path().replacen("/fjcal", "", 1);
    let upstream_path = if upstream_path.is_empty() {
        "/".to_string()
    } else {
        upstream_path
    };

    let query_str = req
        .uri()
        .query()
        .map(|q| format!("?{}", q))
        .unwrap_or_default();
    let url = format!("https://{}{}{}", UPSTREAM, upstream_path, query_str);

    let method = match *req.method() {
        hyper::Method::GET => reqwest::Method::GET,
        hyper::Method::POST => reqwest::Method::POST,
        hyper::Method::HEAD => reqwest::Method::HEAD,
        hyper::Method::OPTIONS => reqwest::Method::OPTIONS,
        _ => reqwest::Method::GET,
    };

    let mut builder = client
        .request(method, &url)
        .header("host", UPSTREAM)
        .header("referer", format!("https://{}/", UPSTREAM))
        .header("origin", format!("https://{}", UPSTREAM))
        .header("accept-encoding", "identity");

    for name in ["user-agent", "accept", "accept-language", "cookie"] {
        if let Some(v) = req.headers().get(name) {
            if let Ok(s) = v.to_str() {
                builder = builder.header(name, s);
            }
        }
    }

    match builder.send().await {
        Ok(up_resp) => {
            let status = hyper::StatusCode::from_u16(up_resp.status().as_u16())
                .unwrap_or(StatusCode::OK);
            let headers = up_resp.headers().clone();
            let ctype = headers
                .get("content-type")
                .and_then(|v| v.to_str().ok())
                .unwrap_or("")
                .to_string();

            let bytes = up_resp.bytes().await.unwrap_or_default();
            let is_html = ctype.contains("text/html");

            let (out_body, out_len) = if is_html {
                let text = String::from_utf8_lossy(&bytes).to_string();
                let injected = inject_css(text);
                let len = injected.len();
                (Bytes::from(injected), Some(len))
            } else {
                (bytes.clone(), Some(bytes.len()))
            };

            let mut resp = Response::builder().status(status);
            for h in [
                "content-type",
                "cache-control",
                "expires",
                "date",
                "last-modified",
                "etag",
            ] {
                if let Some(v) = headers.get(h) {
                    if let Ok(s) = v.to_str() {
                        resp = resp.header(h, s);
                    }
                }
            }
            if let Some(l) = out_len {
                resp = resp.header("content-length", l.to_string());
            }
            // Allow same-origin iframe embedding
            resp = resp.header("access-control-allow-origin", "*");
            Ok(resp.body(full(out_body)).unwrap())
        }
        Err(e) => Ok(Response::builder()
            .status(StatusCode::BAD_GATEWAY)
            .header("Content-Type", "text/plain")
            .body(full(format!("Proxy error: {}", e)))
            .unwrap()),
    }
}

async fn handle(
    client: Arc<reqwest::Client>,
    port: u16,
    req: Request<Incoming>,
) -> Result<Response<BoxBody<Bytes, Infallible>>, Infallible> {
    let path = req.uri().path().to_string();

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
        let json = format!(
            r#"{{"status":"ok","widget":"financialjuice","port":{}}}"#,
            port
        );
        return Ok(Response::builder()
            .status(StatusCode::OK)
            .header("Content-Type", "application/json")
            .header("Access-Control-Allow-Origin", "*")
            .body(full(json))
            .unwrap());
    }

    proxy_upstream(client, req).await
}

pub async fn start_proxy_server(port: u16) -> Result<(), Box<dyn std::error::Error + Send + Sync>> {
    let addr: std::net::SocketAddr = format!("127.0.0.1:{}", port).parse()?;
    // A bind failure used to `return Ok(())`. That reported SUCCESS for a proxy that had
    // not started: a second fj_widget would come up, silently fail to bind 8636, and open
    // a window served by the FIRST instance's proxy - an orphan that looks alive.
    // Observed 2026-09-03. Propagate it; the caller decides whether to die.
    let listener = tokio::net::TcpListener::bind(addr).await?;
    serve_on(listener, port).await
}

/// Serve on a listener the caller already bound. Used by `main` so the port check and
/// the bind are the SAME operation - a pre-flight "is 8636 free?" probe followed by a
/// separate bind is a race, and the loser of that race is the silent orphan above.
pub async fn serve_on(
    listener: tokio::net::TcpListener,
    port: u16,
) -> Result<(), Box<dyn std::error::Error + Send + Sync>> {

    let client = Arc::new(reqwest::Client::builder().build()?);

    loop {
        let (stream, _) = match listener.accept().await {
            Ok(conn) => conn,
            Err(_) => continue,
        };
        let client_cloned = Arc::clone(&client);
        tokio::spawn(async move {
            let service = service_fn(move |req| {
                handle(Arc::clone(&client_cloned), port, req)
            });
            let _ = http1::Builder::new()
                .serve_connection(TokioIo::new(stream), service)
                .await;
        });
    }
}
