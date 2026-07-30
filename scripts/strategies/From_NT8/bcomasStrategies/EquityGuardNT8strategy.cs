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
using NinjaTrader.Cbi;
using NinjaTrader.Gui;
using NinjaTrader.Gui.Chart;
using NinjaTrader.Gui.SuperDom;
using NinjaTrader.Gui.Tools;
using NinjaTrader.Data;
using NinjaTrader.NinjaScript;
using NinjaTrader.Core.FloatingPoint;
using NinjaTrader.NinjaScript.Indicators;
using NinjaTrader.NinjaScript.DrawingTools;
#endregion

//Copyright © <2020>  bcomasSoftware 

/*	
//            \\|//             +-+-+-+-+-+-+-+-+-+-+-+-+             \\|//            //
//           ( o o )            |E|q|u|i|t|y|-|G|u|a|r|d|            ( o o )           //
//    ~~~~oOOo~(_)~oOOo~~~~     +-+-+-+-+-+-+-+-+-+-+-+-+     ~~~~oOOo~(_)~oOOo~~~~    //
*/

    /// <summary>
	/// Coded by bcomas October 2020. Email:  bcomasSoftware@gmail.com for improvements
    /// http://ninjatrader-programming-strategies.mozello.com/
    /// </summary>

//This namespace holds Strategies in this folder and is required. Do not change it. 
namespace NinjaTrader.NinjaScript.Strategies.bcomasStrategies
{
	public class EquityGuardNT8strategy : Strategy
	{
		// Email
		private string toEmailAddress     = @"";  
		
		protected override void OnConnectionStatusUpdate(ConnectionStatusEventArgs connectionStatusUpdate)
        {
        if(connectionStatusUpdate.Status == ConnectionStatus.Connected)
        {
            Print("Connected at " + DateTime.Now);
			{	
			if (UseEmail == true)
			SendMail(toEmailAddress, "* NinjaTrader - Connection", "Connected at " + DateTime.Now);
			}		
        }
        else if(connectionStatusUpdate.Status == ConnectionStatus.ConnectionLost)
        {
            Print("Connection lost at: " + DateTime.Now);
			{
			if (UseEmail == true)
			SendMail(toEmailAddress, "* NinjaTrader - Connect/Lost!!:-(", "Lost !!!! at " + DateTime.Now);
			}		
          }
        }
		
		protected override void OnStateChange()
		{
			if (State == State.SetDefaults)
			{
				
				Description									= @"Monitoring account equity";
				Name										= "EquityGuardNT8strategy";
				Calculate									= Calculate.OnEachTick;
				EntriesPerDirection							= 1;
				EntryHandling								= EntryHandling.AllEntries;
				IsExitOnSessionCloseStrategy				= false;
				ExitOnSessionCloseSeconds					= 30;
				IsFillLimitOnTouch							= false;
				MaximumBarsLookBack							= MaximumBarsLookBack.TwoHundredFiftySix;
				OrderFillResolution							= OrderFillResolution.Standard;
				Slippage									= 0;
				StartBehavior								= StartBehavior.ImmediatelySubmit;
				TimeInForce									= TimeInForce.Day;
				TraceOrders									= false;
				//RealtimeErrorHandling						= RealtimeErrorHandling.StopCancelClose;
				StopTargetHandling							= StopTargetHandling.PerEntryExecution;
				BarsRequiredToTrade							= 5;
				IsInstantiatedOnEachOptimizationIteration	= false;
				
			    // Keeps the strategy running as if no disconnect occurred	
                ConnectionLossHandling                      = ConnectionLossHandling.KeepRunning;
				
				// Email alerts Settings
				UseEmail	                                = false;
				toEmailAddress                              = @"";
				
				UseCloseAtFloatingProfit                    = false;
				FloatingProfit                              = 300;
				
				UseCloseAtFloatingLoss                      = true;
				FloatingLoss                                = -900;
				
				//Stop trading if the Account Cash Value Target is reached ($)
                AccountCashValueTarget                      = 550000;
				AccountCashValueDrawDown                    = 1500;
				
			}
			else if (State == State.Configure)
			{
				
				{   // Ignore Errors Handling -> only messages
                    RealtimeErrorHandling = RealtimeErrorHandling.IgnoreAllErrors;
                }	
				  
			}
			else if (State == State.DataLoaded)
			{
             //---
			}
		}

/// /////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////
	
		protected override void OnBarUpdate()
		{	
			/// PnL
		    if (UseCloseAtFloatingLoss||UseCloseAtFloatingProfit)
		    PnL();
			
			/// Evaluates to see if the account has more than the Account Cash Value Target ($)
            if (Account.Get(AccountItem.CashValue, Currency.UsDollar) > AccountCashValueTarget)
            {
            Draw.TextFixed(this, "limitText", "                                                              Account Cash Value Target reached - Withdraw funds", TextPosition.BottomLeft);
			Print("----------Time is: " +Time[0].ToString("dd/MM/yyyy") + "," + Time[0].ToString("HH:mm:ss"));
			Account.FlattenEverything();
            /// Halt further processing of our strategy - disabling

            }
			
			/// Max Monthly DrawDown permited
            if (Account.Get(AccountItem.CashValue, Currency.UsDollar) < AccountCashValueDrawDown)
            {
            Draw.TextFixed(this, "limitText", "                                                              Max Account Loss reached - STOP TRADING", TextPosition.BottomLeft);
			Print("----------Time is: " +Time[0].ToString("dd/MM/yyyy") + "," + Time[0].ToString("HH:mm:ss"));
			Account.FlattenEverything();
            /// Halt further processing of our strategy - disabling
            }
				
		}
		
		///-------------------------------------------------------------------------------------------------------------------------
			//Flatten if Loss
			///-----------------------------------------------------------------------------------------
			private void PnL()
		    {	
			if ((Account.Get(AccountItem.UnrealizedProfitLoss, Currency.UsDollar) // UnRealized Loss
			<= FloatingLoss) && (UseCloseAtFloatingLoss))

            Account.FlattenEverything();
			//Account.Flatten(new [] { Instrument.GetInstrument(Instrument.FullName) });
			/// Halt further processing of our strategy
			/// 
			if ((Account.Get(AccountItem.UnrealizedProfitLoss, Currency.UsDollar) // UnRealized Profit
			>= FloatingProfit) && (UseCloseAtFloatingProfit))

            Account.FlattenEverything();
			//Account.Flatten(new [] { Instrument.GetInstrument(Instrument.FullName) });
			/// Halt further processing of our strategy
			
			if ((Account.Get(AccountItem.RealizedProfitLoss, Currency.UsDollar) // Realized Loss
			<= FloatingLoss) && (UseCloseAtFloatingLoss))

            Account.FlattenEverything();
			//Account.Flatten(new [] { Instrument.GetInstrument(Instrument.FullName) });
			/// Halt further processing of our strategy
			/// 
			if ((Account.Get(AccountItem.RealizedProfitLoss, Currency.UsDollar) // Realized Profit
			>= FloatingProfit) && (UseCloseAtFloatingProfit))

            Account.FlattenEverything();
			//Account.Flatten(new [] { Instrument.GetInstrument(Instrument.FullName) });
			/// Halt further processing of our strategy
			
			if ((Account.Get(AccountItem.RealizedProfitLoss, Currency.UsDollar) + Account.Get(AccountItem.UnrealizedProfitLoss, Currency.UsDollar)
			<= FloatingLoss) && (UseCloseAtFloatingLoss))// UnRealized + Realized Loss

            Account.FlattenEverything();
			//Account.Flatten(new [] { Instrument.GetInstrument(Instrument.FullName) });
			/// Halt further processing of our strategy
			/// 
			if ((Account.Get(AccountItem.RealizedProfitLoss, Currency.UsDollar) + Account.Get(AccountItem.UnrealizedProfitLoss, Currency.UsDollar)
			>= FloatingProfit) && (UseCloseAtFloatingProfit))// UnRealized + Realized Profit

            Account.FlattenEverything();
			//Account.Flatten(new [] { Instrument.GetInstrument(Instrument.FullName) });
			/// Halt further processing of our strategy
            } 
			///-------------------------------------------------------------------------------------------------------------------------
			
		#region Properties
		
		//>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>> Mail Share Service input properties
		[NinjaScriptProperty]
		[Display(ResourceType = typeof(Custom.Resource), Name="UseEmail", Description="Use Email", Order=1, GroupName="Connection Lost")]
		public bool UseEmail
		{ get; set; }
		
		[NinjaScriptProperty]
        [Display(Description = "To Email id", GroupName = "Connection Lost", Order = 2)]
        public string ToEmailAddress
        {
            get { return toEmailAddress; }
            set 
			{ 
				System.Text.RegularExpressions.Regex reg = new System.Text.RegularExpressions.Regex(@"\b[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,4}\b");
				
				if (reg.IsMatch((string)value))
					toEmailAddress = value; 
			}
        }
		
		//>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>> Account Cash Value Target ($) input properties
		[NinjaScriptProperty]
		[Display(ResourceType = typeof(Custom.Resource), Name="UseCloseAtFloatingLoss", Description="Use Close At Floating Loss", Order=0, GroupName="Money Management")]
		public bool UseCloseAtFloatingLoss
		{ get; set; }

		[NinjaScriptProperty]
		[Display(Name = "FloatingLoss", Description = "Floating Loss", Order = 1, GroupName = "Money Management")]
		public double FloatingLoss
		{ get; set; }
		
		[NinjaScriptProperty]
		[Display(ResourceType = typeof(Custom.Resource), Name="UseCloseAtFloatingProfit", Description="Use Close At Floating Profit", Order=2, GroupName="Money Management")]
		public bool UseCloseAtFloatingProfit
		{ get; set; }

		[NinjaScriptProperty]
		[Display(Name = "FloatingProfit", Description = "Floating Profit", Order = 3, GroupName = "Money Management")]
		public double FloatingProfit
		{ get; set; }
		
        [NinjaScriptProperty]
        [Display(Name="AccountCashValueTarget", Description="Stop if the Account Cash Value Target reached", Order=4, GroupName="Money Management")]
        public double AccountCashValueTarget
        { get; set; }
		
		[NinjaScriptProperty]
        [Display(Name="AccountCashValueDrawDown", Description="Stop if Max DrawDown reached", Order=5, GroupName="Money Management")]
        public double AccountCashValueDrawDown
        { get; set; }

		#endregion

	}
}

// ------------------------------------------------------------------------------------------  //
///                        E N D   O F   S T R A T E G Y                                       //
// ------------------------------------------------------------------------------------------  //
