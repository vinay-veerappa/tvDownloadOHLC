# seed_data.py
import asyncio
import os
import sys
import yaml
from datetime import datetime
from dotenv import load_dotenv

# Load env variables from web/.env BEFORE importing and starting Prisma
dotenv_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../web/.env"))
load_dotenv(dotenv_path)

from prisma import Prisma

CONFIG_PATH = os.path.join(os.path.dirname(__file__), "config.yaml")


# Standard playbook rules in markdown format
PLAYBOOK_RULES = """# Strategy Engine Standard Playbook

## Execution Rules
- Entries must be simulated at the mid-price of the option chain at signal time.
- Exits must be simulated at the mid-price of the option chain at exit signal or expiration.
- Positions are held in designated silo accounts to avoid co-mingling of capital.

## Slippage & Calibration
- Standard slippage of $0.02 per contract is applied for highly liquid tickers (SPY, QQQ).
- Standard slippage of $0.05 per contract is applied for individual equities (NVDA, TSLA, AAPL, GOOGL, MSFT, AMZN).
- Slippage calibration must be performed weekly against live paper fills.

## Risk Management
- Maximum allocation per trade: 10% of silo account value.
- No new entries allowed if portfolio drawdown exceeds 15% from peak.
- All intraday times strictly utilize Eastern Time (EST/New York).
"""

STRATEGY_DETAILS = {
    "WHEEL": {
        "description": "Standard option wheel strategy selling cash-secured puts and covered calls.",
        "color": "#4CAF50"
    },
    "ZERO_DTE_PCS": {
        "description": "Intraday 0DTE Put Credit Spreads entered based on spot price, GEX, and ICT context.",
        "color": "#E91E63"
    },
    "LONG_DTE_CREDIT": {
        "description": "45DTE credit spreads entered during periods of elevated implied volatility rank.",
        "color": "#9C27B0"
    },
    "MEAN_REVERSION_EM": {
        "description": "Selling options or spreads at the 1SD expected move boundary looking for mean reversion.",
        "color": "#3F51B5"
    },
    "WALL_BREAK": {
        "description": "Buying breakout debit spreads when underlying breaches dominant GEX walls.",
        "color": "#FF9800"
    },
    "INCOME_CC": {
        "description": "Systematic covered calls written on long stock holdings based on statistical tier boundaries.",
        "color": "#00BCD4"
    },
    "EARNINGS_STRANGLE": {
        "description": "Selling strangles 5 days before earnings to capture rapid implied volatility crush.",
        "color": "#795548"
    }
}

async def main():
    print("Starting Options Strategy Engine Database Seeding...")

    # Load configuration
    if not os.path.exists(CONFIG_PATH):
        print(f"Error: Configuration file not found at {CONFIG_PATH}")
        sys.exit(1)

    with open(CONFIG_PATH, "r") as f:
        config = yaml.safe_load(f)

    # Instantiate Prisma client
    db = Prisma()
    await db.connect()

    try:
        # 1. Establish AccountGroup for silos
        group_name = config.get("account_group_name", "Strategy Engine Silos")
        print(f"Creating/Retrieving AccountGroup: '{group_name}'")
        account_group = await db.accountgroup.find_unique(where={"name": group_name})
        if not account_group:
            account_group = await db.accountgroup.create(
                data={
                    "name": group_name,
                    "description": "Silo accounts designated for options strategy execution tracking"
                }
            )
        print(f"AccountGroup ID: {account_group.id}")

        # 2. Seed core Strategy definitions (idempotent)
        print("Seeding Strategy definitions...")
        for name, info in STRATEGY_DETAILS.items():
            # Strategy model has no unique constraint on name in schema.prisma, so we query first
            existing = await db.strategy.find_first(where={"name": name})
            if not existing:
                await db.strategy.create(
                    data={
                        "name": name,
                        "description": info["description"],
                        "color": info["color"]
                    }
                )
                print(f"  Created Strategy: {name}")
            else:
                print(f"  Strategy already exists: {name}")

        # 3. Seed Playbook rules (idempotent)
        print("Seeding Playbook rules...")
        playbook_name = "Strategy Engine Playbook"
        playbook = await db.playbook.find_unique(where={"name": playbook_name})
        if not playbook:
            playbook = await db.playbook.create(
                data={
                    "name": playbook_name,
                    "description": "Standard execution and risk management playbook for the options strategy engine",
                    "rules": PLAYBOOK_RULES
                }
            )
            print(f"  Created Playbook: {playbook_name}")
        else:
            await db.playbook.update(
                where={"id": playbook.id},
                data={"rules": PLAYBOOK_RULES}
            )
            print(f"  Updated Playbook: {playbook_name}")

        # 4. Generate the 41 combinations (idempotent)
        print("Seeding silo Accounts and ResearchStrategy configurations for variants...")
        initial_balance = config.get("default_initial_balance", 25000.0)
        combination_count = 0

        for strategy_code, strat_cfg in config.get("strategies", {}).items():
            tickers = strat_cfg.get("tickers", [])
            variants = strat_cfg.get("variants", {})

            for variant_name in variants.keys():
                for ticker in tickers:
                    combination_count += 1
                    comb_name = f"{strategy_code}_{variant_name}_{ticker}"

                    # Create ResearchStrategy configuration
                    research_strat = await db.researchstrategy.find_unique(where={"name": comb_name})
                    if not research_strat:
                        color = STRATEGY_DETAILS.get(strategy_code, {}).get("color", "#2962FF")
                        research_strat = await db.researchstrategy.create(
                            data={
                                "name": comb_name,
                                "description": f"Engine tracking configuration for {strategy_code} variant {variant_name} on ticker {ticker}",
                                "color": color
                            }
                        )
                        print(f"  Created ResearchStrategy: {comb_name}")
                    else:
                        print(f"  ResearchStrategy already exists: {comb_name}")

                    # Create Silo Account linked to AccountGroup
                    # Account has no unique constraint on name in schema.prisma, so we query under the group
                    existing_account = await db.account.find_first(
                        where={
                            "name": comb_name,
                            "groupId": account_group.id
                        }
                    )
                    if not existing_account:
                        await db.account.create(
                            data={
                                "name": comb_name,
                                "groupId": account_group.id,
                                "initialBalance": initial_balance,
                                "currentBalance": initial_balance,
                                "currency": "USD",
                                "isDefault": False
                            }
                        )
                        print(f"  Created Account: {comb_name} with balance ${initial_balance:,.2f}")
                    else:
                        print(f"  Account already exists: {comb_name}")

        print(f"Processed {combination_count} variant combinations.")

        # 5. Seed stock holdings (idempotent)
        print("Seeding stock Holdings...")
        for ticker, h_cfg in config.get("holdings", {}).items():
            existing_holding = await db.holding.find_unique(where={"ticker": ticker})
            acquired_date = datetime.fromisoformat(h_cfg["acquired_at"].replace("Z", "+00:00"))
            if not existing_holding:
                await db.holding.create(
                    data={
                        "ticker": ticker,
                        "shares": h_cfg["shares"],
                        "costBasis": h_cfg["cost_basis"],
                        "acquiredAt": acquired_date,
                        "notes": "Seeded stock holdings representing the long equity leg for Income CC writing"
                    }
                )
                print(f"  Created Holding: {ticker} ({h_cfg['shares']} shares @ ${h_cfg['cost_basis']})")
            else:
                await db.holding.update(
                    where={"id": existing_holding.id},
                    data={
                        "shares": h_cfg["shares"],
                        "costBasis": h_cfg["cost_basis"],
                        "acquiredAt": acquired_date
                    }
                )
                print(f"  Updated Holding: {ticker} ({h_cfg['shares']} shares @ ${h_cfg['cost_basis']})")

        print("Seeding completed successfully!")

    except Exception as e:
        print(f"Error during seeding: {e}")
        raise e
    finally:
        await db.disconnect()

if __name__ == "__main__":
    asyncio.run(main())
