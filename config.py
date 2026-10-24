"""
Strateji, Hisseye Özel Optimum RSI ve Portföy Konfigürasyonu (V6.0)
"""
import os
from dataclasses import dataclass

# 2020'den Günümüze Backtest Sonuçlarına Göre Hisse Bazlı En Kârlı RSI Çıkış Seviyeleri
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


def get_optimal_rsi(symbol: str = None, default: int = 72) -> int:
    """
    Hissenin 2020'den günümüze backtest ile belirlenmiş en kârlı özel RSI çıkış seviyesini döndürür.
    """
    if not symbol:
        return default
    clean = symbol.replace(".IS", "").strip().upper()
    return OPTIMAL_RSI_MAP.get(clean, default)


@dataclass
class StrategyConfig:
    # V6.0 Hisseye Özel Optimum RSI Strateji Parametreleri
    nv_avg_length: int = 5                      # Net Hacim Ortalaması Periyodu (SMA 5)
    rsi_length: int = 14                        # Wilder RSI Periyodu
    rsi_max_buy: float = 65.0                   # Tepe alımlarını engelleyen üst RSI filtresi
    use_per_stock_optimal_rsi: bool = True      # Hisse bazlı özel optimum RSI çıkışı aktif
    rsi_overbought: int = 72                    # Manuel mod seçilirse kullanılacak sabit RSI seviyesi
    use_fast_2bar_neg_flow: bool = True         # 2 ve 3 bar negatif akış dönüşlerini yakalar

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
