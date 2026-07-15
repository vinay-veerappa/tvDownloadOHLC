using System;
using System.IO;
using System.Text;
using System.Threading;
using System.Collections.Generic;
using System.Linq;
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

namespace NinjaTrader.NinjaScript.AddOns
{
    public class RiskGuardAddOn : AddOnBase
    {
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
        private NTMenuItem _myMenuItem;
        private ControlCenter _controlCenter;
        private RiskConfig _config = new RiskConfig();

        // Cached Resources (Fix 12)
        private TimeZoneInfo _etZone;
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
                            SessionStartRealizedPnL = state.SessionStartRealizedPnL
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

        private void OnPositionUpdate(object sender, PositionEventArgs e)
        {
            var dispatcher = Application.Current?.Dispatcher;
            if (dispatcher == null) return;

            dispatcher.InvokeAsync(() =>
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
            });
        }

        private void OnExecutionUpdate(object sender, ExecutionEventArgs e)
        {
            var dispatcher = Application.Current?.Dispatcher;
            if (dispatcher == null) return;

            dispatcher.InvokeAsync(() =>
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
            });
        }

        private void OnOrderUpdate(object sender, OrderEventArgs e)
        {
            var dispatcher = Application.Current?.Dispatcher;
            if (dispatcher == null) return;

            dispatcher.InvokeAsync(() =>
            {
                lock (_stateLock)
                {
                    try
                    {
                        Account account = (Account)sender;
                        string accountName = account.Name;
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
            });
        }

        private void OnSafetySweep(object state)
        {
            // 1-second safety sweep for time-based rules
            try
            {
                var dispatcher = Application.Current?.Dispatcher;
                if (dispatcher == null) return;

                dispatcher.InvokeAsync(() =>
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
                        int totalAggregateContracts = 0;
                        int maxSingleAccountContracts = 0;
                        foreach (var accName in _subscribedAccounts)
                        {
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
                                LogEvent(accName, "SESSION_RESET", $"Session reset for {currentSessionDate:yyyy-MM-dd}");
                                _stateDirty = true;
                            }
                            
                            double rawRealized = account.Get(AccountItem.RealizedProfitLoss, Currency.UsDollar);
                            stateModel.RealizedPnL = rawRealized - stateModel.SessionStartRealizedPnL; // Fix 10: Per-session basis
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
                                    actionsToExecute.Add(new GuardAction
                                    {
                                        AccountName = accName,
                                        ActionType = GuardActionType.FlattenPosition,
                                        RuleId = "LOCKOUT_ENFORCEMENT"
                                    });
                                    
                                    actionsToExecute.Add(new GuardAction
                                    {
                                        AccountName = accName,
                                        ActionType = GuardActionType.CancelAllOrders,
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
                });
            }
            catch (Exception ex)
            {
                LogEvent("SYSTEM", "ERROR", $"Error in OnSafetySweep: {ex.Message}");
            }
        }

        // ──────────────────────────────────────────────────────────────
        // RULE ENGINE FRAMEWORK
        // ──────────────────────────────────────────────────────────────

        private List<GuardAction> EvaluateRules(Account account, AccountState stateModel)
        {
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
                    if (o.OrderType == OrderType.StopMarket || o.OrderType == OrderType.StopLimit)
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
                    state.IsLockedOut = false;
                    state.PeakEquity = 0.0; // Reset high water mark
                    LogEvent(accountName, "UNLOCK", "Account manually unlocked from dashboard.");
                    SavePersistedState();
                }
            }
        }

        private string ProcessAction(GuardAction action, bool forceLive = false)
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
                // --- CLOSE side: finalize the trade that just ended ---
                if (config.Overtrading.CooldownMinutes > 0)
                {
                    CooldownUntil = DateTime.UtcNow.AddMinutes(config.Overtrading.CooldownMinutes);
                }

                double rawRealized = account.Get(AccountItem.RealizedProfitLoss, Currency.UsDollar);
                double tradePnL = rawRealized - LastRealizedPnL;

                if (tradePnL < -0.01)
                {
                    ConsecutiveLosses++;
                }
                else if (tradePnL > 0.01)
                {
                    ConsecutiveLosses = 0;
                }
                LastRealizedPnL = rawRealized;
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
    }

    // ──────────────────────────────────────────────────────────────
    // CONFIGURATION MODELS
    // ──────────────────────────────────────────────────────────────

    public class RiskConfig
    {
        public string Mode { get; set; } = "shadow";
        public bool EnableWindowGate { get; set; } = false;
        public SizingConfig Sizing { get; set; } = new SizingConfig();
        public OvertradingConfig Overtrading { get; set; } = new OvertradingConfig();
        public StopGuardConfig StopGuard { get; set; } = new StopGuardConfig();
        public PnLRulesConfig PnLRules { get; set; } = new PnLRulesConfig();
        public List<WindowConfig> WindowsET { get; set; } = new List<WindowConfig>
        {
            new WindowConfig { Name = "NY_AM_Macro", Start = "09:50", End = "11:10" },
            new WindowConfig { Name = "NY_PM_Macro", Start = "13:50", End = "15:10" }
        };
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

    public class RiskGuardWindow : Window
    {
        private readonly RiskGuardAddOn _addOn;
        private ComboBox _accountCombo;
        private TextBlock _statusText;
        private DispatcherTimer _uiTimer;

        public RiskGuardWindow(RiskGuardAddOn addOn)
        {
            _addOn = addOn;
            Title = "NinjaTrader Cross-Account Risk Guard Dashboard";
            Width = 450;
            Height = 420;
            Background = Brushes.Gray;
            WindowStartupLocation = WindowStartupLocation.CenterScreen;

            var grid = new Grid { Margin = new Thickness(15) };
            
            grid.RowDefinitions.Add(new RowDefinition { Height = new GridLength(45) });
            grid.RowDefinitions.Add(new RowDefinition { Height = new GridLength(45) });
            grid.RowDefinitions.Add(new RowDefinition { Height = new GridLength(45) });
            grid.RowDefinitions.Add(new RowDefinition { Height = new GridLength(1, GridUnitType.Star) });

            // Row 0: Account selection
            var accountPanel = new StackPanel { Orientation = Orientation.Horizontal, VerticalAlignment = VerticalAlignment.Center };
            accountPanel.Children.Add(new TextBlock { 
                Text = "Target Account:", 
                FontWeight = FontWeights.Bold,
                VerticalAlignment = VerticalAlignment.Center,
                Foreground = Brushes.Black
            });
            
            _accountCombo = new ComboBox { Width = 220, Height = 25, Margin = new Thickness(10, 0, 0, 0) };
            foreach (Account acc in Account.All)
            {
                _accountCombo.Items.Add(acc.Name);
            }
            if (_accountCombo.Items.Count > 0)
            {
                _accountCombo.SelectedIndex = 0;
            }
            accountPanel.Children.Add(_accountCombo);
            Grid.SetRow(accountPanel, 0);
            grid.Children.Add(accountPanel);

            // Row 1: Panic Flatten Button
            var panicBtn = new Button
            {
                Content = "PANIC FLATTEN ACCOUNT (CANCEL ORDERS + FLAT POSITION)",
                Background = Brushes.DarkRed,
                Foreground = Brushes.White,
                FontWeight = FontWeights.Bold,
                Height = 30,
                Margin = new Thickness(0, 5, 0, 5)
            };
            panicBtn.Click += OnPanicClick;
            Grid.SetRow(panicBtn, 1);
            grid.Children.Add(panicBtn);

            // Row 2: Panic All / Unlock Buttons
            var btnPanel = new Grid();
            btnPanel.ColumnDefinitions.Add(new ColumnDefinition { Width = new GridLength(1, GridUnitType.Star) });
            btnPanel.ColumnDefinitions.Add(new ColumnDefinition { Width = new GridLength(1, GridUnitType.Star) });
            btnPanel.ColumnDefinitions.Add(new ColumnDefinition { Width = new GridLength(1, GridUnitType.Star) });

            var panicAllBtn = new Button
            {
                Content = "PANIC FLATTEN ALL",
                Background = Brushes.Red,
                Foreground = Brushes.White,
                FontWeight = FontWeights.Bold,
                Height = 30,
                Margin = new Thickness(0, 5, 5, 5)
            };
            panicAllBtn.Click += OnPanicAllClick;
            Grid.SetColumn(panicAllBtn, 0);
            btnPanel.Children.Add(panicAllBtn);

            var toggleBtn = new Button
            {
                Content = "TOGGLE ARMED",
                Background = Brushes.DarkOrange,
                Foreground = Brushes.White,
                FontWeight = FontWeights.Bold,
                Height = 30,
                Margin = new Thickness(5, 5, 5, 5)
            };
            toggleBtn.Click += OnToggleArmedClick;
            Grid.SetColumn(toggleBtn, 1);
            btnPanel.Children.Add(toggleBtn);

            var unlockBtn = new Button
            {
                Content = "UNLOCK ACCOUNT",
                Background = Brushes.DarkGreen,
                Foreground = Brushes.White,
                FontWeight = FontWeights.Bold,
                Height = 30,
                Margin = new Thickness(5, 5, 0, 5)
            };
            unlockBtn.Click += OnUnlockClick;
            Grid.SetColumn(unlockBtn, 2);
            btnPanel.Children.Add(unlockBtn);

            Grid.SetRow(btnPanel, 2);
            grid.Children.Add(btnPanel);

            // Row 3: Status info
            var border = new Border
            {
                BorderBrush = Brushes.DarkGray,
                BorderThickness = new Thickness(1),
                Background = Brushes.White,
                CornerRadius = new CornerRadius(3),
                Margin = new Thickness(0, 10, 0, 0)
            };
            
            _statusText = new TextBlock
            {
                Text = "Loading status data...",
                TextWrapping = TextWrapping.Wrap,
                Margin = new Thickness(10),
                Foreground = Brushes.DarkSlateGray,
                FontFamily = new FontFamily("Consolas"),
                FontSize = 12
            };
            border.Child = new ScrollViewer { Content = _statusText, VerticalScrollBarVisibility = ScrollBarVisibility.Auto };
            Grid.SetRow(border, 3);
            grid.Children.Add(border);

            Content = grid;

            // Start UI Refresh timer
            _uiTimer = new DispatcherTimer();
            _uiTimer.Interval = TimeSpan.FromMilliseconds(500);
            _uiTimer.Tick += (s, e) => UpdateUI();
            _uiTimer.Start();

            Closed += (s, e) => _uiTimer.Stop();
        }

        private void UpdateUI()
        {
            var selectedAccName = _accountCombo.SelectedItem as string;
            if (string.IsNullOrEmpty(selectedAccName)) return;

            string status = _addOn.GetAccountStatusString(selectedAccName);
            _statusText.Text = status;
        }

        private void OnPanicClick(object sender, RoutedEventArgs e)
        {
            var selectedAccName = _accountCombo.SelectedItem as string;
            if (string.IsNullOrEmpty(selectedAccName))
            {
                MessageBox.Show(this, "Please select a target account first.", "Risk Guard Error", MessageBoxButton.OK, MessageBoxImage.Error);
                return;
            }

            var confirmResult = MessageBox.Show(
                this,
                $"Are you sure you want to FLATTEN account {selectedAccName} and CANCEL all its working orders?",
                "Confirm Panic Action",
                MessageBoxButton.YesNo,
                MessageBoxImage.Warning);

            if (confirmResult == MessageBoxResult.Yes)
            {
                _addOn.TriggerManualFlatten(selectedAccName);
            }
        }

        private void OnPanicAllClick(object sender, RoutedEventArgs e)
        {
            var confirmResult = MessageBox.Show(
                this,
                "Are you sure you want to FLATTEN ALL connected accounts and CANCEL all working orders?",
                "Confirm Panic All Action",
                MessageBoxButton.YesNo,
                MessageBoxImage.Warning);

            if (confirmResult == MessageBoxResult.Yes)
            {
                _addOn.TriggerManualFlattenAll();
            }
        }

        private void OnUnlockClick(object sender, RoutedEventArgs e)
        {
            var selectedAccName = _accountCombo.SelectedItem as string;
            if (string.IsNullOrEmpty(selectedAccName)) return;

            var confirmResult = MessageBox.Show(
                this,
                $"Are you sure you want to UNLOCK account {selectedAccName} and reset its drawdown peak?",
                "Confirm Unlock Action",
                MessageBoxButton.YesNo,
                MessageBoxImage.Question);

            if (confirmResult == MessageBoxResult.Yes)
            {
                _addOn.UnlockAccount(selectedAccName);
            }
        }

        private void OnToggleArmedClick(object sender, RoutedEventArgs e)
        {
            var confirmResult = MessageBox.Show(
                this,
                $"Are you sure you want to toggle the ARMED state of the Risk Guard?",
                "Confirm Toggle",
                MessageBoxButton.YesNo,
                MessageBoxImage.Question);

            if (confirmResult == MessageBoxResult.Yes)
            {
                _addOn.ToggleArmed();
            }
        }
    }
}
