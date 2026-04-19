import psycopg2


# -----------------------------------------
# OLD METHOD (OPTIONAL BACKWARD SUPPORT)
# -----------------------------------------
def get_db_connection():
    """
    Optional old static method.
    Keep only if older files still use it.
    """
    raise Exception(
        "Use get_db_connection_dynamic() instead."
    )


# -----------------------------------------
# NEW DYNAMIC CONNECTION
# -----------------------------------------
def get_db_connection_dynamic(config: dict):
    """
    Dynamic PostgreSQL connection from popup UI.

    Expected config:
    {
        "host": "...",
        "port": "5432",
        "database": "...",
        "user": "...",
        "password": "..."
    }
    """

    return psycopg2.connect(
        host=config["host"],
        port=config["port"],
        database=config["database"],
        user=config["user"],
        password=config["password"],
        sslmode="require"
    )
