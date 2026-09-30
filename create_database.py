import random
import sqlite3
from datetime import date, timedelta
from pathlib import Path

DB = Path(__file__).resolve().parent / "ecommerce.db"
rng = random.Random(42)

if DB.exists():
    raise SystemExit("Database already exists; leaving it unchanged.")

with sqlite3.connect(DB) as conn:
    conn.execute("PRAGMA foreign_keys = ON")
    conn.executescript("""
        CREATE TABLE customers (
            customer_id INTEGER PRIMARY KEY,
            customer_name TEXT NOT NULL,
            region TEXT NOT NULL
        );

        CREATE TABLE products (
            product_id INTEGER PRIMARY KEY,
            product_name TEXT NOT NULL,
            category TEXT NOT NULL,
            price_cents INTEGER NOT NULL CHECK(price_cents > 0)
        );

        CREATE TABLE orders (
            order_id INTEGER PRIMARY KEY,
            customer_id INTEGER NOT NULL REFERENCES customers(customer_id),
            order_date TEXT NOT NULL,
            status TEXT NOT NULL
        );

        CREATE TABLE order_items (
            item_id INTEGER PRIMARY KEY,
            order_id INTEGER NOT NULL REFERENCES orders(order_id),
            product_id INTEGER NOT NULL REFERENCES products(product_id),
            quantity INTEGER NOT NULL CHECK(quantity > 0),
            unit_price_cents INTEGER NOT NULL,
            discount_percent INTEGER NOT NULL
        );
    """)

    products = [
        (1, "Laptop", "Electronics", 89900),
        (2, "Headphones", "Electronics", 7900),
        (3, "Keyboard", "Electronics", 4900),
        (4, "T-shirt", "Clothing", 2500),
        (5, "Jeans", "Clothing", 5900),
        (6, "Sneakers", "Clothing", 8500),
        (7, "Desk lamp", "Home", 3500),
        (8, "Coffee maker", "Home", 9900),
        (9, "Bedsheet set", "Home", 4500),
        (10, "Notebook", "Stationery", 800),
        (11, "Pen set", "Stationery", 1200),
        (12, "Planner", "Stationery", 1800),
    ]
    conn.executemany("INSERT INTO products VALUES (?, ?, ?, ?)", products)

    regions = ["North", "South", "East", "West"]
    for customer_id in range(1, 201):
        conn.execute(
            "INSERT INTO customers VALUES (?, ?, ?)",
            (customer_id, f"Customer {customer_id:03}", rng.choice(regions)),
        )

    start = date(2025, 1, 1)
    end = date(2026, 9, 30)

    for order_id in range(1, 2001):
        order_date = start + timedelta(
            days=rng.randrange((end - start).days + 1)
        )
        status = rng.choices(
            ["completed", "cancelled", "returned"],
            weights=[85, 8, 7],
        )[0]
        conn.execute(
            "INSERT INTO orders VALUES (?, ?, ?, ?)",
            (order_id, rng.randint(1, 200), order_date.isoformat(), status),
        )

        for product in rng.sample(products, rng.randint(1, 4)):
            conn.execute(
                """INSERT INTO order_items
                   (order_id, product_id, quantity,
                    unit_price_cents, discount_percent)
                   VALUES (?, ?, ?, ?, ?)""",
                (
                    order_id,
                    product[0],
                    rng.randint(1, 3),
                    product[3],
                    rng.choice([0, 0, 0, 5, 10, 15]),
                ),
            )

    item_count = conn.execute(
        "SELECT COUNT(*) FROM order_items"
    ).fetchone()[0]

print(f"Created ecommerce.db: 200 customers, 12 products, "
      f"2,000 orders, {item_count:,} order items.")
