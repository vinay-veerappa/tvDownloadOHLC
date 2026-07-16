using System;
using System.IO;
using System.Text;
using System.Threading;
using System.Collections.Generic;
using System.Linq;
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
                        AccountEquity = equity
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

        public static RiskGuardAddOn Instance { get; private set; }
        private Timer _safetyTimer;
        private readonly object _stateLock = new object();
        private bool _isArmed = true;
        private string _mode = "shadow"; // fail-safe default; overridden by config in LoadConfig()
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

                // Start 1-second safety sweep timer
                _safetyTimer = new Timer(OnSafetySweep, null, 1000, 1000);

                LogEvent("SYSTEM", "INITIALIZE", $"RiskGuard Add-On initialized in {_mode} mode. Event monitoring started.");
                NinjaTrader.Code.Output.Process($"[RiskGuard] RESOLVED MODE = {_mode} (armed={_isArmed})", PrintTo.OutputTab1);
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

        // ──────────────────────────────────────────────────────────────
        // DEV/TESTING API
        // ──────────────────────────────────────────────────────────────
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
#endif

        public void ResetStateForDev()
        {
            lock (_stateLock)
            {
                _accountStates.Clear();
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
        }

        private void UnsubscribeFromAccount(Account account)
        {
            if (account == null) return;
            if (!_subscribedAccounts.Contains(account.Name)) return;

            account.PositionUpdate -= OnPositionUpdate;
            account.OrderUpdate -= OnOrderUpdate;
            account.ExecutionUpdate -= OnExecutionUpdate;

            _subscribedAccounts.Remove(account.Name);
            LogEvent("SYSTEM", "UNSUBSCRIBE", $"Unsubscribed from account events for: {account.Name}");
        }

        // ──────────────────────────────────────────────────────────────
        // CONFIG & STATE PERSISTENCE
        // ──────────────────────────────────────────────────────────────

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
                            _isArmed = data.IsArmed;
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

        // ──────────────────────────────────────────────────────────────
#if !TESTING
        // WINDOW INTERCEPTION (UI INJECTION)
        // ──────────────────────────────────────────────────────────────

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

        // ──────────────────────────────────────────────────────────────
        // EVENT HANDLERS
        // ──────────────────────────────────────────────────────────────

        private void OnConnectionStatusUpdate(object sender, ConnectionStatusEventArgs e)
        {
            LogEvent("SYSTEM", "CONNECTION_CHANGE", $"Connection status: {e.Status}, Connection: {e.Connection?.Options?.Name}");
            
            // Re-check and subscribe to any new accounts that became available
            lock (_stateLock)
            {
                foreach (Account account in Account.All)
                {
                    SubscribeToAccount(account);
                }
            }
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
            List<GuardAction> actions = null;
            try
            {
                Account account = (Account)sender;
                string accountName = account.Name;
                string instrument = e.Position.Instrument.FullName;
                MarketPosition marketPosition = e.Position.MarketPosition;
                int quantity = e.Position.Quantity;
                double averagePrice = e.Position.AveragePrice;
                double unrealizedPnL = 0.0;
                try { unrealizedPnL = e.Position.GetUnrealizedProfitLoss(PerformanceUnit.Currency); } catch { }

                lock (_stateLock)
                {
                    if (!_accountStates.TryGetValue(accountName, out var state))
                    {
                        state = new AccountState(accountName);
                        state.SessionStartRealizedPnL = account.Get(AccountItem.RealizedProfitLoss, Currency.UsDollar);
                        state.LastRealizedPnL = state.SessionStartRealizedPnL;
                        _accountStates[accountName] = state;
                    }

                    bool changed = state.UpdatePosition(account, e.Position.Instrument, marketPosition, quantity, averagePrice, unrealizedPnL, _config);
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

                    actions = EvaluateRules(account, state);
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
                        if (stateModel.IsLockedOut || stateModel.ConsecutiveLosses >= _config.Overtrading.MaxConsecutiveLosses)
                        {
                            if (e.Order.OrderState == OrderState.Submitted || e.Order.OrderState == OrderState.Accepted || e.Order.OrderState == OrderState.Working)
                            {
                                if (e.Order.OrderType == OrderType.Limit || e.Order.OrderType == OrderType.StopMarket || e.Order.OrderType == OrderType.StopLimit || e.Order.OrderType == OrderType.Market)
                                {
                                    account.Cancel(new[] { e.Order });
                                    LogEvent(accountName, "ENTRY_CANCEL", $"Cancelled order {e.Order.Id} because account is locked out.");
                                }
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

                    LogEvent(accountName, "ORDER_UPDATE", new JObject
                    {
                        { "instrument", instrument },
                        { "orderId", orderId },
                        { "orderState", orderState },
                        { "orderType", orderType },
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
                var actionsToExecute = new List<GuardAction>();
                lock (_stateLock)
                {
                    // Write heartbeat every 5 seconds from UI thread to verify responsiveness
                    if (DateTime.UtcNow - _lastHeartbeatTime >= TimeSpan.FromSeconds(5))
                    {
                        _lastHeartbeatTime = DateTime.UtcNow;
                        try { File.WriteAllText(_heartbeatFile, DateTime.UtcNow.ToString("o")); } catch {}
                    }

                    // Flush logs asynchronously (Fix 11)
                    var logsToWrite = new List<string>();
                    while (_logQueue.TryDequeue(out string logLine))
                    {
                        logsToWrite.Add(logLine);
                    }
                    if (logsToWrite.Count > 0)
                    {
                        try { File.AppendAllLines(_logFile, logsToWrite, Encoding.UTF8); } catch {}
                    }

                    DateTime nowEt = TimeZoneInfo.ConvertTimeFromUtc(DateTime.UtcNow, _etZone);
                    DateTime currentSessionDate = nowEt.TimeOfDay >= new TimeSpan(18, 0, 0) ? nowEt.Date.AddDays(1) : nowEt.Date;

                    // Aggregate cross-account size (Fix 7 + item 4)
                    // Normalize by ExpectedCopies so an intended N-way mirror isn't read as stacking.
                    // Excluded accounts are intentionally invisible to the aggregate rule.
                    int totalAggregateContracts = 0;
                    int maxSingleAccountContracts = 0;
                    foreach (var accName in _subscribedAccounts)
                    {
                        // Skip excluded accounts — they must not inflate the aggregate count
                        if (_config.ExcludedAccounts != null && _config.ExcludedAccounts.Contains(accName)) continue;

                        if (_accountStates.TryGetValue(accName, out var st))
                        {
                            int accContracts = 0;
                            foreach (var pos in st.Positions.Values)
                            {
                                if (pos.MarketPosition != MarketPosition.Flat) accContracts += pos.Quantity;
                            }
                            totalAggregateContracts += accContracts;
                            if (accContracts > maxSingleAccountContracts) maxSingleAccountContracts = accContracts;
                        }
                    }

                    // If mirroring N copies, the "effective" exposure is roughly the per-account leg,
                    // not the raw sum. Compare the normalized figure against the aggregate limit.
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
                            // Excluded accounts must never be flattened by the aggregate rule
                            if (_config.ExcludedAccounts != null && _config.ExcludedAccounts.Contains(accName)) continue;

                            if (_accountStates.TryGetValue(accName, out var st))
                            {
                                bool hasPosition = st.Positions.Values.Any(p => p.MarketPosition != MarketPosition.Flat);
                                if (hasPosition)
                                {
                                    actionsToExecute.Add(new GuardAction
                                    {
                                        AccountName = accName,
                                        ActionType = GuardActionType.FlattenPosition,
                                        RuleId = "AGGREGATE_SIZE_BREACH"
                                    });
                                }
                            }
                        }
                    }


                    foreach (var accName in _subscribedAccounts)
                    {
                        if (_config.ExcludedAccounts != null && _config.ExcludedAccounts.Contains(accName)) continue;

                        var account = Account.All.FirstOrDefault(a => a.Name == accName);
                        if (account == null) continue;

                        if (!_accountStates.TryGetValue(accName, out var stateModel)) continue;
                        
                        if (stateModel.LastSessionDate != currentSessionDate)
                        {
                            stateModel.LastSessionDate = currentSessionDate;
                            stateModel.TradesToday = 0;
                            stateModel.ConsecutiveLosses = 0;
                            stateModel.PeakEquity = 0.0;
                            stateModel.IsLockedOut = false;
                            stateModel.InitialLockoutFlattened = false;
                            stateModel.SessionStartRealizedPnL = account.Get(AccountItem.RealizedProfitLoss, Currency.UsDollar);
                            stateModel.LastRealizedPnL = stateModel.SessionStartRealizedPnL;
                            stateModel.RealizedPnL = 0.0;
                            LogEvent(accName, "SESSION_RESET", $"Session reset for {currentSessionDate:yyyy-MM-dd}");
                            _stateDirty = true;
                        }
                        
                        double rawRealized = account.Get(AccountItem.RealizedProfitLoss, Currency.UsDollar);
                        double newRealizedPnL = rawRealized - stateModel.SessionStartRealizedPnL;
                        
                        // Real-time PnL change detection (Fix lag)
                        if (Math.Abs(newRealizedPnL - stateModel.RealizedPnL) > 0.001)
                        {
                            double tradePnL = newRealizedPnL - stateModel.RealizedPnL;
                            if (tradePnL < -0.01)
                            {
                                stateModel.ConsecutiveLosses++;
                            }
                            else if (tradePnL > 0.01)
                            {
                                stateModel.ConsecutiveLosses = 0;
                            }
                            
                            stateModel.LastRealizedPnL = rawRealized;
                            stateModel.RealizedPnL = newRealizedPnL;
                            
                            // Apply Cooldown if consecutive loss limit breached
                            if (stateModel.ConsecutiveLosses >= _config.Overtrading.MaxConsecutiveLosses && _config.Overtrading.CooldownMinutes > 0)
                            {
                                stateModel.CooldownUntil = DateTime.UtcNow.AddMinutes(_config.Overtrading.CooldownMinutes);
                            }
                            
                            _stateDirty = true;
                        }
                        
                        stateModel.UnrealizedPnL = account.Get(AccountItem.UnrealizedProfitLoss, Currency.UsDollar);
                        
                        foreach (var posPair in stateModel.Positions)
                        {
                            var nPos = account.Positions.FirstOrDefault(p => p.Instrument.FullName == posPair.Key);
                            if (nPos != null && nPos.MarketPosition != MarketPosition.Flat)
                            {
                                try { posPair.Value.UnrealizedPnL = nPos.GetUnrealizedProfitLoss(PerformanceUnit.Currency); } catch {}
                            }
                        }

                        if (stateModel.IsLockedOut)
                        {
                            if (!stateModel.InitialLockoutFlattened)
                            {
                                // Cancel first so orders don't re-open position after flatten
                                actionsToExecute.Add(new GuardAction
                                {
                                    AccountName = accName,
                                    ActionType = GuardActionType.CancelAllOrders,
                                    RuleId = "LOCKOUT_ENFORCEMENT"
                                });

                                actionsToExecute.Add(new GuardAction
                                {
                                    AccountName = accName,
                                    ActionType = GuardActionType.FlattenPosition,
                                    RuleId = "LOCKOUT_ENFORCEMENT"
                                });
                                
                                stateModel.InitialLockoutFlattened = true;
                            }
                            else
                            {
                                // Only flatten if new non-flat position appears
                                foreach (var posPair in stateModel.Positions)
                                {
                                    if (posPair.Value.MarketPosition != MarketPosition.Flat)
                                    {
                                        actionsToExecute.Add(new GuardAction
                                        {
                                            AccountName = accName,
                                            ActionType = GuardActionType.FlattenPosition,
                                            RuleId = "LOCKOUT_ENFORCEMENT"
                                        });
                                        break;
                                    }
                                }
                            }
                            continue;
                        }
                        else
                        {
                            stateModel.InitialLockoutFlattened = false;
                        }

                        var ruleActions = EvaluateRules(account, stateModel);
                        if (ruleActions != null)
                        {
                            actionsToExecute.AddRange(ruleActions);
                        }

                        // Firm-mirror evaluation (DIFF 1: wired in)
                        if (_config.FirmMirror != null && _config.FirmMirror.Enabled)
                        {
                            var firmActions = EvaluateFirmMirror(account, stateModel, nowEt);
                            if (firmActions != null)
                            {
                                actionsToExecute.AddRange(firmActions);
                            }
                        }
                    }

                    // Batched state save (item 1): write once per sweep if anything changed
                    if (_stateDirty)
                    {
                        SavePersistedState();
                        _stateDirty = false;
                    }
                }

                // Outside of _stateLock, execute actions
                foreach (var action in actionsToExecute)
                {
                    ProcessAction(action);
                }
            }
            catch (Exception ex)
            {
                LogEvent("SYSTEM", "ERROR", $"Error in ExecuteSafetySweep: {ex.Message}");
            }
        }

        // ──────────────────────────────────────────────────────────────
        // RULE ENGINE FRAMEWORK
        // ──────────────────────────────────────────────────────────────

        internal List<GuardAction> EvaluateRules(Account account, AccountState stateModel)
        {
            if (!_isArmed || (_config.ExcludedAccounts != null && _config.ExcludedAccounts.Contains(stateModel.AccountName)))
            {
                return new List<GuardAction>();
            }
            var actions = new List<GuardAction>();

            if (!_isArmed)
            {
                return actions;
            }

            // Rule 1: Max Size
            foreach (var posPair in stateModel.Positions)
            {
                var pos = posPair.Value;
                if (pos.MarketPosition != MarketPosition.Flat && pos.Quantity > _config.Sizing.MaxContractsPerAccount)
                {
                    actions.Add(new GuardAction
                    {
                        AccountName = stateModel.AccountName,
                        ActionType = GuardActionType.FlattenPosition,
                        Instrument = pos.Instrument,
                        InstrumentObj = pos.InstrumentObj,
                        Quantity = pos.Quantity,
                        RuleId = "MAX_SIZE_BREACH"
                    });
                }
            }

            // Fix 8: Overtrading Rules
            if (stateModel.TradesToday > _config.Overtrading.MaxTradesPerSession)
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

            // Rule 2: Daily Loss
            double currentPnL = stateModel.RealizedPnL + stateModel.UnrealizedPnL;
            if (currentPnL < -_config.PnLRules.DailyLossLimit)
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
                    _stateDirty = true;
                }
            }

            // Rule 3: Trailing Drawdown
            if (currentPnL > stateModel.PeakEquity)
            {
                stateModel.PeakEquity = currentPnL;
            }
            if (currentPnL < stateModel.PeakEquity - _config.PnLRules.TrailingDrawdown)
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
                    _stateDirty = true;
                }
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

            // Rule 5: Stop-Loss Guard (Auto-Attach)
            foreach (var posPair in stateModel.Positions)
            {
                var pos = posPair.Value;
                if (pos.MarketPosition != MarketPosition.Flat && pos.LastNonFlatTransition != DateTime.MinValue)
                {
                    double elapsed = (DateTime.UtcNow - pos.LastNonFlatTransition).TotalSeconds;
                    if (elapsed > _config.StopGuard.StopAttachSeconds)
                    {
                        int stopQty = GetWorkingStopQuantity(account, pos.Instrument, pos.MarketPosition);
                        if (stopQty < pos.Quantity)
                        {
                            if (_config.StopGuard.OnMissing == "AutoStop")
                            {
                                actions.Add(new GuardAction
                                {
                                    AccountName = stateModel.AccountName,
                                    ActionType = GuardActionType.PlaceStopOrder,
                                    Instrument = pos.Instrument,
                                    InstrumentObj = pos.InstrumentObj,
                                    Quantity = pos.Quantity - stopQty,
                                    RuleId = "MISSING_STOP_ATTACH"
                                });
                            }
                            else if (_config.StopGuard.OnMissing == "Flatten")
                            {
                                actions.Add(new GuardAction
                                {
                                    AccountName = stateModel.AccountName,
                                    ActionType = GuardActionType.FlattenPosition,
                                    Instrument = pos.Instrument,
                                    InstrumentObj = pos.InstrumentObj,
                                    Quantity = pos.Quantity, // Flatten whole position if rule trips
                                    RuleId = "MISSING_STOP_FLATTEN"
                                });
                            }
                            else if (_config.StopGuard.OnMissing == "WarnOnly")
                            {
                                LogEvent(stateModel.AccountName, "MISSING_STOP_WARN", $"Missing stop for {pos.Instrument}, action set to WarnOnly.");
                            }
                        }
                    }
                }
            }

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

        private int GetWorkingStopQuantity(Account account, string instrumentFullName, MarketPosition marketPosition)
        {
            int stopQty = 0;
            foreach (Order o in account.Orders)
            {
                if (o.Instrument.FullName == instrumentFullName &&
                    (o.OrderState == OrderState.Working || o.OrderState == OrderState.Submitted || o.OrderState == OrderState.Accepted))
                {
                    if (o.OrderType == OrderType.StopMarket || o.OrderType == OrderType.StopLimit || o.OrderType == OrderType.Market)
                    {
                        bool isOpposite = (marketPosition == MarketPosition.Long && o.OrderAction == OrderAction.Sell) ||
                                          (marketPosition == MarketPosition.Short && o.OrderAction == OrderAction.Buy);
                        if (isOpposite)
                        {
                            stopQty += o.Quantity;
                        }
                    }
                }
            }
            return stopQty;
        }

        // ──────────────────────────────────────────────────────────────
        // ACTION ARBITER & EXECUTOR
        // ──────────────────────────────────────────────────────────────

        public string GetMode()
        {
            return _mode;
        }

        public bool IsArmed
        {
            get { return _isArmed; }
        }

        public void ToggleArmed()
        {
            lock (_stateLock)
            {
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

        public void UnlockAccount(string accountName)
        {
            lock (_stateLock)
            {
                if (_accountStates.TryGetValue(accountName, out var state))
                {
                    var account = Account.All.FirstOrDefault(a => a.Name == accountName);
                    double currentRealized = account != null ? account.Get(AccountItem.RealizedProfitLoss, Currency.UsDollar) : 0.0;

                    state.IsLockedOut = false;
                    state.PeakEquity = 0.0;
                    state.TradesToday = 0;
                    state.ConsecutiveLosses = 0;
                    state.CooldownUntil = DateTime.MinValue;
                    state.SessionStartRealizedPnL = currentRealized;
                    state.LastRealizedPnL = currentRealized;
                    state.RealizedPnL = 0.0;
                    state.UnrealizedPnL = 0.0;
                    state.InitialLockoutFlattened = false;

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
                // Placing stop order is risk-reducing only if we have an unprotected position covering it.
                return action.InstrumentObj != null && action.Quantity > 0;
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
                    account.Flatten(instrumentsToFlatten.ToArray());
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
                var position = account.Positions.FirstOrDefault(p => p.Instrument.FullName == action.Instrument);
                if (position == null || position.MarketPosition == MarketPosition.Flat) return;

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
                    LogEvent(account.Name, "STOP_SIDE_FLATTEN", $"Market price unavailable for {instrument.FullName}. Flattening.");
                    account.Flatten(new[] { instrument });
                    return;
                }

                if (position.MarketPosition == MarketPosition.Long)
                {
                    stopPrice = position.AveragePrice - (offsetTicks * tickSize);
                    orderAction = OrderAction.Sell;
                    
                    if (stopPrice >= currentPrice)
                    {
                        LogEvent(account.Name, "STOP_SIDE_FLATTEN", $"Long stop {stopPrice} >= current price {currentPrice}. Flattening.");
                        account.Flatten(new[] { instrument });
                        return;
                    }
                }
                else if (position.MarketPosition == MarketPosition.Short)
                {
                    stopPrice = position.AveragePrice + (offsetTicks * tickSize);
                    orderAction = OrderAction.Buy;

                    if (stopPrice <= currentPrice)
                    {
                        LogEvent(account.Name, "STOP_SIDE_FLATTEN", $"Short stop {stopPrice} <= current price {currentPrice}. Flattening.");
                        account.Flatten(new[] { instrument });
                        return;
                    }
                }

                stopPrice = instrument.MasterInstrument.RoundToTickSize(stopPrice);

                Order stopOrder = account.CreateOrder(
                    instrument,
                    orderAction,
                    OrderType.StopMarket,
                    TimeInForce.Day,
                    action.Quantity,
                    0,
                    stopPrice,
                    string.Empty,
                    "RiskGuardAutoStop",
                    null
                );

                if (stopOrder != null)
                {
                    account.Submit(new[] { stopOrder });
                }
            }
        }

        // ──────────────────────────────────────────────────────────────
        // HELPER METHODS FOR UI & LOGGING
        // ──────────────────────────────────────────────────────────────

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

        // ── Firm-mirror logic and unit test diagnostics (FR-24/25/26) ──
        internal List<GuardAction> EvaluateFirmMirror(Account account, AccountState st, DateTime nowEt)
        {
            double balance = account.Get(AccountItem.CashValue, Currency.UsDollar);
            double realized = account.Get(AccountItem.RealizedProfitLoss, Currency.UsDollar);
            double unrealized = account.Get(AccountItem.UnrealizedProfitLoss, Currency.UsDollar);

            var res = ComputeFirmMirror(balance, realized, unrealized, _config.FirmMirror, st, DateTime.UtcNow);
            
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
        public bool IsLockedOut { get; set; } = false;
        public bool InitialLockoutFlattened { get; set; } = false;
        
        // Session and Overtrading
        public DateTime LastSessionDate { get; set; } = DateTime.MinValue;
        public int TradesToday { get; set; } = 0;
        public int ConsecutiveLosses { get; set; } = 0;
        public DateTime CooldownUntil { get; set; } = DateTime.MinValue;
        public double LastRealizedPnL { get; set; } = 0.0; // To track delta for consec losses
        public double SessionStartRealizedPnL { get; set; } = 0.0; // Baseline for session PnL

        // ── Firm-mirror tracking (independent of discretionary PeakEquity) ──
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
                // We no longer calculate realized PnL delta here to prevent lag bugs.
                // It is now tracked in OnSafetySweep based on actual account realized PnL changes.
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
                TradesToday++; // Increment trade count
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

        public PositionState(Instrument instrument)
        {
            InstrumentObj = instrument;
            Instrument = instrument.FullName;
        }
    }

    public class PersistedStateData
    {
        public bool IsArmed { get; set; }
        public string Mode { get; set; }
        public List<string> LockedOutAccounts { get; set; } = new List<string>();
        
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

    // ──────────────────────────────────────────────────────────────
    // CONFIGURATION MODELS
    // ──────────────────────────────────────────────────────────────

    public class RiskConfig
    {
        public List<string> ExcludedAccounts { get; set; } = new List<string>();
        public string Mode { get; set; } = "shadow";
        public bool EnableWindowGate { get; set; } = false;
        public SizingConfig Sizing { get; set; } = new SizingConfig();
        public OvertradingConfig Overtrading { get; set; } = new OvertradingConfig();
        public StopGuardConfig StopGuard { get; set; } = new StopGuardConfig();
        public PnLRulesConfig PnLRules { get; set; } = new PnLRulesConfig();
        public FirmMirrorConfig FirmMirror { get; set; } = new FirmMirrorConfig();
        public List<WindowConfig> WindowsET { get; set; } = new List<WindowConfig>
        {
            new WindowConfig { Name = "NY_AM_Macro", Start = "09:50", End = "11:10" },
            new WindowConfig { Name = "NY_PM_Macro", Start = "13:50", End = "15:10" }
        };
    }

    public class FirmMirrorConfig
    {
        public bool Enabled { get; set; } = false;
        public FirmTrailingDDConfig TrailingDD { get; set; } = new FirmTrailingDDConfig();
        public FirmDailyLossConfig DailyLoss { get; set; } = new FirmDailyLossConfig();
        public int DailyResetHourUtc { get; set; } = 22;
        public int DailyResetMinuteUtc { get; set; } = 0;
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
        public int PnLLockoutMinutes { get; set; } = 60;
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

    // ──────────────────────────────────────────────────────────────
    // WPF UI DASHBOARD
    // ──────────────────────────────────────────────────────────────

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

        // Search and Filter fields
        private TextBox _searchBox;
        private CheckBox _hideInactiveCheck;

        public RiskGuardWindow(RiskGuardAddOn addOn)
        {
            _addOn = addOn;
            Title = "NinjaTrader Cross-Account Risk Guard Dashboard";
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
            statusPanel.Children.Add(new TextBlock { Text = "🛡️ RISK GUARD: ", Foreground = Brushes.White, FontSize = 14, FontWeight = FontWeights.Bold, VerticalAlignment = VerticalAlignment.Center });
            
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
                Content = "🛑 PANIC FLATTEN ALL ACCOUNTS",
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
            _onMissingCombo.Items.Add("flatten");
            _onMissingCombo.Items.Add("ignore");
            missingRow.Children.Add(_onMissingCombo);
            panel.Children.Add(missingRow);

            // SAVE CONFIG BUTTON
            var saveBtn = new Button
            {
                Content = "💾 SAVE AND APPLY CONFIGURATION",
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
            _pnlLockoutMinutesText.Text = cfg.PnLRules.PnLLockoutMinutes.ToString();
            _onMissingCombo.SelectedItem = cfg.StopGuard.OnMissing == "ignore" ? "ignore" : "flatten";
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
                cfg.PnLRules.PnLLockoutMinutes = int.Parse(_pnlLockoutMinutesText.Text.Trim());
                cfg.StopGuard.OnMissing = _onMissingCombo.SelectedItem.ToString();

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
                        card.StatusText.Text = "Locked Out";
                        card.StatusText.Foreground = Brushes.Red;
                        card.BorderEl.BorderBrush = Brushes.Red;
                    }
                    else
                    {
                        card.StatusText.Text = "Active";
                        card.StatusText.Foreground = Brushes.LimeGreen;
                        card.BorderEl.BorderBrush = new SolidColorBrush(Color.FromRgb(0, 122, 204));
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
            MessageBox.Show(string.Format("Account {0} unlocked/reset successfully.", accountName), "Unlock Success", MessageBoxButton.OK, MessageBoxImage.Information);
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