
import math

def f_tos_expected_move(price, iv, dte, asset_class):
    intercept = 0.69 if asset_class == "futures" else 0.24
    t_eff_yr = (0.637 * dte + intercept) / 365.0
    return price * iv * math.sqrt(t_eff_yr)

def test_spy():
    price = 737.72
    # Data from handoff doc
    data = [
        ("May 11", 2, 0.0998, 4.740),
        ("May 12", 3, 0.1203, 6.810),
        ("May 13", 4, 0.1285, 8.282),
        ("May 14", 5, 0.1374, 9.815),
        ("May 15", 6, 0.1453, 11.304),
    ]
    print("### SPY Verification")
    print("| Date | DTE | IV | Target | Calculated | Diff % |")
    print("|------|-----|----|--------|------------|--------|")
    for date, dte, iv, target in data:
        calc = f_tos_expected_move(price, iv, dte, "equity")
        diff_pct = (calc - target) / target * 100
        print(f"| {date} | {dte} | {iv:.2%} | {target:.3f} | {calc:.3f} | {diff_pct:+.3f}% |")

def test_es():
    price = 7420.50
    # Data from handoff doc
    data = [
        ("May 11", 2, 0.0776, 42.270),
        ("May 12", 3, 0.0997, 62.483),
        ("May 13", 4, 0.1100, 76.900),
        ("May 14", 5, 0.1199, 91.699),
        ("May 15", 6, 0.2299, 189.765),
    ]
    print("\n### /ES Verification")
    print("| Date | DTE | IV | Target | Calculated | Diff % |")
    print("|------|-----|----|--------|------------|--------|")
    for date, dte, iv, target in data:
        calc = f_tos_expected_move(price, iv, dte, "futures")
        diff_pct = (calc - target) / target * 100
        print(f"| {date} | {dte} | {iv:.2%} | {target:.3f} | {calc:.3f} | {diff_pct:+.3f}% |")

if __name__ == "__main__":
    test_spy()
    test_es()
