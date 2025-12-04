from flask import Flask, render_template, send_from_directory, abort, request
from datetime import datetime
import os
import json

import db_handler

frontend_path = os.path.abspath('../frontend')
app = Flask(__name__, template_folder=frontend_path)

users = {
    "12345": {
        "first_name": "ofek",
        "last_name": "matzki",
        "email": "ofek@gmail.com",
        "password": "Aa123!",
        "gender": "Male",
        "birth_date": "01/01/1970",
        "phone_number": "0524441154",
        "address": "aaaaaa tlv",
        "balance": 5000
    },
    "98765": {
        "first_name": "aaaaa",
        "last_name": "bbbb",
        "email": "kofe@gmail.com",
        "password": "Aa123!",
        "gender": "Male",
        "birth_date": "01/01/1970",
        "phone_number": "0524441154",
        "address": "aaaaaa tlv",
        "balance": 5000
    }
}

transactions = {

}


@app.route('/')
def login_page():
    return render_template('src/login.html')


@app.route('/style/styles.css')
def get_style_file():
    return send_from_directory(f'{frontend_path}/style', 'styles.css')


@app.route('/images/bank.jpg')
def get_bank_image():
    return send_from_directory(f'{frontend_path}/images', 'bank.jpg')


@app.route('/page/<path:page_name>')
def get_page_name(page_name):
    if os.path.exists(f'{frontend_path}/src/{page_name}.html'):
        return render_template(f'src/{page_name}.html')
    else:
        return abort(404)


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
    print(type(user_id))
    response["status"] = db_handler.insert_user(user_id, firstName, lastName, email, password, gender, birth_date,
                                                phone_number, address, 5000)

    if response["status"] == False:
        response["text"] = "There already a registered user wth this user id"

    return json.dumps(response)


@app.route('/api/withdraw', methods=['POST'])
def handle_withdraw():
    global users
    global transactions

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
        db_handler.insert_transaction(user_id, "Withdrawal", datetime.now().strftime("%d/%m/%y %H:%M:%S"), description, amount)

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
    global users
    global transactions

    data = request.json
    from_id = data.get("from_id")
    to_id = data.get("to_id")
    person_name = data.get("person_name")
    amount = float(data.get('amount'))
    description = data.get("description")

    response = {
        "status": False,
        "text": "",
    }

    resul1 = db_handler.get_user_balance(from_id)
    resul2 = db_handler.get_user_balance(to_id)

    if resul1 is None or resul2 is None:
        response["text"] = "There isn't a registered user wth the user ids"
    # elif f'{users[to_id]["first_name"]} {users[to_id]["last_name"]}' != person_name:
    #     response["text"] = "The person name is not correct"
    elif from_id == to_id:
        response["text"] = "You cannot transfer to yourself"
    elif amount > resul1:
        response["text"] = f"There isn't enough money in the account. You only have {resul1}"
    else:
        db_handler.insert_transaction(from_id, "Transfer", datetime.now().strftime("%d/%m/%y %H:%M:%S"), description,
                                      amount)
        db_handler.insert_transaction(to_id, "Transfer", datetime.now().strftime("%d/%m/%y %H:%M:%S"), description,
                                      amount)

        db_handler.update_balance(from_id, resul1 - amount)
        db_handler.update_balance(to_id, resul2 + amount)
        response["status"] = True

    return json.dumps(response)


app.run(debug=True)
