#if TESTING
// Minimal stubs for types used in RiskGuardAddOn.cs only available in NinjaTrader runtime
using System;
using System.Collections;
using System.Collections.Generic;

namespace NinjaTrader.Data
{
    public class BarsPeriod {}
    public enum BarsPeriodType { Minute, Day }
}

namespace NinjaTrader.Cbi
{
    public enum ConnectionStatus { Connected, Disconnected, Connecting, ConnectionLost }
}

#endif
