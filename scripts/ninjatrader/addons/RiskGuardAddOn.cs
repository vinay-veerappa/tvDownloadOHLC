using System;
using System.IO;
using System.Text;
using System.Threading;
using System.Collections.Generic;
using System.Linq;
using System.Text.RegularExpressions;
#if !TESTING
using System.Windows;
using System.Windows.Controls;
using System.Windows.Media;
using System.Windows.Threading;
using Newtonsoft.Json;
using Newtonsoft.Json.Linq;
using NinjaTrader.Cbi;
using NinjaTrader.Data;
using NinjaTrader.Gui;
using NinjaTrader.Gui.Tools;
using NinjaTrader.NinjaScript;
using NinjaTrader.Core;
#else
using NinjaTrader.Cbi;
using NinjaTrader.NinjaScript;
using NinjaTrader.Core;
using NinjaTrader.Code;
using Newtonsoft.Json;
using Newtonsoft.Json.Linq;
#endif

namespace NinjaTrader.NinjaScript.AddOns
{
    public class RiskGuardAddOn : AddOnBase
    {
        public static RiskGuardAddOn Instance { get; private set; }
        public const string Version = "1.1.0";
        public object StateLock => _stateLock;
        public RiskConfig Config => _config;

        public void SaveAndReloadConfig(RiskConfig newConfig)
        {
            lock (_stateLock)
            {
                try
                {
                    string json = JsonConvert.SerializeObject(newConfig, Formatting.Indented);
                    File.WriteAllText(_configFile, json);
                    LoadConfig(); // Reloads from the file, updating _config and _parsedWindows
                    LogEvent("SYSTEM", "CONFIG_SAVE", "Configuration successfully saved and reloaded from UI.");
                }
                catch (Exception ex)
                {
                    LogEvent("SYSTEM", "ERROR", $"Failed to save config: {ex.Message}");
                }
            }
        }

        public void ReloadConfig()
        {
            LoadConfig();
        }

        // - FSM observation API (for MCP bridge; read-only, -7 of RiskGuardAddOn.md) -
        public class FsmSnapshot
        {
            public string AccountName { get; set; }
            public string Instrument { get; set; }
            public string State { get; set; }
            public string PositionSide { get; set; }
            public int PositionQuantity { get; set; }
            public DateTime EntryTime { get; set; }
            public DateTime GraceDeadline { get; set; }
            public bool HasAutoStopOrder { get; set; }
            public string RecognizedStopName { get; set; }
        }

        public List<FsmSnapshot> GetFsmSnapshots()
        {
            var list = new List<FsmSnapshot>();
            lock (_stateLock)
            {
                foreach (var fsm in _guardFsms.Values)
                {
                    list.Add(new FsmSnapshot
                    {
                        AccountName = fsm.AccountName,
                        Instrument = fsm.Instrument,
                        State = fsm.State.ToString(),
                        PositionSide = fsm.PositionSide.ToString(),
                        PositionQuantity = fsm.PositionQuantity,
                        EntryTime = fsm.EntryTime,
                        GraceDeadline = fsm.GraceDeadline,
                        HasAutoStopOrder = fsm.AutoStopOrder != null,
                        RecognizedStopName = fsm.RecognizedStopOrder?.Name
                    });
                }
            }
            return list;
        }

        public bool ResetFsm(string accountName, string instrument)
        {
            lock (_stateLock)
            {
                return _guardFsms.Remove(FsmKey(accountName, instrument));
            }
        }

        public bool CanTrade(string accountName, string instrument, string strategyName = "DefaultStrategy")
        {
            lock (_stateLock)
            {
                // FR-30 + judge-loop P1-4: lockouts persist even when disarmed, UNLESS the account is
                // explicitly listed in LockoutBypassWhileDisarmedAccounts (e.g. personal/SIM accounts).
                // This prevents a panic toggle-off from defeating a daily-loss/consecutive-loss lockout
                // on prop-firm accounts.
                if (_accountStates.TryGetValue(accountName, out var state) && state.IsLockedOut)
                {
                    bool bypassAllowed = !_isArmed
                        && _config.LockoutBypassWhileDisarmedAccounts != null
                        && _config.LockoutBypassWhileDisarmedAccounts.Contains(accountName);
                    if (!bypassAllowed) return false;
                }

                if (!_isArmed) return true;
                if (_config.ExcludedAccounts != null && _config.ExcludedAccounts.Contains(accountName)) return true;
                if (!string.IsNullOrEmpty(instrument))
                {
                    string root = instrument.Split(' ')[0].ToUpper();
                    if (_config.BlockedInstruments != null && _config.BlockedInstruments.Contains(root)) return false;
                }
                return true;
            }
        }

        public class AccountStateSnapshot
        {
            public string AccountName { get; set; }
            public bool IsLockedOut { get; set; }
            public double RealizedPnL { get; set; }
            public double UnrealizedPnL { get; set; }
            public int TradesToday { get; set; }
            public int ConsecutiveLosses { get; set; }
            public string PositionString { get; set; }
            public bool IsExcluded { get; set; }
            public double AccountEquity { get; set; }
            public DateTime LockoutUntil { get; set; }
        }

        public List<AccountStateSnapshot> GetAccountSnapshots()
        {
            var list = new List<AccountStateSnapshot>();
            lock (_stateLock)
            {
                foreach (var state in _accountStates.Values)
                {
                    var account = Account.All.FirstOrDefault(a => a.Name == state.AccountName);
                    if (account == null)
                    {
                        continue; // Skip historical/blown accounts not currently loaded
                    }
                    double equity = account.Get(AccountItem.CashValue, Currency.UsDollar) + account.Get(AccountItem.UnrealizedProfitLoss, Currency.UsDollar);
                    var snapshot = new AccountStateSnapshot
                    {
                        AccountName = state.AccountName,
                        IsLockedOut = state.IsLockedOut,
                        RealizedPnL = state.RealizedPnL,
                        UnrealizedPnL = state.UnrealizedPnL,
                        TradesToday = state.TradesToday,
                        ConsecutiveLosses = state.ConsecutiveLosses,
                        IsExcluded = _config.ExcludedAccounts != null && _config.ExcludedAccounts.Contains(state.AccountName),
                        AccountEquity = equity,
                        LockoutUntil = state.LockoutUntil
                    };
                    
                    var posList = new List<string>();
                    foreach (var pos in state.Positions.Values)
                    {
                        if (pos.MarketPosition != MarketPosition.Flat)
                        {
                            string posType = pos.MarketPosition == MarketPosition.Long ? "L" : "S";
                            posList.Add(string.Format("{0} {1} {2}", posType, pos.Quantity, pos.Instrument.Split(' ')[0]));
                        }
                    }
                    snapshot.PositionString = posList.Count > 0 ? string.Join(", ", posList) : "FLAT";
                    list.Add(snapshot);
                }
            }
            return list;
        }
        private string _logDir;
        private string _logFile;
        private string _stateFile;
        private string _configFile;
        private string _heartbeatFile;
        private DateTime _lastHeartbeatTime = DateTime.MinValue;
        private bool _stateDirty = false;

        private Timer _safetyTimer;
        private readonly object _stateLock = new object();
        // FR-30: Guard starts each session DISARMED; no enforcement until explicitly armed via Preflight().
        // Previously defaulted to true, which violated FR-30 and bypassed the arming ritual.
        // Under TESTING, tests assume an armed guard by default (call SetArmedForTest(false) to test disarm).
#if TESTING
        private bool _isArmed = true;
#else
        private bool _isArmed = false;
#endif
        // FR-29: count of completed shadow sessions, persisted across restarts. Incremented on session reset.
        private int _shadowSessionsCompleted = 0;
        // Tracks the session date already counted, so we only increment once per ET session day.
        private DateTime _lastShadowSessionDate = DateTime.MinValue.Date;
        private string _mode = "shadow"; // fail-safe default; overridden by config in LoadConfig()

        // Per-position guard state machines (see -6 of RiskGuardAddOn.md).
        // Keyed by "accountName|instrumentFullName". All access under _stateLock.
        private readonly Dictionary<string, PositionGuardFsm> _guardFsms = new Dictionary<string, PositionGuardFsm>();

        // Pending-stop buffer: stops whose OrderUpdate arrived before PositionUpdate
        // (possible per NT8 event ordering). Keyed by "accountName|instrumentFullName".
        // Each entry is the protective-side order awaiting FSM creation. Consumed
        // when the FSM is created on the position-open event; protects against the
        // race where the stop leg is observed before the position leg.
        private readonly Dictionary<string, Order> _pendingStops = new Dictionary<string, Order>();
#if !TESTING
        private NTMenuItem _myMenuItem;
        private ControlCenter _controlCenter;
#endif
        private RiskConfig _config = new RiskConfig();

        // Cached Resources (Fix 12)
        private TimeZoneInfo _etZone = TimeZoneInfo.FindSystemTimeZoneById(
            Environment.OSVersion.Platform == PlatformID.Win32NT
                ? "Eastern Standard Time"
                : "America/New_York");
        private List<ParsedWindow> _parsedWindows = new List<ParsedWindow>();

        // Async Logging (Fix 11)
        private readonly System.Collections.Concurrent.ConcurrentQueue<string> _logQueue = new System.Collections.Concurrent.ConcurrentQueue<string>();

        // Per-account and aggregate state models
        private readonly Dictionary<string, AccountState> _accountStates = new Dictionary<string, AccountState>();
        private readonly List<string> _subscribedAccounts = new List<string>();

        protected override void OnStateChange()
        {
            if (State == State.SetDefaults)
            {
                Name = "RiskGuardAddOn";
                Description = "Cross-Account Risk Guard and Discipline Backstop";
            }
            else if (State == State.Configure)
            {
                Instance = this;
                InitializeRiskGuard();
            }
            else if (State == State.Terminated)
            {
                CleanupRiskGuard();
            }
        }

        private void InitializeRiskGuard()
        {
            try
            {
                _logDir = Path.Combine(Globals.UserDataDir, "RiskGuard");
                if (!Directory.Exists(_logDir))
                {
                    Directory.CreateDirectory(_logDir);
                }

                _logFile = Path.Combine(_logDir, "interventions.jsonl");
                _stateFile = Path.Combine(_logDir, "state.json");
                _configFile = Path.Combine(_logDir, "config.json");
                _heartbeatFile = Path.Combine(_logDir, "heartbeat.txt");

                // Cache timezone (Fix 12)
                _etZone = TimeZoneInfo.FindSystemTimeZoneById("Eastern Standard Time");

                // Load or generate config
                LoadConfig();

                // Load any persisted lockout/session state
                LoadPersistedState();

                // Subscribe to existing accounts
                lock (_stateLock)
                {
                    foreach (Account account in Account.All)
                    {
                        SubscribeToAccount(account);
                    }
                }

                // Subscribe to connection events to catch new account connections dynamically
                Connection.ConnectionStatusUpdate += OnConnectionStatusUpdate;

                // Start 5-second safety sweep timer.
                // Phase 2: all per-account rules are event-driven (PositionUpdate/OrderUpdate).
                // The sweep only handles: heartbeat, log flush, session reset, aggregate
                // sizing, grace-expiry polling, firm-mirror, state persist, FSM watchdog.
                // None of these need 1-second resolution; 5s is sufficient.
                _safetyTimer = new Timer(OnSafetySweep, null, 5000, 5000);

                LogEvent("SYSTEM", "INITIALIZE", $"RiskGuard Add-On v{Version} initialized in {_mode} mode. Event monitoring started.");
                NinjaTrader.Code.Output.Process($"[RiskGuard v{Version}] RESOLVED MODE = {_mode} (armed={_isArmed})", PrintTo.OutputTab1);
            }
            catch (Exception ex)
            {
                LogEvent("SYSTEM", "ERROR", "Initialization failed: " + ex.ToString());
            }
        }

        private void CleanupRiskGuard()
        {
            try
            {
                // Stop safety timer
                _safetyTimer?.Dispose();

                // Unsubscribe from connection events
                Connection.ConnectionStatusUpdate -= OnConnectionStatusUpdate;

                // Unsubscribe from all accounts
                lock (_stateLock)
                {
                    foreach (Account account in Account.All)
                    {
                        UnsubscribeFromAccount(account);
                    }
                }

                // Persist current session state before exit
                SavePersistedState();

                LogEvent("SYSTEM", "SHUTDOWN", "RiskGuard Add-On shut down successfully.");
            }
            catch (Exception ex)
            {
                LogEvent("SYSTEM", "ERROR", "Cleanup failed: " + ex.ToString());
            }
        }

        // -
        // DEV/TESTING API
        // -
#if TESTING
        internal void SetConfigForTest(RiskConfig cfg)
        {
            _config = cfg;
        }

        internal void SetAccountStateForTest(string accountName, AccountState state)
        {
            _accountStates[accountName] = state;
        }

        internal void SetSubscribedAccountForTest(string accountName)
        {
            _subscribedAccounts.Add(accountName);
        }

        internal void SetArmedForTest(bool armed) { _isArmed = armed; }
        internal void SetModeForTest(string mode)  { _mode = mode; }
        internal void SetParsedWindowsForTest(List<ParsedWindow> windows) { _parsedWindows = windows; }
        internal bool GetIsArmed() => _isArmed;

        // - FSM test accessors (-6) -
        internal void TestFsmOnPosition(Account account, string instrument, MarketPosition pos, int qty)
        {
            lock (_stateLock) { UpdateFsmOnPosition(account, instrument, pos, qty); }
        }
        internal void TestFsmOnOrder(Account account, string instrument, Order order)
        {
            lock (_stateLock) { UpdateFsmOnOrder(account, instrument, order); }
        }
        internal PositionGuardFsm TestGetFsm(string accountName, string instrument)
        {
            lock (_stateLock)
            {
                return _guardFsms.TryGetValue(FsmKey(accountName, instrument), out var fsm) ? fsm : null;
            }
        }
        internal List<PositionGuardFsm> TestAllFsms()
        {
            lock (_stateLock) { return _guardFsms.Values.ToList(); }
        }
        internal void TestClearFsms()
        {
            lock (_stateLock) { _guardFsms.Clear(); _pendingStops.Clear(); }
        }
#endif

        public void ResetStateForDev()
        {
            lock (_stateLock)
            {
                _accountStates.Clear();
                _guardFsms.Clear();
                _pendingStops.Clear();
                try { LoadConfig(); } catch {}
                // We'll also clear the persisted file so it doesn't reload old state
                if (File.Exists(_stateFile))
                {
                    try { File.Delete(_stateFile); } catch {}
                }
                LogEvent("SYSTEM", "DEV_RESET", "State was reset via Developer API.");
            }
        }

        private void SubscribeToAccount(Account account)
        {
            if (account == null) return;
            if (_subscribedAccounts.Contains(account.Name)) return;

            account.PositionUpdate += OnPositionUpdate;
            account.OrderUpdate += OnOrderUpdate;
            account.ExecutionUpdate += OnExecutionUpdate;
            account.AccountItemUpdate += OnAccountItemUpdate;

            _subscribedAccounts.Add(account.Name);

            if (!_accountStates.TryGetValue(account.Name, out var state))
            {
                state = new AccountState(account.Name);
                state.SessionStartRealizedPnL = account.Get(AccountItem.RealizedProfitLoss, Currency.UsDollar);
                state.LastRealizedPnL = state.SessionStartRealizedPnL;
                _accountStates[account.Name] = state;
            }
            else
            {
                if (state.SessionStartRealizedPnL == 0.0)
                {
                    state.SessionStartRealizedPnL = account.Get(AccountItem.RealizedProfitLoss, Currency.UsDollar);
                    state.LastRealizedPnL = state.SessionStartRealizedPnL;
                }
            }

            LogEvent("SYSTEM", "SUBSCRIBE", $"Subscribed to account events for: {account.Name}");

            // P1-6 (judge loop): instantiate FSMs for positions that already exist at subscribe time
            // (e.g. add-on startup, account reconnect, or NT8 restart mid-trade). Without this,
            // an existing position has no stop-guard until it first goes flat and re-enters.
            SeedFsmsForExistingPositions(account);
        }

        // Creates a PositionGuardFsm for every non-flat position currently on `account`.
        // If a working protective stop already exists in account.Orders (e.g. placed from
        // TradingView/Tradovate before the guard started), the FSM is seeded as Protected
        // instead of Unprotected so the grace timer does NOT fire a duplicate auto-stop.
        private void SeedFsmsForExistingPositions(Account account)
        {
            if (account == null) return;
            if (_config.ExcludedAccounts != null && _config.ExcludedAccounts.Contains(account.Name)) return;

            try
            {
                foreach (Position pos in account.Positions)
                {
                    if (pos == null || pos.MarketPosition == MarketPosition.Flat || pos.Quantity <= 0) continue;
                    string instrument = pos.Instrument != null ? pos.Instrument.FullName : null;
                    if (string.IsNullOrEmpty(instrument)) continue;

                    string key = FsmKey(account.Name, instrument);
                    if (_guardFsms.ContainsKey(key)) continue; // already tracked

                    var fsm = new PositionGuardFsm(account.Name, instrument)
                    {
                        PositionSide = pos.MarketPosition,
                        PositionQuantity = pos.Quantity,
                        EntryTime = DateTime.UtcNow,
                        State = GuardFsmState.Unprotected
                    };

                    // Scan existing working orders for a protective stop on the opposite side.
                    // If found, seed the FSM as Protected (or ProtectedPending) so the grace
                    // timer does not place a duplicate auto-stop on an already-covered position.
                    foreach (Order o in account.Orders)
                    {
                        if (o == null || o.Instrument == null) continue;
                        if (!string.Equals(o.Instrument.FullName, instrument, StringComparison.OrdinalIgnoreCase)) continue;
                        if (!IsStopType(o) || !IsProtectiveSide(o, pos.MarketPosition)) continue;
                        if (IsTerminal(o.OrderState)) continue;
                        fsm.RecognizedStopOrder = o;
                        fsm.CoveredQuantity = o.Quantity;
                        fsm.State = o.OrderState == OrderState.Working
                            ? GuardFsmState.Protected
                            : GuardFsmState.ProtectedPending;
                        break;
                    }

                    // Arm a one-shot grace timer only if still Unprotected (no existing stop found).
                    if (fsm.State == GuardFsmState.Unprotected && _config.StopGuard.StopAttachSeconds > 0)
                    {
                        ArmGraceTimer(fsm, account, instrument, _config.StopGuard.StopAttachSeconds * 1000);
                    }
                    else if (fsm.State != GuardFsmState.Unprotected && fsm.CoveredQuantity < fsm.PositionQuantity)
                    {
                        // Existing stop is under-sized; arm the grace timer for the uncovered delta.
                        fsm.GraceEmitted = false;
                        if (!fsm.GracePending)
                        {
                            ArmGraceTimer(fsm, account, instrument, _config.StopGuard.StopAttachSeconds * 1000);
                        }
                    }

                    _guardFsms[key] = fsm;
                    LogEvent(account.Name, "FSM_SEED",
                        $"Seeded FSM for existing position {key} -> {fsm.State} (qty {fsm.PositionQuantity})");
                }
            }
            catch (Exception ex)
            {
                LogEvent(account.Name, "ERROR", "SeedFsmsForExistingPositions failed: " + ex.Message);
            }
        }

        private void UnsubscribeFromAccount(Account account)
        {
            if (account == null) return;
            if (!_subscribedAccounts.Contains(account.Name)) return;

            account.PositionUpdate -= OnPositionUpdate;
            account.OrderUpdate -= OnOrderUpdate;
            account.ExecutionUpdate -= OnExecutionUpdate;
            account.AccountItemUpdate -= OnAccountItemUpdate;

            _subscribedAccounts.Remove(account.Name);
            LogEvent("SYSTEM", "UNSUBSCRIBE", $"Unsubscribed from account events for: {account.Name}");
        }

        // -
        // CONFIG & STATE PERSISTENCE
        // -

        private void LoadConfig()
        {
            try
            {
                if (File.Exists(_configFile))
                {
                    string json = File.ReadAllText(_configFile);
                    _config = JsonConvert.DeserializeObject<RiskConfig>(json) ?? new RiskConfig();
                    _mode = _config.Mode;
                }
                else
                {
                    _config = new RiskConfig();
                    string json = JsonConvert.SerializeObject(_config, Formatting.Indented);
                    File.WriteAllText(_configFile, json);
                }

                // Cache parsed windows (Fix 12)
                _parsedWindows.Clear();
                if (_config.WindowsET != null)
                {
                    foreach (var win in _config.WindowsET)
                    {
                        var pw = new ParsedWindow
                        {
                            Start = TimeSpan.Parse(win.Start),
                            End = TimeSpan.Parse(win.End),
                            Days = new HashSet<DayOfWeek>()
                        };
                        foreach (var d in win.Days)
                        {
                            if (Enum.TryParse(d, out DayOfWeek dow))
                            {
                                pw.Days.Add(dow);
                            }
                        }
                        _parsedWindows.Add(pw);
                    }
                }
            }
            catch (Exception ex)
            {
                LogEvent("SYSTEM", "ERROR", $"Failed to load config: {ex.Message}");
            }
        }

        /// <summary>Called by the MCP bridge to hot-reload state.json into the live instance.</summary>
        public void ReloadPersistedState() => LoadPersistedState();

        private void LoadPersistedState()
        {
            lock (_stateLock)
            {
                try
                {
                    if (File.Exists(_stateFile))
                    {
                        string json = File.ReadAllText(_stateFile);
                        var data = JsonConvert.DeserializeObject<PersistedStateData>(json);
                        if (data != null)
                        {
                            // FR-30/31: never rehydrate the armed flag from persisted state.
                            // Lockouts persist, but armed state must be set fresh each session via Preflight().
                            // Previously: _isArmed = data.IsArmed;  (could silently re-arm across restarts)
                            _isArmed = false;
                            // FR-29: shadow-session counter IS rehydrated (it accumulates across sessions).
                            _shadowSessionsCompleted = data.ShadowSessionsCompleted;
                            if (data.LockedOutAccounts != null)
                            {
                                foreach (var accName in data.LockedOutAccounts)
                                {
                                    if (!_accountStates.TryGetValue(accName, out var state))
                                    {
                                        state = new AccountState(accName);
                                        _accountStates[accName] = state;
                                    }
                                    state.IsLockedOut = true;
                                }
                            }
                            if (data.AccountsData != null)
                            {
                                foreach (var kvp in data.AccountsData)
                                {
                                    if (!_accountStates.TryGetValue(kvp.Key, out var state))
                                    {
                                        state = new AccountState(kvp.Key);
                                        _accountStates[kvp.Key] = state;
                                    }
                                    state.LastSessionDate = kvp.Value.LastSessionDate;
                                    state.TradesToday = kvp.Value.TradesToday;
                                    state.ConsecutiveLosses = kvp.Value.ConsecutiveLosses;
                                    state.PeakEquity = kvp.Value.PeakEquity;
                                    state.LastRealizedPnL = kvp.Value.LastRealizedPnL;
                                    state.SessionStartRealizedPnL = kvp.Value.SessionStartRealizedPnL;
                                    state.FirmTrailingPeak = kvp.Value.FirmTrailingPeak;
                                    state.FirmFloorLocked = kvp.Value.FirmFloorLocked;
                                    state.FirmDailyDate = kvp.Value.FirmDailyDate;
                                    state.FirmDailyStartRealized = kvp.Value.FirmDailyStartRealized;
                                    state.FirmStartingBalance = kvp.Value.FirmStartingBalance;
                                }
                            }
                        }
                    }
                }
                catch (Exception ex)
                {
                    LogEvent("SYSTEM", "ERROR", $"Failed to load persisted state: {ex.Message}");
                }
            }
        }

        private void SavePersistedState()
        {
            lock (_stateLock)
            {
                try
                {
                    var lockedOut = _accountStates.Values.Where(s => s.IsLockedOut).Select(s => s.AccountName).ToList();
                    var accountsData = new Dictionary<string, AccountPersistedData>();
                    foreach (var state in _accountStates.Values)
                    {
                        accountsData[state.AccountName] = new AccountPersistedData
                        {
                            LastSessionDate = state.LastSessionDate,
                            TradesToday = state.TradesToday,
                            ConsecutiveLosses = state.ConsecutiveLosses,
                            PeakEquity = state.PeakEquity,
                            LastRealizedPnL = state.LastRealizedPnL,
                            SessionStartRealizedPnL = state.SessionStartRealizedPnL,
                            FirmTrailingPeak = state.FirmTrailingPeak,
                            FirmFloorLocked = state.FirmFloorLocked,
                            FirmDailyDate = state.FirmDailyDate,
                            FirmDailyStartRealized = state.FirmDailyStartRealized,
                            FirmStartingBalance = state.FirmStartingBalance
                        };
                    }
                    var data = new PersistedStateData
                    {
                        IsArmed = _isArmed,
                        ShadowSessionsCompleted = _shadowSessionsCompleted,
                        LockedOutAccounts = lockedOut,
                        AccountsData = accountsData,
                        Timestamp = DateTime.UtcNow
                    };
                    string json = JsonConvert.SerializeObject(data, Formatting.Indented);
                    File.WriteAllText(_stateFile, json);
                }
                catch (Exception ex)
                {
                    LogEvent("SYSTEM", "ERROR", $"Failed to save persisted state: {ex.Message}");
                }
            }
        }

        // -
#if !TESTING
        // WINDOW INTERCEPTION (UI INJECTION)
        // -

        protected override void OnWindowCreated(Window window)
        {
            ControlCenter cc = window as ControlCenter;
            if (cc == null) return;
            _controlCenter = cc;

            cc.Dispatcher.InvokeAsync(() =>
            {
                try
                {
                    NTMenuItem existingMenuItem = cc.FindFirst("ControlCenterMenuItemNew") as NTMenuItem;
                    if (existingMenuItem == null)
                    {
                        LogEvent("SYSTEM", "UI_ERROR", "ControlCenterMenuItemNew not found. Menu injection skipped.");
                        return;
                    }

                    _myMenuItem = new NTMenuItem
                    {
                        Header = "Risk Guard Dashboard",
                        Style = Application.Current.TryFindResource("MainMenuItem") as Style
                    };

                    _myMenuItem.Click += OnMenuItemClick;
                    existingMenuItem.Items.Add(_myMenuItem);

                    LogEvent("SYSTEM", "UI_INJECT", "Risk Guard Dashboard added to Control Center 'New' menu.");
                }
                catch (Exception ex)
                {
                    LogEvent("SYSTEM", "UI_ERROR", "Failed to inject menu item: " + ex.Message);
                }
            });
        }

        protected override void OnWindowDestroyed(Window window)
        {
            ControlCenter cc = window as ControlCenter;
            if (cc == null) return;

            if (_myMenuItem != null)
            {
                NTMenuItem existingMenuItem = cc.FindFirst("ControlCenterMenuItemNew") as NTMenuItem;
                existingMenuItem?.Items.Remove(_myMenuItem);
                _myMenuItem = null;
            }
        }

        private void OnMenuItemClick(object sender, RoutedEventArgs e)
        {
            try
            {
                var win = new RiskGuardWindow(this);
                if (_controlCenter != null)
                {
                    win.Owner = _controlCenter;
                }
                win.Show();
            }
            catch (Exception ex)
            {
                LogEvent("SYSTEM", "UI_ERROR", "Failed to open dashboard window: " + ex.Message);
            }
        }
#endif

        // -
        // EVENT HANDLERS
        // -

        private void OnConnectionStatusUpdate(object sender, ConnectionStatusEventArgs e)
        {
            LogEvent("SYSTEM", "CONNECTION_CHANGE", $"Connection status: {e.Status}, Connection: {e.Connection?.Options?.Name}");
            
            // Re-check, subscribe, and audit open positions for any account returning online
            lock (_stateLock)
            {
                foreach (Account account in Account.All)
                {
                    SubscribeToAccount(account);
                    if (e.Status.ToString() == "Connected")
                    {
                        foreach (Position pos in account.Positions)
                        {
                            if (pos.MarketPosition != MarketPosition.Flat && pos.Instrument != null)
                            {
                                AuditPosition(account, pos);
                            }
                        }
                    }
                }
            }
        }

        private void AuditPosition(Account account, Position pos)
        {
            if (account == null || pos == null || pos.Instrument == null) return;
            ExecutePositionUpdateDetails(account, pos);
        }




        public bool IsAccountLocked(string accountName)
        {
            lock (_stateLock)
            {
                if (_accountStates.TryGetValue(accountName, out var state))
                {
                    return state.IsLockedOut;
                }
                return false;
            }
        }

        private void OnPositionUpdate(object sender, PositionEventArgs e)
        {
#if TESTING
            ExecutePositionUpdate(sender, e);
#else
            var dispatcher = Application.Current?.Dispatcher;
            if (dispatcher == null) return;

            dispatcher.InvokeAsync(() =>
            {
                ExecutePositionUpdate(sender, e);
            });
#endif
        }

        internal void ExecutePositionUpdate(object sender, PositionEventArgs e)
        {
            if (sender is Account acc && e?.Position != null)
            {
                ExecutePositionUpdateDetails(acc, e.Position);
            }
        }

        internal void ExecutePositionUpdateDetails(Account account, Position pos)
        {
            List<GuardAction> actions = null;
            try
            {
                string accountName = account.Name;
                string instrument = pos.Instrument.FullName;
                MarketPosition marketPosition = pos.MarketPosition;
                int quantity = pos.Quantity;
                double averagePrice = pos.AveragePrice;
                double unrealizedPnL = 0.0;
                try { unrealizedPnL = pos.GetUnrealizedProfitLoss(PerformanceUnit.Currency); } catch { }

                lock (_stateLock)
                {
                    if (!_accountStates.TryGetValue(accountName, out var state))
                    {
                        state = new AccountState(accountName);
                        state.SessionStartRealizedPnL = account.Get(AccountItem.RealizedProfitLoss, Currency.UsDollar);
                        state.LastRealizedPnL = state.SessionStartRealizedPnL;
                        _accountStates[accountName] = state;
                    }

                    bool changed = state.UpdatePosition(account, pos.Instrument, marketPosition, quantity, averagePrice, unrealizedPnL, _config);

                    if (changed)
                    {
                        SavePersistedState();
                    }

                    LogEvent(accountName, "POSITION_UPDATE", new JObject
                    {
                        { "instrument", instrument },
                        { "marketPosition", marketPosition.ToString() },
                        { "quantity", quantity },
                        { "averagePrice", averagePrice },
                        { "unrealizedPnL", unrealizedPnL }
                    });

                    // - Per-position guard FSM (-6) -
                    // On flat->nonflat: create/reset FSM, arm grace timer, consume any pending stop.
                    // On nonflat->flat: transition to Flat, cancel grace, cancel orphan auto-stop.
                    UpdateFsmOnPosition(account, instrument, marketPosition, quantity);

                    // -- Event-driven rule evaluation (Phase 2: no longer on the sweep) --
                    // EvaluateRules fires here on every position change. The sweep no
                    // longer calls EvaluateRules; all per-account rules are event-driven.
                    actions = EvaluateRules(account, state);

                    // -- Aggregate sizing (event-driven via PositionUpdate) --
                    // Scan all accounts' positions instantly on any position change.
                    var aggregateActions = EvaluateAggregateSizing();
                    if (aggregateActions != null && aggregateActions.Count > 0)
                    {
                        if (actions == null) actions = new List<GuardAction>();
                        actions.AddRange(aggregateActions);
                    }

                    // -- Lockout phase enforcement (event-driven via PositionUpdate) --
                    // When a position goes flat, check if the lockout can advance to Confirmed.
                    // When a position appears while locked, emit the phased flatten/cancel actions.
                    var lockoutActions = EvaluateLockoutPhase(account, state);
                    if (lockoutActions != null && lockoutActions.Count > 0)
                    {
                        if (actions == null) actions = new List<GuardAction>();
                        actions.AddRange(lockoutActions);
                    }
                }

                if (actions != null)
                {
                    foreach (var action in actions)
                    {
                        ProcessAction(action);
                    }
                }
            }
            catch (Exception ex)
            {
                LogEvent("SYSTEM", "ERROR", $"Error handling OnPositionUpdate: {ex.Message}");
            }
        }

        private void OnExecutionUpdate(object sender, ExecutionEventArgs e)
        {
#if TESTING
            ExecuteExecutionUpdate(sender, e);
#else
            var dispatcher = Application.Current?.Dispatcher;
            if (dispatcher == null) return;

            dispatcher.InvokeAsync(() =>
            {
                ExecuteExecutionUpdate(sender, e);
            });
#endif
        }

        internal void ExecuteExecutionUpdate(object sender, ExecutionEventArgs e)
        {
            lock (_stateLock)
            {
                try
                {
                    Account account = (Account)sender;
                    string accountName = account.Name;
                    string instrument = e.Execution.Instrument.FullName;
                    string orderId = e.Execution.Order != null ? e.Execution.Order.Id.ToString() : "N/A";
                    int quantity = e.Execution.Quantity;
                    double price = e.Execution.Price;
                    string action = e.Execution.Order?.OrderAction.ToString() ?? "N/A";

                    if (!_accountStates.TryGetValue(accountName, out var state))
                    {
                        state = new AccountState(accountName);
                        _accountStates[accountName] = state;
                    }

                    state.RecordExecution(instrument, action, quantity, price);

                    LogEvent(accountName, "EXECUTION_UPDATE", new JObject
                    {
                        { "instrument", instrument },
                        { "orderId", orderId },
                        { "action", action },
                        { "quantity", quantity },
                        { "price", price }
                    });
                }
                catch (Exception ex)
                {
                    LogEvent("SYSTEM", "ERROR", $"Error handling OnExecutionUpdate: {ex.Message}");
                }
            }
        }

        // -- AccountItemUpdate: fires when RealizedPnL, UnrealizedPnL, CashValue, NetLiquidation change --
        // This replaces the sweep's PnL polling with instant event-driven PnL rules.
        private void OnAccountItemUpdate(object sender, AccountItemEventArgs e)
        {
#if TESTING
            ExecuteAccountItemUpdate(sender, e);
#else
            var dispatcher = Application.Current?.Dispatcher;
            if (dispatcher == null) return;
            dispatcher.InvokeAsync(() => ExecuteAccountItemUpdate(sender, e));
#endif
        }

        internal void ExecuteAccountItemUpdate(object sender, AccountItemEventArgs e)
        {
            List<GuardAction> actions = null;
            try
            {
                Account account = (Account)sender;
                string accountName = account.Name;

                if (_config.ExcludedAccounts != null && _config.ExcludedAccounts.Contains(accountName)) return;

                lock (_stateLock)
                {
                    if (!_accountStates.TryGetValue(accountName, out var state))
                        return;

                    // Only react to PnL-related items
                    if (e.AccountItem == AccountItem.RealizedProfitLoss)
                    {
                        double rawRealized = e.Value;
                        double newRealizedPnL = rawRealized - state.SessionStartRealizedPnL;

                        if (Math.Abs(newRealizedPnL - state.RealizedPnL) > 0.001)
                        {
                            double tradePnL = newRealizedPnL - state.RealizedPnL;
                            if (tradePnL < -0.01)
                                state.ConsecutiveLosses++;
                            else if (tradePnL > 0.01)
                                state.ConsecutiveLosses = 0;

                            state.LastRealizedPnL = rawRealized;
                            state.RealizedPnL = newRealizedPnL;

                            // Apply cooldown if consecutive loss limit breached
                            if (state.ConsecutiveLosses >= _config.Overtrading.MaxConsecutiveLosses && _config.Overtrading.CooldownMinutes > 0)
                            {
                                state.CooldownUntil = DateTime.UtcNow.AddMinutes(_config.Overtrading.CooldownMinutes);
                            }
                            _stateDirty = true;
                        }

                        // Evaluate PnL-based rules instantly
                        actions = EvaluatePnLRules(account, state);
                    }
                    else if (e.AccountItem == AccountItem.UnrealizedProfitLoss ||
                             e.AccountItem == AccountItem.NetLiquidation ||
                             e.AccountItem == AccountItem.CashValue)
                    {
                        // Update unrealized PnL and evaluate trailing DD / firm mirror
                        state.UnrealizedPnL = account.Get(AccountItem.UnrealizedProfitLoss, Currency.UsDollar);

                        // Update peak equity for trailing DD
                        double currentPnL = state.RealizedPnL + state.UnrealizedPnL;
                        if (currentPnL > state.PeakEquity)
                            state.PeakEquity = currentPnL;

                        actions = EvaluatePnLRules(account, state);

                        // Firm mirror on PnL change
                        if (_config.FirmMirror != null && _config.FirmMirror.Enabled)
                        {
                            DateTime nowEt = TimeZoneInfo.ConvertTimeFromUtc(DateTime.UtcNow, _etZone);
                            // FirmMirror's daily boundary is expressed in UTC
                            // (FirmMirror.DailyResetHourUtc), so pass UTC. This previously passed
                            // nowEt, which the method silently ignored in favour of DateTime.UtcNow.
                            var firmActions = EvaluateFirmMirror(account, state, DateTime.UtcNow);
                            if (firmActions != null && firmActions.Count > 0)
                            {
                                if (actions == null) actions = new List<GuardAction>();
                                actions.AddRange(firmActions);
                            }
                        }
                    }
                }

                if (actions != null)
                {
                    foreach (var action in actions)
                        ProcessAction(action);
                }
            }
            catch (Exception ex)
            {
                LogEvent("SYSTEM", "ERROR", "Error handling OnAccountItemUpdate: " + ex.Message);
            }
        }

        // Evaluate PnL-based rules (DailyLoss, TrailingDrawdown) - called from AccountItemUpdate.
        internal List<GuardAction> EvaluatePnLRules(Account account, AccountState stateModel)
        {
            var actions = new List<GuardAction>();
            if (!_isArmed) return actions;
            if (_config.ExcludedAccounts != null && _config.ExcludedAccounts.Contains(stateModel.AccountName)) return actions;

            var profile = GetResolvedProfile(account);
            if (profile == null) return actions;

            double currentPnL = stateModel.RealizedPnL + stateModel.UnrealizedPnL;

            // Daily Loss
            if (currentPnL < -profile.DailyLossLimit)
            {
                actions.Add(new GuardAction
                {
                    AccountName = stateModel.AccountName,
                    ActionType = GuardActionType.FlattenPosition,
                    RuleId = "DAILY_LOSS_BREACH"
                });
                if (!stateModel.IsLockedOut)
                {
                    stateModel.IsLockedOut = true;
                    if (_config.PnLRules.LockoutMinutes > 0)
                        stateModel.LockoutUntil = DateTime.UtcNow.AddMinutes(_config.PnLRules.LockoutMinutes);
                    _stateDirty = true;
                }
            }

            // Trailing Drawdown
            if (currentPnL > stateModel.PeakEquity)
                stateModel.PeakEquity = currentPnL;
            if (currentPnL < stateModel.PeakEquity - profile.TrailingDrawdown)
            {
                actions.Add(new GuardAction
                {
                    AccountName = stateModel.AccountName,
                    ActionType = GuardActionType.FlattenPosition,
                    RuleId = "TRAILING_DD_BREACH"
                });
                if (!stateModel.IsLockedOut)
                {
                    stateModel.IsLockedOut = true;
                    if (_config.PnLRules.LockoutMinutes > 0)
                        stateModel.LockoutUntil = DateTime.UtcNow.AddMinutes(_config.PnLRules.LockoutMinutes);
                    _stateDirty = true;
                }
            }

            // Prop Firm Protection Suite Integrations (News Shield, Target Profit Lock, Peak Giveback)
            var propSuite = PropFirmProtectionSuite.Instance;
            if (propSuite != null && propSuite.Config != null)
            {
                // Peak Open Gain tracks the running peak of unrealized PnL for
                // the current open position. It resets when the account is flat
                // and only rises while a position is open.
                bool accountIsFlat = true;
                foreach (var pos in stateModel.Positions.Values)
                {
                    if (pos.MarketPosition != MarketPosition.Flat)
                    {
                        accountIsFlat = false;
                        break;
                    }
                }

                if (!accountIsFlat)
                {
                    if (stateModel.UnrealizedPnL > stateModel.PeakOpenGain)
                    {
                        // New peak = new episode. Re-arm the giveback latch.
                        stateModel.PeakOpenGain = stateModel.UnrealizedPnL;
                        stateModel.PeakGivebackTriggered = false;
                        stateModel.PeakGivebackLastTriggerUnrealized = double.NaN;
                        _stateDirty = true;
                    }
                }
                else
                {
                    bool needsReset = stateModel.PeakOpenGain != 0.0
                        || stateModel.PeakGivebackTriggered
                        || !double.IsNaN(stateModel.PeakGivebackLastTriggerUnrealized);
                    if (needsReset)
                    {
                        stateModel.PeakOpenGain = 0.0;
                        stateModel.PeakGivebackTriggered = false;
                        stateModel.PeakGivebackLastTriggerUnrealized = double.NaN;
                        _stateDirty = true;
                    }
                }

                if (propSuite.Config.EnableNewsShield && propSuite.IsInNewsWindow(DateTime.UtcNow, propSuite.Config.NewsBufferMinutesBefore, propSuite.Config.NewsBufferMinutesAfter))
                {
                    actions.Add(new GuardAction
                    {
                        AccountName = stateModel.AccountName,
                        ActionType = GuardActionType.FlattenPosition,
                        RuleId = "NEWS_SHIELD_LOCKOUT"
                    });
                    if (!stateModel.IsLockedOut)
                    {
                        stateModel.IsLockedOut = true;
                        _stateDirty = true;
                    }
                }

                if (propSuite.EvaluateProfitTargetLock(stateModel.RealizedPnL, propSuite.Config))
                {
                    actions.Add(new GuardAction
                    {
                        AccountName = stateModel.AccountName,
                        ActionType = GuardActionType.FlattenPosition,
                        RuleId = "EVALUATION_TARGET_REACHED"
                    });
                    if (!stateModel.IsLockedOut)
                    {
                        stateModel.IsLockedOut = true;
                        _stateDirty = true;
                    }
                }

                if (!accountIsFlat && stateModel.PeakOpenGain > 0)
                {
                    if (propSuite.EvaluatePeakEquityGiveback(stateModel.PeakOpenGain, stateModel.UnrealizedPnL, propSuite.Config))
                    {
                        bool alreadyTriggered = stateModel.PeakGivebackTriggered;
                        bool worsenedSinceTrigger = alreadyTriggered
                            && stateModel.UnrealizedPnL < stateModel.PeakGivebackLastTriggerUnrealized;

                        // Fire on the first breach of the episode, and re-fire if the
                        // position gives back further than the prior trigger point.
                        // This prevents a silently-failed flatten from leaving the
                        // position unprotected as the loss continues to deepen.
                        if (!alreadyTriggered || worsenedSinceTrigger)
                        {
                            actions.Add(new GuardAction
                            {
                                AccountName = stateModel.AccountName,
                                ActionType = GuardActionType.FlattenPosition,
                                RuleId = "PEAK_GIVEBACK_BREACH"
                            });
                            stateModel.PeakGivebackTriggered = true;
                            stateModel.PeakGivebackLastTriggerUnrealized = stateModel.UnrealizedPnL;
                            _stateDirty = true;
                        }
                    }
                }
            }

            return actions;
        }

        private void OnOrderUpdate(object sender, OrderEventArgs e)
        {
#if TESTING
            ExecuteOrderUpdate(sender, e);
#else
            var dispatcher = Application.Current?.Dispatcher;
            if (dispatcher == null) return;

            dispatcher.InvokeAsync(() =>
            {
                ExecuteOrderUpdate(sender, e);
            });
#endif
        }

        internal void ExecuteOrderUpdate(object sender, OrderEventArgs e)
        {
            List<GuardAction> lockoutActions = null;
            lock (_stateLock)
            {
                try
                {
                    Account account = (Account)sender;
                    string accountName = account.Name;
                    if (_config.ExcludedAccounts != null && _config.ExcludedAccounts.Contains(accountName))
                    {
                        // Skip entry cancellation for excluded accounts
                    }
                    else if (_accountStates.TryGetValue(accountName, out var stateModel))
                    {
                        // Order Rate Governor: detect rogue strategy order loops (>5 orders/sec)
                        if (e.Order.OrderState == OrderState.Submitted || e.Order.OrderState == OrderState.Accepted)
                        {
                            stateModel.OrderTimestamps.Add(DateTime.UtcNow);
                            stateModel.OrderTimestamps.RemoveAll(t => t < DateTime.UtcNow.AddSeconds(-1));
                            if (stateModel.OrderTimestamps.Count > 5)
                            {
                                stateModel.IsLockedOut = true;
                                if (e.Order.OrderState != OrderState.Filled && e.Order.OrderState != OrderState.Cancelled)
                                {
                                    account.Cancel(new[] { e.Order });
                                }
                                LogEvent(accountName, "ORDER_FLOOD_LOCKOUT", $"ORDER FLOOD DETECTED: Rogue order rate ({stateModel.OrderTimestamps.Count} orders/sec) triggered instant lockout.");
                            }
                        }

                        if (stateModel.IsLockedOut || stateModel.ConsecutiveLosses >= _config.Overtrading.MaxConsecutiveLosses)
                        {
                            if (e.Order.OrderState == OrderState.Submitted || e.Order.OrderState == OrderState.Accepted || e.Order.OrderState == OrderState.Working)
                            {
                                if (!IsPositionReducingOrder(e.Order, stateModel))
                                {
                                    if (e.Order.OrderType == OrderType.Limit || e.Order.OrderType == OrderType.StopMarket || e.Order.OrderType == OrderType.StopLimit || e.Order.OrderType == OrderType.Market)
                                    {
                                        account.Cancel(new[] { e.Order });
                                        LogEvent(accountName, "ENTRY_CANCEL", $"Cancelled order {e.Order.Id} because account is locked out.");
                                    }
                                }
                            }
                        }
                    }

                    string rawInst = e.Order.Instrument != null ? e.Order.Instrument.FullName : "";
                    string instRoot = rawInst.Split(' ')[0].ToUpper();
                    if (_config.BlockedInstruments != null && _config.BlockedInstruments.Contains(instRoot))
                    {
                        if (e.Order.OrderState == OrderState.Submitted || e.Order.OrderState == OrderState.Accepted || e.Order.OrderState == OrderState.Working)
                        {
                            account.Cancel(new[] { e.Order });
                            LogEvent(accountName, "BLACKLIST_CANCEL", $"Cancelled order {e.Order.Id} because instrument {instRoot} is blacklisted.");
                        }
                    }
                    if (_config.InstrumentLimits != null && _config.InstrumentLimits.TryGetValue(instRoot, out var perInstCap))
                    {
                        if (e.Order.Quantity > perInstCap.MaxContracts)
                        {
                            if (e.Order.OrderState == OrderState.Submitted || e.Order.OrderState == OrderState.Accepted || e.Order.OrderState == OrderState.Working)
                            {
                                account.Cancel(new[] { e.Order });
                                LogEvent(accountName, "PER_INSTRUMENT_CAP_CANCEL", $"Cancelled order {e.Order.Id} because quantity {e.Order.Quantity} exceeds {instRoot} cap ({perInstCap.MaxContracts}).");
                            }
                        }
                    }
                    string instrument = e.Order.Instrument.FullName;
                    string orderId = e.Order.Id.ToString();
                    string orderState = e.Order.OrderState.ToString();
                    string orderType = e.Order.OrderType.ToString();
                    double limitPrice = e.Order.LimitPrice;
                    double stopPrice = e.Order.StopPrice;
                    int quantity = e.Order.Quantity;

                    // - Per-position guard FSM (-6) -
                    // Classify this order against the active FSM for (account, instrument).
                    // If no FSM exists yet but this is a protective-side stop, buffer it
                    // in _pendingStops so it is consumed when the position-open event arrives.
                    UpdateFsmOnOrder(account, instrument, e.Order);

                    // -- Lockout phase: advance on order state changes --
                    // When an order goes Cancelled/Filled, check if the lockout can
                    // advance to the next phase (PendingFlatten or Confirmed).
                    // Collect actions here; process OUTSIDE the lock to avoid
                    // re-entrancy corruption when ProcessAction triggers events.
                    if (_accountStates.TryGetValue(accountName, out var lockState) &&
                        (lockState.IsLockedOut || DateTime.UtcNow < lockState.LockoutUntil))
                    {
                        lockoutActions = EvaluateLockoutPhase(account, lockState);
                    }

                    LogEvent(accountName, "ORDER_UPDATE", new JObject
                    {
                        { "instrument", instrument },
                        { "orderId", orderId },
                        { "orderState", orderState },
                        { "orderType", orderType },
                        { "orderAction", e.Order.OrderAction.ToString() },
                        { "orderName", e.Order.Name ?? "" },
                        { "quantity", quantity },
                        { "limitPrice", limitPrice },
                        { "stopPrice", stopPrice }
                    });
                }
                catch (Exception ex)
                {
                    LogEvent("SYSTEM", "ERROR", $"Error handling OnOrderUpdate: {ex.Message}");
                }
            }

            // Process lockout actions OUTSIDE the lock to prevent re-entrancy.
            if (lockoutActions != null && lockoutActions.Count > 0)
            {
                foreach (var a in lockoutActions)
                {
                    ProcessAction(a);
                }
            }
        }

        internal bool IsPositionReducingOrder(Order order, AccountState stateModel)
        {
            return RiskGuardOrderUtils.IsPositionReducingOrder(order, stateModel);
        }

        internal void OnSafetySweep(object state)
        {
#if TESTING
            ExecuteSafetySweep();
#else
            try
            {
                var dispatcher = Application.Current?.Dispatcher;
                if (dispatcher == null) return;

                dispatcher.InvokeAsync(() =>
                {
                    ExecuteSafetySweep();
                });
            }
            catch (Exception ex)
            {
                LogEvent("SYSTEM", "ERROR", $"Error in OnSafetySweep Dispatcher: {ex.Message}");
            }
#endif
        }

        internal void ExecuteSafetySweep()
        {
            try
            {
                lock (_stateLock)
                {
                    // 1. Heartbeat (liveness)
                    if (DateTime.UtcNow - _lastHeartbeatTime >= TimeSpan.FromSeconds(5))
                    {
                        _lastHeartbeatTime = DateTime.UtcNow;
                        try { File.WriteAllText(_heartbeatFile, DateTime.UtcNow.ToString("o")); } catch {}
                    }

                    // 2. Log flush (async queue drain)
                    var logsToWrite = new List<string>();
                    while (_logQueue.TryDequeue(out string logLine))
                        logsToWrite.Add(logLine);
                    if (logsToWrite.Count > 0)
                    {
                        try { File.AppendAllLines(_logFile, logsToWrite, Encoding.UTF8); } catch {}
                    }

                    // 3. Session reset (check date change - the one remaining time-based rule)
                    DateTime nowEt = TimeZoneInfo.ConvertTimeFromUtc(DateTime.UtcNow, _etZone);
                    DateTime currentSessionDate = nowEt.TimeOfDay >= new TimeSpan(18, 0, 0) ? nowEt.Date.AddDays(1) : nowEt.Date;

                    foreach (var accName in _subscribedAccounts)
                    {
                        if (_config.ExcludedAccounts != null && _config.ExcludedAccounts.Contains(accName)) continue;
                        if (!_accountStates.TryGetValue(accName, out var stateModel)) continue;
                        if (stateModel.LastSessionDate == currentSessionDate) continue;

                        var account = Account.All.FirstOrDefault(a => a.Name == accName);
                        if (account == null) continue;

                        stateModel.LastSessionDate = currentSessionDate;
                        stateModel.TradesToday = 0;
                        stateModel.ConsecutiveLosses = 0;
                        stateModel.PeakEquity = 0.0;
                        stateModel.PeakOpenGain = 0.0;
                        stateModel.PeakGivebackTriggered = false;
                        stateModel.PeakGivebackLastTriggerUnrealized = double.NaN;
                        stateModel.IsLockedOut = false;
                        stateModel.InitialLockoutFlattened = false;
                        stateModel.CurrentLockoutPhase = AccountState.LockoutPhase.None;
                        stateModel.SessionStartRealizedPnL = account.Get(AccountItem.RealizedProfitLoss, Currency.UsDollar);
                        stateModel.LastRealizedPnL = stateModel.SessionStartRealizedPnL;
                        stateModel.RealizedPnL = 0.0;
                        LogEvent(accName, "SESSION_RESET", $"Session reset for {currentSessionDate:yyyy-MM-dd}");
                        _stateDirty = true;
                    }

                    // FR-29: increment the shadow-session counter once per day when running in shadow mode.
                    // This is the soft gate that RunPreflight() checks before allowing live-mode arming.
                    if (_mode == "shadow" && _lastShadowSessionDate != currentSessionDate)
                    {
                        _lastShadowSessionDate = currentSessionDate;
                        _shadowSessionsCompleted++;
                        _stateDirty = true;
                        LogEvent("SYSTEM", "SHADOW_SESSION",
                            $"Shadow session #{_shadowSessionsCompleted} counted for {currentSessionDate:yyyy-MM-dd} (MinShadowSessions={_config.MinShadowSessions})");
                    }

                    // 4. State persist (batch flush)
                    if (_stateDirty)
                    {
                        SavePersistedState();
                        _stateDirty = false;
                    }

                    // 5. Lockout Watchdog (ensures locked accounts with open positions are continuously flattened until quantity is 0)
                    foreach (var accName in _subscribedAccounts)
                    {
                        if (_config.ExcludedAccounts != null && _config.ExcludedAccounts.Contains(accName)) continue;
                        if (!_accountStates.TryGetValue(accName, out var stateModel)) continue;
                        if (!stateModel.IsLockedOut) continue;

                        var account = Account.All.FirstOrDefault(a => a.Name == accName);
                        if (account == null) continue;

                        // Cancel working orders continuously for locked account
                        var toCancel = account.Orders.Where(o => o.OrderState != OrderState.Filled && o.OrderState != OrderState.Cancelled).ToList();
                        if (toCancel.Count > 0)
                        {
                            try { account.Cancel(toCancel); } catch {}
                        }

                        // Flatten open positions continuously until flat
                        foreach (Position pos in account.Positions)
                        {
                            if (pos.Instrument != null && pos.MarketPosition != MarketPosition.Flat)
                            {
                                try
                                {
                                    account.Flatten(new[] { pos.Instrument });
                                }
                                catch
                                {
                                    var closeAction = pos.MarketPosition == MarketPosition.Long ? OrderAction.Sell : OrderAction.BuyToCover;
                                    var closeOrder = account.CreateOrder(pos.Instrument, closeAction, OrderType.Market, TimeInForce.Day, pos.Quantity, 0, 0, string.Empty, "RiskGuardWatchdogFlatten", null);
                                    try { account.Submit(new[] { closeOrder }); } catch {}
                                }
                            }
                        }

                        var lockoutActions = EvaluateLockoutPhase(account, stateModel);
                        if (lockoutActions != null && lockoutActions.Count > 0)
                        {
                            foreach (var action in lockoutActions)
                            {
                                ProcessAction(action);
                            }
                        }
                    }

                    // 6. FSM watchdog (log-only diagnostic for stuck FSMs)
                    FsmWatchdog();
                }

                // All rule evaluation is now event-driven:
                // - PositionUpdate -> EvaluateRules + EvaluateLockoutPhase + UpdateFsmOnPosition
                // - OrderUpdate -> UpdateFsmOnOrder + EvaluateLockoutPhase
                // - ExecutionUpdate -> RecordExecution
                // - AccountItemUpdate -> EvaluatePnLRules + EvaluateFirmMirror
                // - Per-FSM one-shot Timer -> OnGraceExpired
            }
            catch (Exception ex)
            {
                LogEvent("SYSTEM", "ERROR", $"Error in ExecuteSafetySweep: {ex.Message}");
            }
        }

        // -
        // RULE ENGINE FRAMEWORK
        // -

        private AccountRiskProfile GetResolvedProfile(Account account)
        {
            if (account == null) return null;
            
            if (_config.Profiles != null)
            {
                foreach (var profile in _config.Profiles)
                {
                    if (!string.IsNullOrEmpty(profile.AccountNamePattern) && 
                        Regex.IsMatch(account.Name, profile.AccountNamePattern, RegexOptions.IgnoreCase))
                    {
                        return CreateDynamicProfile(account, profile);
                    }
                }
            }

            var fallback = new AccountRiskProfile
            {
                ProfileName = "GlobalFallback",
                DailyLossLimit = _config.PnLRules.DailyLossLimit,
                TrailingDrawdown = _config.PnLRules.TrailingDrawdown,
                MaxTradesPerSession = _config.Overtrading.MaxTradesPerSession,
                DefaultMaxContracts = _config.Sizing.MaxContractsPerAccount
            };
            return CreateDynamicProfile(account, fallback);
        }

        private AccountRiskProfile CreateDynamicProfile(Account account, AccountRiskProfile baseProfile)
        {
            var p = new AccountRiskProfile
            {
                ProfileName = baseProfile.ProfileName,
                AccountNamePattern = baseProfile.AccountNamePattern,
                InstrumentProfiles = baseProfile.InstrumentProfiles ?? new Dictionary<string, InstrumentProfile>(),
                MaxTradesPerSession = baseProfile.MaxTradesPerSession > 0 ? baseProfile.MaxTradesPerSession : _config.Overtrading.MaxTradesPerSession,
                DefaultMaxContracts = baseProfile.DefaultMaxContracts > 0 ? baseProfile.DefaultMaxContracts : _config.Sizing.MaxContractsPerAccount
            };

            double cashValue = account.Get(AccountItem.CashValue, Currency.UsDollar);

            p.DailyLossLimit = baseProfile.DailyLossLimit > 0.0 
                ? baseProfile.DailyLossLimit 
                : (cashValue > 0 ? cashValue * 0.025 : _config.PnLRules.DailyLossLimit);

            p.TrailingDrawdown = baseProfile.TrailingDrawdown > 0.0
                ? baseProfile.TrailingDrawdown
                : (cashValue > 0 ? cashValue * 0.05 : _config.PnLRules.TrailingDrawdown);
                
            return p;
        }

        // -
        // PER-POSITION GUARD FSM HELPERS (-6 of RiskGuardAddOn.md)
        // All methods assume _stateLock is held by the caller.
        // -
        private static string FsmKey(string accountName, string instrument) =>
            accountName + "|" + instrument;

        private static bool IsProtectiveSide(Order o, MarketPosition positionSide)
        {
            if (positionSide == MarketPosition.Long)
                return o.OrderAction == OrderAction.Sell || o.OrderAction == OrderAction.SellShort;
            if (positionSide == MarketPosition.Short)
                return o.OrderAction == OrderAction.Buy || o.OrderAction == OrderAction.BuyToCover;
            return false;
        }

        private static bool IsStopType(Order o) =>
            o.OrderType == OrderType.StopMarket || o.OrderType == OrderType.StopLimit;

        private static bool IsPendingOrWorking(OrderState s) =>
            s == OrderState.Submitted || s == OrderState.Accepted ||
            s == OrderState.Initialized  || s == OrderState.Working ||
            s == OrderState.PartFilled;

        private static bool IsTerminal(OrderState s) =>
            s == OrderState.Cancelled || s == OrderState.Rejected || s == OrderState.Filled;

        // Called from ExecutePositionUpdate. Handles flat<->nonflat transitions.
        private void UpdateFsmOnPosition(Account account, string instrument, MarketPosition newPos, int qty)
        {
            if (_config.ExcludedAccounts != null && _config.ExcludedAccounts.Contains(account.Name)) return;
            if (!_isArmed) return;

            string key = FsmKey(account.Name, instrument);
            bool isNonFlat = newPos != MarketPosition.Flat && qty > 0;

            if (isNonFlat)
            {
                lock (_stateLock)
                {
                    // Check if an FSM already exists for this (account, instrument).
                    if (_guardFsms.TryGetValue(key, out var existingFsm) && existingFsm.PositionSide == newPos)
                    {
                        // Same-side qty-only update (partial fill, scale-out/in):
                        // update qty in place, preserving Protected/ProtectedPending state
                        // and the recognized stop order. Do NOT recreate the FSM.
                        existingFsm.PositionQuantity = qty;

                        // Under-coverage detection: if we are protected but the stop
                        // does not cover the full position, arm the grace timer.
                        if ((existingFsm.State == GuardFsmState.Protected ||
                             existingFsm.State == GuardFsmState.ProtectedPending) &&
                            existingFsm.CoveredQuantity < existingFsm.PositionQuantity)
                        {
                            LogEvent(account.Name, "FSM_UNDERCOVERED",
                                $"{key}: covered {existingFsm.CoveredQuantity} < pos {existingFsm.PositionQuantity}");
                            existingFsm.GraceEmitted = false;
                            if (!existingFsm.GracePending)
                            {
                                ArmGraceTimer(existingFsm, account, instrument,
                                    _config.StopGuard.StopAttachSeconds * 1000);
                            }
                        }

                        LogEvent(account.Name, "FSM_UPDATE",
                            $"{key}: qty updated to {qty} (state stays {existingFsm.State})");
                        return;
                    }

                    // flat->nonflat or flip: dispose the outgoing FSM's timer before overwriting.
                    if (_guardFsms.TryGetValue(key, out var oldFsm))
                    {
                        oldFsm.GraceTimer?.Dispose();
                    }

                    // (re)create FSM, arm grace, consume pending stop
                    var fsm = new PositionGuardFsm(account.Name, instrument)
                    {
                        PositionSide = newPos,
                        PositionQuantity = qty,
                        EntryTime = DateTime.UtcNow,
                        State = GuardFsmState.Unprotected
                    };

                    // Consume a buffered stop that arrived before the position event
                    if (_pendingStops.TryGetValue(key, out var pending) && pending != null)
                    {
                        if (IsProtectiveSide(pending, newPos) && IsStopType(pending) && !IsTerminal(pending.OrderState))
                        {
                            fsm.RecognizedStopOrder = pending;
                            fsm.CoveredQuantity = pending.Quantity;
                            fsm.State = pending.OrderState == OrderState.Working
                                ? GuardFsmState.Protected
                                : GuardFsmState.ProtectedPending;
                        }
                        _pendingStops.Remove(key);
                    }

                    // Arm a one-shot grace timer that fires at the exact grace deadline.
                    // This replaces the sweep polling of GraceDeadline with an instant trigger.
                    if (fsm.State == GuardFsmState.Unprotected && _config.StopGuard.StopAttachSeconds > 0)
                    {
                        ArmGraceTimer(fsm, account, instrument, _config.StopGuard.StopAttachSeconds * 1000);
                    }

                    _guardFsms[key] = fsm;
                    LogEvent(account.Name, "FSM_TRANSITION",
                        $"Created FSM {key} -> {fsm.State} (grace deadline {fsm.GraceDeadline:HH:mm:ss})");
                }
            }
            else
            {
                // nonflat->flat: tear down, cancel grace timer, cancel orphan auto-stop.
                // NOTE (P1-30): this account.Cancel runs with _stateLock held - every caller of
                // UpdateFsmOnPosition already holds it (ExecutePositionUpdateDetails). Do NOT add a
                // nested lock(_stateLock) here and claim the cancel happens "outside the lock": the
                // nested lock is re-entrant and the outer lock is still held, so it buys nothing and
                // hides the violation. The real fix is to queue orphan cancellations and drain them
                // in ExecutePositionUpdateDetails after it releases the lock, which is tracked as
                // P1-30 in RISKGUARD_COPIER_HARDENING_PLAN.md and is out of scope for this ticket.
                if (_guardFsms.TryGetValue(key, out var fsm))
                {
                    fsm.GraceTimer?.Dispose();
                    if (fsm.AutoStopOrder != null && !IsTerminal(fsm.AutoStopOrder.OrderState))
                    {
                        try { account.Cancel(new[] { fsm.AutoStopOrder }); }
                        catch (Exception cex) { LogEvent(account.Name, "FSM_AUTOSTOP_CANCEL_FAIL", cex.Message); }
                    }
                    _guardFsms.Remove(key);
                    LogEvent(account.Name, "FSM_TRANSITION", $"Tore down FSM {key} -> Flat");
                }
                _pendingStops.Remove(key);
            }
        }

        // Arms a one-shot grace timer. MUST be called with _stateLock already held.
        private void ArmGraceTimer(PositionGuardFsm fsm, Account account, string instrument, int delayMs)
        {
            fsm.GraceTimer?.Dispose();
            fsm.GraceDeadline = DateTime.UtcNow.AddMilliseconds(delayMs);
            fsm.GracePending = true;
            long generation = ++fsm.GraceGeneration;
            var capturedAccount = account;
            var capturedInstrument = instrument;
            fsm.GraceTimer = new Timer(_ =>
            {
                OnGraceTimerCallback(capturedAccount, capturedInstrument, generation);
            }, null, delayMs, Timeout.Infinite);
        }

        // Timer callback that validates the generation before invoking OnGraceExpired.
        private void OnGraceTimerCallback(Account account, string instrument, long generation)
        {
            string key = FsmKey(account.Name, instrument);
            lock (_stateLock)
            {
                if (_guardFsms.TryGetValue(key, out var fsm) && fsm.GraceGeneration == generation)
                {
                    // Valid generation; proceed to evaluate grace expiry.
                    // OnGraceExpired will call EvaluateGraceExpiry which takes _stateLock again,
                    // but that's safe because the lock is reentrant.
                }
                else
                {
                    return; // Stale callback, ignore.
                }
            }
#if TESTING
            OnGraceExpired(account, instrument);
#else
            var dispatcher = Application.Current?.Dispatcher;
            if (dispatcher != null)
                dispatcher.InvokeAsync(() => OnGraceExpired(account, instrument));
            else
                OnGraceExpired(account, instrument);
#endif
        }

        // One-shot grace expiry callback - called by the per-FSM Timer or the sweep.
        internal void OnGraceExpired(Account account, string instrument)
        {
            var actions = EvaluateGraceExpiry(account, instrument);
            if (actions != null)
            {
                foreach (var action in actions)
                    ProcessAction(action);
            }
        }

        // Called from ExecuteOrderUpdate. Classifies the order against the active FSM.
        private void UpdateFsmOnOrder(Account account, string instrument, Order order)
        {
            if (_config.ExcludedAccounts != null && _config.ExcludedAccounts.Contains(account.Name)) return;
            if (!_isArmed) return;
            if (order?.Instrument == null) return;

            string key = FsmKey(account.Name, instrument);

            lock (_stateLock)
            {
                // If no FSM yet, buffer protective-side stops pending the position event.
                if (!_guardFsms.ContainsKey(key))
                {
                    if (IsStopType(order) && !IsTerminal(order.OrderState))
                    {
                        // We don't know the position side yet; buffer and classify on consumption.
                        _pendingStops[key] = order;
                    }
                    return;
                }

                var fsm = _guardFsms[key];
                var prev = fsm.State;

                // Recognise a protective stop for the current position side.
                if (IsProtectiveSide(order, fsm.PositionSide) && IsStopType(order))
                {
                    if (IsTerminal(order.OrderState))
                    {
                        // Only treat a terminal order as losing coverage when it is the
                        // currently recognised stop. Unrelated stops going terminal are ignored.
                        if (object.ReferenceEquals(order, fsm.RecognizedStopOrder))
                        {
                            if (fsm.PositionQuantity > 0)
                            {
                                fsm.State = GuardFsmState.Unprotected;
                                fsm.RecognizedStopOrder = null;
                                fsm.AutoStopOrder = null;
                                fsm.CoveredQuantity = 0;
                                fsm.GraceEmitted = false;
                                if (!fsm.GracePending)
                                {
                                    ArmGraceTimer(fsm, account, instrument,
                                        _config.StopGuard.StopAttachSeconds * 1000);
                                }
                                LogEvent(account.Name, "FSM_TRANSITION",
                                    $"{key}: stop {order.Name} terminal ({order.OrderState}) -> Unprotected");
                            }
                        }
                        else if (object.ReferenceEquals(order, fsm.AutoStopOrder))
                        {
                            // The auto-stop went terminal but it's not the recognised stop;
                            // just clear the auto-stop reference.
                            fsm.AutoStopOrder = null;
                        }
                    }
                    else // Non-terminal order update
                    {
                        // Determine if this order should replace the current recognised stop.
                        bool replace = fsm.RecognizedStopOrder == null
                                    || object.ReferenceEquals(order, fsm.RecognizedStopOrder)
                                    || IsTerminal(fsm.RecognizedStopOrder.OrderState)
                                    || order.Quantity >= fsm.CoveredQuantity;

                        if (replace)
                        {
                            fsm.RecognizedStopOrder = order;
                            fsm.CoveredQuantity = order.Quantity;
                            fsm.GraceEmitted = false;
                            if (order.OrderState == OrderState.Working)
                            {
                                fsm.State = GuardFsmState.Protected;
                                if (order.Name == "RiskGuardAutoStop") fsm.AutoStopOrder = order;
                                LogEvent(account.Name, "FSM_TRANSITION",
                                    $"{key}: stop {order.Name} Working -> Protected");
                            }
                            else // Submitted/Accepted/Initialized/PartFilled
                            {
                                fsm.State = GuardFsmState.ProtectedPending;
                                LogEvent(account.Name, "FSM_TRANSITION",
                                    $"{key}: stop {order.Name} {order.OrderState} -> ProtectedPending");
                            }

                            // If full coverage achieved, cancel any pending grace timer.
                            if (fsm.CoveredQuantity >= fsm.PositionQuantity)
                            {
                                fsm.GraceTimer?.Dispose();
                                fsm.GraceTimer = null;
                                fsm.GracePending = false;
                            }
                            else
                            {
                                // Under-covered: ensure a grace timer is armed for the delta.
                                if (!fsm.GracePending)
                                {
                                    ArmGraceTimer(fsm, account, instrument,
                                        _config.StopGuard.StopAttachSeconds * 1000);
                                }
                            }
                        }
                        else
                        {
                            // A smaller stop arrived while a larger one is already tracked; ignore.
                            LogEvent(account.Name, "FSM_IGNORE",
                                $"{key}: ignoring smaller stop {order.Name} qty {order.Quantity} " +
                                $"(current covered {fsm.CoveredQuantity})");
                        }
                    }
                }

                if (prev != fsm.State)
                {
                    fsm.LastTransitionTime = DateTime.UtcNow;
                    // Do NOT dispose the grace timer here; full-coverage disposal is handled
                    // in the recognition branches, and partial coverage must keep the timer alive.
                }
            }
        }

        // One-shot grace expiry. Called from a per-FSM Timer (or, defensively, from
        // the watchdog in the sweep if the timer was lost). Emits the StopGuard
        // action exactly once because the FSM transitions out of Unprotected.
        internal List<GuardAction> EvaluateGraceExpiry(Account account, string instrument)
        {
            var actions = new List<GuardAction>();
            lock (_stateLock)
            {
                if (_config.ExcludedAccounts != null && _config.ExcludedAccounts.Contains(account.Name)) return actions;
                if (!_isArmed) return actions;

                string key = FsmKey(account.Name, instrument);
                if (!_guardFsms.TryGetValue(key, out var fsm)) return actions;

                // The timer that woke us has fired; clear the pending flag.
                fsm.GracePending = false;

                // Anti-duplicate latch: if a grace action was already emitted and
                // its outcome is still pending, do not emit another.
                if (fsm.GraceEmitted) return actions;

                // Position must still be open and the deadline must have passed.
                if (DateTime.UtcNow < fsm.GraceDeadline) return actions;

                var pos = account.Positions.FirstOrDefault(p => p.Instrument.FullName == instrument);
                if (pos == null || pos.MarketPosition == MarketPosition.Flat) return actions;

                // Proceed when unprotected OR under-covered (stop quantity < position).
                bool isUnprotected = fsm.State == GuardFsmState.Unprotected;
                bool isUnderCovered = fsm.CoveredQuantity < pos.Quantity;
                if (!isUnprotected && !isUnderCovered) return actions;

                // Size the action to the uncovered delta only.
                int uncovered = pos.Quantity - Math.Max(0, fsm.CoveredQuantity);
                if (uncovered <= 0) return actions;

                if (_config.StopGuard.OnMissing == "AutoStop")
                {
                    actions.Add(new GuardAction
                    {
                        AccountName = account.Name,
                        ActionType = GuardActionType.PlaceStopOrder,
                        Instrument = instrument,
                        InstrumentObj = pos.Instrument,
                        Quantity = uncovered,
                        RuleId = "MISSING_STOP_ATTACH"
                    });
                    // For the Unprotected case, transition to a pending state so a
                    // duplicate call does not re-emit. For the under-covered case
                    // the FSM is already Protected/ProtectedPending; do not downgrade.
                    if (isUnprotected)
                    {
                        fsm.State = GuardFsmState.ProtectedPending;
                    }
                }
                else if (_config.StopGuard.OnMissing == "Flatten")
                {
                    actions.Add(new GuardAction
                    {
                        AccountName = account.Name,
                        ActionType = GuardActionType.FlattenPosition,
                        Instrument = instrument,
                        InstrumentObj = pos.Instrument,
                        Quantity = uncovered,
                        RuleId = "MISSING_STOP_FLATTEN"
                    });
                    if (isUnprotected)
                    {
                        fsm.State = GuardFsmState.FlattenPending;
                    }
                }

                // Mark that a grace action has been emitted for this episode.
                fsm.GraceEmitted = true;
            }
            return actions;
        }

        // Watchdog: log any FSM stuck in Unprotected past grace+buffer. Log only.
        private void FsmWatchdog()
        {
            foreach (var kv in _guardFsms)
            {
                var fsm = kv.Value;
                bool isNaked = fsm.State == GuardFsmState.Unprotected ||
                               fsm.CoveredQuantity < fsm.PositionQuantity;
                if (isNaked &&
                    DateTime.UtcNow > fsm.GraceDeadline.AddSeconds(2) &&
                    !fsm.GracePending &&
                    !fsm.GraceEmitted)
                {
                    // Keep the existing log line for the Unprotected case unchanged.
                    if (fsm.State == GuardFsmState.Unprotected)
                    {
                        LogEvent(fsm.AccountName, "FSM_WATCHDOG",
                            $"{fsm.Instrument}: Unprotected past grace deadline by " +
                            $"{(DateTime.UtcNow - fsm.GraceDeadline).TotalSeconds:F1}s");
                    }

                    Account account = Account.All.FirstOrDefault(a => a.Name == fsm.AccountName);
                    if (account != null)
                    {
                        // Arm a short grace timer; the sweep releases _stateLock
                        // before the callback needs it.
                        ArmGraceTimer(fsm, account, fsm.Instrument, 250);
                    }
                }
            }
        }

        // -- Lockout phase enforcement (event-driven) --
        // Called from ExecutePositionUpdate and ExecuteOrderUpdate. Returns
        // actions for the phased lockout: PendingCancel -> PendingFlatten -> Confirmed.
        // Only Confirmed stops emitting actions. This replaces the sweep-based
        // lockout loop with event-driven state transitions.
        internal List<GuardAction> EvaluateLockoutPhase(Account account, AccountState stateModel)
        {
            var actions = new List<GuardAction>();

            if (!stateModel.IsLockedOut && DateTime.UtcNow >= stateModel.LockoutUntil)
            {
                // Not locked out -> reset phase if it was left dirty
                if (stateModel.CurrentLockoutPhase != AccountState.LockoutPhase.None)
                {
                    stateModel.CurrentLockoutPhase = AccountState.LockoutPhase.None;
                    stateModel.InitialLockoutFlattened = false;
                }
                return actions;
            }

            // Check actual account state (not stale memory)
            bool hasWorkingOrders = false;
            bool hasOpenPosition = false;
            foreach (Order o in account.Orders)
            {
                if (o.OrderState == OrderState.Working || o.OrderState == OrderState.Submitted ||
                    o.OrderState == OrderState.Accepted || o.OrderState == OrderState.Initialized)
                {
                    hasWorkingOrders = true;
                    break;
                }
            }
            foreach (Position p in account.Positions)
            {
                if (p.MarketPosition != MarketPosition.Flat)
                {
                    hasOpenPosition = true;
                    break;
                }
            }

            // Confirmed: all clean
            if (!hasWorkingOrders && !hasOpenPosition)
            {
                if (stateModel.CurrentLockoutPhase != AccountState.LockoutPhase.Confirmed)
                {
                    stateModel.CurrentLockoutPhase = AccountState.LockoutPhase.Confirmed;
                    LogEvent(stateModel.AccountName, "LOCKOUT_CONFIRMED",
                        "Lockout confirmed: all orders cancelled, position flat.");
                }
                return actions;
            }

            // Phase: PendingCancel -> cancel all working orders
            if (stateModel.CurrentLockoutPhase == AccountState.LockoutPhase.None ||
                stateModel.CurrentLockoutPhase == AccountState.LockoutPhase.PendingCancel)
            {
                if (hasWorkingOrders)
                {
                    if (stateModel.CurrentLockoutPhase == AccountState.LockoutPhase.None)
                    {
                        stateModel.CurrentLockoutPhase = AccountState.LockoutPhase.PendingCancel;
                        LogEvent(stateModel.AccountName, "LOCKOUT_PHASE",
                            "Phase: PendingCancel - cancelling all working orders");
                    }
                    if (DateTime.UtcNow > stateModel.LastLockoutFlattenAttempt.AddSeconds(3))
                    {
                        actions.Add(new GuardAction
                        {
                            AccountName = stateModel.AccountName,
                            ActionType = GuardActionType.CancelAllOrders,
                            RuleId = "LOCKOUT_CANCEL"
                        });
                        stateModel.LastLockoutFlattenAttempt = DateTime.UtcNow;
                    }
                }
                else
                {
                    stateModel.CurrentLockoutPhase = AccountState.LockoutPhase.PendingFlatten;
                    stateModel.LastLockoutFlattenAttempt = DateTime.MinValue; // Allow immediate flatten action emit
                    LogEvent(stateModel.AccountName, "LOCKOUT_PHASE",
                        "Phase: PendingFlatten - orders cancelled, now flattening position");
                }
            }

            // Phase: PendingFlatten -> flatten the position
            if (stateModel.CurrentLockoutPhase == AccountState.LockoutPhase.PendingFlatten)
            {
                if (hasOpenPosition)
                {
                    if (DateTime.UtcNow > stateModel.LastLockoutFlattenAttempt.AddSeconds(5))
                    {
                        actions.Add(new GuardAction
                        {
                            AccountName = stateModel.AccountName,
                            ActionType = GuardActionType.FlattenPosition,
                            RuleId = "LOCKOUT_FLATTEN"
                        });
                        stateModel.LastLockoutFlattenAttempt = DateTime.UtcNow;
                        LogEvent(stateModel.AccountName, "LOCKOUT_FLATTEN_RETRY",
                            $"Flatten attempt for {stateModel.AccountName} (position still open)");
                    }
                }
                else
                {
                    if (!hasWorkingOrders)
                    {
                        stateModel.CurrentLockoutPhase = AccountState.LockoutPhase.Confirmed;
                        LogEvent(stateModel.AccountName, "LOCKOUT_CONFIRMED",
                            "Lockout confirmed: all orders cancelled, position flat.");
                    }
                }
            }

            // Stuck warning
            if (stateModel.CurrentLockoutPhase == AccountState.LockoutPhase.PendingFlatten &&
                DateTime.UtcNow > stateModel.LastLockoutFlattenAttempt.AddSeconds(30) &&
                hasOpenPosition)
            {
                LogEvent(stateModel.AccountName, "LOCKOUT_STUCK",
                    $"WARNING: Position still open after 30s of flatten attempts. " +
                    $"Manual intervention required. Account: {stateModel.AccountName}");
            }

            return actions;
        }

        // -- Aggregate sizing (event-driven via PositionUpdate) --
        // Scans all accounts' positions instantly on any position change.
        internal List<GuardAction> EvaluateAggregateSizing()
        {
            var actions = new List<GuardAction>();
            if (!_isArmed) return actions;

            int totalAggregateContracts = 0;
            int maxSingleAccountContracts = 0;
            foreach (var accName in _subscribedAccounts)
            {
                if (_config.ExcludedAccounts != null && _config.ExcludedAccounts.Contains(accName)) continue;
                if (!_accountStates.TryGetValue(accName, out var st)) continue;
                int accContracts = 0;
                foreach (var pos in st.Positions.Values)
                {
                    if (pos.MarketPosition != MarketPosition.Flat) accContracts += pos.Quantity;
                }
                totalAggregateContracts += accContracts;
                if (accContracts > maxSingleAccountContracts) maxSingleAccountContracts = accContracts;
            }

            int copies = _config.Sizing.ExpectedCopies > 0 ? _config.Sizing.ExpectedCopies : 1;
            int normalizedAggregate = copies > 1 ? maxSingleAccountContracts : totalAggregateContracts;

            if (normalizedAggregate > _config.Sizing.MaxContractsAggregate)
            {
                LogEvent("SYSTEM", "AGGREGATE_SIZE_BREACH", new JObject
                {
                    { "totalContracts", totalAggregateContracts },
                    { "maxSingleAccount", maxSingleAccountContracts },
                    { "expectedCopies", copies },
                    { "normalizedAggregate", normalizedAggregate },
                    { "limit", _config.Sizing.MaxContractsAggregate }
                });

                foreach (var accName in _subscribedAccounts)
                {
                    if (_config.ExcludedAccounts != null && _config.ExcludedAccounts.Contains(accName)) continue;
                    if (!_accountStates.TryGetValue(accName, out var st)) continue;
                    bool hasPosition = st.Positions.Values.Any(p => p.MarketPosition != MarketPosition.Flat);
                    if (hasPosition)
                    {
                        // Throttle aggregate flatten using LastLockoutFlattenAttempt
                        if (DateTime.UtcNow > st.LastLockoutFlattenAttempt.AddSeconds(5))
                        {
                            actions.Add(new GuardAction
                            {
                                AccountName = accName,
                                ActionType = GuardActionType.FlattenPosition,
                                RuleId = "AGGREGATE_SIZE_BREACH"
                            });
                            st.LastLockoutFlattenAttempt = DateTime.UtcNow;
                        }
                    }
                }
            }

            return actions;
        }

        internal List<GuardAction> EvaluateRules(Account account, AccountState stateModel)
        {
            if (!_isArmed || (_config.ExcludedAccounts != null && _config.ExcludedAccounts.Contains(stateModel.AccountName)))
            {
                return new List<GuardAction>();
            }
            var actions = new List<GuardAction>();

            var profile = GetResolvedProfile(account);
            if (profile == null) return actions;

            // Rule 1: Max Size
            foreach (var posPair in stateModel.Positions)
            {
                var pos = posPair.Value;
                if (pos.MarketPosition != MarketPosition.Flat)
                {
                    int limit = profile.DefaultMaxContracts;
                    string baseSymbol = pos.InstrumentObj?.MasterInstrument?.Name ?? pos.Instrument.Split(' ')[0];
                    
                    if (profile.InstrumentProfiles.TryGetValue(baseSymbol, out var instrProfile))
                    {
                        limit = instrProfile.MaxContracts;
                    }
                    else if (profile.InstrumentProfiles.TryGetValue(pos.Instrument, out var exactProfile))
                    {
                        limit = exactProfile.MaxContracts;
                    }

                    if (pos.Quantity > limit)
                    {
                        stateModel.IsLockedOut = true;
                        actions.Add(new GuardAction
                        {
                            AccountName = stateModel.AccountName,
                            ActionType = GuardActionType.FlattenPosition,
                            Instrument = pos.Instrument,
                            InstrumentObj = pos.InstrumentObj,
                            Quantity = pos.Quantity,
                            RuleId = "MAX_SIZE_BREACH"
                        });
                        stateModel.LastLockoutFlattenAttempt = DateTime.UtcNow;
                    }
                }
            }

            // Fix 8: Overtrading Rules
            if (stateModel.TradesToday > profile.MaxTradesPerSession)
            {
                actions.Add(new GuardAction
                {
                    AccountName = stateModel.AccountName,
                    ActionType = GuardActionType.FlattenPosition,
                    RuleId = "MAX_TRADES_BREACH"
                });
                if (!stateModel.IsLockedOut)
                {
                    stateModel.IsLockedOut = true;
                    if (_config.Overtrading.LockoutMinutes > 0)
                    {
                        stateModel.LockoutUntil = DateTime.UtcNow.AddMinutes(_config.Overtrading.LockoutMinutes);
                    }
                    _stateDirty = true;
                }
            }

            if (stateModel.ConsecutiveLosses >= _config.Overtrading.MaxConsecutiveLosses)
            {
                actions.Add(new GuardAction
                {
                    AccountName = stateModel.AccountName,
                    ActionType = GuardActionType.FlattenPosition,
                    RuleId = "CONSECUTIVE_LOSS_BREACH"
                });
                if (!stateModel.IsLockedOut)
                {
                    stateModel.IsLockedOut = true;
                    if (_config.Overtrading.LockoutMinutes > 0)
                    {
                        stateModel.LockoutUntil = DateTime.UtcNow.AddMinutes(_config.Overtrading.LockoutMinutes);
                    }
                    _stateDirty = true;
                }
            }

            if (DateTime.UtcNow < stateModel.CooldownUntil)
            {
                bool hasOpen = stateModel.Positions.Values.Any(p => p.MarketPosition != MarketPosition.Flat);
                if (hasOpen)
                {
                    actions.Add(new GuardAction
                    {
                        AccountName = stateModel.AccountName,
                        ActionType = GuardActionType.FlattenPosition,
                        RuleId = "COOLDOWN_BREACH"
                    });
                }
            }

            // PnL rules (Daily Loss, Trailing Drawdown) have been migrated to
            // EvaluatePnLRules (called from AccountItemUpdate). They are no longer
            // evaluated here to avoid duplicate-fire when both PositionUpdate and
            // AccountItemUpdate fire for the same logical state change.
            // PeakEquity is still tracked here as a fallback in case AccountItemUpdate
            // hasn't fired yet (e.g. position just opened and PnL hasn't changed).
            double currentPnL = stateModel.RealizedPnL + stateModel.UnrealizedPnL;
            if (currentPnL > stateModel.PeakEquity)
            {
                stateModel.PeakEquity = currentPnL;
            }

            // Rule 4: Edge Window Gate (if enabled)
            if (_config.EnableWindowGate)
            {
                foreach (var posPair in stateModel.Positions)
                {
                    var pos = posPair.Value;
                    if (pos.MarketPosition != MarketPosition.Flat && pos.LastNonFlatTransition != DateTime.MinValue)
                    {
                        DateTime timeEt = TimeZoneInfo.ConvertTimeFromUtc(pos.LastNonFlatTransition, _etZone);
                        if (!IsInsidePermittedWindows(timeEt))
                        {
                            actions.Add(new GuardAction
                            {
                                AccountName = stateModel.AccountName,
                                ActionType = GuardActionType.FlattenPosition,
                                Instrument = pos.Instrument,
                                InstrumentObj = pos.InstrumentObj,
                                RuleId = "EDGE_WINDOW_BREACH"
                            });
                        }
                    }
                }
            }

            // Rule 5: Stop-Loss Guard has been migrated to the per-position FSM
            // (see -6 of RiskGuardAddOn.md). The FSM owns the grace timer and
            // emits MISSING_STOP_* via EvaluateGraceExpiry(); EvaluateRules no
            // longer snapshots account.Orders for this rule, which was the
            // source of the duplicate-SL race on OCO brackets.

            return actions;
        }

        private bool IsInsidePermittedWindows(DateTime timeEt)
        {
            if (_parsedWindows.Count == 0) return true;

            DayOfWeek dayOfWeek = timeEt.DayOfWeek;
            TimeSpan currentTime = timeEt.TimeOfDay;

            foreach (var win in _parsedWindows)
            {
                if (win.Days.Contains(dayOfWeek))
                {
                    if (currentTime >= win.Start && currentTime <= win.End)
                    {
                        return true;
                    }
                }
            }
            return false;
        }

        // -
        // ACTION ARBITER & EXECUTOR
        // -

        public string GetMode()
        {
            return _mode;
        }

        public bool IsArmed
        {
            get { return _isArmed; }
        }

        // FR-31: Arming ritual preflight. Returns true only when all checks pass:
        //   (a) config loaded and valid, (b) at least one non-excluded account connected,
        //   (c) guard mode is a recognised enforcement mode or shadow.
        // Any failure blocks arming and reports which check failed (logged).
        public PreflightResult RunPreflight()
        {
            var result = new PreflightResult();
            // (a) config loaded?
            if (_config == null)
            {
                result.Fail("CONFIG", "RiskConfig not loaded");
                return result;
            }
            // (b) at least one connected, non-excluded account?
            int connected = 0;
            foreach (Account a in Account.All)
            {
                if (a == null) continue;
                if (_config.ExcludedAccounts != null && _config.ExcludedAccounts.Contains(a.Name)) continue;
                connected++;
            }
            if (connected == 0)
                result.Fail("ACCOUNTS", "No connected non-excluded accounts found");
            // (c) mode recognised?
            if (_mode != "shadow" && _mode != "live" && _mode != "pure" && _mode != "override_with_friction")
                result.Fail("MODE", $"Unrecognised mode '{_mode}'");
            // (d) FR-29 soft gate: live enforcement modes require MinShadowSessions completed shadow sessions.
            if ((_mode == "live" || _mode == "pure" || _mode == "override_with_friction")
                && _config.MinShadowSessions > 0
                && _shadowSessionsCompleted < _config.MinShadowSessions)
            {
                result.Fail("SHADOW_SESSIONS",
                    $"Only {_shadowSessionsCompleted} shadow session(s) completed; MinShadowSessions={_config.MinShadowSessions} required before live arming.");
            }
            // (e) FR-36: override friction minimums enforced.
            if (_mode == "override_with_friction" && _config.Override != null && _config.Override.WaitSeconds < 30)
                result.Fail("OVERRIDE_FRICTION", "Override.WaitSeconds below FR-36 enforced minimum of 30s.");
            // (f) FirmMirror validation (P2-8): if enabled, every mapped account's firm must exist in FirmProfiles,
            // and each referenced firm profile must have non-zero amounts when its sub-rule is enabled.
            if (_config.FirmMirror != null && _config.FirmMirror.Enabled)
            {
                var fm = _config.FirmMirror;
                if (fm.AccountFirmMap != null)
                {
                    foreach (var kvp in fm.AccountFirmMap)
                    {
                        if (!string.IsNullOrEmpty(kvp.Value) && (fm.FirmProfiles == null || !fm.FirmProfiles.ContainsKey(kvp.Value)))
                        {
                            result.Fail("FIRM_MIRROR", $"Account '{kvp.Key}' mapped to unknown firm '{kvp.Value}'. Add it to FirmProfiles or clear the mapping.");
                            break;
                        }
                    }
                }
                if (result.Passed && fm.FirmProfiles != null)
                {
                    foreach (var fp in fm.FirmProfiles)
                    {
                        if (fp.Value.TrailingDD != null && fp.Value.TrailingDD.Enabled && fp.Value.TrailingDD.Amount <= 0)
                        {
                            result.Fail("FIRM_MIRROR", $"Firm '{fp.Key}' has TrailingDD enabled but Amount <= 0. Populate real firm limits before arming.");
                            break;
                        }
                        if (fp.Value.DailyLoss != null && fp.Value.DailyLoss.Enabled && fp.Value.DailyLoss.Amount <= 0)
                        {
                            result.Fail("FIRM_MIRROR", $"Firm '{fp.Key}' has DailyLoss enabled but Amount <= 0. Populate real firm limits before arming.");
                            break;
                        }
                    }
                }
            }
            if (result.Passed)
                LogEvent("SYSTEM", "PREFLIGHT", "Preflight passed; arming permitted.");
            else
                LogEvent("SYSTEM", "PREFLIGHT_FAIL", $"Preflight failed: {result.FailureCode} - {result.FailureMessage}");
            return result;
        }

        public class PreflightResult
        {
            public bool Passed = true;
            public string FailureCode = "";
            public string FailureMessage = "";
            public void Fail(string code, string msg) { Passed = false; FailureCode = code; FailureMessage = msg; }
        }

        // FR-30/31: arming now requires a successful preflight. ToggleArmed() will refuse to
        // transition from disarmed -> armed unless RunPreflight() passes. Disarming is always allowed.
        public void ToggleArmed()
        {
            lock (_stateLock)
            {
                if (!_isArmed)
                {
                    // disarmed -> armed: gate on preflight
                    var pf = RunPreflight();
                    if (!pf.Passed)
                    {
                        LogEvent("SYSTEM", "ARM_BLOCKED", $"Arming refused: preflight failed ({pf.FailureCode}).");
                        return;
                    }
                }
                _isArmed = !_isArmed;
                LogEvent("SYSTEM", "TOGGLE_ARMED", $"System Armed State changed to: {_isArmed}");
                SavePersistedState();
            }
        }

        public string TriggerManualFlatten(string accountName)
        {
            var action = new GuardAction
            {
                AccountName = accountName,
                ActionType = GuardActionType.FlattenPosition,
                RuleId = "MANUAL_PANIC"
            };
            return ProcessAction(action, forceLive: true);
        }

        public string TriggerManualFlattenAll()
        {
            var results = new List<string>();
            foreach (var account in Account.All)
            {
                var action = new GuardAction
                {
                    AccountName = account.Name,
                    ActionType = GuardActionType.FlattenPosition,
                    RuleId = "MANUAL_PANIC_ALL"
                };
                results.Add($"{account.Name}: {ProcessAction(action, forceLive: true)}");
            }
            return string.Join("; ", results);
        }

        // FR-35/36: friction-gated lockout override. In "override_with_friction" mode, escaping a
        // lockout requires the exact confirm phrase AND a forced wait (enforced min 30s).
        // Returns true if the override succeeded and the account was unlocked.
        // In "pure" mode this always returns false (no in-session override allowed).
        // In "shadow" mode the friction is still enforced for practice, but no real lockout existed.
        public bool OverrideLockout(string accountName, string confirmPhrase, out string reason)
        {
            reason = "";
            if (_mode == "pure")
            {
                reason = "Override not permitted in 'pure' enforcement mode; lockouts clear only at session reset.";
                LogEvent(accountName, "OVERRIDE_REJECTED", reason);
                return false;
            }
            if (_mode != "override_with_friction" && _mode != "shadow")
            {
                reason = $"Override not implemented for mode '{_mode}'.";
                return false;
            }
            // FR-36: clamp wait to enforced minimum.
            int waitSec = _config.Override?.WaitSeconds ?? 120;
            if (waitSec < 30) waitSec = 30;
            string expected = _config.Override?.ConfirmPhrase ?? "I understand locked means locked";
            if (!string.Equals(confirmPhrase, expected, StringComparison.Ordinal))
            {
                reason = "Confirm phrase does not match. Override refused.";
                LogEvent(accountName, "OVERRIDE_REJECTED", "Incorrect confirm phrase.");
                return false;
            }
            // The forced wait is enforced by the caller (UI/CLI) — this method performs the unlock
            // only after the wait has elapsed. We log the intent and the wait duration.
            LogEvent(accountName, "OVERRIDE_ACCEPTED",
                $"Confirm phrase accepted; applying override after {waitSec}s friction wait. Account will be unlocked.");
            UnlockAccount(accountName);
            reason = $"Override applied after {waitSec}s wait.";
            return true;
        }

        public void UnlockAccount(string accountName)
        {
            lock (_stateLock)
            {
                if (_accountStates.TryGetValue(accountName, out var state))
                {
                    var account = Account.All.FirstOrDefault(a => a.Name == accountName);
                    double currentRealized = account != null ? account.Get(AccountItem.RealizedProfitLoss, Currency.UsDollar) : 0.0;

                    state.IsLockedOut = false;
                    state.LockoutUntil = DateTime.MinValue;
                    state.PeakEquity = 0.0;
                    state.PeakOpenGain = 0.0;
                    state.PeakGivebackTriggered = false;
                    state.PeakGivebackLastTriggerUnrealized = double.NaN;
                    state.TradesToday = 0;
                    state.ConsecutiveLosses = 0;
                    state.CooldownUntil = DateTime.MinValue;
                    state.SessionStartRealizedPnL = currentRealized;
                    state.LastRealizedPnL = currentRealized;
                    state.RealizedPnL = 0.0;
                    state.UnrealizedPnL = 0.0;
                    state.InitialLockoutFlattened = false;
                    state.CurrentLockoutPhase = AccountState.LockoutPhase.None;

                    // Sync positions to avoid stale memory
                    state.Positions.Clear();
                    if (account != null)
                    {
                        foreach (Position p in account.Positions)
                        {
                            if (p.MarketPosition != MarketPosition.Flat)
                            {
                                double unrealized = 0.0;
                                try { unrealized = p.GetUnrealizedProfitLoss(PerformanceUnit.Currency); } catch { }
                                state.UpdatePosition(account, p.Instrument, p.MarketPosition, p.Quantity, p.AveragePrice, unrealized, _config);
                            }
                        }
                    }

                    LogEvent(accountName, "UNLOCK", "Account manually unlocked from dashboard. Metrics reset and synchronized.");
                    SavePersistedState();
                }
            }
        }

        public void LockAccount(string accountName, int minutes)
        {
            lock (_stateLock)
            {
                if (_accountStates.TryGetValue(accountName, out var state))
                {
                    if (minutes == -1)
                    {
                        state.IsLockedOut = true;
                        state.LockoutUntil = DateTime.MinValue;
                    }
                    else if (minutes > 0)
                    {
                        state.LockoutUntil = DateTime.UtcNow.AddMinutes(minutes);
                        state.InitialLockoutFlattened = false; // force flatten sweep
                    }
                    _stateDirty = true;
                    LogEvent(accountName, "MANUAL_LOCKOUT", "Account locked from dashboard for " + (minutes == -1 ? "EOD" : minutes + " minutes"));
                }
            }
        }

        internal string ProcessAction(GuardAction action, bool forceLive = false)
        {
            bool isLive = false;
            lock (_stateLock)
            {
                // 1. ActionArbiter - Check Invariant (Risk-Reducing Only)
                if (!ValidateInvariant(action))
                {
                    LogEvent(action.AccountName, "ARBITER_REJECTED", $"Arbiter rejected action {action.ActionType} - would increase risk or target is invalid.");
                    return "REJECTED (INVARIANT VIOLATION)";
                }

                // 2. Mode Check (Shadow Mode Gate)
                isLive = _mode == "live" || forceLive;
                if (!isLive)
                {
                    LogEvent(action.AccountName, "SHADOW_ACTION", $"[SHADOW] Would execute action {action.ActionType} triggered by {action.RuleId}");
                    return "SHADOW (SKIPPED)";
                }
            }

            // 3. Executor - Run the action (released lock to prevent deadlock with event dispatch thread)
            try
            {
                ExecuteAction(action);
                LogEvent(action.AccountName, "INTERVENTION", $"Executed action {action.ActionType} triggered by {action.RuleId}");
                return "EXECUTED";
            }
            catch (Exception ex)
            {
                LogEvent(action.AccountName, "EXECUTION_ERROR", $"Failed to execute {action.ActionType}: {ex.Message}");
                return $"ERROR: {ex.Message}";
            }
        }

        // Precondition: caller must hold _stateLock.
        private bool ValidateInvariant(GuardAction action)
        {
            var account = Account.All.FirstOrDefault(a => a.Name == action.AccountName);
            if (account == null) return false;

            if (action.ActionType == GuardActionType.FlattenPosition)
            {
                return true; 
            }

            if (action.ActionType == GuardActionType.CancelAllOrders)
            {
                return true;
            }

            if (action.ActionType == GuardActionType.CancelOrder)
            {
                return !string.IsNullOrEmpty(action.OrderId);
            }

            if (action.ActionType == GuardActionType.PlaceStopOrder)
            {
                // A stop order is risk-reducing only when it closes an existing,
                // same-side live position. The actual stop quantity is sized from
                // the live position in ExecuteAction, so the arbiter only verifies
                // that a coverable position exists and the action side matches it.
                // Do not mutate state or call trading methods.
                if (action.InstrumentObj == null || action.Quantity <= 0)
                    return false;

                var position = account.Positions.FirstOrDefault(p => p.Instrument != null && p.Instrument.FullName == action.Instrument);
                if (position == null || position.MarketPosition == MarketPosition.Flat)
                    return false;

                string key = FsmKey(action.AccountName, action.Instrument);
                if (!_guardFsms.TryGetValue(key, out var fsm))
                    return false;
                if (fsm.PositionSide != position.MarketPosition)
                    return false;
                if (fsm.State == GuardFsmState.Protected || fsm.State == GuardFsmState.ProtectedPending)
                    return false;

                int liveQuantity = (int)position.Quantity;
                if (liveQuantity <= 0)
                    return false;

                return true;
            }

            return false;
        }

        private void ExecuteAction(GuardAction action)
        {
            var account = Account.All.FirstOrDefault(a => a.Name == action.AccountName);
            if (account == null) throw new Exception("Account not found");

            if (action.ActionType == GuardActionType.FlattenPosition)
            {
                var instrumentsToFlatten = new List<Instrument>();
                foreach (Position p in account.Positions)
                {
                    if (p.MarketPosition != MarketPosition.Flat && p.Instrument != null)
                    {
                        instrumentsToFlatten.Add(p.Instrument);
                    }
                }
                foreach (Order o in account.Orders)
                {
                    if ((o.OrderState == OrderState.Working || o.OrderState == OrderState.Submitted || o.OrderState == OrderState.Accepted) && o.Instrument != null)
                    {
                        if (!instrumentsToFlatten.Contains(o.Instrument))
                        {
                            instrumentsToFlatten.Add(o.Instrument);
                        }
                    }
                }

                if (instrumentsToFlatten.Count > 0)
                {
                    try
                    {
                        account.Flatten(instrumentsToFlatten.ToArray());
                    }
                    catch (Exception fex)
                    {
                        LogEvent(action.AccountName, "FLATTEN_ERROR",
                            $"Flatten failed for {string.Join(",", instrumentsToFlatten.Select(i => i.FullName))}: {fex.Message}");
                        throw;
                    }
                }
            }
            else if (action.ActionType == GuardActionType.CancelAllOrders)
            {
                var orders = new List<Order>();
                foreach (Order o in account.Orders)
                {
                    if (o.OrderState == OrderState.Working || o.OrderState == OrderState.Submitted || o.OrderState == OrderState.Accepted)
                    {
                        orders.Add(o);
                    }
                }
                if (orders.Count > 0)
                {
                    account.Cancel(orders);
                }
            }
            else if (action.ActionType == GuardActionType.CancelOrder)
            {
                var order = account.Orders.FirstOrDefault(o => o.Id.ToString() == action.OrderId);
                if (order != null)
                {
                    account.Cancel(new[] { order });
                }
            }
            else if (action.ActionType == GuardActionType.PlaceStopOrder)
            {
                var instrument = action.InstrumentObj;
                if (instrument == null)
                {
                    LogEvent(account.Name, "AUTO_STOP_ABORT_NO_INSTRUMENT", "PlaceStopOrder missing InstrumentObj; aborting.");
                    return;
                }

                string key = FsmKey(account.Name, action.Instrument);

                bool IsFsmProtectedOrPending()
                {
                    lock (_stateLock)
                    {
                        return _guardFsms.TryGetValue(key, out PositionGuardFsm localFsm)
                            && (localFsm.State == GuardFsmState.Protected || localFsm.State == GuardFsmState.ProtectedPending);
                    }
                }

                void ReArmGraceIfUnprotected()
                {
                    lock (_stateLock)
                    {
                        if (_guardFsms.TryGetValue(key, out PositionGuardFsm localFsm) && localFsm.State == GuardFsmState.Unprotected)
                        {
                            localFsm.GraceEmitted = false;
                            int delayMs = _config.StopGuard.StopAttachSeconds * 1000;
                            // ArmGraceTimer only schedules a timer callback; it does not invoke account trading methods.
                            ArmGraceTimer(localFsm, account, action.Instrument, delayMs);
                        }
                    }
                }

                void RollbackFsm(string reason)
                {
                    bool wasProtected = false;
                    lock (_stateLock)
                    {
                        if (_guardFsms.TryGetValue(key, out PositionGuardFsm localFsm))
                        {
                            if (localFsm.State == GuardFsmState.Protected)
                            {
                                wasProtected = true;
                                localFsm.GraceEmitted = false;
                            }
                            else
                            {
                                localFsm.AutoStopOrder = null;
                                localFsm.RecognizedStopOrder = null;
                                localFsm.CoveredQuantity = 0;
                                localFsm.GraceEmitted = false;
                                if (localFsm.State != GuardFsmState.Flat)
                                    localFsm.State = GuardFsmState.Unprotected;

                                int delayMs = _config.StopGuard.StopAttachSeconds * 1000;
                                // ArmGraceTimer only schedules a timer callback; it does not invoke account trading methods.
                                ArmGraceTimer(localFsm, account, action.Instrument, delayMs);
                            }
                        }
                    }
                    if (wasProtected)
                        LogEvent(account.Name, "AUTO_STOP_ROLLBACK_PROTECTED", $"Protected FSM left intact for {action.Instrument}: {reason}");
                    else
                        LogEvent(account.Name, "AUTO_STOP_ROLLBACK", $"FSM rolled back for {action.Instrument}: {reason}");
                }

                void ClearTrackingAndSetUnprotected()
                {
                    lock (_stateLock)
                    {
                        if (_guardFsms.TryGetValue(key, out PositionGuardFsm localFsm))
                        {
                            localFsm.AutoStopOrder = null;
                            localFsm.RecognizedStopOrder = null;
                            localFsm.CoveredQuantity = 0;
                            localFsm.GraceEmitted = false;
                            if (localFsm.State != GuardFsmState.Flat)
                                localFsm.State = GuardFsmState.Unprotected;
                        }
                    }
                }

                void AfterFlattenCleanup(string context)
                {
                    var posNow = account.Positions.FirstOrDefault(p => p.Instrument != null && p.Instrument.FullName == action.Instrument);
                    bool positionExists = posNow != null && posNow.MarketPosition != MarketPosition.Flat;

                    lock (_stateLock)
                    {
                        if (!_guardFsms.TryGetValue(key, out PositionGuardFsm localFsm))
                        {
                            if (positionExists)
                            {
                                localFsm = new PositionGuardFsm(account.Name, action.Instrument);
                                localFsm.PositionSide = posNow.MarketPosition;
                                localFsm.PositionQuantity = (int)posNow.Quantity;
                                localFsm.EntryTime = DateTime.UtcNow;
                                localFsm.LastTransitionTime = DateTime.UtcNow;
                                localFsm.State = GuardFsmState.Unprotected;
                                localFsm.GraceEmitted = false;
                                localFsm.AutoStopAttempts = 0;
                                _guardFsms[key] = localFsm;
                            }
                        }

                        if (localFsm != null)
                        {
                            localFsm.AutoStopOrder = null;
                            localFsm.RecognizedStopOrder = null;
                            localFsm.CoveredQuantity = 0;
                            localFsm.GraceEmitted = false;
                            localFsm.AutoStopAttempts = 0;
                            if (localFsm.State != GuardFsmState.Flat)
                                localFsm.State = GuardFsmState.Unprotected;

                            if (positionExists && localFsm.State == GuardFsmState.Unprotected)
                            {
                                int delayMs = _config.StopGuard.StopAttachSeconds * 1000;
                                // ArmGraceTimer only schedules a timer callback; it does not invoke account trading methods.
                                ArmGraceTimer(localFsm, account, action.Instrument, delayMs);
                            }
                        }
                    }

                    LogEvent(account.Name, "AUTO_STOP_FLATTEN_CLEANUP", $"Post-flatten cleanup completed for {action.Instrument} ({context}).");
                }

                void FlattenAndClear(string reason)
                {
                    LogEvent(account.Name, "STOP_SIDE_FLATTEN", reason);
                    try
                    {
                        account.Flatten(new[] { instrument });
                    }
                    catch (Exception fex)
                    {
                        RollbackFsm($"Flatten failed: {fex.Message}");
                        LogEvent(account.Name, "FLATTEN_ERROR", $"Flatten failed for {instrument.FullName}: {fex.Message}");
                        throw;
                    }
                    AfterFlattenCleanup("stop-side-flatten");
                }

                var position = account.Positions.FirstOrDefault(p => p.Instrument != null && p.Instrument.FullName == action.Instrument);
                if (position == null || position.MarketPosition == MarketPosition.Flat)
                {
                    ReArmGraceIfUnprotected();
                    LogEvent(account.Name, "AUTO_STOP_ABORT_NO_POSITION", $"No live position for {action.Instrument}; aborting auto-stop.");
                    return;
                }

                MarketPosition initialSide = position.MarketPosition;

                bool sideMismatch = false;
                lock (_stateLock)
                {
                    if (!_guardFsms.TryGetValue(key, out PositionGuardFsm localFsm) || localFsm.PositionSide != initialSide)
                        sideMismatch = true;
                }
                if (sideMismatch)
                {
                    ReArmGraceIfUnprotected();
                    LogEvent(account.Name, "AUTO_STOP_ABORT_SIDE_MISMATCH",
                        $"Live position side {initialSide} does not match FSM side for {action.Instrument}; aborting auto-stop.");
                    return;
                }

                int maxAttempts = _config.StopGuard.MaxAutoStopAttempts;
                if (maxAttempts <= 0) maxAttempts = 2;

                bool shouldEscalate = false;
                lock (_stateLock)
                {
                    if (_guardFsms.TryGetValue(key, out PositionGuardFsm localFsm))
                    {
                        if (localFsm.AutoStopAttempts + 1 > maxAttempts)
                            shouldEscalate = true;
                    }
                    else
                    {
                        LogEvent(account.Name, "AUTO_STOP_ABORT_FSM_LOST", $"FSM missing for {action.Instrument} during escalation check; aborting.");
                        return;
                    }
                }

                if (shouldEscalate)
                {
                    bool stillEscalate = false;
                    lock (_stateLock)
                    {
                        if (_guardFsms.TryGetValue(key, out PositionGuardFsm localFsm))
                            stillEscalate = localFsm.State == GuardFsmState.Unprotected;
                    }

                    if (!stillEscalate)
                    {
                        LogEvent(account.Name, "AUTO_STOP_ESCALATE_SKIPPED", $"Escalation skipped for {instrument.FullName}; FSM is not unprotected.");
                        return;
                    }

                    ClearTrackingAndSetUnprotected();
                    LogEvent(account.Name, "AUTO_STOP_ESCALATE",
                        $"Auto-stop escalation for {instrument.FullName}: attempts exceeded ceiling {maxAttempts}; flattening position.");

                    try
                    {
                        account.Flatten(new[] { instrument });
                    }
                    catch (Exception fex)
                    {
                        RollbackFsm($"Escalation flatten failed: {fex.Message}");
                        LogEvent(account.Name, "AUTO_STOP_ESCALATE_FAILED", $"Escalation flatten failed for {instrument.FullName}: {fex.Message}");
                        throw;
                    }

                    AfterFlattenCleanup("escalation");
                    return;
                }

                // Re-read the live position before computing the stop price and side.
                position = account.Positions.FirstOrDefault(p => p.Instrument != null && p.Instrument.FullName == action.Instrument);
                if (position == null || position.MarketPosition == MarketPosition.Flat || position.MarketPosition != initialSide)
                {
                    ReArmGraceIfUnprotected();
                    LogEvent(account.Name, "AUTO_STOP_ABORT_NO_POSITION", $"Position changed before stop pricing for {action.Instrument}; aborting auto-stop.");
                    return;
                }

                string symbolName = instrument.MasterInstrument.Name;
                int offsetTicks = 30; // default
                if (_config.StopGuard.Offsets.TryGetValue(symbolName, out int ticks))
                {
                    offsetTicks = ticks;
                }
                else if (_config.StopGuard.Offsets.TryGetValue("default", out int defTicks))
                {
                    offsetTicks = defTicks;
                }

                double tickSize = instrument.MasterInstrument.TickSize;
                double stopPrice = 0.0;
                OrderAction orderAction = OrderAction.Buy;

                // Fix B: Read real last price from market data
                double currentPrice = 0.0;
                if (instrument.MarketData != null && instrument.MarketData.Last != null)
                {
                    currentPrice = instrument.MarketData.Last.Price;
                }

                if (currentPrice <= 0.0)
                {
                    if (IsFsmProtectedOrPending())
                    {
                        LogEvent(account.Name, "AUTO_STOP_ESCALATE_SKIPPED", $"Stop-side flatten skipped for {instrument.FullName}; FSM already protected/pending.");
                        return;
                    }
                    FlattenAndClear($"Market price unavailable for {instrument.FullName}. Flattening.");
                    return;
                }

                if (position.MarketPosition == MarketPosition.Long)
                {
                    stopPrice = position.AveragePrice - (offsetTicks * tickSize);
                    orderAction = OrderAction.Sell;
                    
                    if (stopPrice >= currentPrice)
                    {
                        if (IsFsmProtectedOrPending())
                        {
                            LogEvent(account.Name, "AUTO_STOP_ESCALATE_SKIPPED", $"Stop-side flatten skipped for {instrument.FullName}; FSM already protected/pending.");
                            return;
                        }
                        FlattenAndClear($"Long stop {stopPrice} >= current price {currentPrice}. Flattening.");
                        return;
                    }
                }
                else if (position.MarketPosition == MarketPosition.Short)
                {
                    stopPrice = position.AveragePrice + (offsetTicks * tickSize);
                    orderAction = OrderAction.Buy;

                    if (stopPrice <= currentPrice)
                    {
                        if (IsFsmProtectedOrPending())
                        {
                            LogEvent(account.Name, "AUTO_STOP_ESCALATE_SKIPPED", $"Stop-side flatten skipped for {instrument.FullName}; FSM already protected/pending.");
                            return;
                        }
                        FlattenAndClear($"Short stop {stopPrice} <= current price {currentPrice}. Flattening.");
                        return;
                    }
                }
                else
                {
                    RollbackFsm("Unexpected position side");
                    LogEvent(account.Name, "AUTO_STOP_ABORT_UNEXPECTED_SIDE", $"Unexpected position side {position.MarketPosition} for {action.Instrument}; aborting auto-stop.");
                    return;
                }

                stopPrice = instrument.MasterInstrument.RoundToTickSize(stopPrice);

                // Re-read the live position immediately before sizing the stop.
                var positionForQuantity = account.Positions.FirstOrDefault(p => p.Instrument != null && p.Instrument.FullName == action.Instrument);
                if (positionForQuantity == null || positionForQuantity.MarketPosition == MarketPosition.Flat)
                {
                    ReArmGraceIfUnprotected();
                    LogEvent(account.Name, "AUTO_STOP_ABORT_NO_POSITION", $"Position became flat before stop sizing for {action.Instrument}; aborting auto-stop.");
                    return;
                }
                if (positionForQuantity.MarketPosition != position.MarketPosition)
                {
                    ReArmGraceIfUnprotected();
                    LogEvent(account.Name, "AUTO_STOP_ABORT_SIDE_MISMATCH",
                        $"Position side changed from {position.MarketPosition} to {positionForQuantity.MarketPosition} for {action.Instrument}; aborting auto-stop.");
                    return;
                }

                int stopQuantity = (int)positionForQuantity.Quantity;
                if (stopQuantity <= 0 || stopQuantity > (int)positionForQuantity.Quantity)
                {
                    ReArmGraceIfUnprotected();
                    LogEvent(account.Name, "AUTO_STOP_ABORT_NO_QUANTITY", $"Live position quantity {stopQuantity} for {action.Instrument}; aborting auto-stop.");
                    return;
                }

                // Diagnostic logging
                var orderDump = new StringBuilder();
                orderDump.AppendLine($"RiskGuard triggering auto-stop for {stopQuantity} {symbolName}. Current Orders:");
                foreach (Order o in account.Orders)
                {
                    if (o.Instrument?.FullName == action.Instrument)
                    {
                        orderDump.AppendLine($" - {o.OrderAction} {o.Quantity} {o.OrderType} | State: {o.OrderState} | Name: {o.Name}");
                    }
                }
                LogEvent(account.Name, "AUTO_STOP_DIAGNOSTIC", orderDump.ToString().TrimEnd());

                // Increment the attempt counter and confirm the FSM still exists
                // immediately before CreateOrder.
                PositionGuardFsm fsmForAttempt = null;
                lock (_stateLock)
                {
                    if (_guardFsms.TryGetValue(key, out PositionGuardFsm localFsm))
                    {
                        localFsm.AutoStopAttempts++;
                        fsmForAttempt = localFsm;
                    }
                }

                if (fsmForAttempt == null)
                {
                    LogEvent(account.Name, "AUTO_STOP_ABORT_FSM_LOST", $"FSM lost for {action.Instrument} before CreateOrder; flattening position.");
                    try
                    {
                        account.Flatten(new[] { instrument });
                    }
                    catch (Exception fex)
                    {
                        LogEvent(account.Name, "FLATTEN_ERROR", $"Flatten failed for {instrument.FullName}: {fex.Message}");
                        throw;
                    }
                    AfterFlattenCleanup("fsm-lost");
                    return;
                }

                Order stopOrder = account.CreateOrder(
                    instrument,
                    orderAction,
                    OrderType.StopMarket,
                    TimeInForce.Day,
                    stopQuantity,
                    0,
                    stopPrice,
                    string.Empty,
                    "RiskGuardAutoStop",
                    null
                );

                if (stopOrder == null)
                {
                    RollbackFsm("CreateOrder returned null");
                    LogEvent(account.Name, "AUTO_STOP_SUBMIT_FAILED", $"CreateOrder returned null for {instrument.FullName}.");
                    throw new Exception($"CreateOrder returned null for auto-stop on {instrument.FullName}");
                }

                // Reserve-before-submit: record the pending protection, then release
                // the lock before any account call.
                bool reserved = false;
                lock (_stateLock)
                {
                    if (_guardFsms.TryGetValue(key, out PositionGuardFsm localFsm))
                    {
                        localFsm.AutoStopOrder = stopOrder;
                        localFsm.RecognizedStopOrder = stopOrder;
                        localFsm.CoveredQuantity = stopQuantity;
                        localFsm.State = GuardFsmState.ProtectedPending;
                        reserved = true;
                    }
                }

                if (!reserved)
                {
                    // FSM disappeared after CreateOrder. Cancel the untracked stop
                    // and flatten as a fail-closed fallback.
                    try
                    {
                        account.Cancel(new[] { stopOrder });
                    }
                    catch (Exception cex)
                    {
                        LogEvent(account.Name, "AUTO_STOP_CANCEL_FAILED", $"Cancel of untracked stop failed for {instrument.FullName}: {cex.Message}");
                    }

                    LogEvent(account.Name, "AUTO_STOP_SUBMIT_FAILED", $"FSM lost before submit for {instrument.FullName}; flattening position.");
                    try
                    {
                        account.Flatten(new[] { instrument });
                    }
                    catch (Exception fex)
                    {
                        LogEvent(account.Name, "FLATTEN_ERROR", $"Flatten failed for {instrument.FullName}: {fex.Message}");
                        throw;
                    }
                    AfterFlattenCleanup("reserve-failed");
                    throw new Exception($"FSM lost before submit for auto-stop on {instrument.FullName}");
                }

                try
                {
                    account.Submit(new[] { stopOrder });
                }
                catch (Exception ex)
                {
                    bool alreadyProtected = false;
                    lock (_stateLock)
                    {
                        if (_guardFsms.TryGetValue(key, out PositionGuardFsm localFsm))
                        {
                            alreadyProtected = localFsm.State == GuardFsmState.Protected;
                            if (alreadyProtected)
                                localFsm.GraceEmitted = false;
                        }
                    }

                    if (alreadyProtected)
                    {
                        LogEvent(account.Name, "AUTO_STOP_SUBMIT_RACE",
                            $"Stop already Working for {instrument.FullName} despite Submit exception; leaving FSM Protected.");
                        return;
                    }

                    try
                    {
                        account.Cancel(new[] { stopOrder });
                    }
                    catch (Exception cex)
                    {
                        LogEvent(account.Name, "AUTO_STOP_CANCEL_FAILED", $"Cancel of failed-submit stop failed for {instrument.FullName}: {cex.Message}");
                    }

                    RollbackFsm($"Submit failed: {ex.Message}");
                    LogEvent(account.Name, "AUTO_STOP_SUBMIT_FAILED", $"Submit failed for {instrument.FullName}: {ex.Message}");
                    throw;
                }

                // No post-submit FSM write: UpdateFsmOnOrder owns all further state.
            }
        }

        // -
        // HELPER METHODS FOR UI & LOGGING
        // -

        public string GetAccountStatusString(string accountName)
        {
            lock (_stateLock)
            {
                if (!_accountStates.TryGetValue(accountName, out var state))
                {
                    return $"Account {accountName} not monitored.";
                }

                var sb = new StringBuilder();
                sb.AppendLine($"Account: {accountName}");
                sb.AppendLine($"Mode: {_mode} (Armed: {_isArmed})");
                sb.AppendLine($"Locked Out: {state.IsLockedOut}");
                sb.AppendLine($"Realized PnL: {state.RealizedPnL:C}");
                
                double openPnL = state.UnrealizedPnL;
                sb.AppendLine($"Open PnL: {openPnL:C}");
                sb.AppendLine($"Net PnL: {(state.RealizedPnL + openPnL):C}");
                sb.AppendLine($"Peak Equity (PnL): {state.PeakEquity:C}");
                
                sb.AppendLine("Positions:");
                foreach (var pos in state.Positions.Values)
                {
                    if (pos.MarketPosition != MarketPosition.Flat)
                    {
                        string posType = pos.MarketPosition == MarketPosition.Long ? "LONG" : "SHORT";
                        sb.AppendLine($"  - {pos.Instrument}: {posType} {pos.Quantity} @ {pos.AveragePrice}");
                        if (pos.LastNonFlatTransition != DateTime.MinValue)
                        {
                            double elapsed = (DateTime.UtcNow - pos.LastNonFlatTransition).TotalSeconds;
                            sb.AppendLine($"    Open for: {elapsed:F1}s");
                        }
                    }
                }
                
                return sb.ToString();
            }
        }

        private void LogEvent(string account, string eventType, string message)
        {
            LogEvent(account, eventType, new JObject { { "message", message } });
        }

        private void LogEvent(string account, string eventType, JObject data)
        {
            try
            {
                JObject logEntry = new JObject
                {
                    { "timestamp_utc", DateTime.UtcNow.ToString("o") },
                    { "timestamp_et", TimeZoneInfo.ConvertTimeFromUtc(DateTime.UtcNow, _etZone).ToString("o") },
                    { "account", account },
                    { "eventType", eventType },
                    { "mode", _mode },
                    { "isArmed", _isArmed },
                    { "data", data }
                };

                string logLine = logEntry.ToString(Formatting.None);
                _logQueue.Enqueue(logLine);
            }
            catch
            {
                NinjaTrader.Code.Output.Process($"Failed to serialize log: {eventType} for {account}", PrintTo.OutputTab1);
            }
        }

        // - Firm-mirror logic and unit test diagnostics (FR-24/25/26) -
        /// <summary>
        /// Evaluates the firm-mirror trailing-drawdown and daily-loss rules.
        /// </summary>
        /// <param name="nowUtc">
        /// UTC timestamp to evaluate against. This parameter was previously named nowEt and was
        /// IGNORED - the method read DateTime.UtcNow internally, so the firm daily-reset boundary
        /// (FirmMirror.DailyResetHourUtc, default 22:00 UTC) could roll over mid-test and zero the
        /// P&amp;L basis. That made TestFirmMirrorDailyLossBreachEmitsAction fail every day after
        /// 22:00 UTC, and because a corrupted test called Environment.Exit on failure, it silently
        /// skipped the last 25 tests in the suite. Callers must now pass the clock explicitly.
        /// </param>
        internal List<GuardAction> EvaluateFirmMirror(Account account, AccountState st, DateTime nowUtc)
        {
            double balance = account.Get(AccountItem.CashValue, Currency.UsDollar);
            double realized = account.Get(AccountItem.RealizedProfitLoss, Currency.UsDollar);
            double unrealized = account.Get(AccountItem.UnrealizedProfitLoss, Currency.UsDollar);

            var res = ComputeFirmMirror(balance, realized, unrealized, _config.FirmMirror, st, nowUtc);
            
            if (res.StateChanged)
            {
                _stateDirty = true;
                foreach (var log in res.TraceLogs)
                {
                    LogEvent(st.AccountName, "FIRM_STATE_UPDATE", log);
                }
            }

            var actions = new List<GuardAction>();
            if (res.TrailingDDBreached)
            {
                LogEvent(st.AccountName, "FIRM_TRAILING_DD_BREACH", new JObject
                {
                    { "currentFirmEquity", balance + unrealized },
                    { "guardFloor", res.GuardFloor },
                    { "effectiveFloor", res.EffectiveFloor },
                    { "trailingPeak", res.TrailingPeak },
                    { "floorLocked", res.FloorLocked },
                    { "amount", _config.FirmMirror.TrailingDD.Amount },
                    { "buffer", _config.FirmMirror.TrailingDD.Buffer }
                });

                actions.Add(new GuardAction
                {
                    AccountName = st.AccountName,
                    ActionType = GuardActionType.FlattenPosition,
                    RuleId = "FIRM_TRAILING_DD_BREACH"
                });
                if (!st.IsLockedOut) { st.IsLockedOut = true; _stateDirty = true; }
            }

            if (res.DailyLossBreached)
            {
                double dayRealized = realized - st.FirmDailyStartRealized;
                double dayPnL = _config.FirmMirror.DailyLoss.Basis == "include_unrealized_peak"
                    ? dayRealized + unrealized
                    : dayRealized;

                LogEvent(st.AccountName, "FIRM_DAILY_LOSS_BREACH", new JObject
                {
                    { "dayPnL", dayPnL },
                    { "guardLimit", res.GuardDailyLimit },
                    { "basis", _config.FirmMirror.DailyLoss.Basis },
                    { "amount", _config.FirmMirror.DailyLoss.Amount },
                    { "buffer", _config.FirmMirror.DailyLoss.Buffer }
                });

                actions.Add(new GuardAction
                {
                    AccountName = st.AccountName,
                    ActionType = GuardActionType.FlattenPosition,
                    RuleId = "FIRM_DAILY_LOSS_BREACH"
                });
                if (!st.IsLockedOut) { st.IsLockedOut = true; _stateDirty = true; }
            }

            return actions;
        }

        public static FirmMirrorResult ComputeFirmMirror(
            double balance, 
            double realized, 
            double unrealized, 
            FirmMirrorConfig fm, 
            AccountState st, 
            DateTime nowUtc)
        {
            var result = new FirmMirrorResult();
            bool stateChanged = false;

            if (st.FirmStartingBalance == 0.0)
            {
                st.FirmStartingBalance = balance - realized - unrealized;
                result.TraceLogs.Add($"Initial starting balance captured heuristically: {st.FirmStartingBalance}");
                stateChanged = true;
            }

            var boundary = new TimeSpan(fm.DailyResetHourUtc, fm.DailyResetMinuteUtc, 0);
            DateTime firmDailyDate = nowUtc.TimeOfDay >= boundary ? nowUtc.Date.AddDays(1) : nowUtc.Date;
            if (st.FirmDailyDate != firmDailyDate)
            {
                st.FirmDailyDate = firmDailyDate;
                st.FirmDailyStartRealized = realized;
                result.TraceLogs.Add($"Firm daily boundary rollover for {firmDailyDate:yyyy-MM-dd} (UTC {fm.DailyResetHourUtc:00}:{fm.DailyResetMinuteUtc:00})");
                stateChanged = true;
            }

            if (fm.TrailingDD.Enabled)
            {
                double firmEquity = fm.TrailingDD.IncludesUnrealized
                    ? balance + unrealized
                    : balance;

                if (fm.TrailingDD.Type == "eod")
                {
                    firmEquity = balance;
                }

                if (!st.FirmFloorLocked)
                {
                    if (firmEquity > st.FirmTrailingPeak)
                    {
                        st.FirmTrailingPeak = firmEquity;
                        result.TraceLogs.Add($"Firm trailing peak advanced to: {st.FirmTrailingPeak}");
                        stateChanged = true;
                    }

                    if (fm.TrailingDD.LockAtProfit > 0.0 && st.FirmStartingBalance > 0.0)
                    {
                        if (st.FirmTrailingPeak >= st.FirmStartingBalance + fm.TrailingDD.LockAtProfit)
                        {
                            st.FirmFloorLocked = true;
                            result.TraceLogs.Add($"Trailing floor locked at starting balance. Peak={st.FirmTrailingPeak}, start={st.FirmStartingBalance}");
                            stateChanged = true;
                        }
                    }
                }

                double effectiveFloor = st.FirmFloorLocked
                    ? st.FirmStartingBalance
                    : st.FirmTrailingPeak - fm.TrailingDD.Amount;

                double guardFloor = effectiveFloor + fm.TrailingDD.Buffer;

                if (fm.TrailingDD.Type == "static" && st.FirmStartingBalance > 0.0)
                {
                    guardFloor = (st.FirmStartingBalance - fm.TrailingDD.Amount) + fm.TrailingDD.Buffer;
                }

                result.EffectiveFloor = effectiveFloor;
                result.GuardFloor = guardFloor;
                result.TrailingPeak = st.FirmTrailingPeak;
                result.FloorLocked = st.FirmFloorLocked;

                // DIFF 4: breach test uses the same basis as peak tracking (no mismatch)
                if (firmEquity <= guardFloor)
                {
                    result.TrailingDDBreached = true;
                }
            }

            if (fm.DailyLoss.Enabled)
            {
                double dayRealized = realized - st.FirmDailyStartRealized;
                double dayPnL = fm.DailyLoss.Basis == "include_unrealized_peak"
                    ? dayRealized + unrealized
                    : dayRealized;

                double guardLimit = -(fm.DailyLoss.Amount - fm.DailyLoss.Buffer);
                result.GuardDailyLimit = guardLimit;

                if (dayPnL <= guardLimit)
                {
                    result.DailyLossBreached = true;
                }
            }

            result.StateChanged = stateChanged;
            return result;
        }

        public FirmDiagnosticsResult RunFirmDiagnostics()
        {
            var res = new FirmDiagnosticsResult();
            res.Logs.Add("Starting Firm Mirror Unit Diagnostics...");

            try
            {
                var st = new AccountState("SimMock");
                st.FirmStartingBalance = 100000.0;
                st.FirmTrailingPeak = 100000.0;
                st.FirmFloorLocked = false;
                st.FirmDailyDate = new DateTime(2026, 7, 15);
                st.FirmDailyStartRealized = 0.0;

                var fm = new FirmMirrorConfig
                {
                    Enabled = true,
                    DailyResetHourUtc = 22,
                    DailyResetMinuteUtc = 0,
                    TrailingDD = new FirmTrailingDDConfig
                    {
                        Enabled = true,
                        Type = "intraday",
                        IncludesUnrealized = true,
                        Amount = 2500.0,
                        Buffer = 300.0,
                        LockAtProfit = 3000.0
                    },
                    DailyLoss = new FirmDailyLossConfig
                    {
                        Enabled = true,
                        Basis = "realized",
                        Amount = 1500.0,
                        Buffer = 200.0
                    }
                };

                // Test 1: Trailing DD buffer breach
                res.Logs.Add("[Test 1: Trailing DD] Advancing equity to 102,000...");
                var r1 = ComputeFirmMirror(102000.0, 2000.0, 0.0, fm, st, new DateTime(2026, 7, 15, 12, 0, 0, DateTimeKind.Utc));
                res.Logs.AddRange(r1.TraceLogs);
                if (st.FirmTrailingPeak != 102000.0) throw new Exception("Peak did not trail up to 102,000.");
                if (r1.GuardFloor != 99800.0) throw new Exception(string.Format("Expected guard floor to be 99,800, got {0}", r1.GuardFloor));

                res.Logs.Add("Dropping equity to 99,900...");
                var r2 = ComputeFirmMirror(99900.0, -100.0, 0.0, fm, st, new DateTime(2026, 7, 15, 13, 0, 0, DateTimeKind.Utc));
                if (r2.TrailingDDBreached) throw new Exception("Trailing DD breached prematurely at 99,900.");

                res.Logs.Add("Dropping equity to 99,750...");
                var r3 = ComputeFirmMirror(99750.0, -250.0, 0.0, fm, st, new DateTime(2026, 7, 15, 14, 0, 0, DateTimeKind.Utc));
                if (!r3.TrailingDDBreached) throw new Exception("Guard floor failed to trip at 99,750 (buffer-adjusted floor = 99,800).");
                res.Logs.Add("Test 1 Passed: Trailing DD buffer breach triggered correctly.");

                // Test 2: Floor Lock
                st.FirmStartingBalance = 100000.0;
                st.FirmTrailingPeak = 100000.0;
                st.FirmFloorLocked = false;

                res.Logs.Add("[Test 2: Floor Lock] Advancing equity to 103,500...");
                var r4 = ComputeFirmMirror(103500.0, 3500.0, 0.0, fm, st, new DateTime(2026, 7, 15, 15, 0, 0, DateTimeKind.Utc));
                res.Logs.AddRange(r4.TraceLogs);
                if (!st.FirmFloorLocked) throw new Exception("Floor did not lock after peak crossed LockAtProfit.");

                res.Logs.Add("Dropping equity to 100,250...");
                var r5 = ComputeFirmMirror(100250.0, 250.0, 0.0, fm, st, new DateTime(2026, 7, 15, 16, 0, 0, DateTimeKind.Utc));
                if (!r5.TrailingDDBreached) throw new Exception("Floor lock trailing DD failed to trip at 100,250.");
                res.Logs.Add("Test 2 Passed: Floor lock and breach verified.");

                // Test 3: Daily loss UTC boundary rollover & limit breach
                st.FirmDailyDate = DateTime.MinValue;
                st.FirmDailyStartRealized = 0.0;
                res.Logs.Add("[Test 3: Daily Loss] Initializing daily loss trace at 20:00 UTC...");
                var r6 = ComputeFirmMirror(100000.0, 0.0, 0.0, fm, st, new DateTime(2026, 7, 15, 20, 0, 0, DateTimeKind.Utc));
                res.Logs.AddRange(r6.TraceLogs);

                res.Logs.Add("Rollover daily reset boundary (23:00 UTC)...");
                var r7 = ComputeFirmMirror(102000.0, 2000.0, 0.0, fm, st, new DateTime(2026, 7, 15, 23, 0, 0, DateTimeKind.Utc));
                res.Logs.AddRange(r7.TraceLogs);
                if (st.FirmDailyStartRealized != 2000.0) throw new Exception("Failed to reset daily realized baseline.");

                res.Logs.Add("Post-rollover loss of 1,200...");
                var r8 = ComputeFirmMirror(100800.0, 800.0, 0.0, fm, st, new DateTime(2026, 7, 16, 0, 0, 0, DateTimeKind.Utc));
                if (r8.DailyLossBreached) throw new Exception("Daily loss breached prematurely at -1,200 loss.");

                res.Logs.Add("Post-rollover loss of 1,350...");
                var r9 = ComputeFirmMirror(100650.0, 650.0, 0.0, fm, st, new DateTime(2026, 7, 16, 1, 0, 0, DateTimeKind.Utc));
                if (!r9.DailyLossBreached) throw new Exception("Daily loss failed to breach at -1,350 (limit=-1,300).");
                res.Logs.Add("Test 3 Passed: Daily reset and daily loss limit verified.");

                res.Success = true;
                res.Logs.Add("All diagnostics passed!");
            }
            catch (Exception ex)
            {
                res.Success = false;
                res.Logs.Add("ERROR: " + ex.Message);
            }

            return res;
        }
    }

    public enum GuardActionType
    {
        FlattenPosition,
        CancelAllOrders,
        CancelOrder,
        PlaceStopOrder
    }

    public class GuardAction
    {
        public string AccountName { get; set; }
        public GuardActionType ActionType { get; set; }
        public string Instrument { get; set; }
        public Instrument InstrumentObj { get; set; }
        public string OrderId { get; set; }
        public int Quantity { get; set; }
        public string RuleId { get; set; }
    }

    public class AccountState
    {
        public string AccountName { get; }
        public Dictionary<string, PositionState> Positions { get; } = new Dictionary<string, PositionState>();
        public double RealizedPnL { get; set; } = 0.0;
        public double UnrealizedPnL { get; set; } = 0.0;
        public double PeakEquity { get; set; } = 0.0;
        public double PeakOpenGain { get; set; } = 0.0;
        public bool PeakGivebackTriggered { get; set; } = false;
        public double PeakGivebackLastTriggerUnrealized { get; set; } = double.NaN;
        public bool IsLockedOut { get; set; } = false;
        public DateTime LockoutUntil { get; set; } = DateTime.MinValue;
        public bool InitialLockoutFlattened { get; set; } = false;
        public DateTime LastLockoutFlattenAttempt { get; set; } = DateTime.MinValue;
        public List<DateTime> OrderTimestamps { get; set; } = new List<DateTime>();

        // Lockout phase: PendingCancel -> PendingFlatten -> Confirmed.
        // Only Confirmed stops emitting actions. This prevents the infinite
        // flatten loop where account.Flatten() fails silently but the sweep
        // keeps re-firing every second.
        public enum LockoutPhase { None, PendingCancel, PendingFlatten, Confirmed }
        public LockoutPhase CurrentLockoutPhase { get; set; } = LockoutPhase.None;
        
        // Session and Overtrading
        public DateTime LastSessionDate { get; set; } = DateTime.MinValue;
        public int TradesToday { get; set; } = 0;
        public int ConsecutiveLosses { get; set; } = 0;
        public DateTime CooldownUntil { get; set; } = DateTime.MinValue;
        public double LastRealizedPnL { get; set; } = 0.0; // To track delta for consec losses
        public double SessionStartRealizedPnL { get; set; } = 0.0; // Baseline for session PnL

        // - Firm-mirror tracking (independent of discretionary PeakEquity) -
        public double FirmTrailingPeak { get; set; } = double.MinValue;
        public bool FirmFloorLocked { get; set; } = false;
        public DateTime FirmDailyDate { get; set; } = DateTime.MinValue;
        public double FirmDailyStartRealized { get; set; } = 0.0;
        public double FirmStartingBalance { get; set; } = 0.0;

        public AccountState(string name)
        {
            AccountName = name;
        }

        public bool UpdatePosition(Account account, Instrument instrument, MarketPosition position, int quantity, double avgPrice, double unrealizedPnL, RiskConfig config)
        {
            if (quantity == 0)
            {
                position = MarketPosition.Flat;
            }

            string instrumentName = instrument.FullName;
            if (!Positions.TryGetValue(instrumentName, out var pState))
            {
                pState = new PositionState(instrument);
                Positions[instrumentName] = pState;
            }

            bool stateChanged = false;

            bool wasNonFlat = pState.MarketPosition != MarketPosition.Flat;
            bool isNonFlat = position != MarketPosition.Flat;
            bool isFlip = wasNonFlat && isNonFlat && position != pState.MarketPosition;

            // Treat a flip as a close of the old trade followed by a new entry.
            if ((position == MarketPosition.Flat && wasNonFlat) || isFlip)
            {
                pState.LastFlatTransition = DateTime.UtcNow;
                stateChanged = true;

                if (isFlip)
                {
                    // NinjaTrader collapsed a close + reverse into one update.
                    // Log it so shadow data reveals how often flips occur.
                    NinjaTrader.Code.Output.Process(
                        $"[RiskGuard] FLIP detected on {AccountName}/{instrumentName}: " +
                        $"{pState.MarketPosition} -> {position}. Counted as close+entry.",
                        PrintTo.OutputTab1);
                }
            }

            // --- OPEN side: a new entry begins (flat->nonflat, or the new leg of a flip) ---
            if ((isNonFlat && !wasNonFlat) || isFlip)
            {
                pState.LastNonFlatTransition = DateTime.UtcNow;

                // A flip closes the old position and opens a new opposite leg in one
                // update. Reset the per-open-position peak-giveback tracking so the
                // new leg is not judged against the prior direction's peak.
                if (isFlip)
                {
                    PeakOpenGain = 0.0;
                    PeakGivebackTriggered = false;
                    PeakGivebackLastTriggerUnrealized = double.NaN;
                }

                // Debounce multi-contract / split-order trade count increment:
                // Only increment TradesToday if this is a genuine new trade lifecycle
                // (either a flip, or position was flat for > 1000ms, or initial entry).
                bool isGenuineNewTrade = isFlip || pState.LastFlatTransition == DateTime.MinValue ||
                                         (DateTime.UtcNow - pState.LastFlatTransition).TotalMilliseconds > 1000;

                if (isGenuineNewTrade)
                {
                    TradesToday++; // Increment trade count
                }
                stateChanged = true;
            }
            else if (position == MarketPosition.Flat && wasNonFlat)
            {
                pState.LastNonFlatTransition = DateTime.MinValue;
            }

            pState.MarketPosition = position;
            pState.Quantity = quantity;
            pState.AveragePrice = avgPrice;
            pState.UnrealizedPnL = unrealizedPnL;

            // When the account returns to flat, reset the per-open-position
            // peak-giveback tracking so it cannot carry into the next trade.
            if (position == MarketPosition.Flat && wasNonFlat)
            {
                bool accountNowFlat = true;
                foreach (var pos in Positions.Values)
                {
                    if (pos.MarketPosition != MarketPosition.Flat)
                    {
                        accountNowFlat = false;
                        break;
                    }
                }

                if (accountNowFlat)
                {
                    PeakOpenGain = 0.0;
                    PeakGivebackTriggered = false;
                    PeakGivebackLastTriggerUnrealized = double.NaN;
                }
            }

            return stateChanged;
        }

        public void RecordExecution(string instrument, string action, int quantity, double price)
        {
            // Simple calculation of PnL can be done if execution updates are matched,
            // but in practice NinjaTrader handles account balance updates directly.
        }
    }

    public class FirmMirrorResult
    {
        public bool TrailingDDBreached { get; set; }
        public bool DailyLossBreached { get; set; }
        public double TrailingPeak { get; set; }
        public bool FloorLocked { get; set; }
        public double EffectiveFloor { get; set; }
        public double GuardFloor { get; set; }
        public double GuardDailyLimit { get; set; }
        public bool StateChanged { get; set; }
        public List<string> TraceLogs { get; set; } = new List<string>();
    }

    public class FirmDiagnosticsResult
    {
        public bool Success { get; set; }
        public List<string> Logs { get; set; } = new List<string>();
    }

    public class PositionState
    {
        public string Instrument { get; }
        public Instrument InstrumentObj { get; }
        public MarketPosition MarketPosition { get; set; } = MarketPosition.Flat;
        public int Quantity { get; set; }
        public double AveragePrice { get; set; }
        public double UnrealizedPnL { get; set; }
        public DateTime LastNonFlatTransition { get; set; } = DateTime.MinValue;
        public DateTime LastFlatTransition { get; set; } = DateTime.MinValue;

        public PositionState(Instrument instrument)
        {
            InstrumentObj = instrument;
            Instrument = instrument.FullName;
        }
    }

    internal static class RiskGuardOrderUtils
    {
        public static bool IsPositionReducingOrder(Order order, AccountState stateModel)
        {
            if (order == null || order.Instrument == null || stateModel == null) return false;
            string instrName = order.Instrument.FullName;
            if (!stateModel.Positions.TryGetValue(instrName, out var pState)) return false;

            if (pState.MarketPosition == MarketPosition.Long)
            {
                return order.OrderAction == OrderAction.Sell || order.OrderAction == OrderAction.SellShort;
            }
            else if (pState.MarketPosition == MarketPosition.Short)
            {
                return order.OrderAction == OrderAction.Buy || order.OrderAction == OrderAction.BuyToCover;
            }

            return false;
        }
    }

    // -
    // PER-POSITION GUARD STATE MACHINE (-6 of RiskGuardAddOn.md)
    // -
    // Tracks the protective-stop lifecycle for one (account, instrument) pair.
    // Eliminates the duplicate-SL race on OCO brackets by remembering that the
    // stop leg's Submitted event was already observed, so a later sweep or
    // re-entrant position update finds the FSM in ProtectedPending/Protected.
    public enum GuardFsmState
    {
        Unprotected,       // position open, no covering stop observed yet
        ProtectedPending,  // stop leg Submitted/Initialized/Accepted, not yet Working
        Protected,         // working stop covering the position
        FlattenPending,    // grace expired with OnMissing=Flatten, action emitted once
        Flat               // position closed; FSM entry awaiting cleanup
    }

    public class PositionGuardFsm
    {
        public string AccountName { get; }
        public string Instrument { get; }
        private GuardFsmState _state = GuardFsmState.Unprotected;
        public GuardFsmState State
        {
            get { return _state; }
            set
            {
                GuardFsmState previous = _state;
                _state = value;
                // Reset the per-episode auto-stop attempt counter when the FSM
                // reaches Protected (successful protection), reaches Flat (position
                // closed), transitions from Flat back to Unprotected (new episode),
                // or transitions from Protected back to Unprotected (protection
                // removed). We deliberately do NOT reset on Unprotected ->
                // ProtectedPending so that failed submit attempts continue to count
                // toward escalation.
                if (value == GuardFsmState.Protected && previous != value)
                    AutoStopAttempts = 0;
                else if (value == GuardFsmState.Flat && previous != value)
                    AutoStopAttempts = 0;
                else if (previous == GuardFsmState.Flat && value == GuardFsmState.Unprotected)
                    AutoStopAttempts = 0;
                else if (previous == GuardFsmState.Protected && value == GuardFsmState.Unprotected)
                    AutoStopAttempts = 0;
            }
        }
        public MarketPosition PositionSide { get; set; } = MarketPosition.Flat;
        public int PositionQuantity { get; set; }
        // NOTE: NT8 Order.OrderId is NOT unique and can change over the order's
        // lifetime (historical->live transition). Track recognised stops by the
        // Order object reference, not by id string. See RiskGuardAddOn.md -6.6.
        public Order RecognizedStopOrder { get; set; }
        public Order AutoStopOrder { get; set; }
        public string EntryOcoId { get; set; }   // best-effort join key; may be empty for external brackets
        public DateTime EntryTime { get; set; } = DateTime.MinValue;
        public DateTime GraceDeadline { get; set; } = DateTime.MinValue;
        public DateTime LastTransitionTime { get; set; } = DateTime.UtcNow;
        // One-shot grace timer: fires exactly at EntryTime + StopGuard.StopAttachSeconds.
        // Cancelled when the FSM reaches Protected or Flat. This replaces the sweep
        // polling of GraceDeadline with an instant event-driven trigger.
        public Timer GraceTimer { get; set; }

        // Quantity covered by the single RecognizedStopOrder.
        public int CoveredQuantity { get; set; }
        // True while a one-shot grace timer is armed.
        public bool GracePending { get; set; }
        // True once a grace action has been emitted and its outcome is still pending.
        public bool GraceEmitted { get; set; }
        // Monotonically increasing generation counter to invalidate stale timer callbacks.
        public long GraceGeneration { get; set; }
        // Number of auto-stop submit attempts in the current unprotected episode.
        // Escalation to flatten happens when this exceeds MaxAutoStopAttempts.
        public int AutoStopAttempts { get; set; }

        public PositionGuardFsm(string accountName, string instrument)
        {
            AccountName = accountName;
            Instrument = instrument;
        }
    }

    public class PersistedStateData
    {
        public bool IsArmed { get; set; }
        public string Mode { get; set; }
        public List<string> LockedOutAccounts { get; set; } = new List<string>();
        // FR-29: count of completed shadow sessions. Persisted across restarts.
        public int ShadowSessionsCompleted { get; set; }
        
        // Dictionary for per-account persisted data
        public Dictionary<string, AccountPersistedData> AccountsData { get; set; } = new Dictionary<string, AccountPersistedData>();
        
        public DateTime Timestamp { get; set; }
    }

    public class AccountPersistedData
    {
        public DateTime LastSessionDate { get; set; }
        public int TradesToday { get; set; }
        public int ConsecutiveLosses { get; set; }
        public double PeakEquity { get; set; }
        public double LastRealizedPnL { get; set; }
        public double SessionStartRealizedPnL { get; set; }
        public double FirmTrailingPeak { get; set; }
        public bool FirmFloorLocked { get; set; }
        public DateTime FirmDailyDate { get; set; }
        public double FirmDailyStartRealized { get; set; }
        public double FirmStartingBalance { get; set; }
    }

    // -
    // CONFIGURATION MODELS
    // -

    public class InstrumentProfile
    {
        public int MaxContracts { get; set; } = 5;
    }

    public class AccountRiskProfile
    {
        public string ProfileName { get; set; } = "Default";
        public string AccountNamePattern { get; set; } = ".*";

        public double DailyLossLimit { get; set; } = 0.0;
        public double TrailingDrawdown { get; set; } = 0.0;
        public int MaxTradesPerSession { get; set; } = 0;
        public int DefaultMaxContracts { get; set; } = 0;

        public Dictionary<string, InstrumentProfile> InstrumentProfiles { get; set; } = new Dictionary<string, InstrumentProfile>(StringComparer.OrdinalIgnoreCase);
    }

    public class PerInstrumentRiskConfig
    {
        public int MaxContracts { get; set; } = 10;
        public bool IsBlocked { get; set; } = false;
        public double StopOffsetTicks { get; set; } = 40;
    }

    public class RiskConfig
    {
        public List<AccountRiskProfile> Profiles { get; set; } = new List<AccountRiskProfile>();
        public List<string> ExcludedAccounts { get; set; } = new List<string>();
        // Accounts listed here MAY bypass a persisted lockout when the guard is disarmed.
        // Accounts NOT listed here keep their lockout enforced even when disarmed (safe default for prop-firm accounts).
        // Default empty = lockouts persist for ALL accounts regardless of armed state.
        public List<string> LockoutBypassWhileDisarmedAccounts { get; set; } = new List<string>();
        public string Mode { get; set; } = "shadow";
        public bool EnableWindowGate { get; set; } = false;
        // FR-29: minimum completed shadow sessions before live-mode arming is permitted (soft gate).
        // Set to 0 to disable. The counter is persisted in PersistedStateData and incremented on session reset.
        public int MinShadowSessions { get; set; } = 0;
        public Dictionary<string, PerInstrumentRiskConfig> InstrumentLimits { get; set; } = new Dictionary<string, PerInstrumentRiskConfig>(StringComparer.OrdinalIgnoreCase);
        public List<string> BlockedInstruments { get; set; } = new List<string>();
        public SizingConfig Sizing { get; set; } = new SizingConfig();
        public OvertradingConfig Overtrading { get; set; } = new OvertradingConfig();
        public StopGuardConfig StopGuard { get; set; } = new StopGuardConfig();
        public PnLRulesConfig PnLRules { get; set; } = new PnLRulesConfig();
        public FirmMirrorConfig FirmMirror { get; set; } = new FirmMirrorConfig();
        // FR-35/36: override friction for override_with_friction enforcement mode.
        public OverrideConfig Override { get; set; } = new OverrideConfig();
        public List<WindowConfig> WindowsET { get; set; } = new List<WindowConfig>
        {
            new WindowConfig { Name = "NY_AM_Macro", Start = "09:50", End = "11:10" },
            new WindowConfig { Name = "NY_PM_Macro", Start = "13:50", End = "15:10" }
        };
    }

    // FR-35/36: friction-gated lockout override. When Mode == "override_with_friction",
    // escaping a lockout requires typing the exact confirm phrase AND waiting wait_seconds
    // (enforced minimum 30s). This prevents one-click panic bypasses.
    public class OverrideConfig
    {
        public string ConfirmPhrase { get; set; } = "I understand locked means locked";
        // FR-36 enforced minimum: clamped to >= 30 at validation time.
        public int WaitSeconds { get; set; } = 120;
    }

    public class FirmMirrorConfig
    {
        public bool Enabled { get; set; } = false;
        public FirmTrailingDDConfig TrailingDD { get; set; } = new FirmTrailingDDConfig();
        public FirmDailyLossConfig DailyLoss { get; set; } = new FirmDailyLossConfig();
        public int DailyResetHourUtc { get; set; } = 22;
        public int DailyResetMinuteUtc { get; set; } = 0;
        // Per-firm profiles: map account name -> firm name. The matching FirmProfile in FirmProfiles
        // supplies the firm-specific drawdown/daily-loss rules. Falls back to TrailingDD/DailyLoss above
        // when an account is not mapped or the firm name is not found.
        public Dictionary<string, string> AccountFirmMap { get; set; } = new Dictionary<string, string>(StringComparer.OrdinalIgnoreCase);
        public Dictionary<string, FirmProfile> FirmProfiles { get; set; } = new Dictionary<string, FirmProfile>(StringComparer.OrdinalIgnoreCase);
    }

    // Per-firm rules researched 2026-08-02. All four firms use EOD trailing drawdown for evaluations;
    // daily loss limits vary (TPT has none). Reset boundary is CME Globex rollover (~22:00 UTC).
    public class FirmProfile
    {
        public string Name { get; set; } = "";
        public FirmTrailingDDConfig TrailingDD { get; set; } = new FirmTrailingDDConfig();
        public FirmDailyLossConfig DailyLoss { get; set; } = new FirmDailyLossConfig();
    }

    public class FirmTrailingDDConfig
    {
        public bool Enabled { get; set; } = false;
        public string Type { get; set; } = "intraday";
        public bool IncludesUnrealized { get; set; } = true;
        public double Amount { get; set; } = 2500.0;
        public double Buffer { get; set; } = 300.0;
        public double LockAtProfit { get; set; } = 0.0;
    }

    public class FirmDailyLossConfig
    {
        public bool Enabled { get; set; } = false;
        public string Basis { get; set; } = "realized";
        public double Amount { get; set; } = 1500.0;
        public double Buffer { get; set; } = 200.0;
    }

    public class SizingConfig
    {
        public int MaxContractsPerAccount { get; set; } = 10;
        public int MaxContractsAggregate { get; set; } = 20;
        public int ExpectedCopies { get; set; } = 1; // intended N-way mirror across accounts
    }

    public class OvertradingConfig
    {
        public int MaxTradesPerSession { get; set; } = 8;
        public int CooldownMinutes { get; set; } = 5;
        public int MaxConsecutiveLosses { get; set; } = 3;
        public int LockoutMinutes { get; set; } = 60;
    }

    public class StopGuardConfig
    {
        public string OnMissing { get; set; } = "Flatten"; // "AutoStop", "Flatten", "WarnOnly"
        public int StopAttachSeconds { get; set; } = 3;
        public int MaxAutoStopAttempts { get; set; } = 2;
        public Dictionary<string, int> Offsets { get; set; } = new Dictionary<string, int>
        {
            { "NQ", 40 },
            { "MNQ", 40 },
            { "ES", 16 },
            { "MES", 16 },
            { "default", 30 }
        };
    }

    public class PnLRulesConfig
    {
        public double DailyLossLimit { get; set; } = 1000.0;
        public double TrailingDrawdown { get; set; } = 1500.0;
        public int LockoutMinutes { get; set; } = 60;
    }

    public class WindowConfig
    {
        public string Name { get; set; }
        public string Start { get; set; }
        public string End { get; set; }
        public List<string> Days { get; set; } = new List<string> { "Monday", "Tuesday", "Wednesday", "Thursday", "Friday" };
    }

    public class ParsedWindow
    {
        public TimeSpan Start { get; set; }
        public TimeSpan End { get; set; }
        public HashSet<DayOfWeek> Days { get; set; }
    }

    // -
    // WPF UI DASHBOARD
    // -

#if !TESTING
    public class RiskGuardWindow : Window
    {
        private readonly RiskGuardAddOn _addOn;
        private DispatcherTimer _uiTimer;
        private TextBlock _armedStatusText;
        private Button _toggleArmedBtn;
        private Button _panicAllBtn;
        private WrapPanel _cardsPanel;
        
        private readonly Dictionary<string, CardControls> _cardControls = new Dictionary<string, CardControls>();

        // Config UI fields
        private ComboBox _modeCombo;
        private CheckBox _windowGateCheck;
        private TextBox _maxContractsAccountText;
        private TextBox _maxContractsAggregateText;
        private TextBox _maxTradesSessionText;
        private TextBox _maxConsecutiveLossesText;
        private TextBox _cooldownMinutesText;
        private TextBox _lockoutMinutesText;
        private TextBox _dailyLossLimitText;
        private TextBox _trailingDrawdownText;
        private TextBox _pnlLockoutMinutesText;
        private ComboBox _onMissingCombo;
        private TextBox _stopAttachSecondsText;
        private TextBox _expectedCopiesText;
        private TextBox _excludedAccountsText;
        private CheckBox _firmMirrorEnabledCheck;
        private TextBox _firmTrailingDDAmountText;
        private TextBox _firmDailyLossAmountText;

        // Search and Filter fields
        private TextBox _searchBox;
        private CheckBox _hideInactiveCheck;

        // Track which accounts have already shown a lockout-stuck popup
        // so we don't spam the user every 500ms UI tick.
        private readonly HashSet<string> _lockoutStuckPopupShown = new HashSet<string>();

        public RiskGuardWindow(RiskGuardAddOn addOn)
        {
            _addOn = addOn;
            Title = $"NinjaTrader Cross-Account Risk Guard Dashboard v{RiskGuardAddOn.Version}";
            Width = 1000;
            Height = 700;
            Background = new SolidColorBrush(Color.FromRgb(30, 30, 30));
            WindowStartupLocation = WindowStartupLocation.CenterScreen;

            var mainGrid = new Grid();
            mainGrid.RowDefinitions.Add(new RowDefinition { Height = GridLength.Auto });
            mainGrid.RowDefinitions.Add(new RowDefinition { Height = new GridLength(1, GridUnitType.Star) });

            // TOP BAR (dark theme)
            var topBar = new Border { Background = new SolidColorBrush(Color.FromRgb(45, 45, 48)), Padding = new Thickness(10) };
            var topGrid = new Grid();
            topGrid.ColumnDefinitions.Add(new ColumnDefinition { Width = GridLength.Auto });
            topGrid.ColumnDefinitions.Add(new ColumnDefinition { Width = new GridLength(1, GridUnitType.Star) });
            topGrid.ColumnDefinitions.Add(new ColumnDefinition { Width = GridLength.Auto });
            topBar.Child = topGrid;

            var statusPanel = new StackPanel { Orientation = Orientation.Horizontal };
            statusPanel.Children.Add(new TextBlock { Text = "- RISK GUARD: ", Foreground = Brushes.White, FontSize = 14, FontWeight = FontWeights.Bold, VerticalAlignment = VerticalAlignment.Center });
            
            _armedStatusText = new TextBlock { FontSize = 14, FontWeight = FontWeights.Bold, VerticalAlignment = VerticalAlignment.Center };
            statusPanel.Children.Add(_armedStatusText);

            _toggleArmedBtn = new Button 
            { 
                Content = "TOGGLE ARMED", 
                Margin = new Thickness(15, 0, 0, 0),
                Padding = new Thickness(10, 3, 10, 3),
                Background = new SolidColorBrush(Color.FromRgb(63, 63, 70)),
                Foreground = Brushes.White,
                BorderBrush = Brushes.Transparent
            };
            _toggleArmedBtn.Click += OnToggleArmedClick;
            statusPanel.Children.Add(_toggleArmedBtn);
            
            var reloadBtn = new Button 
            { 
                Content = "RELOAD CONFIG", 
                Margin = new Thickness(10, 0, 0, 0),
                Padding = new Thickness(10, 3, 10, 3),
                Background = new SolidColorBrush(Color.FromRgb(63, 63, 70)),
                Foreground = Brushes.White,
                BorderBrush = Brushes.Transparent
            };
            reloadBtn.Click += OnReloadConfigClick;
            statusPanel.Children.Add(reloadBtn);

            // Add Search Box
            statusPanel.Children.Add(new TextBlock { Text = "Filter:", Foreground = Brushes.LightGray, VerticalAlignment = VerticalAlignment.Center, Margin = new Thickness(20, 0, 5, 0) });
            _searchBox = new TextBox { Width = 90, Height = 22, VerticalAlignment = VerticalAlignment.Center, Background = new SolidColorBrush(Color.FromRgb(40, 40, 40)), Foreground = Brushes.White, BorderBrush = new SolidColorBrush(Color.FromRgb(63, 63, 70)) };
            statusPanel.Children.Add(_searchBox);

            // Add Hide Inactive Checkbox
            _hideInactiveCheck = new CheckBox { Content = "Hide Inactive ($0 Bal)", IsChecked = true, Foreground = Brushes.LightGray, Margin = new Thickness(15, 0, 0, 0), VerticalAlignment = VerticalAlignment.Center };
            statusPanel.Children.Add(_hideInactiveCheck);

            Grid.SetColumn(statusPanel, 0);
            topGrid.Children.Add(statusPanel);

            _panicAllBtn = new Button
            {
                Content = "- PANIC FLATTEN ALL ACCOUNTS",
                FontWeight = FontWeights.Bold,
                Background = new SolidColorBrush(Color.FromRgb(180, 40, 40)),
                Foreground = Brushes.White,
                Padding = new Thickness(15, 5, 15, 5),
                BorderBrush = Brushes.Transparent
            };
            _panicAllBtn.Click += OnPanicAllClick;
            Grid.SetColumn(_panicAllBtn, 2);
            topGrid.Children.Add(_panicAllBtn);

            Grid.SetRow(topBar, 0);
            mainGrid.Children.Add(topBar);

            // TABS CONTROL
            var tabControl = new TabControl 
            { 
                Background = new SolidColorBrush(Color.FromRgb(30, 30, 30)),
                BorderBrush = new SolidColorBrush(Color.FromRgb(45, 45, 48)),
                Margin = new Thickness(5)
            };

            // TAB 1: ACCOUNTS OVERVIEW
            var accountsTab = new TabItem 
            { 
                Header = "Accounts Overview",
                Background = new SolidColorBrush(Color.FromRgb(45, 45, 48)),
                Foreground = Brushes.White
            };
            var scrollViewer = new ScrollViewer { VerticalScrollBarVisibility = ScrollBarVisibility.Auto };
            _cardsPanel = new WrapPanel { ItemWidth = 220, ItemHeight = 200 };
            scrollViewer.Content = _cardsPanel;
            accountsTab.Content = scrollViewer;
            tabControl.Items.Add(accountsTab);

            // TAB 2: CONFIGURATION EDITOR
            var configTab = new TabItem 
            { 
                Header = "Risk & Settings Configuration",
                Background = new SolidColorBrush(Color.FromRgb(45, 45, 48)),
                Foreground = Brushes.White
            };
            
            var editorScroll = new ScrollViewer { VerticalScrollBarVisibility = ScrollBarVisibility.Auto };
            var border = new Border { Padding = new Thickness(20), Background = new SolidColorBrush(Color.FromRgb(35, 35, 35)) };
            var panel = new StackPanel();
            border.Child = panel;
            editorScroll.Content = border;

            panel.Children.Add(new TextBlock { Text = "Global Protection Settings", FontSize = 16, FontWeight = FontWeights.Bold, Foreground = Brushes.White, Margin = new Thickness(0, 0, 0, 15) });

            // Helper to add editable text row
            Func<string, string, TextBox, StackPanel> addEditRow = (label, tooltip, box) =>
            {
                var row = new StackPanel { Orientation = Orientation.Horizontal, Margin = new Thickness(0, 5, 0, 5) };
                row.Children.Add(new TextBlock { Text = label, Width = 220, Foreground = Brushes.LightGray, VerticalAlignment = VerticalAlignment.Center });
                box.Width = 100;
                box.Height = 22;
                box.Background = new SolidColorBrush(Color.FromRgb(45, 45, 45));
                box.Foreground = Brushes.White;
                box.BorderBrush = new SolidColorBrush(Color.FromRgb(65, 65, 65));
                row.Children.Add(box);
                row.Children.Add(new TextBlock { Text = tooltip, Foreground = Brushes.Gray, Margin = new Thickness(10, 0, 0, 0), VerticalAlignment = VerticalAlignment.Center, FontSize = 11 });
                return row;
            };

            // Mode Combo
            var modeRow = new StackPanel { Orientation = Orientation.Horizontal, Margin = new Thickness(0, 5, 0, 5) };
            modeRow.Children.Add(new TextBlock { Text = "Operational Mode:", Width = 220, Foreground = Brushes.LightGray, VerticalAlignment = VerticalAlignment.Center });
            _modeCombo = new ComboBox { Width = 100, Height = 22, Background = new SolidColorBrush(Color.FromRgb(45, 45, 45)), Foreground = Brushes.White };
            _modeCombo.Items.Add("shadow");
            _modeCombo.Items.Add("live");
            modeRow.Children.Add(_modeCombo);
            panel.Children.Add(modeRow);

            // WindowGate Checkbox
            var gateRow = new StackPanel { Orientation = Orientation.Horizontal, Margin = new Thickness(0, 5, 0, 5) };
            gateRow.Children.Add(new TextBlock { Text = "Restrict Outside Trading Hours:", Width = 220, Foreground = Brushes.LightGray, VerticalAlignment = VerticalAlignment.Center });
            _windowGateCheck = new CheckBox { VerticalAlignment = VerticalAlignment.Center };
            gateRow.Children.Add(_windowGateCheck);
            panel.Children.Add(gateRow);

            // Populate all fields
            _maxContractsAccountText = new TextBox();
            panel.Children.Add(addEditRow("Max Contracts Per Account:", "Max size in standard contracts per single account", _maxContractsAccountText));

            _maxContractsAggregateText = new TextBox();
            panel.Children.Add(addEditRow("Max Contracts Aggregate:", "Combined max size across all copy group accounts", _maxContractsAggregateText));

            _maxTradesSessionText = new TextBox();
            panel.Children.Add(addEditRow("Max Trades Per Session:", "Prevents overtrading after N executions", _maxTradesSessionText));

            _maxConsecutiveLossesText = new TextBox();
            panel.Children.Add(addEditRow("Max Consecutive Losses:", "Locks out account if N losses occur in a row", _maxConsecutiveLossesText));

            _cooldownMinutesText = new TextBox();
            panel.Children.Add(addEditRow("Cooldown Period (Mins):", "Cooldown duration after a consecutive loss lockout", _cooldownMinutesText));

            _lockoutMinutesText = new TextBox();
            panel.Children.Add(addEditRow("Lockout Duration (Mins):", "Duration for time-based rule lockouts (0 = lock rest of day)", _lockoutMinutesText));

            _dailyLossLimitText = new TextBox();
            panel.Children.Add(addEditRow("Daily Loss Limit ($):", "Hard daily drawdown limit per account", _dailyLossLimitText));

            _trailingDrawdownText = new TextBox();
            panel.Children.Add(addEditRow("Trailing Drawdown ($):", "Max allowable drawdown from peak session equity", _trailingDrawdownText));

            _pnlLockoutMinutesText = new TextBox();
            panel.Children.Add(addEditRow("PnL Lockout (Mins):", "Lockout duration after hitting Daily Loss / Trailing Drawdown", _pnlLockoutMinutesText));

            // OnMissing Combo
            var missingRow = new StackPanel { Orientation = Orientation.Horizontal, Margin = new Thickness(0, 5, 0, 5) };
            missingRow.Children.Add(new TextBlock { Text = "On Missing Bracket Order:", Width = 220, Foreground = Brushes.LightGray, VerticalAlignment = VerticalAlignment.Center });
            _onMissingCombo = new ComboBox { Width = 100, Height = 22, Background = new SolidColorBrush(Color.FromRgb(45, 45, 45)), Foreground = Brushes.White };
            _onMissingCombo.Items.Add("AutoStop");
            _onMissingCombo.Items.Add("Flatten");
            _onMissingCombo.Items.Add("WarnOnly");
            missingRow.Children.Add(_onMissingCombo);
            panel.Children.Add(missingRow);

            // StopGuard grace period
            _stopAttachSecondsText = new TextBox();
            panel.Children.Add(addEditRow("Stop Attach Grace (Sec):", "Grace period before auto-stop/flatten on missing bracket", _stopAttachSecondsText));

            // Expected copies (N-way mirror)
            _expectedCopiesText = new TextBox();
            panel.Children.Add(addEditRow("Expected Copies (Mirror N):", "Intended N-way mirror count (1 = no mirroring)", _expectedCopiesText));

            // Excluded accounts (global text editor)
            _excludedAccountsText = new TextBox();
            _excludedAccountsText.Width = 300;
            _excludedAccountsText.Height = 22;
            panel.Children.Add(addEditRow("Excluded Accounts (comma-sep):", "Accounts excluded from all rules (also toggle per-card)", _excludedAccountsText));

            // Firm Mirror section header
            panel.Children.Add(new TextBlock { Text = "Firm Mirror (Prop-Firm Rule Replication)", FontSize = 14, FontWeight = FontWeights.Bold, Foreground = Brushes.LightGray, Margin = new Thickness(0, 15, 0, 5) });

            // FirmMirror Enabled checkbox
            var firmRow = new StackPanel { Orientation = Orientation.Horizontal, Margin = new Thickness(0, 5, 0, 5) };
            firmRow.Children.Add(new TextBlock { Text = "Firm Mirror Enabled:", Width = 220, Foreground = Brushes.LightGray, VerticalAlignment = VerticalAlignment.Center });
            _firmMirrorEnabledCheck = new CheckBox { VerticalAlignment = VerticalAlignment.Center };
            firmRow.Children.Add(_firmMirrorEnabledCheck);
            panel.Children.Add(firmRow);

            _firmTrailingDDAmountText = new TextBox();
            panel.Children.Add(addEditRow("Firm Trailing DD ($):", "Prop-firm trailing drawdown limit (with buffer)", _firmTrailingDDAmountText));

            _firmDailyLossAmountText = new TextBox();
            panel.Children.Add(addEditRow("Firm Daily Loss ($):", "Prop-firm daily loss limit (with buffer)", _firmDailyLossAmountText));

            // SAVE CONFIG BUTTON
            var saveBtn = new Button
            {
                Content = "- SAVE AND APPLY CONFIGURATION",
                Width = 250,
                Height = 35,
                Margin = new Thickness(0, 20, 0, 0),
                HorizontalAlignment = HorizontalAlignment.Left,
                FontWeight = FontWeights.Bold,
                Background = new SolidColorBrush(Color.FromRgb(0, 122, 204)),
                Foreground = Brushes.White,
                BorderBrush = Brushes.Transparent
            };
            saveBtn.Click += OnSaveConfigClick;
            panel.Children.Add(saveBtn);

            configTab.Content = editorScroll;
            tabControl.Items.Add(configTab);

            // TAB 3: TRADE COPIER & GROUP MANAGER
            var copierTab = new TabItem
            {
                Header = "Trade Copier & Group Manager",
                Background = new SolidColorBrush(Color.FromRgb(45, 45, 48)),
                Foreground = Brushes.White
            };
            copierTab.Content = new TradeCopierControl();
            tabControl.Items.Add(copierTab);

            Grid.SetRow(tabControl, 1);
            mainGrid.Children.Add(tabControl);

            Content = mainGrid;

            // Load initial config values
            LoadConfigIntoUI();

            // Timer to refresh UI stats
            _uiTimer = new DispatcherTimer { Interval = TimeSpan.FromMilliseconds(500) };
            _uiTimer.Tick += (s, e) => UpdateUI();
            _uiTimer.Start();

            Closed += (s, e) => _uiTimer.Stop();

            UpdateUI();
        }

        private void LoadConfigIntoUI()
        {
            var cfg = _addOn.Config;
            if (cfg == null) return;

            _modeCombo.SelectedItem = cfg.Mode == "live" ? "live" : "shadow";
            _windowGateCheck.IsChecked = cfg.EnableWindowGate;
            _maxContractsAccountText.Text = cfg.Sizing.MaxContractsPerAccount.ToString();
            _maxContractsAggregateText.Text = cfg.Sizing.MaxContractsAggregate.ToString();
            _maxTradesSessionText.Text = cfg.Overtrading.MaxTradesPerSession.ToString();
            _maxConsecutiveLossesText.Text = cfg.Overtrading.MaxConsecutiveLosses.ToString();
            _cooldownMinutesText.Text = cfg.Overtrading.CooldownMinutes.ToString();
            _lockoutMinutesText.Text = cfg.Overtrading.LockoutMinutes.ToString();
            _dailyLossLimitText.Text = cfg.PnLRules.DailyLossLimit.ToString();
            _trailingDrawdownText.Text = cfg.PnLRules.TrailingDrawdown.ToString();
            _pnlLockoutMinutesText.Text = cfg.PnLRules.LockoutMinutes.ToString();

            // StopGuard
            var onMissing = string.IsNullOrEmpty(cfg.StopGuard.OnMissing) ? "Flatten" : cfg.StopGuard.OnMissing;
            // Normalise to one of the dropdown items
            var matched = false;
            foreach (var item in _onMissingCombo.Items) { if (string.Equals(item.ToString(), onMissing, StringComparison.OrdinalIgnoreCase)) { _onMissingCombo.SelectedItem = item; matched = true; break; } }
            if (!matched) _onMissingCombo.SelectedIndex = 1; // default Flatten

            _stopAttachSecondsText.Text = cfg.StopGuard.StopAttachSeconds.ToString();
            _expectedCopiesText.Text = cfg.Sizing.ExpectedCopies.ToString();
            _excludedAccountsText.Text = cfg.ExcludedAccounts != null ? string.Join(", ", cfg.ExcludedAccounts) : "";

            // FirmMirror
            _firmMirrorEnabledCheck.IsChecked = cfg.FirmMirror != null && cfg.FirmMirror.Enabled;
            _firmTrailingDDAmountText.Text = cfg.FirmMirror != null && cfg.FirmMirror.TrailingDD != null ? cfg.FirmMirror.TrailingDD.Amount.ToString() : "0";
            _firmDailyLossAmountText.Text = cfg.FirmMirror != null && cfg.FirmMirror.DailyLoss != null ? cfg.FirmMirror.DailyLoss.Amount.ToString() : "0";
        }

        private void OnSaveConfigClick(object sender, RoutedEventArgs e)
        {
            try
            {
                var cfg = _addOn.Config;
                cfg.Mode = _modeCombo.SelectedItem.ToString();
                cfg.EnableWindowGate = _windowGateCheck.IsChecked ?? false;
                cfg.Sizing.MaxContractsPerAccount = int.Parse(_maxContractsAccountText.Text.Trim());
                cfg.Sizing.MaxContractsAggregate = int.Parse(_maxContractsAggregateText.Text.Trim());
                cfg.Overtrading.MaxTradesPerSession = int.Parse(_maxTradesSessionText.Text.Trim());
                cfg.Overtrading.MaxConsecutiveLosses = int.Parse(_maxConsecutiveLossesText.Text.Trim());
                cfg.Overtrading.CooldownMinutes = int.Parse(_cooldownMinutesText.Text.Trim());
                cfg.Overtrading.LockoutMinutes = int.Parse(_lockoutMinutesText.Text.Trim());
                cfg.PnLRules.DailyLossLimit = double.Parse(_dailyLossLimitText.Text.Trim());
                cfg.PnLRules.TrailingDrawdown = double.Parse(_trailingDrawdownText.Text.Trim());
                cfg.PnLRules.LockoutMinutes = int.Parse(_pnlLockoutMinutesText.Text.Trim());
                cfg.StopGuard.OnMissing = _onMissingCombo.SelectedItem.ToString();
                cfg.StopGuard.StopAttachSeconds = int.Parse(_stopAttachSecondsText.Text.Trim());
                cfg.Sizing.ExpectedCopies = int.Parse(_expectedCopiesText.Text.Trim());

                // Excluded accounts from the text box (comma-separated)
                var exclText = _excludedAccountsText.Text.Trim();
                if (string.IsNullOrEmpty(exclText))
                    cfg.ExcludedAccounts = new List<string>();
                else
                    cfg.ExcludedAccounts = exclText.Split(new[] { ',' }, StringSplitOptions.RemoveEmptyEntries)
                                                   .Select(s => s.Trim())
                                                   .Where(s => !string.IsNullOrEmpty(s))
                                                   .ToList();

                // FirmMirror
                if (cfg.FirmMirror != null)
                {
                    cfg.FirmMirror.Enabled = _firmMirrorEnabledCheck.IsChecked ?? false;
                    if (cfg.FirmMirror.TrailingDD != null)
                        cfg.FirmMirror.TrailingDD.Amount = double.Parse(_firmTrailingDDAmountText.Text.Trim());
                    if (cfg.FirmMirror.DailyLoss != null)
                        cfg.FirmMirror.DailyLoss.Amount = double.Parse(_firmDailyLossAmountText.Text.Trim());
                }

                _addOn.SaveAndReloadConfig(cfg);
                MessageBox.Show("Configuration saved and hot-reloaded successfully!", "Success", MessageBoxButton.OK, MessageBoxImage.Information);
            }
            catch (Exception ex)
            {
                MessageBox.Show($"Failed to parse settings: {ex.Message}", "Error", MessageBoxButton.OK, MessageBoxImage.Error);
            }
        }

        private void UpdateUI()
        {
            bool isArmed = _addOn.IsArmed;
            string mode = _addOn.Config != null ? _addOn.Config.Mode : "shadow";
            _armedStatusText.Text = isArmed ? string.Format("ARMED ({0})", mode.ToUpper()) : "DISABLED";
            _armedStatusText.Foreground = isArmed ? Brushes.LimeGreen : Brushes.Red;

            var snapshots = _addOn.GetAccountSnapshots();
            var existingAccNames = _cardControls.Keys.ToList();

            string filterText = _searchBox != null ? _searchBox.Text.Trim() : "";
            bool hideInactive = _hideInactiveCheck != null && (_hideInactiveCheck.IsChecked ?? true);

            var filteredSnapshots = new List<RiskGuardAddOn.AccountStateSnapshot>();
            foreach (var snapshot in snapshots)
            {
                // Filter by name
                if (!string.IsNullOrEmpty(filterText) && snapshot.AccountName.IndexOf(filterText, StringComparison.OrdinalIgnoreCase) < 0)
                {
                    continue;
                }

                // Filter by inactive ($0 balance, flat, no trades)
                bool isZeroBal = snapshot.AccountEquity == 0 && snapshot.PositionString == "FLAT" && snapshot.TradesToday == 0;
                if (hideInactive && isZeroBal && snapshot.AccountName != "Sim101") // Keep Sim101 visible by default
                {
                    continue;
                }

                filteredSnapshots.Add(snapshot);
            }

            // Remove cards that are no longer in filtered snapshots
            var filteredNames = new HashSet<string>(filteredSnapshots.Select(s => s.AccountName));
            foreach (var accName in existingAccNames)
            {
                if (!filteredNames.Contains(accName))
                {
                    _cardsPanel.Children.Remove(_cardControls[accName].BorderEl);
                    _cardControls.Remove(accName);
                }
            }

            // Create cards for new filtered snapshots
            foreach (var snapshot in filteredSnapshots)
            {
                if (!_cardControls.ContainsKey(snapshot.AccountName))
                {
                    var card = CreateAccountCard(snapshot.AccountName);
                    _cardControls[snapshot.AccountName] = card;
                    _cardsPanel.Children.Add(card.BorderEl);
                }
            }

            // Update details of all visible cards
            foreach (var snapshot in filteredSnapshots)
            {
                if (_cardControls.TryGetValue(snapshot.AccountName, out var card))
                {
                    card.TitleText.Text = snapshot.AccountName;
                    card.PnlText.Text = string.Format("PnL Today: {0:C} (Realized: {1:C})", snapshot.RealizedPnL + snapshot.UnrealizedPnL, snapshot.RealizedPnL);
                    card.TradesText.Text = string.Format("Trades today: {0} / {1}", snapshot.TradesToday, _addOn.Config.Overtrading.MaxTradesPerSession);
                    card.LossesText.Text = string.Format("Consecutive Losses: {0} / {1}", snapshot.ConsecutiveLosses, _addOn.Config.Overtrading.MaxConsecutiveLosses);
                    card.PositionText.Text = string.Format("Position: {0}", snapshot.PositionString);

                    if (snapshot.IsLockedOut)
                    {
                        card.StatusText.Text = "Locked (EOD)";
                        card.StatusText.Foreground = Brushes.Red;
                        card.BorderEl.BorderBrush = Brushes.Red;
                    }
                    else if (DateTime.UtcNow < snapshot.LockoutUntil)
                    {
                        var remaining = snapshot.LockoutUntil - DateTime.UtcNow;
                        card.StatusText.Text = string.Format("Locked ({0}m)", (int)remaining.TotalMinutes);
                        card.StatusText.Foreground = Brushes.Red;
                        card.BorderEl.BorderBrush = Brushes.Red;
                    }
                    else
                    {
                        // Check if lockout phase is stuck (position open but flatten failing)
                        // We can't access CurrentLockoutPhase from the snapshot, so we check
                        // if the account is locked out AND has an open position AND is not excluded.
                        if ((snapshot.IsLockedOut || DateTime.UtcNow < snapshot.LockoutUntil) &&
                            snapshot.PositionString != "FLAT")
                        {
                            card.StatusText.Text = "LOCKED - STUCK!";
                            card.StatusText.Foreground = Brushes.Red;
                            card.BorderEl.BorderBrush = Brushes.Red;

                            // Show a one-time popup for the stuck lockout
                            if (!_lockoutStuckPopupShown.Contains(snapshot.AccountName))
                            {
                                _lockoutStuckPopupShown.Add(snapshot.AccountName);
                                Dispatcher.BeginInvoke(new Action(() =>
                                {
                                    MessageBox.Show(
                                        string.Format(
                                            "Account {0} is LOCKED OUT but the position ({1}) could not be closed automatically.\n\n" +
                                            "RiskGuard has been trying to flatten for over 30 seconds.\n" +
                                            "MANUAL INTERVENTION REQUIRED:\n" +
                                            "  1. Close the position from the NT8 Chart Trader or DOM\n" +
                                            "  2. Cancel any remaining working orders\n" +
                                            "  3. Click 'Unlock' on the RiskGuard dashboard for this account\n\n" +
                                            "This popup will not repeat for this account until unlocked.",
                                            snapshot.AccountName, snapshot.PositionString),
                                        "RiskGuard: Lockout Stuck - Manual Action Required",
                                        MessageBoxButton.OK, MessageBoxImage.Warning);
                                }));
                            }
                        }
                        else
                        {
                            card.StatusText.Text = "Active";
                            card.StatusText.Foreground = Brushes.LimeGreen;
                            card.BorderEl.BorderBrush = new SolidColorBrush(Color.FromRgb(0, 122, 204));
                        }
                    }

                    // Excluded checkbox state
                    card.ExcludeCheck.IsChecked = snapshot.IsExcluded;
                }
            }
        }

        private CardControls CreateAccountCard(string accountName)
        {
            var card = new CardControls();

            card.BorderEl = new Border
            {
                Background = new SolidColorBrush(Color.FromRgb(40, 40, 40)),
                BorderThickness = new Thickness(1),
                CornerRadius = new CornerRadius(5),
                Margin = new Thickness(5),
                Padding = new Thickness(10)
            };

            var panel = new StackPanel();

            // Header panel (Title + Status indicator)
            var header = new Grid();
            header.ColumnDefinitions.Add(new ColumnDefinition { Width = new GridLength(1, GridUnitType.Star) });
            header.ColumnDefinitions.Add(new ColumnDefinition { Width = GridLength.Auto });

            card.TitleText = new TextBlock { Text = accountName, FontWeight = FontWeights.Bold, Foreground = Brushes.White, FontSize = 12 };
            Grid.SetColumn(card.TitleText, 0);
            header.Children.Add(card.TitleText);

            card.StatusText = new TextBlock { Text = "Active", Foreground = Brushes.LimeGreen, FontSize = 10, VerticalAlignment = VerticalAlignment.Center };
            Grid.SetColumn(card.StatusText, 1);
            header.Children.Add(card.StatusText);

            panel.Children.Add(header);

            // Stats fields
            card.PnlText = new TextBlock { Foreground = Brushes.LightGray, Margin = new Thickness(0, 8, 0, 2) };
            panel.Children.Add(card.PnlText);

            card.TradesText = new TextBlock { Foreground = Brushes.LightGray, Margin = new Thickness(0, 2, 0, 2) };
            panel.Children.Add(card.TradesText);

            card.LossesText = new TextBlock { Foreground = Brushes.LightGray, Margin = new Thickness(0, 2, 0, 2) };
            panel.Children.Add(card.LossesText);

            card.PositionText = new TextBlock { Foreground = Brushes.LightGray, Margin = new Thickness(0, 2, 0, 8) };
            panel.Children.Add(card.PositionText);

            // Action row (Panic button, Unlock button)
            var btnRow = new Grid { Margin = new Thickness(0, 5, 0, 5) };
            btnRow.ColumnDefinitions.Add(new ColumnDefinition { Width = new GridLength(1, GridUnitType.Star) });
            btnRow.ColumnDefinitions.Add(new ColumnDefinition { Width = new GridLength(5) }); // space spacer
            btnRow.ColumnDefinitions.Add(new ColumnDefinition { Width = new GridLength(1, GridUnitType.Star) });

            var panicBtn = new Button 
            { 
                Content = "Panic", 
                Background = new SolidColorBrush(Color.FromRgb(180, 40, 40)), 
                Foreground = Brushes.White, 
                FontWeight = FontWeights.Bold,
                BorderBrush = Brushes.Transparent,
                Padding = new Thickness(0, 3, 0, 3)
            };
            panicBtn.Click += (s, e) => OnCardPanicClick(accountName);
            Grid.SetColumn(panicBtn, 0);
            btnRow.Children.Add(panicBtn);

            var unlockBtn = new Button 
            { 
                Content = "Unlock", 
                Background = new SolidColorBrush(Color.FromRgb(40, 130, 40)), 
                Foreground = Brushes.White, 
                FontWeight = FontWeights.Bold,
                BorderBrush = Brushes.Transparent,
                Padding = new Thickness(0, 3, 0, 3)
            };
            unlockBtn.Click += (s, e) => OnCardUnlockClick(accountName);
            Grid.SetColumn(unlockBtn, 2);
            btnRow.Children.Add(unlockBtn);

            panel.Children.Add(btnRow);

            var lockRow = new Grid { Margin = new Thickness(0, 5, 0, 5) };
            lockRow.ColumnDefinitions.Add(new ColumnDefinition { Width = new GridLength(2, GridUnitType.Star) });
            lockRow.ColumnDefinitions.Add(new ColumnDefinition { Width = new GridLength(5) });
            lockRow.ColumnDefinitions.Add(new ColumnDefinition { Width = new GridLength(1, GridUnitType.Star) });

            var lockComboBox = new ComboBox { Margin = new Thickness(0) };
            lockComboBox.Items.Add("15m");
            lockComboBox.Items.Add("30m");
            lockComboBox.Items.Add("1h");
            lockComboBox.Items.Add("EOD");
            lockComboBox.SelectedIndex = 0;
            Grid.SetColumn(lockComboBox, 0);
            lockRow.Children.Add(lockComboBox);

            var lockBtn = new Button 
            { 
                Content = "Lock", 
                Background = new SolidColorBrush(Color.FromRgb(130, 40, 130)), 
                Foreground = Brushes.White, 
                FontWeight = FontWeights.Bold,
                BorderBrush = Brushes.Transparent,
                Padding = new Thickness(0, 3, 0, 3)
            };
            lockBtn.Click += (s, e) => OnCardLockClick(accountName, lockComboBox.SelectedItem.ToString());
            Grid.SetColumn(lockBtn, 2);
            lockRow.Children.Add(lockBtn);

            panel.Children.Add(lockRow);

            // Excluded Checkbox
            card.ExcludeCheck = new CheckBox 
            { 
                Content = "Exclude from Risk Guard", 
                Foreground = Brushes.LightGray, 
                Margin = new Thickness(0, 5, 0, 0) 
            };
            card.ExcludeCheck.Checked += (s, e) => OnCardExcludeChecked(accountName, true);
            card.ExcludeCheck.Unchecked += (s, e) => OnCardExcludeChecked(accountName, false);
            panel.Children.Add(card.ExcludeCheck);

            card.BorderEl.Child = panel;
            return card;
        }

        private void OnCardPanicClick(string accountName)
        {
            var result = MessageBox.Show(string.Format("Are you sure you want to FLATTEN account {0} and cancel all working orders?", accountName), "Confirm Panic", MessageBoxButton.YesNo, MessageBoxImage.Warning);
            if (result == MessageBoxResult.Yes)
            {
                _addOn.TriggerManualFlatten(accountName);
            }
        }

        private void OnCardUnlockClick(string accountName)
        {
            _addOn.UnlockAccount(accountName);
            _lockoutStuckPopupShown.Remove(accountName); // allow popup to show again if re-locked
            MessageBox.Show(string.Format("Account {0} unlocked/reset successfully.", accountName), "Unlock Success", MessageBoxButton.OK, MessageBoxImage.Information);
        }

        private void OnCardLockClick(string accountName, string lockType)
        {
            int minutes = 0;
            switch(lockType)
            {
                case "15m": minutes = 15; break;
                case "30m": minutes = 30; break;
                case "1h": minutes = 60; break;
                case "EOD": minutes = -1; break;
                default: minutes = -1; break;
            }

            var result = MessageBox.Show(string.Format("Are you sure you want to LOCK account {0} for {1}? This will flatten open positions.", accountName, lockType), "Confirm Lock", MessageBoxButton.YesNo, MessageBoxImage.Warning);
            if (result == MessageBoxResult.Yes)
            {
                _addOn.LockAccount(accountName, minutes);
                MessageBox.Show(string.Format("Account {0} locked.", accountName), "Lock Success", MessageBoxButton.OK, MessageBoxImage.Information);
            }
        }

        private void OnCardExcludeChecked(string accountName, bool isExcluded)
        {
            lock (_addOn.StateLock)
            {
                var cfg = _addOn.Config;
                if (isExcluded)
                {
                    if (!cfg.ExcludedAccounts.Contains(accountName))
                    {
                        cfg.ExcludedAccounts.Add(accountName);
                    }
                }
                else
                {
                    cfg.ExcludedAccounts.Remove(accountName);
                }
                _addOn.SaveAndReloadConfig(cfg);
            }
        }

        private void OnToggleArmedClick(object sender, RoutedEventArgs e)
        {
            _addOn.ToggleArmed();
        }

        private void OnReloadConfigClick(object sender, RoutedEventArgs e)
        {
            _addOn.ReloadConfig();
            LoadConfigIntoUI();
            MessageBox.Show("Configuration successfully reloaded.", "Config Reloaded", MessageBoxButton.OK, MessageBoxImage.Information);
        }

        private void OnPanicAllClick(object sender, RoutedEventArgs e)
        {
            var result = MessageBox.Show("Are you sure you want to FLATTEN ALL connected accounts and cancel all working orders?", "Confirm Global Panic", MessageBoxButton.YesNo, MessageBoxImage.Warning);
            if (result == MessageBoxResult.Yes)
            {
                _addOn.TriggerManualFlattenAll();
            }
        }
    }

    public class CardControls
    {
        public Border BorderEl { get; set; }
        public TextBlock TitleText { get; set; }
        public TextBlock StatusText { get; set; }
        public TextBlock PnlText { get; set; }
        public TextBlock TradesText { get; set; }
        public TextBlock LossesText { get; set; }
        public TextBlock PositionText { get; set; }
        public CheckBox ExcludeCheck { get; set; }
    }
#endif
}
