//! Native P&L widget â€” the Chromium-kill for the Fleet P&L HUD.
//!
//! Replaces the Edge/Chrome App-Mode window (300â€“500MB of renderer processes)
//! with a single native egui window fed by the trading_daemon on 8635.
//! Renders: fleet summary bar, accounts table, copier banner, status dot,
//! panic flatten (2-click confirm), per-row close. Order ticket stays
//! browser-only for now (TV in-chart HUD keeps its ticket).

use eframe::egui;
use serde::Deserialize;
use std::time::{Duration, Instant};

const DAEMON: &str = "http://127.0.0.1:8635";

#[derive(Debug, Clone, Deserialize, Default)]
struct Account {
    name: String,
    #[serde(default)]
    provider: String,
    #[serde(default)]
    netLiquidation: f64,
    #[serde(default)]
    realizedPnL: f64,
    #[serde(default)]
    unrealizedPnL: f64,
    #[serde(default)]
    cashValue: f64,
}

#[derive(Debug, Clone, Deserialize, Default)]
struct Position {
    #[serde(default)]
    account: String,
    #[serde(default)]
    symbol: String,
    #[serde(default)]
    marketPosition: String,
    #[serde(default)]
    quantity: f64,
    #[serde(default)]
    unrealizedPnL: f64,
}

#[derive(Debug, Clone, Deserialize, Default)]
struct CopierRow {
    #[serde(default)]
    leaderAccountName: String,
    #[serde(default)]
    followerAccountName: String,
    #[serde(default)]
    isEnabled: bool,
    #[serde(default)]
    verdict: String,
    #[serde(default)]
    enforcing: bool,
    #[serde(default)]
    isQuarantined: bool,
}

#[derive(Debug, Clone, Deserialize, Default)]
struct FleetData {
    #[serde(default)]
    accounts: Vec<Account>,
    #[serde(default)]
    positions: Vec<Position>,
    #[serde(default)]
    copierRows: Vec<CopierRow>,
    #[serde(default)]
    totalNetLiquidation: f64,
    #[serde(default)]
    totalRealizedPnL: f64,
    #[serde(default)]
    totalUnrealizedPnL: f64,
    #[serde(default)]
    activeAccountsCount: i64,
    #[serde(default)]
    totalOpenContracts: i64,
    #[serde(default)]
    activeContracts: String,
    #[serde(default)]
    timestamp: f64,
}

#[derive(Default)]
struct App {
    data: Option<FleetData>,
    last_fetch: Option<Instant>,
    fetch_error: Option<String>,
    panic_armed: bool,
    panic_armed_at: Option<Instant>,
    close_armed: Option<String>,
    close_armed_at: Option<Instant>,
    show_all: bool,
    http: Option<reqwest::Client>,
}

impl App {
    fn fresh(&self) -> bool {
        self.last_fetch
            .map(|t| t.elapsed() < Duration::from_secs(2))
            .unwrap_or(false)
    }

    fn spawn_fetch(&mut self, ctx: &egui::Context) {
        let client = self
            .http
            .get_or_insert_with(|| {
                reqwest::Client::builder()
                    .pool_idle_timeout(Duration::from_secs(90))
                    .tcp_nodelay(true)
                    .build()
                    .unwrap()
            })
            .clone();
        let ctx = ctx.clone();
        tokio::spawn(async move {
            match client
                .get(format!("{}/api/data", DAEMON))
                .timeout(Duration::from_millis(1500))
                .send()
                .await
            {
                Ok(r) => match r.json::<FleetData>().await {
                    Ok(d) => {
                        // Hand the data back to the UI thread on the next frame
                        // via the frame-time callback registry.
                        ctx.request_repaint();
                        { let mut g = DATA.lock().unwrap(); *g = Some(d); }
                    }
                    Err(e) => {
                        { let mut g = FETCH_ERR.lock().unwrap(); *g = Some(e.to_string()); }
                        ctx.request_repaint();
                    }
                },
                Err(e) => {
                    { let mut g = FETCH_ERR.lock().unwrap(); *g = Some(format!("daemon offline: {}", e)); }
                    ctx.request_repaint();
                }
            }
        });
    }
}

// Cross-thread slots (single producer/consumer, polled each frame)
static DATA: std::sync::Mutex<Option<FleetData>> = std::sync::Mutex::new(None);
static FETCH_ERR: std::sync::Mutex<Option<String>> = std::sync::Mutex::new(None);

fn fmt_money(v: f64) -> String {
    if v.abs() >= 1_000_000.0 {
        format!("${:.2}M", v / 1_000_000.0)
    } else if v.abs() >= 10_000.0 {
        format!("${:.1}K", v / 1_000.0)
    } else {
        format!("${:.2}", v)
    }
}

fn fmt_signed(v: f64) -> String {
    let s = if v > 0.0 { "+" } else if v < 0.0 { "-" } else { "" };
    format!("{}{}", s, fmt_money(v.abs()))
}

fn pnl_color(v: f64) -> egui::Color32 {
    if v > 0.0 {
        egui::Color32::from_rgb(38, 166, 91)
    } else if v < 0.0 {
        egui::Color32::from_rgb(239, 83, 80)
    } else {
        egui::Color32::from_rgb(209, 212, 220)
    }
}

impl eframe::App for App {
    fn update(&mut self, ctx: &egui::Context, _frame: &mut eframe::Frame) {
        // Poll every 250ms (native repaint, no browser stack)
        if self.last_fetch.map(|t| t.elapsed() > Duration::from_millis(250)).unwrap_or(true) {
            self.last_fetch = Some(Instant::now());
            self.spawn_fetch(ctx);
        }
        // Drain cross-thread results
        if let Ok(mut g) = DATA.lock() {
            if g.is_some() {
                self.data = g.take();
                self.fetch_error = None;
            }
        }
        if let Ok(mut g) = FETCH_ERR.lock() {
            if g.is_some() {
                self.fetch_error = g.take();
            }
        }

        // 2-click panic confirm expires after 3s
        if let Some(t) = self.panic_armed_at {
            if t.elapsed() > Duration::from_secs(3) {
                self.panic_armed = false;
                self.panic_armed_at = None;
            }
        }
        if let (Some(t), Some(_)) = (self.close_armed_at, self.close_armed.clone()) {
            if t.elapsed() > Duration::from_secs(3) {
                self.close_armed = None;
                self.close_armed_at = None;
            }
        }

        egui::CentralPanel::default()
            .frame(egui::Frame::default().fill(egui::Color32::from_rgb(0x13, 0x17, 0x22)).inner_margin(6.0))
            .show(ctx, |ui| {
                // Header: status dot + title + panic button
                ui.horizontal(|ui| {
                    let (dot, dotcol) = match (&self.data, &self.fetch_error) {
                        (Some(_), None) if self.fresh() => ("â—", egui::Color32::from_rgb(38, 166, 91)),
                        _ => ("â—", egui::Color32::from_rgb(239, 83, 80)),
                    };
                    ui.colored_label(dotcol, dot);
                    ui.strong("Fleet P&L");
                    ui.with_layout(egui::Layout::right_to_left(egui::Align::Center), |ui| {
                        let btn = egui::Button::new(
                            if self.panic_armed {
                                egui::RichText::new("CONFIRM FLATTEN ALL?").color(egui::Color32::WHITE).strong()
                            } else {
                                egui::RichText::new("PANIC FLATTEN").color(egui::Color32::from_rgb(239, 83, 80))
                            },
                        ).fill(if self.panic_armed { egui::Color32::from_rgb(178, 40, 32) } else { egui::Color32::from_rgb(0x2a, 0x2e, 0x39) });
                        if ui.add(btn).clicked() {
                            if self.panic_armed {
                                fire("/api/flatten".to_string());
                                self.panic_armed = false;
                                self.panic_armed_at = None;
                            } else {
                                self.panic_armed = true;
                                self.panic_armed_at = Some(Instant::now());
                            }
                        }
                    });
                });
                ui.separator();

                // Summary bar
                if let Some(d) = &self.data {
                    ui.horizontal_wrapped(|ui| {
                        ui.label(format!("NetLiq {}", fmt_money(d.totalNetLiquidation)));
                        ui.separator();
                        ui.colored_label(pnl_color(d.totalRealizedPnL), format!("Realized {}", fmt_signed(d.totalRealizedPnL)));
                        ui.colored_label(pnl_color(d.totalUnrealizedPnL), format!("Unreal {}", fmt_signed(d.totalUnrealizedPnL)));
                        ui.separator();
                        ui.label(format!("Active {}/{}", d.activeAccountsCount, d.accounts.len()));
                        ui.colored_label(
                            if d.totalOpenContracts > 0 { egui::Color32::from_rgb(255, 213, 79) } else { egui::Color32::from_rgb(0x5d, 0x60, 0x6b) },
                            d.activeContracts.clone(),
                        );
                    });

                    // Copier banner
                    if !d.copierRows.is_empty() {
                        ui.horizontal_wrapped(|ui| {
                            for r in &d.copierRows {
                                let (txt, col) = if r.isQuarantined {
                                    (format!("âš  {}â†’{} QUARANTINE", r.leaderAccountName, r.followerAccountName), egui::Color32::from_rgb(255, 112, 67))
                                } else if !r.enforcing {
                                    (format!("{}â†’{} {}", r.leaderAccountName, r.followerAccountName, r.verdict), egui::Color32::from_rgb(0x5d, 0x60, 0x6b))
                                } else {
                                    (format!("{}â†’{} {}", r.leaderAccountName, r.followerAccountName, r.verdict), egui::Color32::from_rgb(38, 166, 91))
                                };
                                ui.colored_label(col, txt);
                            }
                        });
                    }
                    ui.separator();

                    // Toggle: all accounts vs active only
                    ui.checkbox(&mut self.show_all, "show all accounts (incl. flat)");

                    // Accounts table
                    let mut pos_by_acct: std::collections::HashMap<&str, &Position> = std::collections::HashMap::new();
                    for p in &d.positions {
                        if p.marketPosition != "Flat" {
                            pos_by_acct.insert(p.account.as_str(), p);
                        }
                    }

                    egui::ScrollArea::vertical().show(ui, |ui| {
                        egui::Grid::new("accounts")
                            .num_columns(7)
                            .striped(true)
                            .min_row_height(20.0)
                            .show(ui, |ui| {
                                ui.strong("Account"); ui.strong("Provider"); ui.strong("NetLiq");
                                ui.strong("Realized"); ui.strong("Unreal"); ui.strong("Position"); ui.strong("");
                                ui.end_row();

                                for a in &d.accounts {
                                    let pos = pos_by_acct.get(a.name.as_str()).copied();
                                    let active = a.netLiquidation > 0.0 || a.realizedPnL != 0.0 || a.unrealizedPnL != 0.0 || pos.is_some();
                                    if !self.show_all && !active { continue; }
                                    let nlq = if a.netLiquidation != 0.0 { a.netLiquidation } else { a.cashValue };
                                    ui.label(&a.name);
                                    ui.weak(&a.provider);
                                    ui.label(fmt_money(nlq));
                                    ui.colored_label(pnl_color(a.realizedPnL), fmt_signed(a.realizedPnL));
                                    ui.colored_label(pnl_color(a.unrealizedPnL), fmt_signed(a.unrealizedPnL));
                                    match pos {
                                        Some(p) => {
                                            let dir = if p.marketPosition == "Long" { "â–²" } else { "â–¼" };
                                            let col = if p.marketPosition == "Long" { egui::Color32::from_rgb(38, 166, 91) } else { egui::Color32::from_rgb(239, 83, 80) };
                                            ui.colored_label(col, format!("{} {} {}", dir, p.quantity, p.symbol));
                                            let armed = self.close_armed.as_deref() == Some(a.name.as_str());
                                            let txt = if armed {
                                                egui::RichText::new("sure?").color(egui::Color32::WHITE)
                                            } else {
                                                egui::RichText::new("close").color(egui::Color32::from_rgb(255, 213, 79))
                                            };
                                            let b = egui::Button::new(txt).small();
                                            if ui.add(b).clicked() {
                                                if armed {
                                                    fire("/api/position/close".to_string());
                                                    self.close_armed = None;
                                                } else {
                                                    self.close_armed = Some(a.name.clone());
                                                    self.close_armed_at = Some(Instant::now());
                                                }
                                            }
                                        }
                                        None => { ui.label(""); ui.label(""); }
                                    }
                                    ui.end_row();
                                }
                            });
                    });
                } else if let Some(e) = &self.fetch_error {
                    ui.centered_and_justified(|ui| {
                        ui.colored_label(egui::Color32::from_rgb(239, 83, 80), format!("â— {}", e));
                    });
                } else {
                    ui.centered_and_justified(|ui| ui.label("connecting to daemonâ€¦"));
                }
            });

        ctx.request_repaint_after(Duration::from_millis(250));
    }
}

fn fire(path: String) {
    std::thread::spawn(move || {
        let url = format!("{}{}", DAEMON, path);
        let _ = reqwest::blocking::Client::builder()
            .build()
            .and_then(|c| {
                c.post(&url)
                    .timeout(Duration::from_secs(5))
                    .header("Content-Type", "application/json")
                    .body("{}")
                    .send()
            });
    });
}

fn main() -> eframe::Result {
    let rt = tokio::runtime::Builder::new_multi_thread()
        .enable_all()
        .worker_threads(1)
        .build()
        .expect("tokio rt");

    let options = eframe::NativeOptions {
        viewport: egui::ViewportBuilder::default()
            .with_inner_size([560.0, 680.0])
            .with_min_inner_size([380.0, 300.0])
            .with_always_on_top(),
        ..Default::default()
    };

    rt.block_on(async move {
        eframe::run_native(
            "Fleet P&L Monitor (native)",
            options,
            Box::new(|cc| {
            // Trim fonts: default_fonts bundles emoji + CJK (~40MB mapped).
            // Latin-only at 3 sizes is plenty for this HUD.
            let mut fonts = egui::FontDefinitions::default();
            fonts.families.entry(egui::FontFamily::Proportional).or_default().retain(|f| f != "NotoEmoji-Regular");
            fonts.families.entry(egui::FontFamily::Monospace).or_default().retain(|f| f != "NotoEmoji-Regular");
            cc.egui_ctx.set_fonts(fonts);
            Ok(Box::new(App::default()))
        }),
        )
    })
}
