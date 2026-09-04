# RETIRED 2026-09-03 - this gate could no longer fail.
#
# It fetched http://127.0.0.1:8635/api/data as $node and http://127.0.0.1:8637/api/data
# as $rust and compared them. That was valid for one day. After the Track 1 cutover 8635
# IS the Rust daemon, so on every run since it has been comparing the daemon to itself
# and reporting "100% Data & Balance Parity Verified!" - a green that cannot go red.
# pnl_widget_server.js is archived under scripts/tradingview/legacy_archive/, so the Node
# side cannot be stood back up and the original comparison is unrecoverable by design.
#
# This file is deliberately NOT deleted: the playbook, shell history and any agent
# following the old quick-reference still invoke it by name, and a missing file would
# read as an environment problem. It exits 2 so that path is loud instead of silent.
#
# Use crates\gate1_contract.ps1 instead:
#   contract check (default):  powershell -File crates\gate1_contract.ps1
#   real A/B vs a candidate:   powershell -File crates\gate1_contract.ps1 -ShadowPort 8637
# The replacement refuses to run when both ports resolve to the same pid, which is the
# exact defect this script shipped with.

Write-Host "gate1_parity.ps1 is RETIRED - it compared port 8635 to itself and always passed." -ForegroundColor Red
Write-Host "Run instead:  powershell -ExecutionPolicy Bypass -File crates\gate1_contract.ps1" -ForegroundColor Yellow
exit 2
