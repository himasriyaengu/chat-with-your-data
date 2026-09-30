import sqlite3
import time
from pathlib import Path

import pandas as pd
import sqlglot
from sqlglot import exp

DB = Path(__file__).resolve().parent / "ecommerce.db"
TABLES = {"customers", "products", "orders", "order_items"}
FUNCTIONS = {
    "sum", "count", "avg", "min", "max", "round",
    "coalesce", "nullif", "strftime", "date",
    "lower", "upper", "abs",
}


def authorize(action, arg1, arg2, database, source):
    if action == sqlite3.SQLITE_SELECT:
        return sqlite3.SQLITE_OK
    if action == sqlite3.SQLITE_READ:
        if database == "main" and arg1 in TABLES:
            return sqlite3.SQLITE_OK
    if action == sqlite3.SQLITE_FUNCTION:
        if (arg2 or "").lower() in FUNCTIONS:
            return sqlite3.SQLITE_OK
    return sqlite3.SQLITE_DENY


def run_query(sql):
    if not sql or len(sql) > 20000:
        raise ValueError("SQL is empty or too long.")

    statements = sqlglot.parse(sql, read="sqlite")
    if len(statements) != 1 or not isinstance(statements[0], exp.Select):
        raise ValueError("Only one SELECT query is allowed.")

    conn = sqlite3.connect(DB.as_uri() + "?mode=ro", uri=True)
    try:
        conn.execute("PRAGMA query_only = ON")
        conn.set_authorizer(authorize)

        deadline = time.monotonic() + 3
        conn.set_progress_handler(
            lambda: int(time.monotonic() > deadline), 1000
        )

        cursor = conn.execute(sql)
        rows = cursor.fetchmany(201)
        if len(rows) > 200:
            raise ValueError("Result exceeds 200 rows. Narrow the question.")

        columns = [column[0] for column in cursor.description]
        return pd.DataFrame(rows, columns=columns)
    finally:
        conn.close()


if __name__ == "__main__":
    sql = """
    SELECT p.category,
           ROUND(SUM(oi.quantity * oi.unit_price_cents *
                     (100 - oi.discount_percent) / 10000.0), 2)
               AS revenue_usd
    FROM order_items oi
    JOIN orders o ON o.order_id = oi.order_id
    JOIN products p ON p.product_id = oi.product_id
    WHERE o.status = 'completed'
      AND o.order_date >= '2026-04-01'
      AND o.order_date < '2026-07-01'
    GROUP BY p.category
    ORDER BY revenue_usd DESC
    LIMIT 1;
    """
    print(run_query(sql).to_string(index=False))

    for blocked_sql in [
        "DELETE FROM orders",
        "SELECT * FROM sqlite_master",
        "SELECT load_extension('anything')",
        "SELECT 1; SELECT 2;",
    ]:
        try:
            run_query(blocked_sql)
        except (ValueError, sqlite3.DatabaseError):
            print("Blocked:", blocked_sql)
        else:
            raise AssertionError(f"Guardrail failed: {blocked_sql}")
