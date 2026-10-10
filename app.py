"""
BIST 100 Sinyal & Analiz Web Kontrol Paneli (Streamlit Dashboard)
TradingView Alternatifi Bağımsız Analiz Arayüzü
"""
import sys
import os
import pandas as pd
import streamlit as st
import plotly.graph_objects as go
from plotly.subplots import make_subplots

# Windows terminal ve UTF-8 desteği
try:
    if sys.stdout.encoding and sys.stdout.encoding.lower() != 'utf-8':
        sys.stdout.reconfigure(encoding='utf-8')
except Exception:
    pass

from config import StrategyConfig, TELEGRAM_CONFIG
from strategy import run_strategy
from chart import create_chart
from scanner import fetch_data
from backtest import backtest_strategy
from bist_symbols import BIST_100_SYMBOLS, BIST_30_SYMBOLS, get_bist_symbols, get_index_membership
from telegram_notifier import notify_signal, send_telegram_message, test_telegram_connection

# Sayfa Konfigürasyonu (Mobilde menünün ekranı kaplamaması için 'collapsed' başlatılır)
st.set_page_config(
    page_title="BIST Sinyal & Analiz Paneli",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# Plotly Dokunmatik Ekran ve Mobil Scroll Kilidi Çözümü
CHART_CONFIG = {
    'scrollZoom': False,
    'displayModeBar': False,
    'responsive': True,
    'doubleClick': 'reset'
}

# Özel Stil / CSS (Mobil Uyumlu & Responsive)
st.markdown("""
<style>
    /* Sayfa kenar boşlukları */
    .block-container {
        padding-top: 1.2rem !important;
        padding-bottom: 2rem !important;
        padding-left: 0.8rem !important;
        padding-right: 0.8rem !important;
        max-width: 100% !important;
    }
    
    /* Mobil Cihazlar (Ekran genişliği <= 768px) */
    @media (max-width: 768px) {
        /* 5-6 sütunlu metriklerin ezilmesini önle, 2'şerli kartlar olarak yerleştir */
        div[data-testid="column"] {
            flex: 1 1 calc(50% - 10px) !important;
            min-width: calc(50% - 10px) !important;
            margin-bottom: 8px !important;
        }
        div[data-testid="stHorizontalBlock"] {
            flex-wrap: wrap !important;
            gap: 8px !important;
        }
        .stMetric {
            background-color: #1e222d !important;
            padding: 8px 10px !important;
            border-radius: 8px !important;
            border: 1px solid #2a2e39 !important;
        }
        .stMetric label {
            font-size: 0.72rem !important;
            white-space: normal !important;
        }
        .stMetric div[data-testid="stMetricValue"] {
            font-size: 1.05rem !important;
        }
        /* Dokunmatik butonlar */
        .stButton>button {
            min-height: 44px !important;
            font-size: 0.95rem !important;
        }
    }

    /* Masaüstü Metrik Kartı */
    @media (min-width: 769px) {
        .stMetric {
            background-color: #1e222d !important;
            padding: 12px 14px !important;
            border-radius: 8px !important;
            border: 1px solid #2a2e39 !important;
        }
    }

    /* Üst Menü Navigasyon Butonları Tasarımı */
    div[data-testid="stRadio"] > div[role="radiogroup"] {
        background-color: #1e222d;
        border-radius: 10px;
        padding: 5px;
        border: 1px solid #2a2e39;
        margin-bottom: 15px;
        display: flex;
        justify-content: space-around;
    }
    div[data-testid="stRadio"] label {
        padding: 6px 10px !important;
        border-radius: 6px !important;
        cursor: pointer;
    }
</style>
""", unsafe_allow_html=True)

# Üst Navigasyon Menüsü (Mobilde tek dokunuşla sekmeler arası geçiş)
NAV_OPTIONS = ["📈 Grafik & Sinyal", "🔍 Canlı Tarama", "🧪 Backtest", "⚙️ Ayarlar"]
NAV_MAP = {
    "📈 Grafik & Sinyal": "📈 Hisse Grafiği & Sinyaller",
    "🔍 Canlı Tarama": "🔍 Canlı Piyasa Taraması (Scanner)",
    "🧪 Backtest": "🧪 Backtest & Performans",
    "⚙️ Ayarlar": "⚙️ Ayarlar & Telegram"
}

# Session state senkronizasyonu
if "current_nav" not in st.session_state:
    st.session_state.current_nav = NAV_OPTIONS[0]

selected_nav = st.radio(
    "Menü:",
    NAV_OPTIONS,
    index=NAV_OPTIONS.index(st.session_state.current_nav),
    horizontal=True,
    label_visibility="collapsed"
)
st.session_state.current_nav = selected_nav
app_mode = NAV_MAP[selected_nav]

# Yan Menü (Sidebar) - Ekstra ayarlar ve parametreler için
st.sidebar.title("📊 BIST Bot Kontrol")
st.sidebar.caption(f"Aktif Sayfa: **{selected_nav}**")

# Strateji Parametreleri (Sidebar'dan dinamik ayarlanabilir)
st.sidebar.markdown("---")
st.sidebar.subheader("📋 BIST Endeks Listesi")
with st.sidebar.expander("Endeks Hisselerini Yönet", expanded=False):
    st.write(f"Aktif BIST 100: **{len(BIST_100_SYMBOLS)}** hisse")
    st.write(f"Aktif BIST 30: **{len(BIST_30_SYMBOLS)}** hisse")
    if st.button("🔄 Borsa İstanbul'dan Listeyi Güncelle"):
        with st.spinner("Resmi BIST 100 hisseleri çekiliyor..."):
            new_syms = get_bist_symbols("BIST100", force_refresh=True)
            get_bist_symbols("BIST30", force_refresh=True)
            st.success(f"Liste güncellendi! ({len(new_syms)} hisse)")
            st.rerun()

st.sidebar.subheader("🛠️ Strateji Parametreleri")
with st.sidebar.expander("Girdi Ayarlarını Değiştir", expanded=False):
    nv_avg_len = st.number_input("Net Hacim Ortalaması (NV Avg)", value=5, min_value=2, max_value=50)
    neg_flow = st.number_input("Negatif Akış Onayı (Mum Sayısı)", value=3, min_value=1, max_value=10)
    rsi_len = st.number_input("RSI Periyodu", value=14, min_value=2, max_value=50)
    rsi_ob = st.number_input("RSI Aşırı Alım Seviyesi (Çıkış Sinyali)", value=70, min_value=50, max_value=90)
    start_year = st.number_input("Başlangıç Yılı", value=2020, min_value=2015, max_value=2030)

current_config = StrategyConfig(
    nv_avg_length=nv_avg_len,
    neg_flow_bars=neg_flow,
    rsi_length=rsi_len,
    rsi_overbought=rsi_ob,
    use_date_filter=True,
    start_year=start_year,
    start_month=1,
    start_day=1
)

# ==========================================
# 1. HİSSE GRAFİĞİ & SİNYALLER GÖRÜNÜMÜ
# ==========================================
if app_mode == "📈 Hisse Grafiği & Sinyaller":
    st.title("📈 BIST İnteraktif Hisse Grafiği")
    st.markdown("TradingView alternatifi bağımsız Plotly mum grafiği, Net Hacim Akışı ve al/sat sinyalleri.")

    col1, col2, col3 = st.columns([2, 1, 1])
    with col1:
        # Hisse seçici
        clean_symbols = [s.replace(".IS", "") for s in BIST_100_SYMBOLS]
        selected_clean = st.selectbox("Hisse Seçin veya Arayın:", clean_symbols, index=clean_symbols.index("THYAO") if "THYAO" in clean_symbols else 0)
        selected_symbol = f"{selected_clean}.IS"
    with col2:
        period_choice = st.selectbox("Veri Aralığı:", ["2020'den Günümüze", "1y", "2y", "3y", "5y", "max"], index=0)
    with col3:
        st.write("")
        st.write("")
        refresh_btn = st.button("🔄 Veriyi Yenile", use_container_width=True)

    with st.spinner(f"{selected_symbol} için veriler yükleniyor ve hesaplanıyor..."):
        if period_choice == "2020'den Günümüze":
            df = fetch_data(selected_symbol, start="2020-01-01")
        else:
            df = fetch_data(selected_symbol, period=period_choice)

    if not df.empty:
        df_strat = run_strategy(df, current_config)
        last_row = df_strat.iloc[-1]
        last_date = df_strat.index[-1].strftime("%d.%m.%Y")
        last_price = float(last_row['Close'])
        last_rsi = float(last_row['RSI'])
        in_pos = bool(last_row['Position'] == 1)

        # Durum Kartları
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Son Kapanış", f"{last_price:.2f} TL")
        m2.metric("RSI (14)", f"{last_rsi:.1f}")
        m3.metric("Son Güncelleme", last_date)
        m4.metric("Mevcut Durum", "🟢 Pozisyonda (AL)" if in_pos else "⚪ Nakitte / İzlemede")

        # Son Sinyal Kontrolleri
        if last_row['Long_Signal']:
            st.success(f"🚀 **BUGÜN AL SİNYALİ VERDİ!** ({last_date} kapanışı itibariyle)")
        elif last_row['Exit_Signal']:
            st.error(f"🔻 **BUGÜN SAT SİNYALİ VERDİ!** ({last_date} kapanışı itibariyle)")
        elif last_row['RSI_Warning']:
            st.warning(f"⚠️ **RSI MOMENTUM UYARISI!** RSI 70 seviyesini aşağı kesti, pivot kırılımı bekleniyor.")

        # Plotly Grafiğini Çiz (Dokunmatik Scroll Korumalı)
        fig = create_chart(df_strat, symbol=selected_symbol, save_html=False)
        st.plotly_chart(fig, use_container_width=True, config=CHART_CONFIG)
    else:
        st.error(f"{selected_symbol} için veri alınamadı. Sembolün doğruluğunu kontrol edin.")

# ==========================================
# 2. CANLI PİYASA TARAMASI (SCANNER)
# ==========================================
elif app_mode == "🔍 Canlı Piyasa Taraması (Scanner)":
    st.title("🔍 BIST Günlük Sinyal Tarayıcısı")
    st.markdown("BIST hisselerini otomatik tarayarak son günde **AL**, **SAT** veya **RSI Uyarısı** veren hisseleri listeler.")

    scan_col1, scan_col2, scan_col3 = st.columns([1, 1, 1])
    with scan_col1:
        market_choice = st.radio("Taranacak Hisse Grubu:", ["BIST 30 (Hızlı - ~10 sn)", "BIST 100 (Kapsamlı - ~30 sn)"])
    with scan_col2:
        send_tg_check = st.checkbox("Sinyal bulununca Telegram'a gönder", value=TELEGRAM_CONFIG.get("enabled", False))
    with scan_col3:
        st.write("")
        st.write("")
        start_scan = st.button("🚀 Taramayı Başlat", type="primary", use_container_width=True)

    if start_scan:
        targets = BIST_30_SYMBOLS if "BIST 30" in market_choice else BIST_100_SYMBOLS
        progress_bar = st.progress(0)
        status_text = st.empty()

        buy_list = []
        sell_list = []
        warn_list = []

        for idx, sym in enumerate(targets):
            status_text.text(f"Taranıyor ({idx+1}/{len(targets)}): {sym}")
            progress_bar.progress((idx + 1) / len(targets))

            df = fetch_data(sym)
            if df.empty:
                continue

            df_strat = run_strategy(df, current_config)
            if df_strat.empty:
                continue

            last_row = df_strat.iloc[-1]
            last_date = df_strat.index[-1].strftime("%Y-%m-%d")
            close_price = float(last_row['Close'])
            rsi_val = float(last_row['RSI'])

            clean_name = sym.replace(".IS", "")
            idx_badge = get_index_membership(sym)

            if last_row['Long_Signal']:
                bt_res = backtest_strategy(df_strat)
                wr = bt_res.get('win_rate', 0.0)
                aw = bt_res.get('avg_win_pct', 0.0)
                wt = bt_res.get('win_trades', 0)
                tt = bt_res.get('total_trades', 0)
                pf = bt_res.get('profit_factor', 0.0)

                buy_list.append({
                    "Hisse": clean_name,
                    "Endeks": idx_badge,
                    "Fiyat (TL)": f"{close_price:.2f}",
                    "RSI": f"{rsi_val:.1f}",
                    "Kazanma %": f"%{wr:.1f}",
                    "Ort. Kâr": f"%{aw:.1f}",
                    "Tarih": last_date
                })
                if send_tg_check:
                    notify_signal(
                        symbol=sym,
                        signal_type="BUY",
                        price=close_price,
                        rsi=rsi_val,
                        date_str=last_date,
                        win_rate=wr,
                        avg_win_pct=aw,
                        index_name=idx_badge,
                        win_trades=wt,
                        total_trades=tt,
                        profit_factor=pf
                    )

            elif last_row['Exit_Signal']:
                bt_res = backtest_strategy(df_strat)
                wr = bt_res.get('win_rate', 0.0)
                aw = bt_res.get('avg_win_pct', 0.0)
                wt = bt_res.get('win_trades', 0)
                tt = bt_res.get('total_trades', 0)
                pf = bt_res.get('profit_factor', 0.0)

                sell_list.append({
                    "Hisse": clean_name,
                    "Endeks": idx_badge,
                    "Fiyat (TL)": f"{close_price:.2f}",
                    "RSI": f"{rsi_val:.1f}",
                    "Kazanma %": f"%{wr:.1f}",
                    "Ort. Kâr": f"%{aw:.1f}",
                    "Tarih": last_date
                })
                if send_tg_check:
                    notify_signal(
                        symbol=sym,
                        signal_type="SELL",
                        price=close_price,
                        rsi=rsi_val,
                        date_str=last_date,
                        win_rate=wr,
                        avg_win_pct=aw,
                        index_name=idx_badge,
                        win_trades=wt,
                        total_trades=tt,
                        profit_factor=pf
                    )

            elif last_row['RSI_Warning']:
                warn_list.append({
                    "Hisse": clean_name,
                    "Endeks": idx_badge,
                    "Fiyat (TL)": f"{close_price:.2f}",
                    "RSI": f"{rsi_val:.1f}",
                    "Tarih": last_date
                })

        status_text.success("✅ Tarama başarıyla tamamlandı!")

        # Sonuç Kartları
        c1, c2, c3 = st.columns(3)
        c1.metric("🟢 AL Sinyali Verenler", len(buy_list))
        c2.metric("🔴 SAT Sinyali Verenler", len(sell_list))
        c3.metric("⚠️ RSI Uyarısı Verenler", len(warn_list))

        st.markdown("---")
        
        tab_buy, tab_sell, tab_warn = st.tabs(["🟢 AL Sinyalleri", "🔴 SAT Sinyalleri", "⚠️ RSI Uyarıları"])
        with tab_buy:
            if buy_list:
                st.dataframe(pd.DataFrame(buy_list), use_container_width=True)
            else:
                st.info("Bugün kapanış itibariyle yeni AL sinyali veren hisse bulunamadı.")

        with tab_sell:
            if sell_list:
                st.dataframe(pd.DataFrame(sell_list), use_container_width=True)
            else:
                st.info("Bugün kapanış itibariyle yeni SAT sinyali veren hisse bulunamadı.")

        with tab_warn:
            if warn_list:
                st.dataframe(pd.DataFrame(warn_list), use_container_width=True)
            else:
                st.info("Bugün kapanış itibariyle RSI aşırı alımdan dönen hisse bulunamadı.")

# ==========================================
# 3. BACKTEST & PERFORMANS ANALİZİ
# ==========================================
elif app_mode == "🧪 Backtest & Performans":
    st.title("🧪 Strateji Backtest & Performans Analizi")
    st.markdown("Stratejinin geçmiş yıllardaki kârlılığını, işlem sayısını ve hisseyi sadece elde tutma (Buy & Hold) karşısındaki başarısını ölçün.")

    bcol1, bcol2, bcol3 = st.columns([2, 1, 1])
    with bcol1:
        clean_symbols = [s.replace(".IS", "") for s in BIST_100_SYMBOLS]
        bt_clean = st.selectbox("Test Edilecek Hisse:", clean_symbols, index=clean_symbols.index("THYAO") if "THYAO" in clean_symbols else 0)
        bt_symbol = f"{bt_clean}.IS"
    with bcol2:
        bt_period = st.selectbox("Geçmiş Süre:", ["2020'den Günümüze (Varsayılan)", "3 Yıl", "5 Yıl", "Tüm Geçmiş (Max)"], index=0)
    with bcol3:
        st.write("")
        st.write("")
        run_bt_btn = st.button("🚀 Testi Çalıştır", type="primary", use_container_width=True)

    if run_bt_btn or True:
        with st.spinner(f"{bt_symbol} için backtest yapılıyor..."):
            if "2020" in bt_period:
                df_bt = fetch_data(bt_symbol, start="2020-01-01")
            elif "3 Yıl" in bt_period:
                df_bt = fetch_data(bt_symbol, period="3y")
            elif "5 Yıl" in bt_period:
                df_bt = fetch_data(bt_symbol, period="5y")
            else:
                df_bt = fetch_data(bt_symbol, period="max")
            if not df_bt.empty:
                df_bt_strat = run_strategy(df_bt, current_config)
                res = backtest_strategy(df_bt_strat)

                # Üst Özet Kartları
                st.markdown("### 📊 Genel Performans Özeti")
                col_m1, col_m2, col_m3, col_m4, col_m5 = st.columns(5)
                col_m1.metric("Strateji Toplam Getirisi", f"%{res['total_return_pct']:.2f}")
                col_m2.metric("Al & Tut Getirisi", f"%{res['buy_and_hold_pct']:.2f}")
                col_m3.metric("Kazanma Oranı (Win Rate)", f"%{res['win_rate']:.1f}", f"{res['win_trades']}/{res['total_trades']} İşlem")
                col_m4.metric("Kâr Faktörü", f"{res['profit_factor']:.2f}")
                col_m5.metric("Maksimum Çekilme (DD)", f"%{res['max_drawdown_pct']:.2f}")

                col_r1, col_r2, col_r3 = st.columns(3)
                col_r1.metric("Sharpe Oranı (Yıllık)", f"{res['sharpe_ratio']:.2f}", help="Getiri / Dalgalanma Oranı")
                col_r2.metric("Sortino Oranı (Yıllık)", f"{res['sortino_ratio']:.2f}", help="Sadece zararlı dalgalanmayı cezalandıran risk düzeltilmiş getiri")
                col_r3.metric("Maksimum Çekilme Süresi", f"{res['max_dd_duration_days']} Gün", help="Yeni bir kâr rekoru kırana kadar geçen en uzun toparlanma süresi")

                st.markdown("---")

                # ==========================================
                # İŞLEM ANALİZİ (TRADINGVIEW STİLİ)
                # ==========================================
                st.markdown("## 📈 İşlem Analizi")
                
                ana_tab_dagilim, ana_tab_zaman, ana_tab_yillik = st.tabs(["📊 Dağılım", "⏳ Zaman Modelleri", "📅 Yıllık Getiriler"])

                # --- 1. SEKME: DAĞILIM ---
                with ana_tab_dagilim:
                    # Üst Metrikler (Expectancy, Ortalama Kâr/Zarar, En Büyük Kâr/Zarar, Kâr/Zarar Oranı)
                    k_col1, k_col2, k_col3, k_col4, k_col5, k_col6 = st.columns(6)
                    k_col1.metric("Beklenti (Expectancy)", f"%{res['expectancy_pct']:.2f}", f"{res['expectancy_tl']:+,.0f} TL")
                    k_col2.metric("Ortalama Kâr", f"%{res['avg_win_pct']:.2f}", f"{res['avg_win_tl']:+,.0f} TL")
                    k_col3.metric("Ortalama Zarar", f"%{res['avg_loss_pct']:.2f}", f"{res['avg_loss_tl']:+,.0f} TL")
                    k_col4.metric("Kâr/Zarar Oranı (Payoff)", f"{res['win_loss_ratio']:.2f}")
                    k_col5.metric("En Büyük Kâr (Max Win)", f"%{res['max_win_pct']:.2f}", f"{res['max_win_tl']:+,.0f} TL")
                    k_col6.metric("En Büyük Zarar (Max Loss)", f"%{res['max_loss_pct']:.2f}", f"{res['max_loss_tl']:+,.0f} TL")

                    st.markdown("<br>", unsafe_allow_html=True)

                    # Grafikler: Getiri Dağılımı ve İşlem Dağılımı (Donut)
                    g_col1, g_col2 = st.columns([1.3, 1])

                    with g_col1:
                        st.markdown("##### 📊 Getiri Dağılımı")
                        hist_fig = go.Figure()
                        
                        if not res['trades'].empty:
                            wins_df = res['trades'][res['trades']['win']]
                            loss_df = res['trades'][res['trades']['loss']]

                            if not wins_df.empty:
                                hist_fig.add_trace(go.Histogram(
                                    x=wins_df['return_pct'],
                                    name="Kazananlar",
                                    marker_color="#26a69a",
                                    opacity=0.85
                                ))
                            if not loss_df.empty:
                                hist_fig.add_trace(go.Histogram(
                                    x=loss_df['return_pct'],
                                    name="Azalanlar",
                                    marker_color="#ef5350",
                                    opacity=0.85
                                ))

                            # Dikey Ortalama Çizgileri (TradingView stili)
                            if res['avg_loss_pct'] != 0:
                                hist_fig.add_vline(
                                    x=res['avg_loss_pct'],
                                    line_dash="dash",
                                    line_color="#ef5350",
                                    line_width=2,
                                    annotation_text=f"Ort. Zarar: %{res['avg_loss_pct']:.2f}",
                                    annotation_position="top left",
                                    annotation_font=dict(color="#ef5350", size=11)
                                )
                            if res['avg_win_pct'] != 0:
                                hist_fig.add_vline(
                                    x=res['avg_win_pct'],
                                    line_dash="dash",
                                    line_color="#26a69a",
                                    line_width=2,
                                    annotation_text=f"Ort. Kâr: %{res['avg_win_pct']:.2f}",
                                    annotation_position="top right",
                                    annotation_font=dict(color="#26a69a", size=11)
                                )

                        hist_fig.update_layout(
                            template="plotly_dark",
                            paper_bgcolor="#131722",
                            plot_bgcolor="#1e222d",
                            height=330,
                            barmode='stack',
                            margin=dict(l=30, r=30, t=30, b=30),
                            xaxis_title="Getiri (%)",
                            yaxis_title="İşlem Sayısı",
                            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
                        )
                        st.plotly_chart(hist_fig, use_container_width=True, config=CHART_CONFIG)

                    with g_col2:
                        st.markdown("##### 🍩 İşlem Dağılımı")
                        donut_fig = go.Figure(data=[go.Pie(
                            labels=["Kazananlar", "Azalanlar", "Başa baş"],
                            values=[res['win_trades'], res['loss_trades'], res['even_trades']],
                            hole=0.68,
                            marker=dict(colors=['#26a69a', '#ef5350', '#ffb74d']),
                            textinfo="value+percent",
                            hoverinfo="label+value+percent"
                        )])
                        donut_fig.update_layout(
                            annotations=[dict(
                                text=f"<b>{res['total_trades']}</b><br><span style='font-size:12px;color:#888;'>Toplam İşlem</span>",
                                x=0.5, y=0.5,
                                font_size=20,
                                showarrow=False
                            )],
                            template="plotly_dark",
                            paper_bgcolor="#131722",
                            plot_bgcolor="#1e222d",
                            height=330,
                            margin=dict(l=20, r=20, t=30, b=20),
                            legend=dict(orientation="h", yanchor="bottom", y=-0.15, xanchor="center", x=0.5)
                        )
                        st.plotly_chart(donut_fig, use_container_width=True, config=CHART_CONFIG)

                # --- 2. SEKME: ZAMAN MODELLERİ ---
                with ana_tab_zaman:
                    st.markdown("##### ⏳ İşlem Süresi & Toparlanma Analizi")
                    z_col1, z_col2, z_col3, z_col4 = st.columns(4)
                    z_col1.metric("Ortalama İşlem Süresi", f"{res['avg_duration_days']:.1f} Gün/Bar")
                    z_col2.metric("Kazanan İşlemlerin Ort. Süresi", f"{res['avg_win_duration']:.1f} Gün/Bar")
                    z_col3.metric("Kaybeden İşlemlerin Ort. Süresi", f"{res['avg_loss_duration']:.1f} Gün/Bar")
                    z_col4.metric("En Uzun Toparlanma Süresi", f"{res['max_dd_duration_days']} Gün")

                # --- 3. SEKME: YILLIK GETİRİLER ---
                with ana_tab_yillik:
                    st.markdown("##### 📅 Yıl Bazında Performans Kıyaslaması")
                    if not res['yearly_df'].empty:
                        ydf = res['yearly_df']
                        
                        y_fig = go.Figure()
                        y_fig.add_trace(go.Bar(
                            x=ydf['Yıl'],
                            y=ydf['Strateji (%)'],
                            name='Strateji Getirisi (%)',
                            marker_color='#26a69a'
                        ))
                        y_fig.add_trace(go.Bar(
                            x=ydf['Yıl'],
                            y=ydf['Al & Tut (%)'],
                            name='Al & Tut Getirisi (%)',
                            marker_color='#787b86'
                        ))
                        y_fig.update_layout(
                            template="plotly_dark",
                            paper_bgcolor="#131722",
                            plot_bgcolor="#1e222d",
                            height=320,
                            barmode='group',
                            margin=dict(l=30, r=30, t=30, b=30),
                            yaxis_title="Getiri (%)",
                            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
                        )
                        st.plotly_chart(y_fig, use_container_width=True, config=CHART_CONFIG)
                        
                        ydf_disp = ydf.copy()
                        ydf_disp['Strateji (%)'] = ydf_disp['Strateji (%)'].map(lambda x: f"%{x:+.1f}")
                        ydf_disp['Al & Tut (%)'] = ydf_disp['Al & Tut (%)'].map(lambda x: f"%{x:+.1f}")
                        ydf_disp['Kazanma Oranı (%)'] = ydf_disp['Kazanma Oranı (%)'].map(lambda x: f"%{x:.1f}")
                        st.dataframe(ydf_disp, use_container_width=True)
                    else:
                        st.info("Yıllık getiri verisi bulunamadı.")

                st.markdown("---")

                # Kasa Eğrisi (Equity Curve) Grafiği
                st.subheader("📈 Kasa Gelişimi (Equity Curve)")
                equity_fig = go.Figure()
                equity_fig.add_trace(go.Scatter(
                    x=res['equity_curve'].index,
                    y=res['equity_curve'].values,
                    mode='lines',
                    name='Strateji Kasası (TL)',
                    line=dict(color='#26a69a', width=2)
                ))
                equity_fig.update_layout(
                    template="plotly_dark",
                    paper_bgcolor="#131722",
                    plot_bgcolor="#1e222d",
                    height=400,
                    margin=dict(l=40, r=40, t=20, b=20),
                    yaxis_title="Portföy Değeri (TL)"
                )
                st.plotly_chart(equity_fig, use_container_width=True, config=CHART_CONFIG)

                # İşlem Geçmişi Tablosu
                st.subheader("📋 Gerçekleşen İşlemler Listesi")
                if not res['trades'].empty:
                    format_trades = res['trades'].copy()
                    if 'entry_date' in format_trades.columns:
                        format_trades['entry_date'] = pd.to_datetime(format_trades['entry_date']).dt.strftime('%d.%m.%Y')
                    if 'exit_date' in format_trades.columns:
                        format_trades['exit_date'] = pd.to_datetime(format_trades['exit_date']).dt.strftime('%d.%m.%Y')
                    st.dataframe(format_trades, use_container_width=True)
                else:
                    st.info("Bu tarih aralığında tamamlanmış işlem bulunamadı.")
            else:
                st.error("Veri indirilemedi.")

# ==========================================
# 4. AYARLAR & TELEGRAM
# ==========================================
elif app_mode == "⚙️ Ayarlar & Telegram":
    st.title("⚙️ Telegram & Sistem Ayarları")
    st.markdown("Telegram bot bağlantınızı buradan test edebilir ve güncelleyebilirsiniz.")

    tg_token = st.text_input("Telegram Bot Token:", value=TELEGRAM_CONFIG.get("token", ""), type="password")
    tg_chat = st.text_input("Telegram Chat ID:", value=TELEGRAM_CONFIG.get("chat_id", ""))
    tg_status = st.checkbox("Telegram Bildirimlerini Etkinleştir", value=TELEGRAM_CONFIG.get("enabled", False))

    if st.button("🧪 Telegram Bağlantısını Test Et"):
        if not tg_token or not tg_chat or "BURAYA" in tg_token:
            st.error("Lütfen geçerli bir Bot Token ve Chat ID giriniz.")
        else:
            test_msg = "🤖 <b>Tebrikler!</b>\n\nBIST Sinyal ve Analiz Paneli Telegram bağlantınız başarıyla sağlandı."
            with st.spinner("Mesaj gönderiliyor..."):
                ok = send_telegram_message(test_msg, token=tg_token, chat_id=tg_chat)
                if ok:
                    st.success("Test mesajı Telegram'ınıza başarıyla iletildi! 🎉")
                else:
                    st.error("Mesaj gönderilemedi. Token veya Chat ID bilgilerini kontrol edin.")
