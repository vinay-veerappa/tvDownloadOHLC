#if TESTING
// Minimal stubs for types used in RiskGuardAddOn.cs only available in NinjaTrader/Newtonsoft runtime
using System;
using System.Collections;
using System.Collections.Generic;

namespace Newtonsoft.Json.Linq
{
    public class JObject : IEnumerable<KeyValuePair<string, object>>
    {
        private readonly Dictionary<string, object> _data = new Dictionary<string, object>();
        public JObject() {}
        public JObject(params object[] kvPairs) {}

        public void Add(string key, object value) { _data[key] = value; }
        public object this[string key] { get => _data.ContainsKey(key) ? _data[key] : null; set => _data[key] = value; }
        public bool ContainsKey(string key) => _data.ContainsKey(key);

        public IEnumerator<KeyValuePair<string, object>> GetEnumerator() => _data.GetEnumerator();
        IEnumerator IEnumerable.GetEnumerator() => _data.GetEnumerator();

        public override string ToString() => "{}";
        public string ToString(Newtonsoft.Json.Formatting fmt) => "{}";
    }
}

namespace Newtonsoft.Json
{
    public enum Formatting { None, Indented }

    public static class JsonConvert
    {
        public static string SerializeObject(object obj) => "{}";
        public static string SerializeObject(object obj, Formatting fmt) => "{}";
        public static T DeserializeObject<T>(string json) where T : new() => new T();
    }
}

namespace NinjaTrader.Data
{
    public class BarsPeriod {}
    public enum BarsPeriodType { Minute, Day }
}

#endif
