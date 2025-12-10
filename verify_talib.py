import talib
import numpy as np
import pandas as pd

try:
    print("Attempting to import talib...")
    data = np.random.random(100)
    sma = talib.SMA(data, timeperiod=14)
    print("SUCCESS: TA-Lib imported and calculated SMA.")
except Exception as e:
    print(f"FAILURE: {e}")
