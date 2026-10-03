"""
BIST Endeks Hisseleri Modülü (Dinamik ve Otomatik Güncellenen Liste)
Borsa İstanbul'un resmi BIST 100 ve BIST 30 bileşenlerini çeker veya yerleşik listeden yükler.
"""
import os
import json
from typing import List

CACHE_FILE = os.path.join(os.path.dirname(__file__), "bist_symbols_cache.json")

# 100 Resmi BIST 100 Hissesi (Yedek & Çevrimdışı Güvenlik Listesi)
FALLBACK_BIST_100 = [
    "AEFES.IS", "AGHOL.IS", "AHGAZ.IS", "AKBNK.IS", "AKCNS.IS", "AKFYE.IS", "AKSA.IS", "AKSEN.IS",
    "ALARK.IS", "ALBRK.IS", "ALFAS.IS", "ARCLK.IS", "ARDYZ.IS", "ASELS.IS", "ASTOR.IS", "BERA.IS",
    "BIACH.IS", "BIMAS.IS", "BINHO.IS", "BRSAN.IS", "BRYAT.IS", "BSOKE.IS", "BTCIM.IS", "CANTE.IS",
    "CCOLA.IS", "CIMSA.IS", "CWENE.IS", "DOAS.IS", "DOHOL.IS", "EBEBK.IS", "ECILC.IS", "ECZYT.IS",
    "EGEEN.IS", "EKGYO.IS", "ENERY.IS", "ENKAI.IS", "EREGL.IS", "EUPWR.IS", "FROTO.IS", "GARAN.IS",
    "GENIL.IS", "GESAN.IS", "GOKNR.IS", "GUBRF.IS", "HALKB.IS", "HEKTS.IS", "ISCTR.IS", "ISGYO.IS",
    "ISMEN.IS", "IZENR.IS", "KAYSE.IS", "KCAER.IS", "KCHOL.IS", "KLSER.IS", "KMPUR.IS", "KONTR.IS",
    "KONYA.IS", "KOZAA.IS", "KOZAL.IS", "KRDMD.IS", "KZBGY.IS", "MAVI.IS", "MGROS.IS", "MIATK.IS",
    "ODAS.IS", "OTKAR.IS", "OYAKC.IS", "PASEU.IS", "PETKM.IS", "PGSUS.IS", "QUAGR.IS", "REEDR.IS",
    "SAHOL.IS", "SASA.IS", "SDTTR.IS", "SISE.IS", "SKBNK.IS", "SMRTG.IS", "SOKM.IS", "TABGD.IS",
    "TAVHL.IS", "TCELL.IS", "THYAO.IS", "TKFEN.IS", "TOASO.IS", "TSKB.IS", "TTKOM.IS", "TTRAK.IS",
    "TUKAS.IS", "TUPRS.IS", "ULKER.IS", "VAKBN.IS", "VESBE.IS", "VESTL.IS", "YEOTK.IS", "YKBNK.IS",
    "YYLGD.IS", "ZOREN.IS"
]

FALLBACK_BIST_30 = [
    "AKBNK.IS", "ALARK.IS", "ASELS.IS", "ASTOR.IS", "BIMAS.IS", "BRSAN.IS", "DOAS.IS", "EKGYO.IS",
    "ENKAI.IS", "EREGL.IS", "FROTO.IS", "GARAN.IS", "GUBRF.IS", "HEKTS.IS", "ISCTR.IS", "KCHOL.IS",
    "KONTR.IS", "KOZAL.IS", "KRDMD.IS", "OYAKC.IS", "PETKM.IS", "PGSUS.IS", "SAHOL.IS", "SASA.IS",
    "SISE.IS", "TCELL.IS", "THYAO.IS", "TOASO.IS", "TUPRS.IS", "YKBNK.IS"
]

def fetch_live_index_symbols(index_code: str = "XU100") -> List[str]:
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

def get_bist_symbols(index_name: str = "BIST100", force_refresh: bool = False) -> List[str]:
    """
    Önbellekten veya canlı kaynaktan BIST hisse listesini döndürür.
    Hata durumunda 100 hisselik resmi güvenlik listesini kullanır.
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

BIST_100_SYMBOLS = get_bist_symbols("BIST100")
BIST_30_SYMBOLS = get_bist_symbols("BIST30")
