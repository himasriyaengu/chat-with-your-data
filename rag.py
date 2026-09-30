from functools import lru_cache
from pathlib import Path

import chromadb
from sentence_transformers import SentenceTransformer

ROOT = Path(__file__).resolve().parent

DOCUMENTS = {
    "customers": """
Customers table: customer_id INTEGER primary key, customer_name TEXT,
region TEXT. Regions: North, South, East, West.
Join customers.customer_id = orders.customer_id.
Use this table for customer rankings and regional sales.
""",
    "products": """
Products table: product_id INTEGER primary key, product_name TEXT,
category TEXT, price_cents INTEGER.
Categories: Electronics, Clothing, Home, Stationery.
Join products.product_id = order_items.product_id.
price_cents is the catalog price, not necessarily the historical sale price.
""",
    "orders": """
Orders table: order_id INTEGER primary key, customer_id INTEGER,
order_date TEXT in YYYY-MM-DD format, status TEXT.
Statuses: completed, cancelled, returned.
Join orders.order_id = order_items.order_id.
Count DISTINCT orders.order_id when counting orders after joining items.
""",
    "order_items": """
Order_items table: item_id INTEGER primary key, order_id INTEGER,
product_id INTEGER, quantity INTEGER, unit_price_cents INTEGER,
discount_percent INTEGER.
Each row is one product line in an order.
Use unit_price_cents for historical sales and quantity for units sold.
""",
    "revenue": """
Revenue means discounted merchandise sales from completed orders only.
Exclude cancelled and returned orders. Tax and shipping are not included.
Revenue in USD:
SUM(oi.quantity * oi.unit_price_cents *
    (100 - oi.discount_percent) / 10000.0)
Join order_items oi to orders o ON oi.order_id = o.order_id,
then filter o.status = 'completed'.
Round only the final total to two decimal places.
""",
    "dates": """
The synthetic dataset covers January 1, 2025 through September 30, 2026.
Use a fixed demo reference date of September 30, 2026.
Last quarter means the previous completed calendar quarter:
April 1, 2026 through June 30, 2026.
SQL filter: order_date >= '2026-04-01'
AND order_date < '2026-07-01'.
Monthly grouping: strftime('%Y-%m', order_date).
""",
    "average_order_value": """
Average order value means completed-order revenue divided by the
number of distinct completed orders in the selected period.
After joining order_items, use COUNT(DISTINCT o.order_id).
Do not average individual item prices or line totals.
""",
    "category_example": """
Example: revenue by product category.
SELECT p.category,
       ROUND(SUM(oi.quantity * oi.unit_price_cents *
                 (100 - oi.discount_percent) / 10000.0), 2) AS revenue_usd
FROM order_items oi
JOIN orders o ON o.order_id = oi.order_id
JOIN products p ON p.product_id = oi.product_id
WHERE o.status = 'completed'
GROUP BY p.category
ORDER BY revenue_usd DESC;
Add a date filter when the question specifies a period.
""",
}


@lru_cache(maxsize=1)
def get_model():
    return SentenceTransformer("sentence-transformers/all-MiniLM-L6-v2")


def get_collection():
    client = chromadb.PersistentClient(path=str(ROOT / "chroma_store"))
    return client.get_or_create_collection(
        name="ecommerce_knowledge_v1",
        embedding_function=None,
        metadata={"hnsw:space": "cosine"},
    )


def build_index():
    ids = list(DOCUMENTS)
    texts = [DOCUMENTS[doc_id].strip() for doc_id in ids]
    embeddings = get_model().encode(
        texts, normalize_embeddings=True
    ).tolist()
    collection = get_collection()
    collection.upsert(
        ids=ids,
        documents=texts,
        embeddings=embeddings,
        metadatas=[{"source": doc_id} for doc_id in ids],
    )
    print(f"Indexed {collection.count()} knowledge documents.")


def retrieve(question, k=5):
    collection = get_collection()
    if collection.count() == 0:
        raise RuntimeError("Run python rag.py first to build the index.")
    embedding = get_model().encode(
        [question], normalize_embeddings=True
    ).tolist()
    results = collection.query(
        query_embeddings=embedding,
        n_results=min(k, collection.count()),
        include=["documents", "distances"],
    )
    return [
        {"id": doc_id, "text": text, "distance": distance}
        for doc_id, text, distance in zip(
            results["ids"][0],
            results["documents"][0],
            results["distances"][0],
        )
    ]


if __name__ == "__main__":
    build_index()
    question = "Which product category had the highest revenue last quarter?"
    print(f"\nQuestion: {question}")
    for result in retrieve(question):
        print(f"\n--- {result['id']} ---")
        print(result["text"])
