import os
import re
import sqlite3
import time
from pathlib import Path

import streamlit as st
from dotenv import load_dotenv
from google import genai
from google.genai import errors
from sqlglot.errors import ParseError

from database import run_query
from engine import generate_sql

ROOT = Path(__file__).resolve().parent
load_dotenv(ROOT / ".env")

st.set_page_config(
    page_title="Chat with Your Data",
    page_icon="📊",
    layout="wide",
)

st.title("Chat with Your Data")
st.write("Ask a business question about an e-commerce store.")
st.caption(
    "Synthetic data · January 2025–September 2026 · USD · "
    "Demo reference date: September 30, 2026"
)

with st.sidebar:
    st.header("Try a question")
    st.write("• Which product category had the highest revenue last quarter?")
    st.write("• Show revenue by region in 2026.")
    st.write("• What was the average order value in June 2026?")
    st.write("• How many orders were cancelled in 2025?")
    st.divider()
    st.caption(
        "Ask each question in full. This version treats questions independently."
    )
    st.caption(
        "Revenue includes discounted completed orders, excluding tax and shipping."
    )

key = os.getenv("GEMINI_API_KEY")
model = os.getenv("GEMINI_MODEL", "gemini-3.1-flash-lite")

if not key:
    st.error("Add GEMINI_API_KEY to your .env file, then restart the app.")
    st.stop()

with st.form("question_form"):
    question = st.text_input(
        "Your question",
        value="Which product category had the highest revenue last quarter?",
        max_chars=1000,
    )
    submitted = st.form_submit_button("Ask", type="primary")

if submitted:
    st.session_state.pop("result", None)
    question = question.strip()
    if not question:
        st.warning("Enter a question first.")
        st.stop()

    sql = ""
    try:
        started = time.monotonic()
        with st.spinner("Retrieving context and querying the data..."):
            generated = generate_sql(
                question, api_key=key, model=model
            )
            sql = generated["sql"]
            passages = generated["passages"]

            if not sql or sql == "INSUFFICIENT_CONTEXT":
                st.warning(
                    "I need a clearer question or more reference information. "
                    "Try specifying the metric and date range."
                )
                st.stop()

            frame = run_query(sql)
            st.session_state["result"] = {
                "question": question,
                "sql": sql,
                "frame": frame,
                "passages": passages,
                "schema": generated["schema"],
                "seconds": time.monotonic() - started,
            }

    except errors.APIError as error:
        messages = {
            429: "Gemini's quota or rate limit was reached. Try again later.",
            503: "Gemini is busy. Try again shortly.",
            404: "The configured model is unavailable.",
        }
        st.error(messages.get(error.code, f"Gemini request failed ({error.code})."))
    except (ValueError, sqlite3.DatabaseError, ParseError) as error:
        st.error(f"The query could not be completed: {error}")
        if sql:
            st.code(sql, language="sql")
    except RuntimeError as error:
        st.error(str(error))

if "result" in st.session_state:
    result = st.session_state["result"]
    frame = result["frame"]

    st.subheader("Results")
    st.write(result["question"])

    if frame.empty:
        st.info("No matching records were returned.")
    else:
        if len(frame) == 1:
            for column, value in frame.iloc[0].items():
                label = column.replace("_", " ").title()
                if column.endswith("_usd") and value is not None:
                    st.metric(label, f"${float(value):,.2f}")
                else:
                    st.metric(label, str(value))
        st.dataframe(frame, hide_index=True)

    st.caption(
        f"{len(frame)} rows · {result['seconds']:.1f} seconds · "
        "Results come from generated SQL; inspect the query below."
    )

    with st.expander("Generated SQL"):
        st.code(result["sql"], language="sql")

    with st.expander("Retrieved reference context"):
        for passage in result["passages"]:
            st.markdown(f"**{passage['id']}**")
            st.text(passage["text"])

    with st.expander("Database schema supplied to the model"):
        st.code(result.get("schema", ""), language="sql")
