import sqlite3

conn = sqlite3.connect('bank_website.db', check_same_thread=False)
cursor = conn.cursor()

def insert_user(user_id, first_name, last_name, email, password,
                gender, birth_date, phone_number,
                address, balance):
    try:
        cursor.execute('''
            INSERT INTO users (
                user_id, first_name, last_name, email, password,
                gender, birth_date, phone_number, address, balance
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            user_id, first_name, last_name, email, password,
            gender, birth_date, phone_number, address, balance
        ))

        conn.commit()
        print(f"User {first_name} {last_name} inserted successfully.")
        return True
    except Exception as e:
        print(f"Error inserting user: {e}")
        return False


def check_user_credentials(user_id, password):
    try:
        cursor.execute('''
            SELECT * FROM users
            WHERE user_id = ? AND password = ?
        ''', (user_id, password))

        user = cursor.fetchone()
        if user is None:
            return False
        else:
            return True

    except Exception as e:
        print(f"Error checking credentials: {e}")
        return False


def get_user_balance(user_id):
    try:
        cursor.execute('''
            SELECT balance FROM users
            WHERE user_id = ?
        ''', (user_id, ))

        user = cursor.fetchone()
        if user is None:
            return None
        else:
            print(user)
            return user[0]

    except Exception as e:
        print(f"Error checking credentials: {e}")
        return None


def update_balance(user_id, new_balance):
    try:
        cursor.execute('''
            UPDATE users 
             SET balance = ?
             WHERE user_id = ?
        ''', (
            new_balance, user_id))

        conn.commit()
        print("The balance was updated successfully.")
        return True
    except Exception as e:
        print(f"Error updating balance: {e}")
        return False


def insert_transaction(user_id, type, date, description, amount):
    try:
        cursor.execute('''
            INSERT INTO transactions (
                user_id, type, date, description, amount
            ) VALUES (?, ?, ?, ?, ?)
        ''', (
            user_id, type, date, description, amount))

        conn.commit()
        print("The transaction was inserted successfully.")
        return True
    except Exception as e:
        print(f"Error inserting transaction: {e}")
        return False

def get_user_last_transactions(user_id):
    try:
        cursor.execute('''
            SELECT * FROM transactions
            WHERE user_id = ?
            ORDER BY date DESC
            LIMIT 4
        ''', (user_id, ))

        transactions = cursor.fetchall()
        formatted_transactions = []
        for transaction in transactions:
            formatted_transactions.append({
                "date": transaction[3],
                "description": transaction[4],
                "amount": transaction[5],
                "type": transaction[2]
            })
        return formatted_transactions[::-1]

    except Exception as e:
        print(f"Error getting user transactions: {e}")
        return None