from flask import Flask, render_template, send_from_directory, abort, request, jsonify
from datetime import datetime
import os

import db_handler
db_handler.init_db()

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
FRONTEND_ROOT = os.path.join(BASE_DIR, "..", "frontend")

app = Flask(
    __name__,
    template_folder=FRONTEND_ROOT,
    static_folder=os.path.join(FRONTEND_ROOT, "static")
)

@app.route('/')
def login_page():
    return render_template('src/login.html')

@app.route('/<path:path>')
def serve_frontend(path):
    full_path = os.path.join(FRONTEND_ROOT, path)
    if os.path.exists(full_path):
        return send_from_directory(os.path.dirname(full_path), os.path.basename(full_path))
    return abort(404)

@app.route('/api/login', methods=['POST'])
def is_valid_user():
    data = request.json or {}
    ok = db_handler.check_user_credentials(
        data.get('user_id'),
        data.get('password')
    )
    return jsonify({
        "status": ok,
        "text": "" if ok else "Please fill the correct credentials"
    })

@app.route('/api/register', methods=['POST'])
def register_user():
    data = request.json or {}

    ok, msg = db_handler.insert_user(
        data.get("user_id"),
        data.get("firstName"),
        data.get("lastName"),
        data.get("email"),
        data.get("password"),
        data.get("gender"),
        data.get("birth_date"),
        data.get("phone_number"),
        data.get("address"),
        5000
    )

    return jsonify({
        "status": ok,
        "text": msg
    })

@app.route('/api/withdraw', methods=['POST'])
def handle_withdraw():
    data = request.json or {}
    user_id = data.get('user_id')
    amount = data.get('amount')
    description = data.get("description")

    balance = db_handler.get_user_balance(user_id)
    if balance is None:
        return jsonify({"status": False, "text": "User not found"})

    if amount > balance:
        return jsonify({"status": False, "text": f"Not enough money. Balance: {balance}"})

    db_handler.insert_transaction(
        user_id, "Withdrawal",
        datetime.now().strftime("%d/%m/%y %H:%M:%S"),
        description, amount
    )
    db_handler.update_balance(user_id, balance - amount)

    return jsonify({
        "status": True,
        "balance": balance - amount,
        "transactions": db_handler.get_user_last_transactions(user_id)
    })

@app.route('/api/get_user_data', methods=['POST'])
def get_user_data():
    data = request.json or {}
    user_id = data.get('user_id')

    balance = db_handler.get_user_balance(user_id)
    if balance is None:
        return jsonify({"status": False, "text": "User not found"})

    return jsonify({
        "status": True,
        "balance": balance,
        "transactions": db_handler.get_user_last_transactions(user_id)
    })

@app.route('/api/transfer', methods=['POST'])
def handle_transfer():
    data = request.json or {}
    from_id = data.get("from_id")
    to_id = data.get("to_id")
    amount = float(data.get("amount"))
    description = data.get("description")

    b1 = db_handler.get_user_balance(from_id)
    b2 = db_handler.get_user_balance(to_id)

    if b1 is None or b2 is None:
        return jsonify({"status": False, "text": "User not found"})
    if from_id == to_id:
        return jsonify({"status": False, "text": "Cannot transfer to yourself"})
    if amount > b1:
        return jsonify({"status": False, "text": f"Not enough money. Balance: {b1}"})

    now = datetime.now().strftime("%d/%m/%y %H:%M:%S")
    db_handler.insert_transaction(from_id, "Transfer", now, description, amount)
    db_handler.insert_transaction(to_id, "Transfer", now, description, amount)
    db_handler.update_balance(from_id, b1 - amount)
    db_handler.update_balance(to_id, b2 + amount)

    return jsonify({"status": True})

app.run(host="0.0.0.0", port=5000, debug=False)



