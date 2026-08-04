from flask import Flask, render_template, request, jsonify
from model_engine import train_and_predict

app = Flask(__name__)

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

@app.route("/")
def index():
    return render_template("index.html")

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
