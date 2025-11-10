from __future__ import annotations

import random
from typing import Optional, Tuple

from order_book import Order
from trader import Trader

class MarketMaker(Trader):
    """
    Two-sided market maker:
    - Maintains bid & ask around mid.
    - Refreshes quotes if mid moves beyond a threshold.
    - Inventory-aware sizing and quote skew.
    - Slight size randomization to avoid determinism.

    Usage pattern in your sim loop (pseudo):
        mm.update_state(engine)                     # allows cancel/refresh using engine
        mid = compute_mid(engine, fallback=100.0)   # or pass base price
        while True:
            o = mm.generate_order(mid)
            if o is None:
                break
            engine.submit(o)

    Notes:
    - We call engine.cancel(...) inside update_state when a refresh is needed. Your engine
      supports cancel & amend; we use cancel+repost for simplicity. :contentReference[oaicite:3]{index=3}
    - We compute mid via engine.top_of_book(); if empty, let caller pass a fallback mid. :contentReference[oaicite:4]{index=4}
    """

    def __init__(
        self,
        trader_id: str,
        *,
        # quoting
        tick: float = 0.01,            # absolute tick to ensure prices > 0
        offset: float = 0.50,          # absolute offset if pct_offset=False
        pct_offset: bool = False,      # if True, use offset (%) of mid
        # inventory / sizing
        base_size: float = 5.0,
        size_jitter: float = 0.20,     # +/- % jitter on size (0.20 => ±20%)
        inv_limit: float = 100.0,      # soft absolute bound on inventory
        target_inventory: float = 0.0,
        # refreshing
        refresh_abs: float = 0.50,     # refresh if |mid - last_mid| ≥ this (abs mode)
        refresh_pct: Optional[float] = None,  # or % threshold (e.g., 0.005 = 0.5%)
        # risk skew
        skew_bp_per_unit: float = 0.00,  # optional extra basis points per unit inv (0 = off)
        cash: float = 0.0,
        inventory: float = 0.0,
        seed: Optional[int] = None,
    ) -> None:
        super().__init__(trader_id, cash=cash, inventory=inventory)
        if seed is not None:
            random.seed(seed)

        # params
        self.tick = float(tick)
        self.offset = float(offset)
        self.pct_offset = bool(pct_offset)
        self.base_size = float(base_size)
        self.size_jitter = float(size_jitter)
        self.inv_limit = float(inv_limit)
        self.target_inventory = float(target_inventory)
        self.refresh_abs = float(refresh_abs)
        self.refresh_pct = float(refresh_pct) if refresh_pct is not None else None
        self.skew_bp_per_unit = float(skew_bp_per_unit)

        # state
        self._active_bid: Optional[Tuple[int, float, float]] = None  # (id, px, qty)
        self._active_ask: Optional[Tuple[int, float, float]] = None
        self._want_bid: bool = True   # which side to quote next when (re)building
        self._last_mid: Optional[float] = None
        self._needs_refresh: bool = False

    def should_trade(self, delta_t: float) -> bool:
        return True

    # ---------- public hooks ----------
    def update_state(self, order_book_or_engine) -> None:
        """
        Called once per step with your MatchingEngine instance so we can:
        - compute mid,
        - detect significant mid moves and cancel stale quotes, and
        - schedule re-quote on next generate_order() calls.

        We DO NOT place new orders here; we only cancel and set the refresh flag.
        """
        # Mid from engine
        bid, ask = order_book_or_engine.top_of_book()  # engine API :contentReference[oaicite:5]{index=5}
        mid = self._compute_mid(bid, ask, fallback=self._last_mid or 100.0)

        # Detect refresh condition
        if self._last_mid is not None:
            moved = abs(mid - self._last_mid)
            moved_pct = moved / max(self._last_mid, self.tick)
            hit_abs = moved >= self.refresh_abs if self.refresh_abs is not None else False
            hit_pct = self.refresh_pct is not None and moved_pct >= self.refresh_pct
            if hit_abs or hit_pct:
                # Cancel both outstanding quotes if any
                for active in (self._active_bid, self._active_ask):
                    if active is not None:
                        oid, _, _ = active
                        order_book_or_engine.cancel(oid)  # engine API :contentReference[oaicite:6]{index=6}
                self._active_bid = None
                self._active_ask = None
                self._needs_refresh = True

        self._last_mid = mid

    def generate_order(self, current_midprice: float) -> Optional[Order]:
        """
        Return ONE order per call until both sides are active.
        After both are live and no refresh is needed, returns None.
        """
        # If we don't have a mid, do nothing
        if current_midprice is None or current_midprice <= 0:
            return None

        # If no rebuild needed and both sides are active, nothing to do
        if not self._needs_refresh and self._active_bid and self._active_ask:
            return None

        # Decide which side to (re)quote first based on inventory bias
        if self._active_bid is None and self._active_ask is None:
            # Prefer to relieve risk: long => quote ask first; short => bid first
            self._want_bid = self.inventory <= self.target_inventory

        # Compute prices with offset & optional inventory skew
        bid_px, ask_px = self._compute_quotes(current_midprice)

        # Compute inventory-aware sizes (and jitter)
        bid_sz = self._size_for_side("buy")
        ask_sz = self._size_for_side("sell")

        # Decide which order to return this call
        if self._active_bid is None and (self._want_bid or self._active_ask is not None):
            order = self.new_order("buy", bid_px, bid_sz)
            self._active_bid = (order.id, order.price, order.quantity)
            self._want_bid = False
            return order

        if self._active_ask is None:
            order = self.new_order("sell", ask_px, ask_sz)
            self._active_ask = (order.id, order.price, order.quantity)
            self._want_bid = True
            # If we just (re)built both sides, clear refresh flag
            if self._active_bid is not None:
                self._needs_refresh = False
            return order

        # If we reach here, both sides are active; clear refresh flag
        self._needs_refresh = False
        return None

    # ---------- helpers ----------
    def _compute_mid(self, bid: Optional[float], ask: Optional[float], fallback: float) -> float:
        if bid is not None and ask is not None:
            return 0.5 * (bid + ask)
        return fallback

    def _compute_quotes(self, mid: float) -> Tuple[float, float]:
        # base offset: absolute or percentage
        off = (mid * self.offset) if self.pct_offset else self.offset
        off = max(self.tick, off)

        # risk skew (optional): push ask closer and/or bid farther when long; opposite when short
        skew = 0.0
        if self.skew_bp_per_unit != 0.0:
            # convert bps*units into price shift
            skew = (self.skew_bp_per_unit * 1e-4) * (self.inventory - self.target_inventory) * mid

        bid = max(self.tick, mid - off - skew)   # if long, skew>0 ⇒ bid further from mid
        ask = max(self.tick, mid + off - skew)   # if long, skew>0 ⇒ ask closer to mid
        # Ensure bid < ask
        if bid >= ask:
            # collapse minimally to keep a tiny spread
            ask = bid + self.tick
        return (round(bid, 4), round(ask, 4))

    def _size_for_side(self, side: str) -> float:
        """
        Inventory-aware sizing:
        - Shrinks buy size as we get long; shrinks sell size as we get short.
        - Zeroes size if we'd breach inv_limit.
        - Adds ±jitter.
        """
        inv = self.inventory - self.target_inventory
        # normalized pressure in [-1, 1]: -1 (very short) ... 0 ... +1 (very long)
        pressure = max(-1.0, min(1.0, inv / max(self.inv_limit, 1e-9)))

        # Base scale: prefer buying when short (pressure<0), selling when long (pressure>0)
        if side == "buy":
            scale = max(0.0, 1.0 - max(0.0, pressure))  # shrink as we get long
            # hard stop if this buy would push us over the limit
            if inv >= self.inv_limit:
                scale = 0.0
        else:  # sell
            scale = max(0.0, 1.0 + min(0.0, pressure))  # shrink as we get short
            if -inv >= self.inv_limit:
                scale = 0.0

        size = self.base_size * scale
        if size <= 0.0:
            return 0.0

        # jitter
        jitter = 1.0 + self.size_jitter * random.uniform(-1.0, 1.0)
        size *= max(0.0, jitter)

        # round & enforce a floor so orders aren’t zeroed by rounding
        size = max(0.01, round(size, 4))
        return size