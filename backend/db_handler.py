import sqlite3
import os

DB_PATH = os.environ.get(
    "DB_PATH",
    os.path.join(os.path.dirname(__file__), "bank_website.db")
)

def get_conn():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    return conn, conn.cursor()

def init_db():
    conn, cursor = get_conn()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id TEXT PRIMARY KEY,
            first_name TEXT,
            last_name TEXT,
            email TEXT,
            password TEXT,
            gender TEXT,
            birth_date TEXT,
            phone_number TEXT,
            address TEXT,
            balance REAL DEFAULT 5000
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS transactions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT,
            type TEXT,
            date TEXT,
            description TEXT,
            amount REAL
        )
    """)

    conn.commit()
    conn.close()

def insert_user(user_id, first_name, last_name, email, password,
                gender, birth_date, phone_number, address, balance):
    try:
        conn, cursor = get_conn()
        cursor.execute("""
            INSERT INTO users (
                user_id, first_name, last_name, email, password,
                gender, birth_date, phone_number, address, balance
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            user_id, first_name, last_name, email, password,
            gender, birth_date, phone_number, address, balance
        ))
        conn.commit()
        conn.close()
        return True, ""
    except Exception as e:
        return False, str(e)

def check_user_credentials(user_id, password):
    conn, cursor = get_conn()
    cursor.execute(
        "SELECT 1 FROM users WHERE user_id = ? AND password = ?",
        (user_id, password)
    )
    ok = cursor.fetchone() is not None
    conn.close()
    return ok

def get_user_balance(user_id):
    conn, cursor = get_conn()
    cursor.execute(
        "SELECT balance FROM users WHERE user_id = ?",
        (user_id,)
    )
    row = cursor.fetchone()
    conn.close()
    return None if row is None else row[0]

def update_balance(user_id, new_balance):
    conn, cursor = get_conn()
    cursor.execute(
        "UPDATE users SET balance = ? WHERE user_id = ?",
        (new_balance, user_id)
    )
    conn.commit()
    conn.close()
    return True

def insert_transaction(user_id, type, date, description, amount):
    conn, cursor = get_conn()
    cursor.execute("""
        INSERT INTO transactions (
            user_id, type, date, description, amount
        ) VALUES (?, ?, ?, ?, ?)
    """, (user_id, type, date, description, amount))
    conn.commit()
    conn.close()
    return True

def get_user_last_transactions(user_id):
    conn, cursor = get_conn()
    cursor.execute("""
        SELECT * FROM transactions
        WHERE user_id = ?
        ORDER BY date DESC
        LIMIT 4
    """, (user_id,))
    rows = cursor.fetchall()
    conn.close()

    return [
        {
            "date": r[3],
            "description": r[4],
            "amount": r[5],
            "type": r[2]
        }
        for r in reversed(rows)
    ]
