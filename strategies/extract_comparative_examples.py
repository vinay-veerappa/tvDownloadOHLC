import pandas as pd
from pathlib import Path

def extract_examples(config_path, config_name, ticker):
    if not config_path.exists():
        print(f"File not found: {config_path}")
        return None
    
    df = pd.read_csv(config_path)
    if len(df) == 0:
        return None

    # Winning examples (top 1 by P&L)
    winners = df[df['result'] == 'WIN'].sort_values('pnl_pct', ascending=False).head(1)
    # Losing examples (bottom 1 by P&L)
    losers = df[df['result'] == 'LOSS'].sort_values('pnl_pct', ascending=True).head(1)
    
    combined = pd.concat([winners, losers])
    combined['config'] = config_name
    combined['ticker'] = ticker
    return combined

configs = [
    # (Folder, Name, Ticker)
    ('mechanism_evaluation/Fib_38.2_Only', 'InternalIB_Fib38.2', 'NQ1'),
    ('mechanism_evaluation/Fib_50_Only', 'InternalIB_Fib50', 'NQ1'),
    ('mechanism_evaluation/Fib_61.8_Only', 'InternalIB_Fib61.8', 'NQ1'),
]

all_examples = []
base_path = Path('docs/strategies/initial_balance_break')
for folder_name, config_name, ticker in configs:
    csv_path = base_path / f"{folder_name}.csv"
    examples = extract_examples(csv_path, config_name, ticker)
    if examples is not None:
        all_examples.append(examples)

if all_examples:
    df_all = pd.concat(all_examples)
    output_path = base_path / 'comparative_trade_examples.csv'
    df_all.to_csv(output_path, index=False)
    print(f"Comparative examples saved to {output_path}")
