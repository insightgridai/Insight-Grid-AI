from langchain.tools import tool
from db.connection import get_db_connection
import json


@tool
def execute_sql(query: str) -> str:
    """
    Executes SQL query and returns structured JSON output.
    Works with PostgreSQL, SQLite, MySQL, etc.
    """

    try:
        conn = get_db_connection()
        cur = conn.cursor()

        cur.execute(query)

        # ----------------------------------------------------
        # SELECT queries → return structured data
        # ----------------------------------------------------
        if cur.description is not None:

            columns = [col[0] for col in cur.description]
            rows = cur.fetchall()

            result = {
                "columns": columns,
                "data": rows
            }

        # ----------------------------------------------------
        # INSERT / UPDATE / DELETE
        # ----------------------------------------------------
        else:
            conn.commit()

            result = {
                "status": "success",
                "message": "Query executed successfully"
            }

        cur.close()
        conn.close()

        return json.dumps(result, default=str)

    except Exception as e:

        return json.dumps({
            "error": str(e)
        })