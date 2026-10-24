"""
Ana Çalıştırma ve Kontrol Merkezi (BIST 30 | Hisseye Özel Optimum RSI | Maks. 5 Hisse Portföy)
"""
import sys
import argparse
import webbrowser
import os

try:
    if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
        sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

from config import StrategyConfig, TELEGRAM_CONFIG
from strategy import run_strategy
from chart import create_chart
from scanner import scan_symbols, fetch_data
from backtest import backtest_strategy, print_backtest_report
from bist_symbols import BIST_30_SYMBOLS
from telegram_notifier import test_telegram_connection


def run_single_chart(symbol: str, open_browser: bool = True):
    print(f"\n[Veri İndiriliyor]: {symbol}...")
    df = fetch_data(symbol, start="2019-10-01")
    if df.empty:
        print(f"[HATA]: {symbol} için veri alınamadı.")
        return

    config = StrategyConfig()
    df_strat = run_strategy(df, config, symbol=symbol)
    create_chart(df_strat, symbol=symbol, save_html=True)

    clean_sym = symbol.replace(".IS", "")
    html_path = os.path.abspath(f"charts/{clean_sym}_chart.html")
    print(f"[Grafik Hazır]: {html_path}")
    if open_browser:
        webbrowser.open(f"file://{html_path}")


def run_single_backtest(symbol: str):
    print(f"\n[Veri İndiriliyor]: {symbol}...")
    df = fetch_data(symbol, start="2019-10-01")
    if df.empty:
        print(f"[HATA]: {symbol} için veri alınamadı.")
        return

    config = StrategyConfig()
    df_strat = run_strategy(df, config, symbol=symbol)
    df_eval = df_strat[df_strat["In_Date_Range"]].copy()
    results = backtest_strategy(df_eval)
    print_backtest_report(symbol, results)


def interactive_menu():
    while True:
        print("\n" + "=" * 58)
        print("  📊 BIST 30 OPTİMUM RSI & 5 HİSSE PORTFÖY SİSTEMİ")
        print("=" * 58)
        print("  1. BIST 30 Günlük Tarama & 5 Hisse Portföy Güncellemesi")
        print("  2. Tek Şirket İçin İnteraktif Grafik Çiz (Özel RSI)")
        print("  3. Tek Şirket İçin 2020+ Optimum RSI Backtest Analizi")
        print("  4. Telegram Bot Bağlantısını Test Et")
        print("  0. Çıkış")
        print("=" * 58)

        choice = input("Lütfen seçim yapınız (0-4): ").strip()
        if choice == "1":
            scan_symbols(
                BIST_30_SYMBOLS,
                send_telegram=TELEGRAM_CONFIG.get("enabled", False),
                save_charts=False,
            )
        elif choice == "2":
            sym = input("Hisse Kodu (Örn: THYAO): ").strip().upper()
            if not sym.endswith(".IS"):
                sym += ".IS"
            run_single_chart(sym, open_browser=True)
        elif choice == "3":
            sym = input("Hisse Kodu (Örn: THYAO): ").strip().upper()
            if not sym.endswith(".IS"):
                sym += ".IS"
            run_single_backtest(sym)
        elif choice == "4":
            test_telegram_connection()
        elif choice == "0":
            print("İyi günler!")
            break
        else:
            print("Geçersiz seçim! Tekrar deneyin.")


def main():
    parser = argparse.ArgumentParser(description="BIST 30 Hisseye Özel Optimum RSI & 5 Hisse Portföy Botu")
    parser.add_argument("--scan", action="store_true", help="BIST 30 günlük taramasını başlatır")
    parser.add_argument("--scan-bist30", action="store_true", help="BIST 30 günlük taramasını başlatır")
    parser.add_argument("--chart", type=str, help="Belirtilen hissenin grafiğini üretir (Örn: THYAO.IS)")
    parser.add_argument("--backtest", type=str, help="Belirtilen hissede backtest yapar (Örn: THYAO.IS)")
    parser.add_argument("--test-telegram", action="store_true", help="Telegram bağlantısını test eder")

    args = parser.parse_args()

    if args.scan or args.scan_bist30:
        scan_symbols(BIST_30_SYMBOLS, send_telegram=TELEGRAM_CONFIG.get("enabled", False), save_charts=False)
    elif args.chart:
        sym = args.chart.upper()
        if not sym.endswith(".IS"):
            sym += ".IS"
        run_single_chart(sym, open_browser=True)
    elif args.backtest:
        sym = args.backtest.upper()
        if not sym.endswith(".IS"):
            sym += ".IS"
        run_single_backtest(sym)
    elif args.test_telegram:
        test_telegram_connection()
    else:
        interactive_menu()


if __name__ == "__main__":
    main()
