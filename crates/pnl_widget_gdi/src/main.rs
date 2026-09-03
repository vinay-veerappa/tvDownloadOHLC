//! Fleet P&L Widget Shell — native Win32 GDI, Rust.
//!
//! One always-on-top shell with tabs: P&L | Copier | Risk.
//! Data: trading_daemon :8635 (/api/data, /api/lockouts, /api/guard/config).
//! Actions: /api/order/atm (B/S), /api/position/close (C), /api/flatten (panic)
//! — identical payloads to the original HTML widget (confirmLive + idempotency).
//!
//! Visual language matches account_pnl.js CSS. Double-buffered, flicker-free.

#![windows_subsystem = "windows"]

use serde::Deserialize;
use std::sync::atomic::{AtomicIsize, Ordering};
use std::sync::Mutex;
use std::time::Duration;
use winapi::shared::minwindef::*;
use winapi::shared::windef::*;
use winapi::um::libloaderapi::GetModuleHandleA;
use winapi::um::wingdi::*;
use winapi::um::winuser::*;
use std::ptr::null_mut;

const DAEMON: &str = "http://127.0.0.1:8635";
const POLL_MS: u64 = 250;
const LOCKOUT_POLL_MS: u64 = 3000;
const CONFIG_POLL_MS: u64 = 30_000;

const IDC_SYMBOL: i32 = 2001;
const IDC_QTY: i32 = 2002;
const IDC_ATM: i32 = 2003;
const IDC_STOP: i32 = 2004;
const IDC_TARGET: i32 = 2005;

// ---------------------------------------------------------------- data model
#[derive(Debug, Clone, Deserialize, Default)]
struct Account {
    #[serde(default)] name: String,
    #[serde(default)] provider: String,
    #[serde(default)] netLiquidation: f64,
    #[serde(default)] realizedPnL: f64,
    #[serde(default)] unrealizedPnL: f64,
    #[serde(default)] cashValue: f64,
}

#[derive(Debug, Clone, Deserialize, Default)]
struct Position {
    #[serde(default)] account: String,
    #[serde(default)] symbol: String,
    #[serde(default)] marketPosition: String,
    #[serde(default)] quantity: f64,
    #[serde(default)] avgPrice: f64,
    #[serde(default)] unrealizedPnL: f64,
}

#[derive(Debug, Clone, Deserialize, Default)]
struct CopierRow {
    #[serde(default)] leaderAccountName: String,
    #[serde(default)] followerAccountName: String,
    #[serde(default)] isEnabled: bool,
    #[serde(default)] expectedSide: String,
    #[serde(default)] expectedQuantity: f64,
    #[serde(default)] actualSide: String,
    #[serde(default)] actualQuantity: f64,
    #[serde(default)] isQuarantined: bool,
    #[serde(default)] verdict: String,
    #[serde(default)] enforcing: bool,
}

#[derive(Debug, Clone, Deserialize, Default)]
struct FleetData {
    #[serde(default)] accounts: Vec<Account>,
    #[serde(default)] positions: Vec<Position>,
    #[serde(default)] copierRows: Vec<CopierRow>,
    #[serde(default)] totalNetLiquidation: f64,
    #[serde(default)] totalRealizedPnL: f64,
    #[serde(default)] totalUnrealizedPnL: f64,
    #[serde(default)] activeAccountsCount: i64,
    #[serde(default)] totalOpenContracts: i64,
    #[serde(default)] activeContracts: String,
    #[serde(default)] timestamp: f64,
}

#[derive(Debug, Clone, Deserialize, Default)]
struct GuardConfig {
    #[serde(default)] mode: String,
    #[serde(default, rename = "allowedRoots")] allowed_roots: Vec<String>,
    #[serde(default, rename = "instrumentLimits")] instrument_limits: serde_json::Value,
    #[serde(default, rename = "maxPerAccount")] max_per_account: Option<f64>,
    #[serde(default)] loaded: bool,
}

// ---------------------------------------------------------------- ui state
#[derive(Clone, Copy, PartialEq)]
enum Tab { Pnl, Copier, Risk }

struct UiState {
    data: Option<FleetData>,
    data_at: u64,
    fetch_err: Option<String>,
    lockouts: std::collections::HashMap<String, bool>,
    guard: GuardConfig,
    tab: Tab,
    show_all: bool,
    panic_armed: bool,
    panic_armed_until: u64,
    sort_col: usize,
    sort_asc: bool,
    status: String,
    status_kind: u8,
    close_confirm: Option<String>,
    close_confirm_at: u64,
    busy: std::collections::HashSet<String>,
}

static UI: Mutex<Option<UiState>> = Mutex::new(None);

fn ui() -> std::sync::MutexGuard<'static, Option<UiState>> {
    UI.lock().unwrap()
}

fn with_ui<T>(f: impl FnOnce(&mut UiState) -> T) -> T {
    let mut g = ui();
    if g.is_none() {
        *g = Some(UiState {
            data: None, data_at: 0, fetch_err: None,
            lockouts: std::collections::HashMap::new(),
            guard: GuardConfig::default(),
            tab: Tab::Pnl, show_all: false,
            panic_armed: false, panic_armed_until: 0,
            sort_col: 1, sort_asc: false,
            status: String::new(), status_kind: 0,
            close_confirm: None, close_confirm_at: 0,
            busy: std::collections::HashSet::new(),
        });
    }
    f(g.as_mut().unwrap())
}

fn now_ms() -> u64 {
    std::time::SystemTime::now()
        .duration_since(std::time::UNIX_EPOCH)
        .map(|d| d.as_millis() as u64)
        .unwrap_or(0)
}

static HWND_MAIN: AtomicIsize = AtomicIsize::new(0);

fn invalidate() {
    unsafe { InvalidateRect(HWND_MAIN.load(Ordering::Relaxed) as *mut _, null_mut(), FALSE); }
}

fn set_status(msg: &str, kind: u8) {
    with_ui(|u| {
        u.status = msg.to_string();
        u.status_kind = kind;
    });
}

// ---------------------------------------------------------------- networking
fn fetch_loop() {
    loop {
        let txt = minreq::get(format!("{}/api/data", DAEMON)).with_timeout(2).send();
        let mut ok = false;
        with_ui(|u| {
            match txt {
                Ok(r) => match r.as_str() {
                    Ok(s) => match serde_json::from_str::<FleetData>(s) {
                        Ok(d) => { u.data = Some(d); u.data_at = now_ms(); u.fetch_err = None; ok = true; }
                        Err(e) => u.fetch_err = Some(format!("parse: {}", e)),
                    },
                    Err(e) => u.fetch_err = Some(format!("read: {}", e)),
                },
                Err(e) => u.fetch_err = Some(format!("daemon offline: {}", e)),
            }
        });
        if ok { invalidate(); }
        std::thread::sleep(Duration::from_millis(POLL_MS));
    }
}

fn lockout_loop() {
    loop {
        if let Ok(r) = minreq::get(format!("{}/api/lockouts", DAEMON)).with_timeout(2).send() {
            if let Ok(s) = r.as_str() {
                if let Ok(v) = serde_json::from_str::<std::collections::HashMap<String, bool>>(s) {
                    with_ui(|u| u.lockouts = v);
                    invalidate();
                }
            }
        }
        std::thread::sleep(Duration::from_millis(LOCKOUT_POLL_MS));
    }
}

fn config_loop() {
    loop {
        if let Ok(r) = minreq::get(format!("{}/api/guard/config", DAEMON)).with_timeout(2).send() {
            if let Ok(s) = r.as_str() {
                if let Ok(g) = serde_json::from_str::<GuardConfig>(s) {
                    with_ui(|u| u.guard = g);
                    invalidate();
                }
            }
        }
        std::thread::sleep(Duration::from_millis(CONFIG_POLL_MS));
    }
}

/// Blocking POST, returns (status_code, body).
fn fire(path: &str, body: String) -> (u16, String) {
    match minreq::post(format!("{}{}", DAEMON, path))
        .with_timeout(6)
        .with_header("Content-Type", "application/json")
        .with_body(body)
        .send()
    {
        Ok(r) => {
            let code = r.status_code as u16;
            (code, r.as_str().unwrap_or("").to_string())
        }
        Err(e) => (0, e.to_string()),
    }
}

fn idem() -> String {
    use std::time::{SystemTime, UNIX_EPOCH};
    let t = SystemTime::now().duration_since(UNIX_EPOCH).map(|d| d.as_millis()).unwrap_or(0);
    let mut x = (t ^ 0x9e3779b9) as u32;
    x ^= x << 13; x ^= x >> 17; x ^= x << 5;
    format!("ot-{}-{:x}", t, x)
}

// ---------------------------------------------------------------- formatting
fn fmt_money(v: f64) -> String {
    let sign = if v > 0.0 { "+" } else if v < 0.0 { "-" } else { "" };
    format!("{}${:.2}", sign, v.abs())
}
fn fmt_plain(v: f64) -> String {
    if v.abs() >= 1_000_000.0 { format!("${:.2}M", v / 1_000_000.0) }
    else if v.abs() >= 10_000.0 { format!("${:.1}K", v / 1_000.0) }
    else { format!("${:.2}", v) }
}
fn acc_type(name: &str, provider: &str) -> &'static str {
    let n = name.to_uppercase();
    if n.starts_with("SIM") || provider == "Simulator" { "SIM" }
    else if n.starts_with("LFE") || n.starts_with("LDE") { "LFE" }
    else if n.starts_with("APEX") || n.starts_with("PAAPEX") { "APEX" }
    else if n.starts_with("TAKEPROFIT") { "TPT" }
    else if n.starts_with("TDYG") || n.starts_with("TDFYG") { "TRADEDAY" }
    else { "LIVE" }
}
fn quarterlies() -> Vec<String> {
    let secs = std::time::SystemTime::now()
        .duration_since(std::time::UNIX_EPOCH)
        .map(|d| d.as_secs() as i64)
        .unwrap_or(0);
    let days = secs / 86_400;
    let z = days + 719_468;
    let era = z.div_euclid(146_097);
    let doe = z - era * 146_097;
    let yoe = (doe - doe / 1460 + doe / 36_524 - doe / 146_096) / 365;
    let y = yoe + era * 400;
    let doy = doe - (365 * yoe + yoe / 4 - yoe / 100);
    let mp = (5 * doy + 2) / 153;
    let m = if mp < 10 { mp + 3 } else { mp - 9 };
    let y = if m <= 2 { y + 1 } else { y };
    let m0 = m - 1;
    let yy = |yy_i: i64| format!("{:02}", (yy_i % 100) as i32);
    let mut q: Vec<String> = Vec::new();
    for yi in [y, y + 1] {
        for (mm, code) in [(2i64, "03"), (5, "06"), (8, "09"), (11, "12")] {
            if yi == y && mm < m0 { continue; }
            q.push(format!("{}-{}", code, yy(yi)));
        }
    }
    q.into_iter().take(2).collect()
}

// ---------------------------------------------------------------- theme + fonts
struct Theme {
    bg: COLORREF, header: COLORREF, card: COLORREF, border: COLORREF,
    text: COLORREF, bright: COLORREF, dim: COLORREF,
    green: COLORREF, red: COLORREF, amber: COLORREF, blue: COLORREF, purple: COLORREF,
    green_bg: COLORREF, red_bg: COLORREF, purple_bg: COLORREF, amber_bg: COLORREF,
    btn: COLORREF,
}
fn theme() -> Theme {
    let blend = |c: (u8, u8, u8), a: f32| -> COLORREF {
        RGB(
            (c.0 as f32 * a + 0x13 as f32 * (1.0 - a)) as u8,
            (c.1 as f32 * a + 0x17 as f32 * (1.0 - a)) as u8,
            (c.2 as f32 * a + 0x22 as f32 * (1.0 - a)) as u8,
        )
    };
    Theme {
        bg: RGB(0x13, 0x17, 0x22),
        header: RGB(0x1e, 0x22, 0x2d),
        card: RGB(0x10, 0x14, 0x1d),
        border: RGB(0x2a, 0x2e, 0x39),
        text: RGB(0xd1, 0xd4, 0xdc),
        bright: RGB(0xf0, 0xf3, 0xfa),
        dim: RGB(0x78, 0x7b, 0x86),
        green: RGB(0x08, 0x99, 0x81),
        red: RGB(0xf7, 0x52, 0x5f),
        amber: RGB(0xf7, 0xa6, 0x00),
        blue: RGB(0x29, 0x62, 0xff),
        purple: RGB(0xab, 0x47, 0xbc),
        green_bg: blend((0x08, 0x99, 0x81), 0.25),
        red_bg: blend((0xf7, 0x52, 0x5f), 0.25),
        purple_bg: blend((0xab, 0x47, 0xbc), 0.20),
        amber_bg: blend((0xf7, 0xa6, 0x00), 0.15),
        btn: RGB(0x2a, 0x2e, 0x39),
    }
}

struct Fonts {
    normal: HGDIOBJ, bold: HGDIOBJ, semi: HGDIOBJ, small: HGDIOBJ, mono: HGDIOBJ, tiny: HGDIOBJ,
}
unsafe fn make_fonts() -> Fonts {
    let f = |h: i32, w: i32, mono: bool| -> HGDIOBJ {
        let face: &[u8] = if mono { b"Consolas\0" } else { b"Segoe UI\0" };
        CreateFontW(-h, 0, 0, 0, w, 0, 0, 0, DEFAULT_CHARSET,
            OUT_DEFAULT_PRECIS, CLIP_DEFAULT_PRECIS, CLEARTYPE_QUALITY, DEFAULT_PITCH,
            face.as_ptr() as *const _) as HGDIOBJ
    };
    Fonts {
        normal: f(15, FW_NORMAL, false),
        bold: f(16, FW_BOLD, false),
        semi: f(14, FW_SEMIBOLD, false),
        small: f(13, FW_NORMAL, false),
        mono: f(13, FW_NORMAL, true),
        tiny: f(11, FW_BOLD, false),
    }
}
unsafe fn drop_fonts(f: &Fonts) {
    for h in [&f.normal, &f.bold, &f.semi, &f.small, &f.mono, &f.tiny] {
        DeleteObject(*h);
    }
}

// ---------------------------------------------------------------- draw prims
struct Dc<'a> {
    hdc: HDC,
    th: &'a Theme,
    w: i32,
    h: i32,
    y: i32,
}

impl<'a> Dc<'a> {
    unsafe fn fill(&self, r: &RECT, col: COLORREF) {
        let b = CreateSolidBrush(col);
        FillRect(self.hdc, r, b);
        DeleteObject(b as *mut _);
    }
    unsafe fn round(&self, r: &RECT, fill: COLORREF, border: COLORREF, radius: i32) {
        let b = CreateSolidBrush(fill);
        let pen = CreatePen(PS_SOLID as i32, 1, border);
        let ob = SelectObject(self.hdc, b as HGDIOBJ);
        let op = SelectObject(self.hdc, pen as HGDIOBJ);
        RoundRect(self.hdc, r.left, r.top, r.right, r.bottom, radius, radius);
        SelectObject(self.hdc, ob);
        SelectObject(self.hdc, op);
        DeleteObject(b as HGDIOBJ);
        DeleteObject(pen as HGDIOBJ);
    }
    unsafe fn text_w(&self, s: &str, font: HGDIOBJ) -> i32 {
        let prev = SelectObject(self.hdc, font);
        let wide: Vec<u16> = s.encode_utf16().collect();
        let mut sz = SIZE { cx: 0, cy: 0 };
        GetTextExtentPoint32W(self.hdc, wide.as_ptr(), wide.len() as i32, &mut sz);
        SelectObject(self.hdc, prev);
        sz.cx
    }
    unsafe fn text(&self, s: &str, x: i32, y: i32, col: COLORREF, font: HGDIOBJ) -> i32 {
        let prev = SelectObject(self.hdc, font);
        SetTextColor(self.hdc, col);
        SetBkMode(self.hdc, TRANSPARENT as i32);
        let wide: Vec<u16> = s.encode_utf16().collect();
        TextOutW(self.hdc, x, y, wide.as_ptr(), wide.len() as i32);
        let mut sz = SIZE { cx: 0, cy: 0 };
        GetTextExtentPoint32W(self.hdc, wide.as_ptr(), wide.len() as i32, &mut sz);
        SelectObject(self.hdc, prev);
        sz.cx
    }
    unsafe fn pill(&self, r: &RECT, s: &str, fg: COLORREF, bg: COLORREF, border: COLORREF, font: HGDIOBJ) {
        self.round(r, bg, border, 8);
        let wide: Vec<u16> = s.encode_utf16().collect();
        let prev = SelectObject(self.hdc, font);
        SetTextColor(self.hdc, fg);
        SetBkMode(self.hdc, TRANSPARENT as i32);
        let mut sz = SIZE { cx: 0, cy: 0 };
        GetTextExtentPoint32W(self.hdc, wide.as_ptr(), wide.len() as i32, &mut sz);
        TextOutW(self.hdc, r.left + (r.right - r.left - sz.cx) / 2, r.top + (r.bottom - r.top - sz.cy) / 2, wide.as_ptr(), wide.len() as i32);
        SelectObject(self.hdc, prev);
    }
}

// ---------------------------------------------------------------- hit regions
#[derive(Clone)]
enum Hit {
    Panic,
    Tab(Tab),
    Filter,
    Sort(usize),
    Buy(String),
    Sell(String),
    Close(String),
    CloseConfirm(String),
}
static HITS: Mutex<Vec<(RECT, Hit)>> = Mutex::new(Vec::new());

// ---------------------------------------------------------------- painters
fn pnl_color(v: f64, th: &Theme) -> COLORREF {
    if v > 0.0 { th.green } else if v < 0.0 { th.red } else { th.dim }
}

unsafe fn paint_pnl(d: &mut Dc, f: &Fonts, ui: &UiState, w: i32, h: i32) {
    let Some(data) = &ui.data else {
        d.text("waiting for data...", 10, d.y + 10, d.th.dim, f.normal);
        return;
    };

    // stat cards
    let stats = [
        ("TOTAL FLEET NET LIQ", fmt_plain(data.totalNetLiquidation),
            if data.totalNetLiquidation != 0.0 { d.th.bright } else { d.th.dim }),
        ("OPEN UNREALIZED", fmt_money(data.totalUnrealizedPnL),
            if data.totalUnrealizedPnL > 0.0 { d.th.green } else if data.totalUnrealizedPnL < 0.0 { d.th.red } else { d.th.dim }),
        ("REALIZED TODAY", fmt_money(data.totalRealizedPnL),
            if data.totalRealizedPnL > 0.0 { d.th.green } else if data.totalRealizedPnL < 0.0 { d.th.red } else { d.th.dim }),
        ("OPEN CONTRACTS", format!("{}", data.totalOpenContracts),
            if data.totalOpenContracts > 0 { d.th.amber } else { d.th.dim }),
    ];
    let card_w = (w - 20 - 24) / 4;
    for (i, (label, val, colr)) in stats.iter().enumerate() {
        let r = RECT {
            left: 10 + (i as i32) * (card_w + 8),
            top: d.y,
            right: 10 + (i as i32) * (card_w + 8) + card_w,
            bottom: d.y + 46,
        };
        d.round(&r, d.th.card, d.th.border, 6);
        d.text(label, r.left + 8, r.top + 6, d.th.dim, f.tiny);
        d.text(val, r.left + 8, r.top + 22, *colr, f.bold);
    }
    d.y += 54;

    // copier banner
    if !data.copierRows.is_empty() {
        let parts: Vec<String> = data.copierRows.iter().map(|r| {
            let sync = if r.isQuarantined { "QUAR" } else if !r.isEnabled { "OFF" }
                else if r.expectedSide == r.actualSide && r.expectedQuantity == r.actualQuantity { "SYNC" } else { "DESYNC" };
            format!("{}->{} {}", r.leaderAccountName, r.followerAccountName, sync)
        }).collect();
        d.text(&parts.join("   "), 10, d.y, d.th.dim, f.small);
        d.y += 20;
    } else {
        d.y += 4;
    }

    // table header
    let hdr_y = d.y;
    d.text("Account", 14, hdr_y, d.th.dim, f.tiny);
    d.text("Position / Contracts", 200, hdr_y, d.th.dim, f.tiny);
    let un_w = d.text_w("Unrealized", f.tiny);
    d.text("Unrealized", w - 285 - un_w, hdr_y, d.th.dim, f.tiny);
    let re_w = d.text_w("Realized", f.tiny);
    d.text("Realized", w - 190 - re_w, hdr_y, d.th.dim, f.tiny);
    let nl_w = d.text_w("Net Liq", f.tiny);
    d.text("Net Liq", w - 100 - nl_w, hdr_y, d.th.dim, f.tiny);
    d.text("B/S/C", w - 58, hdr_y, d.th.dim, f.tiny);
    d.y += 20;

    // rows
    let mut pos_map: std::collections::HashMap<&str, &Position> = std::collections::HashMap::new();
    for p in &data.positions {
        if p.marketPosition != "Flat" { pos_map.insert(p.account.as_str(), p); }
    }
    let mut rows: Vec<(&Account, Option<&Position>)> = Vec::new();
    for a in &data.accounts {
        let pos = pos_map.get(a.name.as_str()).copied();
        let active = a.netLiquidation > 0.0 || a.cashValue > 0.0 || a.realizedPnL != 0.0
            || a.unrealizedPnL != 0.0 || pos.is_some();
        if !ui.show_all && !active { continue; }
        rows.push((a, pos));
    }
    rows.sort_by(|(a, pa), (b, pb)| {
        let key = |acc: &Account, pos: Option<&Position>| -> (i64, f64, String) {
            let has = pos.is_some();
            let qty = pos.map(|p| p.quantity.abs()).unwrap_or(0.0);
            match ui.sort_col {
                0 => (0, 0.0, acc.name.clone()),
                1 => (if has { 0 } else { 1 }, -qty, String::new()),
                2 => (0, acc.unrealizedPnL, String::new()),
                3 => (0, acc.realizedPnL, String::new()),
                _ => (0, if acc.netLiquidation != 0.0 { acc.netLiquidation } else { acc.cashValue }, String::new()),
            }
        };
        let (ka, kb) = (key(a, *pa), key(b, *pb));
        let ord = ka.2.cmp(&kb.2)
            .then(ka.0.cmp(&kb.0))
            .then(ka.1.partial_cmp(&kb.1).unwrap_or(std::cmp::Ordering::Equal));
        if ui.sort_asc { ord } else { ord.reverse() }
    });

    let row_h = 26;
    for (a, pos) in &rows {
        if d.y + row_h > h - 30 {
            d.text("\u{2193} more accounts (resize window)", 10, d.y + 2, d.th.dim, f.tiny);
            break;
        }
        let rr = RECT { left: 8, top: d.y, right: w - 8, bottom: d.y + row_h - 2 };
        d.fill(&rr, d.th.card);

        // name + type badge + locked badge
        let mut nx = 14;
        nx += d.text(&a.name, nx, d.y + 6, d.th.text, f.small) + 6;
        let at = acc_type(&a.name, &a.provider);
        let bw = d.text_w(at, f.tiny) + 10;
        let br = RECT { left: nx, top: d.y + 5, right: nx + bw, bottom: d.y + 20 };
        d.pill(&br, at, RGB(0x9d, 0xb2, 0xd4), d.th.btn, d.th.btn, f.tiny);
        nx = br.right + 4;
        let locked = *ui.lockouts.get(&a.name).unwrap_or(&false);
        if locked {
            let lb = RECT { left: nx, top: d.y + 5, right: nx + 52, bottom: d.y + 20 };
            d.pill(&lb, "LOCKED", d.th.red, d.th.red_bg, d.th.red, f.tiny);
        }

        // position badge
        match pos {
            Some(p) => {
                let is_long = p.marketPosition.eq_ignore_ascii_case("long");
                let price = if p.avgPrice > 0.0 { format!(" @ {:.2}", p.avgPrice) } else { String::new() };
                let label = format!("{} {} {}{}",
                    if is_long { "LONG" } else { "SHORT" },
                    p.quantity.abs() as i64, p.symbol, price);
                let bw = d.text_w(&label, f.tiny) + 14;
                let prc = RECT { left: 200, top: d.y + 3, right: 200 + bw.max(80), bottom: d.y + 21 };
                d.pill(&prc, &label,
                    if is_long { d.th.green } else { d.th.red },
                    if is_long { d.th.green_bg } else { d.th.red_bg },
                    if is_long { d.th.green } else { d.th.red }, f.tiny);
            }
            None => {
                d.text("0 (FLAT)", 204, d.y + 6, d.th.dim, f.tiny);
            }
        }

        // numbers (right-aligned mono)
        let up = if let Some(p) = pos { if p.unrealizedPnL != 0.0 { p.unrealizedPnL } else { a.unrealizedPnL } } else { a.unrealizedPnL };
        let rp = a.realizedPnL;
        let nl = if a.netLiquidation != 0.0 { a.netLiquidation } else { a.cashValue };
        let s1 = fmt_money(up);
        d.text(&s1, w - 285 - d.text_w(&s1, f.mono), d.y + 6, pnl_color(up, d.th), f.mono);
        let s2 = fmt_money(rp);
        d.text(&s2, w - 190 - d.text_w(&s2, f.mono), d.y + 6, pnl_color(rp, d.th), f.mono);
        let s3 = fmt_plain(nl);
        d.text(&s3, w - 100 - d.text_w(&s3, f.mono), d.y + 6, d.th.bright, f.mono);

        // B/S/C buttons
        let bx = w - 86;
        if locked {
            for (i, lbl) in ["B", "S", "C"].iter().enumerate() {
                let b = RECT { left: bx + (i as i32) * 22, top: d.y + 3, right: bx + (i as i32) * 22 + 20, bottom: d.y + 21 };
                d.round(&b, d.th.card, d.th.border, 4);
                let tw = d.text_w(lbl, f.tiny);
                d.text(lbl, b.left + (22 - tw) / 2, d.y + 6, d.th.dim, f.tiny);
            }
        } else {
            // B
            let bb = RECT { left: bx, top: d.y + 3, right: bx + 20, bottom: d.y + 21 };
            d.round(&bb, d.th.green_bg, d.th.green, 4);
            let tw = d.text_w("B", f.tiny);
            d.text("B", bb.left + (22 - tw) / 2, d.y + 6, d.th.green, f.tiny);
            HITS.lock().unwrap().push((bb, Hit::Buy(a.name.clone())));
            // S
            let sb = RECT { left: bx + 22, top: d.y + 3, right: bx + 42, bottom: d.y + 21 };
            d.round(&sb, d.th.red_bg, d.th.red, 4);
            let tw = d.text_w("S", f.tiny);
            d.text("S", sb.left + (22 - tw) / 2, d.y + 6, d.th.red, f.tiny);
            HITS.lock().unwrap().push((sb, Hit::Sell(a.name.clone())));
            // C
            let confirming = ui.close_confirm.as_deref() == Some(a.name.as_str())
                && now_ms() < ui.close_confirm_at;
            let cb = RECT { left: bx + 44, top: d.y + 3, right: bx + 64, bottom: d.y + 21 };
            let (ctxt, cfg, cbg) = if confirming { ("sure?", d.th.red, d.th.red_bg) } else { ("C", d.th.dim, d.th.card) };
            d.round(&cb, cbg, if confirming { d.th.red } else { d.th.border }, 4);
            let tw = d.text_w(ctxt, f.tiny);
            d.text(ctxt, cb.left + (22 - tw) / 2, d.y + 6, cfg, f.tiny);
            HITS.lock().unwrap().push((cb, if confirming { Hit::CloseConfirm(a.name.clone()) } else { Hit::Close(a.name.clone()) }));
        }

        d.y += row_h;
    }
}

unsafe fn paint_copier(d: &mut Dc, f: &Fonts, ui: &UiState, w: i32, h: i32) {
    let Some(data) = &ui.data else {
        d.text("waiting for data...", 10, d.y + 10, d.th.dim, f.normal);
        return;
    };
    d.text("COPY RELATIONSHIPS — leader vs follower sync validation", 10, d.y, d.th.dim, f.tiny);
    d.y += 22;
    d.text("Leader -> Follower        Expected        Actual         Sync", 10, d.y, d.th.dim, f.mono);
    d.y += 20;

    if data.copierRows.is_empty() {
        d.text("No copy relationships.", 10, d.y + 8, d.th.dim, f.normal);
        return;
    }
    let acc_map: std::collections::HashMap<&str, &Account> =
        data.accounts.iter().map(|a| (a.name.as_str(), a)).collect();

    for r in &data.copierRows {
        if d.y > h - 44 { d.text("\u{2193} more", 10, d.y, d.th.dim, f.tiny); break; }
        let exp_str = if r.expectedSide == "Flat" { "0 (Flat)".into() } else { format!("{} {} ctr", r.expectedSide, r.expectedQuantity as i64) };
        let act_str = if r.actualSide == "Flat" { "0 (Flat)".into() } else { format!("{} {} ctr", r.actualSide, r.actualQuantity as i64) };
        let is_match = r.expectedSide == r.actualSide && r.expectedQuantity == r.actualQuantity;
        let (badge, bfg, bbg) = if !r.isEnabled { ("DISABLED", d.th.dim, d.th.btn) }
            else if r.isQuarantined { ("QUARANTINE", d.th.purple, d.th.purple_bg) }
            else if is_match { ("SYNCED", d.th.green, d.th.green_bg) }
            else { ("DESYNC", d.th.red, d.th.red_bg) };

        d.text(&format!("{} -> {}", r.leaderAccountName, r.followerAccountName), 10, d.y + 4, d.th.text, f.mono);
        d.text(&exp_str, 260, d.y + 4, d.th.bright, f.mono);
        d.text(&act_str, 380, d.y + 4, if is_match { d.th.green } else { d.th.red }, f.mono);
        let bw = d.text_w(badge, f.tiny) + 12;
        let br = RECT { left: 500, top: d.y + 2, right: 500 + bw, bottom: d.y + 20 };
        d.pill(&br, badge, bfg, bbg, bfg, f.tiny);
        d.y += 24;
    }
    let _ = acc_map;
}

unsafe fn paint_risk(d: &mut Dc, f: &Fonts, ui: &UiState, w: i32, _h: i32) {
    // guard config card
    let card = RECT { left: 10, top: d.y, right: w - 10, bottom: d.y + 96 };
    d.round(&card, d.th.card, d.th.border, 6);
    d.text("RISKGUARD", 20, d.y + 8, d.th.dim, f.tiny);
    let mode = if ui.guard.mode.is_empty() { "?" } else { ui.guard.mode.as_str() };
    let (mfg, mbg) = if mode == "live" { (d.th.green, d.th.green_bg) }
        else if mode == "shadow" { (d.th.amber, d.th.amber_bg) } else { (d.th.dim, d.th.btn) };
    let mw = d.text_w(&format!("GUARD: {}", mode.to_uppercase()), f.tiny) + 14;
    let mr = RECT { left: 110, top: d.y + 4, right: 110 + mw, bottom: d.y + 22 };
    d.pill(&mr, &format!("GUARD: {}", mode.to_uppercase()), mfg, mbg, mfg, f.tiny);
    d.text(if ui.guard.loaded { "loaded" } else { "not loaded" }, 220, d.y + 8,
        if ui.guard.loaded { d.th.green } else { d.th.red }, f.tiny);
    d.text(&format!("Allowed roots: {}",
        if ui.guard.allowed_roots.is_empty() { "-".into() } else { ui.guard.allowed_roots.join(", ") }),
        20, d.y + 34, d.th.text, f.small);
    let max = ui.guard.max_per_account.map(|v| format!("{}", v as i64)).unwrap_or_else(|| "-".into());
    let nlimits = ui.guard.instrument_limits.as_object().map(|o| o.len()).unwrap_or(0);
    d.text(&format!("Max/account: {}   Instrument limits: {} rules", max, nlimits),
        20, d.y + 56, d.th.text, f.small);
    d.text("Loss rules enforced in-NT8 by the RiskGuard addon.", 20, d.y + 78, d.th.dim, f.tiny);
    d.y += 104;

    // lockouts card
    let locked: Vec<&String> = ui.lockouts.iter().filter(|(_, v)| **v).map(|(k, _)| k).collect();
    let card2 = RECT { left: 10, top: d.y, right: w - 10, bottom: d.y + 52 + (locked.len() as i32) * 22 };
    d.round(&card2, d.th.card, d.th.border, 6);
    d.text(&format!("LOCKOUTS ({} active)", locked.len()), 20, d.y + 8, d.th.dim, f.tiny);
    d.y += 30;
    if locked.is_empty() {
        d.text("\u{25cf} no accounts locked", 20, d.y, d.th.green, f.small);
    } else {
        for name in &locked {
            let br = RECT { left: 20, top: d.y - 2, right: 110, bottom: d.y + 16 };
            d.pill(&br, "LOCKED", d.th.red, d.th.red_bg, d.th.red, f.tiny);
            d.text(name, 130, d.y, d.th.text, f.small);
            d.y += 22;
        }
    }
}

// ---------------------------------------------------------------- paint all
unsafe fn paint_all(hdc: HDC, w: i32, h: i32) {
    let th = theme();
    let fonts = make_fonts();
    let mut d = Dc { hdc, th: &th, w, h, y: 0 };
    HITS.lock().unwrap().clear();

    let ui_guard = ui();
    let ui = match ui_guard.as_ref() {
        Some(u) => u,
        None => {
            d.text("starting...", 10, 10, th.dim, fonts.normal);
            drop_fonts(&fonts);
            return;
        }
    };

    // HEADER (40px)
    let hdr = RECT { left: 0, top: 0, right: w, bottom: 40 };
    d.fill(&hdr, th.header);
    d.fill(&RECT { left: 0, top: 39, right: w, bottom: 40 }, th.border);
    let fresh = now_ms() - ui.data_at < 2500;
    let dotc = if ui.data.is_some() && ui.fetch_err.is_none() && fresh { th.green } else { th.red };
    d.fill(&RECT { left: 14, top: 14, right: 24, bottom: 24 }, dotc);
    d.text("Fleet P&L", 32, 11, th.bright, fonts.bold);

    // guard chip
    let mode = if ui.guard.mode.is_empty() { "?" } else { ui.guard.mode.as_str() };
    let (cgt, cfg, cbg) = if mode == "live" { ("GUARD: LIVE", th.green, th.green_bg) }
        else if mode == "shadow" { ("GUARD: SHADOW", th.amber, th.amber_bg) }
        else { ("GUARD: ?", th.dim, th.btn) };
    let cgw = d.text_w(cgt, fonts.tiny) + 16;
    let cgr = RECT { left: w - 220 - cgw, top: 10, right: w - 220, bottom: 30 };
    d.pill(&cgr, cgt, cfg, cbg, cfg, fonts.tiny);

    // panic button
    let armed = ui.panic_armed && now_ms() < ui.panic_armed_until;
    let (ptxt, pfg, pbg, pbd) = if armed {
        ("CONFIRM FLATTEN ALL?", RGB(255, 255, 255), RGB(178, 40, 32), RGB(178, 40, 32))
    } else {
        ("PANIC FLATTEN", th.red, th.card, th.red)
    };
    let prc = RECT { left: w - 200, top: 8, right: w - 10, bottom: 32 };
    d.round(&prc, pbg, pbd, 6);
    {
        let wide: Vec<u16> = ptxt.encode_utf16().collect();
        let prev = SelectObject(hdc, fonts.semi);
        SetTextColor(hdc, pfg);
        SetBkMode(hdc, TRANSPARENT as i32);
        let mut sz = SIZE { cx: 0, cy: 0 };
        GetTextExtentPoint32W(hdc, wide.as_ptr(), wide.len() as i32, &mut sz);
        TextOutW(hdc, prc.left + (190 - sz.cx) / 2, prc.top + (24 - sz.cy) / 2, wide.as_ptr(), wide.len() as i32);
        SelectObject(hdc, prev);
    }
    HITS.lock().unwrap().push((prc, Hit::Panic));

    // TICKET BAR (36px)
    d.fill(&RECT { left: 0, top: 40, right: w, bottom: 76 }, th.card);
    d.fill(&RECT { left: 0, top: 75, right: w, bottom: 76 }, th.border);
    d.text("SYMBOL", 12, 49, th.dim, fonts.tiny);
    d.text("QTY", 208, 49, th.dim, fonts.tiny);
    d.text("ATM", 292, 49, th.dim, fonts.tiny);
    d.text("SL", 462, 49, th.dim, fonts.tiny);
    d.text("T", 548, 49, th.dim, fonts.tiny);
    // max-cap chip
    let root = read_symbol_root();
    let mut cap = ui.guard.max_per_account;
    if let Some(obj) = ui.guard.instrument_limits.as_object() {
        if let Some(lim) = obj.get(&root) {
            if let Some(mc) = lim.get("MaxContracts").and_then(|v| v.as_f64()) {
                cap = Some(cap.map_or(mc, |c| c.min(mc)));
            }
        }
    }
    if let Some(c) = cap {
        let t = format!("max {}", c as i64);
        d.text(&t, 612, 49, th.amber, fonts.tiny);
    }

    // TABS (28px)
    let tab_y = 82;
    let mut tx = 10;
    for (t, label) in [(Tab::Pnl, "P&L"), (Tab::Copier, "Copier"), (Tab::Risk, "Risk")] {
        let tw = d.text_w(label, fonts.semi) + 26;
        let tr = RECT { left: tx, top: tab_y, right: tx + tw, bottom: tab_y + 24 };
        let (bg, fg) = if ui.tab == t { (th.blue, RGB(255, 255, 255)) } else { (th.card, th.dim) };
        d.round(&tr, bg, if ui.tab == t { bg } else { th.border }, 6);
        let tw2 = d.text_w(label, fonts.semi);
        d.text(label, tr.left + (tw - tw2) / 2, tab_y + 4, fg, fonts.semi);
        HITS.lock().unwrap().push((tr, Hit::Tab(t)));
        tx += tw + 6;
    }
    if ui.tab == Tab::Pnl {
        let ftxt = if ui.show_all { "ALL ACCOUNTS" } else { "ACTIVE ONLY" };
        let fw = d.text_w(ftxt, fonts.tiny) + 18;
        let fr = RECT { left: w - 10 - fw, top: tab_y + 2, right: w - 10, bottom: tab_y + 24 };
        d.round(&fr, th.card, th.border, 6);
        d.text(ftxt, fr.left + 9, tab_y + 6, th.dim, fonts.tiny);
        HITS.lock().unwrap().push((fr, Hit::Filter));
    }
    d.y = tab_y + 32;

    // CONTENT
    match ui.tab {
        Tab::Pnl => paint_pnl(&mut d, &fonts, ui, w, h),
        Tab::Copier => paint_copier(&mut d, &fonts, ui, w, h),
        Tab::Risk => paint_risk(&mut d, &fonts, ui, w, h),
    }

    // FOOTER (22px)
    d.fill(&RECT { left: 0, top: h - 22, right: w, bottom: h }, th.header);
    let age = now_ms().saturating_sub(ui.data_at);
    let left = match &ui.fetch_err {
        Some(e) => format!("\u{25cf} {}", e),
        None => format!("\u{25cf} live \u{00b7} data {}ms old", age),
    };
    d.text(&left, 10, h - 17, if ui.fetch_err.is_some() { th.red } else { th.dim }, fonts.tiny);
    if !ui.status.is_empty() {
        let scol = match ui.status_kind { 1 => th.green, 2 => th.red, _ => th.dim };
        d.text(&ui.status, 240, h - 17, scol, fonts.tiny);
    }

    drop_fonts(&fonts);
}

fn read_symbol_root() -> String {
    unsafe {
        let hwnd = HWND_MAIN.load(Ordering::Relaxed) as *mut winapi::shared::windef::HWND__;
        if hwnd.is_null() { return String::new(); }
        let h = GetDlgItem(hwnd, IDC_SYMBOL);
        if h.is_null() { return String::new(); }
        let mut buf = [0u16; 64];
        let n = GetWindowTextW(h, buf.as_mut_ptr(), 64);
        let s = String::from_utf16_lossy(&buf[..n as usize]);
        s.split(' ').next().unwrap_or("").to_string()
    }
}

// ---------------------------------------------------------------- actions
fn read_ticket() -> (String, i64, String, i64, i64) {
    unsafe {
        let get = |id: i32| -> String {
            let h = GetDlgItem(HWND_MAIN.load(Ordering::Relaxed) as *mut _, id);
            if h.is_null() { return String::new(); }
            let mut buf = [0u16; 64];
            let n = GetWindowTextW(h, buf.as_mut_ptr(), 64);
            String::from_utf16_lossy(&buf[..n as usize])
        };
        let symbol = get(IDC_SYMBOL).trim().to_uppercase();
        let qty: i64 = get(IDC_QTY).trim().parse().unwrap_or(0);
        let atm_raw = get(IDC_ATM);
        let atm = if atm_raw == "AUTO" { String::new() } else { atm_raw };
        let stop: i64 = get(IDC_STOP).trim().parse().unwrap_or(0);
        let target: i64 = get(IDC_TARGET).trim().parse().unwrap_or(0);
        (symbol, qty, atm, stop, target)
    }
}

fn place_order(side: &'static str, account: &str) {
    let (symbol, qty, atm, stop, target) = read_ticket();
    if symbol.is_empty() { set_status("Pick a symbol in the ticket bar", 2); invalidate(); return; }
    if qty < 1 { set_status("Qty must be >= 1", 2); invalidate(); return; }
    if stop == 0 || target == 0 { set_status("SL/T ticks required", 2); invalidate(); return; }
    let key = format!("{}|{}", account, side);
    let dup = with_ui(|u| { if u.busy.contains(&key) { true } else { u.busy.insert(key.clone()); false } });
    if dup { return; }
    set_status(&format!("Submitting {} {} {} on {}...", side.to_uppercase(), qty, symbol, account), 0);
    invalidate();

    let body = serde_json::json!({
        "symbol": symbol, "action": side, "quantity": qty, "account": account,
        "strategyName": if atm.is_empty() { serde_json::Value::Null } else { serde_json::json!(atm) },
        "stopTicks": stop, "targetTicks": target,
        "confirmLive": true,
        "idempotencyKey": idem(),
    }).to_string();
    let acc = account.to_string();
    std::thread::spawn(move || {
        let (code, body_txt) = fire("/api/order/atm", body);
        with_ui(|u| { u.busy.remove(&format!("{}|{}", acc, side)); });
        if code == 200 && !body_txt.contains("\"error\"") {
            let bracket = serde_json::from_str::<serde_json::Value>(&body_txt).ok()
                .and_then(|v| v.get("bracketId").and_then(|b| b.as_str()).map(|s| s.to_string()))
                .unwrap_or_else(|| "bracket".into());
            set_status(&format!("OK {} {} {} {} [{}]", side.to_uppercase(), qty, symbol, acc, bracket), 1);
        } else {
            let err = serde_json::from_str::<serde_json::Value>(&body_txt).ok()
                .and_then(|v| v.get("error").and_then(|e| e.as_str()).map(|s| s.to_string()))
                .unwrap_or_else(|| format!("HTTP {}", code));
            set_status(&format!("REJECTED {}: {}", acc, err), 2);
        }
        invalidate();
    });
}

fn close_position(account: &str) {
    let key = format!("{}|close", account);
    let dup = with_ui(|u| { if u.busy.contains(&key) { true } else { u.busy.insert(key.clone()); false } });
    if dup { return; }
    let acc = account.to_string();
    let body = serde_json::json!({ "account": acc, "symbol": "ALL" }).to_string();
    std::thread::spawn(move || {
        let (code, _) = fire("/api/position/close", body);
        with_ui(|u| { u.busy.remove(&format!("{}|close", acc)); });
        if (200..300).contains(&code) {
            set_status(&format!("OK flatten {}", acc), 1);
        } else {
            set_status(&format!("CLOSE FAILED {}: HTTP {}", acc, code), 2);
        }
        invalidate();
    });
}

fn panic_flatten() {
    std::thread::spawn(|| {
        let (code, _) = fire("/api/flatten", "{}".into());
        if code == 200 { set_status("PANIC FLATTEN submitted", 1); }
        else { set_status(&format!("PANIC FAILED HTTP {}", code), 2); }
        invalidate();
    });
}

// ---------------------------------------------------------------- controls
const SYMBOLS_FALLBACK: &[&str] = &["NQ", "ES", "MNQ", "MES"];

unsafe fn create_ticket_controls(hwnd: HWND, hinst: HINSTANCE) {
    // labels painted in paint_all; controls positioned in the ticket bar (y 40..76)
    CreateWindowExA(
        0, b"COMBOBOX\0".as_ptr() as *const _, null_mut(),
        WS_CHILD | WS_VISIBLE | WS_VSCROLL | CBS_DROPDOWNLIST,
        70, 44, 130, 260, hwnd, IDC_SYMBOL as *mut _, hinst, null_mut());

    CreateWindowExA(
        WS_EX_CLIENTEDGE, b"EDIT\0".as_ptr() as *const _, b"1\0".as_ptr() as *const _,
        WS_CHILD | WS_VISIBLE | ES_NUMBER,
        238, 45, 44, 24, hwnd, IDC_QTY as *mut _, hinst, null_mut());

    let atm = CreateWindowExA(
        0, b"COMBOBOX\0".as_ptr() as *const _, null_mut(),
        WS_CHILD | WS_VISIBLE | CBS_DROPDOWNLIST,
        322, 44, 130, 260, hwnd, IDC_ATM as *mut _, hinst, null_mut());
    for s in ["AUTO", "FixedTicks", "AtrAdaptive", "SwingPoint", "DrawdownShield",
              "ScaledRunner", "VolatilityScaled", "SessionAdaptive", "KellyOptimal"] {
        let ansi: Vec<u8> = s.bytes().chain(std::iter::once(0)).collect();
        SendMessageA(atm, CB_ADDSTRING, 0, ansi.as_ptr() as LPARAM);
    }
    SendMessageA(atm, CB_SETCURSEL, 0, 0);

    CreateWindowExA(
        WS_EX_CLIENTEDGE, b"EDIT\0".as_ptr() as *const _, b"0\0".as_ptr() as *const _,
        WS_CHILD | WS_VISIBLE | ES_NUMBER,
        478, 45, 44, 24, hwnd, IDC_STOP as *mut _, hinst, null_mut());

    CreateWindowExA(
        WS_EX_CLIENTEDGE, b"EDIT\0".as_ptr() as *const _, b"0\0".as_ptr() as *const _,
        WS_CHILD | WS_VISIBLE | ES_NUMBER,
        564, 45, 44, 24, hwnd, IDC_TARGET as *mut _, hinst, null_mut());
}

unsafe fn refresh_symbol_combo() {
    let hwnd = HWND_MAIN.load(Ordering::Relaxed) as *mut winapi::shared::windef::HWND__;
    if hwnd.is_null() { return; }
    let h = GetDlgItem(hwnd, IDC_SYMBOL);
    if h.is_null() { return; }
    let guard = with_ui(|u| u.guard.clone());
    let qs = quarterlies();
    let roots: Vec<String> = if guard.allowed_roots.is_empty() {
        SYMBOLS_FALLBACK.iter().map(|s| s.to_string()).collect()
    } else {
        guard.allowed_roots.clone()
    };
    SendMessageA(h, CB_RESETCONTENT, 0, 0);
    let mut added: isize = 0;
    for r in &roots {
        for q in &qs {
            let s = format!("{} {}", r, q);
            let ansi: Vec<u8> = s.bytes().chain(std::iter::once(0)).collect();
            let rc = SendMessageA(h, CB_ADDSTRING, 0, ansi.as_ptr() as LPARAM);
            if rc >= 0 { added += 1; }
        }
    }
    if SendMessageA(h, CB_GETCOUNT, 0, 0) > 0 {
        SendMessageA(h, CB_SETCURSEL, 0, 0);
    }
    let count = SendMessageA(h, CB_GETCOUNT, 0, 0);
    let _ = std::fs::write(
        std::env::temp_dir().join("pnl_gdi_debug.txt"),
        format!("added={} count={} roots={:?} qs={:?}\n", added, count, roots, qs),
    );
}

// ---------------------------------------------------------------- wndproc
unsafe extern "system" fn wndproc(hwnd: HWND, msg: UINT, wparam: WPARAM, lparam: LPARAM) -> LRESULT {
    match msg {
        WM_CREATE => {
            let hinst = GetModuleHandleA(null_mut());
            create_ticket_controls(hwnd, hinst);
            0
        }
        WM_PAINT => {
            let mut ps: PAINTSTRUCT = std::mem::zeroed();
            let hdc = BeginPaint(hwnd, &mut ps);
            let (w, h) = (ps.rcPaint.right, ps.rcPaint.bottom);
            let mem = CreateCompatibleDC(hdc);
            let bmp = CreateCompatibleBitmap(hdc, w, h);
            let old = SelectObject(mem, bmp as HGDIOBJ);
            paint_all(mem, w, h);
            BitBlt(hdc, 0, 0, w, h, mem, 0, 0, SRCCOPY);
            SelectObject(mem, old);
            DeleteObject(bmp as HGDIOBJ);
            DeleteDC(mem);
            EndPaint(hwnd, &ps);
            0
        }
        WM_ERASEBKGND => 1,
        WM_LBUTTONDOWN => {
            let x = (lparam & 0xFFFF) as i16 as i32;
            let y = ((lparam >> 16) & 0xFFFF) as i16 as i32;
            let hit = HITS.lock().unwrap().iter()
                .find(|(r, _)| x >= r.left && x <= r.right && y >= r.top && y <= r.bottom)
                .map(|(_, h)| h.clone());
            let mut repaint = false;
            if let Some(h) = hit {
                match h {
                    Hit::Panic => {
                        let fire_now = with_ui(|u| {
                            if u.panic_armed && now_ms() < u.panic_armed_until {
                                u.panic_armed = false;
                                true
                            } else {
                                u.panic_armed = true;
                                u.panic_armed_until = now_ms() + 3000;
                                false
                            }
                        });
                        if fire_now { panic_flatten(); } else { repaint = true; }
                    }
                    Hit::Tab(t) => { with_ui(|u| { u.tab = t; }); repaint = true; }
                    Hit::Filter => { with_ui(|u| u.show_all = !u.show_all); repaint = true; }
                    Hit::Sort(col) => {
                        with_ui(|u| {
                            if u.sort_col == col { u.sort_asc = !u.sort_asc; }
                            else { u.sort_col = col; u.sort_asc = false; }
                        });
                        repaint = true;
                    }
                    Hit::Buy(acc) => place_order("buy", &acc),
                    Hit::Sell(acc) => place_order("sell", &acc),
                    Hit::Close(acc) => {
                        with_ui(|u| {
                            u.close_confirm = Some(acc.clone());
                            u.close_confirm_at = now_ms() + 3000;
                        });
                        repaint = true;
                    }
                    Hit::CloseConfirm(acc) => {
                        with_ui(|u| u.close_confirm = None);
                        close_position(&acc);
                    }
                }
            }
            if repaint { invalidate(); }
            0
        }
        WM_RBUTTONUP => {
            with_ui(|u| u.show_all = !u.show_all);
            invalidate();
            0
        }
        WM_COMMAND => {
            let code = ((wparam >> 16) & 0xFFFF) as u16;
            let id = (wparam & 0xFFFF) as i32;
            if id == IDC_SYMBOL && (code == CBN_SELCHANGE as u16 || code == CBN_EDITCHANGE as u16) {
                invalidate(); // max-cap chip reads current symbol
            }
            0
        }
        WM_DESTROY => { PostQuitMessage(0); 0 }
        _ => DefWindowProcA(hwnd, msg, wparam, lparam),
    }
}

// ---------------------------------------------------------------- winmain
fn main() {
    unsafe {
        let hinst = GetModuleHandleA(null_mut());

        let wc = WNDCLASSA {
            style: CS_HREDRAW | CS_VREDRAW,
            lpfnWndProc: Some(wndproc),
            cbClsExtra: 0,
            cbWndExtra: 0,
            hInstance: hinst,
            hIcon: null_mut(),
            hCursor: LoadCursorA(null_mut(), IDC_ARROW as *const i8),
            hbrBackground: null_mut(),
            lpszMenuName: std::ptr::null(),
            lpszClassName: b"FleetPnlShell\0".as_ptr() as *const _,
        };
        RegisterClassA(&wc);

        let hwnd = CreateWindowExA(
            WS_EX_TOPMOST | WS_EX_TOOLWINDOW,
            b"FleetPnlShell\0".as_ptr() as *const _,
            b"Fleet P&L Monitor\0".as_ptr() as *const _,
            WS_OVERLAPPEDWINDOW | WS_VISIBLE,
            100, 100, 700, 760,
            null_mut(), null_mut(), hinst, null_mut(),
        );
        if hwnd.is_null() { return; }
        HWND_MAIN.store(hwnd as isize, Ordering::Relaxed);

        std::thread::spawn(fetch_loop);
        std::thread::spawn(lockout_loop);
        std::thread::spawn(config_loop);
        std::thread::spawn(|| {
            std::thread::sleep(Duration::from_millis(1200));
            unsafe { refresh_symbol_combo(); }
            std::thread::sleep(Duration::from_millis(4000));
            unsafe { refresh_symbol_combo(); }
        });

        let mut msg: MSG = std::mem::zeroed();
        while GetMessageA(&mut msg, null_mut(), 0, 0) > 0 {
            TranslateMessage(&msg);
            DispatchMessageA(&msg);
        }
    }
}