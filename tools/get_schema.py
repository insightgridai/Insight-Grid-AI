import json
import psycopg2

from langchain.tools import tool


# ---------------------------------------------------
# FACTORY TOOL
# ---------------------------------------------------
def get_schema_tool(db_config):

    @tool
    def get_schema(_: str = "") -> str:
        """
        Return PostgreSQL tables and columns.
        """

        conn = None
        cur = None

        try:
            conn = psycopg2.connect(
                host=db_config["host"],
                port=db_config["port"],
                database=db_config["database"],
                user=db_config["user"],
                password=db_config["password"],
                sslmode="require"
            )

            cur = conn.cursor()

            cur.execute("""
                SELECT
                    table_name,
                    column_name,
                    data_type
                FROM information_schema.columns
                WHERE table_schema = 'public'
                ORDER BY table_name, ordinal_position
            """)

            rows = cur.fetchall()

            data = [
                list(r)
                for r in rows
            ]

            return json.dumps({
                "columns": [
                    "table_name",
                    "column_name",
                    "data_type"
                ],
                "data": data
            })

        except Exception as e:

            return json.dumps({
                "columns": ["error"],
                "data": [[str(e)]]
            })

        finally:

            if cur:
                cur.close()

            if conn:
                conn.close()

    return get_schema
