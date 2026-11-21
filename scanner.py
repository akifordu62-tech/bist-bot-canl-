"""
BIST 30 Günlük Tarama, Süper Lider + Akıllı Çift Kalkan (XU100 & Hisse EMA50) Modülü (Scanner V9.0)
- Sadece BIST 30 şirketlerini (30 hisse) + XU100 endeksini tarar.
- Giriş: Orijinal V8.0 (V/W soğuma + Net Hacim dönüşü) + Süper Lider Filtresi (Close > EMA200, RS60 >= %15, 52H Zirve >= -%15) + XU100 > EMA50 onayı.
- Çıkış: Hisseye özel optimum Çıkış RSI (68–78) VEYA Akıllı Çift Kalkan (XU100 < EMA50 VE Hisse < EMA50 -> PPF).
- Telegram'a endeks rejimi, bugünkü yeni AL/SAT/STOP sinyalleri, açık Süper Lider işlemleri ve anlık Süper Lider radarını gönderir.
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
    get_stock_risk_note,
)
from strategy import run_strategy, recalibrate_and_save_stock, get_xu100_df
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
    30 adet BIST 30 şirketini V9.0 Süper Lider + Akıllı Çift Kalkan (XU100 & Hisse EMA50) kurallarıyla tarar,
    yeni AL/SAT/STOP sinyallerini, açık Süper Lider işlemlerini ve anlık Süper Lider radarını belirleyip Telegram'a iletir.
    """
    if symbols_list is None:
        targets = list(BIST_30_SYMBOLS)
    else:
        filtered = [s for s in symbols_list if is_bist30(s)]
        targets = filtered if filtered else list(BIST_30_SYMBOLS)

    config = StrategyConfig()
    state = load_portfolio_state()

    print("\n" + "=" * 82)
    print(f"  🔍 BIST 30 SÜPER LİDER + AKILLI ÇİFT KALKAN (V9.0) GÜNLÜK TARAMASI ({len(targets)} Hisse)")
    print("=" * 82)

    print("  🛡️ XU100 (BIST 100 Endeks) verisi indiriliyor...")
    xu_df = get_xu100_df(force_refresh=True, start="2019-10-01")
    xu_info = {
        "close": 0.0,
        "ema50": 0.0,
        "ema200": 0.0,
        "above_ema50": True,
        "date_iso": "",
    }
    if xu_df is not None and not xu_df.empty:
        xu_c = float(xu_df["Close"].iloc[-1])
        xu_e50 = float(xu_df["EMA50"].iloc[-1])
        xu_e200 = float(xu_df["EMA200"].iloc[-1])
        xu_info = {
            "close": round(xu_c, 2),
            "ema50": round(xu_e50, 2),
            "ema200": round(xu_e200, 2),
            "above_ema50": bool(xu_c > xu_e50),
            "date_iso": xu_df.index[-1].strftime("%Y-%m-%d"),
        }
        reg_lbl = "🟢 POZİTİF (ALIM AÇIK)" if xu_info["above_ema50"] else "🔴 NEGATİF (PPF KALKANI AKTİF)"
        print(f"  🛡️ XU100: {xu_c:,.2f} | EMA50: {xu_e50:,.2f} ➔ {reg_lbl}")

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
            "xu_info": xu_info,
            "last_closed_info": None,
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
    all_recent_closed = []

    for sym, df in raw_dfs.items():
        df_strat = run_strategy(df, config, symbol=sym, xu_df=xu_df)
        if df_strat.empty:
            continue

        last_row = df_strat.iloc[-1]
        prev_rsi = float(df_strat["RSI"].iloc[-2]) if len(df_strat) >= 2 else float(last_row["RSI"])
        bar_date_iso = df_strat.index[-1].strftime("%Y-%m-%d")
        clean_sym = sym.replace(".IS", "").strip().upper()
        close_price = float(last_row["Close"])
        rsi_val = float(last_row["RSI"])
        target_rsi = int(last_row["Optimal_RSI_Exit"])
        ema50_val = float(last_row["EMA50"])
        ema200_val = float(last_row["EMA200"])
        rs60_val = float(last_row["RS60_Pct"])
        rs120_val = float(last_row["RS120_Pct"])
        rs_score_val = float(last_row["RS_Score"])
        dist52_val = float(last_row["Dist_52H_Pct"])
        above_ema50 = bool(last_row["Above_EMA50"])
        above_ema200 = bool(last_row["Above_EMA200"])
        is_super_leader = bool(last_row["Super_Leader_OK"])

        raw_long = bool(last_row["Trade_Entry"])
        raw_exit = bool(last_row["Exit_Signal"])
        exit_reason_today = str(last_row.get("Exit_Reason", "")) if raw_exit else ""
        in_pos_now = bool(last_row["Position"] == 1)

        entry_mask = df_strat["Trade_Entry"].fillna(False).to_numpy(dtype=bool)
        exit_mask = df_strat["Exit_Signal"].fillna(False).to_numpy(dtype=bool)
        entry_indices = np.where(entry_mask)[0]
        exit_indices = np.where(exit_mask)[0]

        last_entry_idx = int(entry_indices[-1]) if len(entry_indices) > 0 else -1
        last_exit_idx = int(exit_indices[-1]) if len(exit_indices) > 0 else -1

        # En son kapanan Süper Lider işlemini takip et (0/30 açıkken bilgi amaçlı)
        if last_exit_idx >= 0 and len(entry_indices) > 0:
            prior_entries = entry_indices[entry_indices < last_exit_idx]
            if len(prior_entries) > 0:
                pe_idx = int(prior_entries[-1])
                ep_c = float(df_strat["Close"].iloc[pe_idx])
                xp_c = float(df_strat["Close"].iloc[last_exit_idx])
                ret_c = ((xp_c - ep_c) / ep_c * 100.0) if ep_c > 0 else 0.0
                ex_ts = df_strat.index[last_exit_idx]
                all_recent_closed.append(
                    {
                        "clean_symbol": clean_sym,
                        "entry_date": df_strat.index[pe_idx].strftime("%Y-%m-%d"),
                        "exit_date": ex_ts.strftime("%Y-%m-%d"),
                        "exit_date_disp": ex_ts.strftime("%d.%m.%Y"),
                        "return_pct": round(ret_c, 1),
                        "exit_reason": str(df_strat["Exit_Reason"].iloc[last_exit_idx]) or "Hedef RSI",
                    }
                )

        is_new_buy_today = (bar_date_iso == latest_bar_date) and raw_long
        is_sell_today = (bar_date_iso == latest_bar_date) and raw_exit and (last_entry_idx >= 0)

        if in_pos_now and last_entry_idx >= 0:
            has_active_signal = True
            sig_ts = df_strat.index[last_entry_idx]
            signal_date_iso = sig_ts.strftime("%Y-%m-%d")
            signal_date_short = (
                sig_ts.strftime("%d.%m")
                if sig_ts.year == df_strat.index[-1].year
                else sig_ts.strftime("%m/%y")
            )
            signal_date_disp = sig_ts.strftime("%d.%m.%Y")
            signal_price = float(df_strat["Close"].iloc[last_entry_idx])
            signal_rsi = float(df_strat["RSI"].iloc[last_entry_idx])
            signal_diff_pct = ((close_price - signal_price) / signal_price * 100.0) if signal_price > 0 else 0.0
        elif is_sell_today and last_entry_idx >= 0:
            has_active_signal = False
            sig_ts = df_strat.index[last_entry_idx]
            signal_date_iso = sig_ts.strftime("%Y-%m-%d")
            signal_date_short = (
                sig_ts.strftime("%d.%m")
                if sig_ts.year == df_strat.index[-1].year
                else sig_ts.strftime("%m/%y")
            )
            signal_date_disp = sig_ts.strftime("%d.%m.%Y")
            signal_price = float(df_strat["Close"].iloc[last_entry_idx])
            signal_rsi = float(df_strat["RSI"].iloc[last_entry_idx])
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
            "ema50": ema50_val,
            "ema200": ema200_val,
            "above_ema50": above_ema50,
            "above_ema200": above_ema200,
            "rs60": rs60_val,
            "rs120": rs120_val,
            "rs_score": rs_score_val,
            "dist_52h": dist52_val,
            "is_super_leader": is_super_leader,
            "entry_rule": entry_rule_str,
            "raw_long": raw_long,
            "raw_exit": raw_exit,
            "exit_reason_today": exit_reason_today,
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

    all_recent_closed.sort(key=lambda x: x["exit_date"], reverse=True)
    last_closed_info = all_recent_closed[0] if all_recent_closed else None

    sold_today = []
    bought_today = []
    open_positions_now = []

    is_new_day = state.get("last_processed_date") != latest_bar_date

    # Süper Lider önceliğine göre (RS_Score yüksekten düşüğe) işle
    for csym, snap in sorted(stock_snapshots.items(), key=lambda item: item[1]["rs_score"], reverse=True):
        if snap["is_sell_today"]:
            new_exit_rsi = snap["target_rsi"]
            new_entry_rule = snap["entry_rule"]
            exit_rsn = snap["exit_reason_today"] or "Hedef RSI"

            if update_portfolio and is_new_day and ("EMA50" not in exit_rsn):
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
                "exit_reason": exit_rsn,
                "new_exit_rsi": new_exit_rsi,
                "new_entry_rule": new_entry_rule,
            }
            sold_today.append(sell_item)
            if update_portfolio and is_new_day:
                state.setdefault("closed_history", []).append(
                    {
                        **sell_item,
                        "exit_date": latest_bar_date,
                        "reason": exit_rsn,
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
                "ema50": round(snap["ema50"], 2),
                "rs60": round(snap["rs60"], 1),
                "rs_score": round(snap["rs_score"], 1),
                "dist_52h": round(snap["dist_52h"], 1),
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
                    "entry_date_short": snap["signal_date_short"],
                    "entry_date_disp": snap["signal_date_disp"],
                    "entry_price": round(snap["signal_price"], 2),
                    "entry_rsi": round(snap["signal_rsi"], 1),
                    "target_rsi": snap["target_rsi"],
                    "ema50": round(snap["ema50"], 2),
                    "rs60": round(snap["rs60"], 1),
                    "dist_52h": round(snap["dist_52h"], 1),
                    "entry_rule": snap["entry_rule"],
                    "last_price": round(snap["price"], 2),
                    "last_rsi": round(snap["rsi"], 1),
                    "pnl_pct": round(float(snap["signal_diff_pct"] or 0.0), 2),
                }
            )

    all_stocks_sorted = sorted(stock_snapshots.values(), key=lambda x: x["rs60"], reverse=True)
    all_stocks_list = [
        {
            "symbol": s["symbol"],
            "clean_symbol": s["clean_symbol"],
            "price": round(s["price"], 2),
            "rsi": round(s["rsi"], 1),
            "target_rsi": s["target_rsi"],
            "ema50": round(s["ema50"], 2),
            "ema200": round(s["ema200"], 2),
            "above_ema50": s["above_ema50"],
            "above_ema200": s["above_ema200"],
            "rs60": round(s["rs60"], 1),
            "rs_score": round(s["rs_score"], 1),
            "dist_52h": round(s["dist_52h"], 1),
            "is_super_leader": s["is_super_leader"],
            "entry_rule": s["entry_rule"],
            "has_active_signal": s["has_active_signal"],
            "is_new_buy_today": s["is_new_buy_today"],
            "is_sell_today": s["is_sell_today"],
            "exit_reason_today": s["exit_reason_today"],
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
        state["xu_info"] = xu_info
        state["last_closed_info"] = last_closed_info
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

    super_now_cnt = sum(1 for s in all_stocks_list if s["is_super_leader"])
    print("=" * 82)
    print(f"  📊 BIST 30 SÜPER LİDER & ÇİFT KALKAN RAPORU ({display_date})")
    print("=" * 82)
    if bought_today:
        print(f"  🟢 Bugün Yeni Süper Lider AL Verenler ({len(bought_today)}):")
        for b in bought_today:
            print(
                f"     - {b['clean_symbol']:<8} Fiyat: {b['price']:.2f} TL | "
                f"RS60: %{b['rs60']:+.1f} | RSI: {b['rsi']:.1f} ➔ Hedef RSI: {b['target_rsi']}"
            )
    if sold_today:
        print(f"  🔴 Bugün SAT / Çift EMA50 Stop Verenler ({len(sold_today)}):")
        for s in sold_today:
            print(
                f"     - {s['clean_symbol']:<8} Çıkış: {s['exit_price']:.2f} TL | "
                f"Kâr: %{s['return_pct']:+.1f} ({s.get('exit_reason', 'Hedef RSI')})"
            )
    if not sold_today and not bought_today:
        print("  ⚪ Bugün yeni tetiklenen AL, SAT veya Çift EMA50 Stop sinyali yoktur.")
    print(f"  💼 Açık Süper Lider İşlemi: {len(open_positions_now)} / 30 | ⭐ Anlık Süper Lider: {super_now_cnt} / 30")
    print("=" * 82 + "\n")

    if send_telegram:
        sent_history = _load_sent_history()
        report_key = f"BIST30_SUPERLEADER_V9_{latest_bar_date}"
        if force_telegram or report_key not in sent_history.get("sent_reports", []):
            ok = send_bist30_daily_report(
                date_str=display_date,
                bought_list=bought_today,
                sold_list=sold_today,
                open_positions=open_positions_now,
                skipped_list=[],
                max_positions=30,
                all_stocks_list=all_stocks_list,
                xu_info=xu_info,
                last_closed_info=last_closed_info,
            )
            if ok and report_key not in sent_history.get("sent_reports", []):
                sent_history.setdefault("sent_reports", []).append(report_key)
                _save_sent_history(sent_history)
        else:
            print("[Telegram Bilgi]: Bugünün V9.0 Süper Lider raporu zaten gönderilmiş, tekrar gönderilmedi.")

    return {
        "date": latest_bar_date,
        "display_date": display_date,
        "buy": bought_today,
        "sell": sold_today,
        "skipped": [],
        "open_positions": open_positions_now,
        "all_stocks_list": all_stocks_list,
        "xu_info": xu_info,
        "last_closed_info": last_closed_info,
        "all_bist30": [
            {
                "Sıra": idx,
                "Hisse": f"{s['clean_symbol']}★" if s["is_super_leader"] else s["clean_symbol"],
                "Fiyat (TL)": round(s["price"], 2),
                "EMA50 (TL)": round(s["ema50"], 2),
                "Güncel 1G RSI": round(s["rsi"], 1),
                "Hedef RSI": f"RSI {s['target_rsi']}",
                "RS60 (%)": f"%{s['rs60']:+.1f}",
                "52H Zirve (%)": f"%{s['dist_52h']:+.1f}",
                "Süper Lider": "⭐ EVET" if s["is_super_leader"] else ("👀 Yakın" if (s["above_ema200"] and s["rs60"] >= 8.0) else "⚪ Hayır"),
                "İşlem Durumu": (
                    "🚀 BUGÜN YENİ AL"
                    if s["is_new_buy_today"]
                    else (
                        f"🛡️ {s['exit_reason_today']}"
                        if s["is_sell_today"]
                        else ("🟢 Açık İşlem" if s["has_active_signal"] else "⚪ Nakitte / PPF")
                    )
                ),
                "İlk AL Tarihi": s["signal_date_disp"] if (s["has_active_signal"] or s["is_sell_today"]) else "-",
                "İlk Sinyalden Fark": (
                    f"%{s['signal_diff_pct']:+.2f}" if s["signal_diff_pct"] is not None else "-"
                ),
                "Bilanço / Haber Durumu": get_stock_risk_note(s["clean_symbol"]) or "🟢 Sağlam",
            }
            for idx, s in enumerate(all_stocks_sorted, 1)
        ],
    }


if __name__ == "__main__":
    scan_symbols(BIST_30_SYMBOLS, send_telegram=True, save_charts=False)
