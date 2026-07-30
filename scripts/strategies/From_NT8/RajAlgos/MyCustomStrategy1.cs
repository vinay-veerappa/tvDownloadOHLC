#region Using declarations
using System;
using System.Collections.Generic;
using System.ComponentModel;
using System.ComponentModel.DataAnnotations;
using System.Linq;
using System.Windows;
using System.Windows.Automation;
using System.Windows.Controls;
using System.Windows.Media;
using System.Xml.Serialization;
using NinjaTrader.Cbi;
using NinjaTrader.Gui;
using NinjaTrader.Gui.Chart;
using NinjaTrader.Data;
using NinjaTrader.NinjaScript;
using NinjaTrader.NinjaScript.DrawingTools;
#endregion

namespace NinjaTrader.NinjaScript.Indicators
{
    public class SimpleTradeCopierV2 : Indicator
    {
        #region Private Variables
        
        // ChartTrader WPF elements
        private Chart chartWindow;
        private ChartTrader chartTrader;
        private Grid chartTraderGrid;
        private Grid chartTraderButtonsGrid;
        private bool panelActive;
        private ChartTab chartTab;
        private TabItem tabItem;
        
        // Custom UI elements for ChartTrader panel
        private Grid copierButtonsGrid;
        private RowDefinition copierAddedRow;
        private Button copyButton;
        private TextBlock statusText;
        
        private bool isCopyEnabled = false;
        
        private Account masterAccount = null;
        private List<Account> followerAccounts = new List<Account>();
        
        private Position masterPosition = null;
        
        // Statistics tracking
        private int totalOrdersCopied = 0;
        private int successfulOrders = 0;
        private int failedOrders = 0;
        private DateTime? lastCopyTime = null;
        
        // Prevent duplicate order processing
        private HashSet<string> processedOrderIds = new HashSet<string>();
        private object lockObject = new object();
        
        #endregion

        protected override void OnStateChange()
        {
            if (State == State.SetDefaults)
            {
                Description = @"Advanced Trade Copier - Copies trades from a master account to up to 20 follower accounts. Buttons appear in ChartTrader panel.";
                Name = "Simple Trade Copier V2";
                Calculate = Calculate.OnBarClose;
                IsOverlay = true;
                DisplayInDataBox = false;
                DrawOnPricePanel = false;
                DrawHorizontalGridLines = false;
                DrawVerticalGridLines = false;
                PaintPriceMarkers = false;
                ScaleJustification = ScaleJustification.Right;
                IsSuspendedWhileInactive = false;
                
                // Default values
                CopyAllInstruments = true;
                UseQuantityMultiplier = false;
                QuantityMultiplier = 1.0;
                MaxQuantityPerAccount = 100;
                ShowStatistics = true;
                LogToOutput = true;
            }
            else if (State == State.Configure)
            {
                isCopyEnabled = false;
                ClearData();
            }
            else if (State == State.DataLoaded)
            {
                InitializeAccounts();
            }
            else if (State == State.Historical)
            {
                // Initialize ChartTrader panel buttons
                if (ChartControl != null)
                {
                    ChartControl.Dispatcher.InvokeAsync(() =>
                    {
                        CreateWPFControls();
                    });
                }
            }
            else if (State == State.Terminated)
            {
                if (ChartControl != null)
                {
                    ChartControl.Dispatcher.InvokeAsync(() =>
                    {
                        DisposeWPFControls();
                    });
                }
                CleanupResources();
            }
        }

        #region WPF Controls for ChartTrader Panel
        
        private void CreateWPFControls()
        {
            // Get the chart window
            chartWindow = Window.GetWindow(ChartControl.Parent) as Chart;
            if (chartWindow == null) return;
            
            // Find the ChartTrader control using FindFirst with automation ID
            chartTrader = chartWindow.FindFirst("ChartWindowChartTraderControl") as ChartTrader;
            if (chartTrader == null) return;
            
            // Get the main grid of ChartTrader
            chartTraderGrid = chartTrader.Content as Grid;
            if (chartTraderGrid == null) return;
            
            // Get the buttons grid (first child of chartTraderGrid)
            if (chartTraderGrid.Children.Count > 0)
                chartTraderButtonsGrid = chartTraderGrid.Children[0] as Grid;
            
            // Subscribe to tab changes for proper cleanup
            // Get the current tab through MainTabControl
            foreach (TabItem tab in chartWindow.MainTabControl.Items)
            {
                if ((tab.Content as ChartTab)?.ChartControl == ChartControl)
                {
                    tabItem = tab;
                    chartTab = tab.Content as ChartTab;
                    break;
                }
            }
            
            // Now insert our custom controls
            InsertWPFControls();
        }
        
        private void InsertWPFControls()
        {
            if (panelActive) return;
            if (chartTraderButtonsGrid == null) return;
            
            // Create a new row for our copier controls
            copierAddedRow = new RowDefinition { Height = new GridLength(60) };
            chartTraderGrid.RowDefinitions.Add(copierAddedRow);
            
            // Create our buttons grid
            copierButtonsGrid = new Grid
            {
                Name = "TradeCopierButtonsGrid",
                HorizontalAlignment = HorizontalAlignment.Stretch,
                VerticalAlignment = VerticalAlignment.Top,
                Margin = new Thickness(2, 5, 2, 0)
            };
            
            // Add columns for layout
            copierButtonsGrid.ColumnDefinitions.Add(new ColumnDefinition { Width = new GridLength(1, GridUnitType.Star) });
            copierButtonsGrid.ColumnDefinitions.Add(new ColumnDefinition { Width = new GridLength(1, GridUnitType.Star) });
            
            // Add rows
            copierButtonsGrid.RowDefinitions.Add(new RowDefinition { Height = GridLength.Auto });
            copierButtonsGrid.RowDefinitions.Add(new RowDefinition { Height = GridLength.Auto });
            
            // Create the main COPY button
            copyButton = new Button
            {
                Name = "TradeCopierButton",
                Content = "COPY OFF",
                Foreground = Brushes.White,
                Background = Brushes.Maroon,
                FontWeight = FontWeights.Bold,
                FontSize = 11,
                Height = 25,
                Margin = new Thickness(2, 0, 2, 2),
                ToolTip = "Click to enable/disable trade copying"
            };
            copyButton.Click += OnCopyButtonClick;
            Grid.SetRow(copyButton, 0);
            Grid.SetColumn(copyButton, 0);
            Grid.SetColumnSpan(copyButton, 2);
            copierButtonsGrid.Children.Add(copyButton);
            
            // Create status text
            string modeText = CopyAllInstruments ? "All" : "Chart";
            string statusString = $"M:{(masterAccount != null ? masterAccount.Name.Substring(0, Math.Min(8, masterAccount.Name.Length)) : "None")} | F:{followerAccounts.Count} | {modeText}";
            
            statusText = new TextBlock
            {
                Name = "TradeCopierStatus",
                Text = statusString,
                Foreground = Brushes.Gray,
                FontSize = 9,
                HorizontalAlignment = HorizontalAlignment.Center,
                Margin = new Thickness(2, 2, 2, 0),
                TextWrapping = TextWrapping.Wrap,
                TextAlignment = TextAlignment.Center
            };
            Grid.SetRow(statusText, 1);
            Grid.SetColumn(statusText, 0);
            Grid.SetColumnSpan(statusText, 2);
            copierButtonsGrid.Children.Add(statusText);
            
            // Add to the ChartTrader grid
            chartTraderGrid.Children.Add(copierButtonsGrid);
            
            // Position at the bottom (after ATM strategy section)
            Grid.SetRow(copierButtonsGrid, chartTraderGrid.RowDefinitions.Count - 1);
            Grid.SetColumn(copierButtonsGrid, 0);
            
            panelActive = true;
            
            LogMessage("Trade Copier panel initialized in ChartTrader");
        }
        
        private void RemoveWPFControls()
        {
            if (!panelActive) return;
            
            if (copyButton != null)
            {
                copyButton.Click -= OnCopyButtonClick;
            }
            
            if (chartTraderGrid != null && copierButtonsGrid != null)
            {
                chartTraderGrid.Children.Remove(copierButtonsGrid);
            }
            
            if (chartTraderGrid != null && copierAddedRow != null)
            {
                chartTraderGrid.RowDefinitions.Remove(copierAddedRow);
            }
            
            copierButtonsGrid = null;
            copierAddedRow = null;
            copyButton = null;
            statusText = null;
            panelActive = false;
        }
        
        private void DisposeWPFControls()
        {
            RemoveWPFControls();
            
            chartWindow = null;
            chartTrader = null;
            chartTraderGrid = null;
            chartTraderButtonsGrid = null;
            chartTab = null;
            tabItem = null;
        }
        
        
        #endregion

        #region Initialization Methods
        
        private void ClearData()
        {
            totalOrdersCopied = 0;
            successfulOrders = 0;
            failedOrders = 0;
            lastCopyTime = null;
            processedOrderIds.Clear();
        }
        
        private void InitializeAccounts()
        {
            followerAccounts.Clear();
            
            string[] followerNames = new string[]
            {
                Account1, Account2, Account3, Account4, Account5,
                Account6, Account7, Account8, Account9, Account10,
                Account11, Account12, Account13, Account14, Account15,
                Account16, Account17, Account18, Account19, Account20
            };
            
            lock (Account.All)
            {
                // Setup master account
                if (!string.IsNullOrEmpty(MasterAccountName))
                {
                    masterAccount = Account.All.FirstOrDefault(a => a.Name == MasterAccountName);
                    if (masterAccount != null)
                    {
                        SubscribeToAccount(masterAccount);
                        LogMessage($"Master account connected: {masterAccount.Name}");
                        
                        // Get initial master position
                        foreach (Position pos in masterAccount.Positions)
                        {
                            if (ShouldProcessInstrument(pos.Instrument))
                                masterPosition = pos;
                        }
                    }
                    else
                    {
                        LogMessage($"WARNING: Master account '{MasterAccountName}' not found!");
                    }
                }
                
                // Setup follower accounts - no need to subscribe to their events
                for (int i = 0; i < followerNames.Length; i++)
                {
                    string accName = followerNames[i];
                    if (!string.IsNullOrEmpty(accName))
                    {
                        Account acc = Account.All.FirstOrDefault(a => a.Name == accName);
                        if (acc != null && acc != masterAccount)
                        {
                            followerAccounts.Add(acc);
                            // Don't subscribe to follower account events - we only need to send orders to them
                            LogMessage($"Follower account {i + 1} connected: {acc.Name}");
                        }
                    }
                }
            }
            
            LogMessage($"Initialization complete. Master: {(masterAccount != null ? "Yes" : "No")}, Followers: {followerAccounts.Count}");
            LogMessage($"Copy mode: {(CopyAllInstruments ? "All Instruments" : "Current Instrument Only")}");
        }
        
        private void SubscribeToAccount(Account acc)
        {
            if (acc == null) return;
            
            acc.OrderUpdate += OnOrderUpdate;
            acc.PositionUpdate += OnPositionUpdate;
            acc.ExecutionUpdate += OnExecutionUpdate;
        }
        
        private void UnsubscribeFromAccount(Account acc)
        {
            if (acc == null) return;
            
            acc.OrderUpdate -= OnOrderUpdate;
            acc.PositionUpdate -= OnPositionUpdate;
            acc.ExecutionUpdate -= OnExecutionUpdate;
        }
        
        private void CleanupResources()
        {
            isCopyEnabled = false;
            
            // Only master account has event subscriptions
            if (masterAccount != null)
                UnsubscribeFromAccount(masterAccount);
            
            // Follower accounts don't have subscriptions, just clear the list
            followerAccounts.Clear();
        }
        
        #endregion

        #region Instrument Handling
        
        private bool ShouldProcessInstrument(Instrument orderInstrument)
        {
            if (CopyAllInstruments)
                return true;
            
            return orderInstrument == Instrument;
        }
        
        #endregion

        #region Event Handlers
        
        private void OnCopyButtonClick(object sender, RoutedEventArgs e)
        {
            isCopyEnabled = !isCopyEnabled;
            
            ChartControl.Dispatcher.InvokeAsync(() =>
            {
                if (copyButton != null)
                {
                    if (isCopyEnabled)
                    {
                        copyButton.Content = "COPYING";
                        copyButton.Background = Brushes.DarkGreen;
                        LogMessage("Trade copying ENABLED");
                    }
                    else
                    {
                        copyButton.Content = "COPY OFF";
                        copyButton.Background = Brushes.Maroon;
                        LogMessage("Trade copying DISABLED");
                    }
                }
                UpdateStatusDisplay();
            });
        }
        
        private void OnExecutionUpdate(object sender, ExecutionEventArgs e)
        {
            if (!isCopyEnabled) return;
            if (masterAccount == null) return;
            
            // Only process executions from the master account
            if (e.Execution.Account != masterAccount) return;
            if (!ShouldProcessInstrument(e.Execution.Instrument)) return;
            
            // Use ExecutionId to ensure we only process each execution once
            string executionKey = e.Execution.ExecutionId;
            
            lock (lockObject)
            {
                if (processedOrderIds.Contains(executionKey))
                {
                    LogMessage($"Skipping duplicate execution: {executionKey}");
                    return;
                }
                
                processedOrderIds.Add(executionKey);
                
                // Clean old processed IDs periodically
                if (processedOrderIds.Count > 1000)
                {
                    var oldIds = processedOrderIds.Take(500).ToList();
                    foreach (var old in oldIds)
                        processedOrderIds.Remove(old);
                }
            }
            
            // Copy the execution to all follower accounts (outside the lock to prevent deadlocks)
            LogMessage($"Processing master execution: {e.Execution.Instrument.FullName} {e.Execution.Order.OrderAction} Qty:{e.Execution.Quantity} @ {e.Execution.Price}");
            CopyExecutionToFollowers(e.Execution);
        }
        
        private void OnPositionUpdate(object sender, PositionEventArgs e)
        {
            if (ShouldProcessInstrument(e.Position.Instrument) && e.Position.Account == masterAccount)
            {
                masterPosition = e.Position;
            }
        }
        
        private void OnOrderUpdate(object sender, OrderEventArgs e)
        {
            // Order updates are now only used for logging/debugging if needed
            // Actual trade copying is handled in OnExecutionUpdate for better reliability
        }
        
        #endregion

        #region Order Copying Logic
        
        private void CopyExecutionToFollowers(Execution execution)
        {
            int quantity = CalculateQuantity(execution.Quantity);
            
            // Determine order action based on the execution
            OrderAction orderAction = execution.Order.OrderAction;
            
            LogMessage($"Copying execution: {execution.Instrument.FullName} {orderAction} {quantity} @ {execution.Price} (Original Qty: {execution.Quantity})");
            
            foreach (var followerAcc in followerAccounts)
            {
                try
                {
                    SendOrderToAccount(followerAcc, execution.Instrument, orderAction, OrderType.Market, quantity, execution.ExecutionId);
                }
                catch (Exception ex)
                {
                    LogMessage($"ERROR copying to {followerAcc.Name}: {ex.Message}");
                    failedOrders++;
                }
            }
            
            lastCopyTime = DateTime.Now;
            
            if (ChartControl != null)
            {
                ChartControl.Dispatcher.InvokeAsync(() =>
                {
                    UpdateStatusDisplay();
                });
            }
        }
        
        private int CalculateQuantity(int sourceQuantity)
        {
            int quantity = sourceQuantity;
            
            if (UseQuantityMultiplier)
            {
                quantity = (int)Math.Round(sourceQuantity * QuantityMultiplier);
            }
            
            quantity = Math.Max(1, quantity);
            quantity = Math.Min(quantity, MaxQuantityPerAccount);
            
            return quantity;
        }
        
        private void SendOrderToAccount(Account acc, Instrument instrument, OrderAction orderAction, OrderType orderType, int quantity, string sourceOrderId)
        {
            if (!isCopyEnabled) return;
            if (acc == null) return;
            
            try
            {
                string orderName = $"Copy_{sourceOrderId}_{DateTime.Now.Ticks}";
                
                Order newOrder = acc.CreateOrder(
                    instrument,
                    orderAction,
                    orderType,
                    OrderEntry.Manual,
                    TimeInForce.Day,
                    quantity,
                    0,
                    0,
                    string.Empty,
                    orderName,
                    Core.Globals.MaxDate,
                    null
                );
                
                acc.Submit(new[] { newOrder });
                
                totalOrdersCopied++;
                successfulOrders++;
                
                LogMessage($"Order sent to {acc.Name}: {instrument.FullName} {orderAction} {quantity}");
            }
            catch (Exception ex)
            {
                failedOrders++;
                LogMessage($"Failed to send order to {acc.Name}: {ex.Message}");
                throw;
            }
        }
        
        #endregion

        #region UI Updates
        
        private void UpdateStatusDisplay()
        {
            if (statusText == null) return;
            
            string modeText = CopyAllInstruments ? "All" : "Chart";
            string masterShort = masterAccount != null ? masterAccount.Name.Substring(0, Math.Min(8, masterAccount.Name.Length)) : "None";
            
            string statusString;
            if (ShowStatistics && lastCopyTime.HasValue)
            {
                statusString = $"M:{masterShort} | F:{followerAccounts.Count} | {modeText}\nCopied:{totalOrdersCopied} OK:{successfulOrders} Fail:{failedOrders}";
            }
            else
            {
                statusString = $"M:{masterShort} | F:{followerAccounts.Count} | {modeText}";
            }
            
            statusText.Text = statusString;
            statusText.Foreground = isCopyEnabled ? Brushes.LimeGreen : Brushes.Gray;
        }
        
        #endregion

        #region Helper Methods
        
        private void LogMessage(string message)
        {
            if (LogToOutput)
            {
                Print($"[TradeCopier] {DateTime.Now:HH:mm:ss} - {message}");
            }
        }
        
        public override string DisplayName
        {
            get { return "Simple Trade Copier V2"; }
        }
        
        #endregion

        protected override void OnBarUpdate()
        {
        }

        #region Properties
        
        // Master Account
        [NinjaScriptProperty]
        [Display(Name = "Master Account (Copy From)", Order = 1, GroupName = "1. Master Account")]
        [TypeConverter(typeof(AccountNameConverter))]
        public string MasterAccountName { get; set; }
        
        // Follower Accounts 1-20
        [NinjaScriptProperty]
        [Display(Name = "Follower 1", Order = 1, GroupName = "2. Follower Accounts")]
        [TypeConverter(typeof(AccountNameConverter))]
        public string Account1 { get; set; }
        
        [NinjaScriptProperty]
        [Display(Name = "Follower 2", Order = 2, GroupName = "2. Follower Accounts")]
        [TypeConverter(typeof(AccountNameConverter))]
        public string Account2 { get; set; }
        
        [NinjaScriptProperty]
        [Display(Name = "Follower 3", Order = 3, GroupName = "2. Follower Accounts")]
        [TypeConverter(typeof(AccountNameConverter))]
        public string Account3 { get; set; }
        
        [NinjaScriptProperty]
        [Display(Name = "Follower 4", Order = 4, GroupName = "2. Follower Accounts")]
        [TypeConverter(typeof(AccountNameConverter))]
        public string Account4 { get; set; }
        
        [NinjaScriptProperty]
        [Display(Name = "Follower 5", Order = 5, GroupName = "2. Follower Accounts")]
        [TypeConverter(typeof(AccountNameConverter))]
        public string Account5 { get; set; }
        
        [NinjaScriptProperty]
        [Display(Name = "Follower 6", Order = 6, GroupName = "2. Follower Accounts")]
        [TypeConverter(typeof(AccountNameConverter))]
        public string Account6 { get; set; }
        
        [NinjaScriptProperty]
        [Display(Name = "Follower 7", Order = 7, GroupName = "2. Follower Accounts")]
        [TypeConverter(typeof(AccountNameConverter))]
        public string Account7 { get; set; }
        
        [NinjaScriptProperty]
        [Display(Name = "Follower 8", Order = 8, GroupName = "2. Follower Accounts")]
        [TypeConverter(typeof(AccountNameConverter))]
        public string Account8 { get; set; }
        
        [NinjaScriptProperty]
        [Display(Name = "Follower 9", Order = 9, GroupName = "2. Follower Accounts")]
        [TypeConverter(typeof(AccountNameConverter))]
        public string Account9 { get; set; }
        
        [NinjaScriptProperty]
        [Display(Name = "Follower 10", Order = 10, GroupName = "2. Follower Accounts")]
        [TypeConverter(typeof(AccountNameConverter))]
        public string Account10 { get; set; }
        
        [NinjaScriptProperty]
        [Display(Name = "Follower 11", Order = 11, GroupName = "2. Follower Accounts")]
        [TypeConverter(typeof(AccountNameConverter))]
        public string Account11 { get; set; }
        
        [NinjaScriptProperty]
        [Display(Name = "Follower 12", Order = 12, GroupName = "2. Follower Accounts")]
        [TypeConverter(typeof(AccountNameConverter))]
        public string Account12 { get; set; }
        
        [NinjaScriptProperty]
        [Display(Name = "Follower 13", Order = 13, GroupName = "2. Follower Accounts")]
        [TypeConverter(typeof(AccountNameConverter))]
        public string Account13 { get; set; }
        
        [NinjaScriptProperty]
        [Display(Name = "Follower 14", Order = 14, GroupName = "2. Follower Accounts")]
        [TypeConverter(typeof(AccountNameConverter))]
        public string Account14 { get; set; }
        
        [NinjaScriptProperty]
        [Display(Name = "Follower 15", Order = 15, GroupName = "2. Follower Accounts")]
        [TypeConverter(typeof(AccountNameConverter))]
        public string Account15 { get; set; }
        
        [NinjaScriptProperty]
        [Display(Name = "Follower 16", Order = 16, GroupName = "2. Follower Accounts")]
        [TypeConverter(typeof(AccountNameConverter))]
        public string Account16 { get; set; }
        
        [NinjaScriptProperty]
        [Display(Name = "Follower 17", Order = 17, GroupName = "2. Follower Accounts")]
        [TypeConverter(typeof(AccountNameConverter))]
        public string Account17 { get; set; }
        
        [NinjaScriptProperty]
        [Display(Name = "Follower 18", Order = 18, GroupName = "2. Follower Accounts")]
        [TypeConverter(typeof(AccountNameConverter))]
        public string Account18 { get; set; }
        
        [NinjaScriptProperty]
        [Display(Name = "Follower 19", Order = 19, GroupName = "2. Follower Accounts")]
        [TypeConverter(typeof(AccountNameConverter))]
        public string Account19 { get; set; }
        
        [NinjaScriptProperty]
        [Display(Name = "Follower 20", Order = 20, GroupName = "2. Follower Accounts")]
        [TypeConverter(typeof(AccountNameConverter))]
        public string Account20 { get; set; }
        
        // Settings
        [NinjaScriptProperty]
        [Display(Name = "Copy All Instruments", Description = "When enabled, copies trades for all instruments from master account. When disabled, only copies trades for the current chart instrument.", Order = 1, GroupName = "3. Settings")]
        public bool CopyAllInstruments { get; set; }
        
        [NinjaScriptProperty]
        [Display(Name = "Use Quantity Multiplier", Order = 2, GroupName = "3. Settings")]
        public bool UseQuantityMultiplier { get; set; }
        
        [NinjaScriptProperty]
        [Range(0.1, 10.0)]
        [Display(Name = "Quantity Multiplier", Order = 3, GroupName = "3. Settings")]
        public double QuantityMultiplier { get; set; }
        
        [NinjaScriptProperty]
        [Range(1, 1000)]
        [Display(Name = "Max Quantity Per Account", Order = 4, GroupName = "3. Settings")]
        public int MaxQuantityPerAccount { get; set; }
        
        [NinjaScriptProperty]
        [Display(Name = "Show Statistics", Order = 5, GroupName = "3. Settings")]
        public bool ShowStatistics { get; set; }
        
        [NinjaScriptProperty]
        [Display(Name = "Log to Output Window", Order = 6, GroupName = "3. Settings")]
        public bool LogToOutput { get; set; }
        
        #endregion
    }
}

#region NinjaScript generated code. Neither change nor remove.

namespace NinjaTrader.NinjaScript.Indicators
{
	public partial class Indicator : NinjaTrader.Gui.NinjaScript.IndicatorRenderBase
	{
		private SimpleTradeCopierV2[] cacheSimpleTradeCopierV2;
		public SimpleTradeCopierV2 SimpleTradeCopierV2(string masterAccountName, string account1, string account2, string account3, string account4, string account5, string account6, string account7, string account8, string account9, string account10, string account11, string account12, string account13, string account14, string account15, string account16, string account17, string account18, string account19, string account20, bool copyAllInstruments, bool useQuantityMultiplier, double quantityMultiplier, int maxQuantityPerAccount, bool showStatistics, bool logToOutput)
		{
			return SimpleTradeCopierV2(Input, masterAccountName, account1, account2, account3, account4, account5, account6, account7, account8, account9, account10, account11, account12, account13, account14, account15, account16, account17, account18, account19, account20, copyAllInstruments, useQuantityMultiplier, quantityMultiplier, maxQuantityPerAccount, showStatistics, logToOutput);
		}

		public SimpleTradeCopierV2 SimpleTradeCopierV2(ISeries<double> input, string masterAccountName, string account1, string account2, string account3, string account4, string account5, string account6, string account7, string account8, string account9, string account10, string account11, string account12, string account13, string account14, string account15, string account16, string account17, string account18, string account19, string account20, bool copyAllInstruments, bool useQuantityMultiplier, double quantityMultiplier, int maxQuantityPerAccount, bool showStatistics, bool logToOutput)
		{
			if (cacheSimpleTradeCopierV2 != null)
				for (int idx = 0; idx < cacheSimpleTradeCopierV2.Length; idx++)
					if (cacheSimpleTradeCopierV2[idx] != null && cacheSimpleTradeCopierV2[idx].MasterAccountName == masterAccountName && cacheSimpleTradeCopierV2[idx].Account1 == account1 && cacheSimpleTradeCopierV2[idx].Account2 == account2 && cacheSimpleTradeCopierV2[idx].Account3 == account3 && cacheSimpleTradeCopierV2[idx].Account4 == account4 && cacheSimpleTradeCopierV2[idx].Account5 == account5 && cacheSimpleTradeCopierV2[idx].Account6 == account6 && cacheSimpleTradeCopierV2[idx].Account7 == account7 && cacheSimpleTradeCopierV2[idx].Account8 == account8 && cacheSimpleTradeCopierV2[idx].Account9 == account9 && cacheSimpleTradeCopierV2[idx].Account10 == account10 && cacheSimpleTradeCopierV2[idx].Account11 == account11 && cacheSimpleTradeCopierV2[idx].Account12 == account12 && cacheSimpleTradeCopierV2[idx].Account13 == account13 && cacheSimpleTradeCopierV2[idx].Account14 == account14 && cacheSimpleTradeCopierV2[idx].Account15 == account15 && cacheSimpleTradeCopierV2[idx].Account16 == account16 && cacheSimpleTradeCopierV2[idx].Account17 == account17 && cacheSimpleTradeCopierV2[idx].Account18 == account18 && cacheSimpleTradeCopierV2[idx].Account19 == account19 && cacheSimpleTradeCopierV2[idx].Account20 == account20 && cacheSimpleTradeCopierV2[idx].CopyAllInstruments == copyAllInstruments && cacheSimpleTradeCopierV2[idx].UseQuantityMultiplier == useQuantityMultiplier && cacheSimpleTradeCopierV2[idx].QuantityMultiplier == quantityMultiplier && cacheSimpleTradeCopierV2[idx].MaxQuantityPerAccount == maxQuantityPerAccount && cacheSimpleTradeCopierV2[idx].ShowStatistics == showStatistics && cacheSimpleTradeCopierV2[idx].LogToOutput == logToOutput && cacheSimpleTradeCopierV2[idx].EqualsInput(input))
						return cacheSimpleTradeCopierV2[idx];
			return CacheIndicator<SimpleTradeCopierV2>(new SimpleTradeCopierV2(){ MasterAccountName = masterAccountName, Account1 = account1, Account2 = account2, Account3 = account3, Account4 = account4, Account5 = account5, Account6 = account6, Account7 = account7, Account8 = account8, Account9 = account9, Account10 = account10, Account11 = account11, Account12 = account12, Account13 = account13, Account14 = account14, Account15 = account15, Account16 = account16, Account17 = account17, Account18 = account18, Account19 = account19, Account20 = account20, CopyAllInstruments = copyAllInstruments, UseQuantityMultiplier = useQuantityMultiplier, QuantityMultiplier = quantityMultiplier, MaxQuantityPerAccount = maxQuantityPerAccount, ShowStatistics = showStatistics, LogToOutput = logToOutput }, input, ref cacheSimpleTradeCopierV2);
		}
	}
}

namespace NinjaTrader.NinjaScript.MarketAnalyzerColumns
{
	public partial class MarketAnalyzerColumn : MarketAnalyzerColumnBase
	{
		public Indicators.SimpleTradeCopierV2 SimpleTradeCopierV2(string masterAccountName, string account1, string account2, string account3, string account4, string account5, string account6, string account7, string account8, string account9, string account10, string account11, string account12, string account13, string account14, string account15, string account16, string account17, string account18, string account19, string account20, bool copyAllInstruments, bool useQuantityMultiplier, double quantityMultiplier, int maxQuantityPerAccount, bool showStatistics, bool logToOutput)
		{
			return indicator.SimpleTradeCopierV2(Input, masterAccountName, account1, account2, account3, account4, account5, account6, account7, account8, account9, account10, account11, account12, account13, account14, account15, account16, account17, account18, account19, account20, copyAllInstruments, useQuantityMultiplier, quantityMultiplier, maxQuantityPerAccount, showStatistics, logToOutput);
		}

		public Indicators.SimpleTradeCopierV2 SimpleTradeCopierV2(ISeries<double> input , string masterAccountName, string account1, string account2, string account3, string account4, string account5, string account6, string account7, string account8, string account9, string account10, string account11, string account12, string account13, string account14, string account15, string account16, string account17, string account18, string account19, string account20, bool copyAllInstruments, bool useQuantityMultiplier, double quantityMultiplier, int maxQuantityPerAccount, bool showStatistics, bool logToOutput)
		{
			return indicator.SimpleTradeCopierV2(input, masterAccountName, account1, account2, account3, account4, account5, account6, account7, account8, account9, account10, account11, account12, account13, account14, account15, account16, account17, account18, account19, account20, copyAllInstruments, useQuantityMultiplier, quantityMultiplier, maxQuantityPerAccount, showStatistics, logToOutput);
		}
	}
}

namespace NinjaTrader.NinjaScript.Strategies
{
	public partial class Strategy : NinjaTrader.Gui.NinjaScript.StrategyRenderBase
	{
		public Indicators.SimpleTradeCopierV2 SimpleTradeCopierV2(string masterAccountName, string account1, string account2, string account3, string account4, string account5, string account6, string account7, string account8, string account9, string account10, string account11, string account12, string account13, string account14, string account15, string account16, string account17, string account18, string account19, string account20, bool copyAllInstruments, bool useQuantityMultiplier, double quantityMultiplier, int maxQuantityPerAccount, bool showStatistics, bool logToOutput)
		{
			return indicator.SimpleTradeCopierV2(Input, masterAccountName, account1, account2, account3, account4, account5, account6, account7, account8, account9, account10, account11, account12, account13, account14, account15, account16, account17, account18, account19, account20, copyAllInstruments, useQuantityMultiplier, quantityMultiplier, maxQuantityPerAccount, showStatistics, logToOutput);
		}

		public Indicators.SimpleTradeCopierV2 SimpleTradeCopierV2(ISeries<double> input , string masterAccountName, string account1, string account2, string account3, string account4, string account5, string account6, string account7, string account8, string account9, string account10, string account11, string account12, string account13, string account14, string account15, string account16, string account17, string account18, string account19, string account20, bool copyAllInstruments, bool useQuantityMultiplier, double quantityMultiplier, int maxQuantityPerAccount, bool showStatistics, bool logToOutput)
		{
			return indicator.SimpleTradeCopierV2(input, masterAccountName, account1, account2, account3, account4, account5, account6, account7, account8, account9, account10, account11, account12, account13, account14, account15, account16, account17, account18, account19, account20, copyAllInstruments, useQuantityMultiplier, quantityMultiplier, maxQuantityPerAccount, showStatistics, logToOutput);
		}
	}
}

#endregion
