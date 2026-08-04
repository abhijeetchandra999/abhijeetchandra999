import os
from flask import Flask, render_template, render_template_string, request, jsonify
from model_engine import train_and_predict

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# Configure template folder explicitly
template_dir = os.path.join(BASE_DIR, 'templates')

app = Flask(__name__, template_folder=template_dir)

POPULAR_STOCKS = [
    {"symbol": "GILLETTE.NS", "name": "Gillette India", "market": "NSE (India)"},
    {"symbol": "RELIANCE.NS", "name": "Reliance Industries", "market": "NSE (India)"},
    {"symbol": "TCS.NS", "name": "Tata Consultancy Services", "market": "NSE (India)"},
    {"symbol": "INFY.NS", "name": "Infosys", "market": "NSE (India)"},
    {"symbol": "HDFCBANK.NS", "name": "HDFC Bank", "market": "NSE (India)"},
    {"symbol": "AAPL", "name": "Apple Inc.", "market": "NASDAQ (US)"},
    {"symbol": "NVDA", "name": "NVIDIA Corp.", "market": "NASDAQ (US)"},
    {"symbol": "TSLA", "name": "Tesla Inc.", "market": "NASDAQ (US)"},
    {"symbol": "MSFT", "name": "Microsoft Corp.", "market": "NASDAQ (US)"},
    {"symbol": "GOOGL", "name": "Alphabet Inc.", "market": "NASDAQ (US)"}
]

def load_template_content():
    possible_paths = [
        os.path.join(BASE_DIR, 'templates', 'index.html'),
        os.path.join(BASE_DIR, 'index.html')
    ]
    for p in possible_paths:
        if os.path.exists(p):
            with open(p, 'r', encoding='utf-8') as f:
                return f.read()
    return None

@app.route("/")
def index():
    try:
        return render_template("index.html")
    except Exception:
        html_content = load_template_content()
        if html_content:
            return render_template_string(html_content)
        return "<h3>Stock Prediction AI Web Dashboard is active. API Endpoint: /api/predict</h3>", 200

@app.route("/api/popular", methods=["GET"])
def get_popular_stocks():
    return jsonify(POPULAR_STOCKS)

@app.route("/api/predict", methods=["GET"])
def predict():
    ticker = request.args.get("ticker", "GILLETTE.NS").strip().upper()
    target_date = request.args.get("date", None)
    
    if not ticker:
        return jsonify({"error": "Ticker symbol is required."}), 400
        
    try:
        result = train_and_predict(ticker, target_date_str=target_date)
        return jsonify(result)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
