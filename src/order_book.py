
import heapq
import itertools

class Order:
    _ids = itertools.count(0)  # unique id generator

    def __init__(self, side, price, quantity):
        self.id = next(Order._ids)
        self.side = side  # "buy" or "sell"
        self.price = price
        self.quantity = quantity

    def __repr__(self):
        return f"Order(id={self.id}, side={self.side}, price={self.price}, qty={self.quantity})"

class OrderBook:
    def __init__(self):
        self.buys = []  # max-heap (store as -price)
        self.sells = [] # min-heap (normal)
    
    def add_order(self, order):
        if order.side == "buy":
            # Try to match with lowest sell
            while self.sells and order.quantity > 0 and self.sells[0][0] <= order.price:
                best_sell_price, best_sell = heapq.heappop(self.sells)
                traded_qty = min(order.quantity, best_sell.quantity)
                order.quantity -= traded_qty
                best_sell.quantity -= traded_qty
                print(f"TRADE: Buy {traded_qty} @ {best_sell_price}")
                
                if best_sell.quantity > 0:  # leftover sell goes back
                    heapq.heappush(self.sells, (best_sell.price, best_sell))
            
            if order.quantity > 0:  # leftover buy goes into heap
                heapq.heappush(self.buys, (-order.price, order))

        elif order.side == "sell":
            # Try to match with highest buy
            while self.buys and order.quantity > 0 and -self.buys[0][0] >= order.price:
                best_buy_price, best_buy = heapq.heappop(self.buys)
                best_buy_price = -best_buy_price
                traded_qty = min(order.quantity, best_buy.quantity)
                order.quantity -= traded_qty
                best_buy.quantity -= traded_qty
                print(f"TRADE: Sell {traded_qty} @ {best_buy_price}")

                if best_buy.quantity > 0:  # leftover buy goes back
                    heapq.heappush(self.buys, (-best_buy.price, best_buy))
            
            if order.quantity > 0:  # leftover sell goes into heap
                heapq.heappush(self.sells, (order.price, order))

    def show_book(self):
        print("\nORDER BOOK:")
        print("Buys:")
        for _, o in sorted(self.buys, reverse=True):
            print(f"  {o}")
        print("Sells:")
        for _, o in sorted(self.sells):
            print(f"  {o}")
        print()
