from __future__ import annotations
from collections import deque
from dataclasses import dataclass
import heapq
from typing import Deque, Dict, List, Optional, Tuple, Callable
from order_book import Order

Side = str  # "buy" | "sell"

@dataclass
class Trade:
    taker_order_id: int
    maker_order_id: int
    price: float
    quantity: float

class PriceLevel:
    def __init__(self, price: float) -> None:
        self.price = float(price)
        self.queue: Deque[Order] = deque()  # FIFO for price–time priority

    def add(self, order: Order) -> None:
        self.queue.append(order)

    def peek(self) -> Optional[Order]:
        return self.queue[0] if self.queue else None

    def pop(self) -> Optional[Order]:
        return self.queue.popleft() if self.queue else None

    def remove(self, order_id: int) -> bool:
        for i, o in enumerate(self.queue):
            if o.id == order_id:
                del self.queue[i]
                return True
        return False

    def __bool__(self) -> bool:
        return bool(self.queue)

class MatchingEngine:
    """
    Stand‑alone price–time‑priority matching engine that CONSUMES the user's
    `Order` objects (defined in order_book.py). No new Order type is defined.

    Features
    --------
    - Limit orders (buy/sell) with partial fills
    - Matching at MAKER price (standard)
    - Cancel and Amend (amend resets time priority)
    - Top-of-book and full depth queries
    - Pluggable callbacks for trades/accept/cancel/reject
    """

    def __init__(
        self,
        on_trade: Optional[Callable[[Trade], None]] = None,
        on_accept: Optional[Callable[[Order], None]] = None,
        on_cancel: Optional[Callable[[int], None]] = None,
        on_reject: Optional[Callable[[Order, str], None]] = None,
    ) -> None:
        # price -> level
        self.bids: Dict[float, PriceLevel] = {}
        self.asks: Dict[float, PriceLevel] = {}

        # best-price heaps (max-heap for bids via negatives)
        self._bid_heap: List[float] = []
        self._ask_heap: List[float] = []

        # order_id -> (price, side)
        self._orders: Dict[int, Tuple[float, Side]] = {}

        # hooks
        self._on_trade = on_trade or (lambda t: None)
        self._on_accept = on_accept or (lambda o: None)
        self._on_cancel = on_cancel or (lambda oid: None)
        self._on_reject = on_reject or (lambda o, msg: None)

    # --- public API -----------------------------------------------------
    def submit(self, order: Order) -> int:
        # Only limit orders are supported by the provided Order class
        if order.price is None or order.price <= 0:
            self._on_reject(order, "Price must be positive for limit orders")
            return -1
        if order.quantity is None or order.quantity <= 0:
            self._on_reject(order, "Quantity must be positive")
            return -1

        self._on_accept(order)
        if order.side == "buy":
            # Cross the spread
            while order.quantity > 0 and self._ask_heap and self._ask_heap[0] <= order.price:
                self._consume_best_ask(order)
            # Rest any remainder
            if order.quantity > 0:
                self._rest(order)
        elif order.side == "sell":
            while order.quantity > 0 and self._bid_heap and (-self._bid_heap[0]) >= order.price:
                self._consume_best_bid(order)
            if order.quantity > 0:
                self._rest(order)
        else:
            self._on_reject(order, "Unknown side (use 'buy' or 'sell')")
            return -1
        return order.id

    def cancel(self, order_id: int) -> bool:
        meta = self._orders.get(order_id)
        if not meta:
            return False
        price, side = meta
        level = (self.bids if side == "buy" else self.asks).get(price)
        if level and level.remove(order_id):
            del self._orders[order_id]
            if not level:
                self._delete_level(price, side)
            self._on_cancel(order_id)
            return True
        return False

    def amend(self, order_id: int, new_qty: Optional[float] = None, new_price: Optional[float] = None) -> bool:
        meta = self._orders.get(order_id)
        if not meta:
            return False
        price, side = meta
        book = self.bids if side == "buy" else self.asks
        level = book.get(price)
        if not level:
            return False
        # locate and remove
        target: Optional[Order] = None
        for i, o in enumerate(level.queue):
            if o.id == order_id:
                target = o
                del level.queue[i]
                break
        if target is None:
            return False
        if not level:
            self._delete_level(price, side)
        # apply edits
        if new_qty is not None:
            if new_qty <= 0:
                del self._orders[order_id]
                self._on_cancel(order_id)
                return True
            target.quantity = new_qty
        if new_price is not None:
            if new_price <= 0:
                self._on_reject(target, "New price must be positive")
                return False
            target.price = new_price
        # reset time priority by re-submit
        del self._orders[order_id]
        self.submit(target)
        return True

    # --- queries --------------------------------------------------------
    def top_of_book(self) -> Tuple[Optional[float], Optional[float]]:
        bid = -self._bid_heap[0] if self._bid_heap else None
        ask = self._ask_heap[0] if self._ask_heap else None
        return bid, ask

    def depth(self, side: Side) -> List[Tuple[float, float]]:
        book = self.bids if side == "buy" else self.asks
        prices = sorted(book.keys(), reverse=(side == "buy"))
        out: List[Tuple[float, float]] = []
        for p in prices:
            q = sum(o.quantity for o in book[p].queue)
            if q > 0:
                out.append((p, q))
        return out

    # --- internals ------------------------------------------------------
    def _consume_best_ask(self, taker: Order) -> None:
        best_price = self._ask_heap[0]
        level = self.asks[best_price]
        self._trade_against_level(taker, level, best_price)
        if not level:
            self._delete_level(best_price, "sell")

    def _consume_best_bid(self, taker: Order) -> None:
        best_price = -self._bid_heap[0]
        level = self.bids[best_price]
        self._trade_against_level(taker, level, best_price)
        if not level:
            self._delete_level(best_price, "buy")

    def _trade_against_level(self, taker: Order, level: PriceLevel, maker_price: float) -> None:
        while taker.quantity > 0 and level:
            maker = level.peek()
            traded = min(taker.quantity, maker.quantity)
            taker.quantity -= traded
            maker.quantity -= traded
            self._on_trade(Trade(
                taker_order_id=taker.id,
                maker_order_id=maker.id,
                price=maker_price,
                quantity=traded,
            ))
            if maker.quantity == 0:
                level.pop()
                del self._orders[maker.id]

    def _rest(self, order: Order) -> None:
        price = float(order.price)
        book = self.bids if order.side == "buy" else self.asks
        heap = self._bid_heap if order.side == "buy" else self._ask_heap
        level = book.get(price)
        if level is None:
            level = PriceLevel(price)
            book[price] = level
            if order.side == "buy":
                heapq.heappush(self._bid_heap, -price)
            else:
                heapq.heappush(self._ask_heap, price)
        level.add(order)
        self._orders[order.id] = (price, order.side)

    def _delete_level(self, price: float, side: Side) -> None:
        book = self.bids if side == "buy" else self.asks
        if price in book:
            del book[price]
        if side == "buy":
            while self._bid_heap and (-self._bid_heap[0]) not in self.bids:
                heapq.heappop(self._bid_heap)
        else:
            while self._ask_heap and self._ask_heap[0] not in self.asks:
                heapq.heappop(self._ask_heap)


