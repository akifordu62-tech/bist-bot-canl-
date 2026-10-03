"""
Strateji ve Sistem Konfigürasyonu
"""
from dataclasses import dataclass
from datetime import datetime

@dataclass
class StrategyConfig:
    # 1. Girdi Tanımları (Çıkış Desteği Kaldırılmış Sürüm)
    nv_avg_length: int = 5          # Net Hacim Ortalaması Periyodu
    neg_flow_bars: int = 3          # Negatif Akış Onayı (Adet)
    rsi_length: int = 14            # RSI Periyodu
    rsi_overbought: int = 70        # RSI Aşırı Alım Seviyesi (Doğrudan Çıkış Sinyali)
    
    # Tarih Filtresi
    use_date_filter: bool = True
    start_year: int = 2020
    start_month: int = 1
    start_day: int = 1

    @property
    def start_date_str(self) -> str:
        return f"{self.start_year:04d}-{self.start_month:02d}-{self.start_day:02d}"

import os

# Telegram Bot Ayarları
# Telegram'da @BotFather üzerinden bot oluşturup token alabilirsiniz.
# Chat ID için @userinfobot veya @getmyid_bot kullanabilirsiniz.
TELEGRAM_CONFIG = {
    "enabled": True,
    "token": "8382928514:AAHDsLNZ4hu1k0O0mxEo51ij7jez_3DmI94",
    "chat_id": "966017140"
}