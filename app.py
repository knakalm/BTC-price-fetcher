import base64
import hashlib
import hmac
import json
import os
from datetime import datetime, timezone

import boto3 as boto3
import requests
from flask import Flask, jsonify, request
from flask_cognito import cognito_auth_required, CognitoAuth
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import func, extract
import psycopg2

from apscheduler.schedulers.background import BackgroundScheduler

app = Flask(__name__)
app.app_context().push()
app.config['COGNITO_USERPOOL_ID'] = os.environ.get('COGNITO_USERPOOL_ID', None)
app.config['COGNITO_CLIENT_ID'] = os.environ.get('CLIENT_ID', None)
app.config['COGNITO_CLIENT_SECRET'] = os.environ.get('CLIENT_SECRET', None)
app.config['COGNITO_DOMAIN'] = os.environ.get('COGNITO_DOMAIN', None)
app.config['COGNITO_REGION'] = os.environ.get('COGNITO_REGION', None)

cognito = CognitoAuth(app)

# Database Configuration (User-specific)
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('SQLALCHEMY_DATABASE_URI', None)
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)


class BtcPrice(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    price_eur = db.Column(db.Float, nullable=False)
    price_czk = db.Column(db.Float, nullable=False)
    timestamp = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)


# Create the tables
with app.app_context():
    db.create_all()


# Function to fetch BTC price
def fetch_btc_price():
    endpoint = "https://api.coingecko.com/api/v3/simple/price"
    params = {
        'ids': 'bitcoin',
        'vs_currencies': 'eur,czk'
    }

    response = requests.get(endpoint, params=params)
    data = response.json()

    btc_prices = {
        'eur': {
            'price_per_btc': data['bitcoin']['eur'],
            'currency': 'EUR'
        },
        'czk': {
            'price_per_btc': data['bitcoin']['czk'],
            'currency': 'CZK'
        }
    }

    client_request_time = datetime.now(timezone.utc).isoformat()

    result = {
        'client_request_time': client_request_time,
        'btc_prices': btc_prices
    }

    return result if response.status_code == 200 else None


# Function to store BTC price in the database
def store_btc_price():
    price = fetch_btc_price()
    if price is not None:
        btc_price_record = BtcPrice(price_eur=price['btc_prices']['eur']['price_per_btc'],
                                    price_czk=price['btc_prices']['czk']['price_per_btc'],
                                    timestamp=price['client_request_time'])
        with app.app_context():
            db.session.add(btc_price_record)
            db.session.commit()
    return price


# Schedule to run store_btc_price every 5 minutes
with app.app_context():
    scheduler = BackgroundScheduler()
    scheduler.add_job(store_btc_price, 'interval', minutes=5)
    scheduler.start()


@app.route('/get_btc_price', methods=['GET'])
@cognito_auth_required
def get_btc_price():
    result = store_btc_price()  # Store the price in the database on each call

    return jsonify(result)


@app.route('/get_averages', methods=['GET'])
@cognito_auth_required
def get_averages():
    # Replace with your own logic to calculate averages from local data
    daily_average = calculate_daily_average()
    monthly_average = calculate_monthly_average()

    server_data_time = datetime.now(timezone.utc).isoformat()

    averages = {
        'server_data_time': server_data_time,
    }
    averages |= daily_average
    averages |= monthly_average

    return jsonify(averages)


@app.route('/callback', methods=['GET'])
def callback():
    return jsonify({'response': 'get id_token from URL'})


def get_secret_hash(username, client_id, client_secret):
    message = username + client_id
    dig = hmac.new(str(client_secret).encode('utf-8'),
                   msg=message.encode('utf-8'),
                   digestmod=hashlib.sha256).digest()
    return base64.b64encode(dig).decode()


@app.route('/get_token', methods=['POST'])
def get_token():
    username = request.json.get('username')
    password = request.json.get('password')
    client_id = app.config['COGNITO_CLIENT_ID']
    client_secret = app.config['COGNITO_CLIENT_SECRET']

    if not username or not password:
        return jsonify({"error": "username and password are required"}), 400

    secret_hash = get_secret_hash(username, client_id, client_secret)

    client = boto3.client('cognito-idp')

    try:
        response = client.initiate_auth(
            ClientId=client_id,
            AuthFlow='USER_PASSWORD_AUTH',
            AuthParameters={
                'USERNAME': username,
                'PASSWORD': password,
                'SECRET_HASH': secret_hash
            }
        )
        return jsonify({"id_token": response['AuthenticationResult']['IdToken']})
    except client.exceptions.NotAuthorizedException:
        return jsonify({"error": "The username or password is incorrect"}), 401
    except Exception as e:
        return jsonify({"error": str(e)}), 500


def calculate_daily_average():
    # Get today's date
    today = datetime.utcnow().date()

    # Fetch all records for today
    today_records = BtcPrice.query.filter(
        func.date(BtcPrice.timestamp) == today
    ).all()

    # Calculate averages manually
    total_eur = sum(record.price_eur for record in today_records)
    total_czk = sum(record.price_czk for record in today_records)
    count = len(today_records)

    avg_eur = total_eur / count if count > 0 else 0
    avg_czk = total_czk / count if count > 0 else 0

    # Return JSON format
    return {
        'daily_average': {
            'EUR': avg_eur,
            'CZK': avg_czk
        }
    }

def calculate_monthly_average():
    # Get current month and year
    current_month = datetime.utcnow().month
    current_year = datetime.utcnow().year

    # Fetch all records for the current month
    monthly_records = BtcPrice.query.filter(
        extract('month', BtcPrice.timestamp) == current_month,
        extract('year', BtcPrice.timestamp) == current_year
    ).all()

    # Calculate averages manually
    total_eur = sum(record.price_eur for record in monthly_records)
    total_czk = sum(record.price_czk for record in monthly_records)
    count = len(monthly_records)

    avg_eur = total_eur / count if count > 0 else 0
    avg_czk = total_czk / count if count > 0 else 0

    # Return JSON format
    return {
        'monthly_average': {
            'EUR': avg_eur,
            'CZK': avg_czk
        }
    }


if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
