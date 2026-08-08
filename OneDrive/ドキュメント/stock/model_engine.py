import yfinance as yf
import pandas as pd
import numpy as np
import requests
import time
from datetime import datetime, timedelta
from sklearn.preprocessing import StandardScaler
from sklearn.ensemble import RandomForestRegressor, GradientBoostingRegressor
from sklearn.linear_model import Ridge
from sklearn.metrics import mean_squared_error, mean_absolute_error, r2_score

try:
    from xgboost import XGBRegressor
    HAS_XGBOOST = True
except ImportError:
    HAS_XGBOOST = False

# Simple in-memory cache to prevent hitting Yahoo Finance rate limits
DATA_CACHE = {}
CACHE_TTL_SECONDS = 300  # 5 minutes cache

def fetch_direct_yahoo_chart(ticker, range_str="3y", interval_str="1d"):
    """Directly fetch stock data from Yahoo Finance v8 chart JSON API as fail-safe fallback."""
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.9',
    }
    urls = [
        f"https://query1.finance.yahoo.com/v8/finance/chart/{ticker}?range={range_str}&interval={interval_str}",
        f"https://query2.finance.yahoo.com/v8/finance/chart/{ticker}?range={range_str}&interval={interval_str}"
    ]
    for url in urls:
        try:
            resp = requests.get(url, headers=headers, timeout=8)
            if resp.status_code == 200:
                data = resp.json()
                if 'chart' in data and data['chart'].get('result'):
                    result = data['chart']['result'][0]
                    timestamps = result.get('timestamp', [])
                    quote = result['indicators']['quote'][0]
                    
                    df = pd.DataFrame({
                        'Date': pd.to_datetime(timestamps, unit='s'),
                        'Open': quote.get('open'),
                        'High': quote.get('high'),
                        'Low': quote.get('low'),
                        'Close': quote.get('close'),
                        'Volume': quote.get('volume', 0)
                    }).dropna(subset=['Close'])
                    
                    if not df.empty:
                        meta = result.get('meta', {})
                        info = {
                            "shortName": meta.get('shortName') or meta.get('symbol') or ticker,
                            "longName": meta.get('longName') or meta.get('shortName') or ticker,
                            "symbol": ticker,
                            "currency": meta.get('currency', 'INR' if ticker.endswith('.NS') else 'USD')
                        }
                        return df, info
        except Exception:
            continue
    return pd.DataFrame(), {}

def fetch_stock_data(ticker, period="3y", interval="1d"):
    """Fetch historical stock data using yfinance with direct API fallbacks and caching."""
    cache_key = f"{ticker}_{period}_{interval}"
    now = time.time()
    
    if cache_key in DATA_CACHE:
        cached_df, cached_info, cached_time = DATA_CACHE[cache_key]
        if now - cached_time < CACHE_TTL_SECONDS:
            return cached_df.copy(), cached_info

    df = pd.DataFrame()
    info = {}

    # Method 1: yfinance Ticker
    try:
        stock = yf.Ticker(ticker)
        df = stock.history(period=period, interval=interval)
        if not df.empty:
            try:
                info = stock.info or {}
            except Exception:
                info = {"shortName": ticker, "longName": ticker, "symbol": ticker}
    except Exception:
        df = pd.DataFrame()

    # Method 2: yfinance download
    if df.empty:
        try:
            df = yf.download(ticker, period=period, interval=interval, auto_adjust=True)
        except Exception:
            df = pd.DataFrame()

    # Method 3: Direct Yahoo Finance v8 chart API (Failsafe for cloud hosts / Render)
    if df.empty:
        df, info = fetch_direct_yahoo_chart(ticker, range_str=period, interval_str=interval)

    if df.empty:
        raise ValueError(f"No stock data found for '{ticker}'. Yahoo Finance server is temporarily unreachable. Please try again.")

    # Flatten multi-index columns if present
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = [col[0] for col in df.columns]

    df = df.reset_index()
    if 'Date' not in df.columns and 'Datetime' in df.columns:
        df.rename(columns={'Datetime': 'Date'}, inplace=True)
    
    # Ensure Date column is datetime
    df['Date'] = pd.to_datetime(df['Date'])
    df = df.sort_values('Date').reset_index(drop=True)

    if not info:
        info = {"shortName": ticker, "longName": ticker, "symbol": ticker}

    DATA_CACHE[cache_key] = (df.copy(), info, now)
    return df, info



def compute_technical_indicators(df):
    """Compute comprehensive technical analysis indicators for stock prediction."""
    data = df.copy()
    
    # Basic Price features
    data['Return'] = data['Close'].pct_change()
    data['Log_Volume'] = np.log1p(data['Volume'])
    
    # Moving Averages
    data['SMA_10'] = data['Close'].rolling(window=10).mean()
    data['SMA_20'] = data['Close'].rolling(window=20).mean()
    data['SMA_50'] = data['Close'].rolling(window=50).mean()
    data['EMA_12'] = data['Close'].ewm(span=12, adjust=False).mean()
    data['EMA_26'] = data['Close'].ewm(span=26, adjust=False).mean()
    
    # MACD
    data['MACD'] = data['EMA_12'] - data['EMA_26']
    data['MACD_Signal'] = data['MACD'].ewm(span=9, adjust=False).mean()
    data['MACD_Hist'] = data['MACD'] - data['MACD_Signal']
    
    # RSI (14-period)
    delta = data['Close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
    rs = gain / (loss + 1e-9)
    data['RSI'] = 100 - (100 / (1 + rs))
    
    # Bollinger Bands (20-period)
    data['BB_Middle'] = data['SMA_20']
    bb_std = data['Close'].rolling(window=20).std()
    data['BB_Upper'] = data['BB_Middle'] + (bb_std * 2)
    data['BB_Lower'] = data['BB_Middle'] - (bb_std * 2)
    data['BB_Width'] = (data['BB_Upper'] - data['BB_Lower']) / (data['BB_Middle'] + 1e-9)
    
    # ATR (14-period Average True Range)
    high_low = data['High'] - data['Low']
    high_close = np.abs(data['High'] - data['Close'].shift(1))
    low_close = np.abs(data['Low'] - data['Close'].shift(1))
    tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
    data['ATR'] = tr.rolling(window=14).mean()
    
    # Volume SMA Ratio
    data['Vol_SMA_20'] = data['Volume'].rolling(window=20).mean()
    data['Vol_Ratio'] = data['Volume'] / (data['Vol_SMA_20'] + 1e-9)
    
    # Cyclical Date Features
    data['Month'] = data['Date'].dt.month
    data['DayOfWeek'] = data['Date'].dt.dayofweek
    data['Month_sin'] = np.sin(2 * np.pi * data['Month'] / 12)
    data['Month_cos'] = np.cos(2 * np.pi * data['Month'] / 12)
    data['Day_sin'] = np.sin(2 * np.pi * data['DayOfWeek'] / 7)
    data['Day_cos'] = np.cos(2 * np.pi * data['DayOfWeek'] / 7)
    
    # Lag Features
    for lag in [1, 2, 3, 5]:
        data[f'Lag_{lag}_Close'] = data['Close'].shift(lag)
        data[f'Lag_{lag}_Return'] = data['Return'].shift(lag)
    
    # Targets for next day
    data['Target_Close'] = data['Close'].shift(-1)
    data['Target_High'] = data['High'].shift(-1)
    data['Target_Low'] = data['Low'].shift(-1)
    data['Target_Direction'] = (data['Target_Close'] > data['Close']).astype(int)
    
    return data

def analyze_news_sentiment(stock, ticker):
    """Fetch live news from yfinance and analyze news sentiment using financial lexicon scoring."""
    raw_news = []
    try:
        raw_news = stock.news or []
    except Exception:
        raw_news = []

    pos_words = {
        'surge', 'gain', 'gains', 'profit', 'profits', 'growth', 'record', 'beat', 'beats', 'rally',
        'upgrade', 'upgraded', 'high', 'higher', 'expansion', 'strong', 'boom', 'rise', 'rises',
        'optimistic', 'dividend', 'buy', 'outperform', 'bullish', 'soar', 'soars', 'jump', 'jumps',
        'revenue', 'success', 'positive', 'breakthrough', 'partner', 'partnership', 'acquisition'
    }
    neg_words = {
        'fall', 'falls', 'loss', 'losses', 'drop', 'drops', 'decline', 'declines', 'crash', 'crashes',
        'lawsuit', 'deficit', 'warning', 'downgrade', 'downgraded', 'plunge', 'plunges', 'cut', 'cuts',
        'risk', 'risks', 'fear', 'fears', 'inquiry', 'default', 'penalty', 'slump', 'debt', 'lower',
        'bearish', 'weak', 'struggle', 'struggles', 'investigation', 'layoff', 'layoffs', 'ban'
    }

    processed_news = []
    total_score = 0.0

    for item in raw_news:
        title = ""
        publisher = ""
        link = "#"
        pub_time = "Recent"

        if isinstance(item, dict):
            content = item.get('content', item) if isinstance(item.get('content'), dict) else item
            title = content.get('title', '')
            publisher = content.get('provider', {}).get('displayName') if isinstance(content.get('provider'), dict) else content.get('publisher', 'Financial News')
            pub_time_val = content.get('pubDate') or content.get('providerPublishTime')
            if pub_time_val:
                try:
                    if isinstance(pub_time_val, (int, float)):
                        pub_time = datetime.fromtimestamp(pub_time_val).strftime('%Y-%m-%d %H:%M')
                    else:
                        pub_time = str(pub_time_val)[:16].replace('T', ' ')
                except Exception:
                    pub_time = "Recent"
            
            canonical_url = content.get('canonicalUrl') or content.get('clickThroughUrl')
            if isinstance(canonical_url, dict):
                link = canonical_url.get('url', '#')
            elif isinstance(canonical_url, str):
                link = canonical_url
            else:
                link = item.get('link', '#')

        if not title:
            continue

        words = [w.strip(".,!?\"'()[]").lower() for w in title.split()]
        pos_count = sum(1 for w in words if w in pos_words)
        neg_count = sum(1 for w in words if w in neg_words)

        if pos_count > neg_count:
            sentiment = "BULLISH"
            sentiment_color = "emerald"
            score = 1.0
        elif neg_count > pos_count:
            sentiment = "BEARISH"
            sentiment_color = "rose"
            score = -1.0
        else:
            sentiment = "NEUTRAL"
            sentiment_color = "slate"
            score = 0.0

        total_score += score
        processed_news.append({
            "title": title,
            "publisher": publisher or "Financial News",
            "pub_time": pub_time,
            "link": link,
            "sentiment": sentiment,
            "sentiment_color": sentiment_color
        })

    news_count = len(processed_news)
    if news_count > 0:
        avg_score = total_score / news_count
        bullish_pct = round(sum(1 for n in processed_news if n['sentiment'] == 'BULLISH') / news_count * 100, 1)
        bearish_pct = round(sum(1 for n in processed_news if n['sentiment'] == 'BEARISH') / news_count * 100, 1)
        neutral_pct = round(100 - bullish_pct - bearish_pct, 1)
    else:
        avg_score = 0.0
        bullish_pct, bearish_pct, neutral_pct = 33.3, 33.3, 33.4

    if avg_score > 0.2:
        overall_news_sentiment = "BULLISH"
        overall_news_color = "emerald"
    elif avg_score < -0.2:
        overall_news_sentiment = "BEARISH"
        overall_news_color = "rose"
    else:
        overall_news_sentiment = "NEUTRAL"
        overall_news_color = "amber"

    return {
        "overall_sentiment": overall_news_sentiment,
        "overall_color": overall_news_color,
        "sentiment_score": round(avg_score, 2),
        "bullish_pct": bullish_pct,
        "bearish_pct": bearish_pct,
        "neutral_pct": neutral_pct,
        "articles": processed_news[:6]
    }

def train_and_predict(ticker, target_date_str=None):
    """
    Main function to load stock data, perform feature engineering, train an ensemble model,
    and generate predictions for the target date along with full analytics.
    """
    df, info = fetch_stock_data(ticker, period="3y")
    data = compute_technical_indicators(df)
    
    feature_cols = [
        'Close', 'High', 'Low', 'Volume', 'Return', 'Log_Volume',
        'SMA_10', 'SMA_20', 'SMA_50', 'EMA_12', 'EMA_26',
        'MACD', 'MACD_Signal', 'MACD_Hist', 'RSI',
        'BB_Upper', 'BB_Lower', 'BB_Width', 'ATR', 'Vol_Ratio',
        'Month_sin', 'Month_cos', 'Day_sin', 'Day_cos',
        'Lag_1_Close', 'Lag_1_Return', 'Lag_2_Close', 'Lag_2_Return',
        'Lag_3_Close', 'Lag_3_Return', 'Lag_5_Close', 'Lag_5_Return'
    ]
    
    # Clean rows for training (drop NaN values)
    clean_df = data.dropna(subset=feature_cols + ['Target_Close', 'Target_High', 'Target_Low']).copy()
    
    if len(clean_df) < 100:
        raise ValueError(f"Insufficient historical data for {ticker} to build ML model.")

    X = clean_df[feature_cols]
    y_close = clean_df['Target_Close']
    y_high = clean_df['Target_High']
    y_low = clean_df['Target_Low']
    
    # Time-series split (Chronological: 85% train, 15% test - NO DATA LEAKAGE)
    split_idx = int(len(X) * 0.85)
    X_train, X_test = X.iloc[:split_idx], X.iloc[split_idx:]
    y_train_close, y_test_close = y_close.iloc[:split_idx], y_close.iloc[split_idx:]
    y_train_high, y_test_high = y_high.iloc[:split_idx], y_high.iloc[split_idx:]
    y_train_low, y_test_low = y_low.iloc[:split_idx], y_low.iloc[split_idx:]
    
    # Standardize features
    scaler = StandardScaler()
    X_train_scaled = scaler.fit_transform(X_train)
    X_test_scaled = scaler.transform(X_test)
    
    # Model Setup (Ensemble: XGBoost + GradientBoosting)
    if HAS_XGBOOST:
        model_close = XGBRegressor(n_estimators=150, learning_rate=0.03, max_depth=4, random_state=42)
        model_high = XGBRegressor(n_estimators=150, learning_rate=0.03, max_depth=4, random_state=42)
        model_low = XGBRegressor(n_estimators=150, learning_rate=0.03, max_depth=4, random_state=42)
    else:
        model_close = GradientBoostingRegressor(n_estimators=150, learning_rate=0.03, max_depth=4, random_state=42)
        model_high = GradientBoostingRegressor(n_estimators=150, learning_rate=0.03, max_depth=4, random_state=42)
        model_low = GradientBoostingRegressor(n_estimators=150, learning_rate=0.03, max_depth=4, random_state=42)
        
    model_close.fit(X_train_scaled, y_train_close)
    model_high.fit(X_train_scaled, y_train_high)
    model_low.fit(X_train_scaled, y_train_low)
    
    # Test evaluation metrics
    preds_test_close = model_close.predict(X_test_scaled)
    mae = float(mean_absolute_error(y_test_close, preds_test_close))
    rmse = float(np.sqrt(mean_squared_error(y_test_close, preds_test_close)))
    r2 = float(r2_score(y_test_close, preds_test_close))
    
    # Directional accuracy
    actual_dir = (y_test_close.values > X_test['Close'].values)
    pred_dir = (preds_test_close > X_test['Close'].values)
    directional_accuracy = float(np.mean(actual_dir == pred_dir) * 100)
    
    # Latest Feature Vector (for Next Trading Day Prediction)
    latest_row = data.dropna(subset=feature_cols).iloc[-1]
    latest_features = latest_row[feature_cols].values.reshape(1, -1)
    latest_scaled = scaler.transform(latest_features)
    
    pred_next_close = float(model_close.predict(latest_scaled)[0])
    pred_next_high = float(model_high.predict(latest_scaled)[0])
    pred_next_low = float(model_low.predict(latest_scaled)[0])
    
    # Ensure logical price consistency (Low <= Close <= High)
    current_close = float(latest_row['Close'])
    pred_next_high = max(pred_next_high, pred_next_close, current_close)
    pred_next_low = min(pred_next_low, pred_next_close, current_close)
    
    expected_change = float(pred_next_close - current_close)
    expected_change_pct = float((expected_change / current_close) * 100)
    
    # Technical Signal Determination
    rsi_val = float(latest_row['RSI']) if not np.isnan(latest_row['RSI']) else 50.0
    if expected_change_pct > 1.2 and rsi_val < 70:
        tech_signal = "STRONG BUY"
        tech_score = 1.0
    elif expected_change_pct > 0.3:
        tech_signal = "BUY"
        tech_score = 0.5
    elif expected_change_pct < -1.2 and rsi_val > 30:
        tech_signal = "STRONG SELL"
        tech_score = -1.0
    elif expected_change_pct < -0.3:
        tech_signal = "SELL"
        tech_score = -0.5
    else:
        tech_signal = "NEUTRAL / HOLD"
        tech_score = 0.0

    # News & Sentiment Analysis
    stock_obj = yf.Ticker(ticker)
    news_analysis = analyze_news_sentiment(stock_obj, ticker)
    news_score = news_analysis['sentiment_score']  # Range: -1.0 to +1.0

    # Multi-Factor Synthesis AI Recommendation (60% Technical ML + 40% News Sentiment)
    combined_score = (0.6 * tech_score) + (0.4 * news_score)

    if combined_score >= 0.4:
        ai_recommendation = "STRONG BUY"
        ai_color = "emerald"
    elif combined_score >= 0.15:
        ai_recommendation = "BUY"
        ai_color = "green"
    elif combined_score <= -0.4:
        ai_recommendation = "STRONG SELL"
        ai_color = "rose"
    elif combined_score <= -0.15:
        ai_recommendation = "SELL"
        ai_color = "amber"
    else:
        ai_recommendation = "NEUTRAL / HOLD"
        ai_color = "slate"

    # Dynamic AI Reasoning Synthesis
    reasons = []
    reasons.append(f"Historical ML ensemble predicts a {expected_change_pct:+.2f}% price movement for next trading session.")
    if rsi_val > 70:
        reasons.append(f"RSI indicator is at {rsi_val:.1f} (Overbought zone - exercise caution).")
    elif rsi_val < 30:
        reasons.append(f"RSI indicator is at {rsi_val:.1f} (Oversold zone - potential bounce).")
    else:
        reasons.append(f"RSI is neutral at {rsi_val:.1f}.")

    if news_analysis['articles']:
        reasons.append(f"Market news sentiment is currently {news_analysis['overall_sentiment']} based on {len(news_analysis['articles'])} recent headlines.")
    else:
        reasons.append("No recent high-impact market news found; decision relies primarily on historical technical momentum.")

    ai_reasoning_summary = " ".join(reasons)

    # Prepare Historical Chart Series (last 180 trading days)
    recent_data = data.iloc[-180:].copy()
    chart_series = []
    for _, row in recent_data.iterrows():
        chart_series.append({
            "date": row['Date'].strftime('%Y-%m-%d'),
            "open": float(row['Open']) if not np.isnan(row['Open']) else None,
            "high": float(row['High']) if not np.isnan(row['High']) else None,
            "low": float(row['Low']) if not np.isnan(row['Low']) else None,
            "close": float(row['Close']) if not np.isnan(row['Close']) else None,
            "volume": float(row['Volume']) if not np.isnan(row['Volume']) else None,
            "sma_20": float(row['SMA_20']) if not np.isnan(row['SMA_20']) else None,
            "sma_50": float(row['SMA_50']) if not np.isnan(row['SMA_50']) else None,
            "rsi": float(row['RSI']) if not np.isnan(row['RSI']) else None,
            "macd": float(row['MACD']) if not np.isnan(row['MACD']) else None,
            "bb_upper": float(row['BB_Upper']) if not np.isnan(row['BB_Upper']) else None,
            "bb_lower": float(row['BB_Lower']) if not np.isnan(row['BB_Lower']) else None,
        })
        
    # Append Next Trading Day Prediction to chart
    last_date = recent_data['Date'].iloc[-1]
    next_date = last_date + timedelta(days=1)
    if next_date.weekday() >= 5:  # Weekend shift
        next_date += timedelta(days=(7 - next_date.weekday()))

    # Intraday Pivot Points & Trade Setup Calculations
    latest_high = float(latest_row['High']) if not np.isnan(latest_row['High']) else current_close * 1.01
    latest_low = float(latest_row['Low']) if not np.isnan(latest_row['Low']) else current_close * 0.99
    atr_val = float(latest_row['ATR']) if not np.isnan(latest_row['ATR']) and float(latest_row['ATR']) > 0 else (latest_high - latest_low)

    pivot = (latest_high + latest_low + current_close) / 3.0
    r1 = (2.0 * pivot) - latest_low
    s1 = (2.0 * pivot) - latest_high
    r2 = pivot + (latest_high - latest_low)
    s2 = pivot - (latest_high - latest_low)

    if ai_recommendation in ["STRONG BUY", "BUY"]:
        intraday_action = "INTRADAY LONG (BUY)"
        intraday_color = "emerald"
        entry_min = round(min(current_close * 0.997, s1), 2)
        entry_max = round(current_close * 1.002, 2)
        stop_loss = round(current_close - (1.2 * atr_val), 2)
        target_1 = round(current_close + (1.2 * atr_val), 2)
        target_2 = round(current_close + (2.2 * atr_val), 2)
        risk = max(current_close - stop_loss, 0.01)
        reward = max(target_1 - current_close, 0.01)
        rr_ratio = round(reward / risk, 2)
    elif ai_recommendation in ["STRONG SELL", "SELL"]:
        intraday_action = "INTRADAY SHORT (SELL)"
        intraday_color = "rose"
        entry_min = round(current_close * 0.998, 2)
        entry_max = round(max(current_close * 1.003, r1), 2)
        stop_loss = round(current_close + (1.2 * atr_val), 2)
        target_1 = round(current_close - (1.2 * atr_val), 2)
        target_2 = round(current_close - (2.2 * atr_val), 2)
        risk = max(stop_loss - current_close, 0.01)
        reward = max(current_close - target_1, 0.01)
        rr_ratio = round(reward / risk, 2)
    else:
        intraday_action = "STAND-BY (RANGE-BOUND)"
        intraday_color = "amber"
        entry_min = round(s1, 2)
        entry_max = round(r1, 2)
        stop_loss = round(s2, 2)
        target_1 = round(r1, 2)
        target_2 = round(r2, 2)
        rr_ratio = 1.0

    intraday_setup = {
        "action": intraday_action,
        "color": intraday_color,
        "entry_range": f"{entry_min:.2f} - {entry_max:.2f}",
        "stop_loss": stop_loss,
        "target_1": target_1,
        "target_2": target_2,
        "rr_ratio": f"1 : {rr_ratio:.1f}",
        "pivot_points": {
            "r2": round(r2, 2),
            "r1": round(r1, 2),
            "pivot": round(pivot, 2),
            "s1": round(s1, 2),
            "s2": round(s2, 2)
        }
    }

    prediction_payload = {
        "ticker": ticker.upper(),
        "company_name": info.get('longName') or info.get('shortName') or ticker,
        "currency": info.get('currency', 'INR' if ticker.endswith('.NS') or ticker.endswith('.BO') else 'USD'),
        "as_of_date": last_date.strftime('%Y-%m-%d'),
        "prediction_target_date": next_date.strftime('%Y-%m-%d'),
        "current_close": current_close,
        "predicted_close": round(pred_next_close, 2),
        "predicted_high": round(pred_next_high, 2),
        "predicted_low": round(pred_next_low, 2),
        "expected_change": round(expected_change, 2),
        "expected_change_pct": round(expected_change_pct, 2),
        "signal": ai_recommendation,
        "signal_color": ai_color,
        "technical_signal": tech_signal,
        "ai_reasoning": ai_reasoning_summary,
        "news_analysis": news_analysis,
        "intraday_setup": intraday_setup,
        "metrics": {
            "mae": round(mae, 2),
            "rmse": round(rmse, 2),
            "r2": round(r2, 4),
            "directional_accuracy_pct": round(directional_accuracy, 1)
        },
        "indicators": {
            "rsi": round(rsi_val, 2),
            "macd": round(float(latest_row['MACD']), 2) if not np.isnan(latest_row['MACD']) else 0.0,
            "sma_20": round(float(latest_row['SMA_20']), 2) if not np.isnan(latest_row['SMA_20']) else current_close,
            "sma_50": round(float(latest_row['SMA_50']), 2) if not np.isnan(latest_row['SMA_50']) else current_close,
            "atr": round(float(latest_row['ATR']), 2) if not np.isnan(latest_row['ATR']) else 0.0
        },
        "chart_series": chart_series
    }
    
    return prediction_payload

if __name__ == "__main__":
    import sys
    symbol = sys.argv[1] if len(sys.argv) > 1 else "GILLETTE.NS"
    print(f"Testing Prediction Engine for {symbol}...")
    res = train_and_predict(symbol)
    print(f"Signal: {res['signal']} | Current: {res['current_close']} -> Predicted Next Close: {res['predicted_close']} ({res['expected_change_pct']}%)")
