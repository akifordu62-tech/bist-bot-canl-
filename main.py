"""
Ana Çalıştırma ve Kontrol Merkezi
"""
import sys
import argparse
import webbrowser
import os

# Windows terminal Türkçe ve Unicode / Emoji karakter desteği
try:
    if sys.stdout.encoding and sys.stdout.encoding.lower() != 'utf-8':
        sys.stdout.reconfigure(encoding='utf-8')
except Exception:
    pass

import yfinance as yf
from config import StrategyConfig, TELEGRAM_CONFIG
from strategy import run_strategy
from chart import create_chart
from scanner import scan_symbols, fetch_data
from backtest import backtest_strategy, print_backtest_report
from bist_symbols import BIST_100_SYMBOLS, BIST_30_SYMBOLS
from telegram_notifier import test_telegram_connection

def run_single_chart(symbol: str, open_browser: bool = True):
    print(f"\n[Veri İndiriliyor]: {symbol}...")
    df = fetch_data(symbol)
    if df.empty:
        print(f"[HATA]: {symbol} için veri alınamadı.")
        return

    config = StrategyConfig()
    df_strat = run_strategy(df, config)
    fig = create_chart(df_strat, symbol=symbol, save_html=True)
    
    clean_sym = symbol.replace(".IS", "")
    html_path = os.path.abspath(f"charts/{clean_sym}_chart.html")
    print(f"[Grafik Hazır]: {html_path}")
    if open_browser:
        webbrowser.open(f"file://{html_path}")

def run_single_backtest(symbol: str):
    print(f"\n[Veri İndiriliyor]: {symbol}...")
    df = fetch_data(symbol, period="3y")
    if df.empty:
        print(f"[HATA]: {symbol} için veri alınamadı.")
        return

    config = StrategyConfig()
    df_strat = run_strategy(df, config)
    results = backtest_strategy(df_strat)
    print_backtest_report(symbol, results)

def interactive_menu():
    while True:
        print("\n" + "=" * 50)
        print("  📊 BIST AL/SAT SİNYAL BOTU & ANALİZ SİSTEMİ")
        print("=" * 50)
        print("  1. BIST 100 Günlük Tarama Yap (Tüm Hisseler)")
        print("  2. BIST 30 Hızlı Tarama Yap")
        print("  3. Tek Hisse İçin Plotly İnteraktif Grafik Çiz")
        print("  4. Tek Hisse İçin Backtest / Getiri Analizi")
        print("  5. Telegram Bot Bağlantısını Test Et")
        print("  0. Çıkış")
        print("=" * 50)

        choice = input("Lütfen seçim yapınız (0-5): ").strip()
        if choice == "1":
            scan_symbols(BIST_100_SYMBOLS, send_telegram=TELEGRAM_CONFIG.get("enabled", False), save_charts=True)
        elif choice == "2":
            scan_symbols(BIST_30_SYMBOLS, send_telegram=TELEGRAM_CONFIG.get("enabled", False), save_charts=True)
        elif choice == "3":
            sym = input("Hisse Kodu (Örn: THYAO veya THYAO.IS): ").strip().upper()
            if not sym.endswith(".IS"):
                sym += ".IS"
            run_single_chart(sym, open_browser=True)
        elif choice == "4":
            sym = input("Hisse Kodu (Örn: THYAO veya THYAO.IS): ").strip().upper()
            if not sym.endswith(".IS"):
                sym += ".IS"
            run_single_backtest(sym)
        elif choice == "5":
            test_telegram_connection()
        elif choice == "0":
            print("İyi günler!")
            break
        else:
            print("Geçersiz seçim! Tekrar deneyin.")

def main():
    parser = argparse.ArgumentParser(description="Net Hacim Akışı & RSI Gecikmeli Çıkış Botu")
    parser.add_argument("--scan", action="store_true", help="BIST 100 taraması başlatır")
    parser.add_argument("--scan-bist30", action="store_true", help="BIST 30 hızlı taraması başlatır")
    parser.add_argument("--chart", type=str, help="Belirtilen hissenin grafiğini üretir (Örn: THYAO.IS)")
    parser.add_argument("--backtest", type=str, help="Belirtilen hissede backtest yapar (Örn: THYAO.IS)")
    parser.add_argument("--test-telegram", action="store_true", help="Telegram bağlantısını test eder")

    args = parser.parse_args()

    if args.scan:
        scan_symbols(BIST_100_SYMBOLS, send_telegram=TELEGRAM_CONFIG.get("enabled", False), save_charts=True)
    elif args.scan_bist30:
        scan_symbols(BIST_30_SYMBOLS, send_telegram=TELEGRAM_CONFIG.get("enabled", False), save_charts=True)
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
