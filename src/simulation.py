import random
from typing import List
from matching_engine import MatchingEngine, Trade
from order_book import Order

class TradingSimulation:
    def __init__(self, seed: int = 42):
        """Initialize simulation with matching engine and tracking."""
        random.seed(seed)
        
        # Track all trades and statistics
        self.trades: List[Trade] = []
        self.accepted_orders: List[Order] = []
        self.cancelled_orders: List[int] = []
        self.rejected_orders: List[tuple] = []
        
        # Create matching engine with callbacks
        self.engine = MatchingEngine(
            on_trade=self._on_trade,
            on_accept=self._on_accept,
            on_cancel=self._on_cancel,
            on_reject=self._on_reject
        )
        
    def _on_trade(self, trade: Trade):
        #Callback when a trade occurs
        self.trades.append(trade)
        print(f"  ✓ TRADE: {trade.quantity:.2f} @ ${trade.price:.2f} "
              f"(Taker: {trade.taker_order_id}, Maker: {trade.maker_order_id})")
    
    def _on_accept(self, order: Order):
        #Callback when an order is accepted.
        self.accepted_orders.append(order)
        print(f"  → ACCEPT: Order {order.id} ({order.side} {order.quantity:.2f} @ ${order.price:.2f})")
    
    def _on_cancel(self, order_id: int):
        #Callback when an order is cancelled.
        self.cancelled_orders.append(order_id)
        print(f"  ✗ CANCEL: Order {order_id}")
    
    def _on_reject(self, order: Order, reason: str):
        #Callback when an order is rejected.
        self.rejected_orders.append((order, reason))
        print(f"  ✗ REJECT: Order {order.id} - {reason}")
    
    def generate_random_order(self, base_price: float = 100.0, 
                            price_spread: float = 10.0) -> Order:
        #Generate a random buy or sell order.
        side = random.choice(["buy", "sell"])
        
        # Generate price around base_price with some spread
        if side == "buy":
            # Buys slightly below base price
            price = base_price - random.uniform(0, price_spread)
        else:
            # Sells slightly above base price
            price = base_price + random.uniform(0, price_spread)
        
        # Random quantity between 1 and 100
        quantity = random.uniform(1, 100)
        
        return Order(side=side, price=round(price, 2), quantity=round(quantity, 2))
    
    def show_order_book(self):
        #Display current state of the order book.
        print("\n" + "="*60)
        print("ORDER BOOK")
        print("="*60)
        
        bid, ask = self.engine.top_of_book()
        bid_str = f"${bid:.2f}" if bid is not None else "N/A"
        ask_str = f"${ask:.2f}" if ask is not None else "N/A"
        print(f"Top of Book: Bid={bid_str}, Ask={ask_str}")
        
        if bid and ask:
            spread = ask - bid
            print(f"Spread: ${spread:.2f}")
        
        print("\nBIDS (Buy Orders):")
        bids = self.engine.depth("buy")
        if bids:
            for price, qty in bids[:10]:  # Show top 10 levels
                print(f"  ${price:7.2f} | {qty:8.2f}")
        else:
            print("  (empty)")
        
        print("\nASKS (Sell Orders):")
        asks = self.engine.depth("sell")
        if asks:
            for price, qty in asks[:10]:  # Show top 10 levels
                print(f"  ${price:7.2f} | {qty:8.2f}")
        else:
            print("  (empty)")
        print("="*60 + "\n")
    
    def show_statistics(self):
        #Display simulation statistics.
        print("\n" + "="*60)
        print("SIMULATION STATISTICS")
        print("="*60)
        print(f"Total Orders Accepted: {len(self.accepted_orders)}")
        print(f"Total Trades Executed: {len(self.trades)}")
        print(f"Total Orders Cancelled: {len(self.cancelled_orders)}")
        print(f"Total Orders Rejected: {len(self.rejected_orders)}")
        
        if self.trades:
            total_volume = sum(t.quantity for t in self.trades)
            avg_price = sum(t.price * t.quantity for t in self.trades) / total_volume
            print(f"\nTotal Volume Traded: {total_volume:.2f}")
            print(f"Average Trade Price: ${avg_price:.2f}")
            print(f"Price Range: ${min(t.price for t in self.trades):.2f} - "
                  f"${max(t.price for t in self.trades):.2f}")
        print("="*60 + "\n")
    
    def run(self, num_orders: int = 20, base_price: float = 100.0, 
            show_book_frequency: int = 5):
        """
        Run the simulation.
        
        Args:
            num_orders: Number of random orders to generate
            base_price: Base price for order generation
            show_book_frequency: Show book state every N orders
        """
        print("\n" + "="*60)
        print("STARTING TRADING SIMULATION")
        print("="*60)
        print(f"Parameters: {num_orders} orders, base price ${base_price:.2f}\n")
        
        for i in range(num_orders):
            print(f"\n--- Step {i+1}/{num_orders} ---")
            
            # Generate and submit random order
            order = self.generate_random_order(base_price=base_price)
            self.engine.submit(order)
            
            # Periodically show the book
            if (i + 1) % show_book_frequency == 0:
                self.show_order_book()
        
        # Show final state
        print("\n" + "="*60)
        print("FINAL STATE")
        print("="*60)
        self.show_order_book()
        self.show_statistics()


def main():
    # Create and run basic simulation
    print("Running basic simulation...")
    sim = TradingSimulation(seed=42)
    sim.run(num_orders=20, base_price=100.0, show_book_frequency=5)
    
    # Optional: Run additional scenarios
    print("\n\n" + "#"*60)
    print("# SCENARIO 2: High volatility (wider spread)")
    print("#"*60)
    sim2 = TradingSimulation(seed=123)
    sim2.run(num_orders=15, base_price=100.0, show_book_frequency=5)
    
    # Demonstrate cancel and amend functionality
    print("\n\n" + "#"*60)
    print("# SCENARIO 3: Testing cancel and amend")
    print("#"*60)
    sim3 = TradingSimulation(seed=456)
    
    # Submit some orders
    print("\nSubmitting initial orders...")
    order1 = Order(side="buy", price=99.0, quantity=50.0)
    order2 = Order(side="buy", price=98.0, quantity=30.0)
    order3 = Order(side="sell", price=101.0, quantity=40.0)
    
    sim3.engine.submit(order1)
    sim3.engine.submit(order2)
    sim3.engine.submit(order3)
    
    sim3.show_order_book()
    
    # Cancel an order
    print(f"\nCancelling order {order2.id}...")
    sim3.engine.cancel(order2.id)
    
    # Amend an order
    print(f"\nAmending order {order1.id} (new quantity: 75.0, new price: 99.5)...")
    sim3.engine.amend(order1.id, new_qty=75.0, new_price=99.5)
    
    sim3.show_order_book()
    sim3.show_statistics()


if __name__ == "__main__":
    main()