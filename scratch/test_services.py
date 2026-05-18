import asyncio
import os
import sys
import dotenv
import logging

# Ensure project root is in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

# Ensure environment variables are loaded
dotenv.load_dotenv("web/.env")

# Set up logging to stdout
logging.basicConfig(level=logging.INFO)

from prisma import Prisma
from scripts.libs_py.strategy_engine.services.broker_service import BrokerService
from scripts.libs_py.strategy_engine.services.regime_service import RegimeService
from scripts.libs_py.strategy_engine.services.em_service import ExpectedMoveService
from scripts.libs_py.strategy_engine.services.iv_service import IvService

async def main():
    # Instantiate db
    db = Prisma()
    await db.connect()
    
    print("\n--- Testing Platform Services ---")
    
    # 1. Instantiate Services
    broker = BrokerService()
    regime = RegimeService(db)
    em = ExpectedMoveService(db)
    iv = IvService(db)
    
    # 2. Test RegimeService
    print("\nTesting RegimeService on SPY:")
    gex_data = await regime.get_gex_regime("SPY")
    print("GEX Regime:", gex_data)
    
    macro_data = await regime.get_macro_regime("SPY")
    print("Macro Regime:", macro_data)
    
    # 3. Test ExpectedMoveService
    print("\nTesting ExpectedMoveService on SPY:")
    # Use dummy spot price of 500
    em_bands = await em.get_expected_move_bands("SPY", 500.0)
    print("EM Bands:", em_bands)
    
    # 4. Test IvService
    print("\nTesting IvService on SPY (Direct Dolt):")
    hv = await iv.get_historical_volatility("SPY")
    print("SPY HV:", hv)
    
    # Test SPX Proxy Mapping
    print("\nTesting IvService on SPX (Should fallback to SPY proxy for Dolt):")
    spx_hv = await iv.get_historical_volatility("SPX")
    print("SPX (Proxy SPY) HV:", spx_hv)
    
    # Test current IV from snapshot
    spx_iv = await iv.get_current_iv("SPX")
    print("SPX ATM IV:", spx_iv)
    
    # Clean up
    await db.disconnect()
    print("\nAll service tests completed successfully!")

if __name__ == "__main__":
    asyncio.run(main())
