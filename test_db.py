import sqlite3
import auth

auth.init_db()

conn = sqlite3.connect("users.db")
cursor = conn.cursor()
try:
    cursor.execute("SELECT * FROM user_portfolios")
    rows = cursor.fetchall()
    print("USER PORTFOLIOS ROWS COUNT:", len(rows))
    for r in rows:
        print(r)
except Exception as e:
    print("SQLITE QUERY ERROR:", e)
conn.close()
