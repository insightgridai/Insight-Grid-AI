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


def get_execute_sql_tool(db_config: dict):
    db_type = db_config.get("db_type", "postgresql").lower()

    @tool
    def execute_sql(query: str) -> str:
        """Execute a SQL query and return results as JSON."""
        conn = cur = None
        try:
            if db_type == "snowflake":
                conn = _sf_connect(db_config)
            else:
                conn = _pg_connect(db_config)

            cur = conn.cursor()
            cur.execute(query)

            if cur.description:
                columns = [col[0] for col in cur.description]
                rows    = cur.fetchall()
                data    = []
                for row in rows:
                    clean = []
                    for val in row:
                        if val is None:
                            clean.append(None)
                        elif hasattr(val, "item"):
                            clean.append(val.item())
                        else:
                            try:
                                json.dumps(val)
                                clean.append(val)
                            except (TypeError, ValueError):
                                clean.append(str(val))
                    data.append(clean)
                return json.dumps({"columns": columns, "data": data})
            else:
                conn.commit()
                return json.dumps({"columns": ["status"], "data": [["success"]]})

        except Exception as e:
            return json.dumps({"columns": ["error"], "data": [[str(e)]]})
        finally:
            if cur:
                try: cur.close()
                except Exception: pass
            if conn:
                try: conn.close()
                except Exception: pass

    return execute_sql
