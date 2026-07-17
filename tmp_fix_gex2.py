"""Add target_date parameter to all _format_gex_block calls"""

with open('scripts/trader/signals/intraday_blocks.py', 'r', encoding='utf-8') as f:
    content = f.read()

# Add target_date to each _format_gex_block call
content = content.replace(
    '_format_gex_block(ticker_current, es_current, ticker, session="ASIA")',
    '_format_gex_block(ticker_current, es_current, ticker, session="ASIA", target_date=target_date)'
)
content = content.replace(
    '_format_gex_block(ticker_current, es_current, ticker, session="LONDON")',
    '_format_gex_block(ticker_current, es_current, ticker, session="LONDON", target_date=target_date)'
)
content = content.replace(
    '_format_gex_block(ticker_current, es_current, ticker, session="NY_AM")',
    '_format_gex_block(ticker_current, es_current, ticker, session="NY_AM", target_date=target_date)'
)
content = content.replace(
    '_format_gex_block(ticker_current, es_current, ticker, session="NY_LUNCH")',
    '_format_gex_block(ticker_current, es_current, ticker, session="NY_LUNCH", target_date=target_date)'
)
content = content.replace(
    '_format_gex_block(ticker_current, es_current, ticker, session="NY_PM")',
    '_format_gex_block(ticker_current, es_current, ticker, session="NY_PM", target_date=target_date)'
)

with open('scripts/trader/signals/intraday_blocks.py', 'w', encoding='utf-8') as f:
    f.write(content)
print('Done')