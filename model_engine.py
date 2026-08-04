import yfinance as yf
import pandas as pd
import numpy as np
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

def fetch_stock_data(ticker, period="3y", interval="1d"):
    """Fetch historical stock data using yfinance."""
    stock = yf.Ticker(ticker)
    df = stock.history(period=period, interval=interval)
    if df.empty:
        # Fallback to download
        df = yf.download(ticker, period=period, interval=interval, auto_adjust=True)
    
    if df.empty:
        raise ValueError(f"No stock data found for ticker '{ticker}'. Please check the symbol.")

    # Flatten multi-index columns if present
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = [col[0] for col in df.columns]

    df = df.reset_index()
    if 'Date' not in df.columns and 'Datetime' in df.columns:
        df.rename(columns={'Datetime': 'Date'}, inplace=True)
    
    # Ensure Date column is datetime
    df['Date'] = pd.to_datetime(df['Date'])
    df = df.sort_values('Date').reset_index(drop=True)
    return df, stock.info

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
    
    # Trading Signal Determination
    rsi_val = float(latest_row['RSI']) if not np.isnan(latest_row['RSI']) else 50.0
    if expected_change_pct > 1.2 and rsi_val < 70:
        signal = "STRONG BUY"
        signal_color = "emerald"
    elif expected_change_pct > 0.3:
        signal = "BUY"
        signal_color = "green"
    elif expected_change_pct < -1.2 and rsi_val > 30:
        signal = "STRONG SELL"
        signal_color = "rose"
    elif expected_change_pct < -0.3:
        signal = "SELL"
        signal_color = "amber"
    else:
        signal = "NEUTRAL / HOLD"
        signal_color = "slate"

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
        "signal": signal,
        "signal_color": signal_color,
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
