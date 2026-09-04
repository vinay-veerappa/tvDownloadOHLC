//! Unit tests for `poller`.
//!
//! These reproduce the four semantic diffs that had to be eliminated by hand to reach
//! byte-identical JSON against the Node server during the Track 1 cutover.
//! `pnl_widget_server.js` is archived, so Gate 1 can never re-prove this by A/B again -
//! these tests are now the only thing standing between a refactor and a silently
//! different HUD.

use super::*;
use serde_json::json;

// ====================================================================================
// js_normalize_json_str / js_format_number
// ====================================================================================

#[test]
fn integral_floats_print_without_a_decimal_point() {
    // serde/ryu emits 0.0; V8 emits 0.
    assert_eq!(js_normalize_json_str("0.0"), "0");
    assert_eq!(js_normalize_json_str("5.0"), "5");
    assert_eq!(js_normalize_json_str("-12.0"), "-12");
    assert_eq!(js_normalize_json_str("100000.0"), "100000");
}

#[test]
fn negative_zero_prints_as_zero() {
    // JS: JSON.stringify(-0) === "0".
    assert_eq!(js_normalize_json_str("-0.0"), "0");
    assert_eq!(js_normalize_json_str("-0"), "0");
}

#[test]
fn v8_shortest_repr_drops_the_digit_ryu_keeps() {
    // The exact value from the cutover record.
    assert_eq!(js_normalize_json_str("49453.150000000052"), "49453.15000000005");
}

#[test]
fn normalized_numbers_still_round_trip_to_the_same_f64() {
    // Shortening the representation must never change the VALUE. A formatter that
    // rounds is worse than one that prints a long digit string.
    for raw in [
        "49453.150000000052",
        "626846.25",
        "-1234.5678901234567",
        "0.1",
        "2.5",
    ] {
        let out = js_normalize_json_str(raw);
        let a: f64 = raw.parse().unwrap();
        let b: f64 = out.parse().unwrap();
        assert_eq!(a, b, "value changed: {raw} -> {out}");
    }
}

#[test]
fn numbers_inside_string_literals_are_left_alone() {
    // The scanner walks raw JSON text, so it must not rewrite digits that are part of a
    // string. An account name like "LFE02559938020004" or a symbol "MNQ SEP26" must
    // survive verbatim.
    let src = r#"{"name":"LFE02559938020004","symbol":"MNQ SEP26","qty":2.0}"#;
    let out = js_normalize_json_str(src);
    assert!(out.contains(r#""LFE02559938020004""#), "account name mangled: {out}");
    assert!(out.contains(r#""MNQ SEP26""#), "symbol mangled: {out}");
    assert!(out.contains(r#""qty":2"#), "numeric field not normalized: {out}");
}

#[test]
fn escaped_quotes_inside_strings_do_not_end_the_literal() {
    // If the scanner mishandles \" it falls out of string context mid-value and starts
    // rewriting prose as numbers.
    let src = r#"{"detail":"COPIER \"LIVE\" 1.0 armed","v":1.0}"#;
    let out = js_normalize_json_str(src);
    assert!(out.contains(r#"COPIER \"LIVE\" 1.0 armed"#), "string mangled: {out}");
    assert!(out.contains(r#""v":1"#), "numeric field not normalized: {out}");
}

#[test]
fn structural_json_is_preserved() {
    let src = r#"{"a":[1.0,2.5,{"b":-3.0}],"c":null,"d":true}"#;
    assert_eq!(
        js_normalize_json_str(src),
        r#"{"a":[1,2.5,{"b":-3}],"c":null,"d":true}"#
    );
}

#[test]
fn output_is_still_parseable_json() {
    let src = r#"{"accounts":[{"netLiquidation":100000.0,"realizedPnL":-0.0}]}"#;
    let out = js_normalize_json_str(src);
    let v: Value = serde_json::from_str(&out).expect("normalizer produced invalid JSON");
    assert_eq!(v["accounts"][0]["netLiquidation"], json!(100000));
}

// ====================================================================================
// compute_fleet_summary
// ====================================================================================

fn acct(name: &str, cash: f64, netliq: Value, realized: f64, unrealized: f64) -> Value {
    json!({
        "name": name, "provider": "Test", "denomination": "USD",
        "cashValue": cash, "netLiquidation": netliq,
        "realizedPnL": realized, "unrealizedPnL": unrealized, "buyingPower": 0.0
    })
}

fn no_copier() -> Value {
    json!({ "rows": [], "system": null })
}

#[test]
fn present_but_zero_netliq_falls_back_to_cash_value() {
    // Node does `Number(acc.netLiquidation || acc.cashValue)`, and 0 is FALSY in JS - so
    // a present-but-0 netLiquidation falls through to cashValue. A Rust `unwrap_or` only
    // handles an ABSENT field and would have reported the $100k Backtest account as $0.
    let accounts = json!([acct("Backtest", 100_000.0, json!(0.0), 0.0, 0.0)]);
    let out = compute_fleet_summary(&accounts, &json!([]), &no_copier());
    assert_eq!(out["accounts"][0]["netLiquidation"], json!(100_000.0));
    assert_eq!(out["totalNetLiquidation"], json!(100_000.0));
}

#[test]
fn absent_netliq_also_falls_back_to_cash_value() {
    let accounts = json!([acct("NoNetLiq", 4_200.0, Value::Null, 0.0, 0.0)]);
    let out = compute_fleet_summary(&accounts, &json!([]), &no_copier());
    assert_eq!(out["accounts"][0]["netLiquidation"], json!(4_200.0));
}

#[test]
fn a_real_netliq_is_used_as_is() {
    let accounts = json!([acct("Live", 1.0, json!(50_000.0), 0.0, 0.0)]);
    let out = compute_fleet_summary(&accounts, &json!([]), &no_copier());
    assert_eq!(out["accounts"][0]["netLiquidation"], json!(50_000.0));
}

#[test]
fn position_unrealized_of_zero_keeps_the_account_value() {
    // `Number(pos.unrealizedPnL) || uPnl` - a 0 from the position row must NOT overwrite
    // a non-zero account-level unrealized.
    let accounts = json!([acct("A", 0.0, json!(1_000.0), 0.0, 25.0)]);
    let positions = json!([{ "account": "A", "symbol": "MNQ SEP26",
                             "marketPosition": "Long", "quantity": 1, "unrealizedPnL": 0.0 }]);
    let out = compute_fleet_summary(&accounts, &positions, &no_copier());
    assert_eq!(out["accounts"][0]["unrealizedPnL"], json!(25.0));
}

#[test]
fn position_unrealized_overrides_when_non_zero() {
    let accounts = json!([acct("A", 0.0, json!(1_000.0), 0.0, 25.0)]);
    let positions = json!([{ "account": "A", "symbol": "MNQ SEP26",
                             "marketPosition": "Long", "quantity": 1, "unrealizedPnL": 99.0 }]);
    let out = compute_fleet_summary(&accounts, &positions, &no_copier());
    assert_eq!(out["accounts"][0]["unrealizedPnL"], json!(99.0));
}

#[test]
fn active_contracts_string_matches_the_health_surface() {
    // This string is what /health reports and what the HUD shows; its exact shape was
    // observed live as "1 Contract (+1 MNQ)" / "3 Contracts (+3 MNQ)".
    let accounts = json!([acct("A", 0.0, json!(1_000.0), 0.0, 0.0)]);

    let one = json!([{ "account": "A", "symbol": "MNQ SEP26",
                       "marketPosition": "Long", "quantity": 1, "unrealizedPnL": 2.5 }]);
    let out = compute_fleet_summary(&accounts, &one, &no_copier());
    assert_eq!(out["totalOpenContracts"], json!(1));
    assert_eq!(out["activeContracts"], json!("1 Contract (+1 MNQ)"));

    let three = json!([{ "account": "A", "symbol": "MNQ SEP26",
                         "marketPosition": "Long", "quantity": 3, "unrealizedPnL": 2.5 }]);
    let out = compute_fleet_summary(&accounts, &three, &no_copier());
    assert_eq!(out["totalOpenContracts"], json!(3));
    assert_eq!(out["activeContracts"], json!("3 Contracts (+3 MNQ)"));
}

#[test]
fn flat_positions_are_not_counted_as_open() {
    let accounts = json!([acct("A", 0.0, json!(1_000.0), 0.0, 0.0)]);
    let positions = json!([{ "account": "A", "symbol": "MNQ SEP26",
                             "marketPosition": "Flat", "quantity": 0, "unrealizedPnL": 0.0 }]);
    let out = compute_fleet_summary(&accounts, &positions, &no_copier());
    assert_eq!(out["totalOpenContracts"], json!(0));
    assert_eq!(out["activeContracts"], json!("0 Contracts (Flat)"));
}

#[test]
fn short_positions_render_with_a_minus_sign() {
    let accounts = json!([acct("A", 0.0, json!(1_000.0), 0.0, 0.0)]);
    let positions = json!([{ "account": "A", "symbol": "ES DEC26",
                             "marketPosition": "Short", "quantity": 2, "unrealizedPnL": -5.0 }]);
    let out = compute_fleet_summary(&accounts, &positions, &no_copier());
    assert_eq!(out["activeContracts"], json!("2 Contracts (-2 ES)"));
}

#[test]
fn copier_rows_and_system_pass_through() {
    // The third poll leg. If this silently became an empty array the HUD would show
    // "no followers" rather than an error - the quiet failure, so pin it.
    let accounts = json!([acct("A", 0.0, json!(1.0), 0.0, 0.0)]);
    let copier = json!({ "rows": [{"n": 1}, {"n": 2}], "system": {"loaded": true} });
    let out = compute_fleet_summary(&accounts, &json!([]), &copier);
    assert_eq!(out["copierRows"].as_array().unwrap().len(), 2);
    assert_eq!(out["copierSystem"]["loaded"], json!(true));
}

#[test]
fn missing_copier_snapshot_yields_an_array_not_null() {
    // copierRows must always be an array; the contract gate asserts non-null.
    let accounts = json!([acct("A", 0.0, json!(1.0), 0.0, 0.0)]);
    let out = compute_fleet_summary(&accounts, &json!([]), &json!({}));
    assert!(out["copierRows"].is_array(), "copierRows must be an array");
}

#[test]
fn totals_sum_across_accounts() {
    let accounts = json!([
        acct("A", 0.0, json!(1_000.0), 10.0, 1.0),
        acct("B", 0.0, json!(2_000.0), -4.0, 2.0),
    ]);
    let out = compute_fleet_summary(&accounts, &json!([]), &no_copier());
    assert_eq!(out["totalRealizedPnL"], json!(6.0));
    assert_eq!(out["totalUnrealizedPnL"], json!(3.0));
    assert_eq!(out["activeAccountsCount"], json!(2));
}

#[test]
fn an_empty_fleet_does_not_panic() {
    let out = compute_fleet_summary(&json!([]), &json!([]), &no_copier());
    assert_eq!(out["accounts"].as_array().unwrap().len(), 0);
    assert_eq!(out["totalNetLiquidation"], json!(0.0));
    assert_eq!(out["activeContracts"], json!("0 Contracts (Flat)"));
}

#[test]
fn malformed_input_types_do_not_panic() {
    // The poller feeds whatever NT8 returned. A non-array must degrade, not crash - a
    // panic here kills the daemon and the HUD with it.
    let out = compute_fleet_summary(&json!("not an array"), &json!(42), &json!(null));
    assert_eq!(out["accounts"].as_array().unwrap().len(), 0);
}
