//! trading_daemon — Rust drop-in replacement for pnl_widget_server.js.
//!
//! Port 8635 is the live contract port; shadow test port 8637 is used during
//! verification (8636 is occupied by fj_widget_server.js).

mod poller;
mod server;
mod state;

use once_cell::sync::Lazy;
use state::SharedState;

pub static WIDGET_HTML: Lazy<String> = Lazy::new(|| {
    match std::fs::read_to_string(concat!(
        env!("CARGO_MANIFEST_DIR"),
        "/assets/widget.html"
    )) {
        Ok(s) => s,
        Err(_) => "<html><body><h1>trading_daemon: widget.html missing</h1></body></html>".to_string(),
    }
});

#[tokio::main]
async fn main() {
    let mut port: u16 = 8635;
    let mut args = std::env::args().skip(1);
    while let Some(arg) = args.next() {
        if arg == "--port" {
            if let Some(p) = args.next() {
                port = p.parse().unwrap_or(8635);
            }
        }
    }

    println!("[+] trading_daemon starting on port {} (shadow mode)", port);

    let state = SharedState::new();

    // Background tasks: 2.5s lockout sweep + 30s guard config reload
    tokio::spawn(state::run_lockout_sweep(state.clone()));
    tokio::spawn(state::run_guard_config_reload(state.clone()));

    // 200ms NT8 poller + CDP push
    tokio::spawn(poller::run_poller(state.clone()));

    if let Err(e) = server::serve(port, state).await {
        eprintln!("[!] server error: {}", e);
        std::process::exit(1);
    }
}