"""
BIST Endeks Hisseleri Modülü (Dinamik ve Otomatik Güncellenen Liste)
Borsa İstanbul'un resmi BIST 30 ve BIST 100 bileşenlerini çeker veya yerleşik listeden yükler.
"""
import os
import json
from typing import List

CACHE_FILE = os.path.join(os.path.dirname(__file__), "bist_symbols_cache.json")

# Resmi BIST 30 Hisseleri (30 Şirket)
FALLBACK_BIST_30 = [
    "AEFES.IS", "AKBNK.IS", "ASELS.IS", "ASTOR.IS", "BIMAS.IS", "EKGYO.IS",
    "ENKAI.IS", "EREGL.IS", "FROTO.IS", "GARAN.IS", "GUBRF.IS", "ISCTR.IS",
    "KCHOL.IS", "KRDMD.IS", "MGROS.IS", "PETKM.IS", "PGSUS.IS", "SAHOL.IS",
    "SASA.IS", "SISE.IS", "TAVHL.IS", "TCELL.IS", "THYAO.IS", "TOASO.IS",
    "TRALT.IS", "TRMET.IS", "TTKOM.IS", "TUPRS.IS", "VAKBN.IS", "YKBNK.IS",
]

# Resmi BIST 100 Hisseleri (100 Şirket)
FALLBACK_BIST_100 = [
    "AEFES.IS", "AGHOL.IS", "AHGAZ.IS", "AKBNK.IS", "AKCNS.IS", "AKFYE.IS", "AKSA.IS", "AKSEN.IS",
    "ALARK.IS", "ALBRK.IS", "ALTNY.IS", "ANHYT.IS", "ANSGR.IS", "ARCLK.IS", "ASELS.IS", "ASTOR.IS",
    "AYGAZ.IS", "BERA.IS", "BIMAS.IS", "BINHO.IS", "BRSAN.IS", "BRYAT.IS", "BTCIM.IS", "CANTE.IS",
    "CCOLA.IS", "CIMSA.IS", "CVKMD.IS", "CWENE.IS", "DOAS.IS", "DOHOL.IS", "ECILC.IS", "ECZYT.IS",
    "EGEEN.IS", "EGGUB.IS", "EKGYO.IS", "ENERY.IS", "ENJSA.IS", "ENKAI.IS", "ENTRA.IS", "EREGL.IS",
    "EUREN.IS", "FENER.IS", "FROTO.IS", "GARAN.IS", "GLRMK.IS", "GLYHO.IS", "GRSEL.IS", "GUBRF.IS",
    "GWIND.IS", "HALKB.IS", "HEKTS.IS", "ISCTR.IS", "ISDMR.IS", "ISMEN.IS", "KARSN.IS", "KATMR.IS",
    "KCAER.IS", "KCHOL.IS", "KORDS.IS", "KRDMD.IS", "LMKDC.IS", "MAVI.IS", "MGROS.IS", "MPARK.IS",
    "OBAMS.IS", "ODAS.IS", "OTKAR.IS", "OYAKC.IS", "PAHOL.IS", "PETKM.IS", "PGSUS.IS", "RGYAS.IS",
    "RYSAS.IS", "SAHOL.IS", "SASA.IS", "SISE.IS", "SNGYO.IS", "SOKM.IS", "TABGD.IS", "TAVHL.IS",
    "TCELL.IS", "TCKRC.IS", "THYAO.IS", "TKFEN.IS", "TOASO.IS", "TRALT.IS", "TRENJ.IS", "TRGYO.IS",
    "TRMET.IS", "TSKB.IS", "TTKOM.IS", "TTRAK.IS", "TUKAS.IS", "TUPRS.IS", "TURSG.IS", "ULKER.IS",
    "VAKBN.IS", "VESTL.IS", "YKBNK.IS", "ZOREN.IS",
]


def fetch_live_index_symbols(index_code: str = "XU030") -> List[str]:
    """
    Borsapy aracılığıyla Borsa İstanbul'dan resmi güncel endeks hisselerini çeker.
    """
    try:
        import borsapy as bp
        idx = bp.Index(index_code)
        symbols = idx.component_symbols
        if symbols and len(symbols) > 0:
            formatted = [f"{s.strip().upper()}.IS" for s in symbols]
            return sorted(formatted)
    except Exception:
        pass
    return []


def get_bist_symbols(index_name: str = "BIST30", force_refresh: bool = False) -> List[str]:
    """
    Önbellekten veya canlı kaynaktan BIST hisse listesini döndürür.
    """
    cache_data = {}
    if os.path.exists(CACHE_FILE):
        try:
            with open(CACHE_FILE, "r", encoding="utf-8") as f:
                cache_data = json.load(f)
        except Exception:
            cache_data = {}

    target_key = "BIST100" if "100" in index_name else "BIST30"
    code = "XU100" if target_key == "BIST100" else "XU030"
    fallback_list = FALLBACK_BIST_100 if target_key == "BIST100" else FALLBACK_BIST_30

    if force_refresh or target_key not in cache_data or not cache_data[target_key]:
        live_syms = fetch_live_index_symbols(code)
        if live_syms:
            cache_data[target_key] = live_syms
            try:
                with open(CACHE_FILE, "w", encoding="utf-8") as f:
                    json.dump(cache_data, f, ensure_ascii=False, indent=2)
            except Exception:
                pass
            return live_syms

    res = cache_data.get(target_key, [])
    return res if (res and len(res) > 0) else fallback_list


BIST_30_SYMBOLS = get_bist_symbols("BIST30")
BIST_100_SYMBOLS = get_bist_symbols("BIST100")


def is_bist30(symbol: str) -> bool:
    clean = symbol.replace(".IS", "").strip().upper()
    b30 = {s.replace(".IS", "").strip().upper() for s in BIST_30_SYMBOLS}
    return clean in b30


def get_index_membership(symbol: str) -> str:
    """
    Hissenin BIST 30 veya BIST 100 endeksine ait olup olmadığını kontrol eder.
    """
    clean = symbol.replace(".IS", "").strip().upper()
    b30 = {s.replace(".IS", "").strip().upper() for s in BIST_30_SYMBOLS}
    b100 = {s.replace(".IS", "").strip().upper() for s in BIST_100_SYMBOLS}

    if clean in b30:
        return "BIST 30 🌟"
    elif clean in b100:
        return "BIST 100 🏛️"
    else:
        return "BIST Tüm 🏢"
