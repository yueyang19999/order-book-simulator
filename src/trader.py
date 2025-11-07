from __future__ import annotations

from abc import ABC, abstractmethod
from typing import List, Optional

from order_book import Order  # Order(side, price, quantity), id auto-assigned
# MatchingEngine will consume these Orders and produce Trade callbacks.

class Trader(ABC):
    """
    Base class for all trader types.

    Attributes
    ----------
    trader_id : str
        Unique identifier for this trader.
    cash : float
        Current cash balance.
    inventory : float
        Units/shares currently held.
    order_history : list[Order]
        Log of orders this trader has generated.
    """

    def __init__(self, trader_id: str, cash: float = 0.0, inventory: float = 0.0) -> None:
        self.trader_id: str = trader_id
        self.cash: float = float(cash)
        self.inventory: float = float(inventory)
        self.order_history: List[Order] = []

        # If you want to wire fills later, keep track of open order ids you own:
        self._open_order_ids: set[int] = set()

    # ----- Strategies must implement these -----------------------------------
    @abstractmethod
    def generate_order(self, current_midprice: float) -> Optional[Order]:
        """
        Create and return a limit order compatible with the engine.

        Return None if you choose not to trade on this tick (only if your sim
        allows it). Otherwise return an Order with side in {'buy','sell'},
        price > 0 and quantity > 0.
        """
        ...

    def update_state(self, order_book_view) -> None:
        """Optional hook to react to market state between ticks."""
        return

    # ----- Helper to build and record orders ---------------------------------
    def new_order(self, side: str, price: float, quantity: float) -> Order:
        side_l = side.lower()
        if side_l not in ("buy", "sell"):
            raise ValueError("side must be 'buy' or 'sell'")
        if price <= 0 or quantity <= 0:
            raise ValueError("price and quantity must be positive")

        order = Order(side=side_l, price=float(price), quantity=float(quantity))
        self.order_history.append(order)
        self._open_order_ids.add(order.id)
        return order

    # ----- Optional PnL/inventory hooks (you can call these from engine callbacks) ---
    def on_fill(self, side: str, price: float, quantity: float) -> None:
        if side == "buy":
            self.inventory += quantity
            self.cash -= price * quantity
        elif side == "sell":
            self.inventory -= quantity
            self.cash += price * quantity

    def on_accept(self, order: Order) -> None:
        self._open_order_ids.add(order.id)

    def on_cancel(self, order_id: int) -> None:
        self._open_order_ids.discard(order_id)

    def on_reject(self, order: Order, reason: str) -> None:
        self._open_order_ids.discard(order.id)
