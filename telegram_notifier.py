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

def notify_signal(symbol: str, signal_type: str, price: float, rsi: float, date_str: str, extra_info: str = "") -> bool:
    """
    Seçenek 2: Sade, net ve TradingView'den tamamen ayırt edilebilir tek satırlık/kısa format.
    """
    clean_sym = symbol.replace(".IS", "")
    
    if signal_type == "BUY":
        message = f"🟢 [PYTHON BOT] #{clean_sym} Alış Sinyali ({price:.2f} TL | RSI: {rsi:.1f})"
    elif signal_type == "SELL":
        message = f"🔴 [PYTHON BOT] #{clean_sym} Satış Sinyali ({price:.2f} TL | RSI: {rsi:.1f})"
    elif signal_type == "RSI_WARN":
        message = f"⚠️ [PYTHON BOT] #{clean_sym} RSI Uyarısı ({price:.2f} TL | RSI: {rsi:.1f})"
    else:
        message = f"ℹ️ [PYTHON BOT] #{clean_sym} {signal_type} ({price:.2f} TL)"

    if extra_info:
        message += f" - {extra_info}"

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
