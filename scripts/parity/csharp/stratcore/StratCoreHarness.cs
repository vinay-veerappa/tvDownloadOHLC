// =============================================================================
// StratCoreHarness -- runs StratCore's pure functions over a CSV of cases so the
// Python mirror in scripts/libs_py/the_strat/ can be diffed against them.
//
// StratCore.cs declares itself the C# mirror of that package and says "Rule
// changes go here AND in Python together - never in only one side." This is what
// makes that assertion falsifiable.
//
// CSV in  (arg 1): id,fn,p1..p9,extra
// CSV out (arg 2): id,fn,r1..r6
//
// `extra` is a semicolon-separated list, used only by the two functions that take
// one: `entry` (killzone HHMM pairs) and `ftfc` (timeframe opens).
//
// Every number is written with R (round-trip) formatting and InvariantCulture.
// A parity harness that formats 0.65 as "0,65" on a European locale reports a
// mismatch in every row and names the wrong cause.
// =============================================================================
using System;
using System.Collections.Generic;
using System.Globalization;
using System.IO;
using System.Linq;
using NinjaTrader.NinjaScript.Strategies.Vinay;

class StratCoreHarness
{
    static readonly CultureInfo INV = CultureInfo.InvariantCulture;

    static double D(string s) =>
        string.IsNullOrWhiteSpace(s) ? 0.0 : double.Parse(s, INV);

    static string F(double v) => v.ToString("R", INV);

    static int Main(string[] args)
    {
        if (args.Length < 2)
        {
            Console.Error.WriteLine("usage: StratCoreHarness <cases.csv> <out.csv>");
            return 2;
        }

        var outLines = new List<string> { "id,fn,r1,r2,r3,r4,r5,r6" };
        var lines = File.ReadAllLines(args[0]);

        for (int i = 1; i < lines.Length; i++)   // row 0 is the header
        {
            var raw = lines[i];
            if (string.IsNullOrWhiteSpace(raw)) continue;
            var c = raw.Split(',');
            string id = c[0];
            string fn = c[1];
            double p1 = D(c[2]), p2 = D(c[3]), p3 = D(c[4]), p4 = D(c[5]),
                   p5 = D(c[6]), p6 = D(c[7]), p7 = D(c[8]), p8 = D(c[9]),
                   p9 = D(c[10]);
            string extra = c.Length > 11 ? c[11] : "";

            string[] r = new string[6];
            for (int k = 0; k < 6; k++) r[k] = "";

            switch (fn)
            {
                case "classify":
                    // p1 high, p2 low, p3 prevHigh, p4 prevLow
                    r[0] = StratCore.ClassifyBar(p1, p2, p3, p4).ToString(INV);
                    break;

                case "wick":
                    // p1 open, p2 close, p3 high, p4 low, p5 threshold, p6 tickSize
                    r[0] = StratCore.WickType(p1, p2, p3, p4, p5, p6).ToString(INV);
                    break;

                case "targets":
                {
                    // p1 direction, p2 entry, p3 structuralStop, p4 insideHigh,
                    // p5 insideLow, p6 priorLeg, p7 minTarget, p8 maxRisk, p9 tick
                    var m = StratCore.MeasuredTargets(
                        (int)p1, p2, p3, p4, p5, p6, p7, p8, p9);
                    r[0] = F(m.Target1);
                    r[1] = F(m.Target2);
                    r[2] = F(m.RiskPoints);
                    r[3] = F(m.RewardPoints);
                    r[4] = F(m.RrRatio);
                    r[5] = m.StopCapped ? "1" : "0";
                    break;
                }

                case "entry":
                {
                    // p1 barHHMM, p2 earliest, p3 latest, p4 flatten, p5 useKillzones
                    // extra: flat killzone HHMM pairs, ';'-separated
                    int hhmm = (int)p1;
                    var t = new DateTime(2026, 1, 5, hhmm / 100, hhmm % 100, 0);
                    int[] kz = string.IsNullOrWhiteSpace(extra)
                        ? new int[0]
                        : extra.Split(';').Where(s => s.Length > 0)
                               .Select(s => int.Parse(s, INV)).ToArray();
                    bool ok = StratCore.EntryAllowed(
                        t, (int)p2, (int)p3, (int)p4, kz, p5 != 0.0);
                    r[0] = ok ? "1" : "0";
                    break;
                }

                case "ftfc":
                {
                    // p1 price; extra: ';'-separated timeframe opens
                    double[] opens = string.IsNullOrWhiteSpace(extra)
                        ? new double[0]
                        : extra.Split(';').Where(s => s.Length > 0)
                               .Select(s => double.Parse(s, INV)).ToArray();
                    r[0] = StratCore.FtfcScore(p1, opens).ToString(INV);
                    break;
                }

                default:
                    // An unknown function must not silently produce an empty row
                    // that the differ then reads as agreement.
                    Console.Error.WriteLine("unknown fn: " + fn + " (case " + id + ")");
                    return 3;
            }

            outLines.Add(string.Join(",", new[] { id, fn }.Concat(r)));
        }

        File.WriteAllLines(args[1], outLines);
        Console.Error.WriteLine("wrote " + (outLines.Count - 1) + " result row(s)");
        return 0;
    }
}
