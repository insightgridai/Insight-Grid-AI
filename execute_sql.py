from langchain.tools import tool
from db.connection import get_db_connection

@tool
def execute_sql(query: str) -> str:
    """
    Executes SQL query on any DB-API compatible database.
    Works with PostgreSQL, SQLite, MySQL, etc.
    """
    try:
        conn = get_db_connection()
        cur = conn.cursor()

        cur.execute(query)

        # SELECT queries return rows
        if cur.description is not None:
            rows = cur.fetchall()
            result = rows
        else:
            conn.commit()
            result = "Query executed successfully"

        cur.close()
        conn.close()

        return str(result)

    except Exception as e:
        return f"Error: {str(e)}"