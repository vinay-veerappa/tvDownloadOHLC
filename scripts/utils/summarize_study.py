import optuna
import pandas as pd
from datetime import datetime

study_name = "multi_opt_NQ1_20260330_211240"
storage = "sqlite:///scripts/trading_framework/research_optuna.db"

try:
    study = optuna.load_study(study_name=study_name, storage=storage)
    
    print("\n" + "="*50)
    print(f" STUDY RESULTS: {study_name}")
    print("="*50)
    print(f"Trials completed: {len(study.trials)}")
    
    if study.best_trial:
        print(f"\n🏆 BEST TRIAL: #{study.best_trial.number}")
        print(f"Value (Mean Sharpe): {study.best_trial.value:.4f}")
        print("\nBest Parameters:")
        for key, value in study.best_trial.params.items():
            print(f"  - {key:<20}: {value}")
            
    # Top 5 Trials
    print("\n" + "-"*30)
    print(" TOP 5 PERFORMING TRIALS")
    print("-"*30)
    df = study.trials_dataframe()
    if not df.empty:
        # Sort by value descending
        top_5 = df.sort_values(by="value", ascending=False).head(5)
        for _, row in top_5.iterrows():
            print(f"Trial #{row['number']:<3} | Value: {row['value']:.4f} | State: {row['state']}")
            
except Exception as e:
    print(f"Error loading study: {e}")
