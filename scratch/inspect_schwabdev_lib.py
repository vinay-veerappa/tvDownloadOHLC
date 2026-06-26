import inspect
from schwabdev import Client

print("Inspect Client.price_history signature:")
print(inspect.signature(Client.price_history))

print("\nInspect Client.price_history source:")
try:
    print(inspect.getsource(Client.price_history))
except Exception as e:
    print(f"Error getting source: {e}")
