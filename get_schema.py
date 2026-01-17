from langchain.tools import tool
from db.connection import get_db_connection

@tool
def get_schema(sample_query: str = "SELECT * FROM users LIMIT 1") -> str:
    """
    Returns column names and types inferred from a sample query.
    Works across all DB-API databases.
    """
    try:
        conn = get_db_connection()
        cur = conn.cursor()

        cur.execute(sample_query)

        if cur.description is None:
            return "No schema available for this query."

        schema = []
        for col in cur.description:
            # col[0] = column name, col[1] = type code
            schema.append(f"{col[0]}")

        cur.close()
        conn.close()

        return "Columns: " + ", ".join(schema)

    except Exception as e:
        return f"Error: {str(e)}"