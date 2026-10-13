import hashlib
import json
import os
import re
from urllib.parse import quote
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.exc import SQLAlchemyError

class DatabaseError(RuntimeError):
    pass

def _safe_error(exc):
    # Avoid returning full connection URLs, which can contain credentials.
    msg = str(exc)
    msg = re.sub(r"(mysql\+pymysql://)[^@\s]+@", r"\1***@", msg, flags=re.I)
    return msg[:1200]

class DatabaseService:
    def __init__(self, database_url: str):
        if not database_url:
            raise DatabaseError("DATABASE_URL is missing. Copy .env.example to .env and configure it.")
        self.engine = create_engine(
            database_url,
            pool_pre_ping=True,
            pool_recycle=1800,
            connect_args={"connect_timeout": 8},
        )
        try:
            with self.engine.connect() as conn:
                conn.execute(text("SELECT 1"))
        except Exception as exc:
            raise DatabaseError(_safe_error(exc)) from exc

    def inspect_schema(self):
        try:
            inspector = inspect(self.engine)
            table_names = sorted(inspector.get_table_names())
            tables = {}
            relationships = []
            for table_name in table_names:
                columns = []
                for col in inspector.get_columns(table_name):
                    columns.append({
                        "name": col["name"],
                        "type": str(col["type"]),
                        "nullable": bool(col.get("nullable", True)),
                        "default": str(col.get("default")) if col.get("default") is not None else None,
                    })
                pk = inspector.get_pk_constraint(table_name) or {}
                primary_key = pk.get("constrained_columns") or []
                fks = inspector.get_foreign_keys(table_name) or []
                for fk in fks:
                    constrained = fk.get("constrained_columns") or []
                    referred = fk.get("referred_columns") or []
                    for i, from_col in enumerate(constrained):
                        if i < len(referred):
                            relationships.append({
                                "from_table": table_name,
                                "from_column": from_col,
                                "to_table": fk.get("referred_table"),
                                "to_column": referred[i],
                            })
                try:
                    with self.engine.connect() as conn:
                        count = conn.execute(text(f"SELECT COUNT(*) FROM `{table_name.replace('`', '')}`")).scalar_one()
                except Exception:
                    count = None
                tables[table_name] = {
                    "columns": columns,
                    "primary_key": primary_key,
                    "row_count": int(count) if count is not None else None,
                }
            serial = json.dumps({"tables": tables, "relationships": relationships}, sort_keys=True, default=str)
            return {
                "tables": tables,
                "relationships": relationships,
                "signature": hashlib.sha256(serial.encode("utf-8")).hexdigest(),
            }
        except Exception as exc:
            raise DatabaseError(f"Schema inspection failed: {_safe_error(exc)}") from exc

    def execute_read_query(self, sql: str, max_rows: int = None, timeout_seconds: int = None):
        max_rows = max_rows or int(os.getenv("MAX_ROWS", "200"))
        timeout_seconds = timeout_seconds or int(os.getenv("QUERY_TIMEOUT_SECONDS", "15"))
        # Query has already passed SQLGlot policy validation.
        try:
            with self.engine.connect() as conn:
                # MySQL-specific server-side execution time limit, in milliseconds.
                try:
                    conn.execute(text(f"SET SESSION MAX_EXECUTION_TIME={int(timeout_seconds * 1000)}"))
                except Exception:
                    pass
                result = conn.execute(text(sql))
                columns = list(result.keys())
                rows = result.fetchmany(max_rows + 1)
                truncated = len(rows) > max_rows
                rows = rows[:max_rows]
                serial_rows = []
                for row in rows:
                    serial_rows.append({
                        key: (value.isoformat() if hasattr(value, "isoformat") else value)
                        for key, value in zip(columns, row)
                    })
                return {"columns": columns, "rows": serial_rows, "truncated": truncated}
        except Exception as exc:
            raise DatabaseError(_safe_error(exc)) from exc
