using System;
using System.IO;
using System.Collections.Generic;
using System.Linq;
using System.Text;

#if !TESTING
using System.Windows;
using System.Windows.Controls;
using System.Windows.Media;
using System.Windows.Threading;
using NinjaTrader.Cbi;
using NinjaTrader.Gui;
using NinjaTrader.Gui.Tools;
using NinjaTrader.NinjaScript;
using NinjaTrader.Core;

namespace NinjaTrader.NinjaScript.AddOns
{
    public class TradeCopierAddOn : AddOnBase
    {
        public static TradeCopierAddOn Instance { get; private set; }
        private NTMenuItem _menuItem;
        private ControlCenter _controlCenter;

        protected override void OnStateChange()
        {
            if (State == State.SetDefaults)
            {
                Name = "TradeCopierAddOn";
                Description = "Next-Gen Multi-Account Trade Copier & Group Execution Suite";
            }
            else if (State == State.Configure)
            {
                Instance = this;
            }
        }

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
                    if (existingMenuItem == null) return;

                    _menuItem = new NTMenuItem
                    {
                        Header = "Trade Copier Manager",
                        Style = Application.Current.TryFindResource("MainMenuItem") as Style
                    };

                    _menuItem.Click += (s, e) =>
                    {
                        try
                        {
                            var win = new TradeCopierWindow();
                            win.Owner = _controlCenter;
                            win.Show();
                        }
                        catch (Exception ex)
                        {
                            NinjaTrader.Code.Output.Process($"[TradeCopierAddOn] Error opening window: {ex.Message}", PrintTo.OutputTab1);
                        }
                    };

                    existingMenuItem.Items.Add(_menuItem);
                }
                catch (Exception ex)
                {
                    NinjaTrader.Code.Output.Process($"[TradeCopierAddOn] Error injecting menu item: {ex.Message}", PrintTo.OutputTab1);
                }
            });
        }

        protected override void OnWindowDestroyed(Window window)
        {
            ControlCenter cc = window as ControlCenter;
            if (cc == null) return;

            if (_menuItem != null)
            {
                NTMenuItem existingMenuItem = cc.FindFirst("ControlCenterMenuItemNew") as NTMenuItem;
                existingMenuItem?.Items.Remove(_menuItem);
                _menuItem = null;
            }
        }
    }

    public class TradeCopierControl : UserControl
    {
        private DispatcherTimer _refreshTimer;

        // Active Account Filter Toggle
        private CheckBox _activeOnlyCheck;

        // UI Controls - Direct Relationships
        private StackPanel _relationshipsPanel;
        private ComboBox _newLeaderCombo;
        private ComboBox _newFollowerCombo;
        private ComboBox _newSizingModeCombo;
        private TextBox _newRatioText;
        private CheckBox _newAutoSymbolCheck;
        private CheckBox _newStealthCheck;
        private TextBox _newMaxPosText;
        private CheckBox _newArmedCheck;

        // UI Controls - Copier Groups
        private StackPanel _groupsPanel;
        private TextBox _newGroupNameText;
        private ComboBox _groupLeaderCombo;
        private ComboBox _groupSizingModeCombo;
        private TextBox _groupRatioText;
        private CheckBox _groupAutoSymbolCheck;
        private CheckBox _groupStealthCheck;
        private TextBox _groupMaxPosText;
        private CheckBox _groupArmedCheck;

        // Group Account Checkbox Picker
        private TextBox _pickerSearchBox;
        private StackPanel _accountCheckboxesPanel;
        private readonly List<CheckBox> _accountCheckBoxes = new List<CheckBox>();

        // Tab 3: Symbol Mapping & Per-Ticker Ratios
        private TextBox _ratioNqText;
        private TextBox _ratioEsText;
        private TextBox _ratioYmText;
        private TextBox _ratioClText;
        private TextBox _ratioGcText;
        private TextBox _ratioRtyText;

        // Tab 4: Audit Stream
        private TextBox _auditLogBox;

        private TextBlock _statusText;

        public TradeCopierControl()
        {
            var rootGrid = new Grid();
            rootGrid.RowDefinitions.Add(new RowDefinition { Height = GridLength.Auto });
            rootGrid.RowDefinitions.Add(new RowDefinition { Height = new GridLength(1, GridUnitType.Star) });
            rootGrid.RowDefinitions.Add(new RowDefinition { Height = GridLength.Auto });

            // 1. TOP HEADER BAR (Glassmorphic Slate Theme)
            var topBar = new Border
            {
                Background = new SolidColorBrush(Color.FromRgb(26, 30, 38)),
                Padding = new Thickness(15, 12, 15, 12),
                BorderBrush = new SolidColorBrush(Color.FromRgb(45, 52, 64)),
                BorderThickness = new Thickness(0, 0, 0, 1)
            };
            var topGrid = new Grid();
            topGrid.ColumnDefinitions.Add(new ColumnDefinition { Width = new GridLength(1, GridUnitType.Star) });
            topGrid.ColumnDefinitions.Add(new ColumnDefinition { Width = GridLength.Auto });

            var titlePanel = new StackPanel { Orientation = Orientation.Horizontal };
            titlePanel.Children.Add(new TextBlock
            {
                Text = "⚡ TRADE COPIER SUITE",
                Foreground = Brushes.White,
                FontSize = 17,
                FontWeight = FontWeights.Bold,
                VerticalAlignment = VerticalAlignment.Center
            });

            _statusText = new TextBlock
            {
                Text = "  [ ENGINE: ACTIVE ]",
                Foreground = new SolidColorBrush(Color.FromRgb(46, 204, 113)),
                FontSize = 13,
                FontWeight = FontWeights.Bold,
                VerticalAlignment = VerticalAlignment.Center,
                Margin = new Thickness(10, 0, 0, 0)
            };
            titlePanel.Children.Add(_statusText);

            _activeOnlyCheck = new CheckBox
            {
                Content = "Active & Connected Accounts Only",
                IsChecked = true,
                Foreground = Brushes.LightGray,
                VerticalAlignment = VerticalAlignment.Center,
                Margin = new Thickness(25, 0, 0, 0)
            };
            _activeOnlyCheck.Click += (s, e) => RefreshUI();
            titlePanel.Children.Add(_activeOnlyCheck);

            topGrid.Children.Add(titlePanel);

            var topButtons = new StackPanel { Orientation = Orientation.Horizontal };

            var refreshBtn = new Button
            {
                Content = "🔄 Refresh",
                Background = new SolidColorBrush(Color.FromRgb(52, 73, 94)),
                Foreground = Brushes.White,
                Padding = new Thickness(12, 5, 12, 5),
                Margin = new Thickness(0, 0, 10, 0),
                BorderThickness = new Thickness(0)
            };
            refreshBtn.Click += (s, e) => RefreshUI();
            topButtons.Children.Add(refreshBtn);

            var panicBtn = new Button
            {
                Content = "🚨 FLATTEN ALL & STOP",
                Background = new SolidColorBrush(Color.FromRgb(192, 57, 43)),
                Foreground = Brushes.White,
                FontWeight = FontWeights.Bold,
                Padding = new Thickness(14, 5, 14, 5),
                BorderThickness = new Thickness(0)
            };
            panicBtn.Click += OnPanicAllClick;
            topButtons.Children.Add(panicBtn);

            Grid.SetColumn(topButtons, 1);
            topGrid.Children.Add(topButtons);
            topBar.Child = topGrid;
            Grid.SetRow(topBar, 0);
            rootGrid.Children.Add(topBar);

            // 2. TAB CONTROL
            var tabControl = new TabControl
            {
                Background = new SolidColorBrush(Color.FromRgb(18, 21, 27)),
                BorderThickness = new Thickness(0),
                Margin = new Thickness(10)
            };

            // TAB 1: Direct 1:1 Relationships
            var tabDirect = new TabItem
            {
                Header = "Direct 1:1 Pairs",
                Background = new SolidColorBrush(Color.FromRgb(30, 34, 42)),
                Foreground = Brushes.White,
                FontSize = 13
            };
            tabDirect.Content = CreateDirectRelationshipsTab();
            tabControl.Items.Add(tabDirect);

            // TAB 2: Copier Groups
            var tabGroups = new TabItem
            {
                Header = "Copier Groups (1:N)",
                Background = new SolidColorBrush(Color.FromRgb(30, 34, 42)),
                Foreground = Brushes.White,
                FontSize = 13
            };
            tabGroups.Content = CreateGroupsTab();
            tabControl.Items.Add(tabGroups);

            // TAB 3: Symbol Mapping & Per-Ticker Matrix
            var tabSymbols = new TabItem
            {
                Header = "Symbol & Per-Ticker Matrix",
                Background = new SolidColorBrush(Color.FromRgb(30, 34, 42)),
                Foreground = Brushes.White,
                FontSize = 13
            };
            tabSymbols.Content = CreateSymbolMatrixTab();
            tabControl.Items.Add(tabSymbols);

            // TAB 4: Real-Time Audit Log
            var tabAudit = new TabItem
            {
                Header = "Execution Audit Stream",
                Background = new SolidColorBrush(Color.FromRgb(30, 34, 42)),
                Foreground = Brushes.White,
                FontSize = 13
            };
            tabAudit.Content = CreateAuditStreamTab();
            tabControl.Items.Add(tabAudit);

            Grid.SetRow(tabControl, 1);
            rootGrid.Children.Add(tabControl);

            // 3. FOOTER STATUS BAR
            var footer = new Border
            {
                Background = new SolidColorBrush(Color.FromRgb(15, 17, 21)),
                Padding = new Thickness(12, 6, 12, 6)
            };
            var footerText = new TextBlock
            {
                Text = "Institutional Local Engine | Bidirectional Mini<->Micro Scaling | Stealth Order Tagging | RiskGuard v1.1.0 Integrated",
                Foreground = Brushes.Gray,
                FontSize = 11
            };
            footer.Child = footerText;
            Grid.SetRow(footer, 2);
            rootGrid.Children.Add(footer);

            Content = rootGrid;

            // Timer for periodic UI updates
            _refreshTimer = new DispatcherTimer { Interval = TimeSpan.FromSeconds(2) };
            _refreshTimer.Tick += (s, e) => RefreshUI();
            _refreshTimer.Start();

            Loaded += (s, e) => RefreshUI();
            Unloaded += (s, e) => _refreshTimer?.Stop();
        }

        private List<string> GetFilteredAccounts()
        {
            var all = Account.All.ToList();
            bool activeOnly = _activeOnlyCheck.IsChecked ?? true;

            if (activeOnly)
            {
                var filtered = all.Where(a => 
                    a != null && 
                    a.Connection != null && 
                    a.Connection.Status == ConnectionStatus.Connected).Select(a => a.Name).ToList();

                if (filtered.Count > 0) return filtered;
            }

            var names = all.Select(a => a.Name).ToList();
            if (names.Count == 0) names.Add("Sim101");
            return names;
        }

        private UIElement CreateDirectRelationshipsTab()
        {
            var grid = new Grid();
            grid.RowDefinitions.Add(new RowDefinition { Height = GridLength.Auto });
            grid.RowDefinitions.Add(new RowDefinition { Height = new GridLength(1, GridUnitType.Star) });

            // Form Card
            var addCard = new Border
            {
                Background = new SolidColorBrush(Color.FromRgb(26, 30, 38)),
                CornerRadius = new CornerRadius(6),
                Padding = new Thickness(14),
                Margin = new Thickness(0, 0, 0, 10),
                BorderBrush = new SolidColorBrush(Color.FromRgb(45, 52, 64)),
                BorderThickness = new Thickness(1)
            };
            var formPanel = new StackPanel();
            formPanel.Children.Add(new TextBlock
            {
                Text = "ADD DIRECT 1:1 RELATIONSHIP",
                Foreground = new SolidColorBrush(Color.FromRgb(52, 152, 219)),
                FontWeight = FontWeights.Bold,
                FontSize = 13,
                Margin = new Thickness(0, 0, 0, 10)
            });

            var inputRow = new WrapPanel { Orientation = Orientation.Horizontal };

            inputRow.Children.Add(new TextBlock { Text = "Leader:", Foreground = Brushes.LightGray, VerticalAlignment = VerticalAlignment.Center, Margin = new Thickness(0, 0, 5, 0) });
            _newLeaderCombo = new ComboBox { Width = 120, Margin = new Thickness(0, 0, 15, 0) };
            inputRow.Children.Add(_newLeaderCombo);

            inputRow.Children.Add(new TextBlock { Text = "Follower:", Foreground = Brushes.LightGray, VerticalAlignment = VerticalAlignment.Center, Margin = new Thickness(0, 0, 5, 0) });
            _newFollowerCombo = new ComboBox { Width = 120, Margin = new Thickness(0, 0, 15, 0) };
            inputRow.Children.Add(_newFollowerCombo);

            inputRow.Children.Add(new TextBlock { Text = "Sizing Mode:", Foreground = Brushes.LightGray, VerticalAlignment = VerticalAlignment.Center, Margin = new Thickness(0, 0, 5, 0) });
            _newSizingModeCombo = new ComboBox { Width = 110, Margin = new Thickness(0, 0, 15, 0) };
            _newSizingModeCombo.Items.Add("QuantityRatio");
            _newSizingModeCombo.Items.Add("FixedLot");
            _newSizingModeCombo.SelectedIndex = 0;
            inputRow.Children.Add(_newSizingModeCombo);

            inputRow.Children.Add(new TextBlock { Text = "Ratio:", Foreground = Brushes.LightGray, VerticalAlignment = VerticalAlignment.Center, Margin = new Thickness(0, 0, 5, 0) });
            _newRatioText = new TextBox { Text = "1.0", Width = 45, Margin = new Thickness(0, 0, 15, 0) };
            inputRow.Children.Add(_newRatioText);

            inputRow.Children.Add(new TextBlock { Text = "Max Pos:", Foreground = Brushes.LightGray, VerticalAlignment = VerticalAlignment.Center, Margin = new Thickness(0, 0, 5, 0) });
            _newMaxPosText = new TextBox { Text = "100", Width = 50, Margin = new Thickness(0, 0, 15, 0) };
            inputRow.Children.Add(_newMaxPosText);

            _newAutoSymbolCheck = new CheckBox { Content = "Auto Mini<->Micro", IsChecked = true, Foreground = Brushes.LightGray, VerticalAlignment = VerticalAlignment.Center, Margin = new Thickness(0, 0, 15, 0) };
            inputRow.Children.Add(_newAutoSymbolCheck);

            _newStealthCheck = new CheckBox { Content = "Stealth Tagging", IsChecked = true, Foreground = Brushes.LightGray, VerticalAlignment = VerticalAlignment.Center, Margin = new Thickness(0, 0, 15, 0) };
            inputRow.Children.Add(_newStealthCheck);

            _newArmedCheck = new CheckBox { Content = "Arm Live", IsChecked = false, Foreground = new SolidColorBrush(Color.FromRgb(255, 165, 0)), VerticalAlignment = VerticalAlignment.Center, Margin = new Thickness(0, 0, 15, 0) };
            inputRow.Children.Add(_newArmedCheck);

            var addBtn = new Button
            {
                Content = "➕ Save Relationship",
                Background = new SolidColorBrush(Color.FromRgb(46, 204, 113)),
                Foreground = Brushes.White,
                Padding = new Thickness(12, 5, 12, 5),
                BorderThickness = new Thickness(0),
                FontWeight = FontWeights.Bold
            };
            addBtn.Click += OnAddRelationshipClick;
            inputRow.Children.Add(addBtn);

            formPanel.Children.Add(inputRow);
            addCard.Child = formPanel;
            Grid.SetRow(addCard, 0);
            grid.Children.Add(addCard);

            // Active List
            var scroll = new ScrollViewer { VerticalScrollBarVisibility = ScrollBarVisibility.Auto };
            _relationshipsPanel = new StackPanel();
            scroll.Content = _relationshipsPanel;
            Grid.SetRow(scroll, 1);
            grid.Children.Add(scroll);

            return grid;
        }

        private UIElement CreateGroupsTab()
        {
            var mainGrid = new Grid();
            mainGrid.ColumnDefinitions.Add(new ColumnDefinition { Width = new GridLength(420) }); // Form & Account Picker
            mainGrid.ColumnDefinitions.Add(new ColumnDefinition { Width = new GridLength(1, GridUnitType.Star) }); // Active Groups Cards

            // LEFT SIDE: Create Group Form & Account Checkbox Picker
            var leftCard = new Border
            {
                Background = new SolidColorBrush(Color.FromRgb(26, 30, 38)),
                CornerRadius = new CornerRadius(6),
                Padding = new Thickness(14),
                Margin = new Thickness(0, 0, 10, 0),
                BorderBrush = new SolidColorBrush(Color.FromRgb(45, 52, 64)),
                BorderThickness = new Thickness(1)
            };
            var leftPanel = new StackPanel();

            leftPanel.Children.Add(new TextBlock
            {
                Text = "CREATE COPIER GROUP (1 LEADER ➔ MULTIPLE FOLLOWERS)",
                Foreground = new SolidColorBrush(Color.FromRgb(155, 89, 182)),
                FontWeight = FontWeights.Bold,
                FontSize = 12,
                Margin = new Thickness(0, 0, 0, 10)
            });

            // Inputs
            var gNameRow = new StackPanel { Orientation = Orientation.Horizontal, Margin = new Thickness(0, 0, 0, 6) };
            gNameRow.Children.Add(new TextBlock { Text = "Group Name:", Width = 100, Foreground = Brushes.LightGray, VerticalAlignment = VerticalAlignment.Center });
            _newGroupNameText = new TextBox { Text = "Prop_Group_1", Width = 200 };
            gNameRow.Children.Add(_newGroupNameText);
            leftPanel.Children.Add(gNameRow);

            var gLeaderRow = new StackPanel { Orientation = Orientation.Horizontal, Margin = new Thickness(0, 0, 0, 6) };
            gLeaderRow.Children.Add(new TextBlock { Text = "Leader Account:", Width = 100, Foreground = Brushes.LightGray, VerticalAlignment = VerticalAlignment.Center });
            _groupLeaderCombo = new ComboBox { Width = 200 };
            gLeaderRow.Children.Add(_groupLeaderCombo);
            leftPanel.Children.Add(gLeaderRow);

            var gSizingRow = new StackPanel { Orientation = Orientation.Horizontal, Margin = new Thickness(0, 0, 0, 6) };
            gSizingRow.Children.Add(new TextBlock { Text = "Sizing Mode:", Width = 100, Foreground = Brushes.LightGray, VerticalAlignment = VerticalAlignment.Center });
            _groupSizingModeCombo = new ComboBox { Width = 120 };
            _groupSizingModeCombo.Items.Add("QuantityRatio");
            _groupSizingModeCombo.Items.Add("FixedLot");
            _groupSizingModeCombo.SelectedIndex = 0;
            gSizingRow.Children.Add(_groupSizingModeCombo);
            gSizingRow.Children.Add(new TextBlock { Text = "Ratio:", Foreground = Brushes.LightGray, Margin = new Thickness(10, 0, 5, 0), VerticalAlignment = VerticalAlignment.Center });
            _groupRatioText = new TextBox { Text = "1.0", Width = 40 };
            gSizingRow.Children.Add(_groupRatioText);
            leftPanel.Children.Add(gSizingRow);

            var gFlagsRow = new WrapPanel { Orientation = Orientation.Horizontal, Margin = new Thickness(0, 4, 0, 10) };
            _groupAutoSymbolCheck = new CheckBox { Content = "Auto Mini<->Micro", IsChecked = true, Foreground = Brushes.LightGray, Margin = new Thickness(0, 0, 12, 0) };
            gFlagsRow.Children.Add(_groupAutoSymbolCheck);
            _groupStealthCheck = new CheckBox { Content = "Stealth Tagging", IsChecked = true, Foreground = Brushes.LightGray, Margin = new Thickness(0, 0, 12, 0) };
            gFlagsRow.Children.Add(_groupStealthCheck);
            _groupArmedCheck = new CheckBox { Content = "Arm Live", IsChecked = false, Foreground = new SolidColorBrush(Color.FromRgb(255, 165, 0)) };
            gFlagsRow.Children.Add(_groupArmedCheck);
            leftPanel.Children.Add(gFlagsRow);

            // ACCOUNT CHECKBOX PICKER TITLE & SEARCH
            leftPanel.Children.Add(new TextBlock
            {
                Text = "SELECT FOLLOWER ACCOUNTS (CHECKBOX SELECTOR):",
                Foreground = Brushes.White,
                FontWeight = FontWeights.Bold,
                FontSize = 11,
                Margin = new Thickness(0, 8, 0, 6)
            });

            var searchRow = new Grid { Margin = new Thickness(0, 0, 0, 6) };
            searchRow.ColumnDefinitions.Add(new ColumnDefinition { Width = new GridLength(1, GridUnitType.Star) });
            searchRow.ColumnDefinitions.Add(new ColumnDefinition { Width = GridLength.Auto });

            _pickerSearchBox = new TextBox { Text = "", Height = 22, Background = new SolidColorBrush(Color.FromRgb(40, 44, 52)), Foreground = Brushes.White };
            _pickerSearchBox.TextChanged += (s, e) => FilterAccountCheckboxes();
            Grid.SetColumn(_pickerSearchBox, 0);
            searchRow.Children.Add(_pickerSearchBox);

            var btnPanel = new StackPanel { Orientation = Orientation.Horizontal, Margin = new Thickness(5, 0, 0, 0) };
            var selectAllBtn = new Button { Content = "Select All", Padding = new Thickness(5, 2, 5, 2), Margin = new Thickness(0, 0, 4, 0) };
            selectAllBtn.Click += (s, e) => { foreach (var cb in _accountCheckBoxes) cb.IsChecked = true; };
            btnPanel.Children.Add(selectAllBtn);

            var clearAllBtn = new Button { Content = "Clear", Padding = new Thickness(5, 2, 5, 2) };
            clearAllBtn.Click += (s, e) => { foreach (var cb in _accountCheckBoxes) cb.IsChecked = false; };
            btnPanel.Children.Add(clearAllBtn);

            Grid.SetColumn(btnPanel, 1);
            searchRow.Children.Add(btnPanel);
            leftPanel.Children.Add(searchRow);

            // SCROLLABLE CHECKBOXES LIST
            var pickerScroll = new ScrollViewer { Height = 180, VerticalScrollBarVisibility = ScrollBarVisibility.Auto, Background = new SolidColorBrush(Color.FromRgb(18, 21, 27)), Padding = new Thickness(6) };
            _accountCheckboxesPanel = new StackPanel();
            pickerScroll.Content = _accountCheckboxesPanel;
            leftPanel.Children.Add(pickerScroll);

            // Save Group Button
            var addGroupBtn = new Button
            {
                Content = "➕ Save Copier Group",
                Background = new SolidColorBrush(Color.FromRgb(142, 68, 173)),
                Foreground = Brushes.White,
                FontWeight = FontWeights.Bold,
                Padding = new Thickness(12, 6, 12, 6),
                Margin = new Thickness(0, 12, 0, 0),
                BorderThickness = new Thickness(0)
            };
            addGroupBtn.Click += OnAddGroupClick;
            leftPanel.Children.Add(addGroupBtn);

            leftCard.Child = leftPanel;
            Grid.SetColumn(leftCard, 0);
            mainGrid.Children.Add(leftCard);

            // RIGHT SIDE: Active Groups Cards
            var rightScroll = new ScrollViewer { VerticalScrollBarVisibility = ScrollBarVisibility.Auto };
            _groupsPanel = new StackPanel();
            rightScroll.Content = _groupsPanel;
            Grid.SetColumn(rightScroll, 1);
            mainGrid.Children.Add(rightScroll);

            return mainGrid;
        }

        private UIElement CreateSymbolMatrixTab()
        {
            var scroll = new ScrollViewer { VerticalScrollBarVisibility = ScrollBarVisibility.Auto };
            var panel = new StackPanel { Margin = new Thickness(15) };

            panel.Children.Add(new TextBlock
            {
                Text = "BIDIRECTIONAL MINI <-> MICRO SYMBOL MAPPING MATRIX",
                Foreground = new SolidColorBrush(Color.FromRgb(52, 152, 219)),
                FontSize = 15,
                FontWeight = FontWeights.Bold,
                Margin = new Thickness(0, 0, 0, 10)
            });

            panel.Children.Add(new TextBlock
            {
                Text = "The copier automatically converts Mini contracts (1 NQ) to Micro contracts (10 MNQ) or Micro to Mini (10 MNQ -> 1 NQ) across all futures asset classes.",
                Foreground = Brushes.LightGray,
                TextWrapping = TextWrapping.Wrap,
                Margin = new Thickness(0, 0, 0, 15)
            });

            var matrixCard = new Border
            {
                Background = new SolidColorBrush(Color.FromRgb(26, 30, 38)),
                CornerRadius = new CornerRadius(6),
                Padding = new Thickness(15),
                BorderBrush = new SolidColorBrush(Color.FromRgb(45, 52, 64)),
                BorderThickness = new Thickness(1)
            };

            var grid = new Grid();
            grid.ColumnDefinitions.Add(new ColumnDefinition { Width = new GridLength(120) });
            grid.ColumnDefinitions.Add(new ColumnDefinition { Width = new GridLength(140) });
            grid.ColumnDefinitions.Add(new ColumnDefinition { Width = new GridLength(140) });
            grid.ColumnDefinitions.Add(new ColumnDefinition { Width = new GridLength(150) });

            // Headers
            grid.RowDefinitions.Add(new RowDefinition { Height = GridLength.Auto });
            var h1 = new TextBlock { Text = "Asset Class", Foreground = Brushes.White, FontWeight = FontWeights.Bold };
            var h2 = new TextBlock { Text = "Mini Contract", Foreground = Brushes.White, FontWeight = FontWeights.Bold };
            var h3 = new TextBlock { Text = "Micro Contract", Foreground = Brushes.White, FontWeight = FontWeights.Bold };
            var h4 = new TextBlock { Text = "Scaling Ratio", Foreground = Brushes.White, FontWeight = FontWeights.Bold };

            Grid.SetColumn(h1, 0); Grid.SetRow(h1, 0); grid.Children.Add(h1);
            Grid.SetColumn(h2, 1); Grid.SetRow(h2, 0); grid.Children.Add(h2);
            Grid.SetColumn(h3, 2); Grid.SetRow(h3, 0); grid.Children.Add(h3);
            Grid.SetColumn(h4, 3); Grid.SetRow(h4, 0); grid.Children.Add(h4);

            string[,] rows = new string[,]
            {
                { "Nasdaq 100", "NQ", "MNQ", "1 Mini = 10 Micros" },
                { "S&P 500", "ES", "MES", "1 Mini = 10 Micros" },
                { "Dow Jones", "YM", "MYM", "1 Mini = 10 Micros" },
                { "Crude Oil", "CL", "MCL", "1 Mini = 10 Micros" },
                { "Gold", "GC", "MGC", "1 Mini = 10 Micros" },
                { "Russell 2000", "RTY", "M2K", "1 Mini = 10 Micros" }
            };

            for (int i = 0; i < rows.GetLength(0); i++)
            {
                grid.RowDefinitions.Add(new RowDefinition { Height = GridLength.Auto });
                int rowIdx = i + 1;

                var t1 = new TextBlock { Text = rows[i, 0], Foreground = Brushes.LightGray, Margin = new Thickness(0, 6, 0, 6) };
                var t2 = new TextBlock { Text = rows[i, 1], Foreground = new SolidColorBrush(Color.FromRgb(46, 204, 113)), FontWeight = FontWeights.Bold, Margin = new Thickness(0, 6, 0, 6) };
                var t3 = new TextBlock { Text = rows[i, 2], Foreground = new SolidColorBrush(Color.FromRgb(155, 89, 182)), FontWeight = FontWeights.Bold, Margin = new Thickness(0, 6, 0, 6) };
                var t4 = new TextBlock { Text = rows[i, 3], Foreground = Brushes.Gray, Margin = new Thickness(0, 6, 0, 6) };

                Grid.SetColumn(t1, 0); Grid.SetRow(t1, rowIdx); grid.Children.Add(t1);
                Grid.SetColumn(t2, 1); Grid.SetRow(t2, rowIdx); grid.Children.Add(t2);
                Grid.SetColumn(t3, 2); Grid.SetRow(t3, rowIdx); grid.Children.Add(t3);
                Grid.SetColumn(t4, 3); Grid.SetRow(t4, rowIdx); grid.Children.Add(t4);
            }

            matrixCard.Child = grid;
            panel.Children.Add(matrixCard);
            scroll.Content = panel;
            return scroll;
        }

        private UIElement CreateAuditStreamTab()
        {
            var grid = new Grid();
            grid.RowDefinitions.Add(new RowDefinition { Height = GridLength.Auto });
            grid.RowDefinitions.Add(new RowDefinition { Height = new GridLength(1, GridUnitType.Star) });

            var header = new TextBlock
            {
                Text = "REAL-TIME EXECUTION AUDIT & AUTO-SYNC DRIFT STREAM",
                Foreground = new SolidColorBrush(Color.FromRgb(46, 204, 113)),
                FontWeight = FontWeights.Bold,
                FontSize = 13,
                Margin = new Thickness(10, 10, 10, 5)
            };
            Grid.SetRow(header, 0);
            grid.Children.Add(header);

            _auditLogBox = new TextBox
            {
                IsReadOnly = true,
                Text = "[SYSTEM] Trade Copier Audit Stream Active. Listening for Leader executions...\n",
                Background = new SolidColorBrush(Color.FromRgb(15, 17, 21)),
                Foreground = new SolidColorBrush(Color.FromRgb(46, 204, 113)),
                FontFamily = new FontFamily("Consolas"),
                FontSize = 12,
                Margin = new Thickness(10),
                TextWrapping = TextWrapping.Wrap,
                VerticalScrollBarVisibility = ScrollBarVisibility.Auto
            };
            Grid.SetRow(_auditLogBox, 1);
            grid.Children.Add(_auditLogBox);

            return grid;
        }

        private void PopulateAccountCombosAndCheckboxes()
        {
            var filteredAccounts = GetFilteredAccounts();

            // 1. Save currently checked account names so timer ticks don't wipe out selections
            var previouslyChecked = _accountCheckBoxes
                .Where(cb => cb.IsChecked == true)
                .Select(cb => cb.Content?.ToString())
                .Where(name => !string.IsNullOrEmpty(name))
                .ToHashSet(StringComparer.OrdinalIgnoreCase);

            string currentLeader = _newLeaderCombo.SelectedItem?.ToString();
            string currentFollower = _newFollowerCombo.SelectedItem?.ToString();
            string currentGroupLeader = _groupLeaderCombo.SelectedItem?.ToString();

            _newLeaderCombo.ItemsSource = filteredAccounts;
            if (!string.IsNullOrEmpty(currentLeader) && filteredAccounts.Contains(currentLeader)) _newLeaderCombo.SelectedItem = currentLeader;
            else if (filteredAccounts.Count > 0) _newLeaderCombo.SelectedIndex = 0;

            _newFollowerCombo.ItemsSource = filteredAccounts;
            if (!string.IsNullOrEmpty(currentFollower) && filteredAccounts.Contains(currentFollower)) _newFollowerCombo.SelectedItem = currentFollower;
            else if (filteredAccounts.Count > 1) _newFollowerCombo.SelectedIndex = 1;

            _groupLeaderCombo.ItemsSource = filteredAccounts;
            if (!string.IsNullOrEmpty(currentGroupLeader) && filteredAccounts.Contains(currentGroupLeader)) _groupLeaderCombo.SelectedItem = currentGroupLeader;
            else if (filteredAccounts.Count > 0) _groupLeaderCombo.SelectedIndex = 0;

            // 2. Check if account list changed before wiping UI controls
            var existingNames = _accountCheckBoxes.Select(cb => cb.Content?.ToString()).ToList();
            bool listChanged = !existingNames.SequenceEqual(filteredAccounts);

            if (listChanged || _accountCheckBoxes.Count == 0)
            {
                _accountCheckboxesPanel.Children.Clear();
                _accountCheckBoxes.Clear();

                foreach (var accName in filteredAccounts)
                {
                    var cb = new CheckBox
                    {
                        Content = accName,
                        Foreground = Brushes.White,
                        Margin = new Thickness(0, 3, 0, 3),
                        IsChecked = previouslyChecked.Contains(accName)
                    };
                    _accountCheckBoxes.Add(cb);
                    _accountCheckboxesPanel.Children.Add(cb);
                }
            }
        }

        private void FilterAccountCheckboxes()
        {
            string query = _pickerSearchBox?.Text?.Trim().ToLower() ?? "";
            foreach (var cb in _accountCheckBoxes)
            {
                string name = cb.Content?.ToString().ToLower() ?? "";
                cb.Visibility = string.IsNullOrEmpty(query) || name.Contains(query) ? Visibility.Visible : Visibility.Collapsed;
            }
        }

        public void RefreshUI()
        {
            try
            {
                PopulateAccountCombosAndCheckboxes();

                // Refresh 1:1 Relationships List
                _relationshipsPanel.Children.Clear();
                var rels = TradeCopierEngine.Instance.GetRelationships();

                if (rels.Count == 0)
                {
                    _relationshipsPanel.Children.Add(new TextBlock
                    {
                        Text = "No 1:1 direct relationships configured. Use the form above to add one.",
                        Foreground = Brushes.Gray,
                        Margin = new Thickness(10)
                    });
                }
                else
                {
                    foreach (var rel in rels)
                    {
                        _relationshipsPanel.Children.Add(CreateRelationshipCard(rel));
                    }
                }

                // Refresh Groups List
                _groupsPanel.Children.Clear();
                var groups = TradeCopierEngine.Instance.GetGroups();

                if (groups.Count == 0)
                {
                    _groupsPanel.Children.Add(new TextBlock
                    {
                        Text = "No copier groups configured. Use the form above to create a group.",
                        Foreground = Brushes.Gray,
                        Margin = new Thickness(10)
                    });
                }
                else
                {
                    foreach (var grp in groups)
                    {
                        _groupsPanel.Children.Add(CreateGroupCard(grp));
                    }
                }
            }
            catch (Exception ex)
            {
                Console.WriteLine($"[TradeCopierControl EXCEPTION] {ex.Message}");
            }
        }

        private UIElement CreateRelationshipCard(CopierRelationship rel)
        {
            var card = new Border
            {
                Background = new SolidColorBrush(Color.FromRgb(26, 30, 38)),
                BorderBrush = rel.IsQuarantined ? Brushes.Red : (rel.IsEnabled ? new SolidColorBrush(Color.FromRgb(46, 204, 113)) : Brushes.Gray),
                BorderThickness = new Thickness(1),
                CornerRadius = new CornerRadius(5),
                Padding = new Thickness(12),
                Margin = new Thickness(0, 0, 0, 8)
            };

            var grid = new Grid();
            grid.ColumnDefinitions.Add(new ColumnDefinition { Width = new GridLength(1, GridUnitType.Star) });
            grid.ColumnDefinitions.Add(new ColumnDefinition { Width = GridLength.Auto });

            var info = new StackPanel();
            info.Children.Add(new TextBlock
            {
                Text = $"Leader: {rel.LeaderAccountName} ➔ Follower: {rel.FollowerAccountName}",
                Foreground = Brushes.White,
                FontWeight = FontWeights.Bold,
                FontSize = 14
            });

            string statusText = $"Mode: {rel.SizingMode} | Ratio: {rel.QuantityRatio:F1}x | MaxPos: {rel.MaxPositionSize} | Latency: {rel.LatencyMs:F0}ms | Slippage: {rel.AvgSlippageTicks:F1}t | Stealth: {(rel.StealthMode ? "ON" : "OFF")} | Armed: {(rel.ArmedForLive ? "LIVE" : "SIM")}";
            info.Children.Add(new TextBlock
            {
                Text = statusText,
                Foreground = Brushes.LightGray,
                FontSize = 12,
                Margin = new Thickness(0, 4, 0, 0)
            });

            if (rel.IsQuarantined)
            {
                info.Children.Add(new TextBlock
                {
                    Text = $"⚠️ QUARANTINED: {rel.QuarantineReason ?? "Margin / Order Rejection"}",
                    Foreground = Brushes.Red,
                    FontWeight = FontWeights.Bold,
                    FontSize = 12,
                    Margin = new Thickness(0, 4, 0, 0)
                });
            }

            grid.Children.Add(info);

            var actions = new StackPanel { Orientation = Orientation.Horizontal };

            if (rel.IsQuarantined)
            {
                var resetBtn = new Button
                {
                    Content = "🔄 Reset Quarantine",
                    Background = new SolidColorBrush(Color.FromRgb(231, 76, 60)),
                    Foreground = Brushes.White,
                    Padding = new Thickness(8, 4, 8, 4),
                    Margin = new Thickness(0, 0, 5, 0),
                    BorderThickness = new Thickness(0)
                };
                resetBtn.Click += (s, e) =>
                {
                    rel.IsQuarantined = false;
                    rel.QuarantineReason = null;
                    TradeCopierEngine.Instance.UpsertRelationship(rel, rel.ArmedForLive);
                    TradeCopierEngine.Instance.SaveToDisk(Path.Combine(Globals.UserDataDir, "CopierConfig.json"));
                    RefreshUI();
                };
                actions.Children.Add(resetBtn);
            }

            var toggleBtn = new Button
            {
                Content = rel.IsEnabled ? "⏸ Disable" : "▶ Enable",
                Background = rel.IsEnabled ? new SolidColorBrush(Color.FromRgb(230, 126, 34)) : new SolidColorBrush(Color.FromRgb(46, 204, 113)),
                Foreground = Brushes.White,
                Padding = new Thickness(8, 4, 8, 4),
                Margin = new Thickness(0, 0, 5, 0),
                BorderThickness = new Thickness(0)
            };
            toggleBtn.Click += (s, e) =>
            {
                rel.IsEnabled = !rel.IsEnabled;
                TradeCopierEngine.Instance.UpsertRelationship(rel, rel.ArmedForLive);
                TradeCopierEngine.Instance.SaveToDisk(Path.Combine(Globals.UserDataDir, "CopierConfig.json"));
                RefreshUI();
            };
            actions.Children.Add(toggleBtn);

            var deleteBtn = new Button
            {
                Content = "🗑 Delete",
                Background = new SolidColorBrush(Color.FromRgb(192, 57, 43)),
                Foreground = Brushes.White,
                Padding = new Thickness(8, 4, 8, 4),
                BorderThickness = new Thickness(0)
            };
            deleteBtn.Click += (s, e) =>
            {
                TradeCopierEngine.Instance.RemoveRelationship(rel.LeaderAccountName, rel.FollowerAccountName);
                TradeCopierEngine.Instance.SaveToDisk(Path.Combine(Globals.UserDataDir, "CopierConfig.json"));
                RefreshUI();
            };
            actions.Children.Add(deleteBtn);

            Grid.SetColumn(actions, 1);
            grid.Children.Add(actions);

            card.Child = grid;
            return card;
        }

        private UIElement CreateGroupCard(CopierGroup grp)
        {
            var card = new Border
            {
                Background = new SolidColorBrush(Color.FromRgb(26, 30, 38)),
                BorderBrush = grp.IsEnabled ? new SolidColorBrush(Color.FromRgb(155, 89, 182)) : Brushes.Gray,
                BorderThickness = new Thickness(1),
                CornerRadius = new CornerRadius(5),
                Padding = new Thickness(12),
                Margin = new Thickness(0, 0, 0, 8)
            };

            var grid = new Grid();
            grid.ColumnDefinitions.Add(new ColumnDefinition { Width = new GridLength(1, GridUnitType.Star) });
            grid.ColumnDefinitions.Add(new ColumnDefinition { Width = GridLength.Auto });

            var info = new StackPanel();
            info.Children.Add(new TextBlock
            {
                Text = $"Group: {grp.GroupName} (Leader: {grp.LeaderAccountName})",
                Foreground = Brushes.White,
                FontWeight = FontWeights.Bold,
                FontSize = 14
            });

            string followersStr = (grp.FollowerAccounts != null && grp.FollowerAccounts.Count > 0)
                ? string.Join(", ", grp.FollowerAccounts)
                : "None";

            string statusText = $"Followers ({grp.FollowerAccounts?.Count ?? 0}): [{followersStr}] | Mode: {grp.SizingMode} | Ratio: {grp.QuantityRatio:F1}x | Stealth: {(grp.StealthMode ? "ON" : "OFF")} | Armed: {(grp.ArmedForLive ? "LIVE" : "SIM")}";
            info.Children.Add(new TextBlock
            {
                Text = statusText,
                Foreground = Brushes.LightGray,
                FontSize = 12,
                Margin = new Thickness(0, 4, 0, 0)
            });

            grid.Children.Add(info);

            var actions = new StackPanel { Orientation = Orientation.Horizontal };

            var toggleBtn = new Button
            {
                Content = grp.IsEnabled ? "⏸ Disable Group" : "▶ Enable Group",
                Background = grp.IsEnabled ? new SolidColorBrush(Color.FromRgb(230, 126, 34)) : new SolidColorBrush(Color.FromRgb(46, 204, 113)),
                Foreground = Brushes.White,
                Padding = new Thickness(8, 4, 8, 4),
                Margin = new Thickness(0, 0, 5, 0),
                BorderThickness = new Thickness(0)
            };
            toggleBtn.Click += (s, e) =>
            {
                grp.IsEnabled = !grp.IsEnabled;
                TradeCopierEngine.Instance.UpsertGroup(grp, grp.ArmedForLive);
                TradeCopierEngine.Instance.SaveToDisk(Path.Combine(Globals.UserDataDir, "CopierConfig.json"));
                RefreshUI();
            };
            actions.Children.Add(toggleBtn);

            var deleteBtn = new Button
            {
                Content = "🗑 Delete Group",
                Background = new SolidColorBrush(Color.FromRgb(192, 57, 43)),
                Foreground = Brushes.White,
                Padding = new Thickness(8, 4, 8, 4),
                BorderThickness = new Thickness(0)
            };
            deleteBtn.Click += (s, e) =>
            {
                TradeCopierEngine.Instance.RemoveGroup(grp.GroupName);
                TradeCopierEngine.Instance.SaveToDisk(Path.Combine(Globals.UserDataDir, "CopierConfig.json"));
                RefreshUI();
            };
            actions.Children.Add(deleteBtn);

            Grid.SetColumn(actions, 1);
            grid.Children.Add(actions);

            card.Child = grid;
            return card;
        }

        private void OnAddRelationshipClick(object sender, RoutedEventArgs e)
        {
            try
            {
                string leader = _newLeaderCombo.SelectedItem?.ToString();
                string follower = _newFollowerCombo.SelectedItem?.ToString();

                if (string.IsNullOrEmpty(leader) || string.IsNullOrEmpty(follower))
                {
                    MessageBox.Show("Please select both a Leader and a Follower account.", "Invalid Selection", MessageBoxButton.OK, MessageBoxImage.Warning);
                    return;
                }

                if (leader.Equals(follower, StringComparison.OrdinalIgnoreCase))
                {
                    MessageBox.Show("Leader and Follower cannot be the same account.", "Invalid Relationship", MessageBoxButton.OK, MessageBoxImage.Warning);
                    return;
                }

                double ratio = double.TryParse(_newRatioText.Text, out var r) ? r : 1.0;
                int maxPos = int.TryParse(_newMaxPosText.Text, out var m) ? m : 100;
                bool autoSymbol = _newAutoSymbolCheck.IsChecked ?? true;
                bool stealth = _newStealthCheck.IsChecked ?? true;
                bool armed = _newArmedCheck.IsChecked ?? false;

                var mode = _newSizingModeCombo.SelectedItem?.ToString() == "FixedLot" ? CopierSizingMode.FixedLot : CopierSizingMode.QuantityRatio;

                var rel = new CopierRelationship
                {
                    LeaderAccountName = leader,
                    FollowerAccountName = follower,
                    SizingMode = mode,
                    QuantityRatio = ratio,
                    FixedLotMode = (mode == CopierSizingMode.FixedLot),
                    FixedLotSize = (int)Math.Round(ratio),
                    MaxPositionSize = maxPos,
                    AutoSymbolConversion = autoSymbol,
                    StealthMode = stealth,
                    ArmedForLive = armed,
                    IsEnabled = true
                };

                TradeCopierEngine.Instance.UpsertRelationship(rel, armed);
                TradeCopierEngine.Instance.SaveToDisk(Path.Combine(Globals.UserDataDir, "CopierConfig.json"));

                RefreshUI();
            }
            catch (Exception ex)
            {
                MessageBox.Show($"Error adding relationship: {ex.Message}", "Error", MessageBoxButton.OK, MessageBoxImage.Error);
            }
        }

        private void OnAddGroupClick(object sender, RoutedEventArgs e)
        {
            try
            {
                string grpName = _newGroupNameText.Text?.Trim();
                string leader = _groupLeaderCombo.SelectedItem?.ToString();

                if (string.IsNullOrEmpty(grpName) || string.IsNullOrEmpty(leader))
                {
                    MessageBox.Show("Please enter a Group Name and select a Leader account.", "Invalid Input", MessageBoxButton.OK, MessageBoxImage.Warning);
                    return;
                }

                var selectedFollowers = _accountCheckBoxes
                    .Where(cb => cb.IsChecked == true)
                    .Select(cb => cb.Content.ToString())
                    .Where(f => !f.Equals(leader, StringComparison.OrdinalIgnoreCase))
                    .ToList();

                if (selectedFollowers.Count == 0)
                {
                    MessageBox.Show("Please select at least one follower account using the checkboxes.", "No Followers Selected", MessageBoxButton.OK, MessageBoxImage.Warning);
                    return;
                }

                double ratio = double.TryParse(_groupRatioText.Text, out var r) ? r : 1.0;
                int maxPos = int.TryParse(_groupMaxPosText.Text, out var m) ? m : 100;
                bool autoSymbol = _groupAutoSymbolCheck.IsChecked ?? true;
                bool stealth = _groupStealthCheck.IsChecked ?? true;
                bool armed = _groupArmedCheck.IsChecked ?? false;

                var mode = _groupSizingModeCombo.SelectedItem?.ToString() == "FixedLot" ? CopierSizingMode.FixedLot : CopierSizingMode.QuantityRatio;

                var grp = new CopierGroup
                {
                    GroupName = grpName,
                    LeaderAccountName = leader,
                    FollowerAccounts = selectedFollowers,
                    SizingMode = mode,
                    QuantityRatio = ratio,
                    FixedLotMode = (mode == CopierSizingMode.FixedLot),
                    FixedLotSize = (int)Math.Round(ratio),
                    MaxPositionSize = maxPos,
                    AutoSymbolConversion = autoSymbol,
                    StealthMode = stealth,
                    ArmedForLive = armed,
                    IsEnabled = true
                };

                TradeCopierEngine.Instance.UpsertGroup(grp, armed);
                TradeCopierEngine.Instance.SaveToDisk(Path.Combine(Globals.UserDataDir, "CopierConfig.json"));

                RefreshUI();
            }
            catch (Exception ex)
            {
                MessageBox.Show($"Error adding group: {ex.Message}", "Error", MessageBoxButton.OK, MessageBoxImage.Error);
            }
        }

        private void OnPanicAllClick(object sender, RoutedEventArgs e)
        {
            var result = MessageBox.Show("Are you sure you want to FLATTEN ALL ACCOUNTS and stop copying?", "Emergency Panic Button", MessageBoxButton.YesNo, MessageBoxImage.Exclamation);
            if (result == MessageBoxResult.Yes)
            {
                try
                {
                    foreach (var acc in Account.All)
                    {
                        acc.Flatten(acc.Positions.Select(p => p.Instrument).ToList());
                    }
                    MessageBox.Show("All account positions flattened.", "Panic Execution Complete", MessageBoxButton.OK, MessageBoxImage.Information);
                }
                catch (Exception ex)
                {
                    MessageBox.Show($"Error flattening accounts: {ex.Message}", "Panic Error", MessageBoxButton.OK, MessageBoxImage.Error);
                }
            }
        }
    }

    public class TradeCopierWindow : Window
    {
        public TradeCopierWindow()
        {
            Title = "NinjaTrader Next-Gen Trade Copier & Group Suite v1.2.0";
            Width = 1000;
            Height = 720;
            Background = new SolidColorBrush(Color.FromRgb(18, 21, 27)); // Slate Dark Mode
            WindowStartupLocation = WindowStartupLocation.CenterScreen;

            Content = new TradeCopierControl();
        }
    }
}
#endif
