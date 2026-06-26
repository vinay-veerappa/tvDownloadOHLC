import inspect
from schwabdev import Client

print("Inspect _time_convert source:")
try:
    print(inspect.getsource(Client._time_convert))
except Exception as e:
    print(f"Error getting source: {e}")
