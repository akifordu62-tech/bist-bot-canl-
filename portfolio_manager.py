"""
BIST 30 Otomatik 5 Hisse Portföy Takip Yöneticisi
Kurallar:
- Sadece BIST 30 şirketleri alınır.
- Aynı anda en fazla 5 açık hisse taşınır (Her alım portföyün %10'u -> Maksimum %50 Borsa).
- Boş kontenjan varsa aynı gün AL veren BIST 30 hisseleri arasından RSI değeri en düşük olanlar sırayla seçilir.
- Portföy 5/5 doluyken yeni AL sinyali üretilmez.
- SAT sinyali sadece portföyde açık olan 5 hisseden biri kendi özel optimum RSI hedefine ulaştığında üretilir.
"""
import os
import json
import datetime
from typing import Dict, Any, List
from config import PORTFOLIO_CONFIG, get_optimal_rsi

PORTFOLIO_FILE = os.path.join(os.path.dirname(__file__), "portfolio_state.json")


def _default_state() -> Dict[str, Any]:
    return {
        "universe": PORTFOLIO_CONFIG.get("universe", "BIST30"),
        "max_positions": int(PORTFOLIO_CONFIG.get("max_positions", 5)),
        "allocation_pct": float(PORTFOLIO_CONFIG.get("allocation_pct", 10.0)),
        "updated_at": datetime.date.today().isoformat(),
        "last_processed_date": "",
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
    target_rsi = get_optimal_rsi(clean)
    state["open_positions"].append(
        {
            "symbol": full_sym,
            "clean_symbol": clean,
            "entry_date": dt_str,
            "entry_price": round(float(entry_price), 2),
            "entry_rsi": round(float(entry_rsi), 1),
            "target_rsi": int(target_rsi),
            "allocation_pct": state["allocation_pct"],
            "last_price": round(float(entry_price), 2),
            "last_rsi": round(float(entry_rsi), 1),
            "pnl_pct": 0.0,
        }
    )
    save_portfolio_state(state)
    return True, f"{clean} portföye eklendi ({len(state['open_positions'])}/{max_pos})."


def remove_manual_position(symbol: str, exit_price: float = None) -> tuple[bool, str]:
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
    return True, f"{clean} portföyden çıkarıldı ({len(remaining)}/{state['max_positions']})."
