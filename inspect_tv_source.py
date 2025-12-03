from tvDatafeed import TvDatafeed
import inspect

tv = TvDatafeed()
try:
    # Print __init__ to see how connection is made
    print("--- __init__ ---")
    print(inspect.getsource(TvDatafeed.__init__))
    
    # Print __send_message to see how messages are formatted
    print("\n--- _TvDatafeed__send_message ---")
    # Name mangling: _TvDatafeed__send_message
    print(inspect.getsource(tv._TvDatafeed__send_message))
    
    # Print get_hist to see how it requests data
    print("\n--- get_hist ---")
    print(inspect.getsource(tv.get_hist))
    
except Exception as e:
    print(e)
