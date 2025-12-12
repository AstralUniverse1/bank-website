from flask import Flask, render_template, send_from_directory, abort, request
from datetime import datetime
import os
import json

import db_handler


# FRONTEND ROOT
FRONTEND_ROOT = '/app/frontend'

app = Flask(
    __name__,
    template_folder=FRONTEND_ROOT,       # so render_template('src/login.html') works
    static_folder=f"{FRONTEND_ROOT}/static"  # your CSS folder
)


# ----------------- FRONTEND ROUTES -----------------

@app.route('/')
def login_page():
    return render_template('src/login.html')

# Serve ANY file inside /app/frontend (HTML, images, etc.)
@app.route('/<path:path>')
def serve_frontend(path):
    full_path = os.path.join(FRONTEND_ROOT, path)
    if os.path.exists(full_path):
        # path like: src/register.html, images/bank.jpg
        directory = os.path.dirname(full_path)
        filename = os.path.basename(full_path)
        return send_from_directory(directory, filename)
    return abort(404)


# ----------------- API ROUTES (unchanged) -----------------

@app.route('/api/login', methods=['POST'])
def is_valid_user():
    data = request.json
    user_id = data.get('user_id')
    user_password = data.get('password')

    response = {
        "status": False,
        "text": ""
    }

    response["status"] = db_handler.check_user_credentials(user_id, user_password)
    if not response["status"]:
        response["text"] = "Please fill the correct credentials"

    return json.dumps(response)


@app.route('/api/register', methods=['POST'])
def register_user():
    data = request.json
    user_id = data.get('user_id')
    firstName = data.get("firstName")
    lastName = data.get("lastName")
    email = data.get("email")
    password = data.get("password")
    gender = data.get("gender")
    birth_date = data.get("birth_date")
    phone_number = data.get("phone_number")
    address = data.get("address")

    response = {
        "status": False,
        "text": ""
    }

    response["status"] = db_handler.insert_user(
        user_id, firstName, lastName, email, password,
        gender, birth_date, phone_number, address, 5000
    )

    if not response["status"]:
        response["text"] = "There already a registered user wth this user id"

    return json.dumps(response)


@app.route('/api/withdraw', methods=['POST'])
def handle_withdraw():
    data = request.json
    user_id = data.get('user_id')
    amount = data.get('amount')
    description = data.get("description")

    response = {
        "status": False,
        "text": "",
        "balance": 0,
        "transactions": []
    }

    result = db_handler.get_user_balance(user_id)

    if result is None:
        response["text"] = "There isn't a registered user wth this user id"
    elif amount > result:
        response["text"] = f"There isn't enough money in the account. You only have {result}"
    else:
        db_handler.insert_transaction(
            user_id, "Withdrawal",
            datetime.now().strftime("%d/%m/%y %H:%M:%S"), description, amount
        )
        db_handler.update_balance(user_id, result - amount)

        response["status"] = True
        response["balance"] = result - amount
        response["transactions"] = db_handler.get_user_last_transactions(user_id)

    return json.dumps(response)


@app.route('/api/get_user_data', methods=['POST'])
def get_user_data():
    data = request.json
    user_id = data.get('user_id')

    response = {
        "status": False,
        "text": "",
        "balance": 0,
        "transactions": []
    }

    result = db_handler.get_user_balance(user_id)

    if result is None:
        response["text"] = "There isn't a registered user wth this user id"
    else:
        response["status"] = True
        response["balance"] = result
        response["transactions"] = db_handler.get_user_last_transactions(user_id)

    return json.dumps(response)


@app.route('/api/transfer', methods=['POST'])
def handle_transfer():
    data = request.json
    from_id = data.get("from_id")
    to_id = data.get("to_id")
    amount = float(data.get('amount'))
    description = data.get("description")

    response = {
        "status": False,
        "text": "",
    }

    result1 = db_handler.get_user_balance(from_id)
    result2 = db_handler.get_user_balance(to_id)

    if result1 is None or result2 is None:
        response["text"] = "There isn't a registered user wth the user ids"
    elif from_id == to_id:
        response["text"] = "You cannot transfer to yourself"
    elif amount > result1:
        response["text"] = f"There isn't enough money in the account. You only have {result1}"
    else:
        db_handler.insert_transaction(
            from_id, "Transfer",
            datetime.now().strftime("%d/%m/%y %H:%M:%S"), description, amount
        )
        db_handler.insert_transaction(
            to_id, "Transfer",
            datetime.now().strftime("%d/%m/%y %H:%M:%S"), description, amount
        )

        db_handler.update_balance(from_id, result1 - amount)
        db_handler.update_balance(to_id, result2 + amount)

        response["status"] = True

    return json.dumps(response)


app.run(host="0.0.0.0", port=5000, debug=False)

