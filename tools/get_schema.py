from langchain.tools import tool
from db.connection import get_db_connection


@tool
def get_schema(table_name: str = None) -> str:
    """
    Returns schema (column names + data types).
    If table_name is provided → returns schema of that table
    Else → returns list of tables
    """

    try:
        conn = get_db_connection()
        cur = conn.cursor()

        # If no table → list tables
        if not table_name:
            cur.execute(
                "SELECT table_name FROM information_schema.tables WHERE table_schema='public';"
            )
            tables = [row[0] for row in cur.fetchall()]

            cur.close()
            conn.close()

            return f"Available tables: {', '.join(tables)}"

        # Get schema for specific table
        cur.execute(f"SELECT * FROM {table_name} LIMIT 1")

        if cur.description is None:
            return f"No schema found for table {table_name}"

        schema = []
        for col in cur.description:
            col_name = col[0]
            col_type = str(col[1])
            schema.append(f"{col_name} ({col_type})")

        cur.close()
        conn.close()

        return f"Schema for {table_name}: " + ", ".join(schema)

    except Exception as e:
        return f"Error: {str(e)}"