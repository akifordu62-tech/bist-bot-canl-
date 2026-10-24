"""
BIST 30 Günlük Tarama & Otomatik 5 Hisse Portföy Takip Modülü (Scanner V6.0)
- Sadece BIST 30 şirketlerini tarar.
- Her hisse için 2020'den günümüze en kârlı özel optimum RSI çıkış seviyesini kullanır.
- Maksimum 5 açık hisse (%10 portföy payı) kuralına göre otomatik sepet takibi yapar.
- Telegram'a günde tek bir toplu BIST 30 Portföy & Sinyal Özeti (veya 'Bugün sinyal olmamıştır' bilgisi) gönderir.
"""
import os
import sys
import json
import datetime
import pandas as pd
import yfinance as yf

try:
    if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
        sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

from config import StrategyConfig, PORTFOLIO_CONFIG
from strategy import run_strategy
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
    Sadece BIST 30 şirketlerini Hisseye Özel Optimum RSI stratejisiyle tarar,
    5 hisselik portföy sınırına göre AL/SAT kararlarını üretir ve Telegram'a iletir.
    """
    # Kullanıcı kuralı: Sadece BIST 30 şirketlerinden sinyal üretilir
    if symbols_list is None:
        targets = list(BIST_30_SYMBOLS)
    else:
        filtered = [s for s in symbols_list if is_bist30(s)]
        targets = filtered if filtered else list(BIST_30_SYMBOLS)

    config = StrategyConfig()
    state = load_portfolio_state()
    max_positions = int(state.get("max_positions", PORTFOLIO_CONFIG.get("max_positions", 5)))
    allocation_pct = float(state.get("allocation_pct", PORTFOLIO_CONFIG.get("allocation_pct", 10.0)))

    print("\n" + "=" * 70)
    print(f"  🔍 BIST 30 OPTİMUM RSI & 5 HİSSE PORTFÖY TARAMASI ({len(targets)} Şirket)")
    print(f"  📌 Portföy Kuralı: Maksimum {max_positions} Açık Hisse (Her Alım %{allocation_pct:.0f})")
    print("=" * 70)

    stock_snapshots = {}
    latest_bar_date = None

    total = len(targets)
    for idx, sym in enumerate(targets, 1):
        print(f"\r[{idx}/{total}] Taranıyor: {sym:<12}", end="", flush=True)
        df = fetch_data(sym, start="2019-10-01")
        if df.empty:
            continue

        df_strat = run_strategy(df, config, symbol=sym)
        if df_strat.empty:
            continue

        last_row = df_strat.iloc[-1]
        bar_date_iso = df_strat.index[-1].strftime("%Y-%m-%d")
        if latest_bar_date is None or bar_date_iso > latest_bar_date:
            latest_bar_date = bar_date_iso

        clean_sym = sym.replace(".IS", "").strip().upper()
        close_price = float(last_row["Close"])
        rsi_val = float(last_row["RSI"])
        target_rsi = int(last_row["Optimal_RSI_Exit"])
        raw_long = bool(last_row["Raw_Long_Condition"])
        raw_exit = bool(last_row["Raw_Exit_Condition"])

        bt_res = backtest_strategy(df_strat)
        stock_snapshots[clean_sym] = {
            "symbol": sym,
            "clean_symbol": clean_sym,
            "date_iso": bar_date_iso,
            "price": close_price,
            "rsi": rsi_val,
            "target_rsi": target_rsi,
            "raw_long": raw_long,
            "raw_exit": raw_exit,
            "win_rate": float(bt_res.get("win_rate", 0.0)),
            "avg_win": float(bt_res.get("avg_win_pct", 0.0)),
            "total_return_pct": float(bt_res.get("total_return_pct", 0.0)),
            "df_strat": df_strat,
        }

    print()
    if not latest_bar_date:
        print("[UYARI]: Hiçbir BIST 30 hissesi için güncel veri alınamadı.")
        return {"buy": [], "sell": [], "skipped": [], "open_positions": state.get("open_positions", [])}

    display_date = datetime.datetime.strptime(latest_bar_date, "%Y-%m-%d").strftime("%d.%m.%Y")

    sold_today = []
    bought_today = []
    skipped_today = []

    if update_portfolio and state.get("last_processed_date") != latest_bar_date:
        # 1. ADIM: Sadece portföyde açık olan (maks. 5) hisselerde SAT kontrolü yap
        still_open = []
        sold_symbols_set = set()

        for pos in state.get("open_positions", []):
            csym = pos["clean_symbol"]
            snap = stock_snapshots.get(csym)
            if snap is None:
                still_open.append(pos)
                continue

            ep = float(pos["entry_price"])
            cur_p = snap["price"]
            cur_rsi = snap["rsi"]
            t_rsi = int(pos.get("target_rsi", snap["target_rsi"]))
            ret_pct = ((cur_p - ep) / ep * 100.0) if ep > 0 else 0.0

            # Sadece son bar tarihi güncel ise ve özel optimum RSI kırıldıysa SAT
            if snap["date_iso"] == latest_bar_date and snap["raw_exit"]:
                sell_item = {
                    "symbol": snap["symbol"],
                    "clean_symbol": csym,
                    "date": latest_bar_date,
                    "entry_date": pos.get("entry_date", ""),
                    "entry_price": round(ep, 2),
                    "exit_price": round(cur_p, 2),
                    "rsi": round(cur_rsi, 1),
                    "target_rsi": t_rsi,
                    "return_pct": round(ret_pct, 2),
                }
                sold_today.append(sell_item)
                sold_symbols_set.add(csym)
                state.setdefault("closed_history", []).append(
                    {
                        **sell_item,
                        "exit_date": latest_bar_date,
                        "reason": f"Özel Optimum RSI {t_rsi} Kırılımı",
                    }
                )
            else:
                pos["last_price"] = round(cur_p, 2)
                pos["last_rsi"] = round(cur_rsi, 1)
                pos["target_rsi"] = t_rsi
                pos["pnl_pct"] = round(ret_pct, 2)
                still_open.append(pos)

        # 2. ADIM: Boş kontenjan varsa BIST 30 AL sinyallerinden en düşük RSI'lı olanları seç
        open_syms_set = {p["clean_symbol"] for p in still_open}
        available_slots = max(0, max_positions - len(still_open))

        raw_candidates = []
        for csym, snap in stock_snapshots.items():
            if (
                snap["date_iso"] == latest_bar_date
                and snap["raw_long"]
                and csym not in open_syms_set
                and csym not in sold_symbols_set
            ):
                raw_candidates.append(snap)

        # En düşük RSI'a sahip (en ucuz kalmış) BIST 30 hissesine öncelik ver
        raw_candidates.sort(key=lambda x: x["rsi"])

        chosen = raw_candidates[:available_slots]
        overflow = raw_candidates[available_slots:]

        for c in chosen:
            buy_item = {
                "symbol": c["symbol"],
                "clean_symbol": c["clean_symbol"],
                "date": latest_bar_date,
                "price": round(c["price"], 2),
                "rsi": round(c["rsi"], 1),
                "target_rsi": c["target_rsi"],
                "win_rate": round(c["win_rate"], 1),
                "avg_win": round(c["avg_win"], 1),
                "allocation_pct": allocation_pct,
            }
            bought_today.append(buy_item)
            still_open.append(
                {
                    "symbol": c["symbol"],
                    "clean_symbol": c["clean_symbol"],
                    "entry_date": latest_bar_date,
                    "entry_price": round(c["price"], 2),
                    "entry_rsi": round(c["rsi"], 1),
                    "target_rsi": c["target_rsi"],
                    "allocation_pct": allocation_pct,
                    "last_price": round(c["price"], 2),
                    "last_rsi": round(c["rsi"], 1),
                    "pnl_pct": 0.0,
                }
            )

        for ov in overflow:
            skipped_today.append(
                {
                    "symbol": ov["symbol"],
                    "clean_symbol": ov["clean_symbol"],
                    "price": round(ov["price"], 2),
                    "rsi": round(ov["rsi"], 1),
                    "target_rsi": ov["target_rsi"],
                }
            )

        state["open_positions"] = still_open
        state["last_processed_date"] = latest_bar_date
        state["last_daily_actions"] = {
            "date": latest_bar_date,
            "bought": bought_today,
            "sold": sold_today,
            "skipped": skipped_today,
        }
        save_portfolio_state(state)

    else:
        # Aynı gün içinde tekrar çalıştırıldıysa sadece açık hisselerin güncel fiyat/RSI bilgisini tazele
        for pos in state.get("open_positions", []):
            snap = stock_snapshots.get(pos["clean_symbol"])
            if snap:
                ep = float(pos["entry_price"])
                pos["last_price"] = round(snap["price"], 2)
                pos["last_rsi"] = round(snap["rsi"], 1)
                pos["pnl_pct"] = round(((snap["price"] - ep) / ep * 100.0) if ep > 0 else 0.0, 2)
        if update_portfolio:
            save_portfolio_state(state)

        last_act = state.get("last_daily_actions", {})
        if last_act.get("date") == latest_bar_date:
            bought_today = last_act.get("bought", [])
            sold_today = last_act.get("sold", [])
            skipped_today = last_act.get("skipped", [])

    # İsteğe bağlı HTML grafik kaydı
    if save_charts:
        try:
            from chart import create_chart
            for item in bought_today + sold_today:
                snap = stock_snapshots.get(item["clean_symbol"])
                if snap:
                    create_chart(snap["df_strat"], symbol=snap["symbol"], save_html=True)
        except Exception:
            pass

    # Konsol Özeti
    print("=" * 70)
    print(f"  📊 BIST 30 GÜNLÜK RAPOR ({display_date})")
    print("=" * 70)
    if sold_today:
        print(f"  🔴 Sepetten SAT Verenler ({len(sold_today)}):")
        for s in sold_today:
            print(f"     - {s['clean_symbol']:<8} Çıkış: {s['exit_price']:.2f} TL | Kâr: %{s['return_pct']:+.1f} (Hedef RSI {s['target_rsi']})")
    if bought_today:
        print(f"  🟢 Sepete Yeni Giren AL Sinyalleri ({len(bought_today)}):")
        for b in bought_today:
            print(f"     - {b['clean_symbol']:<8} Fiyat: {b['price']:.2f} TL | RSI: {b['rsi']:.1f} | Hedef RSI: {b['target_rsi']}")
    if not sold_today and not bought_today:
        print("  ⚪ Bugün portföy için yeni bir AL veya SAT sinyali oluşmamıştır.")
    print(f"  💼 Aktif Açık Pozisyon: {len(state.get('open_positions', []))}/{max_positions}")
    print("=" * 70 + "\n")

    # Telegram Gönderimi (Günde 1 kez toplu rapor veya 'Bugün sinyal olmamıştır' mesajı)
    if send_telegram:
        sent_history = _load_sent_history()
        report_key = f"BIST30_DAILY_{latest_bar_date}"
        if force_telegram or report_key not in sent_history.get("sent_reports", []):
            ok = send_bist30_daily_report(
                date_str=display_date,
                bought_list=bought_today,
                sold_list=sold_today,
                open_positions=state.get("open_positions", []),
                skipped_list=skipped_today,
                max_positions=max_positions,
                allocation_pct=allocation_pct,
            )
            if ok and report_key not in sent_history.get("sent_reports", []):
                sent_history.setdefault("sent_reports", []).append(report_key)
                _save_sent_history(sent_history)
        else:
            print("[Telegram Bilgi]: Bugünün BIST 30 günlük portföy raporu zaten gönderilmiş, tekrar gönderilmedi.")

    return {
        "date": latest_bar_date,
        "display_date": display_date,
        "buy": bought_today,
        "sell": sold_today,
        "skipped": skipped_today,
        "open_positions": state.get("open_positions", []),
        "all_bist30": [
            {
                "Hisse": s["clean_symbol"],
                "Fiyat (TL)": round(s["price"], 2),
                "Güncel RSI": round(s["rsi"], 1),
                "Özel Hedef RSI": s["target_rsi"],
                "2020+ Getiri (%)": round(s["total_return_pct"], 1),
                "Kazanma (%)": round(s["win_rate"], 1),
                "Ham Sinyal": "🟢 AL" if s["raw_long"] else ("🔴 RSI Kırılımı" if s["raw_exit"] else "⚪ İzlemede"),
            }
            for s in sorted(stock_snapshots.values(), key=lambda x: x["clean_symbol"])
        ],
    }


if __name__ == "__main__":
    scan_symbols(BIST_30_SYMBOLS, send_telegram=True, save_charts=False)
