#region Using declarations
	using System;
	using System.Collections.Generic;
	using System.ComponentModel;
	using System.ComponentModel.DataAnnotations;
	using System.Linq;
	using System.Text;
	using System.Threading.Tasks;
	using System.Windows;
	using System.Windows.Input;
	using System.Windows.Media;
	using System.Xml.Serialization;
	using System.Xml; //*
	using NinjaTrader.Cbi;
	using NinjaTrader.Gui;
	using NinjaTrader.Gui.Chart;
	using NinjaTrader.Gui.SuperDom;
	using NinjaTrader.Data;
	using NinjaTrader.NinjaScript;
	using NinjaTrader.Core.FloatingPoint;
	using NinjaTrader.NinjaScript.Indicators;
	using NinjaTrader.NinjaScript.DrawingTools;
#endregion

//This namespace holds Strategies in this folder and is required. Do not change it.
namespace NinjaTrader.NinjaScript.Strategies.TrendIsYourFriend
{

	public static class DictionaryExtentions
	{
		// https://www.codeproject.com/Tips/494499/Implementing-Dictionary-RemoveAll
		// this static class adds the method 'RemoveAll' to the Dictionary collection object
		// ex.: myDictionary.tiyfRemoveAll((key, value) => value < 99); // removes all items(key, value) whose value is < 99
		public static void tiyfRemoveAll<K, V>(this IDictionary<K, V> dict, Func<K, V, bool> match)
		{
			foreach (var key in dict.Keys.ToArray()
				.Where(key => match(key, dict[key])))
			dict.Remove(key);
		}
	}
	
	[Gui.CategoryOrder("General", 0)]
	[Gui.CategoryOrder("Toolbar - settings", 1)]
	[Gui.CategoryOrder("Visual markers (entry/exit) - settings", 2)]
	[Gui.CategoryOrder("Entry (STPLMT) - settings", 3)]
	[Gui.CategoryOrder("Exit - settings", 4)]
	[Gui.CategoryOrder("ATR - settings", 5)]
	[Gui.CategoryOrder("PSAR - settings", 6)]
	
	public class tiyfEasyOrdering : Strategy
	{
		/// <summary> 
		/// strategy name : tiyfEasyOrdering
		/// https://ninjatrader.com/support/helpGuides/nt8/?atm_strategy_methods.htm
		/// HELP DOCUMENTATION REFERENCE: Please see the Help Guide section "Using ATM Strategies" under NinjaScript /> Educational Resources /> http://ninjatrader.com/support/helpGuides/nt8/en-us/using_atm_strategies.htm
		/// compiled with Ninjatrader version 8.0.26.1 64-bit
		/// author : trendisyourfriend (futures.io)
		/// trendisyourfriend's discussion thread :
		/// https://futures.io/elite-circle/58876-tiyfeasyordering-strategy-helping-bot-enter-manage-trade.html
		/// historical versions stored @ https://www.notion.so/
		/// 2022.09.06 (YYYY.MM.DD) Version 1 released
		/// 2022.09.12 - minor bug corrected: removing param "Allow Stop loss to move backward"
		/// 2022.09.14 - added the option to attach the stop order(s) to a Ray object (for trailing)
		/// 2022.09.17 - The middle button used to manage the Stop Loss (before and during a trade) has been expanded
		///              to display more information and to quickly move the Stop Loss to break even.
		/// 2022.09.23 - Property 'Stop-limit order margin <as tick(s)>' accepts negative value
		/// 2022.09.23 - New way to enter has been added:
		/// - Psar(↓↑) Buy if Parabolic Sar changes direction from Down to UP
		/// - Psar(↑↓) Sell if Parabolic Sar changes direction from UP to Down
		/// a minor correction has been done to the function created this date 2022.09.17
		/// </summary>

		public enum stratEasyOrdering_StopType { Signal_Bar, PSAR_Swing, ATR }
		public enum stratEasyOrdering_RayAttachedTo { LongSide, ShortSide, NoSide, Trailing }
		// shared variables between all instances of this strategy
		public static int sharedInstanceCnt // count the number of instance running
		{ get; set; }
		public static List<long> sharedInstanceStrategyId // Each time the AtmStrategyCreate() method is executed from any instance of this Ninjascript strategy, we add (this.Id) into this list
		{ get; set; }
		public static Dictionary<string, long> sharedOrderList // keep a record of all orders created within this strategy instance (this.Id)
		{ get; set; }

		#region PROPERTIES
		//-
//		[NinjaScriptProperty]
		[ReadOnly(true)]
		[Display(Name = "Last update (YYYY.MM.DD)", GroupName = "General", Order = 0)]
		public string pStrategyInfo
		{
			get { return SystemVersion; }
			set {;}
//			private set {;}
		}
		
		[NinjaScriptProperty]
		[ReadOnly(true)]
		[Display(Name = "id", GroupName = "General", Description = "Label given to an instance of the strategy for the purpose of identification.\n Helpful when the 'Parameters' column is displayed in the 'Control Center/Strategies' window.", Order = 1)]
		public string id
		{ 
			get
			{ 
				if (this.Id != -1)
					return this.Id.ToString();
				else
					return string.Empty;
			}
			set {;}
		}
		
///		=== Toolbar - settings
		[XmlIgnore()]
		[Display(Name = "Buy button when Clicked", GroupName = "Toolbar - settings", Description="Button background color when clicked", Order = 0)]
		public Brush buyButtonBackgroundColor
		{ get; set; }
		[Browsable(false)] //prevents this property from showing up on the UI
        public string buyButtonBackgroundColorSerializable
        {
            get { return Serialize.BrushToString(buyButtonBackgroundColor); }
            set { buyButtonBackgroundColor = Serialize.StringToBrush(value); }
        }

		[XmlIgnore()]
		[Display(Name = "Sell button when Clicked", GroupName = "Toolbar - settings", Description="Button background color when clicked", Order = 1)]
		public Brush sellButtonBackgroundColor
		{ get; set; }
		[Browsable(false)] //prevents this property from showing up on the UI
        public string sellButtonBackgroundColorSerializable
        {
            get { return Serialize.BrushToString(sellButtonBackgroundColor); }
            set { sellButtonBackgroundColor = Serialize.StringToBrush(value); }
        }

		[XmlIgnore()]
		[Display(Name = "Fade button when clicked", GroupName = "Toolbar - settings", Description="Button background color when clicked", Order = 2)]
		public Brush fadeButtonBackgroundColor
		{ get; set; }
		[Browsable(false)] //prevents this property from showing up on the UI
        public string fadeButtonBackgroundColorSerializable
        {
            get { return Serialize.BrushToString(fadeButtonBackgroundColor); }
            set { fadeButtonBackgroundColor = Serialize.StringToBrush(value); }
        }

		[XmlIgnore()]
		[Display(Name = "Stop type button", GroupName = "Toolbar - settings", Description="Button background color", Order = 3)]
		public Brush stopTypeButtonBackgroundColor
		{ get; set; }
		[Browsable(false)] //prevents this property from showing up on the UI
        public string stopTypeButtonBackgroundColorSerializable
        {
            get { return Serialize.BrushToString(stopTypeButtonBackgroundColor); }
            set { stopTypeButtonBackgroundColor = Serialize.StringToBrush(value); }
        }

		[Display(Name = "Vertical alignment", GroupName = "Toolbar - settings", Description="Position of the toolbar - Y axis", Order = 4)]
		public VerticalAlignment VAlignment
		{
			get { return vAlignment; }
			set { vAlignment = value; }
		}

		[Display(Name = "Horizontal alignment", GroupName = "Toolbar - settings", Description="Position of the toolbar - X axis", Order = 5)]
		public HorizontalAlignment HAlignment
		{
			get { return hAlignment; }
			set { hAlignment = value; }
		}
		
///		=== Visual markers (entry/exit) - settings
		[Display(Name = "Show markers", GroupName = "Visual markers (entry/exit) - settings", Description = "Entries/exits can be marked with a stripe of color and Arrows", Order = 0)]
		public bool showMarkers
		{ get; set; }
		
		[XmlIgnore()]
		[Display(Name = "Arrow color - signal bar", GroupName = "Visual markers (entry/exit) - settings", Description="Color of the arrow above/below the signal bar", Order = 1)]
		public Brush arrowColorSignalBar
		{ get; set; }
		[Browsable(false)] //prevents this property from showing up on the UI
        public string arrowColorSignalBarSerializable
        {
            get { return Serialize.BrushToString(arrowColorSignalBar); }
            set { arrowColorSignalBar = Serialize.StringToBrush(value); }
        }
		
		[XmlIgnore()]
		[Display(Name = "Stripe color - bullish entry", GroupName = "Visual markers (entry/exit) - settings", Description="Color of the vertical stripe to highlight a bullish entry/Selling exit", Order = 2)]
		public Brush backBrushStripeBullishEntry
		{ get; set; }
		[Browsable(false)] //prevents this property from showing up on the UI
        public string backBrushStripeBullishEntrySerializable
        {
            get { return Serialize.BrushToString(backBrushStripeBullishEntry); }
            set { backBrushStripeBullishEntry = Serialize.StringToBrush(value); }
        }

		[XmlIgnore()]
		[Display(Name = "Stripe color - bearish entry", GroupName = "Visual markers (entry/exit) - settings", Description="Color of the vertical stripe to highlight a Bearish entry/Bullish exit", Order = 3)]
		public Brush backBrushStripeBearishEntry
		{ get; set; }
		[Browsable(false)] //prevents this property from showing up on the UI
        public string backBrushStripeBearishEntrySerializable
        {
            get { return Serialize.BrushToString(backBrushStripeBearishEntry); }
            set { backBrushStripeBearishEntry = Serialize.StringToBrush(value); }
        }

		[Range(1, 100)]
		[Display(Name = "Stripe Opacity", GroupName = "Visual markers (entry/exit) - settings", Order = 4)]
		public double stripeOpacity
		{ get; set; }
		
///		=== Entry - settings
		[Range(int.MinValue, int.MaxValue)]
		[Display(Name = "Stop-limit order margin <as tick(s)>", GroupName = "Entry (STPLMT) - settings", Description = "Add extra margin to the stop price of a stop-limit order\n* To be defined as ticks (negative margin accepted)", Order = 0)]
		public int stopLimitMargin
		{ get; set; }

		[Range(1, int.MaxValue)]
		[Display(Name = "Limit offset <as tick(s)>", GroupName = "Entry (STPLMT) - settings", Description = "Number of ticks away at which you wish to place the Limit price of a Stop-Limit order\n* To be defined as ticks", Order = 1)]
		public int stopLimitOffset
		{ get; set; }

///		=== Exit - settings
		[Display(Name = "Manage stop loss", GroupName = "Exit - settings", Description = "Let the strategy manage the stop loss", Order = 0)]
		public bool IsStopLossManaged
		{ get; set; }
		
		[Display(Name = "Manage target", GroupName = "Exit - settings", Description = "Let the strategy manage the target", Order = 1)]
		public bool IsTargetManaged
		{ get; set; }
		
		[Display(Name="Risk - initial stop loss based on", GroupName = "Exit - settings", Description="The risk is evaluated by looking at the difference between the average fill price and one of these \n* 'Signal_Bar' high or low,\n* 'PSAR_Swing' high or low or\n* 'ATR' at the current signal bar.", Order = 2)]
		public stratEasyOrdering_StopType pUserPref_StopType // drop down menu
		{
			get { return userPref_StopType; }
			set { userPref_StopType = value; }
		}

		[Range(0, double.MaxValue)]
		[Display(Name = "Stop loss margin <as tick(s)>", GroupName = "Exit - settings", Description = "Extra room to add to the stop loss.\n* To be defined as ticks", Order = 3)]
		public double yButtonInitialContent
		{ get; set; }

		[Range(0.1, double.MaxValue)]
		[Display(Name = "Reward ratio - Target1", GroupName = "Exit - settings", Description = "Used to calculate the price of the 1st target.\n* To be defined as a ratio of the risk", Order = 4)]
		public double rewardRatio
		{ get; set; }

		[Range(0.1, double.MaxValue)]
		[Display(Name = "Reward ratio - additional Targets", GroupName = "Exit - settings", Description = "Space between additional targets above the 1st target.\n* To be defined as a ratio of the risk", Order = 5)]
		public double rewardRatio2
		{ get; set; }

		[Range(0, double.MaxValue)]
		[Display(Name = "Break even ratio (0 to disregard)", GroupName = "Exit - settings", Description = "Profit to make expressed as a ratio of the initial risk to move the stop to BE.\n* Enter 0 to disregard", Order = 6)]
		public double breakEvenRatio
		{ get; set; }

		[Range(double.MinValue, double.MaxValue)]
		[Display(Name = "Break even margin <as tick(s)>", GroupName = "Exit - settings", Description = "Margin to add to the break even price.\n* To be defined as ticks", Order = 7)]
		public double breakEvenMargin
		{ get; set; }
		
		[Range(0, 0.9)]
		[Display(Name = "Jump stop by x percent (0-0.9)", GroupName = "Exit - settings", Description = "Set the percentage to use to jump the stop loss nearest to the current price\nwhen pressing the Up/Dn button", Order = 8)]
		public double jumpStopbyXPercent
		{ get; set; }

///		=== ATR - settings
		
		[Range(1, int.MaxValue)]
		[Display(Name = "ATR period", GroupName = "ATR - settings", Description = "Define the ATR period. Will be used as a measure of volatility for the stop loss", Order = 0)]
		public int atrPeriod
		{ get; set; }
		
		[Range(1.00, double.MaxValue)]
		[Display(Name = "ATR multiple", GroupName = "ATR - settings", Description = "A rule of thumb is to multiply the ATR by two\nto determine a reasonable stop-loss point", Order = 1)]
		public double atrMultiple
		{ get; set; }
		
///		=== PSAR - settings
		[Display(Name = "Visible", GroupName = "PSAR - settings", Description = "Make the indicator visible on the chart", Order = 0)]
		public bool showPSAR
		{ get; set; }
		
		[Range(0.00, double.MaxValue)]
		[Display(Name = "Acceleration", GroupName = "PSAR - settings", Order = 1)]
		public double psarAcceleration
		{ get; set; }

		[Range(0.001, double.MaxValue)]
		[Display(Name = "AccelerationMax", GroupName = "PSAR - settings", Order = 2)]
		public double psarAccelerationMax
		{ get; set; }

		[Range(0.001, double.MaxValue)]
		[Display(Name = "AccelerationStep", GroupName = "PSAR - settings", Order = 3)]
		public double psarAccelerationStep
		{ get; set; }
		
		[Display(Name = "Plot", GroupName = "PSAR - settings", Order = 4)]
		// a property of type 'Plot' will display a sub-menu to let the user set these items:
		// Color, Dash style, Opacity(%), Plot style, Width
		public NinjaTrader.Gui.Plot psarPlot
		{ get; set; }	
		//-
		#endregion

		#region DICTIONARY_LIST
		//-
		private class CBracket
		{
			public double quantity; // bracket Quantity
			public double ticksStopLoss;
			public double ticksProfit;
			public double stopPrice;
			public double limitPrice;
			public OrderState orderStateStop;
			public OrderState orderStateTarget;
			
			public CBracket(double qty, double ticSL, double ticP, double sp = 0, double lp = 0, OrderState oss = OrderState.Unknown, OrderState ost = OrderState.Unknown)
			{
				quantity = qty;
				ticksStopLoss = ticSL;
				ticksProfit = ticP;
				stopPrice = sp;
				limitPrice = lp;
				orderStateStop = oss;
				orderStateTarget = ost;
			}
		}
		
		private class COrder
		{
			public string id { get; set; }
			public string name { get; set; }
			public int quantity { get; set; }
			public double price { get; set; }
			public OrderState orderState { get; set; }
		}

		private	Dictionary<int, CBracket> bracketList	= new Dictionary<int, CBracket>();	// Key(int) = 1 to x, CBracket(Value) = Target content as defined in the ATM strategy template
		private List<COrder> orderList = new List<COrder>();
		//-
		#endregion
		
		#region CLASS_INSTANCE_VARIABLES
		//-
		
		private const string	SystemVersion = "2022.09.23"; // <- last update YYYY.MM.DD
		private const string	SystemName = "tiyfEasyOrdering";
		private const string	FullSystemName = SystemName;
		private const bool		output1 = false; // flag to determine if we want to enable all Print() statements
		//
		private Account		myAccount				= null;
		private string		atmTemplateName			= string.Empty;
		private string		atmStrategyId			= string.Empty;
		private string		orderId					= string.Empty;
		private bool		isAtmStrategyCreated	= false;
		private bool		isAtmConfigured			= false;
		private double		PnL_atmStrategy			= 0;
		private bool		IsEntryFullyFilled		= false;
		private bool		IsInitialStopLossSet	= false;
		private string		entryOrderFinalStatus	= string.Empty;
		private bool		IsUserRequestToCloseAtm_InProgress	= false; // pressing the left shift key when an ATM is running will set it to true
		private bool		IsUserRequestToOpenAtm_inProgress	= false; // pressing the left shift key when no ATM is running will set it to true
		private int			indexActiveStrategy		= 0;
		private long		atmCreatedInInstanceId	= 0;
		private stratEasyOrdering_RayAttachedTo		rayAttachedTo;
		private double		runningATR				= 0;
		private string		contentMidButton		= string.Empty;
		private string		tooltipMidButton		= string.Empty;
		//

		//Buttons and toolbar variables
		private List<string> contentBuyButton = new List<string> { "C+>H[1]", "C+>TLine", "BO H[1]", "C+ve", "C+|-ve", "Psar ↓↑" };
		private List<string> contentSellButton = new List<string> { "C-<L[1]", "C-<TLine", "BO L[1]", "C-ve", "C-|+ve", "Psar ↑↓" };
		private int idxButtonContent; // Index used to set the content of the Buy and Sell buttons
		private System.Windows.Controls.Button buttonBuy;
		private System.Windows.Controls.Button buttonSell;
		private System.Windows.Controls.Button buttonStopType;
		private System.Windows.Controls.Button buttonFade;
		private System.Windows.Controls.Button buttonArea;
		private System.Windows.Controls.Grid buttonGrid;
		private Brush buttonForegroundColor; // default color
		private Brush buttonBackgroundColor; // default color
		private Brush buttonDisabledBackgroundColor; // default color
		private VerticalAlignment vAlignment; //toolbar VerticalAlignment
		private HorizontalAlignment hAlignment; //toolbar HorizontalAlignment
		private double cellFontSize = 14; //  content buttons' font size
		private bool buyModeEnabled;
		private bool sellModeEnabled;
		private bool fadeModeEnabled;
		private int fadeType; // BOF/Test (1), Test (2), BOF (3)
		
		private bool targetsMovedAtDesiredReward; // flag to determine if target(s) have been moved at the desired reward location (happens once per trade)
		private List< Tuple<double, double, double> > listOfTargets; // A tuple represents a target line (Quantity, Stop, Target) in the ATM strategy template
		
		private NinjaTrader.NinjaScript.DrawingTools.Line myHLine = null; // contains a ref to the selected Horizontal line object
		private NinjaTrader.NinjaScript.DrawingTools.Ray myRay = null; // contains a ref to the selected Ray object
		private bool IsTLineSelected; // flag to let us know if we have a HorizontalLine or Ray selected
		private double anchorPrice_HLineOrSlopeIntercept;

		private struct LineCalculation
		{
			public double Y_Intercept;
			public float Slope;
			public int BarIdxLeftAnchor;
			public int BarIdxRightAnchor;
		}
		LineCalculation lineCalc; //  used to calculate the slope intercept of the Ray object
		
		private NinjaTrader.NinjaScript.DrawingTools.RegionHighlightY myRegionHLY = null; // contains a ref to the selected RegionHighlightY object
		private NinjaTrader.NinjaScript.DrawingTools.Rectangle myRectangle = null; // contains a ref to the selected Rectangle object
		private bool IsRegionHLYSelected; // flag to let us know if we have a RegionHighlightY drawing object selected
		private bool IsRectangleSelected; // flag to let us know if we have a Rectangle drawing object selected
		private double sizeOfSelectedDrawing; // size of the selected Region or Rectangle
		private double stopLossExtraMargin;

		private int idxBarClicked, idxBarClickedCopy;
		private Brush highlightColorBullishEntry;
		private Brush highlightColorBearishEntry;
		
		private double	limitPrice = -1;
		private PSAR	myPSAR;
		private ATR		myATR;
		private bool	IsPSARInDownTrend;
		private int 	barIdxLastBullishPSAR;
		private int 	barIdxLastBearishPSAR;
		private double 	psarHH, psarLL;
		private bool	IsFirstPSARPhaseCompleted;
		private bool	IsAtmOrderFilled;
		private bool	AreOCOBracketOrdersReady;
		private int		cntAtmBracket; // nb of stop/target lines defined in the ATM strategy template selected
		private int		countOnBarUpdateSinceOrderFilled;
		private bool	IsTimeOKToMoveStop;
		private bool	IsTimeOKToBreakEven;
		private bool	IsBreakEvenDone;
		private stratEasyOrdering_StopType activeStopType;
		private stratEasyOrdering_StopType stopType; // used to set the buttonStopType content
		private bool	jumpStopbyXpercentClicked; // When trade in progress then the user can trail faster by x % by pressing the buttonStopType
		private double initialStopSize;
		private double countStopSteppingBackward;
		private double currentPainThreshold;
		private double orderQty;
		private double profitToMakeToBreakEven;
		private string msglevelToExceedCopy;

		private stratEasyOrdering_StopType userPref_StopType; // contains the user pref. for the stop loss placement
		
		private ChartScale		thisChartScale;
		private bool			IsTradeInProgress;
		private int				tradeDir; // used to determine the trade direction: 1 => long, 2 => short
		private int				barIndexSignalBar;
		//-
		#endregion

		protected override void OnStateChange()
		{
			#region ON_STATE_CHANGE
			//-
			if (State == State.SetDefaults)
			{
				#region STATE_SETDEFAULTS
				//-
				PrintTo = PrintTo.OutputTab2;
				ClearOutputWindow();
				PrintTo = PrintTo.OutputTab1;
				ClearOutputWindow();
				
				Description	= NinjaTrader.Custom.Resource.NinjaScriptStrategyDescriptionSampleATMStrategy;
				Name		= "tiyfEasyOrdering";
				Calculate	= Calculate.OnEachTick;
				IsExitOnSessionCloseStrategy				= false;
				ExitOnSessionCloseSeconds					= 30;
				IsFillLimitOnTouch							= false;
				MaximumBarsLookBack							= MaximumBarsLookBack.TwoHundredFiftySix;
				OrderFillResolution							= OrderFillResolution.Standard;
				Slippage									= 0;
				StartBehavior								= StartBehavior.WaitUntilFlat;
				TimeInForce									= TimeInForce.Gtc;
				TraceOrders									= false;
				RealtimeErrorHandling						= RealtimeErrorHandling.StopCancelClose;
				StopTargetHandling							= StopTargetHandling.PerEntryExecution;
				BarsRequiredToTrade							= 20;
				// This strategy has been designed to take advantage of performance gains in Strategy Analyzer optimizations
				// See the Help Guide for additional information
				IsInstantiatedOnEachOptimizationIteration = false;
				
				/// DEFAULT> Buttons Toolbar - settings
				buttonForegroundColor = Brushes.White; //default FG color
				buttonBackgroundColor = Brushes.DarkSlateGray; //default BG color
				buttonDisabledBackgroundColor = Brushes.DimGray;
				buyButtonBackgroundColor = Brushes.Green;
				sellButtonBackgroundColor = Brushes.Red;
				fadeButtonBackgroundColor = Brushes.DodgerBlue;
				stopTypeButtonBackgroundColor = Brushes.DarkRed;
				vAlignment = VerticalAlignment.Bottom;
				hAlignment = HorizontalAlignment.Right;
				
				/// DEFAULT> Visual markers (entry/exit) - settings
				backBrushStripeBullishEntry = Brushes.Chartreuse;
				backBrushStripeBearishEntry = Brushes.DeepPink;
				stripeOpacity = 35;
				showMarkers = true;
				arrowColorSignalBar = Brushes.White;
				
				/// DEFAULT> Entry (STPLMT) - settings
				stopLimitMargin = 1; // extra room to add to the High or Low of the signal bar
				stopLimitOffset = 4; // number of ticks away from the Limit price of a Stop-Limit order
				
				/// DEFAULT> Exit - settings
				rewardRatio = 2; // main ratio for the 1st target
				rewardRatio2 = 0.5; // ratio for additional targets
				breakEvenRatio = 1d; // risk, defined as a fraction of rewardRatio
				breakEvenMargin = 2;
				IsStopLossManaged = true;
				IsTargetManaged = true;
				userPref_StopType = stratEasyOrdering_StopType.PSAR_Swing;
				yButtonInitialContent = 2;
				jumpStopbyXPercent = 0.25d;
				
				/// DEFAULT> ATR - settings
				atrPeriod = 14;
				atrMultiple = 2.5;
				
				/// DEFAULT> ParabolicSAR - settings
				showPSAR = true;
				psarAcceleration = 0.02;
				psarAccelerationMax = 0.2;
				psarAccelerationStep = 0.02;
				psarPlot = new Plot(new Stroke(Brushes.Goldenrod, DashStyleHelper.Solid, 2));
				psarPlot.PlotStyle = PlotStyle.Dot;
				psarPlot.AutoWidth = true;
				
				/// DEFAULT> miscellaneous
				buyModeEnabled = false;
				sellModeEnabled = false;
				fadeModeEnabled = false;
				//-
				#endregion
			}
			else if (State == State.Configure)
			{
				
				#region STATE_CONFIGURE
				//-
				sharedInstanceCnt++;
				if (sharedInstanceCnt == 1)
				{
					sharedOrderList = new Dictionary<string, long>();
					sharedInstanceStrategyId = new List<long>();
				}
//				NinjaTrader.Code.Output.Process( "sharedInstanceCnt: " + sharedInstanceCnt, PrintTo.OutputTab2 );
				highlightColorBullishEntry = convertStaticBrushToCustomColor(backBrushStripeBullishEntry, stripeOpacity);
				highlightColorBullishEntry.Freeze();
				highlightColorBearishEntry = convertStaticBrushToCustomColor(backBrushStripeBearishEntry, stripeOpacity);
				highlightColorBearishEntry.Freeze();
				// Add the slope interceptor indicator
//				AddChartIndicator(tiyfSlopeInterceptor());
				// instantiate the PSAR indicator
				myPSAR = PSAR(psarAcceleration, psarAccelerationMax, psarAccelerationStep);
				if (showPSAR)
				{
					AddChartIndicator(PSAR(psarAcceleration, psarAccelerationMax, psarAccelerationStep));
					myPSAR.Plots[0].Brush = psarPlot.Brush;
					myPSAR.Plots[0].DashStyleHelper = psarPlot.DashStyleHelper;
					myPSAR.Plots[0].Width = psarPlot.Width;
					myPSAR.Plots[0].PlotStyle = psarPlot.PlotStyle;
					myPSAR.Plots[0].Opacity = psarPlot.Opacity;
				}
				rayAttachedTo = stratEasyOrdering_RayAttachedTo.NoSide;
				
				// instantiate the ATR indicator
				myATR = ATR(atrPeriod);
				
				IsTradeInProgress = false;
				barIndexSignalBar = 0;
				PnL_atmStrategy = 0;
				
				psarHH = double.MinValue;
				psarLL = double.MaxValue;
				IsFirstPSARPhaseCompleted = false;
				IsAtmOrderFilled = false;
				AreOCOBracketOrdersReady = false;
				IsTimeOKToMoveStop = false;
				IsTimeOKToBreakEven = false;
				IsBreakEvenDone = false;
				myHLine = null;
				myRay = null;
				IsTLineSelected = false;
				myRegionHLY = null;
				myRectangle = null;
				IsRegionHLYSelected = false;
				sizeOfSelectedDrawing = stopLossExtraMargin = yButtonInitialContent;
				
				stopType = activeStopType = userPref_StopType;
				countStopSteppingBackward = 0;
				currentPainThreshold = 0;
				orderQty = 0;
				fadeType = -1;
				profitToMakeToBreakEven = 0;
				msglevelToExceedCopy = String.Empty;
				//-
				#endregion
  			}
			else if (State == State.DataLoaded)
			{
				if (ChartControl != null && !UserControlCollection.Contains(buttonGrid))
				{
					ChartControl.Dispatcher.InvokeAsync((Action)(() =>
					{
						CreatInsertWPFControls();
					}));
				}
			}
			else if (State == State.Historical)
			{
				#region STATE_HISTORICAL
				//-
				if (ChartControl != null)
				{
					foreach (ChartScale scale in ChartPanel.Scales)
						if (scale.ScaleJustification == ScaleJustification)
							thisChartScale = scale;

					ChartControl.MouseLeftButtonDown += MouseClickedDown;
					ChartControl.PreviewKeyUp += KeyUp;
					ChartControl.PreviewKeyDown += KeyDown;
				}
				//-
				#endregion
			}
			else  if (State == State.Transition)
			{
				#region STATE_TRANSITION
				//-
				lock (Account.All)
				{
					// Get the real world or simulated account configured for the strategy
              		myAccount = Account.All.FirstOrDefault(a => a.Name == Account.Name); // Sim101 Playback101
				}
				// Subscribe to account order updates
				if (myAccount != null)
				{
					DisplayMsg( String.Format("Selected Account: >>> {0} <<<," + Environment.NewLine + "* Please note, to select new entry criteria for the BUY...SELL buttons, press the LEFT or RIGHT shift key.", myAccount) );
					Print("myAccount name :" + myAccount.Name);
					myAccount.OrderUpdate += OnOrderUpdate;
				}
				else
				{
					Log("WARNING ! A valid account name must be selected in the parameters.\nLook up the Setup section/Account property.\n\nThe strategy was disabled.", LogLevel.Alert);
					SetState(State.Terminated);
				}
				//-
				#endregion
			}
			else if (State == State.Terminated)
			{
				#region STATE_TERMINATED
				//-
				if (ChartControl != null)
				{
					ChartControl.MouseLeftButtonDown -= MouseClickedDown;
					ChartControl.PreviewKeyUp -= KeyUp;
					ChartControl.PreviewKeyDown -= KeyDown;
					RemoveWPFControls();
				}

				if (myAccount != null)
				{
					myAccount.OrderUpdate -= OnOrderUpdate;
					myAccount = null;
				}
				if (sharedInstanceCnt > 0)
					sharedInstanceCnt--;
				
				Print("State.Terminated in " + id);
				if (!(sharedOrderList == null))
				{
					if (sharedOrderList.Count > 0)
					{
//						foreach (KeyValuePair<string, long> pair in sharedOrderList)
//						{
//						    Print( pair.Key + "..." + pair.Value );
//						}
						sharedOrderList.tiyfRemoveAll((key, value) => value == this.Id);
					}
				}
				if (sharedInstanceCnt == 0)
				{
					sharedOrderList = null;
					sharedInstanceStrategyId = null;
				}
				Print("sharedInstanceCnt: " + sharedInstanceCnt + " in " + id);
				Print("---");
				//-
				#endregion
			}
			//-
			#endregion
		} // OnStateChange()

		protected override void OnBarUpdate()
		{
			#region OBU
			//-
			double newStopPrice, spaceBetweenAdditonalTarget, firstTargetPrice, newTargetPrice, posAveragePrice, entryPrice, stopLimitOffsetCopy;
			int nbOfOrdersReady = 0;
			string orderName;
			bool did_PSAR_reverse = false;
			
			if (CurrentBar < BarsRequiredToTrade)
				return;
			
			#region Track_PSAR_Activity
			//-
			if (IsFirstTickOfBar) {				
				runningATR = myATR[1];
				did_PSAR_reverse = false;
				/// Check if PSAR just switched from bullish to bearish trend
				if (myPSAR.LongPositionSeries[2] == true && myPSAR.LongPositionSeries[1] == false) {
					did_PSAR_reverse = true;
					if (IsFirstPSARPhaseCompleted && output1) Print( "\n -> psarHH " + psarHH + " confirmed at bar " + (CurrentBar-1) );
					psarLL = double.MaxValue;
					IsFirstPSARPhaseCompleted = true;
					if (isAtmStrategyCreated && tradeDir == 2) IsTimeOKToMoveStop = true;
				}
				/// Check if PSAR just switched from bearish to bullish trend
				if (myPSAR.LongPositionSeries[2] == false && myPSAR.LongPositionSeries[1] == true) {
					did_PSAR_reverse = true;
					if (IsFirstPSARPhaseCompleted && output1) Print( "\n -> psarLL " + psarLL + " confirmed at bar " + (CurrentBar-1) );
					psarHH = double.MinValue;
					IsFirstPSARPhaseCompleted = true;
					if (isAtmStrategyCreated && tradeDir == 1) IsTimeOKToMoveStop = true;
				}
				/// record the HH or LL reached during the current bullish/bearish PSAR trend
				if (myPSAR.LongPositionSeries[1] == false) {
					// PSAR in downtrend
					IsPSARInDownTrend = true;
					psarLL = (Low[1] < psarLL) ? Low[1] : psarLL;
				} else if (myPSAR.LongPositionSeries[1] == true) {
					// PSAR in uptrend
					IsPSARInDownTrend = false;
					psarHH = (High[1] > psarHH) ? High[1] : psarHH;
				}
				
		        if (myRay != null)
				{
					#region ATTACHED_RAY_TO_PSAR_OR_STOPLOSS
					//-
					double psarValue = myPSAR[1];
					double LineHeight;
					DateTime psarTime = Time[1];
					TimeSpan dist2Psar;
					
					if ( !DrawObjects[myRay.Tag].IsSelected )
					{
						IsTLineSelected = false;
						rayAttachedTo = stratEasyOrdering_RayAttachedTo.NoSide;
						myRay = null;
						DisplayMsg("");
					}
					
					if (isAtmStrategyCreated)
					{
						// When a trade is in progress and a Ray object acts as a trendline to follow then attach the Stop to the slope-intercept
						if (rayAttachedTo == stratEasyOrdering_RayAttachedTo.Trailing)
							if (IsFirstTickOfBar && initialStopSize > 0)
								IsTimeOKToMoveStop = true;
					}
					else
					{ // else attach the Ray object to the selected side of the PSAR
						if (rayAttachedTo == stratEasyOrdering_RayAttachedTo.LongSide)
						{	/// Follow ascending trend
							if (!IsPSARInDownTrend)
							{
								dist2Psar = psarTime - myRay.EndAnchor.Time;
								LineHeight = myRay.EndAnchor.Price - myRay.StartAnchor.Price;
								myRay.StartAnchor.Time = myRay.StartAnchor.Time + dist2Psar;
								myRay.StartAnchor.Price = psarValue - LineHeight;
								myRay.EndAnchor.Time = psarTime;
								myRay.EndAnchor.Price = psarValue;
							}
						}
						else if (rayAttachedTo == stratEasyOrdering_RayAttachedTo.ShortSide)
						{	/// Follow descending trend
							if (IsPSARInDownTrend)
							{
								dist2Psar = psarTime - myRay.EndAnchor.Time;
								LineHeight = myRay.EndAnchor.Price - myRay.StartAnchor.Price;
								myRay.StartAnchor.Time = myRay.StartAnchor.Time + dist2Psar;
								myRay.StartAnchor.Price = psarValue - LineHeight;
								myRay.EndAnchor.Time = psarTime;
								myRay.EndAnchor.Price = psarValue;
							}
						}
					}
					//-
					#endregion
				}
			}
			//-
			#endregion
			
			// Make sure this strategy does not execute against historical data
			if(State == State.Historical)
				return;
			
			// Inform the user about the target price to exceed to open a trade
			// it can be the previous bar Hi/Lo or a user drawn HorizonalLine
			DisplayLevelToExceed();

			if (IsFirstTickOfBar)
			{
				/// The mission of the 'fade procedure' is to trigger either the sell or buy button
				/// in regards to the type of fade to monitor (Test, Failed break  or Either Test/Failed break)
				#region TRACK_FADE_OPERATION
				//-
				if (fadeModeEnabled)
				{	// check if we can enable and turn ON the Buy/Sell button and disable the fadeButton accordingly
					
					if (fadeType == 2) /// Fade - Test <- Test
					{
						#region LOGIC_FOR_EVALUATING_A_TEST
						//-
						if ( Close[2] < anchorPrice_HLineOrSlopeIntercept ) /// when selected Hline is above price
						{
							#region HLINE_ABOVE_PRICE
							//-
							// IF bar hits and closes at/or below the Hline, Trigger the Sell button
							if ( High[1] >= anchorPrice_HLineOrSlopeIntercept && Close[1] <= anchorPrice_HLineOrSlopeIntercept )
							{
								sellModeEnabled = true;
								buyModeEnabled = false;
								ChartControl.Dispatcher.InvokeAsync((() =>
								{
									// Enable & Turn ON the Sell button
									buttonSell.IsEnabled = true;
									buttonSell.Background = sellButtonBackgroundColor;
									// Enable & Turn Off the Buy button
									buttonBuy.IsEnabled = true;
									buttonBuy.Background = buttonBackgroundColor;
									// Reset the Fade button and end the current evaluation
									buttonFade.Background = buttonBackgroundColor;
									fadeModeEnabled = false;
									buttonFade.Content = "Fade";
									buttonFade.FontSize = cellFontSize;
								}));
							}
							//-
							#endregion
						}
						else if ( Close[2] > anchorPrice_HLineOrSlopeIntercept ) /// when selected Hline is below price
						{
							#region HLINE_BELOW_PRICE
							//-
							// IF bar hits and closes above the Hline, Trigger the Buy button
							if ( Low[1] <= anchorPrice_HLineOrSlopeIntercept && Close[1] >= anchorPrice_HLineOrSlopeIntercept )
							{
								buyModeEnabled = true;
								sellModeEnabled = false;
								ChartControl.Dispatcher.InvokeAsync((() =>
								{
									// Enable & Turn ON the Buy button
									buttonBuy.IsEnabled = true;
									buttonBuy.Background = buyButtonBackgroundColor;
									// Enable & Turn Off the Sell button
									buttonSell.IsEnabled = true;
									buttonSell.Background = buttonBackgroundColor;
									// Reset the Fade button and end the current evaluation
									buttonFade.Background = buttonBackgroundColor;
									fadeModeEnabled = false;
									buttonFade.Content = "Fade";
									buttonFade.FontSize = cellFontSize;
								}));
							}
							//-
							#endregion
						}
						//-
						#endregion
					}
					else if (fadeType == 3) /// Fade - BOF <- Failed break
					{
						#region LOGIC_FOR_EVALUATING_A_FAILED_BREAK
						//-
						if ( Close[2] < anchorPrice_HLineOrSlopeIntercept ) /// when selected Hline is above price
						{
							#region HLINE_ABOVE_PRICE
							//-
							// IF bar closes above the Hline, 
							if ( Close[1] > anchorPrice_HLineOrSlopeIntercept )
							{	// but within the delimited region, Trigger the Sell button
								if ( Close[1] <= (anchorPrice_HLineOrSlopeIntercept + sizeOfSelectedDrawing * TickSize) )
								{
									sellModeEnabled = true;
									buyModeEnabled = false;
									ChartControl.Dispatcher.InvokeAsync((() =>
									{
										// Enable & Turn ON the Sell button
										buttonSell.IsEnabled = true;
										buttonSell.Background = sellButtonBackgroundColor;
										// Enable & Turn Off the Buy button
										buttonBuy.IsEnabled = true;
										buttonBuy.Background = buttonBackgroundColor;
										// Reset the Fade button and end the current evaluation
										buttonFade.Background = buttonBackgroundColor;
										fadeModeEnabled = false;
										buttonFade.Content = "Fade";
										buttonFade.FontSize = cellFontSize;
									}));
								}
								else
								{	// if we have a long bar that closes behond the delimited region then cancel the fade operation
									revertFadeButtonToItsFormalStyle();
								}
							}
							//-
							#endregion
						}
						else if ( Close[2] > anchorPrice_HLineOrSlopeIntercept ) /// when selected Hline is below price
						{
							#region HLINE_BELOW_PRICE
							//-
							// IF bar closes below the Hline,
							if ( Close[1] < anchorPrice_HLineOrSlopeIntercept )
							{	// but within the delimited region, Trigger the Buy button
								if ( Close[1] >= (anchorPrice_HLineOrSlopeIntercept - sizeOfSelectedDrawing * TickSize) )
								{
									buyModeEnabled = true;
									sellModeEnabled = false;
									ChartControl.Dispatcher.InvokeAsync((() =>
									{
										// Enable & Turn ON the Buy button
										buttonBuy.IsEnabled = true;
										buttonBuy.Background = buyButtonBackgroundColor;
										// Enable & Turn Off the Sell button
										buttonSell.IsEnabled = true;
										buttonSell.Background = buttonBackgroundColor;
										// Reset the Fade button and end the current evaluation
										buttonFade.Background = buttonBackgroundColor;
										fadeModeEnabled = false;
										buttonFade.Content = "Fade";
										buttonFade.FontSize = cellFontSize;
									}));
								}
								else
								{	// if we have a long bar that closes behond the delimited region then cancel the fade operation
									revertFadeButtonToItsFormalStyle();
								}
							}
							//-
							#endregion
						}
						//-
						#endregion
					}
					else if (fadeType == 1) /// Fade - BOF/Test <- Either Test or Failed break
					{
						#region LOGIC_FOR_EVALUATING_EITHER_A_BOF_or_TEST
						//-
						if ( Close[2] < anchorPrice_HLineOrSlopeIntercept ) /// when selected Hline is above price
						{
							#region HLINE_ABOVE_PRICE
							//-
							// IF bar hits the Hline and close within the delimited region, Trigger the Sell button
							if ( High[1] >= anchorPrice_HLineOrSlopeIntercept && Close[1] <= (anchorPrice_HLineOrSlopeIntercept + sizeOfSelectedDrawing * TickSize) )
							{
								sellModeEnabled = true;
								buyModeEnabled = false;
								ChartControl.Dispatcher.InvokeAsync((() =>
								{
									// Enable & Turn ON the Sell button
									buttonSell.IsEnabled = true;
									buttonSell.Background = sellButtonBackgroundColor;
									// Enable & Turn Off the Buy button
									buttonBuy.IsEnabled = true;
									buttonBuy.Background = buttonBackgroundColor;
									// Reset the Fade button and end the current evaluation
									buttonFade.Background = buttonBackgroundColor;
									fadeModeEnabled = false;
									buttonFade.Content = "Fade";
									buttonFade.FontSize = cellFontSize;
								}));
							}
							else
							{
								// if we have a long bar that closes behond the delimited region then cancel the fade operation
								if ( Close[1] > (anchorPrice_HLineOrSlopeIntercept + sizeOfSelectedDrawing * TickSize) )
									revertFadeButtonToItsFormalStyle();
							}
							//-
							#endregion
						}
						else if ( Close[2] > anchorPrice_HLineOrSlopeIntercept ) /// when selected Hline is below price
						{
							#region HLINE_BELOW_PRICE
							//-
							// IF bar hits the Hline and close within the delimited region, Trigger the Buy button
							if ( Low[1] <= anchorPrice_HLineOrSlopeIntercept && Close[1] >= (anchorPrice_HLineOrSlopeIntercept - sizeOfSelectedDrawing * TickSize) )
							{
								buyModeEnabled = true;
								sellModeEnabled = false;
								ChartControl.Dispatcher.InvokeAsync((() =>
								{
									// Enable & Turn ON the Buy button
									buttonBuy.IsEnabled = true;
									buttonBuy.Background = buyButtonBackgroundColor;
									// Enable & Turn Off the Sell button
									buttonSell.IsEnabled = true;
									buttonSell.Background = buttonBackgroundColor;
									// Reset the Fade button and end the current evaluation
									buttonFade.Background = buttonBackgroundColor;
									fadeModeEnabled = false;
									buttonFade.Content = "Fade";
									buttonFade.FontSize = cellFontSize;
								}));
							}
							else
							{
								// if we have a long bar that closes behond the delimited region then cancel the fade operation
								if ( Close[1] < (anchorPrice_HLineOrSlopeIntercept - sizeOfSelectedDrawing * TickSize) )
									revertFadeButtonToItsFormalStyle();
							}
							//-
							#endregion
						}
						//-
						#endregion
					} // endif (fadeType == ?)
				} // endif (fadeModeEnabled)
				else
				{	// at this stage the Buy or Sell button is turned ON
					if (!isAtmStrategyCreated)
					{	// make sure the signal bar occurs within the delimited region and turn OFF the buttons accordingly
						if (fadeType == 2) /// Fade - Test <- Test
						{
							#region CHECK_TEST_VALIDITY
							//-
							if (sellModeEnabled)
							{
								// IF bar closes above the Hline then the Test has failed so we cancel the Fade operation
								if (Close[1] > anchorPrice_HLineOrSlopeIntercept) 
								{
									revertFadeButtonToItsFormalStyle();
								}
							}
							else if (buyModeEnabled)
							{
								// IF bar closes below the Hline then the Test has failed so we cancel the Fade operation
								if (Close[1] < anchorPrice_HLineOrSlopeIntercept) 
								{
									revertFadeButtonToItsFormalStyle();
								}
							} //endif (buyModeEnabled)
							//-
							#endregion
						}
						else if (fadeType == 3) /// Fade - BOF <- Failed break
						{
							#region CHECK_BOF_VALIDITY
							//-
							if (sellModeEnabled)
							{	// if bar closes above the delimited region then cancel the fade operation
								if ( Close[1] > (anchorPrice_HLineOrSlopeIntercept + sizeOfSelectedDrawing * TickSize) )
								{
									revertFadeButtonToItsFormalStyle();
								}
							}
							else if (buyModeEnabled)
							{	// if bar closes below the delimited region then cancel the fade operation
								if ( Close[1] < (anchorPrice_HLineOrSlopeIntercept - sizeOfSelectedDrawing * TickSize) )
								{
									revertFadeButtonToItsFormalStyle();
								}
							} //endif (buyModeEnabled)
							//-
							#endregion
						}
						else if (fadeType == 1) /// Fade - BOF/Test <- Either Test or Failed break
						{
							#region CHECK_BOF_TEST_VALIDITY
							//-
							if (sellModeEnabled)
							{	// if bar closes above the delimited region then cancel the fade operation
								if ( Close[1] > (anchorPrice_HLineOrSlopeIntercept + sizeOfSelectedDrawing * TickSize) )
								{
									revertFadeButtonToItsFormalStyle();
								}
							}
							else if (buyModeEnabled)
							{	// if bar closes below the delimited region then cancel the fade operation
								if ( Close[1] < (anchorPrice_HLineOrSlopeIntercept - sizeOfSelectedDrawing * TickSize) )
								{
									revertFadeButtonToItsFormalStyle();
								}
							} //endif (buyModeEnabled)							
							//-
							#endregion
						}
					} // endif (!isAtmStrategyCreated)
					else
					{
						if (idxButtonContent == 2 && fadeType > 0)
						{
							// cancel the stop limit order if it does not fire within the delimited region
							if ( orderId.Length > 0 && IsTLineSelected )
							{
								string[] orderStatus = GetAtmStrategyEntryOrderStatus(orderId);
								if (orderStatus.GetLength(0) > 0)
								{
									if (orderStatus[2] == "Accepted" || orderStatus[2] == "Working")
									{
										if (fadeType == 2) /// Fade - Test <- Test
										{
											#region CHECK_IF_ORDER_WITHIN_DELIMITED_REGION
											if (sellModeEnabled)
											{
												// IF bar closes above the Hline then the Test has failed so we cancel the order
												if (Close[1] > anchorPrice_HLineOrSlopeIntercept) 
												{
													fadeType = -1;
													AtmStrategyCancelEntryOrder(orderId);
												}
											}
											else if (buyModeEnabled)
											{
												// IF bar closes below the Hline then the Test has failed so we cancel the order
												if (Close[1] < anchorPrice_HLineOrSlopeIntercept) 
												{
													fadeType = -1;
													AtmStrategyCancelEntryOrder(orderId);
												}
											} //endif (buyModeEnabled)
											#endregion
										}
										else if (fadeType == 3) /// Fade - BOF <- Failed break
										{
											#region CHECK_IF_ORDER_WITHIN_DELIMITED_REGION
											//-
											if (sellModeEnabled)
											{	// if bar closes above the delimited region then cancel the order
												if ( Close[1] > (anchorPrice_HLineOrSlopeIntercept + sizeOfSelectedDrawing * TickSize) )
												{
													fadeType = -1;
													AtmStrategyCancelEntryOrder(orderId);
												}
											}
											else if (buyModeEnabled)
											{	// if bar closes below the delimited region then cancel the order
												if ( Close[1] < (anchorPrice_HLineOrSlopeIntercept - sizeOfSelectedDrawing * TickSize) )
												{
													fadeType = -1;
													AtmStrategyCancelEntryOrder(orderId);
												}
											} //endif (buyModeEnabled)
											//-
											#endregion
										}
										else if (fadeType == 1) /// Fade - BOF/Test <- Either Test or Failed break
										{
											#region CHECK_IF_ORDER_WITHIN_DELIMITED_REGION
											//-
											if (sellModeEnabled)
											{	// if bar closes above the delimited region then cancel the order
												if ( Close[1] > (anchorPrice_HLineOrSlopeIntercept + sizeOfSelectedDrawing * TickSize) )
												{
													fadeType = -1;
													AtmStrategyCancelEntryOrder(orderId);
												}
											}
											else if (buyModeEnabled)
											{	// if bar closes below the delimited region then cancel the order
												if ( Close[1] < (anchorPrice_HLineOrSlopeIntercept - sizeOfSelectedDrawing * TickSize) )
												{
													fadeType = -1;
													AtmStrategyCancelEntryOrder(orderId);
												}
											} //endif (buyModeEnabled)							
											//-
											#endregion
										}
									}
								} //endif (orderStatus.GetLength(0) > 0)
							} // endif (orderId.Length > 0)
						} // endif (idxButtonContent == 2)
					} // endif else
				} // endif else (fadeModeEnabled)
				//-
				#endregion
			} // endif (IsFirstTickOfBar)
			
			// if no trade is in progress
			if (!isAtmStrategyCreated)
			{	// and no buttons (Buy/Sell) have been pressed or triggered, no need to go any further
				if ( !(buyModeEnabled || sellModeEnabled) )
					return;
			}

			// make sure there is no ATM strategy order currently active
			if (orderId.Length == 0 && atmStrategyId.Length == 0)
			{
				/// *** CONDITIONS to fill to go long/short ***
				#region CHECK_CONDITIONS
				//-
				tradeDir = -1; // tradeDir == 1 when bullish condition fulfilled, tradeDir == 2 when bearish condition fulfilled
				
				switch (idxButtonContent) {
				case 1: // C>TLine or C<TLine /buy if bar close > selected Horizontal/Ray Line/-/Sell if bar close < selected Horizontal/Ray Line/
						
					#region idxButtonContent_1
					//-
					if (IsFirstTickOfBar)
					{
						if(IsTLineSelected)
						{
							if (buyModeEnabled) /// If Buy button is turned ON
							{
								if ( Close[1] > Open[1] ) // Is the current bar bullish ?
								{
									// Did it close above the selected Horizontal/Ray Line ?
									if (anchorPrice_HLineOrSlopeIntercept > 0)
										if ( Close[1] > anchorPrice_HLineOrSlopeIntercept ) tradeDir = 1;
								}
							}

							if (sellModeEnabled) /// If Sell button is turned ON
							{
								if ( Close[1] < Open[1] ) // Is the current bar bearish ?
								{
									// Did it close below the selected Horizontal/Ray Line ?
									if (anchorPrice_HLineOrSlopeIntercept > 0)
									 if ( Close[1] < anchorPrice_HLineOrSlopeIntercept ) tradeDir = 2;
								}
							}
						}
					}
					//-
					#endregion
						
					break;
				case 2: // BO H[1] or BO L[1] /buy if price crosses previous bar high/-/Sell if price crosses previous bar low
						
					#region idxButtonContent_2
					//-
					if (buyModeEnabled) /// If Buy button is turned ON
					{
						if (GetCurrentAsk() <= High[1] + stopLimitMargin * TickSize)
						{
							tradeDir = 1;
						}
					}

					if (sellModeEnabled) /// If Sell button is turned ON
					{
						if (GetCurrentBid() >= Low[1] - stopLimitMargin * TickSize)
						{
							tradeDir = 2;
						}
					}
					//-
					#endregion
						
					break;
				case 3: // C+ve or C-ve /buy if bar closes up/-/Sell if bar closes down/
						
					#region idxButtonContent_3
					//-
					if (IsFirstTickOfBar)
					{
						if (buyModeEnabled) /// If Buy button is turned ON
						{
							if ( Close[1] > Open[1] ) // Is the current bar bullish ?
							{
								tradeDir = 1;
							}
						}

						if (sellModeEnabled) /// If Sell button is turned ON
						{
							if ( Close[1] < Open[1] ) // Is the current bar bearish ?
							{
								tradeDir = 2;
							}
						}
					}
					//-
					#endregion
						
					break;
				case 4: // C+|-ve or C-|+ve /buy at bar close/-/Sell at bar close/
						
					#region idxButtonContent_4
					//-
					if (IsFirstTickOfBar)
					{
						if (buyModeEnabled) /// If Buy button is turned ON
						{
							tradeDir = 1;
						}

						if (sellModeEnabled) /// If Sell button is turned ON
						{
							tradeDir = 2;
						}
					}
					//-
					#endregion
						
					break;
				case 5: // Psar(↓↑)...Psar(↑↓) Buy or Sell at bar close when the Parabolic Sar reverses direction
						
					#region idxButtonContent_5
					//-
					if (IsFirstTickOfBar)
					{
						if (buyModeEnabled) /// If Buy button is turned ON
						{
							if (did_PSAR_reverse && !IsPSARInDownTrend)
								// Parabolic Sar changes direction from Down to UP
								if ( Close[1] > Open[1] ) // Is the current bar bullish ?
									tradeDir = 1;
						}

						if (sellModeEnabled) /// If Sell button is turned ON
						{
							if (did_PSAR_reverse && IsPSARInDownTrend)
								// Parabolic Sar changes direction from UP to Down
								if ( Close[1] < Open[1] ) // Is the current bar bearish ?
									tradeDir = 2;
						}
					}
					//-
					#endregion
						
					break;
				default: // C>H[1] buy if bar close > previous bar high or C<L[1] Sell if bar close < previous bar low
						
					#region idxButtonContent_0
					//-
					if (IsFirstTickOfBar)
					{
						if (buyModeEnabled) /// If Buy button is turned ON
						{
							if ( Close[1] > Open[1] ) // Is the current bar bullish ?
							{
								// Did it close above the previous bar high ?
								if ( Close[1] > High[2] ) tradeDir = 1;
							}
						}

						if (sellModeEnabled) /// If Sell button is turned ON
						{
							if ( Close[1] < Open[1] ) // Is the current bar bearish ?
							{
								// Did it close below the previous bar low ?
								if ( Close[1] < Low[2] ) tradeDir = 2;
							}
						}
					}
					//-
					#endregion
		
					break;
				} //end switch
				//-
				#endregion
			} //if (orderId.Length == 0 && atmStrategyId.Length == 0)
			
			if (orderId.Length == 0 && atmStrategyId.Length == 0 && tradeDir > -1)
			{
				/// *** OPEN TRADE AS A RESULT ***
				#region CREATE_ATM
				//-
				PrintTo = PrintTo.OutputTab2;
				ClearOutputWindow();
				PrintTo = PrintTo.OutputTab1;
				ClearOutputWindow();
				// make sure the user has selected a saved ATM template in the chart trader panel (Custom ATM strategy is not accepted)
				atmTemplateName = GetATMStrategy();
				if ( !(atmTemplateName != null) ) {
					Log("WARNING !\nThe Order has been skipped as no ATM Strategy template has been selected. As a result, the strategy has been disabled. Corrective action:\n1) Open the Chart Trader panel\n2) Select an ATM strategy\n3) Re-enable the Ninjascript strategy.", LogLevel.Alert);
					SetState(State.Terminated); // disable the strategy if no saved ATM template is selected
				}
				cntAtmBracket = parseAtmXMLfile(); // get nb of stop/target lines defined in the current ATM strategy template
				if (cntAtmBracket == -1)
					return;
				
				isAtmStrategyCreated = isAtmConfigured = AreOCOBracketOrdersReady = false;
				atmStrategyId = GetAtmStrategyUniqueId(); // unique identifier for the ATM strategy
				orderId = GetAtmStrategyUniqueId(); // unique identifier for the entry order
				if (sharedInstanceStrategyId.IndexOf(this.Id) == -1) 
					sharedInstanceStrategyId.Add(this.Id);
				IsEntryFullyFilled = false;
				
				barIndexSignalBar = CurrentBar - 1;
				entryPrice = ( idxButtonContent != 2 ) ? 0 : (tradeDir == 1) ? High[1] + stopLimitMargin * TickSize : Low[1] - stopLimitMargin * TickSize;
				//output1
				if (output1) Print(String.Format( "> New entry signal triggered on chart id: {0} @ Bar: {1}", id, barIndexSignalBar) );
				stopLimitOffsetCopy = (idxButtonContent != 2) ? 0 : stopLimitOffset;
				orderList.Clear();
				
//				AtmStrategyCreate(OrderAction, OrderType, double limitPrice, double stopPrice, TimeInForce, ...
				AtmStrategyCreate( (tradeDir == 1) ? OrderAction.Buy : OrderAction.Sell, (idxButtonContent != 2) ? OrderType.Market : OrderType.StopLimit, (tradeDir == 1) ? entryPrice + stopLimitOffsetCopy * TickSize : entryPrice - stopLimitOffsetCopy * TickSize, entryPrice, TimeInForce.Day, orderId, atmTemplateName, atmStrategyId, (atmCallbackErrorCode, atmCallBackId) => {
					// check that the ATM Strategy is successfully started
					if (atmCallbackErrorCode == ErrorCode.NoError && atmCallBackId == atmStrategyId)
						isAtmStrategyCreated = true;
				} );
				//-
				#endregion
			}

			// Check that atm strategy was created before checking other properties
			if (!isAtmStrategyCreated)
				return;
			else if (!isAtmConfigured)
			{	// to be done once after the Atm creation
				#region CONFIGURE_ATM
				//-
				if (output1) Print("CONFIGURE_ATM");
				isAtmConfigured = true;
				PnL_atmStrategy = 0;
				entryOrderFinalStatus = string.Empty;
				IsUserRequestToCloseAtm_InProgress = false;
				rayAttachedTo = stratEasyOrdering_RayAttachedTo.NoSide;
				//
				IsAtmOrderFilled = false;
				IsTimeOKToMoveStop = false;
				IsInitialStopLossSet = false;
				//
				initialStopSize = 0;
				profitToMakeToBreakEven = 0;
				IsTimeOKToBreakEven = false;
				IsBreakEvenDone = false;
				if (idxButtonContent != 2) fadeType = -1;
				targetsMovedAtDesiredReward = false; // Take profit orders are updated once at the start of a new trade
				jumpStopbyXpercentClicked = false;
				if (showMarkers && idxButtonContent != 2)
				{
					// Draw an arrow above/below the signal bar
					if (tradeDir == 1)
						Draw.ArrowUp(this, "ArrowAt"+CurrentBar.ToString(), true, CurrentBar - barIndexSignalBar, Low[CurrentBar - barIndexSignalBar] - TickSize*3, arrowColorSignalBar);
					else
						Draw.ArrowDown(this, "ArrowAt"+CurrentBar.ToString(), true, CurrentBar - barIndexSignalBar, High[CurrentBar - barIndexSignalBar] + TickSize*3, arrowColorSignalBar);
					
					// Draw a vertical stripe behind the entry bar on all chart panels
					BackBrushesAll[0] = (tradeDir == 1) ? highlightColorBullishEntry : highlightColorBearishEntry;
					// https://ninjatrader.com/support/helpGuides/nt8/NT%20HelpGuide%20English.html?backbrushall.htm
				}
				ChartControl.Dispatcher.InvokeAsync((() =>
				{
					buttonFade.Background = buttonDisabledBackgroundColor;
					buttonFade.IsEnabled = false;
				}));
				//-
				#endregion
			}
			
			if (orderId.Length > 0)
			{
				#region MONITOR_ENTRY_ORDER_STATUS
				//-
				// https://ninjatrader.com/support/helpGuides/nt8/?order_state_definitions.htm
				
				string[] orderStatus = GetAtmStrategyEntryOrderStatus(orderId);
				// If the status call can't find the order specified, the return array length will be zero otherwise it will hold elements
				if (orderStatus.GetLength(0) > 0)
				{
					entryOrderFinalStatus = orderStatus[2];
					if (orderStatus[2] == "Filled")
					{
						IsAtmOrderFilled = true;
						orderId = string.Empty;
						countOnBarUpdateSinceOrderFilled = 0;
						currentPainThreshold = (tradeDir == 1) ? double.MinValue : double.MaxValue;

						if (idxButtonContent == 2)
						{
							fadeType = -1;
							if (showMarkers)
							{
								// Draw an arrow above/below the signal bar
								if (tradeDir == 1)
									Draw.ArrowUp(this, "ArrowAt"+CurrentBar.ToString(), true, CurrentBar - barIndexSignalBar, Low[CurrentBar - barIndexSignalBar] - TickSize*3, arrowColorSignalBar);
								else
									Draw.ArrowDown(this, "ArrowAt"+CurrentBar.ToString(), true, CurrentBar - barIndexSignalBar, High[CurrentBar - barIndexSignalBar] + TickSize*3, arrowColorSignalBar);
								
								// Draw a vertical stripe behind the entry bar on all chart panels
								BackBrushesAll[0] = (tradeDir == 1) ? highlightColorBullishEntry : highlightColorBearishEntry;
								// https://ninjatrader.com/support/helpGuides/nt8/NT%20HelpGuide%20English.html?backbrushall.htm
							}
						}
					}
					else if (orderStatus[2] == "Partially filled")
					{
						if (idxButtonContent == 2) fadeType = -1;
					}
					else if (orderStatus[2] == "Accepted" || orderStatus[2] == "Working")
					{
						if (idxButtonContent == 2)
						{	// Move the Stop limit order on each new bar closer to price
							if (IsFirstTickOfBar)
							{	// AtmStrategyChangeEntryOrder(double limitPrice, double stopPrice, string orderId)
								if (tradeDir == 1)
								{
									entryPrice = High[1] + stopLimitMargin * TickSize;
//									Print( String.Format("{2}> GetCurrentAsk({0}) <= entryPrice[{1}]", GetCurrentAsk(), entryPrice, CurrentBar-1) );
									if (GetCurrentAsk() <= entryPrice)
									{
										barIndexSignalBar = CurrentBar - 1;
//										Print( String.Format("barIndexSignalBar: {3} > GetCurrentAsk(){0} < High[1]{1}, entryPrice{2}", GetCurrentAsk(), High[1], entryPrice, barIndexSignalBar) );
										AtmStrategyChangeEntryOrder(entryPrice + stopLimitOffset * TickSize, entryPrice, orderId);
									}
								}
								else
								{
									entryPrice = Low[1] - stopLimitMargin * TickSize;
//									Print( String.Format("{2}> GetCurrentBid({0}) >= entryPrice[{1}]", GetCurrentBid(), entryPrice, CurrentBar-1) );
									if (GetCurrentBid() >= entryPrice)
									{
										barIndexSignalBar = CurrentBar - 1;
//										Print( String.Format("barIndexSignalBar: {3} > GetCurrentBid(){0} < Low[1]{1}, entryPrice{2}", GetCurrentAsk(), Low[1], entryPrice, barIndexSignalBar) );
										AtmStrategyChangeEntryOrder(entryPrice - stopLimitOffset * TickSize, entryPrice, orderId);
									}
								}
							}
						}
					}
					// If the order state is terminal, reset key variables
					else if (orderStatus[2] == "Cancelled" || orderStatus[2] == "Rejected")
					{
						orderId = string.Empty;
					}
				} // endif (orderStatus.GetLength(0) > 0)
				//-
				#endregion
				
				// keep monitoring until entry order is filled, cancelled or rejected
				if (orderId.Length > 0)
					return;
			} // endif (orderId.Length > 0)
			
			// If the strategy has terminated conclude the ATM
			if (atmStrategyId.Length > 0 && GetAtmStrategyMarketPosition(atmStrategyId) == Cbi.MarketPosition.Flat)
			{	
				concludeATM();
			}
			// If the ATM strategy has been reset then no need to go any further
			if ( atmStrategyId.Length == 0 )
				return;

			// Otherwise if the ATM is still in progress then Update the Stop Loss(es) and Target(s)
			if (!IsUserRequestToCloseAtm_InProgress)
			{
				#region UPDATE_STOP
				// check to do before updating the stop loss(es) & target(s):
				// wait for all Stop loss(es) to be accepted or target(s) in a working state
				if (!AreOCOBracketOrdersReady)
				{
					if (orderList.Count > 0)
					{
						nbOfOrdersReady = 0;
						foreach (KeyValuePair<int, CBracket> pair in bracketList)
						{
							if ( (pair.Value.orderStateStop == OrderState.Accepted) && (pair.Value.orderStateTarget == OrderState.Working) )
								nbOfOrdersReady++;
						}
						if (nbOfOrdersReady == cntAtmBracket)
						{
							AreOCOBracketOrdersReady = true;
							IsTimeOKToMoveStop = true;
							if (output1) Print( String.Format("All OCO bracket orders ready after {0} OBU",  countOnBarUpdateSinceOrderFilled) );
						}
						countOnBarUpdateSinceOrderFilled++;
					}
					// if not ready then wait for another OBU event
					if (!AreOCOBracketOrdersReady)
						return;
				}

				/// note: IsTimeOKToMoveStop = true
				// 1) when all stop(s) & target(s) have been placed and accepted according to the ATM settings
				// 2) when a new PSAR swing has formed (see track PSAR activity region)
				// 3) when the profit to break even has been hit
				// 4) when the middle button (Dn or Up by x%) has been clicked
				// 5) when a bar close and a Ray object acts as a trailing stop
				
				if (initialStopSize > 0 && !IsBreakEvenDone)
				{
					// the method GetAtmStrategyUnrealizedProfitLoss() returns the results in dollar
					if (GetAtmStrategyUnrealizedProfitLoss(atmStrategyId) >= profitToMakeToBreakEven)
					{
						if (output1) Print("*** Time to move stop loss to break even ***");
						IsTimeOKToBreakEven = true;
						IsTimeOKToMoveStop = true;
					}
				}
				if (IsTimeOKToMoveStop)
				{
					if (GetAtmStrategyMarketPosition(atmStrategyId) == MarketPosition.Long)
					{
						manageAtmLongPosition();
					}
					else if (GetAtmStrategyMarketPosition(atmStrategyId) == MarketPosition.Short)
					{
						manageAtmShortPosition();
					}
					IsTimeOKToMoveStop = false;
				}
				//-
				#endregion
			}
			//-
			#endregion
		} // OBU
	
		private void manageAtmLongPosition()
		{
			#region LONG_SETUP
			//-
			double newStopPrice, newTargetPrice, spaceBetweenAdditonalTarget, firstTargetPrice, posAveragePrice, stopLossNearestToPrice;
			string orderName;
//			string[,] stopTargetOrdersStatus; // receives value from method GetAtmStrategyStopTargetOrderStatus(...)

			if (output1) Print("in manageAtmLongPosition");
			
			newStopPrice = 0;
			posAveragePrice = GetAtmStrategyPositionAveragePrice(atmStrategyId);
			if (IsTimeOKToBreakEven && breakEvenRatio > 0)
			{
				// calculate the break even level
				newStopPrice = posAveragePrice + breakEvenMargin*TickSize;
				//reset the stop loss extra margin to the initial value
				sizeOfSelectedDrawing = stopLossExtraMargin = yButtonInitialContent;
				ChartControl.Dispatcher.InvokeAsync((() =>
				{
					buttonArea.Content = "Y=" + sizeOfSelectedDrawing.ToString() + "t+";
				}));
				// if Break Even called by user (Click on Middle button while LeftCTRL pressed) then
				// Revert to the default behavior for the Middle button (Up+ x%)
				if (jumpStopbyXpercentClicked)
				{
					IsTimeOKToBreakEven = false;
					IsBreakEvenDone = true;
					ChartControl.Dispatcher.InvokeAsync((() =>
					{
						buttonStopType.Content = contentMidButton;
						buttonStopType.ToolTip = tooltipMidButton;
					}));
				}
			}
			else
			{
				if ( jumpStopbyXpercentClicked )
				{
					if (initialStopSize > 0)
					{
						stopLossNearestToPrice = getStopLossNearestToPrice();
						newStopPrice = stopLossNearestToPrice + Instrument.MasterInstrument.RoundToTickSize( (Close[0] - stopLossNearestToPrice) * jumpStopbyXPercent );
					}
					else
						jumpStopbyXpercentClicked = false;
				}
				else
				{
			        if ( myRay != null && rayAttachedTo == stratEasyOrdering_RayAttachedTo.Trailing ) // do we have a Ray line selected
					{
						update_AnchorPrice();
						newStopPrice = anchorPrice_HLineOrSlopeIntercept;
					}
					else
					{
						if (activeStopType == stratEasyOrdering_StopType.PSAR_Swing)
						{
							newStopPrice = psarLL - stopLossExtraMargin * TickSize;
						}
						else if (activeStopType == stratEasyOrdering_StopType.ATR)
						{
							newStopPrice = posAveragePrice - (stopLossExtraMargin * TickSize) - Instrument.MasterInstrument.RoundToTickSize(myATR[CurrentBar - barIndexSignalBar] * atrMultiple);
							if (output1) Print( "Extra room (ATR): " +  (stopLossExtraMargin * TickSize) + Instrument.MasterInstrument.RoundToTickSize(myATR[CurrentBar - barIndexSignalBar] * atrMultiple) );
						}
						else // activeStopType == stratEasyOrdering_StopType.Signal_Bar
						{
							newStopPrice = Low[CurrentBar - barIndexSignalBar] - stopLossExtraMargin * TickSize;
							if (newStopPrice > posAveragePrice) newStopPrice = posAveragePrice; // enforce the use of the minimum size as defined in the ATM strategy template
						}
					}
				}
				if (initialStopSize == 0)
				{	// make sure the initial stop has a minimum size (as defined in the 1st target line of the ATM strategy template)
					if (output1) Print(newStopPrice + " / " + bracketList[1].stopPrice + " / " + stopLossExtraMargin);
					if (newStopPrice > bracketList[1].stopPrice)
						newStopPrice = bracketList[1].stopPrice;
					if ( IsStopLossManaged )
						initialStopSize = Math.Abs( posAveragePrice - newStopPrice );
					else
						initialStopSize = Math.Abs( posAveragePrice - getStopLossNearestToPrice() );
					DisplayProfitToMakeToBE();
					// once the initial stop has been set, make sure the PSAR_Swing is the active method for trailing stop
					activeStopType = stratEasyOrdering_StopType.PSAR_Swing;
					// keep a copy of the content in case the user leftCTRL-click on Middle button to revert back to this default info
					contentMidButton = "Up+" + (jumpStopbyXPercent * 100).ToString() + "%";
					tooltipMidButton = "Press this button to move the Stop Lost Up by " + (jumpStopbyXPercent * 100).ToString() + "%";
					ChartControl.Dispatcher.InvokeAsync((() =>
					{
						buttonStopType.Content = contentMidButton;
						buttonStopType.ToolTip = tooltipMidButton;
					}));
				}
			}

			if (jumpStopbyXpercentClicked)
			{
				jumpStopbyXpercentClicked = false;
				changeAllStopLines( newStopPrice );
			}
			else if ( IsStopLossManaged ) // if stop managed by strat
			{
				stopLossNearestToPrice = getStopLossNearestToPrice();
				if (IsTimeOKToBreakEven && !IsBreakEvenDone)
				{
					IsTimeOKToBreakEven = false;
					IsBreakEvenDone = true;
					if (breakEvenRatio > 0)
						if ( newStopPrice > stopLossNearestToPrice )
							changeAllStopLines( newStopPrice );
				}
				else
				{
					if (!IsInitialStopLossSet)
					{
						IsInitialStopLossSet = true;
						changeAllStopLines( newStopPrice );
					}
					else
					{
						if (newStopPrice > stopLossNearestToPrice )
							changeAllStopLines( newStopPrice );
					}
				}
			}

			/// Update TARGETS (LONG in progress)
			if (IsTargetManaged && !targetsMovedAtDesiredReward)
			{
				firstTargetPrice = Instrument.MasterInstrument.RoundToTickSize( posAveragePrice + initialStopSize * rewardRatio );
				spaceBetweenAdditonalTarget = Instrument.MasterInstrument.RoundToTickSize( initialStopSize * rewardRatio2 );
				for (int i = 1; i <= cntAtmBracket; i++)
				{
					if (i == 1)
						newTargetPrice = firstTargetPrice;
					else
						newTargetPrice = firstTargetPrice + spaceBetweenAdditonalTarget * (i-1);
					
					 // make sure a target has been defined in the ATM strategy template (Target? > 0)
					if (bracketList[i].ticksProfit > 0)
					{
						if (bracketList[i].orderStateTarget == OrderState.Working)
						{
							if (output1) Print( String.Format("\nUpdating target position (Target{0}): {1}",  i, newTargetPrice) );
							orderName = "Target" + i.ToString();
							AtmStrategyChangeStopTarget(newTargetPrice, 0, orderName, atmStrategyId);
						}
					}
				}
				targetsMovedAtDesiredReward = true;
			}
			//-
			#endregion
		} // end manageAtmLongPosition()
		
		private void manageAtmShortPosition()
		{
			#region SHORT_SETUP
			//-
			double newStopPrice, newTargetPrice, spaceBetweenAdditonalTarget, firstTargetPrice, posAveragePrice, stopLossNearestToPrice;
			string orderName;
//			string[,] stopTargetOrdersStatus; // receives value from method GetAtmStrategyStopTargetOrderStatus(...)
			
			if (output1) Print("in manageAtmShortPosition");

			newStopPrice = 0;
			posAveragePrice = GetAtmStrategyPositionAveragePrice(atmStrategyId);
			if (IsTimeOKToBreakEven && breakEvenRatio > 0)
			{
				// calculate the break even level
				newStopPrice = posAveragePrice - breakEvenMargin*TickSize;
				//reset the stop loss extra margin to the initial value
				sizeOfSelectedDrawing = stopLossExtraMargin = yButtonInitialContent;
				ChartControl.Dispatcher.InvokeAsync((() =>
				{
					buttonArea.Content = "Y=" + sizeOfSelectedDrawing.ToString() + "t+";
				}));
				// if Break Even called by user (Click on Middle button while LeftCTRL pressed) then
				// Revert to the default behavior for the Middle button (Dn- x%)
				if (jumpStopbyXpercentClicked)
				{
					IsTimeOKToBreakEven = false;
					IsBreakEvenDone = true;
					ChartControl.Dispatcher.InvokeAsync((() =>
					{
						buttonStopType.Content = contentMidButton;
						buttonStopType.ToolTip = tooltipMidButton;
					}));
				}
			}
			else
			{						
				if ( jumpStopbyXpercentClicked )
				{
					if (initialStopSize > 0)
					{
						stopLossNearestToPrice = getStopLossNearestToPrice();
						newStopPrice = stopLossNearestToPrice - Instrument.MasterInstrument.RoundToTickSize( (stopLossNearestToPrice - Close[0]) * jumpStopbyXPercent );
					}
					else
						jumpStopbyXpercentClicked = false;
				}
				else
				{
			        if ( myRay != null && rayAttachedTo == stratEasyOrdering_RayAttachedTo.Trailing ) // do we have a Ray line selected
					{
						update_AnchorPrice();
						newStopPrice = anchorPrice_HLineOrSlopeIntercept;
					}
					else
					{
						if (activeStopType == stratEasyOrdering_StopType.PSAR_Swing)
						{
							newStopPrice = psarHH + stopLossExtraMargin * TickSize;
						}
						else if (activeStopType == stratEasyOrdering_StopType.ATR)
						{
							newStopPrice = posAveragePrice + (stopLossExtraMargin * TickSize) + Instrument.MasterInstrument.RoundToTickSize(myATR[CurrentBar - barIndexSignalBar] * atrMultiple);
							if (output1) Print( "Extra room (ATR): " +  (stopLossExtraMargin * TickSize) + Instrument.MasterInstrument.RoundToTickSize(myATR[CurrentBar - barIndexSignalBar] * atrMultiple) );
						}
						else // activeStopType == stratEasyOrdering_StopType.Signal_Bar
						{
							newStopPrice = High[CurrentBar - barIndexSignalBar] + stopLossExtraMargin * TickSize;
							if (newStopPrice < posAveragePrice) newStopPrice = posAveragePrice; // enforce the use of the minimum size as defined in the ATM strategy template 
						}
					}
				}
				if (initialStopSize == 0)
				{	// make sure the initial stop has a minimum size (as defined in the 1st target line of the ATM strategy template)
					if (output1) Print(newStopPrice + " / " + bracketList[1].stopPrice + " / " + stopLossExtraMargin);
					if (newStopPrice < bracketList[1].stopPrice)
						newStopPrice = bracketList[1].stopPrice;
					if ( IsStopLossManaged )
						initialStopSize = Math.Abs( posAveragePrice - newStopPrice );
					else
						initialStopSize = Math.Abs( posAveragePrice - getStopLossNearestToPrice() );
					DisplayProfitToMakeToBE();
					// once the initial stop has been set, make sure the PSAR_Swing is the active method for trailing stop
					activeStopType = stratEasyOrdering_StopType.PSAR_Swing;
					// keep a copy of the content in case the user leftCTRL-click on Middle button to revert back to this default info
					contentMidButton = "Dn-" + (jumpStopbyXPercent * 100).ToString() + "%";
					tooltipMidButton = "Press this button to move the Stop Lost Down by " + (jumpStopbyXPercent * 100).ToString() + "%";
					ChartControl.Dispatcher.InvokeAsync((() =>
					{
						buttonStopType.Content = contentMidButton;
						buttonStopType.ToolTip = tooltipMidButton;
					}));
				}
			}

			if (jumpStopbyXpercentClicked)
			{
				jumpStopbyXpercentClicked = false;
				changeAllStopLines( newStopPrice );
			}
			else if ( IsStopLossManaged ) // if stop managed by strat
			{
				stopLossNearestToPrice = getStopLossNearestToPrice();
				if (IsTimeOKToBreakEven && !IsBreakEvenDone)
				{
					IsTimeOKToBreakEven = false;
					IsBreakEvenDone = true;
					if (breakEvenRatio > 0)
						if (newStopPrice < stopLossNearestToPrice)
							changeAllStopLines( newStopPrice );
				}
				else
				{
					if (!IsInitialStopLossSet)
					{
						IsInitialStopLossSet = true;
						changeAllStopLines( newStopPrice );
					}
					else
					{
						if (newStopPrice < stopLossNearestToPrice)
							changeAllStopLines( newStopPrice );
					}
				}
			}
			
			/// Update TARGETS (SHORT in progress)
			if (IsTargetManaged && !targetsMovedAtDesiredReward)
			{
				firstTargetPrice = Instrument.MasterInstrument.RoundToTickSize( posAveragePrice - initialStopSize * rewardRatio );
				spaceBetweenAdditonalTarget = Instrument.MasterInstrument.RoundToTickSize( initialStopSize * rewardRatio2 );
				for (int i = 1; i <= cntAtmBracket; i++)
				{
					if (i == 1)
						newTargetPrice = firstTargetPrice;
					else
						newTargetPrice = firstTargetPrice - spaceBetweenAdditonalTarget * (i-1);

					 // make sure a target has been defined in the ATM strategy template (Target? > 0)
					if (bracketList[i].ticksProfit > 0)
					{
						if (bracketList[i].orderStateTarget == OrderState.Working)
						{
							if (output1) Print( String.Format("\nUpdating target position (Target{0}): {1}",  i, newTargetPrice) );
							orderName = "Target" + i.ToString();
							AtmStrategyChangeStopTarget(newTargetPrice, 0, orderName, atmStrategyId);
						}
					}
				}
				targetsMovedAtDesiredReward = true;
			}
			//- endregion SHORT_SETUP
			#endregion
		} // end manageAtmShortPosition()
		
		private double getStopLossNearestToPrice()
		{
			// find the stop price nearest to the current Close[0]
			// used when a group of stop loss orders have been splitted by the user manually
			// or when  we have to move the stop loss to a new location
			double nearestToClose, distanceToClose;
			int indexKey = 1;
			
			nearestToClose = Double.MaxValue;
			for (int i = 1; i <= cntAtmBracket; i++)
			{
				distanceToClose = Math.Abs(Close[0] - bracketList[i].stopPrice);
				if (distanceToClose < nearestToClose)
				{
					nearestToClose =  distanceToClose;
					indexKey = i;
				}
			}
			return bracketList[indexKey].stopPrice;
		}
	
		private void changeAllStopLines(double stopPrice)
		{
			/// Move all stop Loss orders to a new location
			#region CHANGE_All_STOPLINES
			//-
			string orderName;
			
			if (output1)
			{
				Print("in changeAllStopLines...\n[...");
				string str2Print = String.Format( " tradeDir = {0}\n stopPrice = {1}\n GetCurrentBid() = {2}\n---", tradeDir , stopPrice , GetCurrentBid() );
				Print(str2Print);
			}
			
			if (tradeDir == 1) // if long
			{
				// make sure it is safe to move the stop loss given the CurrentBid
				if ( stopPrice >= GetCurrentBid() ) return;
			}
			else // if short
			{
				// make sure it is safe to move the stop loss given the CurrentAsk
				if ( stopPrice <= GetCurrentAsk() ) return;
			}
			if (output1) Print("Check of GetCurrentBid() / GetCurrentAsk() passed ...\n...]");
			
			// loop through all lines as defined in the ATM strategy template
			for (int x = 1; x <= cntAtmBracket; x++)
			{
				orderName = "Stop" + x.ToString();
				if (bracketList[x].orderStateStop == OrderState.Accepted)
				{
					if (output1) Print( String.Format("\nUpdating stop loss (Stop{0}): {1}",  x, stopPrice) );
					AtmStrategyChangeStopTarget(0, stopPrice, orderName, atmStrategyId);
				}
			} //end for...loop
			//-
			#endregion
		}
		
		private void concludeATM()
		{
			#region CONCLUDE_ATM
			//-
			if (entryOrderFinalStatus == "Filled")
			{
			 	// Draw a vertical stripe behind the exit bar on all chart panels
				BackBrushesAll[0] = (tradeDir == 1) ? highlightColorBearishEntry : highlightColorBullishEntry;
				PnL_atmStrategy = GetAtmStrategyRealizedProfitLoss( atmStrategyId );
//					if (true) = if (output1)
				if (output1) Print( String.Format("The trade is over: PnL: {0} at bar {1}", PnL_atmStrategy, CurrentBar) );
			}
			else if (entryOrderFinalStatus == "Cancelled" || entryOrderFinalStatus == "Rejected")
			{
				if (output1) Print("Entry Order Cancelled at bar " + CurrentBar);
			}
			atmCreatedInInstanceId = 0;
			isAtmStrategyCreated = AreOCOBracketOrdersReady = false; /// reset key flag
			atmStrategyId = string.Empty; /// reset key flag
			barIndexSignalBar = 0;
			tradeDir = -1;
			fadeType = -1;
			resetBothTheBuySellButtons();
			if (IsTLineSelected)
			{
				// Must use ChartControl.Dispatcher.InvokeAsync when accessing an object like a button because the NinjaScript object runs on a non-UI thread:
				ChartControl.Dispatcher.InvokeAsync((() =>
				{
					buttonFade.Background = buttonBackgroundColor;
					buttonFade.IsEnabled = true;
				}));
				fadeModeEnabled = false;
			}
			
			activeStopType = stopType;
			
			string thisContent = string.Empty;
			if (stopType == stratEasyOrdering_StopType.PSAR_Swing)
				thisContent = "PSAR";
				else if (stopType == stratEasyOrdering_StopType.Signal_Bar)
					thisContent = "S.Bar";
					else if (stopType == stratEasyOrdering_StopType.ATR)
						thisContent = "ATR";
			ChartControl.Dispatcher.InvokeAsync((() =>
			{
				buttonStopType.Content = thisContent;
				buttonStopType.ToolTip = "Press this button to cycle through the types of stop to use\nto calculate the initial risk";
			}));
					
			foreach (COrder xO in orderList)
				if (output1) Print( String.Format("{5} {0} {1} {2} {3} {4}", xO.id, xO.name, xO.quantity, xO.price, xO.orderState, id) );
			if (output1) Print("--- end of CONCLUDE_ATM");
			
			DisplayMsg(" ");
			//-
			#endregion
		}

		private void OnOrderUpdate(object sender, OrderEventArgs e)
		{
			#region ON_ORDER_UPDATE
			//-
			int bracketKey, idx;
			double ePrice;
			AtmStrategy atmOwnerStrategy;
			StrategyBase stratbase;
			
			if (output1)
			{
				if (e.OrderState == OrderState.Initialized)
					NinjaTrader.Code.Output.Process(string.Format("{0}", "---"), PrintTo.OutputTab2);
				NinjaTrader.Code.Output.Process(string.Format("{0}: {1} {2} ({3}) {4}", 
					id, e.OrderId, e.Order.Name, (e.StopPrice + e.LimitPrice),  e.OrderState), PrintTo.OutputTab2);
			}

			// ?? means... If whatever is to the left is not null, use that, otherwise use what's to the right
			stratbase = e.Order.GetOwnerStrategy() ?? null;
			
			// not all orders has an OwnerStrategy ex. Close order will return null
			// the name "AtmStrategy" is returned for all orders which are created with any of the buttons on the Chart trader panel
			atmOwnerStrategy = stratbase as AtmStrategy;
			if (atmOwnerStrategy == null)
				return;
			else if (atmOwnerStrategy.Name == "AtmStrategy")
				return;

			/// filter messages to keep only those that belong to the order created in this instance
			if (!sharedOrderList.ContainsKey(atmOwnerStrategy.Name))
			{
				sharedOrderList.Add( atmOwnerStrategy.Name, sharedInstanceStrategyId[0] );
				sharedInstanceStrategyId.Remove(this.Id);
			}
			/// if order event does not belong to this instance then skip event
			if (sharedOrderList[atmOwnerStrategy.Name] != this.Id)
				return;
			
			// only 1 of these 3 items will be > 0
			ePrice = e.AverageFillPrice + e.LimitPrice + e.StopPrice;
			// find the order to update
			idx = orderList.FindIndex(a => a.id == e.OrderId);
			if (idx != -1)
			{
				// if Order exits in list modify it
				orderList[idx].price = ePrice;
				orderList[idx].orderState = e.OrderState;
			}
			else
			{
				// if not, add order to the list
				orderList.Add(new COrder() { id = e.OrderId, name = e.Order.Name, quantity = e.Quantity, price = ePrice, orderState = e.OrderState } );				
				idx = orderList.Count - 1;
			}

//			NinjaTrader.Code.Output.Process( String.Format("{0}: ({1}) {2} {3} {4}", 
//				id, orderList[idx].id, orderList[idx].name, orderList[idx].price, orderList[idx].orderState), PrintTo.OutputTab1);

			if (e.Order.Name.ToUpper().Contains("ENTRY"))
			{
				if (e.Filled == e.Quantity)
				{
					IsEntryFullyFilled = true;
				}
			}
			else if (e.Order.Name.ToUpper().Contains("STOP"))
			{
				// strip out the word STOP
				bracketKey = int.Parse( e.Order.Name.ToUpper().Replace("STOP", "") );
				bracketList[bracketKey].stopPrice = e.StopPrice;
				bracketList[bracketKey].orderStateStop = e.OrderState;
			}
			else if (e.Order.Name.ToUpper().Contains("TARGET"))
			{
				// strip out the word TARGET
				bracketKey = int.Parse( e.Order.Name.ToUpper().Replace("TARGET", "") );
				bracketList[bracketKey].limitPrice = e.LimitPrice;
				bracketList[bracketKey].orderStateTarget = e.OrderState;
			}
			
//			if (true) //output1
//			{
//				if (e.OrderState == OrderState.Initialized)
//					NinjaTrader.Code.Output.Process(string.Format("{0}", "---"), PrintTo.OutputTab2);
//				NinjaTrader.Code.Output.Process(string.Format("{0}: ({1}) {2} {3}", 
//					id, e.OrderId, e.Order.Name, e.OrderState), PrintTo.OutputTab2);
//			}
			
			//-
			#endregion
		}

		private void KeyUp(object sender, System.Windows.Input.KeyEventArgs e)
		{
			/// loop through all variations of the Buy & Sell buttons when one of these keys is pressed
			
			#region KEYUP_PRESSED
			//-
			string strMsg = string.Empty;
			
			if (e.Key == Key.Tab)
			{
				if (myRay != null)
				{
					if (!isAtmStrategyCreated)
					{
						double minPrice = Math.Min(myRay.EndAnchor.Price, myRay.StartAnchor.Price);
						double maxPrice = Math.Max(myRay.EndAnchor.Price, myRay.StartAnchor.Price);
						double midAnchorPrice = (maxPrice - minPrice) / 2;
						midAnchorPrice = minPrice + midAnchorPrice;
						if (midAnchorPrice > Bars.GetClose(ChartBars.Count-1))
						{
							rayAttachedTo = stratEasyOrdering_RayAttachedTo.ShortSide;
							strMsg = "The selected Ray will start to follow the PSAR trend on the SHORT side on the next bar onward...";
						}
						else
						{
							rayAttachedTo = stratEasyOrdering_RayAttachedTo.LongSide;
							strMsg = "The selected Ray will start to follow the PSAR trend on the LONG side on the next bar onward...";
						}
					}
					else
					{
						rayAttachedTo = stratEasyOrdering_RayAttachedTo.Trailing;
						strMsg = "The selected Ray will act as a trailing Stop on the next bar onward...";
					}
				}
				else
				{
					rayAttachedTo = stratEasyOrdering_RayAttachedTo.NoSide;
					strMsg = "Warning! The TAB key is used to either attach..." +  Environment.NewLine +"A) A selected Ray object to the PSAR or B) the Stop Loss to a selected Ray (if trade in progress)!";
				}
				DisplayMsg(strMsg);
			}
			else if (e.Key == Key.LeftShift || e.Key == Key.RightShift)
			{
				if (!isAtmStrategyCreated)
				{
					idxButtonContent++;
					if (idxButtonContent == contentBuyButton.Count) idxButtonContent = 0;
					buttonBuy.Content = contentBuyButton[ idxButtonContent ];
					buttonSell.Content = contentSellButton[ idxButtonContent ];
					
					switch (idxButtonContent)
					{
					case 1:
						if (IsTLineSelected)
						{
							if (buyModeEnabled)
								DisplayMsg( string.Format("IF bar closes +ve & above {0} THEN a Buy market order will be submitted", Math.Round(anchorPrice_HLineOrSlopeIntercept, 2)) );
								else if (sellModeEnabled)
									DisplayMsg( string.Format("IF bar closes -ve & below {0} THEN a Sell market order will be submitted", Math.Round(anchorPrice_HLineOrSlopeIntercept, 2)) );
									else
										DisplayMsg("Buy if bar closes above any selected Horizontal/Ray Line or Sell if bar closes below any selected Horizontal/Ray line");
						}
						else
						{
							if (buyModeEnabled || sellModeEnabled)
							{
								DisplayMsg("An Horizontal or Ray line object must be selected to trigger the C+>TLine or C-<TLine buttons.");
								resetBothTheBuySellButtons();
							}
							else
							{
								DisplayMsg("Buy if bar closes above any selected Horizontal/Ray line or Sell if bar closes below any selected Horizontal/Ray line");
							}
						}
								
						break;
					case 2:
						if (buyModeEnabled)
							DisplayMsg( string.Format("Buy Stop Limit order will be submitted at the previous bar high") );
							else if (sellModeEnabled)
								DisplayMsg( string.Format("Sell Stop Limit order will be submitted at the previous bar low") );
								else
									DisplayMsg("Put a Buy Stop Limit order at the previous bar high or a Sell Stop Limit order at the previous bar low");
							
						break;
					case 3:
						if (buyModeEnabled)
							DisplayMsg("IF bar closes +ve THEN a Buy market order will be submitted");
							else if (sellModeEnabled)
								DisplayMsg("IF bar closes -ve THEN a Sell market order will be submitted");
								else
									DisplayMsg("Buy if bar closes positive (+ve) or Sell if bar closes negative (-ve)");
							
						break;
					case 4:
						if (buyModeEnabled)
							DisplayMsg("A Buy market order will be submitted at bar close regardless the closed sign (+ve or -ve)");
							else if (sellModeEnabled)
								DisplayMsg("A Sell market order will be submitted at bar close regardless the closed sign (+ve or -ve)");
								else
									DisplayMsg("Buy or Sell at bar close regardless the closed sign (+ve or -ve)");
							
						break;
					case 5:
						if (buyModeEnabled)
							DisplayMsg("A Buy market order will be submitted when both the Parabolic Sar reverses UP and bar closes +ve");
							else if (sellModeEnabled)
								DisplayMsg("A Sell market order will be submitted when both the Parabolic Sar reverses DOWN and bar closes -ve");
								else
									DisplayMsg("Buy or Sell when both the Parabolic Sar reverses and bar closes in the new direction");
							
						break;
					default:
						if (buyModeEnabled)
							DisplayMsg("IF bar closes +ve & above previous bar high THEN a Buy market order will be submitted");
							else if (sellModeEnabled)
								DisplayMsg("IF bar closes -ve & below previous bar low THEN a Sell market order will be submitted");
								else
									DisplayMsg("Buy if bar closes +ve and above the previous bar high or Sell if bar closes -ve and below the previous bar low");
							
						break;
					} // end switch
				} //endif (!isAtmStrategyCreated)
			} //endif (e.Key == Key.LeftShift || e.Key == Key.RightShift)
			else if (e.Key == Key.LeftCtrl)
			{
				if (IsStopLossManaged)
				{
					if (AreOCOBracketOrdersReady)
					{ // revert content to the default behavior
						buttonStopType.Content = contentMidButton;
						buttonStopType.ToolTip = tooltipMidButton;
						DisplayMsg("");
					}
				}
			}
			//-
			#endregion
		}
		
		protected void KeyDown(object sender, System.Windows.Input.KeyEventArgs e)
		{
			#region KEYDOWN_PRESSED
			//-
			if (e.Key == Key.LeftCtrl)
			{
				if (IsStopLossManaged)
				{
					if (AreOCOBracketOrdersReady)
					{
						if (!IsBreakEvenDone)
						{
							if (buttonStopType.Content != "Go2BE")
							{
								buttonStopType.Content = "Go2BE";
								buttonStopType.ToolTip = "Move Stop Loss to Break Even";
								DisplayMsg( "Click the middle button to move the Stop Loss to Break Even..." );
							}
						}
					}
				}
			}
			//-
			#endregion
		}
		
		private void closeAtm()
		{
			if (isAtmStrategyCreated)
			{	/// Close ATM in progress
				if (!IsUserRequestToCloseAtm_InProgress)
				{
					if (entryOrderFinalStatus == "Filled")
					{
						IsUserRequestToCloseAtm_InProgress = true; // request allowed once per trade
//						Print( String.Format("---\n{0} Request[1] to close executed order at bar: {1}", id, CurrentBar) );
//						Print( " UnrealizedProfitLoss: " + GetAtmStrategyUnrealizedProfitLoss(atmStrategyId).ToString() );
//						Print( " RealizedProfitLoss: " + GetAtmStrategyRealizedProfitLoss(atmStrategyId).ToString() );
						if (atmStrategyId.Length > 0)
							AtmStrategyClose(atmStrategyId);
					}
					else if (entryOrderFinalStatus == "Working" || entryOrderFinalStatus == "Accepted")
					{
						IsUserRequestToCloseAtm_InProgress = true; // request allowed once per trade
//						Print( String.Format("---\n{0} Request[2] to close Working/Accepted order at bar: ", id, CurrentBar) );
						if (atmStrategyId.Length > 0)
							AtmStrategyClose(atmStrategyId);
					}
				}
			}
		}
		
		protected void MouseClickedDown(object sender, MouseButtonEventArgs e)
		{
			/// find out if an HorizontalLine, Ray, RegionHighlightY or Rectangle has been selected
			/// enable/disable buttons accordingly
			#region MOUSECLICKEDDOWN
			//-
		
			NinjaTrader.NinjaScript.DrawingTools.Ray selectedRayObject = null; // ref. of the selected Ray object
			IsTLineSelected = false;
			IsRegionHLYSelected = false;
			IsRectangleSelected = false;
			myHLine = null;
			myRegionHLY = null;
			myRectangle = null;
			foreach ( DrawingTool drawTool in DrawObjects.ToList() )
			{
				if ( drawTool.GetType().ToString().Contains(".HorizontalLine") )
				{
					if( drawTool.IsUserDrawn && drawTool.IsSelected )
					{
						// set a ref to the selected drawing tool
				        myHLine = drawTool as DrawingTools.Line;
						IsTLineSelected = true;
						
						break;
					}
				}
				else if ( drawTool.GetType().ToString().Contains(".Ray") )
				{
					if( drawTool.IsUserDrawn && drawTool.IsSelected )
					{
						// set a ref to the selected drawing tool
						selectedRayObject = drawTool as DrawingTools.Ray;
						IsTLineSelected = true;
						
						break;
					}
				}
				else if ( drawTool.GetType().ToString().Contains(".RegionHighlightY") )
				{
					if( drawTool.IsUserDrawn && drawTool.IsSelected )
					{
						// set a ref to the selected drawing tool
				        myRegionHLY = drawTool as DrawingTools.RegionHighlightY;
						IsRegionHLYSelected = true;
						
						break;
					}
				}
				else if ( drawTool.GetType().ToString().Contains(".Rectangle") )
				{
					if( drawTool.IsUserDrawn && drawTool.IsSelected )
					{
						// set a ref to the selected drawing tool
				        myRectangle = drawTool as DrawingTools.Rectangle;
						IsRectangleSelected = true;
						
						break;
					}
				}
			}

			if (selectedRayObject == null)
			{
				myRay = null;
				rayAttachedTo = stratEasyOrdering_RayAttachedTo.NoSide;
			}
			else
			{
				if (myRay != null)
				{ // if TAG name different for both objects then user needs to press/release TAB key to trail stop loss
					if (myRay.Tag != selectedRayObject.Tag)
						rayAttachedTo = stratEasyOrdering_RayAttachedTo.NoSide;
				}
				else
				{
					rayAttachedTo = stratEasyOrdering_RayAttachedTo.NoSide;
				}
				myRay = DrawObjects[selectedRayObject.Tag] as DrawingTools.Ray;
//				myRay = (NinjaTrader.NinjaScript.DrawingTools.Ray)selectedRayObject.Clone();
			}
			
			if ( IsRegionHLYSelected || IsRectangleSelected )
			{
				if (!buttonArea.IsEnabled)
				{ // enable and turn on the button
					buttonArea.IsEnabled = true;
					buttonArea.Background = buttonBackgroundColor;
				}
			}
			else
			{
				if (buttonArea.IsEnabled)
				{ // disable and dim the button
					buttonArea.IsEnabled = false;
					buttonArea.Background = buttonDisabledBackgroundColor;
				}
			}

			if (IsTLineSelected)
			{
				if (!buttonFade.IsEnabled)
				{
					// if buttonFade is disabled and an Hline or Ray is selected turn it on if not in a trade
					// 
					if (isAtmStrategyCreated) // check to do if in a trade
					{
						if (myRay != null)
						{
							if (rayAttachedTo != stratEasyOrdering_RayAttachedTo.Trailing)
								DisplayMsg("The selected Ray can be used to trail your Stop Loss IF you press/release the TAB key!");
						}
						else // then it is an Hline and has no utility when a trade is in progress
						{
							DisplayMsg("Selecting an Horizontal Line has no effect when a trade is in progress!");
						}
					}
					else // check to do if not in a trade
					{ // enable and turn on the button
						buttonFade.IsEnabled = true;
						buttonFade.Background = buttonBackgroundColor;
						fadeModeEnabled = false;						
					}
				}
			}
			else
			{
				if (isAtmStrategyCreated)
					DisplayProfitToMakeToBE();
				else
					DisplayMsg(" ");
				
				if (buttonFade.IsEnabled)
				{
					// disable & reset Fade button
					buttonFade.IsEnabled = false;
					buttonFade.Background = buttonDisabledBackgroundColor;
					buttonFade.FontSize = cellFontSize;
					buttonFade.Content = "Fade";
					fadeType = -1;
					if (fadeModeEnabled)
					{
						fadeModeEnabled = false;
						// enable & reset Buy and Sell buttons
						buttonBuy.IsEnabled = true;
						buttonBuy.Background = buttonBackgroundColor;
						buyModeEnabled = false;
						buttonSell.IsEnabled = true;
						buttonSell.Background = buttonBackgroundColor;
						sellModeEnabled = false;
					}
				}
			}
			
			DisplayLevelToExceed();
			//-
			#endregion
		}

		private void OnButtonClick(object sender, RoutedEventArgs rea)
		{
			#region ON_BUTTON_CLICK
			//-
			System.Windows.Controls.Button button = sender as System.Windows.Controls.Button;
			double curATRmultiple = Instrument.MasterInstrument.RoundToTickSize(runningATR * atrMultiple);
			double stopSizeLongSide, stopSizeShortSide;
			double minProfitToGo2BE = 0;
			
			
			if ( button == buttonBuy )
			{
				fadeType = -1;
				if (sellModeEnabled)
				{ // turn Off the Sell button
					buttonSell.Background = buttonBackgroundColor;
					sellModeEnabled = false;
					if (isAtmStrategyCreated) closeAtm();
				}
				
				if (buyModeEnabled)
				{	// turn Off the Buy button if it was already ON
					buttonBuy.Background = buttonBackgroundColor;
					buyModeEnabled = false;
					if (isAtmStrategyCreated) closeAtm();
				}
				else
				{	// turn ON the Buy button
					buttonBuy.Background = buyButtonBackgroundColor;
					buyModeEnabled = true;
				}
			}
			else if ( button == buttonStopType )
			{
				if (!AreOCOBracketOrdersReady)
				{
					if (stopType == stratEasyOrdering_StopType.PSAR_Swing) // PSAR (1), Signal bar (2), ATR (3)
					{
						stopType = stratEasyOrdering_StopType.Signal_Bar;
						buttonStopType.Content = "S.Bar";
						DisplayMsg( "Initial stop loss based on the Signal Bar high/low" );
					}
					else if (stopType == stratEasyOrdering_StopType.Signal_Bar)
					{
						stopType = stratEasyOrdering_StopType.ATR;
						buttonStopType.Content = "ATR";
						DisplayMsg( string.Format("Initial stop loss based on a multiple ({0}x) of the ATR ({1}) => {2}pts, + extra margin ({3}t)", atrMultiple, Math.Round(runningATR,2), curATRmultiple, stopLossExtraMargin) );
					}
					else if (stopType == stratEasyOrdering_StopType.ATR)
					{
						stopSizeLongSide = psarLL - stopLossExtraMargin * TickSize;
						stopSizeLongSide = Math.Abs( stopSizeLongSide - Bars.GetClose(ChartBars.Count-1) );
						stopSizeShortSide = psarHH + stopLossExtraMargin * TickSize;
						stopSizeShortSide = Math.Abs( stopSizeShortSide - Bars.GetClose(ChartBars.Count-1) );
						stopType = stratEasyOrdering_StopType.PSAR_Swing;
						buttonStopType.Content = "PSAR";
						DisplayMsg( string.Format("Initial stop loss based on Parabolic Sar. From the last bar close...if long ({0}pts), if short ({1}pts), include extra margin ({2}t)", stopSizeLongSide, stopSizeShortSide, stopLossExtraMargin) );
					}
					activeStopType = stopType;
				}
				else
				{
					if ( Keyboard.IsKeyDown(Key.LeftCtrl) )
					{
						minProfitToGo2BE = breakEvenMargin * TickSize;
						minProfitToGo2BE = minProfitToGo2BE * Bars.Instrument.MasterInstrument.PointValue;
						if ( GetAtmStrategyUnrealizedProfitLoss(atmStrategyId) > minProfitToGo2BE )
						{
							IsTimeOKToMoveStop = jumpStopbyXpercentClicked = IsTimeOKToBreakEven = true;
						}
						else
						{
							// stop loss can go to break even ONLY if price is in positive territory
							DisplayMsg( "Stop Loss can go to break even ONLY if price is in positive territory..." );
						}
					}
					else
					{
						IsTimeOKToMoveStop = jumpStopbyXpercentClicked = true;
					}
				}
				return;
			}
			else if ( button == buttonSell )
			{
				fadeType = -1;
				if (buyModeEnabled)
				{	// turn Off the Buy button
					buttonBuy.Background = buttonBackgroundColor;
					buyModeEnabled = false;
					if (isAtmStrategyCreated) closeAtm();
				}
				
				if (sellModeEnabled)
				{	// turn Off the Sell if it was already ON
					buttonSell.Background = buttonBackgroundColor;
					sellModeEnabled = false;
					if (isAtmStrategyCreated) closeAtm();
				}
				else
				{	// turn ON the Sell button
					buttonSell.Background = sellButtonBackgroundColor;
					sellModeEnabled = true;
				}
			}
			else if ( button == buttonFade )
			{
				if (fadeModeEnabled)
				{
					/// On each click on the fade button cycle through the various type of fade
					if (fadeType == 1) // 1 = BOF|Test, 2 = Test, 3 = BOF
					{
						fadeType = 2;
						buttonFade.Content = "Test";
						buttonFade.FontSize = cellFontSize;
					}
					else if (fadeType == 2)
					{
						fadeType = 3;
						buttonFade.Content = "BOF";
						buttonFade.FontSize = cellFontSize;
					}
					else if (fadeType == 3)
					{
						fadeType = 1;
						buttonFade.Content = "BOF|Test";
						buttonFade.FontSize = cellFontSize-1;
					}
				}
				else
				{
					// disable both the Buy and Sell buttons
					buttonBuy.IsEnabled = false;
					buttonBuy.Background = buttonDisabledBackgroundColor;
					buyModeEnabled = false;
					buttonSell.IsEnabled = false;
					buttonSell.Background = buttonDisabledBackgroundColor;
					sellModeEnabled = false;
					
					// turn ON the fade mode
					fadeType = 1; // BOF|Test
					fadeModeEnabled = true;
					buttonFade.Content = "BOF|Test";
					buttonFade.FontSize = cellFontSize-1;
					buttonFade.Background = fadeButtonBackgroundColor;
				}
			}
			else if ( button == buttonArea )
			{
				if (IsRegionHLYSelected || IsRectangleSelected)
				{
					if (IsRegionHLYSelected)
						sizeOfSelectedDrawing = Math.Abs( Instrument.MasterInstrument.RoundToTickSize( myRegionHLY.EndAnchor.Price ) - Instrument.MasterInstrument.RoundToTickSize( myRegionHLY.StartAnchor.Price ) );
					else
						sizeOfSelectedDrawing = Math.Abs( Instrument.MasterInstrument.RoundToTickSize( myRectangle.EndAnchor.Price ) - Instrument.MasterInstrument.RoundToTickSize( myRectangle.StartAnchor.Price ) );					
					sizeOfSelectedDrawing = stopLossExtraMargin = sizeOfSelectedDrawing / TickSize; // sizeOfSelectedDrawing = Heigth of selected drawing object in ticks
					// if leftctrl key is pressed while clicking on the buttonArea then
					// do not change the Stop Loss Margin
					if ( Keyboard.IsKeyDown(Key.LeftCtrl) )
					{
						// apply the sizeOfSelectedDrawing to the Fade operation only
						buttonArea.Content = "Y=" + sizeOfSelectedDrawing.ToString() + "t";
						stopLossExtraMargin = yButtonInitialContent;
					}
					else
					{ 
						// apply the sizeOfSelectedDrawing to the Fade operation and Stop Loss management
						buttonArea.Content = "Y=" + sizeOfSelectedDrawing.ToString() + "t+";
					}
				}
			}
					
			DisplayLevelToExceed();
			//-
			#endregion
		}
		
		private void resetBothTheBuySellButtons()
		{
			#region RESET_BUY_SELL_BUTTONS
			//-
			if (sellModeEnabled)
			{
				ChartControl.Dispatcher.InvokeAsync((() =>
				{
					buttonSell.Background = buttonBackgroundColor;
					buttonSell.IsEnabled = true;
				}));
				sellModeEnabled = false;
			}
			if (buyModeEnabled)
			{
				ChartControl.Dispatcher.InvokeAsync((() =>
				{
					buttonBuy.Background = buttonBackgroundColor;
					buttonBuy.IsEnabled = true;
				}));
				buyModeEnabled = false;
			}
			//-
			#endregion
		}
		
		private void revertFadeButtonToItsFormalStyle()
		{
			#region REVERT_FADE_BUTTON
			//-
			fadeType = -1;
			sellModeEnabled = false;
			buyModeEnabled = false;
			ChartControl.Dispatcher.InvokeAsync((() =>
			{
				// Enable & Turn Off the Sell button
				buttonSell.IsEnabled = true;
				buttonSell.Background = buttonBackgroundColor;
				// Enable & Turn Off the Buy button
				buttonBuy.IsEnabled = true;
				buttonBuy.Background = buttonBackgroundColor;
				// Reset the Fade button and end the current evaluation
				buttonFade.Background = buttonBackgroundColor;
				fadeModeEnabled = false;
				buttonFade.Content = "Fade";
				buttonFade.FontSize = cellFontSize;
			}));
			DisplayMsg("The Fade operation was cancelled as the signal did not trigger.");
			//-
			#endregion
		}		

		private void CreatInsertWPFControls()
		{
			#region CREATE_INSERT_WPF_CONTROLS
			//-
			// create controls here
			// set event handlers here
			// set rows and columns
			System.Windows.Media.FontFamily cellFont = new FontFamily("Consolas, Courier");
			System.Windows.FontWeight cellFontWeight = FontWeights.ExtraBold;
			
			buttonGrid = new System.Windows.Controls.Grid
			{ // Margin (left, top, right, bottom)
				Name = "MyCustomGrid", HorizontalAlignment = hAlignment, VerticalAlignment = vAlignment, Margin = new Thickness(1, 1, 0, 0), Width = 70
			};
			buttonGrid.ShowGridLines = false;
			
//			System.Windows.Controls.ColumnDefinition 	column1 = new System.Windows.Controls.ColumnDefinition();
//			System.Windows.Controls.ColumnDefinition 	column2 = new System.Windows.Controls.ColumnDefinition();
			System.Windows.Controls.RowDefinition		row1 = new System.Windows.Controls.RowDefinition();
			System.Windows.Controls.RowDefinition		row2 = new System.Windows.Controls.RowDefinition();
			System.Windows.Controls.RowDefinition		row3 = new System.Windows.Controls.RowDefinition();
			System.Windows.Controls.RowDefinition		row4 = new System.Windows.Controls.RowDefinition();
			System.Windows.Controls.RowDefinition		row5 = new System.Windows.Controls.RowDefinition();

//			buttonGrid.ColumnDefinitions.Add(column1);
//			buttonGrid.ColumnDefinitions.Add(column2);
			buttonGrid.RowDefinitions.Add(row1);
			buttonGrid.RowDefinitions.Add(row2);
			buttonGrid.RowDefinitions.Add(row3);
			buttonGrid.RowDefinitions.Add(row4);
			buttonGrid.RowDefinitions.Add(row5);
			
/// 		ex. 1- how to underline a text label (create a TextBlock object)
//			System.Windows.Controls.TextBlock labelBuyButton = new System.Windows.Controls.TextBlock()
//			{
//				Text = "",
//				TextDecorations = null
//			};
//			labelBuyButton.Text = "C+>H[1]";
//			labelBuyButton.TextDecorations = TextDecorations.Underline; // = null to remove any text decoration

			///Buttons attributes
			idxButtonContent = 0; // idxButtonContent == 0 at creation time. This is the default behavior of the "Buy>" and "Sell<" buttons
			buttonBuy = new System.Windows.Controls.Button { Name = "buy", Content = "C+>H[1]", ToolTip = "Enable/Disable Buying mode or Close trade", Foreground = buttonForegroundColor, Background = buttonBackgroundColor, Margin = new Thickness(1, 0, 1, 2), HorizontalAlignment = HorizontalAlignment.Center, FontFamily = cellFont, FontWeight = cellFontWeight, FontSize = cellFontSize };
/// 		ex. 2- how to underline a text label (remove the field: Content = "C+>H[1]")
//			buttonBuy = new System.Windows.Controls.Button { Name = "buy", ToolTip = "Enable/Disable Buying mode or Close trade", Foreground = buttonForegroundColor, Background = buttonBackgroundColor, Margin = new Thickness(1, 0, 1, 2), HorizontalAlignment = HorizontalAlignment.Center, FontFamily = cellFont, FontWeight = cellFontWeight, FontSize = cellFontSize };
			buttonStopType = new System.Windows.Controls.Button { Name = "buyStopType", Content = "", ToolTip = "Press this button to cycle through the types of stop to use\nto calculate the initial risk", Foreground = buttonForegroundColor, Background = stopTypeButtonBackgroundColor, Margin = new Thickness(1, 0, 1, 2), HorizontalAlignment = HorizontalAlignment.Center, FontFamily = cellFont, FontWeight = cellFontWeight, FontSize = cellFontSize };
			buttonSell = new System.Windows.Controls.Button { Name = "sell", Content = "C-<L[1]", ToolTip = "Enable/Disable Selling mode or Close trade", Foreground = buttonForegroundColor, Background = buttonBackgroundColor, Margin = new Thickness(1, 0, 1, 2), HorizontalAlignment = HorizontalAlignment.Center, FontFamily = cellFont, FontWeight = cellFontWeight, FontSize = cellFontSize };
			buttonFade = new System.Windows.Controls.Button { Name = "fade", Content = "Fade", ToolTip = "Set the type of Fade:\n\n> BOF (Breakout failure), \n> Test (strictly enforced), \n> either BOF|Test", Foreground = buttonForegroundColor, Background = buttonDisabledBackgroundColor, Margin = new Thickness(1, 20, 1, 2), HorizontalAlignment = HorizontalAlignment.Center, FontFamily = cellFont, FontWeight = cellFontWeight, FontSize = cellFontSize };
			buttonArea = new System.Windows.Controls.Button { Name = "area", Content = "Y=" + yButtonInitialContent.ToString() + "t+", ToolTip = "Set the size of the area to be used\n\n> to limit the extent of a BOF signal and/or\n> to give extra room to your stop loss (...t+)", Foreground = buttonForegroundColor, Background = buttonDisabledBackgroundColor, Margin = new Thickness(1, 0, 1, 2), HorizontalAlignment = HorizontalAlignment.Center, FontFamily = cellFont, FontWeight = cellFontWeight, FontSize = cellFontSize };
/// 		ex. 3- how to underline a text label (add the content via the object labelBuyButton)
//			buttonBuy.Content = labelBuyButton;
			
			if (stopType == stratEasyOrdering_StopType.PSAR_Swing)
					buttonStopType.Content = "PSAR";
				else if (stopType == stratEasyOrdering_StopType.Signal_Bar)
						buttonStopType.Content = "S.Bar";
					else if (stopType == stratEasyOrdering_StopType.ATR)
							buttonStopType.Content = "ATR";
			
			buttonBuy.Click += OnButtonClick;
			buttonStopType.Click += OnButtonClick;
			buttonSell.Click += OnButtonClick;
			buttonFade.Click += OnButtonClick;
			buttonFade.IsEnabled = false;
			buttonArea.Click += OnButtonClick;
			buttonArea.IsEnabled = false;
					
			System.Windows.Controls.Grid.SetRow(buttonBuy, 0);
			System.Windows.Controls.Grid.SetRow(buttonStopType, 1);
			System.Windows.Controls.Grid.SetRow(buttonSell, 2);
			System.Windows.Controls.Grid.SetRow(buttonFade, 3);
			System.Windows.Controls.Grid.SetRow(buttonArea, 4);
//			System.Windows.Controls.Grid.SetColumn(buttonBuy, 0);
//			System.Windows.Controls.Grid.SetColumn(buttonSell, 1);

			buttonGrid.Children.Add(buttonBuy);
			buttonGrid.Children.Add(buttonStopType);
			buttonGrid.Children.Add(buttonSell);
			buttonGrid.Children.Add(buttonFade);
			buttonGrid.Children.Add(buttonArea);

			UserControlCollection.Add(buttonGrid);
			//-
			#endregion
		}

		private void RemoveWPFControls()
		{
			#region REMOVE_WPF_CONTROLS
			//-
			// remove any handlers
			Dispatcher.InvokeAsync((() =>
			{
				if (buttonGrid != null)
				{
					if (buttonBuy != null)
					{
						buttonBuy.Click -= OnButtonClick;
						buttonGrid.Children.Remove(buttonBuy);
						buttonBuy = null;
					}
					if (buttonStopType != null)
					{
						buttonStopType.Click -= OnButtonClick;
						buttonGrid.Children.Remove(buttonStopType);
						buttonStopType = null;
					}
					if (buttonSell != null)
					{
						buttonSell.Click -= OnButtonClick;
						buttonGrid.Children.Remove(buttonSell);
						buttonSell = null;
					}
					if (buttonFade != null)
					{
						buttonFade.Click -= OnButtonClick;
						buttonGrid.Children.Remove(buttonFade);
						buttonFade = null;
					}
					if (buttonArea != null)
					{
						buttonArea.Click -= OnButtonClick;
						buttonGrid.Children.Remove(buttonArea);
						buttonArea = null;
					}
				}
			}));
			//-
			#endregion
		}

		private void DisplayMsg(string msg)
		{
			Draw.TextFixed(this, "tiyfEasyOrdering_InfoBox", msg, TextPosition.BottomLeft);
			ForceRefresh();
		}

		private void DisplayLevelToExceed()
		{
			/// notify the user about the level that needs to be crossed/hit to consider a trade
			/// depending on which buttons have been pressed and/or if a drawing tool (HLine, RegionY, Rectangle) has been selected
			#region DISPLAY_LEVEL_TO_EXCEED
			//-	
			string msglevelToExceed;
			double previousBarClose;
			
			update_AnchorPrice();
			
			msglevelToExceed = msglevelToExceedCopy;
			if (!isAtmStrategyCreated)
			{
//				msglevelToExceed = " ";
				
				if (!fadeModeEnabled)
				{	// if no user drawn Horizontal/Ray line has been selected
					
					switch (idxButtonContent)
					{
					case 1: // C>TLine or C<TLine /buy if bar close > selected Horizontal/Ray Line/-/Sell if bar close < selected Horizontal/Ray Line/
						if (IsTLineSelected)
						{
							if (buyModeEnabled)
								msglevelToExceed = string.Format("IF bar closes +ve & above {0} THEN a Buy market order will be submitted", Math.Round(anchorPrice_HLineOrSlopeIntercept, 2) );
							else if (sellModeEnabled)
								msglevelToExceed = string.Format("IF bar closes -ve & below {0} THEN a Sell market order will be submitted", Math.Round(anchorPrice_HLineOrSlopeIntercept, 2) );
						}
						else
						{
							msglevelToExceed = "An Horizontal or Ray line object must be selected to trigger the C+>TLine or C-<TLine buttons.";
							resetBothTheBuySellButtons();
						}
						break;

					case 2: // BO H[1] or BO L[1] /buy if price crosses previous bar high/-/Sell if price crosses previous bar low
							
						if (buyModeEnabled)
							msglevelToExceed = string.Format("Buy Stop Limit order will be submitted at the previous bar high");
						else if (sellModeEnabled)
							msglevelToExceed = string.Format("Sell Stop Limit order will be submitted at the previous bar low");
						break;
						
					case 3: // C+ve or C-ve /buy if bar closes up/-/Sell if bar closes down/
						
						if (buyModeEnabled)
							msglevelToExceed = "IF bar closes +ve THEN a Buy market order will be submitted";
						else if (sellModeEnabled)
							msglevelToExceed = "IF bar closes -ve THEN a Sell market order will be submitted";
						break;						

					case 4: // C+|-ve or C-|+ve /buy at bar close/-/Sell at bar close/
						
						if (buyModeEnabled)
							msglevelToExceed = "A Buy market order will be submitted at bar close regardless the closed sign (+ve or -ve)";
						else if (sellModeEnabled)
							msglevelToExceed = "A Sell market order will be submitted at bar close regardless the closed sign (+ve or -ve)";
						break;						

					case 5: // Psar(↓↑)...Psar(↑↓)
						
						if (buyModeEnabled)
							msglevelToExceed = "A Buy market order will be submitted when both the Parabolic Sar reverses UP and bar closes +ve";
						else if (sellModeEnabled)
							msglevelToExceed = "A Sell market order will be submitted when both the Parabolic Sar reverses DOWN and bar closes -ve";
						break;
						
					default: // C>H[1] buy if bar close > previous bar high or C<L[1] Sell if bar close < previous bar low
						
						if (buyModeEnabled)
							msglevelToExceed = "IF bar closes +ve & above previous bar high THEN a Buy market order will be submitted";
						else if (sellModeEnabled)
							msglevelToExceed = "IF bar closes -ve & below previous bar low THEN a Sell market order will be submitted";
						break;						
					} // end switch case
				}
				else
				{
					 // get the currentBar close @ -2 because the developing bar must be skipped (CurrentBar value is guaranteed to be <= Count - 1)
					previousBarClose = Bars.GetClose(Bars.Count-2);
					if (fadeType == 1) // BOF / Test
						if ( previousBarClose < anchorPrice_HLineOrSlopeIntercept )
							msglevelToExceed = string.Format("BOF | Test in progress. Touching or crossing {0} will turn ON the Sell button", Math.Round(anchorPrice_HLineOrSlopeIntercept, 2) );
						else
							msglevelToExceed = string.Format("BOF | Test in progress. Touching or crossing {0} will turn ON the Buy button", Math.Round(anchorPrice_HLineOrSlopeIntercept, 2) );
					else if (fadeType == 2) // Test
						if ( previousBarClose <= anchorPrice_HLineOrSlopeIntercept )
							msglevelToExceed = string.Format("Test in progress. A touch and close below {0} will turn ON the Sell button.", Math.Round(anchorPrice_HLineOrSlopeIntercept, 2) );
						else
							msglevelToExceed = string.Format("Test in progress. A touch and close above {0} will turn ON the Buy button.", Math.Round(anchorPrice_HLineOrSlopeIntercept, 2) );
					else if (fadeType == 3) // BOF
						if ( previousBarClose < anchorPrice_HLineOrSlopeIntercept )
							msglevelToExceed = string.Format("BOF in progress. Price crossing and closing above {0} will turn ON the Sell button", Math.Round(anchorPrice_HLineOrSlopeIntercept, 2) );
						else
							msglevelToExceed = string.Format("BOF in progress. Price crossing and closing below {0} will turn ON the Buy button", Math.Round(anchorPrice_HLineOrSlopeIntercept, 2) );
				}
			} //endif (!isAtmStrategyCreated)
			
			if (IsRegionHLYSelected || IsRectangleSelected) msglevelToExceed = string.Format("You can now limit the range of a BOF signal to the size of the selected drawing (RegionY/Rectangle) and/or\ngive extra margin to your Stop Loss by pressing the 'Y=?t+' button\n* To leave the Stop Loss margin untouched as configured at ({0}t), hold down the left CTRL key when pressing the button.", yButtonInitialContent);
			
			if (msglevelToExceed != msglevelToExceedCopy) DisplayMsg(msglevelToExceed);
			msglevelToExceedCopy = msglevelToExceed;
			//-
			#endregion
		}
		
		private void DisplayProfitToMakeToBE()
		{
			double breakEvenInTick, projectedPriceToBE;
				
			if (breakEvenRatio  > 0)
			{
				projectedPriceToBE = 0;
				// find the nb of points to BE
				breakEvenInTick = Instrument.MasterInstrument.RoundToTickSize(initialStopSize*breakEvenRatio);
				// calculate the price level to reach BE
				if (GetAtmStrategyMarketPosition(atmStrategyId) == MarketPosition.Long)
					projectedPriceToBE = GetAtmStrategyPositionAveragePrice(atmStrategyId) + breakEvenInTick;
				else if (GetAtmStrategyMarketPosition(atmStrategyId) == MarketPosition.Short)
					projectedPriceToBE = GetAtmStrategyPositionAveragePrice(atmStrategyId) - breakEvenInTick;
				// convert the nb of points to BE in tick(s)
				breakEvenInTick = breakEvenInTick / Bars.Instrument.MasterInstrument.TickSize;
				profitToMakeToBreakEven = ( Instrument.MasterInstrument.RoundToTickSize(initialStopSize*breakEvenRatio) * orderQty ) * Bars.Instrument.MasterInstrument.PointValue;
				DisplayMsg( string.Format( "Current trade can be closed by pressing either the Buy or Sell button.\nProfit to make to hit B.E.: ${0} @ price level: {2} ({1}t)", profitToMakeToBreakEven.ToString(), breakEvenInTick.ToString(), projectedPriceToBE.ToString() ) );
			}
			else
			{
				DisplayMsg( "Current trade can be closed by pressing either the Buy or Sell button." );
			}
		}
		
		public override string DisplayName
        {
            get
			{ 
				id = this.Id.ToString();
				if (this.Id != -1)
					return FullSystemName + " - " + id + " (id)" + Environment.NewLine;
				else
					return FullSystemName;
			}
        }		

		/// *** below this line are helper functions ***

		private Brush convertStaticBrushToCustomColor(Brush staticBrush, double brushOpacity)
		{
			/// this function is used to set the opacity level (1..100) of a static color
			/// ex. if brushOpacity = 25 then the opacity level will be set at 25%
			SolidColorBrush mySolidColorBrush;
			Color myColor;
			
			// Convert Brush staticBrush -> Color
			mySolidColorBrush = (SolidColorBrush)staticBrush;
			myColor = mySolidColorBrush.Color;
			return new SolidColorBrush(myColor) {Opacity = brushOpacity / 100};
		}
		
		private string GetATMStrategy()
        {
			/// returns a string holding the name of the selected ATM strategy in the chart trader panel
			/// a null value is returned if no selection has been made
			#region GETATMSTRATEGY
			//-
            string tempATMStrategyName = null;

            try
            {
                AtmStrategy atmStrategy = this.ChartControl.OwnerChart.ChartTrader.AtmStrategy;
                if (atmStrategy != null)
                {
                    tempATMStrategyName = atmStrategy.Template + "";
                }
            }
            catch (Exception ex)
            {
                //stuff exception
//				tempATMStrategyName = null;
            }

            return tempATMStrategyName;
			//-
			#endregion
        }
		
		private int parseAtmXMLfile()
		{
			/// Reads the ATM template XML file and returns the number of targets added by the user
			/// return -1 if no ATM file specified in chart trader otherwise a valid count
			#region PARSE_ATM_XML_FILE
			//-
			atmTemplateName = GetATMStrategy();
			if (atmTemplateName == null) return -1;
			
			int	bracketKey;
			double nodeQuantity = 0;
			double nodeStopLoss = 0;
			double nodeTarget = 0;
			string nodeAutoBreakEvenAt = string.Empty;

			string pathToAtmStratFolder = NinjaTrader.Core.Globals.UserDataDir + "templates\\AtmStrategy\\";
			string xmlFileToLoad = pathToAtmStratFolder + atmTemplateName + ".xml";
			
			XmlDocument xmlDoc = new XmlDocument();
			xmlDoc.Load( xmlFileToLoad );
			
			// https://docs.microsoft.com/en-us/dotnet/api/system.xml.xmlnode.selectnodes?redirectedfrom=MSDN&view=net-6.0#System_Xml_XmlNode_SelectNodes_System_String_
			// solution found here -> https://stackoverflow.com/questions/12607895/cant-get-xmldocument-selectnodes-to-retrieve-any-of-my-nodes
			
			// the XML tag <Brackets>...</Bracket> contains the nodes that define the Stop/Target/StopStrategy
			var mgr = new XmlNamespaceManager(xmlDoc.NameTable);
			mgr.AddNamespace("", "http://schemas.microsoft.com/appx/2010/manifest");
			XmlNode root = xmlDoc.DocumentElement;
			XmlNodeList xnList = root.SelectNodes("//*[local-name()='Brackets']/*[local-name()='Bracket']");
			
//			Loop through all Targets and read its content.
//			Each pair of tag <Bracket>...</Bracket> contains a Target definition (Quantity, Stop, Target, Stop strategy)
			
			// start with a fresh new empty list (Quantity, Stop, Target, StopPrice, LimitPrice, OrderStateStop, OrderStateTarget)
			bracketList.Clear();
			bracketKey = 0;
			orderQty = 0;
			foreach (XmlNode xn in xnList)
			{
				bracketKey++;
				try
				{	// if node <Quantity> does not exists then return an empty value
				nodeQuantity = Double.Parse(xn["Quantity"].InnerText);
				}
				catch(Exception ex) { nodeQuantity = 0; }
				
				try
				{	// if node <StopLoss> does not exists then return an empty value
				nodeStopLoss = Double.Parse(xn["StopLoss"].InnerText);
				}
				catch(Exception ex) { nodeStopLoss = 0; }
				
				try
				{	// if node <Target> does not exists then return an empty value
				nodeTarget = Double.Parse(xn["Target"].InnerText);
				}
				catch(Exception ex) { nodeTarget = 0; }
				
				bracketList.Add( bracketKey, new CBracket(nodeQuantity, nodeStopLoss, nodeTarget) );
				orderQty = orderQty + nodeQuantity;
				// uncomment the following lines to read the Stop Strategy and Add a new property in the CBracket class definition
//				try
//				{	// if node <StopStrategy><AutoBreakEvenProfitTrigger> does not exists then return an empty value
//					nodeAutoBreakEvenAt = xn["StopStrategy"].SelectSingleNode("AutoBreakEvenProfitTrigger").InnerText;
//				}
//				catch(Exception ex) { nodeAutoBreakEvenAt = string.Empty; }
				
//				string str2Print = String.Format( " Quantity = {0}/ StopLoss = {1}/ Target = {2}/ AutoBreakEvenAt = {3}", nodeQuantity , nodeStopLoss , nodeTarget, nodeAutoBreakEvenAt );
//				Print(str2Print);					
			}
			
			return xnList.Count;
			//-
			#endregion
		} // parseAtmXMLfile

		private void update_AnchorPrice()
		{
			anchorPrice_HLineOrSlopeIntercept = 0;
			if (myHLine != null)
				anchorPrice_HLineOrSlopeIntercept = myHLine.StartAnchor.Price;
			else if (myRay != null)
			{
				lineCalc = calculate_YIntercept(myRay.Tag);
				if (lineCalc.Y_Intercept > 0)
					anchorPrice_HLineOrSlopeIntercept = lineCalc.Y_Intercept;
			}
		}
		
		private LineCalculation calculate_YIntercept( string lineTagName )
		{
			#region CALCULATE_YINTERCEPT
			//-
			NinjaTrader.NinjaScript.DrawingTools.Ray myLine;
			int x1, x2, x3, y1, y2, y3;
			Point leftPoint, rightPoint, linePoint1, linePoint2, barPoint;
			float slope, Y_InterceptAtLastBarClose;
			double Y_Intercept;
			LineCalculation lineCalc = new LineCalculation();
			lineCalc.Y_Intercept = 0;
			lineCalc.Slope = 0.0f;
			lineCalc.BarIdxLeftAnchor = 0;
			lineCalc.BarIdxRightAnchor = 0;
			
			myLine = DrawObjects[lineTagName] as NinjaTrader.NinjaScript.DrawingTools.Ray;
			if (myLine != null)
			{	
				//get the pixel coordinates of point 1
				x1 = ChartControl.GetXByTime(myLine.StartAnchor.Time);
				y1 = thisChartScale.GetYByValue(myLine.StartAnchor.Price);
				linePoint1 = new Point(x1, y1);
				
				//get the pixel coordinates of point 2
				x2 = ChartControl.GetXByTime(myLine.EndAnchor.Time);
				y2 = thisChartScale.GetYByValue(myLine.EndAnchor.Price);
				linePoint2 = new Point(x2, y2);
				
				//get the pixel coordinates of last bar closed
				x3 = ChartControl.GetXByBarIndex(ChartBars, Bars.Count - 2);
				y3 = thisChartScale.GetYByValue(Bars.GetClose(Bars.Count - 2));
				// barPoint = last price displayed
				barPoint = new Point(x3, y3);
				
				//normailize for cases where the line was drawn from right to left
				if (linePoint1.X < linePoint2.X) {
					leftPoint = linePoint1;
					lineCalc.BarIdxLeftAnchor = ChartBars.GetBarIdxByTime( ChartControl, myLine.StartAnchor.Time );
				} else {
					leftPoint = linePoint2;
					lineCalc.BarIdxLeftAnchor = ChartBars.GetBarIdxByTime( ChartControl, myLine.EndAnchor.Time );
				}
				if (linePoint2.X > linePoint1.X) {
					rightPoint = linePoint2;
					lineCalc.BarIdxRightAnchor = ChartBars.GetBarIdxByTime( ChartControl, myLine.EndAnchor.Time );
				} else {
					rightPoint = linePoint1;
					lineCalc.BarIdxRightAnchor = ChartBars.GetBarIdxByTime( ChartControl, myLine.StartAnchor.Time );
				}

				// slope = rise over run (rise/run) or (Vertical Y / Time X)
				slope = (float)(leftPoint.Y - rightPoint.Y) / (float)(leftPoint.X - rightPoint.X);
                Y_InterceptAtLastBarClose = (float)leftPoint.Y - slope * (float)(leftPoint.X - barPoint.X);
				
				// convert the Y pixel coordinate into a usable price format
				Y_Intercept = thisChartScale.GetValueByY(Y_InterceptAtLastBarClose);
				lineCalc.Y_Intercept = Y_Intercept;
				lineCalc.Slope = slope;
			}
			return lineCalc;
			//-
			#endregion
		} // end private LineCalculation calculate_YIntercept
		
	} // class tiyfEasyOrdering : Strategy
}
