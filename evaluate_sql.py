import csv
import json
import os
import time
from datetime import datetime, timezone
from decimal import Decimal
from numbers import Number
from pathlib import Path

import pandas as pd
from dotenv import load_dotenv
from google.genai import errors

from database import run_query
from engine import generate_sql

ROOT = Path(__file__).resolve().parent
load_dotenv(ROOT / ".env")

REVENUE = """
SUM(oi.quantity * oi.unit_price_cents *
    (100 - oi.discount_percent) / 10000.0)
"""

CASES = [
    (
        "category_last_quarter",
        "Which product category had the highest revenue last quarter?",
        f"""
        SELECT p.category, ROUND({REVENUE}, 2)
        FROM orders o
        JOIN order_items oi ON oi.order_id = o.order_id
        JOIN products p ON p.product_id = oi.product_id
        WHERE o.status = 'completed'
          AND o.order_date >= '2026-04-01'
          AND o.order_date < '2026-07-01'
        GROUP BY p.category
        ORDER BY 2 DESC LIMIT 1
        """,
    ),
    (
        "regional_revenue",
        "Show revenue by region in 2026.",
        f"""
        SELECT c.region, ROUND({REVENUE}, 2)
        FROM orders o
        JOIN customers c ON c.customer_id = o.customer_id
        JOIN order_items oi ON oi.order_id = o.order_id
        WHERE o.status = 'completed'
          AND o.order_date >= '2026-01-01'
          AND o.order_date < '2027-01-01'
        GROUP BY c.region
        """,
    ),
    (
        "average_order_value",
        "What was the average order value in June 2026?",
        f"""
        SELECT ROUND(
            {REVENUE} / NULLIF(COUNT(DISTINCT o.order_id), 0), 2
        )
        FROM orders o
        JOIN order_items oi ON oi.order_id = o.order_id
        WHERE o.status = 'completed'
          AND o.order_date >= '2026-06-01'
          AND o.order_date < '2026-07-01'
        """,
    ),
    (
        "cancelled_orders",
        "How many orders were cancelled in 2025?",
        """
        SELECT COUNT(*) FROM orders
        WHERE status = 'cancelled'
          AND order_date >= '2025-01-01'
          AND order_date < '2026-01-01'
        """,
    ),
    (
        "completed_orders_may",
        "How many distinct completed orders were placed in May 2026?",
        """
        SELECT COUNT(DISTINCT order_id) FROM orders
        WHERE status = 'completed'
          AND order_date >= '2026-05-01'
          AND order_date < '2026-06-01'
        """,
    ),
    (
        "home_units_january",
        "How many Home-category units were sold in completed orders in January 2026?",
        """
        SELECT SUM(oi.quantity)
        FROM orders o
        JOIN order_items oi ON oi.order_id = o.order_id
        JOIN products p ON p.product_id = oi.product_id
        WHERE o.status = 'completed'
          AND p.category = 'Home'
          AND o.order_date >= '2026-01-01'
          AND o.order_date < '2026-02-01'
        """,
    ),
    (
        "unsupported_profit",
        "What was net profit after supplier costs in 2026?",
        None,
    ),
]

def normalize(frame):
    # Ignore aliases and row order; preserve duplicates and column order.
    def cell(value):
        if pd.isna(value):
            return ("null", "")
        if isinstance(value, Number):
            number = Decimal(str(value)).quantize(Decimal("0.000001"))
            return ("number", number)
        return ("text", str(value))

    return sorted(
        tuple(cell(value) for value in row)
        for row in frame.itertuples(index=False, name=None)
    )

def main():
    key = os.getenv("GEMINI_API_KEY")
    model = os.getenv("GEMINI_MODEL", "gemini-3.1-flash-lite")
    if not key:
        raise SystemExit("GEMINI_API_KEY is missing.")

    # Validate reference queries before making any API requests.
    references = {
        name: run_query(sql) if sql is not None else None
        for name, _, sql in CASES
    }

    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    folder = ROOT / "eval_results" / f"sql_{stamp}"
    folder.mkdir(parents=True)
    records = []

    for name, question, reference_sql in CASES:
        started = time.monotonic()
        record = {
            "case": name,
            "question": question,
            "model": model,
            "expected": "refusal" if reference_sql is None else "answer",
            "status": "",
            "generated_sql": "",
            "reference_sql": reference_sql or "",
        }

        try:
            generated = generate_sql(question, api_key=key, model=model)
            sql = generated["sql"]
            record["generated_sql"] = sql
            record["retrieved_ids"] = [p["id"] for p in generated["passages"]]

            if reference_sql is None:
                record["status"] = (
                    "PASS" if sql == "INSUFFICIENT_CONTEXT"
                    else "FAIL_EXPECTED_REFUSAL"
                )
            elif sql == "INSUFFICIENT_CONTEXT" or not sql:
                record["status"] = "FAIL_NO_ANSWER"
            else:
                actual = run_query(sql)
                expected = references[name]
                match = (
                    actual.shape == expected.shape
                    and normalize(actual) == normalize(expected)
                )
                record["status"] = "PASS" if match else "FAIL_RESULT"
                record["actual"] = json.loads(
                    actual.to_json(orient="split", index=False)
                )
                record["reference"] = json.loads(
                    expected.to_json(orient="split", index=False)
                )
        except errors.APIError as error:
            record["status"] = f"API_ERROR_{error.code}"
        except Exception as error:
            record["status"] = "ERROR"
            record["error_type"] = type(error).__name__
            record["error"] = str(error)

        record["seconds"] = round(time.monotonic() - started, 2)
        records.append(record)
        print(f"{name}: {record['status']}", flush=True)

        # Save after every case so completed work survives interruption.
        (folder / "details.json").write_text(
            json.dumps(records, indent=2), encoding="utf-8"
        )

    fields = ["case", "expected", "status", "seconds", "model"]
    with (folder / "summary.csv").open("w", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(records)

    answers = [r for r in records if r["expected"] == "answer"]
    passed = sum(r["status"] == "PASS" for r in answers)
    print(f"\nAnswer result matches: {passed}/{len(answers)}")
    print(f"Unsupported-question check: {records[-1]['status']}")
    print("API errors remain in the denominator.")
    print(f"Saved evaluation: {folder}")

if __name__ == "__main__":
    main()
