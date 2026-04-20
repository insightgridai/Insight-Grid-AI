# =============================================================
# db/connection.py
# Supports: PostgreSQL (Neon/standard) + Snowflake
# =============================================================

import psycopg2


def get_db_connection_dynamic(cfg: dict):
    """
    cfg keys for PostgreSQL:
        db_type : "postgresql"  (default if missing)
        host, port, database, user, password

    cfg keys for Snowflake:
        db_type   : "snowflake"
        account   : e.g. "dbcitil-nc64603"
        user      : Snowflake username
        password  : Snowflake password
        warehouse : e.g. "COMPUTE_WH"
        database  : Snowflake database name
        schema    : Snowflake schema  (default "PUBLIC")
        role      : optional
    """

    db_type = cfg.get("db_type", "postgresql").lower()

    # ----------------------------------------------------------
    # POSTGRESQL
    # ----------------------------------------------------------
    if db_type == "postgresql":
        conn = psycopg2.connect(
            host=cfg["host"],
            port=int(cfg.get("port", 5432)),
            dbname=cfg["database"],
            user=cfg["user"],
            password=cfg["password"],
            connect_timeout=10,
            sslmode="require"
        )
        return conn

    # ----------------------------------------------------------
    # SNOWFLAKE
    # ----------------------------------------------------------
    elif db_type == "snowflake":
        try:
            import snowflake.connector
        except ImportError:
            raise ImportError(
                "snowflake-connector-python is not installed. "
                "Run: pip install snowflake-connector-python"
            )

        connect_kwargs = {
            "account":   cfg["account"],
            "user":      cfg["user"],
            "password":  cfg["password"],
            "warehouse": cfg.get("warehouse", "COMPUTE_WH"),
            "database":  cfg.get("database", ""),
            "schema":    cfg.get("schema", "PUBLIC"),
        }

        if cfg.get("role"):
            connect_kwargs["role"] = cfg["role"]

        conn = snowflake.connector.connect(**connect_kwargs)
        return conn

    else:
        raise ValueError(f"Unsupported db_type: {db_type}")


def test_connection(cfg: dict) -> tuple[bool, str]:
    """Returns (success: bool, message: str)"""
    try:
        conn = get_db_connection_dynamic(cfg)

        db_type = cfg.get("db_type", "postgresql").lower()

        if db_type == "postgresql":
            cur = conn.cursor()
            cur.execute("SELECT 1")
            cur.close()
        elif db_type == "snowflake":
            cur = conn.cursor()
            cur.execute("SELECT CURRENT_VERSION()")
            cur.close()

        conn.close()
        return True, "Connected Successfully"

    except Exception as e:
        return False, str(e)
