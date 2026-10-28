"""
Telegram Bildirim Modülü (V8.0 - BIST 30 | Hibrit Özel Mod V/W Soğuma & Çıkış RSI | Maks. 5 Hisse Portföy)
- Sadece BIST 30 ve 5 hisse kontenjanına göre tek bir toplu günlük portföy raporu gönderir.
- SAT gerçekleştiğinde yeni kapanan işlem verisiyle güncellenen V/W tipini ve özel RSI seviyelerini de raporlar.
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
    bought_list: List[Dict[str, Any]],
    sold_list: List[Dict[str, Any]],
    open_positions: List[Dict[str, Any]],
    skipped_list: List[Dict[str, Any]] = None,
    max_positions: int = 5,
    allocation_pct: float = 10.0,
) -> str:
    """
    BIST 30 + Maksimum 5 Hisse (%10 Alım) + Hibrit Özel Mod (V/W Soğuma & Çıkış RSI) kurallarına göre
    tek toplu Telegram mesajını oluşturur.
    """
    skipped_list = skipped_list or []
    has_action = bool(bought_list or sold_list)
    open_cnt = len(open_positions)
    empty_slots = max(0, max_positions - open_cnt)
    stock_exposure = int(open_cnt * allocation_pct)
    cash_exposure = max(0, 100 - stock_exposure)

    lines = [
        "📊 <b>BIST 30 PORTFÖY & SİNYAL RAPORU</b>",
        f"📅 <b>Tarih:</b> {date_str} | <b>Mod:</b> Hibrit Özel Mod (V/W Soğuma & Çıkış RSI)",
        "━━━━━━━━━━━━━━━━━━━━",
    ]

    if not has_action:
        lines.append("⚪ <b>Bugün sinyal olmamıştır.</b>")
        if open_cnt >= max_positions and skipped_list:
            skipped_names = ", ".join(f"#{x['clean_symbol']}" for x in skipped_list)
            lines.append(
                f"🔒 <i>Portföy kontenjanı dolu ({open_cnt}/{max_positions}) olduğu için yeni alım yapılmamıştır "
                f"(Pas geçilen: {skipped_names}). Sepetteki hisselerde SAT sinyali yoktur.</i>"
            )
        else:
            lines.append(
                "<i>BIST 30 portföyünüz için bugün yeni bir AL veya açık hisselerinizde SAT sinyali oluşmadı.</i>"
            )
    else:
        if sold_list:
            lines.append("\n🔴 <b>SATIŞ SİNYALİ (Sepetten Çıkanlar):</b>")
            for s in sold_list:
                ret_val = float(s.get("return_pct", 0.0))
                sign = "+" if ret_val >= 0 else ""
                lines.append(
                    f"• <b>#{s['clean_symbol']}</b> | Çıkış: {s['exit_price']:.2f} TL "
                    f"(Giriş: {s['entry_price']:.2f} TL | <b>%{sign}{ret_val:.1f}</b>)"
                )
                lines.append(
                    f"  ↳ Güncel RSI: {s['rsi']:.1f} (Kilitli Hedef <b>RSI {s['target_rsi']}</b> aşağı kırıldı)"
                )
                if s.get("new_exit_rsi"):
                    lines.append(
                        f"  ↳ 🔄 <i>Yeni işlem verisi eklendi ➔ Sonraki Hedef: RSI {s['new_exit_rsi']} "
                        f"({s.get('new_entry_rule', '')})</i>"
                    )

        if bought_list:
            lines.append(f"\n🟢 <b>YENİ ALIM SİNYALİ (Sepete Girenler - %{allocation_pct:.0f} Pay):</b>")
            for b in bought_list:
                wr_txt = f"%{b['win_rate']:.1f}" if b.get("win_rate") is not None else "-"
                aw_txt = f"%{b['avg_win']:.1f}" if b.get("avg_win") is not None else "-"
                rule_txt = b.get("entry_rule", "")
                lines.append(
                    f"• <b>#{b['clean_symbol']}</b> | Fiyat: {b['price']:.2f} TL | RSI: {b['rsi']:.1f}"
                )
                lines.append(
                    f"  ↳ Kilitli Çıkış Hedefi: <b>RSI {b['target_rsi']}</b> | Başarı: {wr_txt} (Ort. Kâr: {aw_txt})"
                )
                if rule_txt:
                    lines.append(f"  ↳ 🛡️ <i>Hibrit Filtre: {rule_txt}</i>")

        if skipped_list:
            skipped_names = ", ".join(f"#{x['clean_symbol']} (RSI {x['rsi']:.1f})" for x in skipped_list)
            lines.append(
                f"\n🔒 <i>5 hisse sınırı dolduğu için alınmayan diğer BIST 30 sinyalleri: {skipped_names}</i>"
            )

    lines.append("\n━━━━━━━━━━━━━━━━━━━━")
    lines.append(
        f"💼 <b>AKTİF SEPET ({open_cnt}/{max_positions} Hisse | %{stock_exposure} Borsa - %{cash_exposure} Nakit):</b>"
    )

    if open_positions:
        bought_syms = {b["clean_symbol"] for b in bought_list}
        for idx, pos in enumerate(open_positions, 1):
            csym = pos["clean_symbol"]
            ep = float(pos["entry_price"])
            lp = float(pos.get("last_price", ep))
            lrsi = float(pos.get("last_rsi", pos.get("entry_rsi", 50.0)))
            trsi = int(pos["target_rsi"])
            pnl = float(pos.get("pnl_pct", ((lp - ep) / ep * 100.0) if ep > 0 else 0.0))
            sign = "+" if pnl >= 0 else ""

            if csym in bought_syms:
                lines.append(
                    f"{idx}. <b>#{csym}</b> | {lp:.2f} TL (<b>Yeni Eklendi</b>) | RSI: {lrsi:.1f} / Hedef: {trsi}"
                )
            else:
                lines.append(
                    f"{idx}. <b>#{csym}</b> | {ep:.2f} ➔ {lp:.2f} TL (<b>%{sign}{pnl:.1f}</b>) | RSI: {lrsi:.1f} / Hedef: {trsi}"
                )
    else:
        lines.append("• <i>Şu an sepette açık hisse bulunmuyor (%100 Nakit / Mevduat).</i>")

    if empty_slots > 0:
        lines.append(f"⚪ <i>Boş Kontenjan: {empty_slots} Hisse (Yeni BIST 30 sinyaline hazır)</i>")
    else:
        lines.append("🔒 <i>Kontenjan Dolu (5/5): Bir hisse hedefe ulaşıp satılana kadar yeni AL gelmez.</i>")

    return "\n".join(lines)


def send_bist30_daily_report(
    date_str: str,
    bought_list: List[Dict[str, Any]],
    sold_list: List[Dict[str, Any]],
    open_positions: List[Dict[str, Any]],
    skipped_list: List[Dict[str, Any]] = None,
    max_positions: int = 5,
    allocation_pct: float = 10.0,
) -> bool:
    msg = format_bist30_daily_report(
        date_str=date_str,
        bought_list=bought_list,
        sold_list=sold_list,
        open_positions=open_positions,
        skipped_list=skipped_list,
        max_positions=max_positions,
        allocation_pct=allocation_pct,
    )
    return send_telegram_message(msg)


def test_telegram_connection(token: str = None, chat_id: str = None) -> bool:
    """
    Telegram ayarlarını V8.0 (Hibrit Özel Mod V/W Soğuma & Otomatik Öğrenme) formatıyla test eder.
    """
    msg = (
        "🤖 <b>BIST 30 HİBRİT ÖZEL MOD (V8.0) PORTFÖY BOTU AKTİF!</b>\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        "✅ <b>Kapsam:</b> Sadece BIST 30 Şirketleri\n"
        "✅ <b>Strateji:</b> Hibrit Özel Mod — Hisseye Göre V-Tipi / W-Tipi Soğuma + Özel Çıkış RSI\n"
        "✅ <b>Canlı Öğrenme:</b> Her kapanan işlem (SAT) sonrası V/W tipi ve RSI seviyeleri otomatik güncellenir\n"
        "✅ <b>Portföy Kuralı:</b> Maksimum 5 Açık Hisse (%10 Pay / Hisse)"
    )
    return send_telegram_message(msg, token=token, chat_id=chat_id)


if __name__ == "__main__":
    print("Telegram bağlantısı test ediliyor...")
    test_telegram_connection()
