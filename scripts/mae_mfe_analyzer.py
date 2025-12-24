"""
MAE/MFE Analyzer - Analyze Maximum Adverse/Favorable Excursion

Analyzes historical trade data to optimize:
- Stop loss placement (based on MAE)
- Take profit levels (based on MFE)
- Entry timing (based on pullback depth)
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Tuple
from pathlib import Path


class MAEMFEAnalyzer:
    """Analyze MAE/MFE to optimize strategy parameters"""
    
    def __init__(self, trades_df: pd.DataFrame):
        """
        Initialize analyzer with trade data
        
        Args:
            trades_df: DataFrame with trade results including mae_pct, mfe_pct columns
        """
        self.trades_df = trades_df.copy()
        self.analysis_results = {}
    
    def analyze_mae_distribution(self) -> Dict:
        """
        Analyze MAE (Maximum Adverse Excursion) distribution
        
        Returns:
            Dictionary with MAE statistics
        """
        df = self.trades_df
        
        # Separate winners and losers
        winners = df[df['result'] == 'WIN']
        losers = df[df['result'] == 'LOSS']
        
        analysis = {
            'all_trades': {
                'mean': df['mae_pct'].mean(),
                'median': df['mae_pct'].median(),
                'std': df['mae_pct'].std(),
                'min': df['mae_pct'].min(),
                'max': df['mae_pct'].max(),
                'percentiles': {
                    '25%': df['mae_pct'].quantile(0.25),
                    '50%': df['mae_pct'].quantile(0.50),
                    '75%': df['mae_pct'].quantile(0.75),
                    '90%': df['mae_pct'].quantile(0.90)
                }
            },
            'winners': {
                'mean': winners['mae_pct'].mean() if len(winners) > 0 else 0,
                'median': winners['mae_pct'].median() if len(winners) > 0 else 0,
                'std': winners['mae_pct'].std() if len(winners) > 0 else 0
            },
            'losers': {
                'mean': losers['mae_pct'].mean() if len(losers) > 0 else 0,
                'median': losers['mae_pct'].median() if len(losers) > 0 else 0,
                'std': losers['mae_pct'].std() if len(losers) > 0 else 0
            }
        }
        
        self.analysis_results['mae'] = analysis
        return analysis
    
    def analyze_mfe_distribution(self) -> Dict:
        """
        Analyze MFE (Maximum Favorable Excursion) distribution
        
        Returns:
            Dictionary with MFE statistics
        """
        df = self.trades_df
        
        # Separate winners and losers
        winners = df[df['result'] == 'WIN']
        losers = df[df['result'] == 'LOSS']
        
        analysis = {
            'all_trades': {
                'mean': df['mfe_pct'].mean(),
                'median': df['mfe_pct'].median(),
                'std': df['mfe_pct'].std(),
                'min': df['mfe_pct'].min(),
                'max': df['mfe_pct'].max(),
                'percentiles': {
                    '25%': df['mfe_pct'].quantile(0.25),
                    '50%': df['mfe_pct'].quantile(0.50),
                    '75%': df['mfe_pct'].quantile(0.75),
                    '90%': df['mfe_pct'].quantile(0.90)
                }
            },
            'winners': {
                'mean': winners['mfe_pct'].mean() if len(winners) > 0 else 0,
                'median': winners['mfe_pct'].median() if len(winners) > 0 else 0,
                'std': winners['mfe_pct'].std() if len(winners) > 0 else 0
            },
            'losers': {
                'mean': losers['mfe_pct'].mean() if len(losers) > 0 else 0,
                'median': losers['mfe_pct'].median() if len(losers) > 0 else 0,
                'std': losers['mfe_pct'].std() if len(losers) > 0 else 0
            }
        }
        
        self.analysis_results['mfe'] = analysis
        return analysis
    
    def calculate_optimal_stop(self, safety_multiplier: float = 1.2) -> float:
        """
        Calculate optimal stop loss based on MAE analysis
        
        Args:
            safety_multiplier: Multiplier for winner MAE (default 1.2 = 20% buffer)
            
        Returns:
            Optimal stop loss distance as % (negative value)
        """
        if 'mae' not in self.analysis_results:
            self.analyze_mae_distribution()
        
        # Use median MAE of winning trades
        winner_mae_median = self.analysis_results['mae']['winners']['median']
        
        # Add safety buffer to avoid stopping out winners
        optimal_stop = winner_mae_median * safety_multiplier
        
        return optimal_stop
    
    def calculate_optimal_targets(self) -> List[Dict]:
        """
        Calculate optimal take profit levels based on MFE probability
        
        Returns:
            List of dictionaries with TP levels and hit probability
        """
        if 'mfe' not in self.analysis_results:
            self.analyze_mfe_distribution()
        
        df = self.trades_df
        
        # Calculate what % of trades reached various R-multiples
        # Assuming entry price and stop loss are available to calculate R
        targets = []
        
        for r_multiple in [0.5, 1.0, 1.5, 2.0, 2.5, 3.0]:
            # Count trades where MFE >= r_multiple (assuming 1R = 1%)
            # This is simplified - in reality, need to calculate based on actual stop distance
            hit_count = (df['mfe_pct'] >= r_multiple).sum()
            hit_probability = (hit_count / len(df)) * 100
            
            targets.append({
                'r_multiple': r_multiple,
                'hit_count': hit_count,
                'hit_probability': hit_probability,
                'recommended': hit_probability >= 40  # Recommend if >40% probability
            })
        
        return targets
    
    def analyze_pullback_depth(self) -> Dict:
        """
        Analyze optimal pullback depth for entries
        
        Note: This requires additional data about pullback depth in trades_df
        
        Returns:
            Dictionary with pullback depth statistics
        """
        # This is a placeholder - would need pullback_depth_pct column in trades
        if 'pullback_depth_pct' not in self.trades_df.columns:
            return {
                'note': 'Pullback depth data not available in trades',
                'recommendation': 'Add pullback_depth_pct tracking to strategy'
            }
        
        df = self.trades_df
        winners = df[df['result'] == 'WIN']
        
        analysis = {
            'all_trades': {
                'mean': df['pullback_depth_pct'].mean(),
                'median': df['pullback_depth_pct'].median(),
                'optimal_range': (
                    df['pullback_depth_pct'].quantile(0.25),
                    df['pullback_depth_pct'].quantile(0.75)
                )
            },
            'winners': {
                'mean': winners['pullback_depth_pct'].mean() if len(winners) > 0 else 0,
                'median': winners['pullback_depth_pct'].median() if len(winners) > 0 else 0
            }
        }
        
        return analysis
    
    def generate_optimization_report(self, output_path: str = None) -> str:
        """
        Generate comprehensive optimization report
        
        Args:
            output_path: Optional path to save report
            
        Returns:
            Report as string
        """
        # Run all analyses
        mae_analysis = self.analyze_mae_distribution()
        mfe_analysis = self.analyze_mfe_distribution()
        optimal_stop = self.calculate_optimal_stop()
        optimal_targets = self.calculate_optimal_targets()
        
        # Build report
        report = []
        report.append("="*80)
        report.append("MAE/MFE OPTIMIZATION REPORT")
        report.append("="*80)
        report.append(f"\nTotal Trades Analyzed: {len(self.trades_df)}")
        report.append(f"Winners: {(self.trades_df['result']=='WIN').sum()}")
        report.append(f"Losers: {(self.trades_df['result']=='LOSS').sum()}")
        
        # MAE Analysis
        report.append("\n" + "="*80)
        report.append("MAXIMUM ADVERSE EXCURSION (MAE) ANALYSIS")
        report.append("="*80)
        report.append(f"\nAll Trades:")
        report.append(f"  Mean MAE: {mae_analysis['all_trades']['mean']:.3f}%")
        report.append(f"  Median MAE: {mae_analysis['all_trades']['median']:.3f}%")
        report.append(f"  90th Percentile: {mae_analysis['all_trades']['percentiles']['90%']:.3f}%")
        
        report.append(f"\nWinning Trades:")
        report.append(f"  Mean MAE: {mae_analysis['winners']['mean']:.3f}%")
        report.append(f"  Median MAE: {mae_analysis['winners']['median']:.3f}%")
        
        report.append(f"\nLosing Trades:")
        report.append(f"  Mean MAE: {mae_analysis['losers']['mean']:.3f}%")
        report.append(f"  Median MAE: {mae_analysis['losers']['median']:.3f}%")
        
        report.append(f"\n✓ RECOMMENDED STOP LOSS: {optimal_stop:.3f}%")
        report.append(f"  (Based on winner median MAE × 1.2 safety factor)")
        
        # MFE Analysis
        report.append("\n" + "="*80)
        report.append("MAXIMUM FAVORABLE EXCURSION (MFE) ANALYSIS")
        report.append("="*80)
        report.append(f"\nAll Trades:")
        report.append(f"  Mean MFE: {mfe_analysis['all_trades']['mean']:.3f}%")
        report.append(f"  Median MFE: {mfe_analysis['all_trades']['median']:.3f}%")
        report.append(f"  75th Percentile: {mfe_analysis['all_trades']['percentiles']['75%']:.3f}%")
        
        report.append(f"\nWinning Trades:")
        report.append(f"  Mean MFE: {mfe_analysis['winners']['mean']:.3f}%")
        report.append(f"  Median MFE: {mfe_analysis['winners']['median']:.3f}%")
        
        # Target Probability
        report.append("\n" + "="*80)
        report.append("TAKE PROFIT PROBABILITY ANALYSIS")
        report.append("="*80)
        report.append(f"\n{'R-Multiple':<12} {'Hit Count':<12} {'Probability':<15} {'Recommended'}")
        report.append("-"*60)
        
        for target in optimal_targets:
            rec_mark = "✓" if target['recommended'] else ""
            report.append(
                f"{target['r_multiple']:<12.1f} "
                f"{target['hit_count']:<12} "
                f"{target['hit_probability']:<14.1f}% "
                f"{rec_mark}"
            )
        
        # Recommendations
        report.append("\n" + "="*80)
        report.append("RECOMMENDATIONS")
        report.append("="*80)
        
        recommended_tps = [t for t in optimal_targets if t['recommended']]
        if len(recommended_tps) >= 3:
            report.append(f"\n✓ Use 3-tier take profit system:")
            report.append(f"  TP1: {recommended_tps[0]['r_multiple']}R (25% position)")
            report.append(f"  TP2: {recommended_tps[1]['r_multiple']}R (50% position)")
            report.append(f"  TP3: {recommended_tps[2]['r_multiple']}R (25% position)")
        elif len(recommended_tps) >= 2:
            report.append(f"\n✓ Use 2-tier take profit system:")
            report.append(f"  TP1: {recommended_tps[0]['r_multiple']}R (50% position)")
            report.append(f"  TP2: {recommended_tps[1]['r_multiple']}R (50% position)")
        
        report.append(f"\n✓ Move stop to breakeven after TP1 hit")
        report.append(f"✓ Trail stop to TP1 level after TP2 hit")
        
        report_text = "\n".join(report)
        
        # Save if path provided
        if output_path:
            Path(output_path).write_text(report_text, encoding='utf-8')
            print(f"\n✓ Optimization report saved to: {output_path}")
        
        return report_text


def analyze_backtest_results(csv_path: str, output_path: str = None):
    """
    Convenience function to analyze backtest results from CSV
    
    Args:
        csv_path: Path to backtest results CSV
        output_path: Optional path to save optimization report
    """
    df = pd.read_csv(csv_path)
    analyzer = MAEMFEAnalyzer(df)
    report = analyzer.generate_optimization_report(output_path)
    print(report)
    return analyzer


if __name__ == '__main__':
    # Example usage
    csv_path = 'docs/strategies/initial_balance_break/backtest_results_45min.csv'
    output_path = 'docs/strategies/initial_balance_break/mae_mfe_optimization.txt'
    
    analyzer = analyze_backtest_results(csv_path, output_path)
