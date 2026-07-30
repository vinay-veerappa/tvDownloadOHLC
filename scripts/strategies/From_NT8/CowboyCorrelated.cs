#region Using declarations
using System;
using System.ComponentModel.DataAnnotations;
using System.Windows;
using System.Windows.Media;
using NinjaTrader.Cbi;
using NinjaTrader.Gui.Chart;
using NinjaTrader.Data;
using NinjaTrader.NinjaScript.Indicators;
using System.Windows.Controls;
using NinjaTrader.NinjaScript.DrawingTools;
using System.ComponentModel;
#endregion

//This namespace holds Strategies in this folder and is required. Do not change it. 
namespace NinjaTrader.NinjaScript.Strategies
{
    public class CowboyCorrelated : Strategy
    {
        #region Variables
        private string timeStr;
        private int thisTime;

        private Order longEntry1 = null;
        private Order shortEntry1 = null;

        private Order longEntry2 = null;
        private Order shortEntry2 = null;

        private Order longEntry3 = null;
        private Order shortEntry3 = null;

        private Order correlatedLongEntry1 = null;
        private Order correlatedShortEntry1 = null;

        private Order correlatedLongEntry2 = null;
        private Order correlatedShortEntry2 = null;

        private Order correlatedLongEntry3 = null;
        private Order correlatedShortEntry3 = null;

        private Order correlatedManualLong = null;
        private Order correlatedManualShort = null;

        private Order manualLong = null;  // 
        private Order manualShort = null;

        private Order stopOrder = null;
        private Order profitOrder1 = null;
        private Order profitOrder2 = null;
        private Order profitOrder3 = null;

        private Order correlatedStopOrder = null;
        private Order correlatedProfitOrder1 = null;
        private Order correlatedProfitOrder2 = null;
        private Order correlatedProfitOrder3 = null;

        private bool entryTime1Once = false;
        private bool entryTime2Once = false;
        private bool entryTime3Once = false;

        private Grid CowboyGrid;
        #region CowboySettingsGrid
        // So, how do you accomplish this?  You create a grid (CowboySettingsGrid) with two columns on one row.  
        // The 1st column is the button (CowboyButton) that places the orders.  Click it and the orders are placed.
        // The 2nd column holds a panel (CowboyTicksPanel).  
        // That panel has a horizontal orientation that holds two controls, the Offset text box (CowboyOffsetTextBox) and another panel (CowboyUpDownBtnPanel)
        // The CowboyUpDownBtnPanel has a vertical orientation that holds the up/down buttons. (CowboyBtnUp and CowboyBtnDown)
        // Got all that?  The hardest part is keeping it all straight.  When you are finished, you end up with the entire control (CowboySettingsGrid)
        // that is placed in the CowboyGrid along with the Flatten button.  Easy peasy.
        private Grid CowboySettingsGrid = null;        
        private Button CowboyButton = null;          
        private StackPanel CowboyTicksPanel = null;  
        private TextBox CowboyOffsetTextBox = null;  
        private StackPanel CowboyUpDownBtnPanel = null;
        private Button CowboyBtnUp = null;           
        private Button CowboyBtnDown = null;         
        #endregion
        private Button FlattenButton;
        private Button UseCorrelatedButton;
        private double LastPrice = -1;
        private double HighWater = 0.00;
        private bool BEHit = false;

        private double correlatedLastPrice = -1;
        private double correlatedHighWater = 0.00;
        private bool correlatedBEHit = false;
        private Button InverseCorrelationButton;
        private Button EnterLongButton;
        private Button EnterShortButton;
        #endregion

        #region OnStateChange
        protected override void OnStateChange()
        {
            if (State == State.SetDefaults)
            {
                Description = @"The strategy enters a cowboy trade, or one that will place a long order x ticks above a certain price and a short order x ticks below a certain price.";
                Name = "CowboyCorrelated";
                Calculate = Calculate.OnBarClose;
                IsExitOnSessionCloseStrategy = true;
                ExitOnSessionCloseSeconds = 30;
                IsFillLimitOnTouch = false;
                MaximumBarsLookBack = MaximumBarsLookBack.TwoHundredFiftySix;
                OrderFillResolution = OrderFillResolution.Standard;
                Slippage = 0;
                StartBehavior = StartBehavior.WaitUntilFlat;
                TimeInForce = TimeInForce.Gtc;
                TraceOrders = false;
                RealtimeErrorHandling = RealtimeErrorHandling.StopCancelClose;
                StopTargetHandling = StopTargetHandling.PerEntryExecution;
                BarsRequiredToTrade = 20;
                // Disable this property for performance gains in Strategy Analyzer optimizations
                // See the Help Guide for additional information
                IsInstantiatedOnEachOptimizationIteration = true;
                IsUnmanaged = true;

                Qty = 3;
                Offset = 15;

                TimeEntry1 = -1;
                Sunday1 = true;
                Monday1 = true;
                Tuesday1 = true;
                Wednesday1 = true;
                Thursday1 = true;
                Friday1 = true;

                TimeEntry2 = -1;
                Sunday2 = true;
                Monday2 = true;
                Tuesday2 = true;
                Wednesday2 = true;
                Thursday2 = true;
                Friday2 = true;

                TimeEntry3 = -1;
                Sunday3 = true;
                Monday3 = true;
                Tuesday3 = true;
                Wednesday3 = true;
                Thursday3 = true;
                Friday3 = true;

                StopLoss = 45;
                ProfitTarget1 = 40;
                ProfitTarget2 = 55;
                ProfitTarget3 = 70;

                ProfitTarget1Qty = 1;
                ProfitTarget2Qty = 1;
                ProfitTarget3Qty = 1;

                MoveToBE = false;
                TriggerBE = 35;

                CorrelatedStopLoss = 45;
                CorrelatedProfitTarget1 = 40;
                CorrelatedProfitTarget2 = 55;
                CorrelatedProfitTarget3 = 70;

                CorrelatedProfitTarget1Qty = 1;
                CorrelatedProfitTarget2Qty = 1;
                CorrelatedProfitTarget3Qty = 1;

                MoveToBECorrelated = false;
                TriggerBECorrelated = 35;

                UseCorrelatedDataSeries = true;
                InverseCorrelatedTrades = false;
                CorrelatedDataSeriesInstrument = "YM 09-20";
            }
            else if (State == State.Configure)
            {
                // The data series we trade off the chart
                AddDataSeries(BarsPeriodType.Second, 1);

                // The background data series we trade off the correlated market
                // Always load the correlated data series.  The user may have it off at first but could change his/her mind
                AddDataSeries( CorrelatedDataSeriesInstrument, BarsPeriodType.Second, 1 );
            }
            else if( State == State.DataLoaded )
            {
                if ( ChartControl != null )
                {
                    ChartControl.Dispatcher.InvokeAsync((() =>
                    {
                        // Grid already exists
                        if (UserControlCollection.Contains(CowboyGrid))
                        {
                            return;
                        }
                        else
                        {
                            AddCowboyGrid();
                        }
                    }));
                }
            }
            else if (State == State.Terminated)
            {
                if (ChartControl == null)
                    return;

                // Again, we need to use a Dispatcher to interact with the UI elements
                ChartControl.Dispatcher.InvokeAsync((() =>
                {
                    // Unwind these in reverse order.  Start with the very inside and work your way out
                    if (CowboyGrid != null)
                    {
                        if (CowboySettingsGrid != null)
                        {
                            // First the button on the left side of the  CowboySettingsGrid
                            if (CowboyButton != null)
                            {
                                CowboySettingsGrid.Children.Remove(CowboyButton);
                                CowboyButton = null;
                            }
                            // Then the panel that ...
                            if (CowboyTicksPanel != null)
                            {
                                // holds the offset text box ...
                                if (CowboyOffsetTextBox != null)
                                {
                                    CowboyTicksPanel.Children.Remove(CowboyOffsetTextBox);
                                    CowboyOffsetTextBox = null;
                                }
                                // and the up/down buttons panel
                                if (CowboyUpDownBtnPanel != null)
                                {
                                    if (CowboyBtnUp != null)
                                    {
                                        CowboyUpDownBtnPanel.Children.Remove(CowboyBtnUp);
                                        CowboyBtnUp = null;
                                    }
                                    if (CowboyBtnDown != null)
                                    {
                                        CowboyUpDownBtnPanel.Children.Remove(CowboyBtnDown);
                                        CowboyBtnDown = null;
                                    }
                                    CowboySettingsGrid.Children.Remove(CowboyUpDownBtnPanel);
                                    CowboyUpDownBtnPanel = null;
                                }
                                CowboySettingsGrid.Children.Remove(CowboyTicksPanel);
                                CowboyTicksPanel = null;
                            }
                            CowboyGrid.Children.Remove(CowboySettingsGrid);
                            CowboySettingsGrid = null;
                        }

                        if (EnterLongButton != null)
                        {
                            CowboyGrid.Children.Remove(EnterLongButton);
                            EnterLongButton.Click -= EnterLongButton_Click;
                            EnterLongButton = null;
                        }

                        if( EnterShortButton != null)
                        {
                            CowboyGrid.Children.Remove(EnterShortButton);
                            EnterShortButton.Click -= EnterShortButton_Click;
                            EnterShortButton = null;
                        }

                        if (FlattenButton != null)
                        {
                            CowboyGrid.Children.Remove(FlattenButton);
                            FlattenButton.Click -= FlattenButton_Click;
                            FlattenButton = null;
                        }

                        if( UseCorrelatedButton != null)
                        {
                            CowboyGrid.Children.Remove(UseCorrelatedButton);
                            UseCorrelatedButton.Click -= UseCorrelatedButton_Click;
                            UseCorrelatedButton = null;
                        }

                        if (InverseCorrelationButton != null)
                        {
                            CowboyGrid.Children.Remove(InverseCorrelationButton);
                            InverseCorrelationButton.Click -= InverseCorrelationButton_Click;
                            InverseCorrelationButton = null;
                        }

                        CowboyGrid = null;
                    }
                }));
            }
        }

        private void AddCowboyGrid()
        {
            double buttonHeight = 25;
            double buttonWidth = 175;
            int buttonFontSize = 12;
            Brush borderColor = Brushes.Black;
            Thickness borderThickness = new Thickness(0);

            int cowboyButtonColumnWidth = (int)Math.Floor(buttonWidth * 0.67); // CowboyButton column width
            int orderOffsetColumnWidth = (int)Math.Floor(buttonWidth * 0.33); // CowboyTicksPanel column "control" column width

            int orderTextColumnWidth = orderOffsetColumnWidth * 4 / 7;  // Defines the widths of the Offset text control
            int upDownButtonsColumnWidth = orderOffsetColumnWidth * 3 / 7;  // Defines the widths of the Up/Down buttons 

            // Add a control grid which will host our custom buttons
            CowboyGrid = new Grid
            {
                Name = "CowboyGrid",
                Width = buttonWidth,                  // Align the control to the top left corner of the chart
                HorizontalAlignment = HorizontalAlignment.Left,
                VerticalAlignment = VerticalAlignment.Top,
                Margin = new Thickness(5, 20, 0, 0)
            };

            CowboyGrid.RowDefinitions.Add(new RowDefinition());  // CowboySettingsGrid
            CowboyGrid.RowDefinitions.Add(new RowDefinition());  // Long Market button
            CowboyGrid.RowDefinitions.Add(new RowDefinition());  // Short Market button
            CowboyGrid.RowDefinitions.Add(new RowDefinition());  // FlattenButton
            CowboyGrid.RowDefinitions.Add(new RowDefinition());  // UseCorrelatedButton
            CowboyGrid.RowDefinitions.Add(new RowDefinition());  // InverseCorrelationButton

            CowboyGrid.ColumnDefinitions.Add( new ColumnDefinition() ); 
 
            #region CowboyTicksGrid
            CowboySettingsGrid = new Grid
            {
                Name = "CowboySettingsGrid",
                Width = buttonWidth,                  // Align the control to the top left corner of the chart
                HorizontalAlignment = HorizontalAlignment.Left,
                VerticalAlignment = VerticalAlignment.Top,
                //Margin = new Thickness(5, 25, 0, 0)
            };

            // The left side of the row is the CowboyButton
            CowboyButton = new Button
            {
                Name = "CowboyButton",
                Content = "Cowboy",
                Foreground = Brushes.Black,
                Background = Brushes.PaleGreen,
                FontWeight = FontWeights.DemiBold,
                FontSize = buttonFontSize,
                Width = cowboyButtonColumnWidth,
                Height = buttonHeight,
                HorizontalContentAlignment = HorizontalAlignment.Center,
                HorizontalAlignment = HorizontalAlignment.Center,
                VerticalAlignment = VerticalAlignment.Bottom,
                BorderBrush = borderColor,
                BorderThickness = borderThickness,
                Margin = new Thickness(0, 0, 0, 2),
                ToolTip = "Click to enter an order (x) ticks above and (x) ticks below the previous close"
            };
            CowboyButton.Click += CowboyButton_Click;

            // The right side of the row is the CowboyTicksPanel
            CowboyTicksPanel = new StackPanel
            {
                Orientation = Orientation.Horizontal,
                Name = "CowboyTicksPanel",
                Width = orderOffsetColumnWidth,
                HorizontalAlignment = HorizontalAlignment.Right,
                VerticalAlignment = VerticalAlignment.Center,
            };

            // The CowboyTicksPanel consists of a textbox and StackPanel, which consists of the two up/down buttons
            CowboyOffsetTextBox = new TextBox 
            {
                Name = "CowboyOffsetTextBox",
                FontWeight = FontWeights.Bold,
                Width = orderTextColumnWidth,
                Text = Offset.ToString(),
                TextAlignment = TextAlignment.Center,
                HorizontalAlignment = HorizontalAlignment.Left,
                HorizontalContentAlignment = HorizontalAlignment.Left,
                IsReadOnly = true,
                ToolTip = "Number of ticks the buy order is placed above and the sell order is placed below the previous close."
            };
            CowboyUpDownBtnPanel = new StackPanel     
            {
                Name = "CowboyUpDownBtnPanel",
                Orientation = Orientation.Vertical,
                Width = orderOffsetColumnWidth,
                HorizontalAlignment = HorizontalAlignment.Right,
                VerticalAlignment = VerticalAlignment.Center,
            };
            CowboyBtnUp = new Button
            {
                Height = 12,
                Name = "CowboyBtnUp",
                Width = upDownButtonsColumnWidth
            };
            CowboyBtnUp.Click += LongOrderBtnUp_Click;
            CowboyBtnDown = new Button
            {
                Height = 12,
                Name = "CowboyBtnDown",
                Width = upDownButtonsColumnWidth
            };
            CowboyBtnDown.Click += CowboyBtnDown_Click;

            // Load the two up/down buttons into the CowboyUpDownBtnPanel stackpanel
            CowboyUpDownBtnPanel.Children.Add(CowboyBtnUp);
            CowboyUpDownBtnPanel.Children.Add(CowboyBtnDown);

            // Now add the stackpanel and the Text Box to the CowboyTicksPanel
            CowboyTicksPanel.Children.Add(CowboyOffsetTextBox);
            CowboyTicksPanel.Children.Add(CowboyUpDownBtnPanel);

            // Now add the CowboyTicksPanel and Cowboy button to the strategy grid
            ColumnDefinition CowboyBtnCol = new ColumnDefinition();
            ColumnDefinition CowboyTicksCol = new ColumnDefinition();
            CowboyBtnCol.Width = new GridLength(cowboyButtonColumnWidth, GridUnitType.Star);
            CowboyTicksCol.Width = new GridLength(orderOffsetColumnWidth, GridUnitType.Star);

            CowboySettingsGrid.ColumnDefinitions.Add(CowboyBtnCol); // button column
            CowboySettingsGrid.ColumnDefinitions.Add(CowboyTicksCol); // offset panel column
            CowboySettingsGrid.RowDefinitions.Add(new RowDefinition());

            CowboySettingsGrid.Children.Add(CowboyButton);
            CowboySettingsGrid.Children.Add(CowboyTicksPanel);
            #endregion

            EnterLongButton = new Button
            {
                Name = "EnterLongButton",
                Content = "Long Market",
                Foreground = Brushes.Black,
                Background = Brushes.LightPink,
                FontWeight = FontWeights.DemiBold,
                FontSize = buttonFontSize,
                Width = buttonWidth,
                Height = buttonHeight,
                HorizontalContentAlignment = HorizontalAlignment.Center,
                HorizontalAlignment = HorizontalAlignment.Left,
                VerticalAlignment = VerticalAlignment.Bottom,
                BorderBrush = borderColor,
                BorderThickness = borderThickness,
                Margin = new Thickness(0, 0, 0, 1),
                ToolTip = "Initiates a manual entry in the long direction"
            };
            EnterLongButton.Click += EnterLongButton_Click;

            EnterShortButton = new Button
            {
                Name = "EnterShortButton",
                Content = "Short Market",
                Foreground = Brushes.Black,
                Background = Brushes.LightPink,
                FontWeight = FontWeights.DemiBold,
                FontSize = buttonFontSize,
                Width = buttonWidth,
                Height = buttonHeight,
                HorizontalContentAlignment = HorizontalAlignment.Center,
                HorizontalAlignment = HorizontalAlignment.Left,
                VerticalAlignment = VerticalAlignment.Bottom,
                BorderBrush = borderColor,
                BorderThickness = borderThickness,
                Margin = new Thickness(0, 0, 0, 1),
                ToolTip = "Initiates a manual entry in the short direction"
            };
            EnterShortButton.Click += EnterShortButton_Click;

            FlattenButton = new Button
            {
                Name = "FlattenButton",
                Content = "Flatten / Cancel orders",
                Style = null,
                Foreground = Brushes.Black,
                Background = Brushes.LightPink,
                FontWeight = FontWeights.DemiBold,
                FontSize = buttonFontSize,
                Width = buttonWidth,
                Height = buttonHeight,
                HorizontalContentAlignment = HorizontalAlignment.Center,
                HorizontalAlignment = HorizontalAlignment.Left,
                VerticalAlignment = VerticalAlignment.Bottom,
                BorderBrush = borderColor,
                BorderThickness = borderThickness,
                Margin = new Thickness(0, 0, 0, 1),
                ToolTip = "Flattens the trade and cancels all orders"
            };
            FlattenButton.Click += FlattenButton_Click;

            UseCorrelatedButton = new Button
            {
                Name = "UseCorrelatedButton",
                Content = "Use correlated data series?",
                Style = null,
                Foreground = UseCorrelatedDataSeries == true ? Brushes.Black : Brushes.Gray,
                Background = UseCorrelatedDataSeries == true ? Brushes.Cyan : Brushes.Silver,
                FontWeight = FontWeights.DemiBold,
                FontSize = buttonFontSize,
                Width = buttonWidth,
                Height = buttonHeight,
                HorizontalContentAlignment = HorizontalAlignment.Center,
                HorizontalAlignment = HorizontalAlignment.Left,
                VerticalAlignment = VerticalAlignment.Bottom,
                BorderBrush = borderColor,
                BorderThickness = borderThickness,
                Margin = new Thickness(0, 0, 0, 1),
                ToolTip = "Toggle button to switch back and forth from entering trades on a secondary data series"
            };
            UseCorrelatedButton.Click += UseCorrelatedButton_Click;

            InverseCorrelationButton = new Button
            {
                Name = "InverseCorrelation",
                Content = "Inverse correlated entries?",
                Style = null,
                Foreground = InverseCorrelatedTrades == true ? Brushes.Black : Brushes.Gray,
                Background = InverseCorrelatedTrades == true ? Brushes.Cyan : Brushes.Silver,
                FontWeight = FontWeights.DemiBold,
                FontSize = buttonFontSize,
                Width = buttonWidth,
                Height = buttonHeight,
                HorizontalContentAlignment = HorizontalAlignment.Center,
                HorizontalAlignment = HorizontalAlignment.Left,
                VerticalAlignment = VerticalAlignment.Bottom,
                BorderBrush = borderColor,
                BorderThickness = borderThickness,
                Margin = new Thickness(0, 0, 0, 1),
                ToolTip = "For the correlated data series, execute trades opposite to the primary data series on the chart."
            };
            InverseCorrelationButton.Click += InverseCorrelationButton_Click;

            Grid.SetRow(CowboyButton, 0);
            Grid.SetColumn(CowboyButton, 0);
            Grid.SetColumn(CowboyTicksPanel, 1);
            Grid.SetRow(CowboySettingsGrid, 0);

            Grid.SetRow(EnterLongButton, 1);
            Grid.SetColumn(EnterLongButton, 0);

            Grid.SetRow(EnterShortButton, 2);
            Grid.SetColumn(EnterShortButton, 0);

            Grid.SetRow(FlattenButton, 3);
            Grid.SetColumn(FlattenButton, 0);

            Grid.SetRow( UseCorrelatedButton, 4);
            Grid.SetColumn( UseCorrelatedButton, 0);

            Grid.SetRow(InverseCorrelationButton, 5);
            Grid.SetColumn(InverseCorrelationButton, 0);

            CowboyGrid.Children.Add(CowboySettingsGrid);
            CowboyGrid.Children.Add(EnterLongButton);
            CowboyGrid.Children.Add(EnterShortButton);
            CowboyGrid.Children.Add(FlattenButton);
            CowboyGrid.Children.Add(UseCorrelatedButton);
            CowboyGrid.Children.Add(InverseCorrelationButton);

            UserControlCollection.Add(CowboyGrid);

        }

        private void InverseCorrelationButton_Click(object sender, RoutedEventArgs e)
        {
            InverseCorrelatedTrades = !InverseCorrelatedTrades;

            if (InverseCorrelatedTrades == true)
            {
                InverseCorrelationButton.Background = Brushes.Cyan;
                InverseCorrelationButton.Foreground = Brushes.Black;
            }
            else
            {
                InverseCorrelationButton.Background = Brushes.Silver;
                InverseCorrelationButton.Foreground = Brushes.Gray;
            }
        }

        #region Cowboy grid event handlers
        // Manually enters a short trade at the market
        private void EnterShortButton_Click(object sender, RoutedEventArgs e)
        {
            if (Position.MarketPosition == MarketPosition.Flat)
            {
                manualShort = SubmitOrderUnmanaged(1, OrderAction.SellShort, OrderType.Market, Qty, 0, 0, "", "ManualEntry" );
            }
        }

        // Manually enters a long trade at the market
        private void EnterLongButton_Click(object sender, RoutedEventArgs e)
        {
            if (Position.MarketPosition == MarketPosition.Flat)
            {
                manualLong = SubmitOrderUnmanaged(1, OrderAction.Buy, OrderType.Market, Qty, 0, 0, "", "ManualEntry");
            }
        }

        private void UseCorrelatedButton_Click(object sender, RoutedEventArgs e)
        {
            UseCorrelatedDataSeries = !UseCorrelatedDataSeries;

            if( UseCorrelatedDataSeries == true )
            {
                UseCorrelatedButton.Background = Brushes.Cyan;
                UseCorrelatedButton.Foreground = Brushes.Black;
            }
            else
            {
                UseCorrelatedButton.Background = Brushes.Silver;
                UseCorrelatedButton.Foreground = Brushes.Gray;
            }
        }

        private void FlattenButton_Click(object sender, RoutedEventArgs e)
        {
            if( Positions[1].MarketPosition == MarketPosition.Long )
            {
                SubmitOrderUnmanaged(1, OrderAction.Sell, OrderType.Market, Positions[1].Quantity, 0, 0, "", "Manual exit");
            }
            else if( Positions[1].MarketPosition == MarketPosition.Short )
            {
                SubmitOrderUnmanaged(1, OrderAction.BuyToCover, OrderType.Market, Positions[1].Quantity, 0, 0, "", "Manual exit");
            }

            if (Positions[2].MarketPosition == MarketPosition.Long)
            {
                SubmitOrderUnmanaged(2, OrderAction.Sell, OrderType.Market, Positions[2].Quantity, 0, 0, "", "Correlated Manual exit");
            }
            else if (Positions[2].MarketPosition == MarketPosition.Short)
            {
                SubmitOrderUnmanaged(2, OrderAction.BuyToCover, OrderType.Market, Positions[2].Quantity, 0, 0, "", "Correlated Manual exit");
            }
                        
            // Cancel orders
            if (longEntry1 != null )
            {
                CancelOrder(longEntry1);
            }
            if (shortEntry1 != null)
            {
                CancelOrder(shortEntry1);
            }
            if (longEntry2 != null)
            {
                CancelOrder(longEntry2);
            }
            if (shortEntry2 != null)
            {
                CancelOrder(shortEntry2);
            }
            if (longEntry3 != null)
            {
                CancelOrder(longEntry2);
            }
            if (shortEntry3 != null)
            {
                CancelOrder(shortEntry2);
            }

            if (manualLong != null)
            {
                CancelOrder(manualLong);
            }
            if (manualShort != null)
            {
                CancelOrder(manualShort);
            }

            if (correlatedManualLong != null)
            {
                CancelOrder(correlatedManualLong);
            }
            if (correlatedManualShort != null)
            {
                CancelOrder(correlatedManualShort);
            }

        }

		// Adjusts the tick offset for the order placement in the negative direction
        private void CowboyBtnDown_Click(object sender, RoutedEventArgs e)
        {
            Offset -= 1;
            if( Offset < 1 )
            {
                Offset = 1;
            }
            CowboyOffsetTextBox.Text = Offset.ToString();
        }

        // Adjusts the tick offset for the order placement in the positive direction
        private void LongOrderBtnUp_Click(object sender, RoutedEventArgs e)
        {
            Offset += 1;
            CowboyOffsetTextBox.Text = Offset.ToString();
        }

        // Places a "cowboy trade"
        private void CowboyButton_Click(object sender, RoutedEventArgs e)
        {
            EnterCowboyTrade(4, "ManualEntry");
        }
        #endregion
        #endregion

        public override string DisplayName
        {
            get
            {
                return "Cowboy (correlated)";
            }
        }
  
        protected override void OnBarUpdate()
        {
            if( CurrentBars[0] < BarsRequiredToTrade
                || CurrentBars[1] < BarsRequiredToTrade) return;

            if (BarsInProgress == 1
                && IsFirstTickOfBar)
            {
                if (State == State.Historical)
                {
                    if( Positions[1].MarketPosition != MarketPosition.Flat
                        && Positions[1].Quantity > 0)
                    {
                        if (Positions[1].MarketPosition == MarketPosition.Long)
                        {
                            HighWater = Math.Max(Closes[1][0], HighWater);
                        }
                        else if (Positions[1].MarketPosition == MarketPosition.Short)
                        {
                            HighWater = Math.Min(Closes[1][0], HighWater);
                        }
                        else
                        {
                            HighWater = 0;
                        }
                        // ...or move the trailing stops
                        CheckMoveStopLossBE();
                    }
                    else if( Positions[2].MarketPosition != MarketPosition.Flat
                             && Positions[2].Quantity > 0)
                    {
                        if( Positions[2].MarketPosition == MarketPosition.Long )
                        {
                            correlatedHighWater = Math.Max(Closes[2][0], correlatedHighWater );
                        }
                        else if (Positions[2].MarketPosition == MarketPosition.Short)
                        {
                            correlatedHighWater = Math.Min(Closes[2][0], correlatedHighWater );
                        }
                        else
                        {
                            correlatedHighWater = 0;
                        }
                        // ...or move the trailing stops
                        CheckMoveStopLossBE();
                    }
                }

                // Entry
                if (Positions[1].MarketPosition == MarketPosition.Flat)
                {
                    thisTime = ToTime(Times[1][0]);

                    if (TimeEntry1 >= 0
                        && thisTime >= TimeEntry1
                        && thisTime < TimeEntry1 + 20
                        && entryTime1Once == false
                        && CanTradeToday(1) )
                    {
                        entryTime1Once = true;
                        EnterCowboyTrade(1, "Entry1");
                    }
                    else if (TimeEntry2 >= 0
                             && thisTime >= TimeEntry2
                             && thisTime < TimeEntry2 + 20
                             && entryTime2Once == false
                             && CanTradeToday(2) )
                    {
                        entryTime2Once = true;
                        EnterCowboyTrade(2, "Entry2");
                    }
                    else if (TimeEntry3 >= 0
                             && thisTime >= TimeEntry3
                             && thisTime < TimeEntry3 + 20
                             && entryTime3Once == false
                             && CanTradeToday(3) )
                    {
                        entryTime3Once = true;
                        EnterCowboyTrade(3, "Entry3");
                    }
                }
            }
            else if( BarsInProgress == 0
                     && Bars.IsFirstBarOfSession == true)
            {
                entryTime1Once = false;
                entryTime2Once = false;
                entryTime3Once = false;

                longEntry1 = null;
                shortEntry1 = null;
                longEntry2 = null;
                shortEntry2 = null;
                longEntry3 = null;
                shortEntry3 = null;

                manualLong = null;
                manualShort = null;

                correlatedManualLong = null;
                correlatedManualShort = null;
            }

        }

        private bool CanTradeToday( int idx )
        {
            bool retVal = true;

            DateTime today = Times[1][0].ToLocalTime();

            switch( idx )
            {
                case 1:
                    if( today.DayOfWeek == DayOfWeek.Sunday
                        && Sunday1 == false )
                    {
                        retVal = false;
                    }
                    else if( today.DayOfWeek == DayOfWeek.Monday
                             && Monday1 == false)
                    {
                        retVal = false;
                    }
                    else if (today.DayOfWeek == DayOfWeek.Tuesday
                             && Tuesday1 == false)
                    {
                        retVal = false;
                    }
                    else if (today.DayOfWeek == DayOfWeek.Wednesday
                             && Wednesday1 == false)
                    {
                        retVal = false;
                    }
                    else if (today.DayOfWeek == DayOfWeek.Thursday
                             && Thursday1 == false)
                    {
                        retVal = false;
                    }
                    else if (today.DayOfWeek == DayOfWeek.Friday
                             && Friday1 == false)
                    {
                        retVal = false;
                    }
                    break;

                case 2:
                    if (today.DayOfWeek == DayOfWeek.Sunday
                        && Sunday2 == false)
                    {
                        retVal = false;
                    }
                    else if (today.DayOfWeek == DayOfWeek.Monday
                             && Monday2 == false)
                    {
                        retVal = false;
                    }
                    else if (today.DayOfWeek == DayOfWeek.Tuesday
                             && Tuesday2 == false)
                    {
                        retVal = false;
                    }
                    else if (today.DayOfWeek == DayOfWeek.Wednesday
                             && Wednesday2 == false)
                    {
                        retVal = false;
                    }
                    else if (today.DayOfWeek == DayOfWeek.Thursday
                             && Thursday2 == false)
                    {
                        retVal = false;
                    }
                    else if (today.DayOfWeek == DayOfWeek.Friday
                             && Friday2 == false)
                    {
                        retVal = false;
                    }
                    break;

                case 3:
                    if (today.DayOfWeek == DayOfWeek.Sunday
                        && Sunday3 == false)
                    {
                        retVal = false;
                    }
                    else if (today.DayOfWeek == DayOfWeek.Monday
                             && Monday3 == false)
                    {
                        retVal = false;
                    }
                    else if (today.DayOfWeek == DayOfWeek.Tuesday
                             && Tuesday3 == false)
                    {
                        retVal = false;
                    }
                    else if (today.DayOfWeek == DayOfWeek.Wednesday
                             && Wednesday3 == false)
                    {
                        retVal = false;
                    }
                    else if (today.DayOfWeek == DayOfWeek.Thursday
                             && Thursday3 == false)
                    {
                        retVal = false;
                    }
                    else if (today.DayOfWeek == DayOfWeek.Friday
                             && Friday3 == false)
                    {
                        retVal = false;
                    }
                    break;

            }

            return retVal;
        }

        protected override void OnMarketData(MarketDataEventArgs e)
        {
            if (CurrentBars[0] < BarsRequiredToTrade
                || CurrentBars[1] < BarsRequiredToTrade) return;

            base.OnMarketData(e);

            if( e.MarketDataType == MarketDataType.Last )
            {
                if( BarsInProgress == 1 )
                {
                    try
                    {
                        if (Times[1][0] != null)
                        {
                            timeStr = Times[1][0].TimeOfDay.ToString();
                        }
                    }
                    catch { }
                }

                if (BarsInProgress == 1)
                {
                    if (LastPrice > 0)
                    {
                        // Update HighWaters
                        if( Positions[1].MarketPosition != MarketPosition.Flat
                            && Positions[1].Quantity > 0)
                        {
                            if (Positions[1].MarketPosition == MarketPosition.Long)
                            {
                                HighWater = Math.Max(e.Price, HighWater);
                            }
                            else if (Positions[1].MarketPosition == MarketPosition.Short)
                            {
                                HighWater = Math.Min(e.Price, HighWater);
                            }
                        }
                        else
                        {
                            HighWater = 0;
                        }
                    }
                    LastPrice = e.Price;
                }
                else if( BarsInProgress == 2 )
                {
                    if( correlatedLastPrice > 0 )
                    {
                        // Update HighWaters
                        if(Positions[2].MarketPosition != MarketPosition.Flat
                            && Positions[2].Quantity > 0)
                        {
                            if (Positions[2].MarketPosition == MarketPosition.Long)
                            {
                                correlatedHighWater = Math.Max(e.Price, correlatedHighWater);
                            }
                            else if (Positions[2].MarketPosition == MarketPosition.Short)
                            {
                                correlatedHighWater = Math.Min(e.Price, correlatedHighWater);
                            }
                        }
                        else
                        {
                            correlatedHighWater = 0;
                        }
                    }
                    correlatedLastPrice = e.Price;
                }

                // Manage each position on every other tick in the same direction
                CheckMoveStopLossBE();
            }

        }

        protected override void OnPositionUpdate(Position position, double averagePrice, int quantity, MarketPosition marketPosition)
        {
            base.OnPositionUpdate(position, averagePrice, quantity, marketPosition);

            if( Positions[1].MarketPosition == MarketPosition.Flat )
            {
                manualLong = null;
                manualShort = null;

                longEntry1 = shortEntry1 = longEntry2 = shortEntry2 = longEntry3 = shortEntry3 = null;
                BEHit = false;

                correlatedLongEntry1 = correlatedShortEntry1 = correlatedLongEntry2 = correlatedShortEntry2 = correlatedLongEntry3 = correlatedShortEntry3 = null;
                correlatedBEHit = false;
            }
        }

        // This method puts up a "Cowboy trade;" that is, a set of orders, one long and one short that is
        // <Offset> above/below the current price, respectively.
        private void EnterCowboyTrade(int idx, string oco)
        {
            double tickSize = Instruments[1].MasterInstrument.TickSize;
            switch (idx)
            {
                case 1:
                    {
                        if( longEntry1 == null )
                        {
                            longEntry1 = SubmitOrderUnmanaged(1, OrderAction.Buy, OrderType.StopMarket, Qty, 0, GetCurrentAsk(0) + Offset * tickSize, oco + timeStr, oco);
                        }
                        if( shortEntry1 == null )
                        {
                            shortEntry1 = SubmitOrderUnmanaged(1, OrderAction.SellShort, OrderType.StopMarket, Qty, 0, GetCurrentBid(0) - Offset * tickSize, oco + timeStr, oco);
                        }
                    }
                    break;

                case 2:
                    {
                        if (longEntry2 == null)
                        {
                            longEntry2 = SubmitOrderUnmanaged(1, OrderAction.Buy, OrderType.StopMarket, Qty, 0, GetCurrentAsk(0) + Offset * tickSize, oco + timeStr, oco);
                        }
                        if (shortEntry2 == null)
                        {
                            shortEntry2 = SubmitOrderUnmanaged(1, OrderAction.SellShort, OrderType.StopMarket, Qty, 0, GetCurrentBid(0) - Offset * tickSize, oco + timeStr, oco);
                        }
                    }
                    break;

                case 3:
                    {
                        if (longEntry3 == null)
                        {
                            longEntry3 = SubmitOrderUnmanaged(1, OrderAction.Buy, OrderType.StopMarket, Qty, 0, GetCurrentAsk(0) + Offset * tickSize, oco + timeStr, oco);
                        }
                        if (shortEntry3 == null)
                        {
                            shortEntry3 = SubmitOrderUnmanaged(1, OrderAction.SellShort, OrderType.StopMarket, Qty, 0, GetCurrentBid(0) - Offset * tickSize, oco + timeStr, oco);
                        }
                    }
                    break;
                default:
                    {
                        if (manualLong == null)
                        {
                            manualLong = SubmitOrderUnmanaged(1, OrderAction.Buy, OrderType.StopMarket, Qty, 0, GetCurrentAsk(1) + Offset * tickSize, oco + timeStr, oco);
                        }
                        if (manualShort == null)
                        {
                            manualShort = SubmitOrderUnmanaged(1, OrderAction.SellShort, OrderType.StopMarket, Qty, 0, GetCurrentBid(1) - Offset * tickSize, oco + timeStr, oco);
                        }
                    }
                    break;
            }            
        }

        protected override void OnExecutionUpdate(Execution execution, string executionId, double price, int quantity, MarketPosition marketPosition, string orderId, DateTime time)
        {
            if( UseCorrelatedDataSeries == true )
            {
                if(correlatedManualLong == null 
                    && execution.Order.OrderAction == OrderAction.Buy )
                {
                    if (InverseCorrelatedTrades == true)
                    {
                        // Sell short on the correlated market 
                        correlatedManualShort = SubmitOrderUnmanaged(2, OrderAction.SellShort, OrderType.Market, Qty, 0, 0, "CorrelatedManualEntry" + timeStr, "CorrelatedManualEntry");
                    }
                    else
                    {
                        // Buy on the correlated market
                        correlatedManualLong = SubmitOrderUnmanaged(2, OrderAction.Buy, OrderType.Market, Qty, 0, 0, "CorrelatedManualEntry" + timeStr, "CorrelatedManualEntry");
                    }
                }
                else if( correlatedManualShort == null
                         && execution.Order.OrderAction == OrderAction.SellShort )
                {
                    if (InverseCorrelatedTrades == true)
                    {
                        // Buy on the correlated market
                        correlatedManualLong = SubmitOrderUnmanaged(2, OrderAction.Buy, OrderType.Market, Qty, 0, 0, "CorrelatedManualEntry" + timeStr, "CorrelatedManualEntry");
                    }
                    else
                    {
                        // Sell short on the correlated market 
                        correlatedManualShort = SubmitOrderUnmanaged(2, OrderAction.SellShort, OrderType.Market, Qty, 0, 0, "CorrelatedManualEntry" + timeStr, "CorrelatedManualEntry");
                    }
                }
            }
        }

        protected override void OnOrderUpdate(Order order, double limitPrice, double stopPrice, int quantity, int filled,
                                               double averageFillPrice, OrderState orderState, DateTime time, ErrorCode error, string comment)
        {
            if (order.OrderState == OrderState.Cancelled)
            {
                if (order.Name == "ManualEntry")
                {
                    if (order.OrderAction == OrderAction.Buy)
                    {
                        manualLong = null;
                    }
                    else if (order.OrderAction == OrderAction.SellShort)
                    {
                        manualShort = null;
                    }
                }
                else if (order.Name == "CorrelatedManualEntry")
                {
                    if (order.OrderAction == OrderAction.Buy)
                    {
                        correlatedManualLong = null;
                    }
                    else if (order.OrderAction == OrderAction.SellShort)
                    {
                        correlatedManualShort = null;
                    }
                }
            }

            if( (order.OrderAction == OrderAction.Sell || order.OrderAction == OrderAction.BuyToCover)
                 && order.OrderState == OrderState.Filled
                 && order.Filled == order.Quantity)
            {
                if (order.Name == "Stop"
                    || order.Name == "Manual exit")
                {
                    // Cancel any targets left
                    if (profitOrder1 != null)
                    {
                        CancelOrder(profitOrder1);
                        profitOrder1 = null;
                    }
                    if (profitOrder2 != null)
                    {
                        CancelOrder(profitOrder2);
                        profitOrder2 = null;
                    }
                    if (profitOrder3 != null)
                    {
                        CancelOrder(profitOrder3);
                        profitOrder3 = null;
                    }
                    if (stopOrder != null)
                    {
                        CancelOrder(stopOrder);
                    }
                    // Null all entry orders
                    longEntry1 = shortEntry1 = longEntry2 = shortEntry2 = longEntry3 = shortEntry3 = null;
                    manualLong = manualShort = null;
                }
                else if( order.Name == "Correlated Stop Loss"
                         || order.Name == "Correlated Manual exit" )
                {
                    // Cancel any targets left
                    if (correlatedProfitOrder1 != null)
                    {
                        CancelOrder(correlatedProfitOrder1);
                        correlatedProfitOrder1 = null;
                    }
                    if (correlatedProfitOrder2 != null)
                    {
                        CancelOrder(correlatedProfitOrder2);
                        correlatedProfitOrder2 = null;
                    }
                    if (correlatedProfitOrder3 != null)
                    {
                        CancelOrder(correlatedProfitOrder3);
                        correlatedProfitOrder3 = null;
                    }
                    if (correlatedStopOrder != null)
                    {
                        CancelOrder(correlatedStopOrder);
                        correlatedStopOrder = null;
                    }
                    // Null all entry orders
                    correlatedLongEntry1 = correlatedShortEntry1 = correlatedLongEntry2 = correlatedShortEntry2 = correlatedLongEntry3 = correlatedShortEntry3 = null;
                    correlatedManualLong = correlatedManualShort = null;
                }
                else if (order.Name == "Target1"
                         || order.Name == "Target2"
                         || order.Name == "Target3")
                {
                    if (order.Name == "Target1")
                    {
                        profitOrder1 = null;
                        if (stopOrder != null)
                        {
                            // If there are any orders left, change the stop loss accordingly.  If not, cancel the stop order
                            // because all profit targets have been hit.
                            if (stopOrder.Quantity - ProfitTarget1Qty > 0)
                            {
                                ChangeOrder(stopOrder, stopOrder.Quantity - ProfitTarget1Qty, stopOrder.LimitPrice, stopOrder.StopPrice);
                            }
                            else
                            {
                                CancelOrder(stopOrder);
                            }
                        }
                    }
                    else if (order.Name == "Target2")
                    {
                        profitOrder2 = null;
                        if (stopOrder != null)
                        {
                            // If there are any orders left, change the stop loss accordingly.  If not, cancel the stop order
                            // because all profit targets have been hit.
                            if (stopOrder.Quantity - ProfitTarget2Qty > 0)
                            {
                                ChangeOrder(stopOrder, stopOrder.Quantity - ProfitTarget2Qty, stopOrder.LimitPrice, stopOrder.StopPrice);
                            }
                            else
                            {
                                CancelOrder(stopOrder);
                            }
                        }
                    }
                    else if (order.Name == "Target3")
                    {
                        profitOrder3 = null;
                        if (stopOrder != null)
                        {
                            // If there are any orders left, change the stop loss accordingly.  If not, cancel the stop order
                            // because all profit targets have been hit.
                            if (stopOrder.Quantity - ProfitTarget3Qty > 0)
                            {
                                ChangeOrder(stopOrder, stopOrder.Quantity - ProfitTarget3Qty, stopOrder.LimitPrice, stopOrder.StopPrice);
                            }
                            else
                            {
                                CancelOrder(stopOrder);
                            }
                        }
                    }

                    if( Positions[1].Quantity == 0
                        && stopOrder != null)
                    {
                        CancelOrder(stopOrder);
                    }
                    else if (Positions[1].Quantity == 0)
                    {
                        // Null all entry orders
                        longEntry1 = shortEntry1 = longEntry2 = shortEntry2 = longEntry3 = shortEntry3 = null;
                        manualLong = manualShort = null;
                    }
                }
                else if (order.Name == "Correlated target1"
                         || order.Name == "Correlated target2"
                         || order.Name == "Correlated target3")
                {
                    // For all these guys, a profit target was hit and now we need to change the quantity on the stop loss
                    if (order.Name == "Correlated target1")
                    {
                        correlatedProfitOrder1 = null;
                        if( correlatedStopOrder != null )
                        {
                            // If there's any orders left, change the stop loss accordingly.  If not, cancel the stop order
                            // because all profit targets have been hit.
                            if (correlatedStopOrder.Quantity - CorrelatedProfitTarget1Qty > 0)
                            {
                                ChangeOrder(correlatedStopOrder, correlatedStopOrder.Quantity - CorrelatedProfitTarget1Qty, correlatedStopOrder.LimitPrice, correlatedStopOrder.StopPrice);
                            }
                            else
                            {
                                CancelOrder(correlatedStopOrder);
                            }
                        }
                    }
                    else if (order.Name == "Correlated target2")
                    {
                        correlatedProfitOrder2 = null;
                        if (correlatedStopOrder != null)
                        {
                            // If there's any orders left, change the stop loss accordingly.  If not, cancel the stop order
                            // because all profit targets have been hit.
                            if (correlatedStopOrder.Quantity - ProfitTarget2Qty > 0)
                            {
                                ChangeOrder(correlatedStopOrder, correlatedStopOrder.Quantity - CorrelatedProfitTarget2Qty, correlatedStopOrder.LimitPrice, correlatedStopOrder.StopPrice);
                            }
                            else
                            {
                                CancelOrder(correlatedStopOrder);
                            }
                        }
                    }
                    else if (order.Name == "Correlated target3")
                    {
                        correlatedProfitOrder3 = null;
                        if( correlatedStopOrder != null )
                        {
                            // If there's any orders left, change the stop loss accordingly.  If not, cancel the stop order
                            // because all profit targets have been hit.
                            if (correlatedStopOrder.Quantity - CorrelatedProfitTarget3Qty > 0)
                            {
                                ChangeOrder(correlatedStopOrder, correlatedStopOrder.Quantity - ProfitTarget3Qty, correlatedStopOrder.LimitPrice, correlatedStopOrder.StopPrice);
                            }
                            else
                            {
                                CancelOrder(correlatedStopOrder);
                            }
                        }
                    }

                    if (Positions[2].Quantity == 0
                        && correlatedStopOrder != null)
                    {
                        CancelOrder(correlatedStopOrder);
                    }
                }
            }
            else if (order.OrderAction == OrderAction.Buy
                     || order.OrderAction == OrderAction.SellShort)
            {
                // Entries
                if (order.OrderState == OrderState.Filled)
                {
                    // Add a stop loss on the primary market
                    OrderAction action = order.IsLong ? OrderAction.Sell : OrderAction.BuyToCover;
                    if( StopLoss > 0
                        && order.Name == "ManualEntry" || order.Name.Substring(0, 5) == "Entry" )
                    {
                        double stopLoss = order.IsLong ? order.AverageFillPrice - StopLoss * TickSize : order.AverageFillPrice + StopLoss * TickSize;
                        stopOrder = SubmitOrderUnmanaged(1, action, OrderType.StopMarket, Qty, 0, stopLoss, "", "Stop");
                        HighWater = order.AverageFillPrice;
                    }
                    else
                    {
                        // Add a stop loss on the correlated market
                        if( CorrelatedStopLoss > 0
                            && order.Name == "CorrelatedManualEntry")
                        {
                            double correlatedStopLoss = order.IsLong ? order.AverageFillPrice - CorrelatedStopLoss * TickSize : order.AverageFillPrice + CorrelatedStopLoss * TickSize;
                            correlatedStopOrder = SubmitOrderUnmanaged(2, action, OrderType.StopMarket, Qty, 0, correlatedStopLoss, "", "Correlated Stop Loss");
                            correlatedHighWater = order.AverageFillPrice;
                        }
                    }

                    if( ProfitTarget1Qty > 0
                        && order.Name == "ManualEntry" || order.Name.Substring(0, 5) == "Entry" )
                    {
                        double profitTarget1 = order.IsLong ? order.AverageFillPrice + ProfitTarget1 * TickSize : order.AverageFillPrice - ProfitTarget1 * TickSize;
                        profitOrder1 = SubmitOrderUnmanaged(1, action, OrderType.Limit, ProfitTarget1Qty, profitTarget1, 0, "", "Target1");
                    }
                    else
                    {
                        // Maybe put a Profit Target 1 on a correlated market
                        if( CorrelatedProfitTarget1Qty > 0
                            && order.Name == "CorrelatedManualEntry" )
                        {
                            double correlatedProfitTarget = order.IsLong ? order.AverageFillPrice + CorrelatedProfitTarget1 * TickSize : order.AverageFillPrice - CorrelatedProfitTarget1 * TickSize;
                            correlatedProfitOrder1 = SubmitOrderUnmanaged(2, action, OrderType.Limit, CorrelatedProfitTarget1Qty, correlatedProfitTarget, 0, "", "Correlated target1");
                        }
                    }

                    if ( ProfitTarget2Qty > 0
                        && order.Name == "ManualEntry" || order.Name.Substring(0, 5) == "Entry" )
                    {
                        double profitTarget2 = order.IsLong ? order.AverageFillPrice + ProfitTarget2 * TickSize : order.AverageFillPrice - ProfitTarget2 * TickSize;
                        profitOrder2 = SubmitOrderUnmanaged(1, action, OrderType.Limit, ProfitTarget2Qty, profitTarget2, 0, "", "Target2");
                    }
                    else
                    {
                        // Maybe put a Profit Target 2 on a correlated market
                        if( CorrelatedProfitTarget2Qty > 0
                            && order.Name == "CorrelatedManualEntry" )
                        {
                            double correlatedProfitTarget2 = order.IsLong ? order.AverageFillPrice + CorrelatedProfitTarget2 * TickSize : order.AverageFillPrice - CorrelatedProfitTarget2 * TickSize;
                            correlatedProfitOrder2 = SubmitOrderUnmanaged(2, action, OrderType.Limit, CorrelatedProfitTarget2Qty, correlatedProfitTarget2, 0, "", "Correlated target2");
                        }
                    }

                    if( ProfitTarget3Qty > 0
                        && order.Name == "ManualEntry" || order.Name.Substring(0, 5) == "Entry" )
                    {
                        double profitTarget3 = order.IsLong ? order.AverageFillPrice + ProfitTarget3 * TickSize : order.AverageFillPrice - ProfitTarget3 * TickSize;
                        profitOrder3 = SubmitOrderUnmanaged(1, action, OrderType.Limit, ProfitTarget3Qty, profitTarget3, 0, "", "Target3");
                    }
                    else
                    {
                        // Maybe put a Profit Target 3 on a correlated market
                        if( CorrelatedProfitTarget3Qty > 0
                            && order.Name == "CorrelatedManualEntry" )
                        {
                            double correlatedProfitTarget3 = order.IsLong ? order.AverageFillPrice + CorrelatedProfitTarget3 * TickSize : order.AverageFillPrice - CorrelatedProfitTarget3 * TickSize;
                            correlatedProfitOrder3 = SubmitOrderUnmanaged( 2, action, OrderType.Limit, CorrelatedProfitTarget3Qty, correlatedProfitTarget3, 0, "", "Correlated target3" );
                        }
                    }
                }
            }        
        }

        private void CheckMoveStopLossBE()
        {
            if( BarsInProgress == 1 )
            {
                #region Primary longs
                if( Positions[1].MarketPosition == MarketPosition.Long )
                {
                    if( State == State.Historical )  // This is normally set in OnMarketData but for historical data, it isn't called
                    {                               // so this is the best we can do.
                        HighWater = Math.Max(HighWater, Highs[1][0]);
                    }

                    Order Entry = GetEntryOrder( 1, MarketPosition.Long );
                    if( Entry == null
                        || HighWater == 0 )
                    {
                        return;
                    }

                    double profit = Instrument.MasterInstrument.RoundDownToTickSize( HighWater - Entry.AverageFillPrice);

                    #region Maybe move stops to break even
                    double StopPrice;

                    if (stopOrder == null)
                    {
                        return;
                    }
                    else
                    {
                        StopPrice = stopOrder.StopPrice;
                    }

                    bool beHit = BEHit;    // See if we've already hit a break even.  If so, we don't need to move it again

                    if (MoveToBE)
                    {
                        if (!beHit
                            && profit >= TriggerBE * TickSize)
                        {
                            BEHit = true;
                        }

                        if (BEHit)
                        {
                            StopPrice = Entry.AverageFillPrice;
                        }
                    }

                    if (StopPrice > 0
                        && BEHit == true
                        && beHit == false)
                    {
                        ChangeOrder(stopOrder, Positions[1].Quantity, 0, StopPrice);
                    }
                    #endregion
                }
                #endregion

                #region Primary shorts
                if (Positions[1].MarketPosition == MarketPosition.Short)
                {
                    if (State == State.Historical)
                    {
                        HighWater = Math.Min(HighWater, Lows[1][0]);
                    }

                    // Maybe move the stops to break even
                    Order Entry = GetEntryOrder( 1, MarketPosition.Short);
                    if (Entry == null
                        || HighWater == 0)
                    {
                        return;
                    }

                    double profit = Instrument.MasterInstrument.RoundDownToTickSize(Entry.AverageFillPrice - HighWater);

                    #region Maybe set stops to break even
                    double StopPrice;
                    if (stopOrder == null)
                    {
                        return;
                    }
                    else
                    {
                        StopPrice = stopOrder.StopPrice;
                    }

                    bool beHit = BEHit;    // See if we've already hit a break even.  If so, we don't need to move it again

                    if (MoveToBE)
                    {
                        if( !BEHit
                            && profit >= TriggerBE * TickSize)
                        {
                            BEHit = true;
                        }

                        if (BEHit)
                        {
                            // Set the stop price
                            StopPrice = Entry.AverageFillPrice;
                        }
                    }

                    #endregion

                    #region Maybe move stop loss if the variables were set 
                    if (StopPrice > 0
                        && (BEHit && !beHit))
                    {
                        ChangeOrder(stopOrder, Positions[1].Quantity, 0, StopPrice);
                    }
                    #endregion
                }
                #endregion
            }
            if( BarsInProgress == 2 )
            {
                #region Correlated longs
                if(Positions[2].MarketPosition == MarketPosition.Long )
                {
                    if( State == State.Historical )  // This is normally set in OnMarketData but for historical data, it isn't called
                    {                               // so this is the best we can do.
                        correlatedHighWater = Math.Max(correlatedHighWater, Highs[2][0]);
                    }

                    Order Entry = GetEntryOrder( 2, MarketPosition.Long );
                    if( Entry == null
                        || correlatedHighWater == 0)
                    {
                        return;
                    }

                    double profit = Instrument.MasterInstrument.RoundDownToTickSize( correlatedHighWater - Entry.AverageFillPrice);

                    #region Maybe move stops to break even
                    double StopPrice;

                    if( correlatedStopOrder == null)
                    {
                        return;
                    }
                    else
                    {
                        StopPrice = correlatedStopOrder.StopPrice;
                    }

                    bool beHit = correlatedBEHit;    // See if we've already hit a break even.  If so, we don't need to move it again

                    if( MoveToBECorrelated )
                    {
                        if( beHit == false 
                            && profit >= TriggerBECorrelated * TickSize)
                        {
                            correlatedBEHit = true;
                        }

                        if( correlatedBEHit == true )
                        {
                            StopPrice = Entry.AverageFillPrice;
                        }
                    }

                    if( StopPrice > 0
                        && correlatedBEHit == true
                        && beHit == false )
                    {
                        ChangeOrder( correlatedStopOrder, Positions[2].Quantity, 0, StopPrice);
                    }
                    #endregion
                }
                #endregion

                #region Correlated shorts
                if ( Positions[2].MarketPosition == MarketPosition.Short )
                {
                    if( State == State.Historical )
                    {
                        correlatedHighWater = Math.Min( correlatedHighWater, Lows[2][0] );
                    }

                    // Maybe move the stops to break even
                    Order Entry = GetEntryOrder( 2, MarketPosition.Short);
                    if( Entry == null
                        || correlatedHighWater == 0 )
                    {
                        return;
                    }

                    double profit = Instrument.MasterInstrument.RoundDownToTickSize( Entry.AverageFillPrice - correlatedHighWater );

                    #region Maybe set stops to break even
                    double StopPrice;
                    if (correlatedStopOrder == null)
                    {
                        return;
                    }
                    else
                    {
                        StopPrice = correlatedStopOrder.StopPrice;
                    }

                    bool beHit = correlatedBEHit;    // See if we've already hit a break even.  If so, we don't need to move it again

                    if( MoveToBECorrelated )
                    {
                        if( correlatedBEHit == false
                            && profit >= TriggerBECorrelated * TickSize)
                        {
                            correlatedBEHit = true;
                        }

                        if( correlatedBEHit == true )
                        {
                            // Set the stop price
                            StopPrice = Entry.AverageFillPrice;
                        }
                    }

                    if( StopPrice > 0
                        && BEHit == true 
                        && beHit == false )
                    {
                        ChangeOrder( correlatedStopOrder, Positions[2].Quantity, 0, StopPrice);
                    }
                    #endregion
                }
                #endregion
            }
        }

        private Order GetEntryOrder( int BiP, MarketPosition pos )
        {
            if( BiP == 1 )
            {
                if( pos == MarketPosition.Long )
                {
                    if (longEntry1 != null)
                    {
                        return longEntry1;
                    }
                    else if (longEntry2 != null)
                    {
                        return longEntry2;
                    }
                    else if (longEntry3 != null)
                    {
                        return longEntry3;
                    }
                    else if (manualLong != null)
                    {
                        return manualLong;
                    }
                }
                else if ( pos == MarketPosition.Short )
                {
                    if (shortEntry1 != null)
                    {
                        return shortEntry1;
                    }
                    else if (shortEntry2 != null)
                    {
                        return shortEntry2;
                    }
                    else if (shortEntry3 != null)
                    {
                        return shortEntry3;
                    }
                    else if (manualShort != null)
                    {
                        return manualShort;
                    }
                }
            }
            else if( BiP == 2 )
            {
                if( pos == MarketPosition.Long )
                {
                    if (correlatedLongEntry1 != null)
                    {
                        return correlatedLongEntry1;
                    }
                    else if ( correlatedLongEntry2 != null)
                    {
                        return correlatedLongEntry2;
                    }
                    else if ( correlatedLongEntry3 != null)
                    {
                        return correlatedLongEntry3;
                    }
                    else if( correlatedManualLong != null)
                    {
                        return correlatedManualLong;
                    }
                }
                else if( pos == MarketPosition.Short )
                {
                    if (shortEntry1 != null)
                    {
                        return correlatedShortEntry1;
                    }
                    else if (correlatedShortEntry2 != null)
                    {
                        return correlatedShortEntry2;
                    }
                    else if ( correlatedShortEntry3 != null)
                    {
                        return correlatedShortEntry3;
                    }
                    else if (correlatedManualShort != null)
                    {
                        return correlatedManualShort;
                    }
                }
            }
            return null;            
        }

        #region Properties
        [NinjaScriptProperty]
        [Range(-1, int.MaxValue)]
        [Display(Name = "Quantity", Description = "Quantity (the qty is how many for each target, including a possible runner.)", Order = 0, GroupName = "Parameters")]
        public int Qty
        { get; set; }

        [NinjaScriptProperty]
        [Range(1, int.MaxValue)]
        [Display(Name = "Offset cowboy", Description = "Number of ticks to place the trade away from the close of the 1-second background data series", Order = 1, GroupName = "Parameters")]
        public int Offset
        { get; set; }

        #region Time1
        [NinjaScriptProperty]
		[Range(-1, int.MaxValue)]
		[Display(Name="TimeEntry1", Description="1st time period to enter (Use negative value to disable)", Order=1, GroupName="Time 1")]
		public int TimeEntry1
		{ get; set; }

        [NinjaScriptProperty]
        [Display(Name = "Trade on Sunday?", Description = "Check to allow trading on Sundays", Order = 2, GroupName = "Time 1")]
        public bool Sunday1
        { get; set; }

        [NinjaScriptProperty]
        [Display(Name = "Trade on Monday?", Description = "Check to allow trading on Mondays", Order = 3, GroupName = "Time 1")]
        public bool Monday1
        { get; set; }

        [NinjaScriptProperty]
        [Display(Name = "Trade on Tuesday?", Description = "Check to allow trading on Mondays", Order = 4, GroupName = "Time 1")]
        public bool Tuesday1
        { get; set; }

        [NinjaScriptProperty]
        [Display(Name = "Trade on Wednesday?", Description = "Check to allow trading on Wednesdays", Order = 5, GroupName = "Time 1")]
        public bool Wednesday1
        { get; set; }

        [NinjaScriptProperty]
        [Display(Name = "Trade on Thursday?", Description = "Check to allow trading on Thursdays", Order = 6, GroupName = "Time 1")]
        public bool Thursday1
        { get; set; }

        [NinjaScriptProperty]
        [Display(Name = "Trade on Friday?", Description = "Check to allow trading on Fridays", Order = 7, GroupName = "Time 1")]
        public bool Friday1
        { get; set; }
        #endregion

        #region Time2
        [NinjaScriptProperty]
        [Range(-1, int.MaxValue)]
        [Display(Name = "TmeEntry2", Description = "2nd time period to enter (Use negative value to disable)", Order = 1, GroupName = "Time 2")]
        public int TimeEntry2
        { get; set; }

        [NinjaScriptProperty]
        [Display(Name = "Trade on Sunday?", Description = "Check to allow trading on Sundays", Order = 2, GroupName = "Time 2")]
        public bool Sunday2
        { get; set; }

        [NinjaScriptProperty]
        [Display(Name = "Trade on Monday?", Description = "Check to allow trading on Mondays", Order = 3, GroupName = "Time 2")]
        public bool Monday2
        { get; set; }

        [NinjaScriptProperty]
        [Display(Name = "Trade on Tuesday?", Description = "Check to allow trading on Mondays", Order = 4, GroupName = "Time 2")]
        public bool Tuesday2
        { get; set; }

        [NinjaScriptProperty]
        [Display(Name = "Trade on Wednesday?", Description = "Check to allow trading on Wednesdays", Order = 5, GroupName = "Time 2")]
        public bool Wednesday2
        { get; set; }

        [NinjaScriptProperty]
        [Display(Name = "Trade on Thursday?", Description = "Check to allow trading on Thursdays", Order = 6, GroupName = "Time 2")]
        public bool Thursday2
        { get; set; }

        [NinjaScriptProperty]
        [Display(Name = "Trade on Friday?", Description = "Check to allow trading on Fridays", Order = 7, GroupName = "Time 2")]
        public bool Friday2
        { get; set; }
        #endregion

        #region Time3
        [NinjaScriptProperty]
        [Range(-1, int.MaxValue)]
        [Display(Name = "TimeEntry3", Description = "3rd time period to enter (Use negative value to disable)", Order = 1, GroupName = "Time 3")]
        public int TimeEntry3
        { get; set; }

        [NinjaScriptProperty]
        [Display(Name = "Trade on Sunday?", Description = "Check to allow trading on Sundays", Order = 2, GroupName = "Time 3")]
        public bool Sunday3
        { get; set; }

        [NinjaScriptProperty]
        [Display(Name = "Trade on Monday?", Description = "Check to allow trading on Mondays", Order = 3, GroupName = "Time 3")]
        public bool Monday3
        { get; set; }

        [NinjaScriptProperty]
        [Display(Name = "Trade on Tuesday?", Description = "Check to allow trading on Mondays", Order = 4, GroupName = "Time 3")]
        public bool Tuesday3
        { get; set; }

        [NinjaScriptProperty]
        [Display(Name = "Trade on Wednesday?", Description = "Check to allow trading on Wednesdays", Order = 5, GroupName = "Time 3")]
        public bool Wednesday3
        { get; set; }

        [NinjaScriptProperty]
        [Display(Name = "Trade on Thursday?", Description = "Check to allow trading on Thursdays", Order = 6, GroupName = "Time 3")]
        public bool Thursday3
        { get; set; }

        [NinjaScriptProperty]
        [Display(Name = "Trade on Friday?", Description = "Check to allow trading on Fridays", Order = 7, GroupName = "Time 3")]
        public bool Friday3
        { get; set; }
        #endregion

        #region Stops & Targets
        [NinjaScriptProperty]
        [Range(0, int.MaxValue)]
        [Display(Name = "Stop loss", Description = "Stop loss (ticks)", Order = 1, GroupName = "Stops & targets")]
        public int StopLoss
        { get; set; }

        [NinjaScriptProperty]
        [Range(0, int.MaxValue)]
        [Display(Name = "Profit target 1", Description = "Profit target 1 (ticks)", Order = 2, GroupName = "Stops & targets")]
        public int ProfitTarget1
        { get; set; }

        [NinjaScriptProperty]
        [Range(0, int.MaxValue)]
        [Display(Name = "Profit target 1 qty", Description = "Profit target 1 qty", Order = 3, GroupName = "Stops & targets")]
        public int ProfitTarget1Qty
        { get; set; }

        [NinjaScriptProperty]
        [Range(0, int.MaxValue)]
        [Display(Name = "Profit target 2", Description = "Profit target 2 (ticks)", Order = 4, GroupName = "Stops & targets")]
        public int ProfitTarget2
        { get; set; }

        [NinjaScriptProperty]
        [Range(0, int.MaxValue)]
        [Display(Name = "Profit target 2 qty", Description = "Profit target 2 qty", Order = 5, GroupName = "Stops & targets")]
        public int ProfitTarget2Qty
        { get; set; }

        [NinjaScriptProperty]
        [Range(0, int.MaxValue)]
        [Display(Name = "Profit target 3", Description = "Profit target 3 (ticks)", Order = 6, GroupName = "Stops & targets")]
        public int ProfitTarget3
        { get; set; }

        [NinjaScriptProperty]
        [Range(0, int.MaxValue)]
        [Display(Name = "Profit target 3 qty", Description = "Profit target 3 qty", Order = 7, GroupName = "Stops & targets")]
        public int ProfitTarget3Qty
        { get; set; }

        [NinjaScriptProperty]
        [Display(Name = "Move stop to BE?", Description = "Check to move to BE after so many ticks", Order = 8, GroupName = "Stops & targets")]
        public bool MoveToBE
        { get; set; }

        [NinjaScriptProperty]
        [Display(Name = "BE trigger", Description = "Number of ticks to move to BE if triggered", Order = 9, GroupName = "Stops & targets")]
        public int TriggerBE
        { get; set; }
        #endregion

        #region Stops & Targets (Correlated)
        [NinjaScriptProperty]
        [Range(0, int.MaxValue)]
        [Display(Name = "Correlated stop loss", Description = "Correlated stop loss (ticks)", Order = 1, GroupName = "Stops & targets (Correlated)")]
        public int CorrelatedStopLoss
        { get; set; }

        [NinjaScriptProperty]
        [Range(0, int.MaxValue)]
        [Display(Name = "Correlated profit target 1", Description = "Correlated profit target 1 (ticks)", Order = 2, GroupName = "Stops & targets (Correlated)")]
        public int CorrelatedProfitTarget1
        { get; set; }

        [NinjaScriptProperty]
        [Range(0, int.MaxValue)]
        [Display(Name = "Correlated profit target 1 qty", Description = "Correlated Profit target 1 qty", Order = 3, GroupName = "Stops & targets (Correlated)")]
        public int CorrelatedProfitTarget1Qty
        { get; set; }

        [NinjaScriptProperty]
        [Range(0, int.MaxValue)]
        [Display(Name = "Correlated profit target 2", Description = "Correlated profit target 2 (ticks)", Order = 4, GroupName = "Stops & targets (Correlated)")]
        public int CorrelatedProfitTarget2
        { get; set; }

        [NinjaScriptProperty]
        [Range(0, int.MaxValue)]
        [Display(Name = "Correlated profit target 2 qty", Description = "Correlated profit target 2 qty", Order = 5, GroupName = "Stops & targets (Correlated)")]
        public int CorrelatedProfitTarget2Qty
        { get; set; }

        [NinjaScriptProperty]
        [Range(0, int.MaxValue)]
        [Display(Name = "Correlated profit target 3", Description = "Correlated profit target 3 (ticks)", Order = 6, GroupName = "Stops & targets (Correlated)")]
        public int CorrelatedProfitTarget3
        { get; set; }

        [NinjaScriptProperty]
        [Range(0, int.MaxValue)]
        [Display(Name = "Correlated profit target 3 qty", Description = "Correlated profit target 3 qty", Order = 7, GroupName = "Stops & targets (Correlated)")]
        public int CorrelatedProfitTarget3Qty
        { get; set; }

        [NinjaScriptProperty]
        [Display(Name = "Move correlated stop to BE?", Description = "Check to move correlated order to BE after so many ticks", Order = 8, GroupName = "Stops & targets (Correlated)")]
        public bool MoveToBECorrelated
        { get; set; }

        [NinjaScriptProperty]
        [Display(Name = "Correlated BE trigger", Description = "Number of ticks to move correlated order to BE if triggered", Order = 9, GroupName = "Stops & targets (Correlated)")]
        public int TriggerBECorrelated
        { get; set; }


        #endregion

        #region Correlated data series 
        [Display(Name = "Use correlated data series?", Description = "True to use execute a simultaneous trade on a correlated data series.", Order = 1, GroupName = "Correlated data series")]
        public bool UseCorrelatedDataSeries { get; set; }

        [Browsable(false)]

        [Display(Name = "Inverse correlated trades?", Description = "True to use execute a simultaneous trade in the opposite direction on a correlated data series.", Order = 2, GroupName = "Correlated data series")]
        public bool InverseCorrelatedTrades { get; set; }

        [Display(Name = "Correlated data series instrument", Description = "Correlated data series instrument; Enter as: NQ 09-20", Order = 3, GroupName = "Correlated data series")]
        public string CorrelatedDataSeriesInstrument { get; set; }
        #endregion

        #endregion

    }
}
