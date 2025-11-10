import math
import random
from order_book import Order
from trader import Trader  # only needed if Trader is in a separate file


class NoiseTrader(Trader):
    """
    A trader that places random buy/sell orders based on a Poisson process.

    Each NoiseTrader has:
      - λ (lambda_rate): expected trading frequency (trades per unit time)
      - price_vol: max relative deviation from the midprice (volatility)
      - quantity_range: (min, max) order sizes

    At each simulation tick, the simulation will call trader.should_trade(dt).
    If it returns True, generate_order(mid_price) is called to create an order.
    """

    def __init__(
        self,
        trader_id: str,
        lambda_rate: float = 0.4,
        price_vol: float = 0.02,
        quantity_range=(1.0, 100.0)
    ):
        super().__init__(trader_id)
        self.lambda_rate = lambda_rate
        self.price_vol = price_vol
        self.quantity_range = quantity_range

    # --- Poisson decision process ---
    def should_trade(self, delta_t: float) -> bool:
        """
        Decide whether to trade during this time tick.

        Uses a Poisson process with arrival rate λ:
            P(trade occurs) = 1 - exp(-λ * Δt)
        """
        p_trade = 1 - math.exp(-self.lambda_rate * delta_t)
        return random.random() < p_trade

    # --- Order generation logic ---
    def generate_order(self, mid_price: float) -> Order:
        """
        Create a random buy or sell order around the current midprice.
        """
        side = random.choice(["buy", "sell"])

        # Perturb price by up to ±price_vol fraction of the midprice
        deviation = 1 + random.uniform(-self.price_vol, self.price_vol)
        price = round(mid_price * deviation, 2)

        quantity = round(random.uniform(*self.quantity_range), 2)

        print(f"[{self.trader_id}] {side.upper()} {quantity:.2f} @ ${price:.2f}")
        return self.new_order(side, price, quantity)
