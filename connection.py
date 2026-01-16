# db/connection.py

import psycopg2
from config.settings import Settings

def get_db_connection():
    Settings.validate()

    return psycopg2.connect(
        host=Settings.DB_HOST,
        database=Settings.DB_NAME,
        user=Settings.DB_USER,
        password=Settings.DB_PASSWORD,
        port=Settings.DB_PORT,
        sslmode="require"
    )
