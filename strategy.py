"""
Net Hacim Akışı & 1. Mod Hisseye Özel Giriş/Soğuma/Çıkış RSI Strateji Motoru (V7.0)
- Her hisse için özel Giriş Üst RSI, SAT Sonrası Soğuma (Reset RSI / Bekleme / Pahalıdan Almama) ve Çıkış RSI uygular.
- İşlem kapandığında (SAT) yeni işlem verisini dahil ederek hissenin giriş ve çıkış RSI seviyelerini otomatik günceller.
"""
import datetime
from typing import Dict, Any, Optional
import numpy as np
import pandas as pd
from config import (
    StrategyConfig,
    load_optimal_params,
    save_optimal_params,
    get_stock_params,
    format_stock_entry_rule,
)


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


def _compute_best_exit_rsi(
    close_arr: np.ndarray,
    rsi_arr: np.ndarray,
    base_trig_arr: np.ndarray,
    in_range_arr: np.ndarray,
) -> int:
    """
    2020'den son kapanışa kadar gerçekleşen tüm kapanmış işlemleri tarayarak
    68-78 aralığındaki en kârlı Çıkış RSI seviyesini bulur.
    """
    best_lvl = 72
    best_cap = -1.0
    fee = 0.001
    n = len(close_arr)

    for lvl in range(68, 79):
        cap = 1.0
        in_pos = False
        ep = 0.0
        t_cnt = 0
        for i in range(1, n):
            if not in_range_arr[i]:
                continue
            if not in_pos:
                if base_trig_arr[i] and rsi_arr[i] < 65.0:
                    in_pos = True
                    ep = close_arr[i] * (1.0 + fee)
            else:
                if rsi_arr[i] < lvl and rsi_arr[i - 1] >= lvl:
                    xp = close_arr[i] * (1.0 - fee)
                    cap *= xp / ep
                    in_pos = False
                    t_cnt += 1
        if t_cnt >= 1 and cap > best_cap:
            best_cap = cap
            best_lvl = lvl
    return int(best_lvl)


def calibrate_stock_parameters(
    df: pd.DataFrame,
    fixed_exit_rsi: Optional[int] = None,
    start_date_str: str = "2020-01-01",
) -> Dict[str, Any]:
    """
    1. Mod (Tepe Korumalı Dengeli Tam Özel Mod) Kalibrasyon Motoru:
    2020'den bugüne (yeni kapanan işlemler dahil) tüm geçmişi milisaniyeler içinde tarayarak
    hissenin en kârlı ve tepe yakalanmalarından koruyan özel Çıkış RSI + Giriş/Soğuma kurallarını belirler.
    """
    clean_df = df.copy()
    for col in ["Open", "High", "Low", "Close", "Volume"]:
        if col not in clean_df.columns and col.lower() in clean_df.columns:
            clean_df[col] = clean_df[col.lower()]
    clean_df = clean_df[["Open", "High", "Low", "Close", "Volume"]].dropna()

    if len(clean_df) < 50:
        return {
            "exit_rsi": int(fixed_exit_rsi or 72),
            "reset_rsi": 48.0,
            "max_buy_rsi": 60.0,
            "cooldown_bars": 8,
            "no_higher_bars": 0,
            "calibrated_at": datetime.date.today().isoformat(),
        }

    net_vol = calculate_net_volume(clean_df)
    nv_avg = net_vol.rolling(5).mean()
    rsi_ser = calculate_rsi(clean_df["Close"], 14)

    is_neg = (net_vol < 0).astype(int)
    neg2 = is_neg.rolling(2).sum().shift(1) == 2
    neg3 = is_neg.rolling(3).sum().shift(2) == 3
    cross = (net_vol > nv_avg) & (net_vol.shift(1) <= nv_avg.shift(1))
    strong = (clean_df["Close"] > clean_df["Open"]) & (
        clean_df["Close"] > (clean_df["High"] + clean_df["Low"]) / 2.0
    )
    base_trig = ((neg2 | neg3) & cross & strong).fillna(False).to_numpy(dtype=bool)

    start_ts = pd.Timestamp(start_date_str)
    if clean_df.index.tz is not None:
        start_ts = start_ts.tz_localize(clean_df.index.tz)
    in_range = np.asarray(clean_df.index >= start_ts, dtype=bool)
    in_range_loop = in_range.copy()
    in_range_loop[0] = False

    close_arr = clean_df["Close"].to_numpy(dtype=float)
    rsi_arr = rsi_ser.to_numpy(dtype=float)
    n = len(clean_df)
    fee = 0.001

    # 1. Aşama: Kapanan tüm işlemlerle en kârlı Çıkış RSI hedefini güncelle (68..78)
    if fixed_exit_rsi is not None:
        exit_lvl = int(fixed_exit_rsi)
    else:
        exit_lvl = _compute_best_exit_rsi(close_arr, rsi_arr, base_trig, in_range_loop)

    # 2. Aşama: 1. Mod Hisseye Özel Giriş & Soğuma Kalibrasyonu (140 Kombinasyon)
    trig_indices = np.where(base_trig & in_range_loop)[0]
    first_valid_idx = int(np.argmax(in_range_loop)) if np.any(in_range_loop) else 1

    raw_exit = np.zeros(n, dtype=bool)
    raw_exit[1:] = in_range_loop[1:] & (rsi_arr[1:] < exit_lvl) & (rsi_arr[:-1] >= exit_lvl)
    exit_indices = np.where(raw_exit)[0]

    reset_opts = [None, 55.0, 52.0, 50.0, 48.0, 45.0, 42.0]
    buy_opts = [65.0, 60.0, 58.0, 55.0, 52.0]
    cd_opts = [(0, 0), (8, 0), (10, 0), (10, 35)]

    def _search_with_min_trades(min_req: int) -> Optional[Dict[str, Any]]:
        best_score = -1e18
        chosen = None

        for reset_lvl in reset_opts:
            for max_buy in buy_opts:
                valid_trigs = trig_indices[rsi_arr[trig_indices] < max_buy]
                if len(valid_trigs) == 0:
                    continue

                for cd, nh in cd_opts:
                    trades_ret = []
                    trades_hold = []
                    trade_spans = []
                    last_exit_idx = -9999
                    last_exit_price = 0.0
                    cap = 1.0
                    open_entry_idx = -1
                    open_entry_price = 0.0

                    t_ptr = 0
                    n_trigs = len(valid_trigs)
                    while t_ptr < n_trigs:
                        b_idx = int(valid_trigs[t_ptr])
                        if b_idx <= last_exit_idx:
                            t_ptr += 1
                            continue

                        if cd > 0 and last_exit_idx > 0 and (b_idx - last_exit_idx) <= cd:
                            t_ptr += 1
                            continue

                        if nh > 0 and last_exit_idx > 0 and (b_idx - last_exit_idx) <= nh:
                            if close_arr[b_idx] > last_exit_price:
                                t_ptr += 1
                                continue

                        if reset_lvl is not None and last_exit_idx > 0:
                            if float(np.min(rsi_arr[last_exit_idx : b_idx + 1])) > reset_lvl:
                                t_ptr += 1
                                continue

                        ep = close_arr[b_idx] * (1.0 + fee)
                        ex_pos = int(np.searchsorted(exit_indices, b_idx + 1))
                        if ex_pos < len(exit_indices):
                            e_idx = int(exit_indices[ex_pos])
                            xp = close_arr[e_idx] * (1.0 - fee)
                            ret = (xp - ep) / ep * 100.0
                            cap *= 1.0 + ret / 100.0
                            trades_ret.append(ret)
                            trades_hold.append(e_idx - b_idx)
                            trade_spans.append((b_idx, e_idx, ep, cap))
                            last_exit_idx = e_idx
                            last_exit_price = close_arr[e_idx]
                            t_ptr += 1
                        else:
                            open_entry_idx = b_idx
                            open_entry_price = ep
                            break

                    if len(trades_ret) < min_req:
                        continue

                    realized_ret = (cap - 1.0) * 100.0
                    if open_entry_idx >= 0:
                        final_eq = cap * (close_arr[-1] / (open_entry_price / (1.0 + fee)))
                        cur_open_ret = (close_arr[-1] - open_entry_price) / open_entry_price * 100.0
                        open_hold = (n - 1) - open_entry_idx
                    else:
                        final_eq = cap
                        cur_open_ret = 0.0
                        open_hold = 0
                    mtm_ret = (final_eq - 1.0) * 100.0

                    eq_len = max(1, n - first_valid_idx)
                    eq_arr = np.full(eq_len, 1.0, dtype=float)
                    cur_c = 1.0
                    last_end = 0
                    for b_i, e_i, ep_val, cap_after in trade_spans:
                        s_rel = b_i - first_valid_idx
                        e_rel = e_i - first_valid_idx
                        if s_rel > last_end:
                            eq_arr[last_end:s_rel] = cur_c
                        raw_ep = ep_val / (1.0 + fee)
                        eq_arr[s_rel : e_rel + 1] = cur_c * (close_arr[b_i : e_i + 1] / raw_ep)
                        eq_arr[e_rel] = cap_after
                        cur_c = cap_after
                        last_end = e_rel + 1
                    if open_entry_idx >= 0:
                        s_rel = open_entry_idx - first_valid_idx
                        if s_rel > last_end:
                            eq_arr[last_end:s_rel] = cur_c
                        raw_ep = open_entry_price / (1.0 + fee)
                        eq_arr[s_rel:] = cur_c * (close_arr[open_entry_idx:] / raw_ep)
                    elif last_end < eq_len:
                        eq_arr[last_end:] = cur_c

                    cummax = np.maximum.accumulate(eq_arr)
                    mdd = float(((eq_arr - cummax) / cummax).min() * 100.0) if eq_len else 0.0

                    losses = sum(1 for r in trades_ret if r <= 0)
                    stuck = sum(1 for r, h in zip(trades_ret, trades_hold) if h > 65 and r < 5.0)
                    open_bad = 1 if (open_entry_idx >= 0 and open_hold > 50 and cur_open_ret < -10.0) else 0

                    penalty = (losses * 45.0) + (stuck * 60.0) + (open_bad * 120.0) + (abs(mdd) * 3.0)
                    score = (0.60 * mtm_ret + 0.40 * realized_ret) - penalty

                    if score > best_score:
                        best_score = score
                        chosen = {
                            "exit_rsi": int(exit_lvl),
                            "reset_rsi": float(reset_lvl) if reset_lvl is not None else None,
                            "max_buy_rsi": float(max_buy),
                            "cooldown_bars": int(cd),
                            "no_higher_bars": int(nh),
                            "calibrated_at": datetime.date.today().isoformat(),
                        }
        return chosen

    primary_min = 4 if (n - first_valid_idx) > 400 else 2
    best_params = _search_with_min_trades(primary_min)
    if best_params is None:
        best_params = _search_with_min_trades(1)
    if best_params is None:
        best_params = {
            "exit_rsi": int(exit_lvl),
            "reset_rsi": None,
            "max_buy_rsi": 65.0,
            "cooldown_bars": 0,
            "no_higher_bars": 0,
            "calibrated_at": datetime.date.today().isoformat(),
        }
    return best_params


def recalibrate_and_save_stock(symbol: str, df: pd.DataFrame) -> Dict[str, Any]:
    """
    Bir işlem kapandığında (SAT) veya aylık periyodik bakımda çağrılır:
    Hissenin tüm geçmişini + yeni kapanan işlemini değerlendirip hem Giriş/Soğuma
    hem Çıkış RSI seviyelerini yeniden hesaplar ve optimal_params.json dosyasına yazar.
    """
    clean = symbol.replace(".IS", "").strip().upper()
    new_params = calibrate_stock_parameters(df, fixed_exit_rsi=None)
    all_params = load_optimal_params()
    all_params[clean] = new_params
    save_optimal_params(all_params)
    return {
        **new_params,
        "rule_summary": format_stock_entry_rule(new_params),
    }


def run_strategy(
    df: pd.DataFrame,
    config: StrategyConfig = None,
    symbol: str = None,
) -> pd.DataFrame:
    """
    V7.0 (1. Mod) Hisseye Özel Giriş/Soğuma + Çıkış RSI stratejisini çalıştırır.
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

    # 3. Baz Hacim Akışı Dönüş Koşulu
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
    base_trigger = (neg_direct | neg3_prev) & crossover & strong_close

    # 4. Hisseye Özel Parametreleri Çözümle (Çıkış RSI + Giriş/Soğuma Kuralları)
    if symbol:
        clean_sym = symbol.replace(".IS", "").strip().upper()
        all_p = load_optimal_params()
        if clean_sym in all_p:
            stock_params = get_stock_params(clean_sym)
        else:
            stock_params = calibrate_stock_parameters(df)
    else:
        stock_params = get_stock_params(None, default_exit=config.rsi_overbought)

    if config.use_per_stock_optimal_rsi:
        exit_rsi_level = int(stock_params["exit_rsi"])
    else:
        exit_rsi_level = int(config.rsi_overbought)

    if config.use_per_stock_entry_cooldown:
        reset_rsi = stock_params.get("reset_rsi")
        max_buy_rsi = float(stock_params.get("max_buy_rsi", config.rsi_max_buy))
        cooldown_bars = int(stock_params.get("cooldown_bars", 0))
        no_higher_bars = int(stock_params.get("no_higher_bars", 0))
    else:
        reset_rsi = None
        max_buy_rsi = float(config.rsi_max_buy)
        cooldown_bars = 0
        no_higher_bars = 0

    df["Optimal_RSI_Exit"] = exit_rsi_level
    df["Optimal_Reset_RSI"] = float(reset_rsi) if reset_rsi is not None else np.nan
    df["Optimal_Max_Buy_RSI"] = max_buy_rsi
    df["Optimal_Cooldown_Bars"] = cooldown_bars
    df["Optimal_No_Higher_Bars"] = no_higher_bars

    date_ok_arr = np.asarray(in_date_range, dtype=bool)
    base_trig_arr = base_trigger.fillna(False).to_numpy(dtype=bool)
    close_arr = df["Close"].to_numpy(dtype=float)
    rsi_arr = df["RSI"].to_numpy(dtype=float)

    rsi_exit = (df["RSI"] < exit_rsi_level) & (df["RSI"].shift(1) >= exit_rsi_level)
    rsi_exit_arr = rsi_exit.fillna(False).to_numpy(dtype=bool)
    df["Raw_Exit_Condition"] = rsi_exit & in_date_range

    # 5. Tekil Hisse Pozisyon Simülasyonu & Portföy Aday Sinyal Motoru (1. Mod Soğuma Korumalı)
    n = len(df)
    positions = np.zeros(n, dtype=int)
    long_entries = np.zeros(n, dtype=bool)
    exit_signals = np.zeros(n, dtype=bool)
    portfolio_long_cond = np.zeros(n, dtype=bool)

    # Tekil hisse durum değişkenleri
    current_position = 0
    last_exit_idx = -9999
    last_exit_price = 0.0
    rsi_reset_ok = True

    # 5 Hisselik Sepet için Tepe Sonrası Soğuma Takibi (sepette olmasa bile zirve kırılımından hemen sonra almaz)
    peak_exit_idx = -9999
    peak_exit_price = 0.0
    peak_reset_ok = True

    for i in range(n):
        if i == 0 or not bool(date_ok_arr[i]):
            positions[i] = current_position
            continue

        if reset_rsi is not None:
            if rsi_arr[i] <= reset_rsi or rsi_arr[i - 1] <= reset_rsi:
                rsi_reset_ok = True
                peak_reset_ok = True

        # A) 5 Hisselik Portföy Aday Sinyali (Tepe Korumalı Raw_Long_Condition)
        if bool(rsi_exit_arr[i]):
            peak_exit_idx = i
            peak_exit_price = float(close_arr[i])
            if reset_rsi is not None:
                peak_reset_ok = False
        else:
            p_cond = bool(base_trig_arr[i]) and (rsi_arr[i] < max_buy_rsi)
            if p_cond and cooldown_bars > 0 and (i - peak_exit_idx) <= cooldown_bars:
                p_cond = False
            if p_cond and (reset_rsi is not None) and (not peak_reset_ok):
                p_cond = False
            if (
                p_cond
                and no_higher_bars > 0
                and (i - peak_exit_idx) <= no_higher_bars
                and peak_exit_price > 0
                and close_arr[i] > peak_exit_price
            ):
                p_cond = False
            portfolio_long_cond[i] = p_cond

        # B) Tekil Hisse Gerçek AL / SAT Durum Makinesi
        if current_position == 0:
            cond = bool(base_trig_arr[i]) and (rsi_arr[i] < max_buy_rsi)
            if cond and cooldown_bars > 0 and (i - last_exit_idx) <= cooldown_bars:
                cond = False
            if cond and (reset_rsi is not None) and (not rsi_reset_ok):
                cond = False
            if (
                cond
                and no_higher_bars > 0
                and (i - last_exit_idx) <= no_higher_bars
                and last_exit_price > 0
                and close_arr[i] > last_exit_price
            ):
                cond = False

            if cond:
                current_position = 1
                long_entries[i] = True
        else:
            if bool(rsi_exit_arr[i]):
                current_position = 0
                exit_signals[i] = True
                last_exit_idx = i
                last_exit_price = float(close_arr[i])
                if reset_rsi is not None:
                    rsi_reset_ok = False

        positions[i] = current_position

    df["Raw_Long_Condition"] = portfolio_long_cond
    df["Position"] = positions
    df["Trade_Entry"] = long_entries
    df["Long_Signal"] = long_entries
    df["Exit_Signal"] = exit_signals
    df["RSI_Warning"] = False

    return df
