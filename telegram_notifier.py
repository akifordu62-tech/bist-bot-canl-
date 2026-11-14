"""
Telegram Bildirim Modülü (V8.0 - BIST 30 | Hibrit Özel Mod V/W Soğuma & Çıkış RSI | 30 Hisse Tam Tablo)
- 5 hisse sınırı olmadan tüm BIST 30 hisselerinin güncel sinyal durumunu,
  varsa ne zaman sinyal geldiğini ve sinyal fiyatından yüzde kaç eksi/artıda olduğunu tablo halinde gönderir.
- O gün yeni AL veya SAT sinyali varsa en üstte ayrıca vurgular.
"""
import os
from typing import List, Dict, Any
import requests
from config import TELEGRAM_CONFIG


def send_telegram_message(text: str, token: str = None, chat_id: str = None) -> bool:
    """
    Belirtilen Telegram botu ve chat ID'sine HTML formatlı mesaj gönderir.
    GitHub Secrets ortam değişkenlerine (os.getenv) öncelik verir.
    """
    bot_token = token or os.getenv("TELEGRAM_TOKEN") or TELEGRAM_CONFIG.get("token")
    target_chat = chat_id or os.getenv("TELEGRAM_CHAT_ID") or TELEGRAM_CONFIG.get("chat_id")

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
        "disable_web_page_preview": True,
    }

    try:
        response = requests.post(url, json=payload, timeout=12)
        res_data = response.json()
        if res_data.get("ok"):
            print("[Telegram Başarılı]: Rapor Telegram'a iletildi!")
            return True
        err = res_data.get("description", "Bilinmeyen hata")
        print(f"[Telegram API Hatası]: {err}")
        return False
    except Exception as e:
        print(f"[Telegram İletişim Hatası]: {e}")
        return False


def format_bist30_daily_report(
    date_str: str,
    bought_list: List[Dict[str, Any]] = None,
    sold_list: List[Dict[str, Any]] = None,
    open_positions: List[Dict[str, Any]] = None,
    skipped_list: List[Dict[str, Any]] = None,
    max_positions: int = 30,
    allocation_pct: float = 10.0,
    all_stocks_list: List[Dict[str, Any]] = None,
) -> str:
    """
    5 hisse sınırı olmadan BIST 30 hisselerinin tamamı için:
    1) Bugün yeni gelen AL ve SAT sinyallerini,
    2) 30 hissenin tamamının güncel fiyat, RSI/Hedef RSI, Sinyal Tarihi ve Sinyalden % Fark tablosunu oluşturur.
    """
    bought_list = bought_list or []
    sold_list = sold_list or []
    open_positions = open_positions or []
    all_stocks_list = all_stocks_list or []

    lines = [
        "📊 <b>BIST 30 GÜNLÜK SİNYAL & AÇIK İŞLEM TABLOSU</b>",
        f"📅 <b>Tarih:</b> {date_str} | <b>Periyot:</b> 1 Günlük (Orijinal V8.0)",
        "━━━━━━━━━━━━━━━━━━━━",
    ]

    # 1. BÖLÜM: BUGÜN YENİ TETİKLENEN AL / SAT SİNYALLERİ
    if bought_list:
        lines.append(f"🟢 <b>BUGÜN YENİ AL SİNYALİ VERENLER ({len(bought_list)} Hisse):</b>")
        for b in sorted(bought_list, key=lambda x: float(x.get("rsi", 50.0))):
            lines.append(
                f"• <b>#{b['clean_symbol']}</b> | Fiyat: {b['price']:.2f} TL | "
                f"RSI: {b['rsi']:.1f} ➔ Hedef: <b>RSI {b['target_rsi']}</b>"
            )

    if sold_list:
        if bought_list:
            lines.append("")
        lines.append(f"🔴 <b>BUGÜN SAT SİNYALİ VERENLER ({len(sold_list)} Hisse):</b>")
        for s in sold_list:
            ret_val = float(s.get("return_pct", 0.0))
            sign = "+" if ret_val >= 0 else ""
            s_dt = s.get("entry_date_short") or s.get("entry_date", "-")
            lines.append(
                f"• <b>#{s['clean_symbol']}</b> | {s['entry_price']:.2f} ➔ {s['exit_price']:.2f} TL "
                f"(<b>%{sign}{ret_val:.1f}</b> | Sinyal: {s_dt} | Hedef RSI {s['target_rsi']} Kırıldı)"
            )

    if not bought_list and not sold_list:
        lines.append("⚪ <b>Bugün Yeni Sinyal:</b> Bugün yeni tetiklenen AL veya SAT sinyali yoktur.")

    # 2. BÖLÜM: TÜM BIST 30 HİSSELERİ GÜNCEL DURUM TABLOSU (1G RSI EN DÜŞÜKTEN SIRALI)
    # Eğer all_stocks_list verilmemişse open_positions üzerinden yedek tablo kur
    table_items = list(all_stocks_list) if all_stocks_list else []
    if not table_items and open_positions:
        for p in open_positions:
            ep = float(p.get("entry_price", 0.0))
            lp = float(p.get("last_price", ep))
            diff = ((lp - ep) / ep * 100.0) if ep > 0 else 0.0
            ed = str(p.get("entry_date", ""))
            ed_short = f"{ed[8:10]}.{ed[5:7]}" if len(ed) >= 10 else (ed or "AÇIK")
            table_items.append(
                {
                    "clean_symbol": p["clean_symbol"],
                    "price": lp,
                    "rsi": float(p.get("last_rsi", p.get("entry_rsi", 50.0))),
                    "target_rsi": int(p.get("target_rsi", 72)),
                    "has_active_signal": True,
                    "signal_date_short": ed_short,
                    "signal_diff_pct": diff,
                    "is_new_buy_today": False,
                    "is_sell_today": False,
                }
            )

    table_items.sort(key=lambda x: float(x.get("rsi", 50.0)))

    active_cnt = sum(1 for x in table_items if x.get("has_active_signal"))
    cheaper_list = [
        x for x in table_items
        if x.get("has_active_signal") and x.get("signal_diff_pct") is not None and float(x["signal_diff_pct"]) <= 0.0
    ]

    lines.append("")
    lines.append(
        f"📋 <b>BIST 30 TAM TABLO (RSI Ucuzdan Pahalıya | Açık Sinyal: {active_cnt}/{len(table_items)}):</b>"
    )

    pre_lines = [
        "#  HİSSE  FİYAT  RSI>HD SİNYAL  FARK%",
        "─────────────────────────────────────",
    ]

    for idx, item in enumerate(table_items, 1):
        sym = str(item.get("clean_symbol", ""))[:5].ljust(5)
        price = float(item.get("price", 0.0))
        if price >= 100.0:
            p_str = f"{price:6.1f}"
        elif price >= 10.0:
            p_str = f"{price:6.2f}"
        else:
            p_str = f"{price:6.2f}"

        rsi_int = int(round(float(item.get("rsi", 50.0))))
        trsi_int = int(item.get("target_rsi", 72))
        rsi_str = f"{rsi_int:2d}>{trsi_int:2d}"

        if item.get("is_sell_today"):
            sig_str = " SAT! "
            diff_val = float(item.get("signal_diff_pct", 0.0) or 0.0)
            diff_str = f"{diff_val:+5.1f}%"
        elif item.get("has_active_signal"):
            if item.get("is_new_buy_today"):
                sig_str = "BUGÜN "
            else:
                s_short = str(item.get("signal_date_short", "AÇIK"))[:5]
                sig_str = f"{s_short:<6}"
            diff_val = float(item.get("signal_diff_pct", 0.0) or 0.0)
            diff_str = f"{diff_val:+5.1f}%"
        else:
            sig_str = " YOK  "
            diff_str = "   -  "

        pre_lines.append(f"{idx:02d} {sym} {p_str}  {rsi_str} {sig_str} {diff_str}")

    lines.append("<pre>" + "\n".join(pre_lines) + "</pre>")

    if cheaper_list:
        cheap_txt = ", ".join(
            f"<b>#{x['clean_symbol']}</b> (%{float(x['signal_diff_pct']):+.1f})"
            for x in cheaper_list
        )
        lines.append(f"🟢 <b>Sinyal Fiyatından Ucuz Olanlar ({len(cheaper_list)}):</b> {cheap_txt}")

    no_sig_list = [x["clean_symbol"] for x in table_items if not x.get("has_active_signal") and not x.get("is_sell_today")]
    if no_sig_list:
        lines.append(f"⚪ <b>Sinyali Olmayan / Beklemedekiler ({len(no_sig_list)}):</b> " + ", ".join(f"#{s}" for s in no_sig_list))

    return "\n".join(lines)


def send_bist30_daily_report(
    date_str: str,
    bought_list: List[Dict[str, Any]] = None,
    sold_list: List[Dict[str, Any]] = None,
    open_positions: List[Dict[str, Any]] = None,
    skipped_list: List[Dict[str, Any]] = None,
    max_positions: int = 30,
    allocation_pct: float = 10.0,
    all_stocks_list: List[Dict[str, Any]] = None,
) -> bool:
    msg = format_bist30_daily_report(
        date_str=date_str,
        bought_list=bought_list,
        sold_list=sold_list,
        open_positions=open_positions,
        skipped_list=skipped_list,
        max_positions=max_positions,
        allocation_pct=allocation_pct,
        all_stocks_list=all_stocks_list,
    )
    return send_telegram_message(msg)


def test_telegram_connection(token: str = None, chat_id: str = None) -> bool:
    """
    Telegram ayarlarını V8.0 (BIST 30 Tam Tablo & Açık Sinyal Takibi) formatıyla test eder.
    """
    msg = (
        "🤖 <b>BIST 30 SİNYAL & AÇIK İŞLEM TAKİP BOTU (V8.0) AKTİF!</b>\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        "✅ <b>Kapsam:</b> Tüm BIST 30 Şirketleri (30 Hisse — 5 Hisse Sınırı Yok)\n"
        "✅ <b>Günlük Bildirim:</b> O gün yeni AL / SAT sinyali verenler + 30 hissenin tamamı için sinyal tarihi ve sinyalden % eksi/artı tablosu\n"
        "✅ <b>Strateji:</b> Orijinal V8.0 (1 Günlük Grafik — Hisseye Özel V/W Soğuma + Çıkış RSI)"
    )
    return send_telegram_message(msg, token=token, chat_id=chat_id)


if __name__ == "__main__":
    print("Telegram bağlantısı test ediliyor...")
    test_telegram_connection()
