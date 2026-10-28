"""
Plotly ile İnteraktif Grafik Modülü (V7.0 - 1. Mod Hisseye Özel Giriş/Soğuma & Çıkış RSI)
"""
import os
import numpy as np
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from config import get_stock_params, format_stock_entry_rule


def create_chart(
    df: pd.DataFrame,
    symbol: str = "HISSE",
    save_html: bool = True,
    output_dir: str = "charts",
    height: int = 680,
) -> go.Figure:
    """
    1. Mod Hisseye Özel Giriş/Soğuma & Çıkış RSI sinyallerini ve gerçek işlem bağlantı çizgilerini çizer:
    - Panel 1: Mum grafiği, gerçek AL / SAT noktaları ve kâr/zarar bağlantı çizgileri
    - Panel 2: Net Hacim barları ve SMA 5 ortalaması
    - Panel 3: RSI (14), Özel Çıkış Hedefi, Özel Alım Üst Sınırı ve varsa Özel Soğuma (Reset RSI) çizgisi
    """
    plot_df = df.copy()
    if "In_Date_Range" in plot_df.columns:
        first_valid = plot_df[plot_df["In_Date_Range"]].index
        if len(first_valid) > 0:
            plot_df = plot_df.loc[first_valid[0]:]

    clean_sym = symbol.replace(".IS", "")
    sparams = get_stock_params(clean_sym)

    if "Optimal_RSI_Exit" in plot_df.columns and not plot_df.empty:
        opt_rsi = int(plot_df["Optimal_RSI_Exit"].iloc[-1])
    else:
        opt_rsi = int(sparams["exit_rsi"])

    if "Optimal_Max_Buy_RSI" in plot_df.columns and not plot_df.empty:
        max_buy_rsi = float(plot_df["Optimal_Max_Buy_RSI"].iloc[-1])
    else:
        max_buy_rsi = float(sparams.get("max_buy_rsi", 65.0))

    reset_rsi = None
    if "Optimal_Reset_RSI" in plot_df.columns and not plot_df.empty:
        val_rst = plot_df["Optimal_Reset_RSI"].iloc[-1]
        if pd.notna(val_rst) and float(val_rst) > 0:
            reset_rsi = float(val_rst)
    elif sparams.get("reset_rsi") is not None:
        reset_rsi = float(sparams["reset_rsi"])

    rule_txt = format_stock_entry_rule(
        {
            "exit_rsi": opt_rsi,
            "reset_rsi": reset_rsi,
            "max_buy_rsi": max_buy_rsi,
            "cooldown_bars": int(plot_df["Optimal_Cooldown_Bars"].iloc[-1])
            if "Optimal_Cooldown_Bars" in plot_df.columns and not plot_df.empty
            else int(sparams.get("cooldown_bars", 0)),
            "no_higher_bars": int(plot_df["Optimal_No_Higher_Bars"].iloc[-1])
            if "Optimal_No_Higher_Bars" in plot_df.columns and not plot_df.empty
            else int(sparams.get("no_higher_bars", 0)),
        }
    )

    fig = make_subplots(
        rows=3,
        cols=1,
        shared_xaxes=True,
        vertical_spacing=0.035,
        row_heights=[0.60, 0.20, 0.20],
        subplot_titles=(
            f"<b>{clean_sym}</b> - Fiyat & İşlemler (Çıkış: RSI {opt_rsi} | {rule_txt})",
            "<b>Net Hacim Akışı</b> & NV Ortalaması (SMA 5)",
            f"<b>RSI (14)</b> & Hisseye Özel Seviyeler (Çıkış: {opt_rsi}"
            + (f" | Soğuma: ≤{int(reset_rsi)})" if reset_rsi is not None else ")"),
        ),
    )

    # 1. Mum Grafiği
    fig.add_trace(
        go.Candlestick(
            x=plot_df.index,
            open=plot_df["Open"],
            high=plot_df["High"],
            low=plot_df["Low"],
            close=plot_df["Close"],
            name="Fiyat",
            increasing_line_color="#26a69a",
            decreasing_line_color="#ef5350",
        ),
        row=1,
        col=1,
    )

    # 2. Gerçek İşlem Çizgileri (AL -> SAT arası kesikli kâr/zarar çizgisi)
    buy_signals = plot_df[plot_df["Long_Signal"]]
    exit_signals = plot_df[plot_df["Exit_Signal"]]

    buy_dates = list(buy_signals.index)
    exit_dates = list(exit_signals.index)

    exit_labels = []
    for b_dt in buy_dates:
        b_price = float(plot_df.loc[b_dt, "Close"])
        matching_exits = [e_dt for e_dt in exit_dates if e_dt > b_dt]
        if matching_exits:
            e_dt = matching_exits[0]
            e_price = float(plot_df.loc[e_dt, "Close"])
            ret_pct = ((e_price - b_price) / b_price) * 100.0
            line_col = "rgba(0, 230, 118, 0.70)" if ret_pct >= 0 else "rgba(255, 23, 68, 0.75)"
            fig.add_trace(
                go.Scatter(
                    x=[b_dt, e_dt],
                    y=[b_price, e_price],
                    mode="lines",
                    line=dict(color=line_col, width=2, dash="dot"),
                    hoverinfo="skip",
                    showlegend=False,
                ),
                row=1,
                col=1,
            )

    # 3. AL Sinyalleri (Yeşil Üçgen)
    if not buy_signals.empty:
        fig.add_trace(
            go.Scatter(
                x=buy_signals.index,
                y=buy_signals["Low"] * 0.982,
                mode="markers+text",
                marker=dict(
                    symbol="triangle-up",
                    size=14,
                    color="#00e676",
                    line=dict(width=1.2, color="white"),
                ),
                text=[f"AL #{i+1}" for i in range(len(buy_signals))],
                textposition="bottom center",
                textfont=dict(color="#00e676", size=11),
                name="AL Sinyali",
                customdata=buy_signals["Close"],
                hovertemplate="<b>AL Sinyali</b><br>Tarih: %{x|%d.%m.%Y}<br>Kapanış: %{customdata:.2f} TL<extra></extra>",
            ),
            row=1,
            col=1,
        )

    # 4. SAT Sinyalleri (Kırmızı Ters Üçgen + Getiri %)
    if not exit_signals.empty:
        for idx_s, s_dt in enumerate(exit_signals.index):
            s_price = float(plot_df.loc[s_dt, "Close"])
            prior_buys = [b_dt for b_dt in buy_dates if b_dt < s_dt]
            if prior_buys:
                bp = float(plot_df.loc[prior_buys[-1], "Close"])
                rp = ((s_price - bp) / bp) * 100.0
                exit_labels.append(f"SAT #{idx_s+1} (%{rp:+.1f})")
            else:
                exit_labels.append(f"SAT #{idx_s+1}")

        fig.add_trace(
            go.Scatter(
                x=exit_signals.index,
                y=exit_signals["High"] * 1.022,
                mode="markers+text",
                marker=dict(
                    symbol="triangle-down",
                    size=14,
                    color="#ff1744",
                    line=dict(width=1.2, color="white"),
                ),
                text=exit_labels,
                textposition="top center",
                textfont=dict(color="#ff5252", size=11),
                name=f"SAT (RSI {opt_rsi})",
                customdata=exit_signals["Close"],
                hovertemplate=f"<b>SAT (RSI {opt_rsi} Kırılımı)</b><br>Tarih: %{{x|%d.%m.%Y}}<br>Kapanış: %{{customdata:.2f}} TL<extra></extra>",
            ),
            row=1,
            col=1,
        )

    # --- PANEL 2: Net Hacim ve Ortalama ---
    if "Net_Volume" in plot_df.columns:
        nv_colors = ["#26a69a" if val >= 0 else "#ef5350" for val in plot_df["Net_Volume"]]
        fig.add_trace(
            go.Bar(
                x=plot_df.index,
                y=plot_df["Net_Volume"],
                marker_color=nv_colors,
                name="Net Hacim",
                opacity=0.75,
            ),
            row=2,
            col=1,
        )
        if "NV_Avg" in plot_df.columns:
            fig.add_trace(
                go.Scatter(
                    x=plot_df.index,
                    y=plot_df["NV_Avg"],
                    line=dict(color="#ffb74d", width=1.5),
                    name="NV Ortalaması (SMA 5)",
                ),
                row=2,
                col=1,
            )

    # --- PANEL 3: RSI ve Hisseye Özel Seviyeler ---
    if "RSI" in plot_df.columns:
        fig.add_trace(
            go.Scatter(
                x=plot_df.index,
                y=plot_df["RSI"],
                line=dict(color="#ab47bc", width=2),
                name="RSI (14)",
            ),
            row=3,
            col=1,
        )
        fig.add_hline(
            y=opt_rsi,
            line_dash="dash",
            line_color="#ff1744",
            line_width=1.5,
            annotation_text=f"Özel Çıkış: RSI {opt_rsi}",
            annotation_position="top left",
            annotation_font=dict(color="#ff5252", size=11),
            row=3,
            col=1,
        )
        fig.add_hline(
            y=max_buy_rsi,
            line_dash="dot",
            line_color="rgba(255, 183, 77, 0.70)",
            line_width=1.2,
            annotation_text=f"Alım Üst RSI: {int(max_buy_rsi)}",
            annotation_position="top right",
            annotation_font=dict(color="#ffb74d", size=10),
            row=3,
            col=1,
        )
        if reset_rsi is not None:
            fig.add_hline(
                y=reset_rsi,
                line_dash="dash",
                line_color="#00e5ff",
                line_width=1.3,
                annotation_text=f"Özel Soğuma: RSI ≤ {int(reset_rsi)}",
                annotation_position="bottom left",
                annotation_font=dict(color="#00e5ff", size=10),
                row=3,
                col=1,
            )
        fig.add_hline(
            y=30,
            line_dash="dash",
            line_color="#26a69a",
            line_width=1,
            row=3,
            col=1,
        )

    fig.update_layout(
        template="plotly_dark",
        paper_bgcolor="#131722",
        plot_bgcolor="#1e222d",
        showlegend=False,
        xaxis_rangeslider_visible=False,
        margin=dict(l=10, r=10, t=28, b=20),
        height=height,
        hovermode="x unified",
    )

    fig.update_xaxes(rangebreaks=[dict(bounds=["sat", "mon"])])

    if save_html:
        os.makedirs(output_dir, exist_ok=True)
        safe_sym = symbol.replace(".IS", "").replace(":", "_")
        filename = os.path.join(output_dir, f"{safe_sym}_chart.html")
        fig.write_html(filename)
        print(f"[Grafik Kaydedildi]: {filename}")

    return fig
