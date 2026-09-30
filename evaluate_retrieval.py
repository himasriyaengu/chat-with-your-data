import csv
from pathlib import Path
from rag import retrieve

# Manually labeled development cases.
# These identify the essential reference documents for each question.
CASES = [
    {
        "question": "Which product category had the highest revenue last quarter?",
        "required": {"products", "order_items", "orders", "revenue", "dates"},
    },
    {
        "question": "Show revenue by customer region in 2026.",
        "required": {"customers", "orders", "order_items", "revenue"},
    },
    {
        "question": "What was the average order value in June 2026?",
        "required": {"average_order_value", "revenue", "orders", "order_items"},
    },
    {
        "question": "How many orders were cancelled in 2025?",
        "required": {"orders"},
    },
    {
        "question": "Which products sold the most units in completed orders?",
        "required": {"products", "orders", "order_items"},
    },
]

def main():
    rows = []

    for case in CASES:
        results = retrieve(case["question"], k=5)
        retrieved = [result["id"] for result in results]
        required = case["required"]
        found = required.intersection(retrieved)
        missing = required.difference(retrieved)

        rows.append({
            "question": case["question"],
            "required_recall_at_5": len(found) / len(required),
            "all_required_found": not missing,
            "missing_documents": "; ".join(sorted(missing)),
            "retrieved_documents": "; ".join(retrieved),
        })

        print(f"\nQuestion: {case['question']}")
        print(f"Required-document recall@5: {len(found) / len(required):.0%}")
        print(f"Missing: {', '.join(sorted(missing)) or 'None'}")

    output = Path(__file__).resolve().parent / "eval_results"
    output.mkdir(exist_ok=True)
    destination = output / "retrieval.csv"

    with destination.open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)

    mean_recall = sum(row["required_recall_at_5"] for row in rows) / len(rows)
    complete = sum(row["all_required_found"] for row in rows)

    print(f"\nMean required-document recall@5: {mean_recall:.1%}")
    print(f"Cases with all required documents: {complete}/{len(rows)}")
    print(f"Saved: {destination}")

if __name__ == "__main__":
    main()
