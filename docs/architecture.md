order-book-simulator/
│
├── README.md              # High-level project description, setup instructions
├── .gitignore             # Ignore venv, __pycache__, data files, etc.
├── requirements.txt       # Python libraries (numpy, pandas, etc.)
│
├── src/                   # Source code lives here
│   ├── __init__.py
│   ├── order.py           # Order object (price, size, side, timestamp)
│   ├── order_book.py      # Core order book logic (bids/asks, matching)
│   ├── matching_engine.py # Matching + trade execution rules
│   ├── data_handler.py    # (Future) load/save order flow, simulations
│   └── utils.py           # Helper functions (logging, validation, etc.)
│
├── tests/                 # Unit tests for each component
│   ├── test_order.py
│   ├── test_order_book.py
│   └── test_matching_engine.py
│
└── docs/                  # Any documentation, design notes, diagrams
    └── architecture.md    # Overview of system design

