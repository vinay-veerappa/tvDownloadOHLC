// =============================================================================
// CsdEngineHarness — feeds a pinned OHLC CSV through the ICT engines and
// writes the per-bar state CSV that run_signal_parity.py diffs against the
// Python kernel's output.
//
// CSV in  (arg 1): time,open,high,low,close  (from scripts/parity/export_fixture.py)
// CSV out (arg 2): the parity row schema:
//   BarTime,Open,High,Low,Close,CisdEvent,CisdState,ActiveBullLevel,
//   ActiveBearLevel,FvgEvent,FvgTop,FvgBottom,IfvgEvent,BprEvent
//
// Engine wiring mirrors the Python strategy's hunt() composition:
//   cisd=fvg=ifvg=bpr computed on the SAME bars, setup consumes all events.
// =============================================================================
using System;
using System.Globalization;
using System.IO;
using Vinay.Ict;

class CsdEngineHarness
{
    static int Main(string[] args)
    {
        if (args.Length < 2)
        {
            Console.Error.WriteLine("usage: CsdEngineHarness <bars.csv> <out.csv> [variant] [stopType] [entryMech]");
            return 2;
        }
        int variant = args.Length > 2 ? int.Parse(args[2]) : 2;
        int stopType = args.Length > 3 ? int.Parse(args[3]) : 0;
        int entryMech = args.Length > 4 ? int.Parse(args[4]) : 1;

        var cisd = new IctCisdEngine();
        var fvg = new IctFvgEngine { IncludeVi = true, RequireDirectional = false };
        var ifvg = new IctIfvgEngine { IncludeVi = true, RequireDirectional = false };
        var bpr = new IctBprEngine { IncludeVi = true, RequireDirectional = false };
        var setup = new IctCisdReversalSetup
        {
            Variant = variant, TickSize = 0.25,
            MinRiskBps = 2.0, MaxRiskBps = 15.0,
            StopLossType = stopType, StopLossBps = 5.0,
            EntryMechanism = entryMech,
        };

        double prevEndBull = double.NaN, prevEndBear = double.NaN;

        using var reader = new StreamReader(args[0]);
        using var writer = new StreamWriter(args[1], false);
        writer.WriteLine("BarTime,Open,High,Low,Close,CisdEvent,CisdState,ActiveBullLevel,"
            + "ActiveBearLevel,FvgEvent,FvgTop,FvgBottom,IfvgEvent,BprEvent,"
            + "Signal,EntryPrice,StopPrice,RiskPts");

        string line;
        bool header = true;
        while ((line = reader.ReadLine()) != null)
        {
            if (header) { header = false; continue; }   // skip csv header
            var f = line.Split(',');
            if (f.Length < 5) continue;
            string t = f[0];
            double o = double.Parse(f[1], CultureInfo.InvariantCulture);
            double h = double.Parse(f[2], CultureInfo.InvariantCulture);
            double l = double.Parse(f[3], CultureInfo.InvariantCulture);
            double c = double.Parse(f[4], CultureInfo.InvariantCulture);

            int ce = cisd.OnBar(o, h, l, c);
            var fr = fvg.OnBar(o, h, l, c);
            var ir = ifvg.OnBar(o, h, l, c);
            var br = bpr.OnBar(o, h, l, c);

            double endBull = cisd.State == 1 ? cisd.ActiveLevel : double.NaN;
            double endBear = cisd.State == -1 ? cisd.ActiveLevel : double.NaN;

            setup.PushEngineEvents(ce, cisd.State,
                fr.Event,
                fr.Event != 0 ? fr.Top : double.NaN,
                fr.Event != 0 ? fr.Bottom : double.NaN,
                ir.Event, br.Event,
                prevEndBull, prevEndBear, endBull, endBear, o);
            var st = setup.OnBar(o, h, l, c);

            prevEndBull = endBull;
            prevEndBear = endBear;

            writer.WriteLine(string.Format(CultureInfo.InvariantCulture,
                "{0},{1:G},{2:G},{3:G},{4:G},{5},{6},{7},{8},{9},{10},{11},{12},{13},{14},{15},{16},{17}",
                t, o, h, l, c,
                ce, cisd.State,
                Na(endBull), Na(endBear),
                fr.Event,
                fr.Event != 0 ? fr.Top.ToString("G") : "",
                fr.Event != 0 ? fr.Bottom.ToString("G") : "",
                ir.Event, br.Event,
                st.Signal,
                Na(st.EntryPrice), Na(st.StopPrice), Na(st.RiskPts)));
        }
        return 0;
    }

    static string Na(double v) { return double.IsNaN(v) ? "" : v.ToString("G", CultureInfo.InvariantCulture); }
}