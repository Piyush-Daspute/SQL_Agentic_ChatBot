import os
import time
import streamlit as st
import pandas as pd
import plotly.express as px
from dotenv import load_dotenv

from database import DatabaseService, DatabaseError
from retrieval import SchemaRetriever
from workflow import build_workflow, serialize_recent_chat_history
from llm_client import create_llm

load_dotenv()

st.set_page_config(page_title="SQL Sentinel", page_icon="🛡️", layout="wide")

st.markdown(
    """
    <style>
    div[data-testid="stChatInput"] {
        position: fixed;
        z-index: 1000;
        bottom: 1rem;
        left: 50%;
        transform: translateX(-50%);
        width: min(48rem, calc(100vw - 2rem));
        padding: 0.5rem;
        border-radius: 1rem;
        background: var(--background-color);
        box-shadow: 0 0.25rem 1rem rgba(0, 0, 0, 0.12);
    }

    div[data-testid="stMainBlockContainer"] {
        padding-bottom: 6rem;
    }

    @media (max-width: 640px) {
        div[data-testid="stChatInput"] {
            bottom: 0.5rem;
            width: calc(100vw - 1rem);
        }
    }
    </style>
    """,
    unsafe_allow_html=True,
)

@st.cache_resource(show_spinner=False)
def get_db_service():
    return DatabaseService(os.getenv("DATABASE_URL", "").strip())

@st.cache_resource(show_spinner=False)
def get_llm():
    return create_llm(
        os.getenv("OLLAMA_MODEL", "gemma4:31b-cloud"),
        os.getenv("OLLAMA_BASE_URL", "http://localhost:11434"),
    )

def init_state():
    st.session_state.setdefault("chat", [])
    st.session_state.setdefault("query_history", [])
    st.session_state.setdefault("schema_retriever", None)
    st.session_state.setdefault("schema_signature", None)

def refresh_schema(db):
    catalog = db.inspect_schema()
    st.session_state.schema_retriever = SchemaRetriever(catalog)
    st.session_state.schema_signature = catalog.get("signature")
    return catalog

init_state()
st.title("🛡️ SQL Sentinel")
st.caption("Multi-agent database intelligence · Streamlit + LangGraph + Ollama")

with st.sidebar:
    st.header("Connection")
    st.write("**LLM model:**", os.getenv("OLLAMA_MODEL", "gemma4:31b-cloud"))
    st.write("**Ollama URL:**", os.getenv("OLLAMA_BASE_URL", "http://localhost:11434"))
    if st.button("Refresh schema", use_container_width=True):
        st.session_state.schema_retriever = None
        st.rerun()
    st.divider()
    st.write("**Safety policy**")
    st.caption("Read-only SQL · One statement · Known tables · Bounded result rows")
    if st.button("Clear chat history", use_container_width=True):
        st.session_state.chat = []
        st.session_state.query_history = []
        st.rerun()

try:
    db = get_db_service()
    with st.spinner("Connecting to database and inspecting schema..."):
        catalog = db.inspect_schema()
        if (st.session_state.schema_retriever is None or
                st.session_state.schema_signature != catalog.get("signature")):
            st.session_state.schema_retriever = SchemaRetriever(catalog)
            st.session_state.schema_signature = catalog.get("signature")
except Exception as exc:
    st.error("Could not connect to the database or inspect its schema.")
    st.code(str(exc))
    st.info("Edit DATABASE_URL in .env, then restart Streamlit. See README.md for setup.")
    st.stop()

try:
    llm = get_llm()
except Exception as exc:
    st.error("Could not initialize the Ollama model client.")
    st.code(str(exc))
    st.info("Confirm Ollama is running and the model works with `ollama run gemma4:31b-cloud`.")
    st.stop()

catalog = st.session_state.schema_retriever.catalog
table_names = list(catalog["tables"].keys())
total_rows = sum((t.get("row_count") or 0) for t in catalog["tables"].values())

tab_overview, tab_schema, tab_chat, tab_history = st.tabs(
    ["Overview", "Database Explorer", "Ask your database", "Query History"]
)

with tab_overview:
    c1, c2, c3 = st.columns(3)
    c1.metric("Tables discovered", len(table_names))
    c2.metric("Approx. total rows", f"{total_rows:,}")
    c3.metric("Schema relationships", len(catalog.get("relationships", [])))
    st.subheader("Table overview")
    overview = pd.DataFrame([
        {"Table": name, "Rows": details.get("row_count", 0),
         "Columns": len(details.get("columns", [])),
         "Primary key": ", ".join(details.get("primary_key", [])) or "Not declared"}
        for name, details in catalog["tables"].items()
    ])
    st.dataframe(overview, use_container_width=True, hide_index=True)
    if table_names:
        selected = st.selectbox("Quick chart: row count by table", table_names)
        chart_df = overview.sort_values("Rows", ascending=False)
        st.plotly_chart(px.bar(chart_df, x="Table", y="Rows", title="Rows per table"),
                        use_container_width=True)
    st.caption("Counts are calculated from the connected database and may take a moment on larger tables.")

with tab_schema:
    st.subheader("Live schema explorer")
    chosen_table = st.selectbox("Select a table", table_names, key="schema_table")
    details = catalog["tables"][chosen_table]
    st.write("**Primary key:**", ", ".join(details.get("primary_key", [])) or "Not declared")
    cols_df = pd.DataFrame(details.get("columns", []))
    st.dataframe(cols_df, use_container_width=True, hide_index=True)
    related = [r for r in catalog.get("relationships", [])
               if r.get("from_table") == chosen_table or r.get("to_table") == chosen_table]
    st.write("**Relationships**")
    if related:
        st.dataframe(pd.DataFrame(related), use_container_width=True, hide_index=True)
    else:
        st.caption("No declared foreign-key relationships discovered for this table.")
    with st.expander("All relationships"):
        if catalog.get("relationships"):
            st.dataframe(pd.DataFrame(catalog["relationships"]), use_container_width=True, hide_index=True)
        else:
            st.write("No declared foreign keys were found.")

with tab_chat:
    st.subheader("Ask a question in plain English")
    st.caption("The system routes schema questions to the schema agent and data questions to the SQL agent.")
    examples = [
        "Which tables and primary keys are available?",
        "Which product category generated the highest completed revenue?",
        "Count employees by department.",
        "How many employees left in each department?",
        "Compare projects by status.",
        "Show monthly completed revenue for 2026.",
    ]
    st.write("Example questions")
    ex_cols = st.columns(3)
    for idx, question in enumerate(examples):
        if ex_cols[idx % 3].button(question, key=f"example_{idx}", use_container_width=True):
            st.session_state.pending_question = question

    for item in st.session_state.chat:
        with st.chat_message(item["role"]):
            st.markdown(item["content"])
            if item.get("details"):
                with st.expander("Agent execution details"):
                    st.json(item["details"])
            if item.get("sql"):
                with st.expander("SQL generated"):
                    st.code(item["sql"], language="sql")
            if item.get("rows") is not None:
                with st.expander("Result preview"):
                    st.dataframe(pd.DataFrame(item["rows"]), use_container_width=True, hide_index=True)

    pending = st.session_state.pop("pending_question", None)
    question = st.chat_input("Ask about schema or business data...")
    if pending:
        question = pending

    if question:
        chat_history_json = serialize_recent_chat_history(st.session_state.chat)
        st.session_state.chat.append({"role": "user", "content": question})
        with st.chat_message("user"):
            st.markdown(question)
        try:
            graph = build_workflow(llm, db, st.session_state.schema_retriever)
            with st.chat_message("assistant"):
                with st.spinner("Agents are working..."):
                    result = graph.invoke({
                        "question": question,
                        "chat_history_json": chat_history_json,
                        "intent": "",
                        "decision": "",
                        "reason": "",
                        "retrieved_schema": [],
                        "sql": "",
                        "validation": {},
                        "rows": [],
                        "answer": "",
                        "trace": [],
                        "retry_count": 0,
                        "error": "",
                    })
                st.markdown(result.get("answer", "No answer was returned."))
                if result.get("sql"):
                    with st.expander("SQL generated"):
                        st.code(result["sql"], language="sql")
                with st.expander("Agent execution details"):
                    st.json({
                        "decision": result.get("decision"),
                        "intent": result.get("intent"),
                        "reason": result.get("reason"),
                        "validation": result.get("validation"),
                        "trace": result.get("trace"),
                        "error": result.get("error"),
                    })
                rows = result.get("rows") or []
                if rows:
                    with st.expander("Result preview", expanded=True):
                        st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
                        if len(rows) > 1:
                            numeric_cols = [c for c in pd.DataFrame(rows).columns
                                            if pd.api.types.is_numeric_dtype(pd.DataFrame(rows)[c])]
                            text_cols = [c for c in pd.DataFrame(rows).columns
                                         if c not in numeric_cols]
                            if numeric_cols and text_cols:
                                chart_df = pd.DataFrame(rows)
                                st.plotly_chart(px.bar(chart_df, x=text_cols[0], y=numeric_cols[0],
                                                       title=f"{numeric_cols[0]} by {text_cols[0]}"),
                                                use_container_width=True)
                response = {
                    "role": "assistant",
                    "content": result.get("answer", "No answer was returned."),
                    "details": {
                        "decision": result.get("decision"),
                        "intent": result.get("intent"),
                        "reason": result.get("reason"),
                        "validation": result.get("validation"),
                        "trace": result.get("trace"),
                        "error": result.get("error"),
                    },
                    "sql": result.get("sql", ""),
                    "rows": rows,
                }
                st.session_state.chat.append(response)
                st.session_state.query_history.insert(0, {
                    "time": time.strftime("%Y-%m-%d %H:%M:%S"),
                    "question": question,
                    "intent": result.get("intent", ""),
                    "decision": result.get("decision", ""),
                    "validation": (result.get("validation") or {}).get("status", ""),
                    "row_count": len(rows),
                })
        except Exception as exc:
            msg = f"Workflow failed: {exc}"
            st.error(msg)
            st.session_state.chat.append({"role": "assistant", "content": msg})

with tab_history:
    st.subheader("Current-session query history")
    if st.session_state.query_history:
        st.dataframe(pd.DataFrame(st.session_state.query_history), use_container_width=True, hide_index=True)
    else:
        st.caption("No questions have been processed in this session yet.")
