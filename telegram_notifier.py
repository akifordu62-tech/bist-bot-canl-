"""
Telegram Bildirim Modülü (V9.0 - BIST 30 Süper Lider + Akıllı Çift Kalkan [XU100 & Hisse EMA50])
- Endeks rejimi (XU100 > EMA50) durumunu, PPF kalkanını, o gün yeni tetiklenen Süper Lider AL / SAT / Çift EMA50 Stop
  sinyallerini, açık Süper Lider işlemlerini (ilk giriş tarihine göre % farkla) ve anlık Süper Lider radarını gönderir.
"""
import os
from typing import List, Dict, Any, Optional
import requests
from config import TELEGRAM_CONFIG, get_stock_risk_note


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
    allocation_pct: float = 25.0,
    all_stocks_list: List[Dict[str, Any]] = None,
    xu_info: Optional[Dict[str, Any]] = None,
    last_closed_info: Optional[Dict[str, Any]] = None,
    meta_info: Optional[Dict[str, Any]] = None,
) -> str:
    """
    V9.0 BIST 30 Süper Lider + Akıllı Çift Kalkan (XU100 & Hisse EMA50) günlük Telegram raporunu oluşturur.
    """
    bought_list = bought_list or []
    sold_list = sold_list or []
    open_positions = open_positions or []
    all_stocks_list = all_stocks_list or []
    xu_info = xu_info or {}
    meta_info = meta_info or {}

    xu_close = float(xu_info.get("close", 0.0) or 0.0)
    xu_ema50 = float(xu_info.get("ema50", 0.0) or 0.0)
    xu_above50 = bool(xu_info.get("above_ema50", True))
    xu_chg_pct = xu_info.get("daily_change_pct")
    xu_chg_str = f" (<b>%{float(xu_chg_pct):+.2f}</b>)" if xu_chg_pct is not None else ""
    xu_diff_pct = ((xu_close - xu_ema50) / xu_ema50 * 100.0) if xu_ema50 > 0 else 0.0

    lines = [
        "📊 <b>BIST 30 SÜPER LİDER & ÇİFT KALKAN RAPORU</b>",
        f"📅 <b>Tarih:</b> {date_str} | <b>Mod:</b> V9.0 (Süper Lider + Çift EMA50)",
        "━━━━━━━━━━━━━━━━━━━━",
    ]

    # 1. BÖLÜM: ENDEKS REJİMİ (XU100 vs EMA50)
    if xu_close > 0 and xu_ema50 > 0:
        if xu_above50:
            lines.append("🛡️ <b>ENDEKS REJİMİ (XU100):</b> 🟢 <b>POZİTİF (ALIM AÇIK)</b>")
            lines.append(
                f"• XU100: <b>{xu_close:,.2f}</b>{xu_chg_str} | EMA50: {xu_ema50:,.2f} (EMA50 Üstü: <b>%{xu_diff_pct:+.1f}</b>)"
            )
            lines.append("• <i>Kural: Süper Lider şartını sağlayanlarda yeni AL açık (Önerilen: 3–4 Lider × %25–%33).</i>")
        else:
            lines.append("🛡️ <b>ENDEKS REJİMİ (XU100):</b> 🔴 <b>NEGATİF (PPF KALKANI AKTİF)</b>")
            lines.append(
                f"• XU100: <b>{xu_close:,.2f}</b>{xu_chg_str} | EMA50: {xu_ema50:,.2f} (EMA50'ye Uzaklık: <b>%{xu_diff_pct:+.1f}</b>)"
            )
            lines.append("• <i>Kural: Endeks EMA50 üstüne çıkana kadar YENİ ALIM KAPALI. Açık hissede de EMA50 kırılırsa STOP ➔ PPF!</i>")
        lines.append("")

    # 2. BÖLÜM: BUGÜN YENİ TETİKLENEN SÜPER LİDER AL / SAT / ÇİFT EMA50 STOP
    mentioned_risk_syms = []

    if bought_list:
        sorted_buys = sorted(bought_list, key=lambda x: float(x.get("rs_score", x.get("rs60", 0.0))), reverse=True)
        lines.append(f"🟢 <b>BUGÜN YENİ SÜPER LİDER AL SİNYALİ ({len(sorted_buys)} Hisse):</b>")
        for b in sorted_buys:
            csym = b["clean_symbol"]
            rnote = get_stock_risk_note(csym)
            mark = "!" if rnote else ""
            if rnote:
                mentioned_risk_syms.append(csym)
            rs60_v = float(b.get("rs60", 0.0))
            d52_v = float(b.get("dist_52h", 0.0))
            ema50_v = float(b.get("ema50", 0.0))
            lines.append(
                f"• <b>#{csym}★{mark}</b> | Fiyat: <b>{b['price']:.2f} TL</b> | EMA50: {ema50_v:.2f} TL"
            )
            lines.append(
                f"  ↳ RSI: {b['rsi']:.1f} ➔ Hedef: <b>RSI {b['target_rsi']}</b> | RS60: <b>%{rs60_v:+.1f}</b> | Zirve: %{d52_v:+.1f}"
            )

    if sold_list:
        if bought_list:
            lines.append("")
        rsi_sells = [s for s in sold_list if "EMA50" not in str(s.get("exit_reason", ""))]
        ema_stops = [s for s in sold_list if "EMA50" in str(s.get("exit_reason", ""))]

        if rsi_sells:
            lines.append(f"🔴 <b>BUGÜN HEDEF RSI SAT SİNYALİ ({len(rsi_sells)} Hisse):</b>")
            for s in rsi_sells:
                ret_val = float(s.get("return_pct", 0.0))
                sign = "+" if ret_val >= 0 else ""
                s_dt = s.get("entry_date_short") or s.get("entry_date", "-")
                lines.append(
                    f"• <b>#{s['clean_symbol']}</b> | {s['entry_price']:.2f} ➔ {s['exit_price']:.2f} TL "
                    f"(<b>%{sign}{ret_val:.1f}</b> | İlk AL: {s_dt} | Hedef RSI {s['target_rsi']} Kırıldı)"
                )

        if ema_stops:
            if rsi_sells:
                lines.append("")
            lines.append(f"🛡️ <b>BUGÜN ÇİFT EMA50 STOP — PPF'YE GEÇ ({len(ema_stops)} Hisse):</b>")
            for s in ema_stops:
                ret_val = float(s.get("return_pct", 0.0))
                sign = "+" if ret_val >= 0 else ""
                s_dt = s.get("entry_date_short") or s.get("entry_date", "-")
                lines.append(
                    f"• <b>#{s['clean_symbol']}</b> | {s['entry_price']:.2f} ➔ {s['exit_price']:.2f} TL "
                    f"(<b>%{sign}{ret_val:.1f}</b> | İlk AL: {s_dt} | XU100 & Hisse EMA50 Altı)"
                )

    if not bought_list and not sold_list:
        lines.append("⚪ <b>Bugün Yeni İşlem / Stop:</b> Bugün yeni AL, SAT veya Çift EMA50 Stop tetiklenmedi.")

    # 3. BÖLÜM: AÇIK SÜPER LİDER İŞLEMLERİ
    open_cnt = len(open_positions)
    lines.append("")
    if open_cnt > 0:
        lines.append(f"💼 <b>AÇIK SÜPER LİDER İŞLEMLERİ ({open_cnt}/30 Hisse):</b>")
        pre_lines = [
            "#  HİSSE  FİYAT  RSI>HD SİNYAL  FARK%",
            "─────────────────────────────────────",
        ]
        sorted_open = sorted(open_positions, key=lambda x: float(x.get("last_rsi", 50.0)))
        for idx, pos in enumerate(sorted_open, 1):
            csym_raw = str(pos.get("clean_symbol", "")).strip().upper()
            rnote = get_stock_risk_note(csym_raw)
            if rnote:
                mentioned_risk_syms.append(csym_raw)
            sym_col = (f"{csym_raw[:5]}!" if rnote else csym_raw[:5]).ljust(6)
            price = float(pos.get("last_price", pos.get("entry_price", 0.0)))
            p_str = f"{price:6.1f}" if price >= 100.0 else f"{price:6.2f}"
            rsi_int = int(round(float(pos.get("last_rsi", 50.0))))
            trsi_int = int(pos.get("target_rsi", 72))
            rsi_str = f"{rsi_int:2d}>{trsi_int:2d}"

            ed = str(pos.get("entry_date", ""))
            ed_short = str(pos.get("entry_date_short", ""))
            if not ed_short:
                ed_short = f"{ed[8:10]}.{ed[5:7]}" if len(ed) >= 10 else "AÇIK"
            sig_str = f"{ed_short[:5]:<6}"
            pnl = float(pos.get("pnl_pct", 0.0))
            diff_str = f"{pnl:+5.1f}%"
            pre_lines.append(f"{idx:02d} {sym_col}{p_str}  {rsi_str} {sig_str} {diff_str}")
        lines.append("<pre>" + "\n".join(pre_lines) + "</pre>")

        # Her açık hissenin Çift Kalkan EMA50 stop seviyesini satırda göster
        ema_notes = []
        for pos in sorted_open:
            csym = pos["clean_symbol"]
            e50 = float(pos.get("ema50", 0.0) or 0.0)
            lp = float(pos.get("last_price", 0.0) or 0.0)
            if e50 > 0:
                status_icon = "✓" if lp >= e50 else "⚠️"
                ema_notes.append(f"<b>#{csym}</b>: {e50:.2f} {status_icon}")
        if ema_notes:
            lines.append("🛡️ <i>EMA50 Kalkan Seviyeleri:</i> " + " | ".join(ema_notes))
    else:
        lines.append("💼 <b>AÇIK SÜPER LİDER İŞLEMLERİ (0/30 — %100 NAKİT / PPF):</b>")
        lines.append("• <i>Şu an açık işlem bulunmuyor — kasa %100 PPF kalkanında korunuyor.</i>")
        if last_closed_info and last_closed_info.get("clean_symbol"):
            lc_ret = float(last_closed_info.get("return_pct", 0.0))
            lc_sign = "+" if lc_ret >= 0 else ""
            lines.append(
                f"• <i>Son kapanan işlem: <b>#{last_closed_info['clean_symbol']}</b> "
                f"({last_closed_info.get('exit_date_disp', last_closed_info.get('exit_date', ''))} | "
                f"%{lc_sign}{lc_ret:.1f} | {last_closed_info.get('exit_reason', '')})</i>"
            )

    # 4. BÖLÜM: ANLIK SÜPER LİDER RADARI (RS60 >= %15 & 52H >= -%15 & EMA200 Üstü)
    if all_stocks_list:
        super_now = [x for x in all_stocks_list if x.get("is_super_leader")]
        super_now.sort(key=lambda x: float(x.get("rs60", 0.0)), reverse=True)

        lines.append("")
        lines.append("━━━━━━━━━━━━━━━━━━━━")
        lines.append(f"⭐ <b>ANLIK SÜPER LİDER RADARI ({len(super_now)}/30 Hisse):</b>")
        if super_now:
            for idx, item in enumerate(super_now, 1):
                csym = item["clean_symbol"]
                rnote = get_stock_risk_note(csym)
                mark = "!" if rnote else ""
                if rnote:
                    mentioned_risk_syms.append(csym)
                p = float(item["price"])
                e50 = float(item.get("ema50", 0.0))
                e50_ok = "✓" if p >= e50 else "⚠️"
                rsi_v = float(item["rsi"])
                trsi_v = int(item["target_rsi"])
                rs60_v = float(item.get("rs60", 0.0))
                d52_v = float(item.get("dist_52h", 0.0))
                open_tag = " [AÇIK]" if item.get("has_active_signal") else ""
                lines.append(
                    f"{idx}. <b>#{csym}★{mark}</b>{open_tag} | {p:.2f} TL (EMA50: {e50:.2f} {e50_ok}) "
                    f"| RSI: {rsi_v:.1f}>{trsi_v} | RS60: <b>%{rs60_v:+.1f}</b> | Zirve: %{d52_v:+.1f}"
                )
        else:
            lines.append("• <i>Şu an 3 Süper Lider şartını birden sağlayan BIST 30 hissesi yok.</i>")

        # 5. BÖLÜM: SINIRA EN YAKIN PUSUDaKİ ADAYLAR (EMA200 Üstü & RS60 >= %8 ama henüz Süper Lider olmamış)
        near_list = [
            x
            for x in all_stocks_list
            if (not x.get("is_super_leader"))
            and x.get("above_ema200")
            and float(x.get("rs60", -999.0)) >= 8.0
        ]
        near_list.sort(key=lambda x: float(x.get("rs60", 0.0)), reverse=True)
        if near_list:
            lines.append("")
            lines.append(f"👀 <b>Sınıra Yakın Pusudaki Liderler (EMA200 Üstü):</b>")
            for item in near_list[:5]:
                csym = item["clean_symbol"]
                rnote = get_stock_risk_note(csym)
                mark = "!" if rnote else ""
                lines.append(
                    f"• <b>#{csym}{mark}</b> | {item['price']:.2f} TL | RSI: {item['rsi']:.1f}>{item['target_rsi']} "
                    f"| RS60: %{float(item.get('rs60', 0.0)):+.1f} | Zirve: %{float(item.get('dist_52h', 0.0)):+.1f}"
                )

    # Riskli hisseler sadece yukarıdaki listelerde (AL / Açık / Radar) geçtiyse not düş
    unique_risks = list(dict.fromkeys(mentioned_risk_syms))
    if unique_risks:
        lines.append("")
        lines.append("⚠️ <b>BİLANÇO / HABER UYARISI ('!' İşaretliler):</b>")
        for rc in unique_risks:
            lines.append(f"• <b>#{rc}!</b> ➔ {get_stock_risk_note(rc)}")

    # Alt bilgi: Veri kaynağı, taranan hisse sayısı ve İstanbul saati doğrulaması
    if meta_info:
        scanned_cnt = int(meta_info.get("scanned_count", len(all_stocks_list) or 0))
        total_cnt = int(meta_info.get("total_count", max_positions or 30))
        fresh_cnt = int(meta_info.get("fresh_count", scanned_cnt))
        src_lbl = str(meta_info.get("data_source", "TradingView"))
        run_ist = str(meta_info.get("run_time_ist", ""))
        stale_warn = f" (⚠️ {scanned_cnt - fresh_cnt} eski bar)" if fresh_cnt < scanned_cnt else ""
        time_part = f" | {run_ist}" if run_ist else ""
        lines.append("━━━━━━━━━━━━━━━━━━━━")
        lines.append(
            f"✅ <i>Tarama: {scanned_cnt}/{total_cnt} BIST 30{stale_warn} | Kaynak: {src_lbl}{time_part}</i>"
        )

    return "\n".join(lines)


def send_bist30_daily_report(
    date_str: str,
    bought_list: List[Dict[str, Any]] = None,
    sold_list: List[Dict[str, Any]] = None,
    open_positions: List[Dict[str, Any]] = None,
    skipped_list: List[Dict[str, Any]] = None,
    max_positions: int = 30,
    allocation_pct: float = 25.0,
    all_stocks_list: List[Dict[str, Any]] = None,
    xu_info: Optional[Dict[str, Any]] = None,
    last_closed_info: Optional[Dict[str, Any]] = None,
    meta_info: Optional[Dict[str, Any]] = None,
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
        xu_info=xu_info,
        last_closed_info=last_closed_info,
        meta_info=meta_info,
    )
    return send_telegram_message(msg)


def test_telegram_connection(token: str = None, chat_id: str = None) -> bool:
    """
    Telegram ayarlarını V9.0 (BIST 30 Süper Lider + Akıllı Çift Kalkan) formatıyla test eder.
    """
    msg = (
        "🤖 <b>BIST 30 SÜPER LİDER + AKILLI ÇİFT KALKAN BOTU (V9.0) AKTİF!</b>\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        "✅ <b>Kapsam:</b> BIST 30 Şirketleri (30 Hisse)\n"
        "✅ <b>Süper Lider Filtresi:</b> Close > EMA200 | RS60 ≥ %15 | 52H Zirve ≥ -%15\n"
        "✅ <b>Endeks Kalkanı:</b> XU100 > EMA50 değilken yeni AL kapalı (Nakit PPF'de)\n"
        "✅ <b>Akıllı Çift Stop:</b> XU100 < EMA50 VE Hisse < EMA50 ise koruma stopu ➔ PPF\n"
        "✅ <b>Kâr Al Çıkışı:</b> Orijinal V8.0 hisseye özel optimum Çıkış RSI (68–78)"
    )
    return send_telegram_message(msg, token=token, chat_id=chat_id)


if __name__ == "__main__":
    print("Telegram bağlantısı test ediliyor...")
    test_telegram_connection()
