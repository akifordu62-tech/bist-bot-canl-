"""
BIST 30 Otomatik 5 Hisse Portföy Takip Yöneticisi (V7.0 - 1. Mod Hisseye Özel Giriş/Soğuma & Otomatik Öğrenme)
Kurallar:
- Sadece BIST 30 şirketleri alınır.
- Aynı anda en fazla 5 açık hisse taşınır (Her alım portföyün %10'u -> Maksimum %50 Borsa).
- Boş kontenjan varsa aynı gün AL veren (soğuma kuralını geçmiş) BIST 30 hisseleri arasından RSI değeri en düşük olanlar sırayla seçilir.
- Açık pozisyon devam ederken giriş anındaki hedef RSI kilitli kalır; pozisyon SAT ile kapandığı anda yeni işlem verisi eklenerek hissenin özel seviyeleri yeniden hesaplanır.
"""
import os
import json
import datetime
from typing import Dict, Any
from config import PORTFOLIO_CONFIG, get_optimal_rsi, get_stock_params, format_stock_entry_rule

PORTFOLIO_FILE = os.path.join(os.path.dirname(__file__), "portfolio_state.json")


def _default_state() -> Dict[str, Any]:
    return {
        "universe": PORTFOLIO_CONFIG.get("universe", "BIST30"),
        "max_positions": int(PORTFOLIO_CONFIG.get("max_positions", 5)),
        "allocation_pct": float(PORTFOLIO_CONFIG.get("allocation_pct", 10.0)),
        "updated_at": datetime.date.today().isoformat(),
        "last_processed_date": "",
        "last_calibrated_month": "",
        "open_positions": [],
        "closed_history": [],
        "last_daily_actions": {
            "date": "",
            "bought": [],
            "sold": [],
            "skipped": [],
        },
    }


def load_portfolio_state() -> Dict[str, Any]:
    if os.path.exists(PORTFOLIO_FILE):
        try:
            with open(PORTFOLIO_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            base = _default_state()
            base.update(data)
            base["max_positions"] = int(PORTFOLIO_CONFIG.get("max_positions", 5))
            base["allocation_pct"] = float(PORTFOLIO_CONFIG.get("allocation_pct", 10.0))
            return base
        except Exception:
            pass
    return _default_state()


def save_portfolio_state(state: Dict[str, Any]) -> None:
    state["updated_at"] = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
    if len(state.get("closed_history", [])) > 100:
        state["closed_history"] = state["closed_history"][-100:]
    with open(PORTFOLIO_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)


def add_manual_position(
    symbol: str,
    entry_price: float,
    entry_date: str = None,
    entry_rsi: float = 50.0,
) -> tuple[bool, str]:
    """
    Web arayüzünden manuel olarak BIST 30 hissesi eklemek için yardımcı fonksiyon.
    """
    state = load_portfolio_state()
    max_pos = state["max_positions"]
    clean = symbol.replace(".IS", "").strip().upper()
    full_sym = f"{clean}.IS"

    if any(p["clean_symbol"] == clean for p in state["open_positions"]):
        return False, f"{clean} zaten portföyde açık durumda."

    if len(state["open_positions"]) >= max_pos:
        return False, f"Portföy kontenjanı dolu ({max_pos}/{max_pos}). Yeni hisse eklenemez."

    dt_str = entry_date or datetime.date.today().isoformat()
    sparams = get_stock_params(clean)
    target_rsi = int(sparams["exit_rsi"])
    state["open_positions"].append(
        {
            "symbol": full_sym,
            "clean_symbol": clean,
            "entry_date": dt_str,
            "entry_price": round(float(entry_price), 2),
            "entry_rsi": round(float(entry_rsi), 1),
            "target_rsi": target_rsi,
            "entry_rule": format_stock_entry_rule(sparams),
            "allocation_pct": state["allocation_pct"],
            "last_price": round(float(entry_price), 2),
            "last_rsi": round(float(entry_rsi), 1),
            "pnl_pct": 0.0,
        }
    )
    save_portfolio_state(state)
    return True, f"{clean} portföye eklendi ({len(state['open_positions'])}/{max_pos} | Kilitli Çıkış Hedefi: RSI {target_rsi})."


def remove_manual_position(symbol: str, exit_price: float = None, df_for_recal=None) -> tuple[bool, str]:
    """
    Web arayüzünden açık bir pozisyonu manuel kapatmak/silmek için yardımcı fonksiyon.
    """
    state = load_portfolio_state()
    clean = symbol.replace(".IS", "").strip().upper()
    remaining = []
    removed = None

    for pos in state["open_positions"]:
        if pos["clean_symbol"] == clean:
            removed = pos
        else:
            remaining.append(pos)

    if removed is None:
        return False, f"{clean} açık portföyde bulunamadı."

    xp = float(exit_price) if exit_price is not None else float(removed.get("last_price", removed["entry_price"]))
    ep = float(removed["entry_price"])
    ret_pct = ((xp - ep) / ep * 100.0) if ep > 0 else 0.0

    recal_note = ""
    if df_for_recal is not None and not df_for_recal.empty:
        try:
            from strategy import recalibrate_and_save_stock
            new_p = recalibrate_and_save_stock(clean, df_for_recal)
            recal_note = f" | Güncel Seviyeler: Çıkış RSI {new_p['exit_rsi']} ({new_p['rule_summary']})"
        except Exception:
            pass

    state["closed_history"].append(
        {
            "symbol": removed["symbol"],
            "clean_symbol": clean,
            "entry_date": removed["entry_date"],
            "exit_date": datetime.date.today().isoformat(),
            "entry_price": round(ep, 2),
            "exit_price": round(xp, 2),
            "return_pct": round(ret_pct, 2),
            "target_rsi": removed["target_rsi"],
            "reason": "Manuel Çıkış",
        }
    )
    state["open_positions"] = remaining
    save_portfolio_state(state)
    return True, f"{clean} portföyden çıkarıldı ({len(remaining)}/{state['max_positions']}){recal_note}."
