import requests
from typing import Dict, List, Optional, Any

class NinjaTraderClient:
    """
    Python wrapper client for the NinjaTrader 8 REST API bridge.
    Talks directly to the HttpListener running inside the NT8 AddOn.
    """
    def __init__(self, host: str = "localhost", port: int = 7890):
        self.base_url = f"http://{host}:{port}"
        
    def _get(self, path: str, params: Optional[Dict] = None) -> Any:
        response = requests.get(f"{self.base_url}{path}", params=params)
        response.raise_for_status()
        return response.json()
        
    def _post(self, path: str, json_data: Optional[Dict] = None) -> Any:
        response = requests.post(f"{self.base_url}{path}", json=json_data)
        response.raise_for_status()
        return response.json()

    def get_health(self) -> Dict:
        """Check bridge health and version info."""
        return self._get("/api/health")

    def get_accounts(self) -> List[Dict]:
        """List all accounts and balances (cash, net liq, buying power, PnL)."""
        return self._get("/api/account")

    def get_positions(self) -> List[Dict]:
        """List open active positions."""
        return self._get("/api/positions")

    def get_orders(self) -> List[Dict]:
        """List all pending/working orders."""
        return self._get("/api/orders")

    def get_quote(self, symbol: str) -> Dict:
        """
        Get the current quote snapshot.
        If NinjaTrader is not subscribed to this symbol, the bridge will auto-subscribe.
        """
        return self._get("/api/quote", params={"symbol": symbol})

    def get_bars(self, symbol: str, period: str = "Minute", period_value: int = 1, count: int = 100) -> Dict:
        """Get historical bars."""
        return self._get("/api/bars", params={
            "symbol": symbol,
            "period": period,
            "periodValue": period_value,
            "count": count
        })

    def place_order(
        self,
        symbol: str,
        action: str,
        quantity: int,
        order_type: str = "Market",
        limit_price: Optional[float] = None,
        stop_price: Optional[float] = None,
        time_in_force: str = "Day",
        oco_id: Optional[str] = None,
        name: Optional[str] = None,
        account: Optional[str] = None
    ) -> Dict:
        """
        Place an order.
        :param limit_price: Price for Limit/StopLimit/MIT orders (maps to limitPrice or price)
        :param stop_price: Stop price for StopMarket/StopLimit orders
        :param oco_id: Group string to link multiple orders (e.g. bracket TP/SL)
        :param name: Custom signal name/tag for the order
        """
        payload = {
            "symbol": symbol,
            "action": action.lower(),
            "quantity": quantity,
            "orderType": order_type,
            "timeInForce": time_in_force
        }
        if limit_price is not None:
            payload["limitPrice"] = limit_price
        if stop_price is not None:
            payload["stopPrice"] = stop_price
        if oco_id is not None:
            payload["ocoId"] = oco_id
        if name is not None:
            payload["name"] = name
        if account is not None:
            payload["account"] = account
            
        return self._post("/api/order", payload)

    def change_order(
        self,
        order_id: str,
        quantity: Optional[int] = None,
        limit_price: Optional[float] = None,
        stop_price: Optional[float] = None
    ) -> Dict:
        """Modify a working order."""
        payload = {"orderId": order_id}
        if quantity is not None:
            payload["quantity"] = quantity
        if limit_price is not None:
            payload["limitPrice"] = limit_price
        if stop_price is not None:
            payload["stopPrice"] = stop_price
            
        return self._post("/api/order/change", payload)

    def cancel_order(self, order_id: Optional[str] = None, oco_id: Optional[str] = None) -> Dict:
        """Cancel an order by orderId or cancel an entire bracket group by ocoId."""
        payload = {}
        if order_id is not None:
            payload["orderId"] = order_id
        if oco_id is not None:
            payload["ocoId"] = oco_id
        return self._post("/api/order/cancel", payload)

    def cancel_all_orders(self) -> Dict:
        """Cancel all working orders across all accounts."""
        return self._post("/api/orders/cancel-all")

    def close_position(self, symbol: str, account: Optional[str] = None) -> Dict:
        """Flatten active position for a symbol and cancel its open working orders."""
        payload = {"symbol": symbol}
        if account is not None:
            payload["account"] = account
        return self._post("/api/position/close", payload)
