"""
Net Hacim Akışı & Hisseye Özel Optimum RSI Strateji Motoru (V6.0)
2020'den günümüze hisse bazlı en yüksek getiriyi üreten özel RSI çıkış seviyeleriyle çalışır.
"""
import numpy as np
import pandas as pd
from config import StrategyConfig, OPTIMAL_RSI_MAP, get_optimal_rsi


def calculate_net_volume(df: pd.DataFrame) -> pd.Series:
    """
    Fiyat artış günlerinde pozitif hacim, düşüş günlerinde negatif hacim üretir.
    """
    close_diff = df["Close"].diff()
    net_vol = np.where(
        close_diff > 0,
        df["Volume"],
        np.where(close_diff < 0, -df["Volume"], 0.0),
    )
    return pd.Series(net_vol, index=df.index, name="Net_Volume")


def calculate_rsi(series: pd.Series, period: int = 14) -> pd.Series:
    """
    Wilder's RSI (RMA smoothing ile TradingView ta.rsi 1:1 uyumlu).
    """
    delta = series.diff()
    gain = delta.clip(lower=0.0)
    loss = (-delta).clip(lower=0.0)

    avg_gain = gain.ewm(alpha=1.0 / period, min_periods=period, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1.0 / period, min_periods=period, adjust=False).mean()

    rs = avg_gain / avg_loss
    rsi = 100.0 - (100.0 / (1.0 + rs))
    return pd.Series(rsi, index=series.index, name="RSI")


def _compute_dynamic_optimal_rsi(
    close_arr: np.ndarray,
    rsi_arr: np.ndarray,
    raw_long_arr: np.ndarray,
    date_ok_arr: np.ndarray,
) -> int:
    """
    Haritada yer almayan yeni bir hisse gelirse 2020'den günümüze 68-78 arası
    tüm RSI çıkışlarını test edip en kârlı seviyeyi otomatik bulur.
    """
    best_lvl = 72
    best_cap = -1.0
    fee = 0.001
    n = len(close_arr)

    for lvl in range(68, 79):
        cap = 1.0
        in_pos = False
        ep = 0.0
        for i in range(1, n):
            if not date_ok_arr[i]:
                continue
            if not in_pos:
                if raw_long_arr[i]:
                    in_pos = True
                    ep = close_arr[i] * (1.0 + fee)
            else:
                if rsi_arr[i] < lvl and rsi_arr[i - 1] >= lvl:
                    xp = close_arr[i] * (1.0 - fee)
                    cap *= xp / ep
                    in_pos = False
        if cap > best_cap:
            best_cap = cap
            best_lvl = lvl
    return best_lvl


def resolve_stock_exit_rsi(
    symbol: str = None,
    config: StrategyConfig = None,
    close_arr: np.ndarray = None,
    rsi_arr: np.ndarray = None,
    raw_long_arr: np.ndarray = None,
    date_ok_arr: np.ndarray = None,
) -> int:
    """
    Hissenin kullanacağı RSI çıkış seviyesini belirler:
    - Hisseye özel mod aktifse OPTIMAL_RSI_MAP tablosundan (veya dinamik backtestten) alır.
    - Manuel mod seçildiyse config.rsi_overbought değerini döndürür.
    """
    if config is not None and not config.use_per_stock_optimal_rsi:
        return int(config.rsi_overbought)

    if symbol:
        clean = symbol.replace(".IS", "").strip().upper()
        if clean in OPTIMAL_RSI_MAP:
            return int(OPTIMAL_RSI_MAP[clean])

    if (
        close_arr is not None
        and rsi_arr is not None
        and raw_long_arr is not None
        and date_ok_arr is not None
    ):
        return _compute_dynamic_optimal_rsi(close_arr, rsi_arr, raw_long_arr, date_ok_arr)

    return get_optimal_rsi(symbol, default=config.rsi_overbought if config else 72)


def run_strategy(
    df: pd.DataFrame,
    config: StrategyConfig = None,
    symbol: str = None,
) -> pd.DataFrame:
    """
    V6.0 Hisseye Özel Optimum RSI stratejisini çalıştırır.
    """
    if config is None:
        config = StrategyConfig()

    df = df.copy()

    for col in ["Open", "High", "Low", "Close", "Volume"]:
        if col not in df.columns and col.lower() in df.columns:
            df[col] = df[col.lower()]

    # 1. Göstergeler
    df["Net_Volume"] = calculate_net_volume(df)
    df["NV_Avg"] = df["Net_Volume"].rolling(window=config.nv_avg_length).mean()
    df["RSI"] = calculate_rsi(df["Close"], period=config.rsi_length)

    # 2. Tarih Filtresi
    if config.use_date_filter:
        start_ts = pd.Timestamp(config.start_date_str)
        if df.index.tz is not None:
            start_ts = start_ts.tz_localize(df.index.tz)
        in_date_range = pd.Series(df.index >= start_ts, index=df.index)
    else:
        in_date_range = pd.Series(True, index=df.index)
    df["In_Date_Range"] = in_date_range

    # 3. V6.0 AL (Giriş) Koşulları:
    # - 2 veya 3 bar negatif hacim akışının ardından gelen ilk güçlü hacim dönüşü
    # - Net_Volume > NV_Avg yukarı kesişimi
    # - Güçlü mum kapanışı: Close > Open ve Close > (High + Low) / 2
    # - Aşırı alımdan korumalı giriş: RSI < 65
    is_neg = (df["Net_Volume"] < 0).astype(int)
    neg3_prev = is_neg.rolling(window=3).sum().shift(2) == 3
    if config.use_fast_2bar_neg_flow:
        neg_direct = is_neg.rolling(window=2).sum().shift(1) == 2
    else:
        neg_direct = is_neg.rolling(window=3).sum().shift(1) == 3

    crossover = (df["Net_Volume"] > df["NV_Avg"]) & (
        df["Net_Volume"].shift(1) <= df["NV_Avg"].shift(1)
    )
    strong_close = (df["Close"] > df["Open"]) & (
        df["Close"] > (df["High"] + df["Low"]) / 2.0
    )

    raw_long = (neg_direct | neg3_prev) & crossover & strong_close & (
        df["RSI"] < config.rsi_max_buy
    )

    date_ok_arr = in_date_range.to_numpy(dtype=bool)
    raw_long_arr = raw_long.fillna(False).to_numpy(dtype=bool)
    close_arr = df["Close"].to_numpy(dtype=float)
    rsi_arr = df["RSI"].to_numpy(dtype=float)

    # 4. Hisseye Özel Optimum RSI Çıkış Seviyesi ve SAT Koşulu
    exit_rsi_level = resolve_stock_exit_rsi(
        symbol=symbol,
        config=config,
        close_arr=close_arr,
        rsi_arr=rsi_arr,
        raw_long_arr=raw_long_arr,
        date_ok_arr=date_ok_arr,
    )
    df["Optimal_RSI_Exit"] = exit_rsi_level

    rsi_exit = (df["RSI"] < exit_rsi_level) & (df["RSI"].shift(1) >= exit_rsi_level)
    rsi_exit_arr = rsi_exit.fillna(False).to_numpy(dtype=bool)

    df["Raw_Long_Condition"] = raw_long & in_date_range
    df["Raw_Exit_Condition"] = rsi_exit & in_date_range

    # 5. Tekil Hisse Gerçek Pozisyon Simülasyonu
    n = len(df)
    positions = np.zeros(n, dtype=int)
    long_entries = np.zeros(n, dtype=bool)
    exit_signals = np.zeros(n, dtype=bool)

    current_position = 0
    for i in range(n):
        date_ok = bool(date_ok_arr[i])
        long_cond = bool(raw_long_arr[i]) and date_ok
        exit_cond = bool(rsi_exit_arr[i]) and date_ok

        if current_position == 0:
            if long_cond:
                current_position = 1
                long_entries[i] = True
        else:
            if exit_cond:
                current_position = 0
                exit_signals[i] = True

        positions[i] = current_position

    df["Position"] = positions
    df["Trade_Entry"] = long_entries
    df["Long_Signal"] = long_entries
    df["Exit_Signal"] = exit_signals
    df["RSI_Warning"] = False

    return df
