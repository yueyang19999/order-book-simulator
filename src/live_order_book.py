# live_order_book.py

import random
from typing import List, Tuple, Optional

import matplotlib.pyplot as plt
import matplotlib.animation as animation

from matching_engine import MatchingEngine, Trade
from order_book import Order
from noise_trader import NoiseTrader
from informed_trader import InformedTrader
from market_maker import MarketMaker

BASE_PRICE = 100.0


class LiveOrderBookSim:
    """
    A lightweight simulation that uses your existing MatchingEngine and
    trader classes, and exposes a single `step()` method suitable for
    driving a live matplotlib animation.
    """

    def __init__(self, seed: int = 42):
        random.seed(seed)

        # Matching engine + callbacks
        self.trades: List[Trade] = []
        self.accepted_orders: List[Order] = []
        self.cancelled_orders: List[int] = []
        self.rejected_orders: List[tuple] = []

        self.engine = MatchingEngine(
            on_trade=self._on_trade,
            on_accept=self._on_accept,
            on_cancel=self._on_cancel,
            on_reject=self._on_reject,
        )

        self.traders = []
        self.current_time = 0.0

        # Set up initial book + traders
        self._setup_initial_book()
        self._setup_traders()

    # ---------- callbacks for MatchingEngine ----------

    def _on_trade(self, trade: Trade):
        self.trades.append(trade)
        # For a cleaner presentation, keep this short:
        print(f"TRADE: {trade.quantity:.1f} @ {trade.price:.2f}")

    def _on_accept(self, order: Order):
        self.accepted_orders.append(order)
        # You can comment this out if it’s too spammy:
        # print(f"ACCEPT: {order.id} {order.side} {order.quantity:.1f} @ {order.price:.2f}")

    def _on_cancel(self, order_id: int):
        self.cancelled_orders.append(order_id)
        # print(f"CANCEL: {order_id}")

    def _on_reject(self, order: Order, reason: str):
        self.rejected_orders.append((order, reason))
        print(f"REJECT: {order.id} - {reason}")

    # ---------- setup ----------

    def _setup_initial_book(self):
        print("Submitting initial orders to seed the book...")
        o1 = Order(side="buy",  price=0.99 * BASE_PRICE, quantity=50.0)
        o2 = Order(side="buy",  price=0.98 * BASE_PRICE, quantity=30.0)
        o3 = Order(side="sell", price=1.01 * BASE_PRICE, quantity=40.0)

        self.engine.submit(o1)
        self.engine.submit(o2)
        self.engine.submit(o3)

        bid, ask = self.engine.top_of_book()
        print(f"Initial top of book: bid={bid}, ask={ask}")

    def _setup_traders(self):
        # Noise traders
        self.traders.append(NoiseTrader("NoiseTrader_A", lambda_rate=0.3))
        self.traders.append(NoiseTrader("NoiseTrader_B", lambda_rate=0.8))
        self.traders.append(NoiseTrader("NoiseTrader_C", lambda_rate=0.9))

        # Informed traders
        self.traders.append(
            InformedTrader(
                "InformedTrader_X",
                lambda_rate=0.4,
                info_strength=10,
                true_value=150,
            )
        )
        self.traders.append(
            InformedTrader(
                "InformedTrader_Y",
                lambda_rate=0.2,
                info_strength=100,
                true_value=130,
            )
        )

        # Market makers
        self.traders.append(
            MarketMaker(
                "MarketMaker_1",
                offset=0.10,
                base_size=10.0,
                refresh_abs=0.5,
            )
        )
        self.traders.append(
            MarketMaker(
                "MarketMaker_2",
                offset=0.05,
                base_size=8.0,
                refresh_abs=0.3,
            )
        )

        print("Registered traders:")
        for t in self.traders:
            print(f"  - {t.trader_id}")

    # ---------- one simulation step ----------

    def step(self, delta_t: float = 1.0, base_price: float = BASE_PRICE):
        """
        Advance the simulation by one time tick:
          - Market makers refresh quotes
          - Noise + Informed traders possibly trade
        """
        self.current_time += delta_t
        print(f"\n=== t = {self.current_time:.1f} ===")

        bid, ask = self.engine.top_of_book()
        if bid is not None and ask is not None:
            mid = 0.5 * (bid + ask)
        else:
            mid = base_price

        # 1) Market makers update & quote
        for trader in self.traders:
            if isinstance(trader, MarketMaker):
                trader.update_state(self.engine)
                while True:
                    order = trader.generate_order(mid)
                    if order is None:
                        break
                    self.engine.submit(order)

        # 2) Noise + Informed traders
        for trader in self.traders:
            if isinstance(trader, MarketMaker):
                continue

            if trader.should_trade(delta_t):
                if isinstance(trader, InformedTrader):
                    order = trader.generate_order(mid, (bid, ask))
                else:
                    order = trader.generate_order(mid)

                if order is not None:
                    self.engine.submit(order)

    # ---------- helpers for plotting ----------

    def get_depth(self, depth_levels: int = 10):
        """
        Return top N levels for bids and asks from the engine.
        """
        bids = self.engine.depth("buy") or []
        asks = self.engine.depth("sell") or []
        return bids[:depth_levels], asks[:depth_levels]

    def get_midprice(self, fallback: float = BASE_PRICE) -> Optional[float]:
        bid, ask = self.engine.top_of_book()
        if bid is not None and ask is not None:
            return 0.5 * (bid + ask)
        return fallback


# ---------- live plotting code ----------

def main():
    sim = LiveOrderBookSim()

    # Matplotlib setup
    fig, ax = plt.subplots()
    plt.tight_layout()

    depth_levels = 10
    delta_t = 1.0  # simulation time step per frame (can tweak for speed)

    def update(frame):
        # Step the simulation forward
        sim.step(delta_t=delta_t)

        # Get order book depth
        bids, asks = sim.get_depth(depth_levels)

        bid_prices = [p for p, q in bids]
        bid_qtys = [q for p, q in bids]

        ask_prices = [p for p, q in asks]
        ask_qtys = [q for p, q in asks]

        ax.clear()

        # Plot bids and asks
        if bid_prices:
            ax.bar(bid_prices, bid_qtys, width=0.05, color="green", label="Bids")
        if ask_prices:
            ax.bar(ask_prices, ask_qtys, width=0.05, color="red", label="Asks")

        # Midprice line
        mid = sim.get_midprice()
        if mid is not None:
            ax.axvline(mid, linestyle="--", color="black", label=f"Mid: {mid:.2f}")
            ax.set_title(f"Live Order Book (t={sim.current_time:.1f}, mid={mid:.2f})")
        else:
            ax.set_title(f"Live Order Book (t={sim.current_time:.1f})")

        ax.set_xlabel("Price")
        ax.set_ylabel("Quantity")
        ax.legend(loc="upper right")

        # Make x-limits a bit padded
        all_prices = bid_prices + ask_prices
        if all_prices:
            ax.set_xlim(min(all_prices) - 0.5, max(all_prices) + 0.5)

    # Animation: call update() every 500 ms
    ani = animation.FuncAnimation(fig, update, interval=500)

    plt.show()


if __name__ == "__main__":
    main()
