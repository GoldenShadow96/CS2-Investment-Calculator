from flask import Flask, request, jsonify
from flask_cors import CORS
import json
import os
import numpy as np
from sklearn.cluster import KMeans
from collections import Counter
from datetime import datetime, timedelta
import inspect

app = Flask(__name__)
CORS(app)

DATA_FILE = 'transactions.json'
PRICE_FILE = 'markethistory.json'

# ----------------- TRANSAKCJE -----------------

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

# ----------------- ANALIZA LOKALNA -----------------

def _parse_dt(date_str: str):
    """Próbuje z ciągu 'Dec 05 2024 01: +0' zbudować obiekt datetime (ignoruje godzinę)."""
    try:
        return datetime.strptime(date_str[:11], "%b %d %Y")  # 'Dec 05 2024'
    except Exception:
        return None

@app.route('/analyze-local', methods=['GET'])
def analyze_local():
    """
    • current_price_raw        – ostatnia cena surowa
    • current_price_smoothed   – ostatnia cena po SMA‑3
    • current_state            – (bucketPrice, bucketDelta)  np.  P3_D4
    • centroids                – 5 środków klastrów (∆ po wygładzeniu)
    • delta_boundaries         – 6 granic (jak wcześniej)
    • price_boundaries         – kwantyle [0,20,40,60,80,100] (po wygładzeniu)
    • markov_chain             – macierz przejść 25 × 25
    • transition_counts / totals
    """
    # ------------------------ parametry & dane ------------------------------
    since_days = int(request.args.get('since_days', 730))
    SMA_WINDOW = 3                     #  <‑‑ lekkie wygładzenie

    if not os.path.exists(PRICE_FILE):
        return jsonify({'error': 'Brak pliku markethistory.json'}), 400

    with open(PRICE_FILE, 'r', encoding='utf-8') as f:
        try:
            data = json.load(f)
        except json.JSONDecodeError:
            return jsonify({'error': 'Nieprawidłowy JSON'}), 400

    if not data.get("success") or not data.get("prices"):
        return jsonify({'error': 'Brak danych lub niepoprawna struktura'}), 400

    # ------------------------ filtr po dacie jak dotąd ----------------------
    today  = datetime.now().date()
    cutoff = today - timedelta(days=since_days)
    filtered = [
        p for p in data["prices"]
        if (dt := _parse_dt(p[0])) and dt.date() >= cutoff
    ]

    if len(filtered) < 10:
        return jsonify({'error': f'Za mało danych z ostatnich {since_days} dni'}), 400

    prices_raw = np.array([float(p[1]) for p in filtered])
    if len(prices_raw) < SMA_WINDOW + 2:                 # musi starczyć na SMA + deltę
        return jsonify({'error': 'Za mało danych do analizy'}), 400

    # ------------------------ SMA‑3 wygładzenie -----------------------------
    #  np.convolve z maską ones / window
    kernel = np.ones(SMA_WINDOW) / SMA_WINDOW
    prices_smooth = np.convolve(prices_raw, kernel, mode='valid')  # długość N‑(W‑1)

    #  dopasuj indeksację aby ∆ miało tę samą długość co prices_smooth‑1
    deltas = np.diff(prices_smooth)

    # ------------------------ 5‑klastrowy K‑means na ∆ ----------------------
    X = deltas.reshape(-1, 1)
    if len(set(deltas)) >= 5:
        kmeans = KMeans(n_clusters=5, n_init=50, random_state=42).fit(X)
        centroids = sorted(float(c[0]) for c in kmeans.cluster_centers_)
    else:   # fallback: unikalne + zera
        centroids = sorted(list(set(deltas)) + [0] * (5 - len(set(deltas))))

    # granice ∆ pomiędzy centroidami (6 wartości)
    d0, d1, d2, d3, d4 = centroids
    delta_boundaries = [d0, (d0+d1)/2, (d1+d2)/2, (d2+d3)/2, (d3+d4)/2, d4]

    def delta_bucket(d):
        if d <=  delta_boundaries[0]: return 0  # S2
        if d <=  delta_boundaries[1]: return 1  # S1
        if d <=  delta_boundaries[2]: return 2  # F
        if d <=  delta_boundaries[3]: return 3  # W1
        return 4                               # W2

    # ------------------------ kwantylowe buckety ceny -----------------------
    #  5 przedziałów = 6 granic
    price_boundaries = np.percentile(prices_smooth, [0,20,40,60,80,100]).tolist()

    def price_bucket(p):
        # zwraca 0..4
        if p <= price_boundaries[1]: return 0
        if p <= price_boundaries[2]: return 1
        if p <= price_boundaries[3]: return 2
        if p <= price_boundaries[4]: return 3
        return 4

    # ------------------------ budowa sekwencji 25‑stanowej ------------------
    #  ciąg z indeksu SMA_WINDOW (bo tam zaczyna się prices_smooth)
    states = []
    for i in range(1, len(prices_smooth)):
        pb = price_bucket(prices_smooth[i-1])          # poziom z chwili t‑1
        db = delta_bucket(deltas[i-1])                 # zmiana t‑1 → t
        states.append(f"P{pb}_D{db}")                  # np. 'P3_D1'

    if not states:
        return jsonify({'error': 'Brak sekwencji stanów'}), 400

    # ------------------------ łańcuch Markowa (25 × 25) ---------------------
    price_labels  = [f"P{i}" for i in range(5)]
    delta_labels  = [f"D{i}" for i in range(5)]
    all_states    = [f"{p}_{d}" for p in price_labels for d in delta_labels]

    transition_pairs  = list(zip(states[:-1], states[1:]))
    transition_hist   = Counter(transition_pairs)
    transition_totals = Counter(a for a, _ in transition_pairs)

    # macierz prawdopodobieństw
    transitions = {s: {t: 0 for t in all_states} for s in all_states}
    for a, b in transition_pairs:
        transitions[a][b] += 1
    for s in all_states:
        total = sum(transitions[s].values())
        if total:
            for t in all_states:
                transitions[s][t] = round(transitions[s][t] / total, 3)

    # ------------------------ WYJŚCIE --------------------------------------
    return jsonify({
        "current_price_raw":      round(float(prices_raw[-1]), 4),
        "current_price_smoothed": round(float(prices_smooth[-1]), 4),
        "current_state":          states[-1],
        "centroids":              [round(c, 4) for c in centroids],
        "delta_boundaries":       [round(b, 4) for b in delta_boundaries],
        "price_boundaries":       [round(b, 4) for b in price_boundaries],
        "markov_chain":           transitions,
        "transition_counts":      {f"{a}→{b}": n for (a, b), n in transition_hist.items()},
        "transition_totals":      dict(transition_totals)
    })

@app.route('/update-history', methods=['POST'])
def update_history():
    try:
        content = request.json
        if not isinstance(content, dict) or 'success' not in content or 'prices' not in content:
            return jsonify({'error': 'Nieprawidłowy format danych'}), 400

        with open(PRICE_FILE, 'w', encoding='utf-8') as f:
            json.dump(content, f, indent=2, ensure_ascii=False)

        return jsonify({'status': 'saved'}), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/price-chart', methods=['GET'])
def price_chart():
    # --- 1. pobierz liczbę dni wstecz (domyślnie 730) -----------------
    since_days = int(request.args.get('since_days', 730))

    try:
        with open(PRICE_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
        prices_raw = data.get('prices', [])
        if not prices_raw:
            return jsonify({'error': 'Brak danych'}), 400

        # --- 2. filtruj rekordy po dacie tak samo jak w analyze_local --
        today = datetime.now().date()
        cutoff = today - timedelta(days=since_days)
        filtered = [
            p for p in prices_raw
            if (dt := _parse_dt(p[0])) and dt.date() >= cutoff
        ]

        if not filtered:
            return jsonify({'error': f'Brak danych z ostatnich {since_days} dni'}), 400

        # --- 3. buduj listy do wykresu --------------------------------
        labels = [p[0] for p in filtered]
        values = [float(p[1]) for p in filtered]

        return jsonify({'labels': labels, 'prices': values})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# ----------------- URUCHOMIENIE -----------------

if __name__ == '__main__':
    app.run(debug=False, use_reloader=True)
    print(inspect.getsource(server.analyze_local))