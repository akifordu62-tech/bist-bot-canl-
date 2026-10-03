"""
Net Hacim Akışı (RSI Gecikmeli Çıkış) Stratejisi V5.1
Pine Script'ten Python/Pandas'a 1:1 Sadakatle Dönüştürülmüş Strateji Motoru
"""
import numpy as np
import pandas as pd
from config import StrategyConfig

def calculate_net_volume(df: pd.DataFrame) -> pd.Series:
    """
    Pine Script:
    net_volume = close > close[1] ? volume : close < close[1] ? -volume : 0
    """
    close_diff = df['Close'].diff()
    net_vol = np.where(close_diff > 0, df['Volume'], np.where(close_diff < 0, -df['Volume'], 0.0))
    return pd.Series(net_vol, index=df.index, name="Net_Volume")

def calculate_rsi(series: pd.Series, period: int = 14) -> pd.Series:
    """
    Wilder's RSI (Pine Script ta.rsi ile 1:1 uyumlu - RMA smoothing)
    """
    delta = series.diff()
    gain = delta.clip(lower=0.0)
    loss = (-delta).clip(lower=0.0)

    # Pine Script ta.rma alpha = 1 / period ile birebir aynıdır
    avg_gain = gain.ewm(alpha=1.0 / period, min_periods=period, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1.0 / period, min_periods=period, adjust=False).mean()

    rs = avg_gain / avg_loss
    rsi = 100.0 - (100.0 / (1.0 + rs))
    return pd.Series(rsi, index=series.index, name="RSI")

def run_strategy(df: pd.DataFrame, config: StrategyConfig = None) -> pd.DataFrame:
    """
    Pine Script V5.1 mantığını bar-by-bar ve vektörel olarak çalıştırır.
    """
    if config is None:
        config = StrategyConfig()

    df = df.copy()
    
    # Sütun isimlerinin büyük harf olduğundan emin olalım (Open, High, Low, Close, Volume)
    for col in ['Open', 'High', 'Low', 'Close', 'Volume']:
        if col not in df.columns and col.lower() in df.columns:
            df[col] = df[col.lower()]

    # 1. Gösterge Hesaplamaları
    df['Net_Volume'] = calculate_net_volume(df)
    df['NV_Avg'] = df['Net_Volume'].rolling(window=config.nv_avg_length).mean()
    df['RSI'] = calculate_rsi(df['Close'], period=config.rsi_length)

    # 2. Tarih Filtresi
    if config.use_date_filter:
        start_ts = pd.Timestamp(config.start_date_str)
        if df.index.tz is not None:
            start_ts = start_ts.tz_localize(df.index.tz)
        in_date_range = pd.Series(df.index >= start_ts, index=df.index)
    else:
        in_date_range = pd.Series(True, index=df.index)
    df['In_Date_Range'] = in_date_range

    # 3. AL (Long) Koşulları
    # neg_flow_condition: Son neg_flow_bars boyunca net_volume negatif mi?
    is_neg = (df['Net_Volume'] < 0).astype(int)
    neg_flow_condition = (is_neg.rolling(window=config.neg_flow_bars).sum().shift(1) == config.neg_flow_bars)
    
    # Pine Script: neg_flow_condition[1]
    neg_flow_cond_prev = neg_flow_condition.shift(1).fillna(False)

    # ta.crossover(net_volume, nv_avg)
    crossover = (df['Net_Volume'] > df['NV_Avg']) & (df['Net_Volume'].shift(1) <= df['NV_Avg'].shift(1))

    # strong_close_confirmation = close > open and close > (high + low) / 2
    strong_close = (df['Close'] > df['Open']) & (df['Close'] > (df['High'] + df['Low']) / 2.0)

    # longCondition = neg_flow_condition[1] and ta.crossover(net_volume, nv_avg) and strong_close_confirmation
    raw_long_condition = neg_flow_cond_prev & crossover & strong_close
    df['Raw_Long_Condition'] = raw_long_condition & in_date_range

    # 4. SAT (Exit) Koşulları (Çıkış Desteği Kaldırıldı - Doğrudan RSI Aşırı Alım Kırılımı)
    # rsiExit = ta.crossunder(rsi_value, rsi_overbought) and rsi_value[1] > rsi_overbought
    rsi_exit = (df['RSI'] < config.rsi_overbought) & (df['RSI'].shift(1) > config.rsi_overbought)
    df['RSI_Warning'] = rsi_exit & in_date_range

    # 5. Pozisyon ve Emir Simülasyonu
    n = len(df)
    positions = np.zeros(n, dtype=int)
    long_entries = np.zeros(n, dtype=bool)
    exit_signals = np.zeros(n, dtype=bool)

    # Hız ve güvenilirlik için numpy array'lerine çevirelim
    date_ok_arr = in_date_range.to_numpy()
    raw_long_arr = raw_long_condition.to_numpy()
    rsi_exit_arr = rsi_exit.to_numpy()

    current_position = 0

    for i in range(n):
        date_ok = bool(date_ok_arr[i])
        long_cond = bool(raw_long_arr[i]) and date_ok
        exit_cond = bool(rsi_exit_arr[i]) and date_ok

        # Emir Kontrolü
        if long_cond:
            if current_position == 0:
                current_position = 1
                long_entries[i] = True
        elif exit_cond and current_position == 1:
            current_position = 0
            exit_signals[i] = True

        positions[i] = current_position

    df['Position'] = positions
    df['Long_Signal'] = long_entries
    df['Exit_Signal'] = exit_signals
    df['RSI_Alert_Active'] = False

    return df
