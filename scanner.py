"""
BIST 100 Günlük Tarama Modülü (Scanner)
BIST 100 hisselerini tarar, son günde AL veya SAT sinyali veren hisseleri tespit eder,
interaktif grafiklerini hazırlar ve Telegram'a bildirim gönderir.
"""
import time
import os
import sys
import pandas as pd
import yfinance as yf

# Windows terminal Türkçe ve Unicode / Emoji karakter desteği
try:
    if sys.stdout.encoding and sys.stdout.encoding.lower() != 'utf-8':
        sys.stdout.reconfigure(encoding='utf-8')
except Exception:
    pass
from config import StrategyConfig, TELEGRAM_CONFIG
from strategy import run_strategy
from bist_symbols import BIST_100_SYMBOLS, BIST_30_SYMBOLS
from telegram_notifier import notify_signal, send_telegram_message

def safe_create_chart(df, symbol, save_html=True):
    try:
        from chart import create_chart
        return create_chart(df, symbol=symbol, save_html=save_html)
    except Exception:
        return None

def fetch_data(symbol: str, period: str = "max", interval: str = "1d", start: str = None) -> pd.DataFrame:
    """
    Yahoo Finance üzerinden hisse geçmiş verisini çeker ve temizler.
    start: '2020-01-01' gibi başlangıç tarihi belirtilebilir.
    """
    try:
        if start:
            df = yf.download(symbol, start=start, interval=interval, progress=False, auto_adjust=True)
        else:
            df = yf.download(symbol, period=period, interval=interval, progress=False, auto_adjust=True)
        if df.empty or len(df) < 30:
            return pd.DataFrame()
            
        # MultiIndex sütun yapısını düzelt (yfinance 0.2.x+ tekil sembollerde MultiIndex yapabiliyor)
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)

        df = df[['Open', 'High', 'Low', 'Close', 'Volume']].dropna()
        return df
    except Exception as e:
        print(f"[{symbol} Veri Çekme Hatası]: {e}")
        return pd.DataFrame()

def scan_symbols(symbols_list: list = None, send_telegram: bool = True, save_charts: bool = True) -> dict:
    """
    Tüm hisseleri sırayla tarar ve oluşan sinyalleri raporlar.
    """
    if symbols_list is None:
        symbols_list = BIST_100_SYMBOLS

    config = StrategyConfig()
    results = {
        "buy": [],
        "sell": [],
        "rsi_warning": []
    }

    print("\n" + "=" * 65)
    print(f"  🔍 BIST GÜNLÜK TARAMA BAŞLATILDI ({len(symbols_list)} Hisse)")
    print(f"  📅 Strateji Başlangıç Tarihi: {config.start_date_str}")
    print("=" * 65)

    total = len(symbols_list)
    for idx, sym in enumerate(symbols_list, 1):
        print(f"\r[{idx}/{total}] Taranıyor: {sym:<12}", end="", flush=True)
        
        df = fetch_data(sym)
        if df.empty:
            continue

        df_strat = run_strategy(df, config)
        if df_strat.empty:
            continue

        # Son tamamlanan bar
        last_row = df_strat.iloc[-1]
        last_date = df_strat.index[-1].strftime("%Y-%m-%d")
        close_price = float(last_row['Close'])
        rsi_val = float(last_row['RSI'])

        # 1. AL Sinyali Kontrolü
        if last_row['Long_Signal']:
            results["buy"].append({
                "symbol": sym,
                "date": last_date,
                "price": close_price,
                "rsi": rsi_val
            })
            print(f"\n  🟢 [AL SİNYALİ]: {sym} | Fiyat: {close_price:.2f} TL | RSI: {rsi_val:.1f}")
            
            if save_charts:
                safe_create_chart(df_strat, symbol=sym, save_html=True)
            if send_telegram:
                notify_signal(sym, "BUY", close_price, rsi_val, last_date)

        # 2. SAT Sinyali Kontrolü
        elif last_row['Exit_Signal']:
            results["sell"].append({
                "symbol": sym,
                "date": last_date,
                "price": close_price,
                "rsi": rsi_val
            })
            print(f"\n  🔴 [SAT SİNYALİ]: {sym} | Fiyat: {close_price:.2f} TL | RSI: {rsi_val:.1f}")
            
            if save_charts:
                safe_create_chart(df_strat, symbol=sym, save_html=True)
            if send_telegram:
                notify_signal(sym, "SELL", close_price, rsi_val, last_date)

        # 3. RSI Uyarısı Kontrolü
        elif last_row['RSI_Warning']:
            results["rsi_warning"].append({
                "symbol": sym,
                "date": last_date,
                "price": close_price,
                "rsi": rsi_val
            })
            print(f"\n  ⚠️ [RSI UYARISI]: {sym} | Fiyat: {close_price:.2f} TL | RSI: {rsi_val:.1f}")

    print("\n\n" + "=" * 65)
    print("                      TARAMA ÖZETİ")
    print("=" * 65)
    print(f"  🟢 AL Veren Hisseler ({len(results['buy'])}):")
    for item in results['buy']:
        print(f"     - {item['symbol']:<10} Fiyat: {item['price']:>7.2f} TL | RSI: {item['rsi']:.1f}")

    print(f"\n  🔴 SAT Veren Hisseler ({len(results['sell'])}):")
    for item in results['sell']:
        print(f"     - {item['symbol']:<10} Fiyat: {item['price']:>7.2f} TL | RSI: {item['rsi']:.1f}")

    print(f"\n  ⚠️ RSI Uyarısı Veren Hisseler ({len(results['rsi_warning'])}):")
    for item in results['rsi_warning']:
        print(f"     - {item['symbol']:<10} Fiyat: {item['price']:>7.2f} TL | RSI: {item['rsi']:.1f}")
    print("=" * 65 + "\n")

    # Sinyal çıkmadığında kullanıcının botun çalıştığını bilmesi için sade Telegram bilgilendirmesi
    if send_telegram and len(results["buy"]) == 0 and len(results["sell"]) == 0:
        import datetime
        now_str = datetime.datetime.now().strftime("%d.%m.%Y %H:%M")
        no_signal_msg = f"⚪ [PYTHON BOT] BIST 100 Taraması Tamamlandı: Bugün yeni sinyal yok. ({now_str})"
        send_telegram_message(no_signal_msg)

    return results

if __name__ == "__main__":
    # BIST 100 hisselerini tara ve Telegram bildirimlerini gönder
    scan_symbols(BIST_100_SYMBOLS, send_telegram=True, save_charts=False)
