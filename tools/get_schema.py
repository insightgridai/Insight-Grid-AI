# tools/get_schema.py
# Supports PostgreSQL AND Snowflake.
# Returns JSON string with table/column/data_type info.

import json
from langchain.tools import tool


def _pg_connect(db_config):
    import psycopg2
    return psycopg2.connect(
        host=db_config["host"],
        port=int(db_config.get("port", 5432)),
        database=db_config["database"],
        user=db_config["user"],
        password=db_config["password"],
        connect_timeout=15,
        sslmode="require",
    )


def _sf_connect(db_config):
    import snowflake.connector
    kwargs = {
        "account":   db_config["account"],
        "user":      db_config["user"],
        "password":  db_config["password"],
        "warehouse": db_config.get("warehouse", "COMPUTE_WH"),
        "database":  db_config.get("database", ""),
        "schema":    db_config.get("schema", "PUBLIC"),
    }
    if db_config.get("role"):
        kwargs["role"] = db_config["role"]
    return snowflake.connector.connect(**kwargs)


def get_schema_tool(db_config: dict):

    db_type = db_config.get("db_type", "postgresql").lower()

    @tool
    def get_schema(_: str = "") -> str:
        """Return database tables and columns as JSON."""
        conn = None
        cur  = None
        try:
            if db_type == "snowflake":
                conn = _sf_connect(db_config)
                cur  = conn.cursor()
                # Snowflake: use INFORMATION_SCHEMA in the connected database
                db_name = db_config.get("database", "").upper()
                schema  = db_config.get("schema", "PUBLIC").upper()
                cur.execute(f"""
                    SELECT TABLE_NAME, COLUMN_NAME, DATA_TYPE
                    FROM {db_name}.INFORMATION_SCHEMA.COLUMNS
                    WHERE TABLE_SCHEMA = '{schema}'
                    ORDER BY TABLE_NAME, ORDINAL_POSITION
                """)
            else:
                conn = _pg_connect(db_config)
                cur  = conn.cursor()
                cur.execute("""
                    SELECT table_name, column_name, data_type
                    FROM information_schema.columns
                    WHERE table_schema = 'public'
                    ORDER BY table_name, ordinal_position
                """)

            rows = cur.fetchall()
            data = [list(r) for r in rows]
            return json.dumps({
                "columns": ["table_name", "column_name", "data_type"],
                "data": data
            })

        except Exception as e:
            return json.dumps({"columns": ["error"], "data": [[str(e)]]})
        finally:
            if cur:
                try: cur.close()
                except Exception: pass
            if conn:
                try: conn.close()
                except Exception: pass

    return get_schema