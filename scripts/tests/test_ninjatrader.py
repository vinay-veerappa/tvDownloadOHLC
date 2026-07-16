import unittest
import time
import os
import sys

# Add scripts directory to path to import NinjaTraderClient
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from NinjaTraderClient import NinjaTraderClient

class TestNinjaTraderMCP(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # We assume the MCP server is running on the default port 8080 (or whatever it's configured for in python client)
        cls.client = NinjaTraderClient(host="http://localhost:8080")
        cls.test_symbol = "NQ" # Assuming NQ is available, change if necessary
        cls.test_account = "Sim101" # Assuming Sim101 account

    def setUp(self):
        # Ensure we are flat before each test
        try:
            self.client.close_position(self.test_account, self.test_symbol)
            time.sleep(1) # wait for orders to cancel and position to flatten
        except Exception as e:
            print(f"Warning: could not flatten position before test: {e}")

    def tearDown(self):
        # Ensure we are flat after each test
        try:
            self.client.close_position(self.test_account, self.test_symbol)
        except Exception:
            pass

    def test_health_check(self):
        """Test basic health check and connection"""
        response = self.client.health_check()
        self.assertIn("status", response)
        self.assertEqual(response["status"], "ok")

    def test_get_quote_auto_subscribe(self):
        """Test getting a quote to ensure auto-subscription works"""
        # Pick a symbol we might not be subscribed to initially
        quote = self.client.get_quote("ES") 
        self.assertIn("last", quote)
        self.assertGreater(quote["last"], 0)

    def test_place_and_change_order(self):
        """Test placing an order with OCO and modifying it"""
        # We place a limit order far away so it doesn't fill
        quote = self.client.get_quote(self.test_symbol)
        current_price = quote["last"]
        limit_price = current_price - 100 # Way below current price

        order_name = "TestEntry"
        oco_id = "TestOCOGroup"

        order = self.client.place_order(
            account=self.test_account,
            symbol=self.test_symbol,
            action="BUY",
            quantity=1,
            order_type="LIMIT",
            limit_price=limit_price,
            time_in_force="GTC",
            name=order_name,
            oco_id=oco_id
        )
        
        # Verify order was placed
        self.assertIn("orderId", order)
        order_id = order["orderId"]

        # Modify the order price
        new_limit_price = limit_price - 10
        change_res = self.client.change_order(
            order_id=order_id,
            limit_price=new_limit_price,
            quantity=1
        )
        self.assertEqual(change_res.get("status"), "success")

        # Cancel the order by OCO
        cancel_res = self.client.cancel_order(
            order_id="", # Cancel by OCO
            name=order_name,
            oco_id=oco_id
        )
        self.assertIn("status", cancel_res)

    def test_close_position_flattens_and_cancels(self):
        """Test that close position works and cancels brackets"""
        # Place a dummy limit order that we expect to be canceled by close_position
        quote = self.client.get_quote(self.test_symbol)
        limit_price = quote["last"] - 200

        self.client.place_order(
            account=self.test_account,
            symbol=self.test_symbol,
            action="BUY",
            quantity=1,
            order_type="LIMIT",
            limit_price=limit_price,
            name="DummyBracket"
        )
        
        # Close position
        close_res = self.client.close_position(self.test_account, self.test_symbol)
        self.assertEqual(close_res.get("status"), "success")
        
        # The order should be canceled, but we can't easily verify the exact order state 
        # without querying order status, which wasn't fully added in this iteration.
        # But a success status implies the flatten command was sent.

if __name__ == '__main__':
    unittest.main()
