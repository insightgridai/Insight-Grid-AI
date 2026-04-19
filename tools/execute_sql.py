import json
import psycopg2

from langchain.tools import tool


# ---------------------------------------------------
# FACTORY TOOL
# ---------------------------------------------------
def get_execute_sql_tool(db_config):

    @tool
    def execute_sql(query: str) -> str:
        """
        Execute PostgreSQL SQL query and return JSON.
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
            cur.execute(query)

            if cur.description:

                columns = [
                    col[0]
                    for col in cur.description
                ]

                rows = cur.fetchall()

                data = [
                    list(row)
                    for row in rows
                ]

                return json.dumps({
                    "columns": columns,
                    "data": data
                })

            else:
                conn.commit()

                return json.dumps({
                    "columns": ["status"],
                    "data": [["success"]]
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

    return execute_sql
