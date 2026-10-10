"""
Telegram Bildirim Modülü
Al / Sat / RSI Uyarısı sinyallerini Telegram üzerinden iletir.
"""
import os
import requests
from config import TELEGRAM_CONFIG

def send_telegram_message(text: str, token: str = None, chat_id: str = None) -> bool:
    """
    Belirtilen Telegram botu ve chat ID'sine mesaj gönderir.
    GitHub Secrets ortam değişkenlerine (os.getenv) en yüksek önceliği verir.
    """
    bot_token = token or os.getenv("TELEGRAM_TOKEN") or TELEGRAM_CONFIG.get("token")
    target_chat = chat_id or os.getenv("TELEGRAM_CHAT_ID") or TELEGRAM_CONFIG.get("chat_id")
    
    # GitHub Secrets mevcutsa otomatik olarak aktifleştir
    if os.getenv("TELEGRAM_TOKEN") and os.getenv("TELEGRAM_CHAT_ID"):
        enabled = True
    else:
        env_enabled = os.getenv("TELEGRAM_ENABLED")
        if env_enabled is not None:
            enabled = env_enabled.lower() in ("true", "1")
        else:
            enabled = TELEGRAM_CONFIG.get("enabled", False)

    if not enabled and token is None:
        print("[Telegram Bilgi]: Telegram bildirimleri kapalı.")
        return False

    if not bot_token or not target_chat or "BURAYA" in str(bot_token):
        print("[Telegram Uyarısı]: Telegram bot token veya Chat ID tanımlanmamış.")
        return False

    url = f"https://api.telegram.org/bot{str(bot_token).strip()}/sendMessage"
    payload = {
        "chat_id": str(target_chat).strip(),
        "text": text,
        "parse_mode": "HTML",
        "disable_web_page_preview": True
    }

    try:
        response = requests.post(url, json=payload, timeout=10)
        res_data = response.json()
        if res_data.get("ok"):
            print("[Telegram Başarılı]: Mesaj Telegram'a iletildi!")
            return True
        else:
            err = res_data.get('description', 'Bilinmeyen hata')
            print(f"[Telegram API Hatası]: {err}")
            return False
    except Exception as e:
        print(f"[Telegram İletişim Hatası]: {e}")
        return False

def notify_signal(symbol: str, signal_type: str, price: float, rsi: float, date_str: str, 
                  win_rate: float = None, avg_win_pct: float = None, index_name: str = None, 
                  win_trades: int = None, total_trades: int = None, profit_factor: float = None,
                  extra_info: str = "") -> bool:
    """
    Kullanıcının isteğine göre zenginleştirilmiş sinyal bildirim formatı:
    - Sinyal Türü & Hisse Kodu
    - BIST 100 / BIST 30 Endeks Bilgisi
    - Fiyat & RSI Değeri
    - Kazanma Oranı (Win Rate) & İşlem Sayısı
    - Ortalama Kâr & Kâr Faktörü
    - Tarih
    """
    clean_sym = symbol.replace(".IS", "")
    
    if signal_type == "BUY":
        icon = "🟢"
        action = "ALIŞ SİNYALİ"
    elif signal_type == "SELL":
        icon = "🔴"
        action = "SATIŞ SİNYALİ"
    elif signal_type == "RSI_WARN":
        icon = "⚠️"
        action = "RSI UYARISI"
    else:
        icon = "ℹ️"
        action = signal_type

    msg_lines = [
        f"{icon} <b>[PYTHON BOT] #{clean_sym} {action}</b>",
        f"🏷️ <b>Endeks:</b> {index_name or 'BIST 100'}",
        f"💵 <b>Fiyat:</b> {price:.2f} TL | <b>RSI:</b> {rsi:.1f}"
    ]

    # Kazanma Oranı ve İşlem Sayısı
    if win_rate is not None and win_rate > 0:
        trades_text = f" ({win_trades}/{total_trades} Başarılı İşlem)" if (win_trades is not None and total_trades is not None and total_trades > 0) else ""
        msg_lines.append(f"🎯 <b>Kazanma Oranı:</b> %{win_rate:.1f}{trades_text}")

    # Ortalama Kâr ve Kâr Faktörü
    metrics_str = []
    if avg_win_pct is not None and avg_win_pct > 0:
        metrics_str.append(f"📈 <b>Ort. Kâr:</b> %{avg_win_pct:.1f}")
    if profit_factor is not None and profit_factor > 0:
        metrics_str.append(f"⚡ <b>Kâr Faktörü:</b> {profit_factor:.2f}")
    if metrics_str:
        msg_lines.append(" | ".join(metrics_str))

    msg_lines.append(f"📅 <b>Tarih:</b> {date_str}")

    if extra_info:
        msg_lines.append(f"ℹ️ {extra_info}")

    message = "\n".join(msg_lines)
    return send_telegram_message(message)

def test_telegram_connection() -> bool:
    """
    Telegram ayarlarını test eden sade mesaj.
    """
    msg = "🤖 [PYTHON BOT] Bağlantı başarılı! Sistem aktif ve hazır."
    res = send_telegram_message(msg)
    if res:
        print("[Telegram Başarılı]: Test mesajı Telegram'a iletildi!")
    else:
        print("[Telegram Başarısız]: Mesaj gönderilemedi. config.py içerisindeki token ve chat_id bilgilerini kontrol edin.")
    return res

if __name__ == "__main__":
    print("Telegram bağlantısı test ediliyor...")
    test_telegram_connection()
