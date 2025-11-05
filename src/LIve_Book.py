import yfinance as yf
import random
import time
import matplotlib.pyplot as plt
import matplotlib.animation as animation

# ---------- PARAMETERS ----------
symbol = "AAPL"       # Change to any stock you want (e.g., MSFT, SPY, NVDA)
depth = 5              # How many bid/ask levels to show
spread = 0.02          # Base spread width
refresh_ms = 1000      # Refresh interval in milliseconds

# ---------- ORDER BOOK SIMULATION ----------
def get_live_price(symbol):
    try:
        data = yf.Ticker(symbol).history(period="1m")
        return float(data["Close"].iloc[-1])
    except Exception:
        return None

def simulate_order_book(price):
    bids = [(round(price - i * spread, 2), random.randint(10, 50)) for i in range(1, depth + 1)]
    asks = [(round(price + i * spread, 2), random.randint(10, 50)) for i in range(1, depth + 1)]
    return bids, asks

# ---------- LIVE VISUALIZATION ----------
fig, ax = plt.subplots()

def update(frame):
    price = get_live_price(symbol)
    if not price:
        return

    bids, asks = simulate_order_book(price)
    ax.clear()

    # Plot bids (green) and asks (red)
    ax.bar([p for p, _ in bids], [s for _, s in bids], color='green', width=0.01, label='Bids')
    ax.bar([p for p, _ in asks], [s for _, s in asks], color='red', width=0.01, label='Asks')

    ax.axvline(price, color='black', linestyle='--', label=f'Midprice: ${price:.2f}')
    ax.set_title(f"Simulated Live Order Book for {symbol}")
    ax.set_xlabel("Price")
    ax.set_ylabel("Order Size")
    ax.legend(loc="upper right")

ani = animation.FuncAnimation(fig, update, interval=refresh_ms)
plt.show()
