from langchain.tools import tool
from db.connection import get_db_connection


@tool
def get_schema(table_name: str = None) -> str:
    """
    Get database schema information.

    - If no table_name is provided → returns all available tables
    - If table_name is provided → returns column names and data types
    """

    try:
        conn = get_db_connection()
        cur = conn.cursor()

        # ----------------------------------------------------
        # CASE 1: Return list of tables
        # ----------------------------------------------------
        if not table_name:
            cur.execute("""
                SELECT table_name
                FROM information_schema.tables
                WHERE table_schema = 'public';
            """)

            tables = [row[0] for row in cur.fetchall()]

            cur.close()
            conn.close()

            if not tables:
                return "No tables found in database."

            return "Available tables: " + ", ".join(tables)

        # ----------------------------------------------------
        # CASE 2: Return schema of specific table
        # ----------------------------------------------------
        cur.execute(f"""
            SELECT column_name, data_type
            FROM information_schema.columns
            WHERE table_name = '{table_name}';
        """)

        rows = cur.fetchall()

        cur.close()
        conn.close()

        if not rows:
            return f"No schema found for table '{table_name}'."

        schema = [f"{col} ({dtype})" for col, dtype in rows]

        return f"Schema for {table_name}: " + ", ".join(schema)

    except Exception as e:
        return f"Error fetching schema: {str(e)}"