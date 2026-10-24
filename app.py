"""
BIST 30 Hisseye Özel Optimum RSI & 5 Hisse Portföy Web Kontrol Paneli (Streamlit Dashboard V6.0)
"""
import sys
import pandas as pd
import streamlit as st
import plotly.graph_objects as go

try:
    if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
        sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

from config import StrategyConfig, TELEGRAM_CONFIG, PORTFOLIO_CONFIG, get_optimal_rsi
from strategy import run_strategy
from chart import create_chart
from scanner import fetch_data, scan_symbols
from backtest import backtest_strategy
from bist_symbols import BIST_30_SYMBOLS, BIST_100_SYMBOLS, get_bist_symbols
from portfolio_manager import (
    load_portfolio_state,
    add_manual_position,
    remove_manual_position,
)
from telegram_notifier import (
    send_telegram_message,
    format_bist30_daily_report,
    send_bist30_daily_report,
    test_telegram_connection,
)

st.set_page_config(
    page_title="BIST 30 Optimum RSI & Portföy Paneli",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="collapsed",
)

CHART_CONFIG = {
    "scrollZoom": False,
    "displayModeBar": False,
    "responsive": True,
    "doubleClick": "reset",
}

st.markdown(
    """
<style>
    .block-container {
        padding-top: 5rem !important;
        padding-bottom: 2rem !important;
        padding-left: 0.8rem !important;
        padding-right: 0.8rem !important;
        max-width: 100% !important;
    }

    @media (max-width: 768px) {
        div[data-testid="column"] {
            flex: 1 1 calc(50% - 10px) !important;
            min-width: calc(50% - 10px) !important;
            margin-bottom: 8px !important;
        }
        div[data-testid="stHorizontalBlock"] {
            flex-wrap: wrap !important;
            gap: 8px !important;
        }
        .stButton>button {
            min-height: 44px !important;
            font-size: 0.95rem !important;
        }
    }

    div[data-testid="stMetric"] {
        background-color: #1e222d !important;
        padding: 12px 14px !important;
        border-radius: 10px !important;
        border: 1px solid #363c4e !important;
        box-shadow: 0 3px 6px rgba(0, 0, 0, 0.25) !important;
    }

    div[data-testid="stMetric"] label,
    div[data-testid="stMetric"] label *,
    div[data-testid="stMetric"] [data-testid="stMetricLabel"],
    div[data-testid="stMetric"] [data-testid="stMetricLabel"] * {
        color: #9aa0a6 !important;
        font-size: 0.8rem !important;
        font-weight: 500 !important;
    }

    div[data-testid="stMetric"] div[data-testid="stMetricValue"],
    div[data-testid="stMetric"] div[data-testid="stMetricValue"] *,
    div[data-testid="stMetric"] [data-testid="stMetricValue"],
    div[data-testid="stMetric"] [data-testid="stMetricValue"] * {
        color: #ffffff !important;
        font-size: 1.3rem !important;
        font-weight: 700 !important;
    }

    div[data-testid="stMetric"] div[data-testid="stMetricDelta"],
    div[data-testid="stMetric"] div[data-testid="stMetricDelta"] * {
        color: #00e676 !important;
        font-weight: 600 !important;
    }

    div[data-testid="stSegmentedControl"] {
        width: 100% !important;
        margin-top: 0.2rem !important;
        margin-bottom: 1.4rem !important;
    }
    div[data-testid="stSegmentedControl"] button {
        flex: 1 1 0px !important;
        min-height: 44px !important;
        font-size: 0.92rem !important;
        font-weight: 600 !important;
    }

    div[data-testid="stRadio"] > div[role="radiogroup"] {
        background-color: #1e222d !important;
        border-radius: 12px !important;
        padding: 6px !important;
        border: 1px solid #363c4e !important;
        margin-top: 0.2rem !important;
        margin-bottom: 1.4rem !important;
        display: flex !important;
        justify-content: space-around !important;
    }
    div[data-testid="stRadio"] label {
        padding: 6px 10px !important;
        border-radius: 8px !important;
        cursor: pointer !important;
    }
    div[data-testid="stRadio"] label,
    div[data-testid="stRadio"] label p,
    div[data-testid="stRadio"] label span {
        color: #ffffff !important;
        font-size: 0.9rem !important;
        font-weight: 600 !important;
    }
</style>
""",
    unsafe_allow_html=True,
)

NAV_OPTIONS = ["📈 Grafik", "💼 Portföy (5)", "🔍 Tarama", "🧪 Backtest", "⚙️ Ayarlar"]
NAV_MAP = {
    "📈 Grafik": "📈 Hisse Grafiği & Sinyaller",
    "💼 Portföy (5)": "💼 BIST 30 Portföyüm (Max 5 Hisse)",
    "🔍 Tarama": "🔍 BIST 30 Günlük Tarama",
    "🧪 Backtest": "🧪 Backtest & Performans",
    "⚙️ Ayarlar": "⚙️ Ayarlar & Telegram",
}

if "current_nav" not in st.session_state:
    st.session_state.current_nav = NAV_OPTIONS[0]

if hasattr(st, "segmented_control"):
    selected_nav = (
        st.segmented_control(
            "Menü",
            NAV_OPTIONS,
            default=st.session_state.current_nav
            if st.session_state.current_nav in NAV_OPTIONS
            else NAV_OPTIONS[0],
            label_visibility="collapsed",
        )
        or st.session_state.current_nav
    )
else:
    nav_idx = (
        NAV_OPTIONS.index(st.session_state.current_nav)
        if st.session_state.current_nav in NAV_OPTIONS
        else 0
    )
    selected_nav = st.radio(
        "Menü:",
        NAV_OPTIONS,
        index=nav_idx,
        horizontal=True,
        label_visibility="collapsed",
    )
st.session_state.current_nav = selected_nav
app_mode = NAV_MAP[selected_nav]

# Yan Menü (Sidebar)
st.sidebar.title("📊 BIST 30 Bot Kontrol")
st.sidebar.caption(f"Aktif Sayfa: **{selected_nav}**")

st.sidebar.markdown("---")
st.sidebar.subheader("📋 BIST Endeks Listesi")
with st.sidebar.expander("Endeks Hisselerini Yönet", expanded=False):
    st.write(f"Aktif BIST 30: **{len(BIST_30_SYMBOLS)}** şirket")
    st.write(f"Aktif BIST 100: **{len(BIST_100_SYMBOLS)}** şirket")
    if st.button("🔄 Borsa İstanbul'dan Listeyi Güncelle"):
        with st.spinner("Resmi BIST 30 ve BIST 100 listeleri güncelleniyor..."):
            get_bist_symbols("BIST30", force_refresh=True)
            get_bist_symbols("BIST100", force_refresh=True)
            st.success("Endeks listeleri güncellendi!")
            st.rerun()

st.sidebar.subheader("🛠️ Strateji Parametreleri (V6.0)")
with st.sidebar.expander("Girdi Ayarlarını Değiştir", expanded=False):
    use_opt_rsi = st.checkbox(
        "Hisseye Özel Optimum RSI (2020+ En Kârlı)",
        value=True,
        help="Aktifken her hisse kendi 2020-2026 backtest en kârlı RSI seviyesinde (68-78) SAT üretir.",
    )
    rsi_ob = st.number_input(
        "Manuel Sabit RSI Çıkışı (Özel Mod Kapalıysa)",
        value=72,
        min_value=55,
        max_value=85,
        disabled=use_opt_rsi,
    )
    rsi_max_buy = st.number_input(
        "Maksimum Alım RSI Filtresi", value=65, min_value=50, max_value=80
    )
    nv_avg_len = st.number_input(
        "Net Hacim Ortalaması (NV Avg)", value=5, min_value=2, max_value=50
    )
    rsi_len = st.number_input("RSI Periyodu", value=14, min_value=2, max_value=50)
    start_year = st.number_input("Başlangıç Yılı", value=2020, min_value=2015, max_value=2030)

current_config = StrategyConfig(
    nv_avg_length=nv_avg_len,
    rsi_length=rsi_len,
    rsi_max_buy=float(rsi_max_buy),
    use_per_stock_optimal_rsi=use_opt_rsi,
    rsi_overbought=rsi_ob,
    use_date_filter=True,
    start_year=start_year,
    start_month=1,
    start_day=1,
)

# ==========================================
# 1. HİSSE GRAFİĞİ & SİNYALLER GÖRÜNÜMÜ
# ==========================================
if app_mode == "📈 Hisse Grafiği & Sinyaller":
    st.title("📈 BIST 30 Hisseye Özel Optimum RSI Grafiği")
    st.markdown(
        "Net Hacim Akışı (V6.0) ve her hissenin **2020'den günümüze en kârlı özel RSI çıkış hedefiyle** çalışan canlı analiz grafiği."
    )

    col1, col2, col3, col4 = st.columns([1.8, 1.1, 1, 0.9])
    with col1:
        universe_opt = st.selectbox(
            "Hisse Grubu:",
            ["Sadece BIST 30 (Ana Portföy)", "Tüm BIST 100 (İnceleme)"],
            index=0,
        )
        base_syms = BIST_30_SYMBOLS if "BIST 30" in universe_opt else BIST_100_SYMBOLS
        clean_symbols = [s.replace(".IS", "") for s in base_syms]
    with col2:
        selected_clean = st.selectbox(
            "Şirket Seçin:",
            clean_symbols,
            index=clean_symbols.index("THYAO") if "THYAO" in clean_symbols else 0,
        )
        selected_symbol = f"{selected_clean}.IS"
    with col3:
        period_choice = st.selectbox(
            "Veri Aralığı:", ["2020'den Günümüze", "1y", "2y", "3y", "5y", "max"], index=0
        )
    with col4:
        st.write("")
        st.write("")
        st.button("🔄 Veriyi Yenile", use_container_width=True)

    with st.spinner(f"{selected_clean} için veriler ve özel optimum RSI sinyalleri hesaplanıyor..."):
        if period_choice == "2020'den Günümüze":
            df = fetch_data(selected_symbol, start="2019-10-01")
        else:
            df = fetch_data(selected_symbol, period=period_choice)

    if not df.empty:
        df_strat = run_strategy(df, current_config, symbol=selected_symbol)
        last_row = df_strat.iloc[-1]
        last_date = df_strat.index[-1].strftime("%d.%m.%Y")
        last_price = float(last_row["Close"])
        last_rsi = float(last_row["RSI"])
        opt_rsi = int(last_row["Optimal_RSI_Exit"])
        in_pos = bool(last_row["Position"] == 1)

        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Son Kapanış", f"{last_price:.2f} TL", f"Tarih: {last_date}")
        m2.metric("Güncel RSI (14)", f"{last_rsi:.1f}", f"Hedef Çıkış: RSI {opt_rsi}")
        m3.metric("Hisseye Özel Çıkış Hedefi", f"RSI {opt_rsi}", "2020+ En Kârlı Seviye")
        m4.metric("Tekil Hisse Durumu", "🟢 Pozisyonda (AL)" if in_pos else "⚪ Nakitte / İzlemede")

        if bool(last_row["Raw_Long_Condition"]):
            st.success(
                f"🚀 **BUGÜN AL SİNYALİ VERDİ!** ({last_date} kapanışı | Güncel RSI: {last_rsi:.1f} | Özel Çıkış Hedefi: RSI {opt_rsi})"
            )
        elif bool(last_row["Exit_Signal"]):
            st.error(
                f"🔻 **BUGÜN SAT SİNYALİ VERDİ!** ({last_date} kapanışı itibariyle özel hedef RSI {opt_rsi} aşağı kırıldı)"
            )

        fig = create_chart(df_strat, symbol=selected_symbol, save_html=False)
        st.plotly_chart(fig, use_container_width=True, config=CHART_CONFIG)
    else:
        st.error(f"{selected_symbol} için veri alınamadı.")

# ==========================================
# 2. BIST 30 PORTFÖYÜM (MAKSİMUM 5 HİSSE)
# ==========================================
elif app_mode == "💼 BIST 30 Portföyüm (Max 5 Hisse)":
    st.title("💼 BIST 30 Otomatik Portföy Takibi (Maks. 5 Hisse)")
    st.markdown(
        "**Kural:** Sadece **BIST 30** şirketleri alınır. Her alım toplam portföyün **%10**'u kadardır ve aynı anda en fazla **5 açık hisse** taşınır (**Maksimum %50 Borsa / %50 Nakit-Mevduat**). Telegram botu bu listeye göre bildirim gönderir."
    )

    state = load_portfolio_state()
    max_pos = int(state.get("max_positions", 5))
    alloc_pct = float(state.get("allocation_pct", 10.0))
    open_positions = state.get("open_positions", [])
    open_cnt = len(open_positions)
    empty_slots = max(0, max_pos - open_cnt)
    stock_exp = int(open_cnt * alloc_pct)
    cash_exp = max(0, 100 - stock_exp)

    p1, p2, p3, p4 = st.columns(4)
    p1.metric("Açık Kontenjan", f"{open_cnt} / {max_pos} Hisse", f"{empty_slots} Boş Yer")
    p2.metric("İşlem Başına Pay", f"%{alloc_pct:.0f}", "BIST 30 Odaklı")
    p3.metric("Aktif Borsa Ağırlığı", f"%{stock_exp}", "Maks. %50 Sınır")
    p4.metric("Nakit / Mevduat Payı", f"%{cash_exp}", "PPF / Mevduat Kalkanı")

    act_col1, act_col2 = st.columns([1, 1])
    with act_col1:
        refresh_port_btn = st.button(
            "🔄 BIST 30 Taraması Yap & Portföy Fiyatlarını Güncelle",
            type="primary",
            use_container_width=True,
        )
    with act_col2:
        send_port_tg_btn = st.button(
            "📲 Güncel Portföy Raporunu Telegram'a Gönder",
            use_container_width=True,
        )

    if refresh_port_btn:
        with st.spinner("BIST 30 şirketleri taranıyor ve 5 hisselik portföy güncelleniyor..."):
            scan_symbols(BIST_30_SYMBOLS, send_telegram=False, save_charts=False, update_portfolio=True)
            st.success("Portföy durumu güncel BIST 30 verileriyle yenilendi!")
            st.rerun()

    if send_port_tg_btn:
        last_act = state.get("last_daily_actions", {})
        disp_dt = state.get("last_processed_date") or state.get("updated_at", "")
        ok = send_bist30_daily_report(
            date_str=disp_dt,
            bought_list=last_act.get("bought", []),
            sold_list=last_act.get("sold", []),
            open_positions=open_positions,
            skipped_list=last_act.get("skipped", []),
            max_positions=max_pos,
            allocation_pct=alloc_pct,
        )
        if ok:
            st.success("Portföy raporu Telegram'a başarıyla gönderildi!")
        else:
            st.error("Telegram gönderimi başarısız oldu. Ayarlar sekmesini kontrol edin.")

    st.markdown("### 📌 Sepetteki Açık BIST 30 Hisseleri")
    if open_positions:
        rows = []
        for idx, pos in enumerate(open_positions, 1):
            ep = float(pos["entry_price"])
            lp = float(pos.get("last_price", ep))
            pnl = ((lp - ep) / ep * 100.0) if ep > 0 else 0.0
            rows.append(
                {
                    "#": idx,
                    "Hisse": pos["clean_symbol"],
                    "Alış Tarihi": pos["entry_date"],
                    "Alış Fiyatı": f"{ep:.2f} TL",
                    "Güncel Fiyat": f"{lp:.2f} TL",
                    "Anlık Kâr/Zarar": f"%{pnl:+.2f}",
                    "Güncel RSI": f"{float(pos.get('last_rsi', pos.get('entry_rsi', 50.0))):.1f}",
                    "Özel Satış Hedefi": f"RSI {int(pos['target_rsi'])}",
                    "Portföy Payı": f"%{alloc_pct:.0f}",
                }
            )
        st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
    else:
        st.info(
            "Şu an portföyde açık hisse bulunmuyor (`0/5` — `%100` Nakit/Mevduat). İlk BIST 30 AL sinyali geldiğinde otomatik olarak buraya eklenecek ve Telegram'dan bildirilecektir."
        )

    with st.expander("🛠️ Sepeti Manuel Düzenle (Elinizdeki BIST 30 Hissesini Ekleyin veya Çıkarın)", expanded=False):
        mcol1, mcol2 = st.columns(2)
        with mcol1:
            st.markdown("**➕ Portföye Manuel BIST 30 Hissesi Ekle**")
            b30_clean_list = [s.replace(".IS", "") for s in BIST_30_SYMBOLS]
            add_sym = st.selectbox("BIST 30 Şirketi:", b30_clean_list, key="man_add_sym")
            add_price = st.number_input("Alış Fiyatınız (TL):", min_value=0.01, value=100.0, step=0.5)
            if st.button("➕ Sepete Ekle"):
                ok, msg = add_manual_position(add_sym, add_price)
                if ok:
                    st.success(msg)
                    st.rerun()
                else:
                    st.warning(msg)

        with mcol2:
            st.markdown("**➖ Açık Pozisyonu Sepetten Çıkar**")
            if open_positions:
                open_syms = [p["clean_symbol"] for p in open_positions]
                rem_sym = st.selectbox("Çıkarılacak Hisse:", open_syms, key="man_rem_sym")
                if st.button("🗑️ Sepetten Çıkar"):
                    ok, msg = remove_manual_position(rem_sym)
                    if ok:
                        st.success(msg)
                        st.rerun()
                    else:
                        st.warning(msg)
            else:
                st.caption("Çıkarılacak açık pozisyon yok.")

    closed_hist = state.get("closed_history", [])
    if closed_hist:
        st.markdown("---")
        st.subheader("📜 Kapanan Portföy İşlemleri")
        st.dataframe(pd.DataFrame(closed_hist[::-1]), use_container_width=True, hide_index=True)

# ==========================================
# 3. BIST 30 GÜNLÜK TARAMA (SCANNER)
# ==========================================
elif app_mode == "🔍 BIST 30 Günlük Tarama":
    st.title("🔍 BIST 30 Günlük Sinyal & 5 Hisse Filtresi")
    st.markdown(
        "Sadece **30 adet BIST 30 şirketini** Hisseye Özel Optimum RSI stratejisiyle tarar ve **5 hisse kontenjanına** göre aksiyon üretir."
    )

    sc1, sc2 = st.columns([1.5, 1])
    with sc1:
        send_tg_check = st.checkbox(
            "Tarama tamamlandığında toplu raporu Telegram'a da gönder",
            value=False,
        )
    with sc2:
        start_scan = st.button("🚀 BIST 30 Taramasını Başlat", type="primary", use_container_width=True)

    if start_scan:
        with st.spinner("30 adet BIST 30 şirketi Hisseye Özel Optimum RSI ile taranıyor..."):
            res_scan = scan_symbols(
                BIST_30_SYMBOLS,
                send_telegram=send_tg_check,
                save_charts=False,
                force_telegram=send_tg_check,
                update_portfolio=True,
            )

        c1, c2, c3 = st.columns(3)
        c1.metric("🟢 Sepete Giren Yeni AL", len(res_scan["buy"]))
        c2.metric("🔴 Sepetten Çıkan SAT", len(res_scan["sell"]))
        c3.metric("💼 Güncel Açık Sepet", f"{len(res_scan['open_positions'])} / 5 Hisse")

        preview_msg = format_bist30_daily_report(
            date_str=res_scan.get("display_date", ""),
            bought_list=res_scan["buy"],
            sold_list=res_scan["sell"],
            open_positions=res_scan["open_positions"],
            skipped_list=res_scan["skipped"],
            max_positions=PORTFOLIO_CONFIG.get("max_positions", 5),
            allocation_pct=PORTFOLIO_CONFIG.get("allocation_pct", 10.0),
        )
        with st.expander("📩 Telegram Mesaj Önizlemesi", expanded=True):
            st.markdown(preview_msg, unsafe_allow_html=True)

        st.subheader("📋 Tüm BIST 30 Şirketleri Güncel Durum & Özel Hedef RSI Tablosu")
        if res_scan.get("all_bist30"):
            st.dataframe(pd.DataFrame(res_scan["all_bist30"]), use_container_width=True, hide_index=True)

# ==========================================
# 4. BACKTEST & PERFORMANS ANALİZİ
# ==========================================
elif app_mode == "🧪 Backtest & Performans":
    st.title("🧪 Hisseye Özel Optimum RSI Backtest Analizi")
    st.markdown(
        "Seçilen şirketin **2020'den günümüze en kârlı özel RSI çıkış seviyesiyle** ürettiği gerçek performansı ölçer."
    )

    bcol1, bcol2, bcol3 = st.columns([2, 1, 1])
    with bcol1:
        bt_group = st.radio(
            "Endeks:", ["BIST 30", "BIST 100"], index=0, horizontal=True
        )
        bt_list = BIST_30_SYMBOLS if bt_group == "BIST 30" else BIST_100_SYMBOLS
        clean_symbols = [s.replace(".IS", "") for s in bt_list]
        bt_clean = st.selectbox(
            "Test Edilecek Şirket:",
            clean_symbols,
            index=clean_symbols.index("THYAO") if "THYAO" in clean_symbols else 0,
        )
        bt_symbol = f"{bt_clean}.IS"
    with bcol2:
        bt_period = st.selectbox(
            "Geçmiş Süre:",
            ["2020'den Günümüze (Varsayılan)", "3 Yıl", "5 Yıl", "Tüm Geçmiş (Max)"],
            index=0,
        )
    with bcol3:
        st.write("")
        st.write("")
        st.button("🚀 Testi Yenile", type="primary", use_container_width=True)

    with st.spinner(f"{bt_clean} için Hisseye Özel Optimum RSI backtest yapılıyor..."):
        if "2020" in bt_period:
            df_bt = fetch_data(bt_symbol, start="2019-10-01")
        elif "3 Yıl" in bt_period:
            df_bt = fetch_data(bt_symbol, period="3y")
        elif "5 Yıl" in bt_period:
            df_bt = fetch_data(bt_symbol, period="5y")
        else:
            df_bt = fetch_data(bt_symbol, period="max")

        if not df_bt.empty:
            df_bt_strat = run_strategy(df_bt, current_config, symbol=bt_symbol)
            if "2020" in bt_period:
                df_bt_eval = df_bt_strat[df_bt_strat["In_Date_Range"]].copy()
            else:
                df_bt_eval = df_bt_strat.copy()

            opt_lvl = int(df_bt_eval["Optimal_RSI_Exit"].iloc[-1])
            res = backtest_strategy(df_bt_eval)

            st.info(
                f"🎯 **{bt_clean}** için kullanılan **Hisseye Özel Çıkış Hedefi: RSI {opt_lvl}** (2020–Günümüz Backtest Optimum Seviyesi)"
            )

            st.markdown("### 📊 Genel Performans Özeti")
            col_m1, col_m2, col_m3, col_m4, col_m5 = st.columns(5)
            col_m1.metric("Strateji Toplam Getirisi", f"%{res['total_return_pct']:.2f}")
            col_m2.metric("Al & Tut Getirisi", f"%{res['buy_and_hold_pct']:.2f}")
            col_m3.metric(
                "Kazanma Oranı (Win Rate)",
                f"%{res['win_rate']:.1f}",
                f"{res['win_trades']}/{res['total_trades']} İşlem",
            )
            col_m4.metric("Kâr Faktörü", f"{res['profit_factor']:.2f}")
            col_m5.metric("Maksimum Çekilme (DD)", f"%{res['max_drawdown_pct']:.2f}")

            col_r1, col_r2, col_r3 = st.columns(3)
            col_r1.metric("Sharpe Oranı (Yıllık)", f"{res['sharpe_ratio']:.2f}")
            col_r2.metric("Sortino Oranı (Yıllık)", f"{res['sortino_ratio']:.2f}")
            col_r3.metric("Maksimum Çekilme Süresi", f"{res['max_dd_duration_days']} Gün")

            st.markdown("---")
            st.markdown("## 📈 İşlem Analizi")

            ana_tab_dagilim, ana_tab_zaman, ana_tab_yillik = st.tabs(
                ["📊 Dağılım", "⏳ Zaman Modelleri", "📅 Yıllık Getiriler"]
            )

            with ana_tab_dagilim:
                k_col1, k_col2, k_col3, k_col4, k_col5, k_col6 = st.columns(6)
                k_col1.metric("Beklenti", f"%{res['expectancy_pct']:.2f}", f"{res['expectancy_tl']:+,.0f} TL")
                k_col2.metric("Ortalama Kâr", f"%{res['avg_win_pct']:.2f}", f"{res['avg_win_tl']:+,.0f} TL")
                k_col3.metric("Ortalama Zarar", f"%{res['avg_loss_pct']:.2f}", f"{res['avg_loss_tl']:+,.0f} TL")
                k_col4.metric("Kâr/Zarar Oranı", f"{res['win_loss_ratio']:.2f}")
                k_col5.metric("En Büyük Kâr", f"%{res['max_win_pct']:.2f}", f"{res['max_win_tl']:+,.0f} TL")
                k_col6.metric("En Büyük Zarar", f"%{res['max_loss_pct']:.2f}", f"{res['max_loss_tl']:+,.0f} TL")

                g_col1, g_col2 = st.columns([1.3, 1])
                with g_col1:
                    st.markdown("##### 📊 Getiri Dağılımı")
                    hist_fig = go.Figure()
                    if not res["trades"].empty:
                        wins_df = res["trades"][res["trades"]["win"]]
                        loss_df = res["trades"][res["trades"]["loss"]]
                        if not wins_df.empty:
                            hist_fig.add_trace(
                                go.Histogram(
                                    x=wins_df["return_pct"],
                                    name="Kazananlar",
                                    marker_color="#26a69a",
                                    opacity=0.85,
                                )
                            )
                        if not loss_df.empty:
                            hist_fig.add_trace(
                                go.Histogram(
                                    x=loss_df["return_pct"],
                                    name="Kaybedenler",
                                    marker_color="#ef5350",
                                    opacity=0.85,
                                )
                            )
                    hist_fig.update_layout(
                        template="plotly_dark",
                        paper_bgcolor="#131722",
                        plot_bgcolor="#1e222d",
                        height=330,
                        barmode="stack",
                        margin=dict(l=30, r=30, t=30, b=30),
                        xaxis_title="Getiri (%)",
                        yaxis_title="İşlem Sayısı",
                    )
                    st.plotly_chart(hist_fig, use_container_width=True, config=CHART_CONFIG)

                with g_col2:
                    st.markdown("##### 🍩 İşlem Dağılımı")
                    donut_fig = go.Figure(
                        data=[
                            go.Pie(
                                labels=["Kazananlar", "Kaybedenler", "Başa baş"],
                                values=[res["win_trades"], res["loss_trades"], res["even_trades"]],
                                hole=0.68,
                                marker=dict(colors=["#26a69a", "#ef5350", "#ffb74d"]),
                                textinfo="value+percent",
                            )
                        ]
                    )
                    donut_fig.update_layout(
                        annotations=[
                            dict(
                                text=f"<b>{res['total_trades']}</b><br><span style='font-size:12px;color:#888;'>İşlem</span>",
                                x=0.5,
                                y=0.5,
                                font_size=20,
                                showarrow=False,
                            )
                        ],
                        template="plotly_dark",
                        paper_bgcolor="#131722",
                        plot_bgcolor="#1e222d",
                        height=330,
                        margin=dict(l=20, r=20, t=30, b=20),
                    )
                    st.plotly_chart(donut_fig, use_container_width=True, config=CHART_CONFIG)

            with ana_tab_zaman:
                z_col1, z_col2, z_col3, z_col4 = st.columns(4)
                z_col1.metric("Ortalama İşlem Süresi", f"{res['avg_duration_days']:.1f} Gün/Bar")
                z_col2.metric("Kazanan İşlem Ort. Süresi", f"{res['avg_win_duration']:.1f} Gün/Bar")
                z_col3.metric("Kaybeden İşlem Ort. Süresi", f"{res['avg_loss_duration']:.1f} Gün/Bar")
                z_col4.metric("En Uzun Toparlanma", f"{res['max_dd_duration_days']} Gün")

            with ana_tab_yillik:
                if not res["yearly_df"].empty:
                    ydf = res["yearly_df"].copy()
                    ydf["Strateji (%)"] = ydf["Strateji (%)"].map(lambda x: f"%{x:+.1f}")
                    ydf["Al & Tut (%)"] = ydf["Al & Tut (%)"].map(lambda x: f"%{x:+.1f}")
                    ydf["Kazanma Oranı (%)"] = ydf["Kazanma Oranı (%)"].map(lambda x: f"%{x:.1f}")
                    st.dataframe(ydf, use_container_width=True, hide_index=True)

            st.markdown("---")
            st.subheader("📈 Kasa Gelişimi (Equity Curve)")
            equity_fig = go.Figure()
            equity_fig.add_trace(
                go.Scatter(
                    x=res["equity_curve"].index,
                    y=res["equity_curve"].values,
                    mode="lines",
                    name="Strateji Kasası (TL)",
                    line=dict(color="#26a69a", width=2),
                )
            )
            equity_fig.update_layout(
                template="plotly_dark",
                paper_bgcolor="#131722",
                plot_bgcolor="#1e222d",
                height=380,
                margin=dict(l=40, r=40, t=20, b=20),
                yaxis_title="Portföy Değeri (TL)",
            )
            st.plotly_chart(equity_fig, use_container_width=True, config=CHART_CONFIG)

            st.subheader("📋 Gerçekleşen İşlemler Listesi")
            if not res["trades"].empty:
                format_trades = res["trades"].copy()
                format_trades["entry_date"] = pd.to_datetime(format_trades["entry_date"]).dt.strftime("%d.%m.%Y")
                format_trades["exit_date"] = pd.to_datetime(format_trades["exit_date"]).dt.strftime("%d.%m.%Y")
                st.dataframe(format_trades, use_container_width=True, hide_index=True)
            else:
                st.info("Bu tarih aralığında tamamlanmış işlem bulunamadı.")
        else:
            st.error("Veri indirilemedi.")

# ==========================================
# 5. AYARLAR & TELEGRAM
# ==========================================
elif app_mode == "⚙️ Ayarlar & Telegram":
    st.title("⚙️ Telegram & BIST 30 Portföy Sistemi Ayarları")
    st.markdown(
        "**Aktif Kurallar:**\n"
        "- **Evren:** Sadece **BIST 30** Şirketleri (Eski BIST 100 tekil mesajları kaldırıldı)\n"
        "- **Çıkış Kuralı:** 2020'den günümüze hisse bazlı en kârlı **Özel Optimum RSI**\n"
        "- **Portföy Sınırı:** Maksimum **5 Açık Hisse** (`%10` Alım Payı)\n"
        "- **Günlük Bildirim:** AL/SAT varsa tek toplu BIST 30 Portföy Raporu; işlem yoksa *'Bugün sinyal olmamıştır'* özeti"
    )

    tg_token = st.text_input("Telegram Bot Token:", value=TELEGRAM_CONFIG.get("token", ""), type="password")
    tg_chat = st.text_input("Telegram Chat ID:", value=TELEGRAM_CONFIG.get("chat_id", ""))
    st.checkbox("Telegram Bildirimleri Aktif", value=TELEGRAM_CONFIG.get("enabled", True), disabled=True)

    if st.button("🧪 Yeni BIST 30 Telegram Formatını Test Et"):
        if not tg_token or not tg_chat or "BURAYA" in tg_token:
            st.error("Lütfen geçerli bir Bot Token ve Chat ID giriniz.")
        else:
            with st.spinner("Test mesajı gönderiliyor..."):
                ok = test_telegram_connection(token=tg_token, chat_id=tg_chat)
                if ok:
                    st.success("Yeni BIST 30 Optimum RSI test mesajı Telegram'ınıza iletildi! 🎉")
                else:
                    st.error("Mesaj gönderilemedi. Token veya Chat ID bilgilerini kontrol edin.")
