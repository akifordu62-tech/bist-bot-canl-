"""
BIST 30 Günlük Tarama, Hibrit Özel Mod (V/W Soğuma) & Sınırsız Açık Sinyal Takip Modülü (Scanner V8.0)
- Sadece BIST 30 şirketlerini (30 hisse) tarar.
- 5 hisse sınırı olmadan tüm BIST 30 hisselerinde o gün yeni AL / SAT sinyali olup olmadığını ve
  açıkta devam eden tüm AL sinyallerini (sinyal tarihi ve sinyal fiyatından % farkı ile) takip eder.
- İşlem SAT ile kapandığı anda yeni işlem verisi eklenerek optimal_params.json otomatik güncellenir.
"""
import os
import sys
import json
import datetime
import numpy as np
import pandas as pd
import yfinance as yf

try:
    if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
        sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

from config import (
    StrategyConfig,
    PORTFOLIO_CONFIG,
    get_stock_params,
    format_stock_entry_rule,
)
from strategy import run_strategy, recalibrate_and_save_stock
from bist_symbols import BIST_30_SYMBOLS, is_bist30
from backtest import backtest_strategy
from portfolio_manager import load_portfolio_state, save_portfolio_state
from telegram_notifier import send_bist30_daily_report

HISTORY_FILE = os.path.join(os.path.dirname(__file__), ".daily_sent_signals.json")


def _load_sent_history() -> dict:
    today_str = datetime.date.today().isoformat()
    if os.path.exists(HISTORY_FILE):
        try:
            with open(HISTORY_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                if data.get("date") == today_str:
                    return data
        except Exception:
            pass
    return {"date": today_str, "sent_reports": []}


def _save_sent_history(data: dict) -> None:
    try:
        with open(HISTORY_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception:
        pass


def fetch_data(
    symbol: str,
    period: str = "max",
    interval: str = "1d",
    start: str = None,
) -> pd.DataFrame:
    """
    Yahoo Finance üzerinden hisse geçmiş verisini çeker ve temizler.
    """
    try:
        if start:
            df = yf.download(symbol, start=start, interval=interval, progress=False, auto_adjust=True)
        else:
            df = yf.download(symbol, period=period, interval=interval, progress=False, auto_adjust=True)
        if df.empty or len(df) < 30:
            return pd.DataFrame()

        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)

        df = df[["Open", "High", "Low", "Close", "Volume"]].dropna()
        return df
    except Exception as e:
        print(f"[{symbol} Veri Çekme Hatası]: {e}")
        return pd.DataFrame()


def scan_symbols(
    symbols_list: list = None,
    send_telegram: bool = True,
    save_charts: bool = False,
    force_telegram: bool = False,
    update_portfolio: bool = True,
) -> dict:
    """
    30 adet BIST 30 şirketini Hibrit Özel Mod (V/W Giriş-Soğuma + Çıkış RSI) stratejisiyle tarar,
    5 hisse sınırı olmadan tüm yeni AL/SAT sinyallerini ve açık işlemleri belirler,
    ve Telegram'a 30 hissenin güncel durum tablosunu iletir.
    """
    if symbols_list is None:
        targets = list(BIST_30_SYMBOLS)
    else:
        filtered = [s for s in symbols_list if is_bist30(s)]
        targets = filtered if filtered else list(BIST_30_SYMBOLS)

    config = StrategyConfig()
    state = load_portfolio_state()

    print("\n" + "=" * 78)
    print(f"  🔍 BIST 30 HİBRİT ÖZEL MOD (1G) GÜNLÜK SİNYAL & AÇIK İŞLEM TARAMASI ({len(targets)} Hisse)")
    print("=" * 78)

    raw_dfs = {}
    latest_bar_date = None
    total = len(targets)

    for idx, sym in enumerate(targets, 1):
        print(f"\r[{idx}/{total}] İndiriliyor: {sym:<12}", end="", flush=True)
        df = fetch_data(sym, start="2019-10-01")
        if df.empty:
            continue
        raw_dfs[sym] = df
        bar_date_iso = df.index[-1].strftime("%Y-%m-%d")
        if latest_bar_date is None or bar_date_iso > latest_bar_date:
            latest_bar_date = bar_date_iso

    print()
    if not latest_bar_date:
        print("[UYARI]: Hiçbir BIST 30 hissesi için güncel veri alınamadı.")
        return {
            "buy": [],
            "sell": [],
            "skipped": [],
            "open_positions": [],
            "all_stocks_list": [],
            "all_bist30": [],
        }

    # Aylık Otomatik Kalibrasyon Kontrolü
    current_month = latest_bar_date[:7]
    if update_portfolio and state.get("last_calibrated_month") != current_month:
        print(f"  🔄 Yeni ay ({current_month}) periyodik Hibrit Mod kalibrasyonu çalıştırılıyor...")
        for sym, df_raw in raw_dfs.items():
            recalibrate_and_save_stock(sym, df_raw)
        state["last_calibrated_month"] = current_month
        save_portfolio_state(state)

    stock_snapshots = {}
    for sym, df in raw_dfs.items():
        df_strat = run_strategy(df, config, symbol=sym)
        if df_strat.empty:
            continue

        last_row = df_strat.iloc[-1]
        prev_rsi = float(df_strat["RSI"].iloc[-2]) if len(df_strat) >= 2 else float(last_row["RSI"])
        bar_date_iso = df_strat.index[-1].strftime("%Y-%m-%d")
        clean_sym = sym.replace(".IS", "").strip().upper()
        close_price = float(last_row["Close"])
        rsi_val = float(last_row["RSI"])
        target_rsi = int(last_row["Optimal_RSI_Exit"])
        raw_long = bool(last_row["Raw_Long_Condition"]) or bool(last_row["Trade_Entry"])
        raw_exit = bool(last_row["Raw_Exit_Condition"]) or bool(last_row["Exit_Signal"])

        # Son AL ve son SAT sinyal indekslerini bul
        long_mask = (
            df_strat["Raw_Long_Condition"].fillna(False).to_numpy(dtype=bool)
            | df_strat["Trade_Entry"].fillna(False).to_numpy(dtype=bool)
        )
        exit_mask = (
            df_strat["Raw_Exit_Condition"].fillna(False).to_numpy(dtype=bool)
            | df_strat["Exit_Signal"].fillna(False).to_numpy(dtype=bool)
        )
        long_indices = np.where(long_mask)[0]
        exit_indices = np.where(exit_mask)[0]

        last_long_idx = int(long_indices[-1]) if len(long_indices) > 0 else -1
        last_exit_idx = int(exit_indices[-1]) if len(exit_indices) > 0 else -1

        is_new_buy_today = (bar_date_iso == latest_bar_date) and raw_long

        # Bugün SAT verip kapanan açık bir sinyal var mı?
        was_active_before_today = False
        if len(long_indices) > 0:
            prev_exits = exit_indices[exit_indices < (len(df_strat) - 1)]
            prev_last_exit = int(prev_exits[-1]) if len(prev_exits) > 0 else -1
            prev_longs = long_indices[long_indices < (len(df_strat) - 1)]
            prev_last_long = int(prev_longs[-1]) if len(prev_longs) > 0 else -1
            if prev_last_long > prev_last_exit:
                was_active_before_today = True

        is_sell_today = (bar_date_iso == latest_bar_date) and raw_exit and was_active_before_today

        if last_long_idx > last_exit_idx:
            has_active_signal = True
            sig_ts = df_strat.index[last_long_idx]
            signal_date_iso = sig_ts.strftime("%Y-%m-%d")
            signal_date_short = sig_ts.strftime("%d.%m")
            signal_date_disp = sig_ts.strftime("%d.%m.%Y")
            signal_price = float(df_strat["Close"].iloc[last_long_idx])
            signal_rsi = float(df_strat["RSI"].iloc[last_long_idx])
            signal_diff_pct = ((close_price - signal_price) / signal_price * 100.0) if signal_price > 0 else 0.0
        elif is_sell_today:
            has_active_signal = False
            prev_longs = long_indices[long_indices < last_exit_idx]
            entry_idx = int(prev_longs[-1]) if len(prev_longs) > 0 else last_long_idx
            sig_ts = df_strat.index[entry_idx]
            signal_date_iso = sig_ts.strftime("%Y-%m-%d")
            signal_date_short = sig_ts.strftime("%d.%m")
            signal_date_disp = sig_ts.strftime("%d.%m.%Y")
            signal_price = float(df_strat["Close"].iloc[entry_idx])
            signal_rsi = float(df_strat["RSI"].iloc[entry_idx])
            signal_diff_pct = ((close_price - signal_price) / signal_price * 100.0) if signal_price > 0 else 0.0
        else:
            has_active_signal = False
            signal_date_iso = ""
            signal_date_short = "YOK"
            signal_date_disp = "Sinyal Yok"
            signal_price = 0.0
            signal_rsi = 0.0
            signal_diff_pct = None

        sparams = get_stock_params(clean_sym)
        entry_rule_str = format_stock_entry_rule(sparams)
        bt_res = backtest_strategy(df_strat)

        stock_snapshots[clean_sym] = {
            "symbol": sym,
            "clean_symbol": clean_sym,
            "date_iso": bar_date_iso,
            "price": close_price,
            "rsi": rsi_val,
            "prev_rsi": prev_rsi,
            "target_rsi": target_rsi,
            "entry_rule": entry_rule_str,
            "raw_long": raw_long,
            "raw_exit": raw_exit,
            "has_active_signal": has_active_signal,
            "is_new_buy_today": is_new_buy_today,
            "is_sell_today": is_sell_today,
            "signal_date_iso": signal_date_iso,
            "signal_date_short": signal_date_short,
            "signal_date_disp": signal_date_disp,
            "signal_price": signal_price,
            "signal_rsi": signal_rsi,
            "signal_diff_pct": signal_diff_pct,
            "win_rate": float(bt_res.get("win_rate", 0.0)),
            "avg_win": float(bt_res.get("avg_win_pct", 0.0)),
            "total_return_pct": float(bt_res.get("total_return_pct", 0.0)),
            "df_raw": df,
            "df_strat": df_strat,
        }

    display_date = datetime.datetime.strptime(latest_bar_date, "%Y-%m-%d").strftime("%d.%m.%Y")

    sold_today = []
    bought_today = []
    open_positions_now = []

    is_new_day = state.get("last_processed_date") != latest_bar_date

    for csym, snap in sorted(stock_snapshots.items(), key=lambda item: item[1]["rsi"]):
        if snap["is_sell_today"]:
            new_exit_rsi = snap["target_rsi"]
            new_entry_rule = snap["entry_rule"]
            if update_portfolio and is_new_day:
                recal_res = recalibrate_and_save_stock(snap["symbol"], snap["df_raw"])
                new_exit_rsi = int(recal_res["exit_rsi"])
                new_entry_rule = recal_res["rule_summary"]
                print(
                    f"  🔄 [{csym}] Kapanan işlem verisi eklendi -> Yeni Hibrit Seviyeler: "
                    f"Çıkış RSI {new_exit_rsi} | {new_entry_rule}"
                )

            sell_item = {
                "symbol": snap["symbol"],
                "clean_symbol": csym,
                "date": latest_bar_date,
                "entry_date": snap["signal_date_iso"],
                "entry_date_short": snap["signal_date_short"],
                "entry_price": round(snap["signal_price"], 2),
                "exit_price": round(snap["price"], 2),
                "rsi": round(snap["rsi"], 1),
                "target_rsi": snap["target_rsi"],
                "return_pct": round(float(snap["signal_diff_pct"] or 0.0), 2),
                "new_exit_rsi": new_exit_rsi,
                "new_entry_rule": new_entry_rule,
            }
            sold_today.append(sell_item)
            if update_portfolio and is_new_day:
                state.setdefault("closed_history", []).append(
                    {
                        **sell_item,
                        "exit_date": latest_bar_date,
                        "reason": f"Özel Optimum RSI {snap['target_rsi']} Kırılımı",
                    }
                )

        if snap["is_new_buy_today"]:
            buy_item = {
                "symbol": snap["symbol"],
                "clean_symbol": csym,
                "date": latest_bar_date,
                "price": round(snap["price"], 2),
                "rsi": round(snap["rsi"], 1),
                "target_rsi": snap["target_rsi"],
                "entry_rule": snap["entry_rule"],
                "win_rate": round(snap["win_rate"], 1),
                "avg_win": round(snap["avg_win"], 1),
            }
            bought_today.append(buy_item)

        if snap["has_active_signal"]:
            open_positions_now.append(
                {
                    "symbol": snap["symbol"],
                    "clean_symbol": csym,
                    "entry_date": snap["signal_date_iso"],
                    "entry_date_disp": snap["signal_date_disp"],
                    "entry_price": round(snap["signal_price"], 2),
                    "entry_rsi": round(snap["signal_rsi"], 1),
                    "target_rsi": snap["target_rsi"],
                    "entry_rule": snap["entry_rule"],
                    "last_price": round(snap["price"], 2),
                    "last_rsi": round(snap["rsi"], 1),
                    "pnl_pct": round(float(snap["signal_diff_pct"] or 0.0), 2),
                }
            )

    all_stocks_sorted = sorted(stock_snapshots.values(), key=lambda x: x["rsi"])
    all_stocks_list = [
        {
            "symbol": s["symbol"],
            "clean_symbol": s["clean_symbol"],
            "price": round(s["price"], 2),
            "rsi": round(s["rsi"], 1),
            "target_rsi": s["target_rsi"],
            "entry_rule": s["entry_rule"],
            "has_active_signal": s["has_active_signal"],
            "is_new_buy_today": s["is_new_buy_today"],
            "is_sell_today": s["is_sell_today"],
            "signal_date_iso": s["signal_date_iso"],
            "signal_date_short": s["signal_date_short"],
            "signal_date_disp": s["signal_date_disp"],
            "signal_price": round(s["signal_price"], 2) if s["signal_price"] else None,
            "signal_diff_pct": round(float(s["signal_diff_pct"]), 2) if s["signal_diff_pct"] is not None else None,
        }
        for s in all_stocks_sorted
    ]

    if update_portfolio:
        state["max_positions"] = 30
        state["open_positions"] = open_positions_now
        state["last_processed_date"] = latest_bar_date
        state["last_daily_actions"] = {
            "date": latest_bar_date,
            "bought": bought_today,
            "sold": sold_today,
            "skipped": [],
        }
        save_portfolio_state(state)

    if save_charts:
        try:
            from chart import create_chart
            for item in bought_today + sold_today:
                snap = stock_snapshots.get(item["clean_symbol"])
                if snap:
                    create_chart(snap["df_strat"], symbol=snap["symbol"], save_html=True)
        except Exception:
            pass

    print("=" * 78)
    print(f"  📊 BIST 30 GÜNLÜK SİNYAL & AÇIK İŞLEM RAPORU ({display_date})")
    print("=" * 78)
    if bought_today:
        print(f"  🟢 Bugün Yeni AL Sinyali Verenler ({len(bought_today)}):")
        for b in bought_today:
            print(
                f"     - {b['clean_symbol']:<8} Fiyat: {b['price']:.2f} TL | "
                f"RSI: {b['rsi']:.1f} ➔ Hedef RSI: {b['target_rsi']}"
            )
    if sold_today:
        print(f"  🔴 Bugün SAT Sinyali Verenler ({len(sold_today)}):")
        for s in sold_today:
            print(
                f"     - {s['clean_symbol']:<8} Çıkış: {s['exit_price']:.2f} TL | "
                f"Kâr: %{s['return_pct']:+.1f} (Hedef RSI {s['target_rsi']})"
            )
    if not sold_today and not bought_today:
        print("  ⚪ Bugün yeni tetiklenen AL veya SAT sinyali yoktur.")
    print(f"  📌 Takipteki Açık AL Sinyali Sayısı: {len(open_positions_now)} / {len(all_stocks_list)} Hisse")
    print("=" * 78 + "\n")

    if send_telegram:
        sent_history = _load_sent_history()
        report_key = f"BIST30_TABLE_{latest_bar_date}"
        if force_telegram or report_key not in sent_history.get("sent_reports", []):
            ok = send_bist30_daily_report(
                date_str=display_date,
                bought_list=bought_today,
                sold_list=sold_today,
                open_positions=open_positions_now,
                skipped_list=[],
                max_positions=30,
                all_stocks_list=all_stocks_list,
            )
            if ok and report_key not in sent_history.get("sent_reports", []):
                sent_history.setdefault("sent_reports", []).append(report_key)
                _save_sent_history(sent_history)
        else:
            print("[Telegram Bilgi]: Bugünün BIST 30 günlük tablosu zaten gönderilmiş, tekrar gönderilmedi.")

    return {
        "date": latest_bar_date,
        "display_date": display_date,
        "buy": bought_today,
        "sell": sold_today,
        "skipped": [],
        "open_positions": open_positions_now,
        "all_stocks_list": all_stocks_list,
        "all_bist30": [
            {
                "Sıra": idx,
                "Hisse": s["clean_symbol"],
                "Fiyat (TL)": round(s["price"], 2),
                "Güncel 1G RSI": round(s["rsi"], 1),
                "Hedef Çıkış RSI": f"RSI {s['target_rsi']}",
                "Sinyal Durumu": (
                    "🚀 BUGÜN YENİ AL"
                    if s["is_new_buy_today"]
                    else (
                        "🔴 BUGÜN SAT"
                        if s["is_sell_today"]
                        else ("🟢 Açık Sinyal" if s["has_active_signal"] else "⚪ Sinyal Yok")
                    )
                ),
                "Son AL Sinyal Tarihi": s["signal_date_disp"] if (s["has_active_signal"] or s["is_sell_today"]) else "Yok",
                "Sinyal Fiyatı (TL)": round(s["signal_price"], 2) if (s["has_active_signal"] or s["is_sell_today"]) else "-",
                "Sinyalden Fark (%)": (
                    f"%{s['signal_diff_pct']:+.2f}" if s["signal_diff_pct"] is not None else "-"
                ),
                "Hibrit Giriş / Soğuma Kuralı (V/W)": s["entry_rule"],
            }
            for idx, s in enumerate(all_stocks_sorted, 1)
        ],
    }


if __name__ == "__main__":
    scan_symbols(BIST_30_SYMBOLS, send_telegram=True, save_charts=False)
