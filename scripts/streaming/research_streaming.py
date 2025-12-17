import schwab
import inspect
import json

def inspect_module():
    print("--- Checking schwab module ---")
    if hasattr(schwab, 'streaming'):
        print("Found 'schwab.streaming' module.")
        stream_mod = schwab.streaming
        
        # List classes in streaming module
        for name, obj in inspect.getmembers(stream_mod):
            if inspect.isclass(obj):
                print(f"\nClass: {name}")
                # Check for handler methods or subscription methods
                methods = [n for n, m in inspect.getmembers(obj) if not n.startswith('_')]
                print(f"  Methods: {methods[:10]}...") 
                
                if 'Client' in name:
                    print(f"  --- Details for {name} ---")
                    methods = [m for m in dir(obj) if not m.startswith('_')]
                    print(f"  Public Methods: {methods}")
                    
                    # Filter for 'Fields' classes to identify services
                    fields_classes = [n for n, o in inspect.getmembers(stream_mod) if 'Fields' in n and inspect.isclass(o)]
                    print(f"\n--- Available Streaming Services (Inferred from Field Classes) ---")
                    for fc in sorted(fields_classes):
                        print(f"- {fc}")

                    print(f"\n--- Subscription Methods (likely) ---")
                    subs = [m for m in methods if 'subs' in m or 'add' in m]
                    for s in sorted(subs):
                        print(f"- {s}")
                    
    else:
        print("No 'schwab.streaming' module found directly under 'schwab'.")
        print("Dir(schwab):", dir(schwab))

if __name__ == "__main__":
    try:
        inspect_module()
    except Exception as e:
        print(f"Error: {e}")
