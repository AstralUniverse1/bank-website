import os
import time
import sqlite3

DB_PATH = os.environ.get(
    "DB_PATH",
    os.path.join(os.path.dirname(__file__), "bank_website.db")
)

def using_mysql() -> bool:
    return bool(os.environ.get("MYSQL_HOST")) or os.environ.get("DB_ENGINE", "").lower() == "mysql"

def get_conn():
    if not using_mysql():
        conn = sqlite3.connect(DB_PATH, check_same_thread=False)
        return conn, conn.cursor()

    # MySQL
    try:
        import pymysql
    except Exception as e:
        raise RuntimeError("PyMySQL not installed. Add 'pymysql' to backend requirements.") from e

    host = os.environ.get("MYSQL_HOST", "localhost")
    port = int(os.environ.get("MYSQL_PORT", "3306"))
    user = os.environ.get("MYSQL_USER", "root")
    password = os.environ.get("MYSQL_PASSWORD", "")
    database = os.environ.get("MYSQL_DATABASE", "bank")

    conn = pymysql.connect(
        host=host,
        port=port,
        user=user,
        password=password,
        database=database,
        charset="utf8mb4",
        autocommit=False,
        cursorclass=pymysql.cursors.Cursor,
    )
    return conn, conn.cursor()

def _wait_for_mysql(timeout_seconds=45):
    start = time.time()
    last_err = None
    while time.time() - start < timeout_seconds:
        try:
            conn, cur = get_conn()
            cur.execute("SELECT 1")
            conn.close()
            return
        except Exception as e:
            last_err = e
            time.sleep(1)
    raise RuntimeError(f"MySQL not ready after {timeout_seconds}s: {last_err}")

def init_db():
    if using_mysql():
        _wait_for_mysql()
        conn, cursor = get_conn()

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id VARCHAR(64) PRIMARY KEY,
                first_name VARCHAR(255),
                last_name VARCHAR(255),
                email VARCHAR(255),
                password VARCHAR(255),
                gender VARCHAR(50),
                birth_date VARCHAR(50),
                phone_number VARCHAR(50),
                address VARCHAR(255),
                balance DECIMAL(12,2) DEFAULT 5000
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS transactions (
                id INT AUTO_INCREMENT PRIMARY KEY,
                user_id VARCHAR(64),
                type VARCHAR(50),
                `date` VARCHAR(50),
                description VARCHAR(255),
                amount DECIMAL(12,2)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
        """)

        conn.commit()
        conn.close()
        return

    # SQLite (existing behavior)
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

        if using_mysql():
            cursor.execute("""
                INSERT INTO users (
                    user_id, first_name, last_name, email, password,
                    gender, birth_date, phone_number, address, balance
                ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
            """, (
                user_id, first_name, last_name, email, password,
                gender, birth_date, phone_number, address, balance
            ))
        else:
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

    if using_mysql():
        cursor.execute(
            "SELECT 1 FROM users WHERE user_id = %s AND password = %s",
            (user_id, password)
        )
    else:
        cursor.execute(
            "SELECT 1 FROM users WHERE user_id = ? AND password = ?",
            (user_id, password)
        )

    ok = cursor.fetchone() is not None
    conn.close()
    return ok

def get_user_balance(user_id):
    conn, cursor = get_conn()

    if using_mysql():
        cursor.execute("SELECT balance FROM users WHERE user_id = %s", (user_id,))
    else:
        cursor.execute("SELECT balance FROM users WHERE user_id = ?", (user_id,))

    row = cursor.fetchone()
    conn.close()
    return None if row is None else row[0]

def update_balance(user_id, new_balance):
    conn, cursor = get_conn()

    if using_mysql():
        cursor.execute("UPDATE users SET balance = %s WHERE user_id = %s", (new_balance, user_id))
    else:
        cursor.execute("UPDATE users SET balance = ? WHERE user_id = ?", (new_balance, user_id))

    conn.commit()
    conn.close()
    return True

def insert_transaction(user_id, type, date, description, amount):
    conn, cursor = get_conn()

    if using_mysql():
        cursor.execute("""
            INSERT INTO transactions (user_id, type, `date`, description, amount)
            VALUES (%s,%s,%s,%s,%s)
        """, (user_id, type, date, description, amount))
    else:
        cursor.execute("""
            INSERT INTO transactions (user_id, type, date, description, amount)
            VALUES (?, ?, ?, ?, ?)
        """, (user_id, type, date, description, amount))

    conn.commit()
    conn.close()
    return True

def get_user_last_transactions(user_id):
    conn, cursor = get_conn()

    if using_mysql():
        cursor.execute("""
            SELECT * FROM transactions
            WHERE user_id = %s
            ORDER BY `date` DESC
            LIMIT 4
        """, (user_id,))
    else:
        cursor.execute("""
            SELECT * FROM transactions
            WHERE user_id = ?
            ORDER BY date DESC
            LIMIT 4
        """, (user_id,))

    rows = cursor.fetchall()
    conn.close()

    return [
        {"date": r[3], "description": r[4], "amount": r[5], "type": r[2]}
        for r in reversed(rows)
    ]