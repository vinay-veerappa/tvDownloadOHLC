//! FinancialJuice Squawk & News Native Desktop Widget (Rust).
//!
//! Replaces msedge.exe --app=... and Node.js proxy with a single, standalone
//! native Rust executable (fj_widget.exe).
//!
//! Features:
//! - Embedded WebView2 renderer (wry + tao) with hardware acceleration.
//! - Autoplay enabled (--autoplay-policy=no-user-gesture-required) for Live Audio Squawk.
//! - Always-on-top floating desktop window (toggleable via UI or flag).
//! - In-process HTTP reverse proxy on 127.0.0.1:8636 serving the dark-theme
//!   HUD and injecting CSS overrides into the Economic Calendar (/fjcal/...).
//! - Dual-mode: Standalone desktop app (default) or --daemon-only / --headless.

#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

mod proxy;

use std::sync::atomic::{AtomicBool, Ordering};
use std::sync::Arc;
use tao::dpi::LogicalSize;
use tao::event::{Event, WindowEvent};
use tao::event_loop::{ControlFlow, EventLoop};
use tao::window::{Theme, WindowBuilder};
use wry::WebViewBuilder;

const DEFAULT_PORT: u16 = 8636;
const DEFAULT_WIDTH: f64 = 520.0;
const DEFAULT_HEIGHT: f64 = 680.0;

fn main() -> Result<(), Box<dyn std::error::Error>> {
    let args: Vec<String> = std::env::args().collect();
    let mut port = DEFAULT_PORT;
    let mut width = DEFAULT_WIDTH;
    let mut height = DEFAULT_HEIGHT;
    let mut daemon_only = false;
    let mut frameless = false;
    let mut start_pinned = true;

    let mut i = 1;
    while i < args.len() {
        match args[i].as_str() {
            "--port" => {
                if i + 1 < args.len() {
                    port = args[i + 1].parse().unwrap_or(DEFAULT_PORT);
                    i += 1;
                }
            }
            "--width" => {
                if i + 1 < args.len() {
                    width = args[i + 1].parse().unwrap_or(DEFAULT_WIDTH);
                    i += 1;
                }
            }
            "--height" => {
                if i + 1 < args.len() {
                    height = args[i + 1].parse().unwrap_or(DEFAULT_HEIGHT);
                    i += 1;
                }
            }
            "--daemon-only" | "--headless" => {
                daemon_only = true;
            }
            "--frameless" => {
                frameless = true;
            }
            "--no-pin" => {
                start_pinned = false;
            }
            _ => {}
        }
        i += 1;
    }

    // Set Web Audio autoplay policy before WebView2 initialization
    std::env::set_var(
        "WEBVIEW2_ADDITIONAL_BROWSER_ARGUMENTS",
        "--autoplay-policy=no-user-gesture-required",
    );

    // If running in daemon-only mode, run the Tokio runtime on the main thread
    if daemon_only {
        let rt = tokio::runtime::Builder::new_multi_thread()
            .enable_all()
            .build()?;
        rt.block_on(async move {
            let _ = proxy::start_proxy_server(port).await;
        });
        return Ok(());
    }

    // Spawn the in-process reverse proxy in a background thread
    let server_port = port;
    std::thread::spawn(move || {
        let rt = tokio::runtime::Builder::new_multi_thread()
            .enable_all()
            .build()
            .expect("failed to start tokio runtime for proxy");
        rt.block_on(async move {
            let _ = proxy::start_proxy_server(server_port).await;
        });
    });

    std::thread::sleep(std::time::Duration::from_millis(80));

    // Native Desktop Window via Tao
    let event_loop = EventLoop::new();
    let window = Arc::new(
        WindowBuilder::new()
            .with_title("FinancialJuice Squawk & News")
            .with_inner_size(LogicalSize::new(width, height))
            .with_min_inner_size(LogicalSize::new(320.0, 220.0))
            .with_always_on_top(start_pinned)
            .with_theme(Some(Theme::Dark))
            .with_decorations(!frameless)
            .with_resizable(true)
            .with_visible(true)
            .build(&event_loop)?,
    );

    let is_pinned = Arc::new(AtomicBool::new(start_pinned));
    let window_for_ipc = Arc::clone(&window);
    let is_pinned_for_ipc = Arc::clone(&is_pinned);

    let widget_url = format!("http://127.0.0.1:{}/fj-widget", port);

    // Build the embedded WebView2
    let webview = WebViewBuilder::new()
        .with_url(&widget_url)
        .with_ipc_handler(move |req| {
            let body = req.body().trim();
            match body {
                "close" => {
                    std::process::exit(0);
                }
                "minimize" => {
                    window_for_ipc.set_minimized(true);
                }
                "drag_window" => {
                    let _ = window_for_ipc.drag_window();
                }
                "toggle_pin" => {
                    let current = is_pinned_for_ipc.load(Ordering::Relaxed);
                    let new_state = !current;
                    is_pinned_for_ipc.store(new_state, Ordering::Relaxed);
                    window_for_ipc.set_always_on_top(new_state);
                }
                _ => {}
            }
        })
        .build(&*window)?;

    // Run the native Windows event loop
    event_loop.run(move |event, _, control_flow| {
        let _keep_alive = &webview;
        *control_flow = ControlFlow::Wait;

        match event {
            Event::WindowEvent {
                event: WindowEvent::CloseRequested,
                ..
            } => {
                *control_flow = ControlFlow::Exit;
            }
            _ => (),
        }
    });
}
