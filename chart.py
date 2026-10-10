"""
Plotly ile TradingView Benzeri İnteraktif Grafik Modülü
"""
import os
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import pandas as pd

def create_chart(df: pd.DataFrame, symbol: str = "HISSE", save_html: bool = True, output_dir: str = "charts", height: int = 650) -> go.Figure:
    """
    Pine Script görselleştirmesini birebir Plotly interaktif grafiğine dönüştürür:
    - Panel 1: Mum grafiği, Çıkış Destek Seviyesi (Lowest Low), AL / SAT / RSI Uyarı işaretleri
    - Panel 2: Net Hacim barları ve Hacim Hareketli Ortalaması (SMA)
    - Panel 3: RSI (14) çizgisi ve 70 / 30 seviyeleri
    Mobil ve masaüstü ekranlar için optimize edilmiştir.
    """
    # Sadece tarih filtresi içindeki veya son 1-2 yıllık veriyi gösterelim
    plot_df = df.copy()
    if 'In_Date_Range' in plot_df.columns:
        # Eğer tarih filtresi aktifse, grafiği başlangıçtan itibaren göster
        first_valid = plot_df[plot_df['In_Date_Range']].index
        if len(first_valid) > 0:
            plot_df = plot_df.loc[first_valid[0]:]

    fig = make_subplots(
        rows=3, cols=1,
        shared_xaxes=True,
        vertical_spacing=0.03,
        row_heights=[0.60, 0.20, 0.20],
        subplot_titles=(
            f"<b>{symbol}</b> - Fiyat & Sinyaller",
            "<b>Net Hacim Akışı</b> & NV Ortalaması",
            "<b>RSI (14)</b> & Aşırı Alım Uyarısı (70)"
        )
    )

    # 1. Mum Grafiği
    fig.add_trace(
        go.Candlestick(
            x=plot_df.index,
            open=plot_df['Open'],
            high=plot_df['High'],
            low=plot_df['Low'],
            close=plot_df['Close'],
            name="Fiyat",
            increasing_line_color="#26a69a",
            decreasing_line_color="#ef5350"
        ),
        row=1, col=1
    )

    # 2. Lowest Low Exit Destek Çizgisi (Pine Script: Lowest Low Exit)
    if 'Lowest_Low_Exit' in plot_df.columns:
        fig.add_trace(
            go.Scatter(
                x=plot_df.index,
                y=plot_df['Lowest_Low_Exit'].shift(1),
                mode='lines',
                line=dict(color='rgba(255, 0, 255, 0.7)', width=1.5, dash='dot'),
                name="Çıkış Destek Seviyesi (Lowest Low)"
            ),
            row=1, col=1
        )

    # 3. AL Sinyalleri (Pine Script: Long Condition - Yeşil Üçgen)
    buy_signals = plot_df[plot_df['Long_Signal']]
    if not buy_signals.empty:
        fig.add_trace(
            go.Scatter(
                x=buy_signals.index,
                y=buy_signals['Low'] * 0.985,
                mode='markers+text',
                marker=dict(symbol='triangle-up', size=14, color='#00e676', line=dict(width=1, color='white')),
                text=["AL" for _ in range(len(buy_signals))],
                textposition="bottom center",
                textfont=dict(color="#00e676", size=11),
                name="AL Sinyali",
                hoverinfo="x+y+text"
            ),
            row=1, col=1
        )

    # 4. RSI Uyarısı (Pine Script: rsiWarning - Turuncu Baklava)
    rsi_warns = plot_df[plot_df['RSI_Warning']]
    if not rsi_warns.empty:
        fig.add_trace(
            go.Scatter(
                x=rsi_warns.index,
                y=rsi_warns['High'] * 1.015,
                mode='markers',
                marker=dict(symbol='diamond', size=9, color='#ff9800', line=dict(width=1, color='black')),
                name="RSI Uyarısı (Aşırı Alımdan Dönüş)",
                hoverinfo="x+y+name"
            ),
            row=1, col=1
        )

    # 5. SAT Sinyalleri (Pine Script: Exit Condition - Kırmızı Ters Üçgen)
    exit_signals = plot_df[plot_df['Exit_Signal']]
    if not exit_signals.empty:
        fig.add_trace(
            go.Scatter(
                x=exit_signals.index,
                y=exit_signals['High'] * 1.025,
                mode='markers+text',
                marker=dict(symbol='triangle-down', size=14, color='#ff1744', line=dict(width=1, color='white')),
                text=["SAT" for _ in range(len(exit_signals))],
                textposition="top center",
                textfont=dict(color="#ff1744", size=11),
                name="SAT Sinyali",
                hoverinfo="x+y+text"
            ),
            row=1, col=1
        )

    # --- PANEL 2: Net Hacim ve Ortalama ---
    if 'Net_Volume' in plot_df.columns:
        nv_colors = ['#26a69a' if val >= 0 else '#ef5350' for val in plot_df['Net_Volume']]
        fig.add_trace(
            go.Bar(
                x=plot_df.index,
                y=plot_df['Net_Volume'],
                marker_color=nv_colors,
                name="Net Hacim",
                opacity=0.75
            ),
            row=2, col=1
        )
        if 'NV_Avg' in plot_df.columns:
            fig.add_trace(
                go.Scatter(
                    x=plot_df.index,
                    y=plot_df['NV_Avg'],
                    line=dict(color='#ffb74d', width=1.5),
                    name="NV Ortalaması (SMA 5)"
                ),
                row=2, col=1
            )

    # --- PANEL 3: RSI Çizgisi ve Referans Çizgileri ---
    if 'RSI' in plot_df.columns:
        fig.add_trace(
            go.Scatter(
                x=plot_df.index,
                y=plot_df['RSI'],
                line=dict(color='#ab47bc', width=2),
                name="RSI (14)"
            ),
            row=3, col=1
        )
        # Aşırı alım çizgisi (70)
        fig.add_hline(y=70, line_dash="dash", line_color="#ef5350", line_width=1, row=3, col=1)
        # Aşırı satım çizgisi (30)
        fig.add_hline(y=30, line_dash="dash", line_color="#26a69a", line_width=1, row=3, col=1)

    # Genel Görünüm ve TradingView Koyu Tema Ayarları (Mobil ve Masaüstü Uyumlu)
    fig.update_layout(
        template="plotly_dark",
        paper_bgcolor="#131722",
        plot_bgcolor="#1e222d",
        title=dict(
            text=f"<b>{symbol}</b> | Net Hacim & RSI Çıkış Stratejisi V5.1",
            font=dict(size=14, color="#e0e0e0"),
            x=0.02
        ),
        xaxis_rangeslider_visible=False,
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.02,
            xanchor="right",
            x=1,
            font=dict(size=9)
        ),
        margin=dict(l=15, r=15, t=40, b=25),
        height=height,
        hovermode='x unified'
    )

    # Hafta sonu boşluklarını temizle (Borsa açık günleri göster)
    fig.update_xaxes(rangebreaks=[dict(bounds=["sat", "mon"])])

    if save_html:
        os.makedirs(output_dir, exist_ok=True)
        safe_sym = symbol.replace(".IS", "").replace(":", "_")
        filename = os.path.join(output_dir, f"{safe_sym}_chart.html")
        fig.write_html(filename)
        print(f"[Grafik Kaydedildi]: {filename}")

    return fig
