# SQL Sentinel: Multi-Agent Database Assistant

A small college-demo application for asking natural-language questions about a MySQL database. It uses Streamlit, LangGraph, Ollama (`gemma4:31b-cloud` by default), SQLAlchemy, SQLGlot, and a lightweight schema-retrieval index.

## What it does

- Dashboard with live table counts, schema explorer, and basic charts.
- Three agent roles: classifier/security, schema intelligence, and SQL/data analysis.
- Schema retrieval (TF-IDF retrieval over live database metadata).
- LangGraph conditional routing and visible execution trace.
- The latest five question-and-answer pairs are passed as JSON context to help with follow-up questions during the current session.
- SQL validation before execution: single statement, read-only SELECT/CTE only, known tables, row limit.
- Query history in the current Streamlit session.
- No database writes are supported.

## Requirements

- Python 3.10+
- MySQL database access
- Ollama installed and running
- Access to the `gemma4:31b-cloud` model in Ollama

For the cloud model, make sure you are signed in to Ollama and that this works in a terminal first:

```bash
ollama run gemma4:31b-cloud
```

The app calls Ollama through its local API at `http://localhost:11434` by default. If your Ollama setup uses another URL, edit `OLLAMA_BASE_URL` in `.env`.

## Setup

1. Unzip the project.
2. Copy `.env.example` to `.env`.
3. Edit `DATABASE_URL` with your MySQL credentials and database name.
4. Install dependencies in a virtual environment:

### Windows PowerShell

```powershell
py -m venv .venv
.venv\\Scripts\\Activate.ps1
pip install -r requirements.txt
streamlit run app.py
```

### Windows CMD

```bat
py -m venv .venv
.venv\\Scripts\\activate.bat
pip install -r requirements.txt
streamlit run app.py
```

### macOS/Linux

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
streamlit run app.py
```

Open the URL Streamlit prints, usually `http://localhost:8501`.

## Database permissions

Use a dedicated MySQL account with `SELECT` permission only for the target database. The application blocks write statements, but database-level read-only permissions are an important second layer.

Example (run as a MySQL administrator, replacing username/host/password appropriately):

```sql
CREATE USER 'sql_sentinel_reader'@'localhost' IDENTIFIED BY 'replace-with-a-strong-password';
GRANT SELECT, SHOW VIEW ON psd_pvt_ltd.* TO 'sql_sentinel_reader'@'localhost';
FLUSH PRIVILEGES;
```

Use that account in `DATABASE_URL`. If MySQL is on another machine, adjust the host part of the account and connection URL.

## Example questions

- Which tables and primary keys are available?
- Show me the columns in `sales`.
- Which product category generated the highest completed revenue?
- Count employees by department.
- What is the number of employees who left in each department?
- Compare project counts by status.
- How many projects does each department own?
- Show monthly completed revenue for 2026.

## Notes and limitations

- The supplied database snapshot described five tables: `employees`, `projects`, `products`, `sales`, and `employee_project_assignments`. The application inspects the live database instead of hardcoding this schema.
- RAG retrieves schema metadata, not business rows. Actual business answers come from SQL results.
- If schema changes, use the **Refresh schema** button or restart the app.
- A language model can misunderstand ambiguous wording. For example, “revenue” may mean completed sales only or all statuses; specify the intended status where it matters.
- The app is intended for a college demonstration, not an internet-facing production deployment.
- Do not expose the app or Ollama API publicly. Do not put `.env` in GitHub.
- The app never intentionally executes writes. Use a read-only DB user anyway.

## Troubleshooting

**Ollama connection error**
- Start Ollama.
- Confirm `ollama run gemma4:31b-cloud` works in the terminal.
- Check `OLLAMA_BASE_URL`.

**Model not found / cloud access error**
- Confirm the model name exactly matches the one available in your Ollama account.
- Sign in to Ollama if required by your cloud model.
- Test the model in the terminal before starting the app.

**MySQL connection error**
- Check `DATABASE_URL`, database name, host, port, and credentials.
- URL-encode special characters in the password (for example `@` as `%40`).
- Confirm the database user has `SELECT` access.

**Query rejected**
- Open the execution details. The validator deliberately rejects writes, multiple statements, unknown tables, and unsupported query patterns.
