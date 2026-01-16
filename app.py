# app.py

from db.connection import get_db_connection

def main():
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT version()")
    print("Database connected:")
    print(cur.fetchone())

if __name__ == "__main__":
    main()
