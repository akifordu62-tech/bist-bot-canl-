"""
Strateji, Hisseye Özel Giriş/Soğuma/Çıkış RSI (1. Mod) ve Portföy Konfigürasyonu (V7.0)
- Her hisse kendi karakterine özel Giriş Üst RSI, SAT Sonrası Soğuma (Reset RSI / Bekleme) ve Çıkış RSI seviyelerini kullanır.
- Kapanan işlemlerden sonra yeni işlem verisiyle optimal_params.json otomatik güncellenir.
"""
import os
import json
import datetime
from dataclasses import dataclass
from typing import Dict, Any, Optional

OPTIMAL_PARAMS_FILE = os.path.join(os.path.dirname(__file__), "optimal_params.json")

# Yedek (Fallback) 2020+ Hisse Bazlı En Kârlı Çıkış RSI Haritası
OPTIMAL_RSI_MAP = {
    # BIST 30 Şirketleri (30 Hisse)
    "AEFES": 76, "AKBNK": 68, "ASELS": 76, "ASTOR": 78, "BIMAS": 69, "EKGYO": 78,
    "ENKAI": 70, "EREGL": 71, "FROTO": 78, "GARAN": 69, "GUBRF": 72, "ISCTR": 77,
    "KCHOL": 78, "KRDMD": 77, "MGROS": 78, "PETKM": 69, "PGSUS": 77, "SAHOL": 78,
    "SASA": 78, "SISE": 74, "TAVHL": 78, "TCELL": 72, "THYAO": 73, "TOASO": 77,
    "TRALT": 74, "TRMET": 76, "TTKOM": 78, "TUPRS": 78, "VAKBN": 77, "YKBNK": 78,
    # BIST 30 - BIST 100 Arası Şirketler (70 Hisse)
    "AGHOL": 78, "AHGAZ": 78, "AKCNS": 71, "AKFYE": 68, "AKSA": 74, "AKSEN": 78,
    "ALARK": 78, "ALBRK": 72, "ALTNY": 77, "ANHYT": 78, "ANSGR": 74, "ARCLK": 74,
    "AYGAZ": 78, "BERA": 77, "BINHO": 68, "BRSAN": 74, "BRYAT": 71, "BTCIM": 74,
    "CANTE": 71, "CCOLA": 75, "CIMSA": 77, "CVKMD": 68, "CWENE": 68, "DOAS": 78,
    "DOHOL": 78, "ECILC": 78, "ECZYT": 68, "EGEEN": 78, "EGGUB": 73, "ENERY": 76,
    "ENJSA": 78, "ENTRA": 72, "EUREN": 76, "FENER": 76, "GLRMK": 74, "GLYHO": 71,
    "GRSEL": 71, "GWIND": 78, "HALKB": 76, "HEKTS": 78, "ISDMR": 68, "ISMEN": 68,
    "KARSN": 76, "KATMR": 78, "KCAER": 78, "KORDS": 78, "LMKDC": 69, "MAVI": 74,
    "MPARK": 78, "OBAMS": 68, "ODAS": 78, "OTKAR": 78, "OYAKC": 74, "PAHOL": 68,
    "RGYAS": 78, "RYSAS": 77, "SNGYO": 68, "SOKM": 69, "TABGD": 68, "TCKRC": 78,
    "TKFEN": 74, "TRENJ": 74, "TRGYO": 74, "TSKB": 78, "TTRAK": 76, "TUKAS": 78,
    "TURSG": 77, "ULKER": 78, "VESTL": 75, "ZOREN": 78,
}


def load_optimal_params() -> Dict[str, Dict[str, Any]]:
    """
    Hisse bazlı özel giriş/soğuma/çıkış parametre tablosunu (optimal_params.json) okur.
    """
    if os.path.exists(OPTIMAL_PARAMS_FILE):
        try:
            with open(OPTIMAL_PARAMS_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, dict):
                return data
        except Exception:
            pass
    return {}


def save_optimal_params(params_map: Dict[str, Dict[str, Any]]) -> None:
    """
    Güncellenen hisse bazlı özel RSI parametrelerini optimal_params.json dosyasına kaydeder.
    """
    sorted_map = {k: params_map[k] for k in sorted(params_map.keys())}
    with open(OPTIMAL_PARAMS_FILE, "w", encoding="utf-8") as f:
        json.dump(sorted_map, f, ensure_ascii=False, indent=2)


def get_stock_params(symbol: Optional[str] = None, default_exit: int = 72) -> Dict[str, Any]:
    """
    Belirtilen hissenin güncel özel parametrelerini döndürür:
    - exit_rsi: Özel satış hedefi (68-78)
    - reset_rsi: SAT sonrası yeni AL için RSI'ın inmesi gereken soğuma seviyesi (veya None)
    - max_buy_rsi: Alım için izin verilen en yüksek RSI sınırı
    - cooldown_bars: SAT sonrası minimum bekleme bar sayısı
    - no_higher_bars: SAT fiyatından daha pahalıya almama süresi (bar)
    """
    if not symbol:
        return {
            "exit_rsi": int(default_exit),
            "reset_rsi": None,
            "max_buy_rsi": 65.0,
            "cooldown_bars": 0,
            "no_higher_bars": 0,
            "calibrated_at": "",
        }

    clean = symbol.replace(".IS", "").strip().upper()
    all_params = load_optimal_params()
    if clean in all_params and isinstance(all_params[clean], dict):
        raw = all_params[clean]
        rst = raw.get("reset_rsi")
        return {
            "exit_rsi": int(raw.get("exit_rsi", OPTIMAL_RSI_MAP.get(clean, default_exit))),
            "reset_rsi": float(rst) if rst is not None else None,
            "max_buy_rsi": float(raw.get("max_buy_rsi", 65.0)),
            "cooldown_bars": int(raw.get("cooldown_bars", 0)),
            "no_higher_bars": int(raw.get("no_higher_bars", 0)),
            "calibrated_at": str(raw.get("calibrated_at", "")),
        }

    return {
        "exit_rsi": int(OPTIMAL_RSI_MAP.get(clean, default_exit)),
        "reset_rsi": None,
        "max_buy_rsi": 65.0,
        "cooldown_bars": 0,
        "no_higher_bars": 0,
        "calibrated_at": datetime.date.today().isoformat(),
    }


def format_stock_entry_rule(params: Dict[str, Any]) -> str:
    """
    Hissenin özel giriş ve soğuma kuralını okunabilir Türkçe metne çevirir.
    """
    parts = []
    rst = params.get("reset_rsi")
    max_buy = float(params.get("max_buy_rsi", 65.0))
    cd = int(params.get("cooldown_bars", 0))
    nh = int(params.get("no_higher_bars", 0))

    if rst is not None:
        parts.append(f"SAT sonrası RSI ≤ {int(rst)} Soğuma")
    parts.append(f"Alım RSI < {int(max_buy)}")
    if cd > 0:
        parts.append(f"{cd}g Bekle")
    if nh > 0:
        parts.append(f"{nh}g Pahalıdan Alma")

    if rst is None and max_buy >= 65.0 and cd == 0 and nh == 0:
        return "Güçlü Trend (Alım RSI < 65, Ek Bekleme Yok)"
    return " | ".join(parts)


def get_optimal_rsi(symbol: Optional[str] = None, default: int = 72) -> int:
    """
    Hissenin güncel özel RSI çıkış seviyesini döndürür.
    """
    if not symbol:
        return default
    return int(get_stock_params(symbol, default_exit=default)["exit_rsi"])


@dataclass
class StrategyConfig:
    # V7.0 1. Mod: Hisseye Özel Giriş/Soğuma + Çıkış RSI Strateji Parametreleri
    nv_avg_length: int = 5                        # Net Hacim Ortalaması Periyodu (SMA 5)
    rsi_length: int = 14                          # Wilder RSI Periyodu
    rsi_max_buy: float = 65.0                     # Manuel mod seçilirse kullanılacak üst alım RSI sınırı
    use_per_stock_optimal_rsi: bool = True        # Hisse bazlı özel optimum Çıkış RSI aktif
    use_per_stock_entry_cooldown: bool = True     # 1. Mod: Hisse bazlı özel Giriş & Soğuma RSI aktif
    rsi_overbought: int = 72                      # Manuel mod seçilirse kullanılacak sabit çıkış RSI seviyesi
    use_fast_2bar_neg_flow: bool = True           # 2 ve 3 bar negatif akış dönüşlerini yakalar

    # Portföy Kuralları (Sadece BIST 30 | %10 Alım x Maksimum 5 Hisse)
    max_open_positions: int = 5
    position_size_pct: float = 10.0

    # Tarih Filtresi (2020'den günümüze)
    use_date_filter: bool = True
    start_year: int = 2020
    start_month: int = 1
    start_day: int = 1

    @property
    def start_date_str(self) -> str:
        return f"{self.start_year:04d}-{self.start_month:02d}-{self.start_day:02d}"


PORTFOLIO_CONFIG = {
    "universe": "BIST30",
    "max_positions": 5,
    "allocation_pct": 10.0,
}

# Telegram Bot Ayarları
TELEGRAM_CONFIG = {
    "enabled": True,
    "token": "8382928514:AAHDsLNZ4hu1k0O0mxEo51ij7jez_3DmI94",
    "chat_id": "966017140",
}
