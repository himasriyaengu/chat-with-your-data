# Chat with Your Data

Ask plain-English questions about a synthetic e-commerce database.
The app retrieves reference knowledge, generates SQLite queries with
Gemini, and displays results from guarded, read-only execution.

## Problem

Business users need answers without writing SQL. Correct answers require
both the database schema and business definitions, such as how revenue
and average order value are calculated.

## Architecture

1. Read the four allowed table definitions directly from SQLite.
2. Retrieve five reference documents using MiniLM embeddings and Chroma.
3. Supply the schema, retrieved context, and question to Gemini.
4. Validate and execute generated SQL through a restricted database layer.
5. Display results, SQL, schema, and retrieved sources in Streamlit.

The corpus currently contains eight hand-authored reference documents.
This is a small portfolio prototype, not a production-scale knowledge base.

## Data and business rules

- Synthetic data: January 2025 through September 2026.
- Tables: customers, products, orders, and order_items.
- 200 customers, 12 products, 2,000 orders, and 4,927 order items.
- Revenue includes discounted merchandise from completed orders only.
- Tax, shipping, cancelled orders, and returned orders are excluded.
- Historical sales use order-item prices rather than catalog prices.
- Demo reference date: September 30, 2026.
- Last quarter: April 1 through June 30, 2026.

## Guardrails

- SQLite connection opened in read-only mode.
- Query-only mode enabled.
- SQL parser restricts execution to one SELECT statement.
- SQLite authorizer restricts tables and functions.
- Progress handler interrupts long-running queries.
- Results exceeding 200 rows are rejected.

These controls restrict database access; they do not guarantee that a
generated query correctly interprets the user's question.

## Development evaluations

Model: gemini-3.1-flash-lite.

| Evaluation | Observed result |
| --- | --- |
| Mean required-document recall@5, five questions | 86% |
| Mean required-document recall@6, same questions | 91% |
| SQL result matches, initial run | 5/6 |
| Initial API failures | 1 HTTP 503 |
| Separate retry of failed case | 1/1 matched |
| Unsupported-profit question | Correctly declined, 1/1 |

Retrieval scores describe the original retrieval-only context selection.
The revised application always supplies the database schema separately
and retains top-5 retrieval.

SQL evaluations call the same generation function as the app and compare
results against reference SQL. Comparison ignores aliases and row order
but preserves duplicates and column order.

These are development cases on one synthetic database. Some questions
were used during implementation. Results are not a held-out benchmark,
and the retry is reported separately from the initial run.

Evaluation scripts:
- evaluate_retrieval.py
- evaluate_retrieval_k6.py
- evaluate_sql.py

Saved results are in eval_results/.

## Run locally

Requires Python and a Gemini API key.

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Create a local .env file:

```text
GEMINI_API_KEY=your_key_here
GEMINI_MODEL=gemini-3.1-flash-lite
```

Then run:

```bash
python create_database.py
python rag.py
python -m streamlit run app.py --server.fileWatcherType=none
```

Never commit your .env file.

## Cost and limitations

Embeddings and SQLite execution run locally. Each app question makes
one Gemini generation request. API usage is subject to the account's
quota and pricing; monetary cost has not been measured.

The app treats questions independently. Model availability can interrupt
requests. Ambiguous questions or missing reference knowledge can produce
refusals or incorrect SQL.

## Deployment status

Currently runs locally. Public deployment is pending.
