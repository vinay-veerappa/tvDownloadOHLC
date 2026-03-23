import yfinance as yf
import pprint

def test_yf():
    ticker = yf.Ticker("ES=F")
    print("\n--- Testing yfinance for ES=F ---")
    try:
        options = ticker.options
        print(f"Options available: {len(options) if options else 0}")
        if options:
            print(f"First 5 expiries: {options[:5]}")
            chain = ticker.option_chain(options[0])
            print("Successfully fetched first chain!")
            print(f"Calls: {len(chain.calls)}, Puts: {len(chain.puts)}")
        
        # Check fast_info
        print("\n--- Fast Info ---")
        try:
            info = ticker.fast_info
            print(f"Last Price: {info.get('lastPrice')}")
            print(f"Open Price: {info.get('openPrice')}")
        except Exception as e:
            print(f"Fast Info error: {e}")
            
    except Exception as e:
        print(f"Main error: {e}")

if __name__ == "__main__":
    test_yf()
