from flask import Flask, request, jsonify
from flask_cors import CORS
import json
import os

app = Flask(__name__)
CORS(app)

DATA_FILE = 'transactions.json'

def load_data():
    if not os.path.exists(DATA_FILE):
        return []
    with open(DATA_FILE, 'r', encoding='utf-8') as f:
        try:
            return json.load(f)
        except json.JSONDecodeError:
            return []

def save_data(data):
    with open(DATA_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

@app.route('/transactions', methods=['GET'])
def get_transactions():
    return jsonify(load_data())

@app.route('/transactions', methods=['POST'])
def add_transaction():
    data = request.json
    transactions = load_data()
    transactions.append(data)
    save_data(transactions)
    return jsonify({'status': 'success'}), 201

@app.route('/transactions/<int:index>', methods=['DELETE'])
def delete_transaction(index):
    transactions = load_data()
    if 0 <= index < len(transactions):
        transactions.pop(index)
        save_data(transactions)
        return jsonify({'status': 'deleted'})
    return jsonify({'error': 'Index out of range'}), 400

@app.route('/transactions/<int:index>', methods=['PATCH'])
def update_transaction(index):
    updated_data = request.json
    transactions = load_data()
    if 0 <= index < len(transactions):
        transactions[index].update(updated_data)
        save_data(transactions)
        return jsonify({'status': 'updated'})
    return jsonify({'error': 'Index out of range'}), 400

if __name__ == '__main__':
    app.run(debug=True)
