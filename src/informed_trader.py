# trader.py
import math
import random
from order_book import Order
from trader import Trader  # if base class is in a separate file

class InformedTrader(Trader):
    def __init__(
        self,
        trader_id: str,
        info_strength: float = 0.05,
        true_value: float = 0.01,
        threshold: float = 0.01,
        lambda_rate: float = 0.3,
        quantity_range=(10.0, 100.0),
    ):
        super().__init__(trader_id)
        self.info_strength = info_strength
        self.threshold = threshold
        self.lambda_rate = lambda_rate
        self.quantity_range = quantity_range
        self.true_value = true_value

    def should_trade(self, delta_t: float) -> bool:
        p_info = 1 - math.exp(-self.lambda_rate * delta_t)
        return random.random() < p_info

    def generate_order(
        self,
        mid_price: float,
        book: tuple[float | None, float | None] | None = None
    ):
        """
        Submit a LIMIT order priced to CROSS the spread (market-like):
          - If buying: price = best_ask (if available)
          - If selling: price = best_bid (if available)
        Falls back to mid_price ± 2% if the book side is empty.
        """
        mispricing = (self.true_value - mid_price) / mid_price
        if abs(mispricing) < self.threshold:
            return None

        best_bid, best_ask = book or (None, None)
        side = "buy" if mispricing > 0 else "sell"

        # Size scales with signal
        size_factor = min(1.0, abs(mispricing) * self.info_strength)
        qty = round(random.uniform(*self.quantity_range) * size_factor, 2)

        if side == "buy":
            price = best_ask if best_ask is not None else round(mid_price * 1.02, 2)
        else:
            price = best_bid if best_bid is not None else round(mid_price * 0.98, 2)

        print(f"[{self.trader_id}] MARKET {side.upper()} {qty:.2f} @ ${price:.2f} "
              f"(mispricing={mispricing:+.3f})"
              f"(true_value={self.true_value})"
              f"(mid price={mid_price} ")
        return self.new_order(side, price, qty)


