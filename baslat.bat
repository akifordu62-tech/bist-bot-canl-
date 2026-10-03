@echo off
chcp 65001 > nul
title BIST Sinyal & Analiz Paneli
echo ======================================================
echo    BIST 100 Sinyal & Analiz Paneli Baslatiliyor...
echo ======================================================
echo Tarayiciniz otomatik olarak acilacaktir...
echo Kapatmak icin bu pencereyi kapatabilirsiniz.
echo.

python -m streamlit run app.py
pause
