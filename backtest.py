"""
Backtest & Performans Analiz Modülü
TradingView benzeri detaylı işlem analizi (Dağılım, Ortalama Kâr/Zarar, Beklenti, Seriler).
"""
import sys
import pandas as pd
import numpy as np

try:
    if sys.stdout.encoding and sys.stdout.encoding.lower() != 'utf-8':
        sys.stdout.reconfigure(encoding='utf-8')
except Exception:
    pass

import plotly.graph_objects as go
import yfinance as yf
from config import StrategyConfig
from strategy import run_strategy

def calculate_streaks(returns: pd.Series):
    """
    Ardışık en fazla kazanan ve kaybeden işlem serilerini hesaplar.
    """
    if len(returns) == 0:
        return 0, 0
    max_w, max_l = 0, 0
    cur_w, cur_l = 0, 0
    for r in returns:
        if r > 0:
            cur_w += 1
            cur_l = 0
            if cur_w > max_w:
                max_w = cur_w
        elif r < 0:
            cur_l += 1
            cur_w = 0
            if cur_l > max_l:
                max_l = cur_l
        else:
            cur_w = 0
            cur_l = 0
    return max_w, max_l

def backtest_strategy(df: pd.DataFrame, initial_capital: float = 100000.0, fee_pct: float = 0.001) -> dict:
    """
    Hesaplanan sinyallere göre geçmiş işlemleri ve TradingView İşlem Analizi metriklerini hesaplar.
    """
    trades = []
    in_pos = False
    entry_price = 0.0
    entry_date = None
    entry_idx = 0
    capital = initial_capital
    equity_curve = [initial_capital]
    dates = [df.index[0]]

    # Sinyal döngüsü
    for i in range(len(df)):
        current_date = df.index[i]
        close_price = df['Close'].iloc[i]
        long_sig = df['Long_Signal'].iloc[i]
        exit_sig = df['Exit_Signal'].iloc[i]

        if not in_pos and long_sig:
            in_pos = True
            entry_price = close_price * (1.0 + fee_pct)
            entry_date = current_date
            entry_idx = i
            capital_before = capital

        elif in_pos and exit_sig:
            exit_price = close_price * (1.0 - fee_pct)
            ret = (exit_price - entry_price) / entry_price
            pnl_tl = capital_before * ret
            capital = capital_before * (1.0 + ret)
            duration = i - entry_idx

            pos_df = df.iloc[entry_idx : i + 1]
            max_p = pos_df['High'].max() if 'High' in pos_df.columns else max(entry_price, exit_price)
            min_p = pos_df['Low'].min() if 'Low' in pos_df.columns else min(entry_price, exit_price)
            runup_pct = max(0.0, (max_p - entry_price) / entry_price * 100.0)
            drawdown_trade_pct = min(0.0, (min_p - entry_price) / entry_price * 100.0)
            runup_tl = max(0.0, capital_before * (max_p - entry_price) / entry_price)
            drawdown_trade_tl = min(0.0, capital_before * (min_p - entry_price) / entry_price)

            trades.append({
                "trade_num": len(trades) + 1,
                "entry_date": entry_date,
                "exit_date": current_date,
                "entry_price": entry_price,
                "exit_price": exit_price,
                "return_pct": ret * 100.0,
                "pnl_tl": pnl_tl,
                "runup_pct": runup_pct,
                "runup_tl": runup_tl,
                "drawdown_pct": drawdown_trade_pct,
                "drawdown_tl": drawdown_trade_tl,
                "duration_days": duration,
                "win": ret > 0,
                "loss": ret < 0,
                "even": ret == 0
            })
            in_pos = False

        equity_curve.append(capital if not in_pos else capital_before * (close_price / (entry_price / (1.0 + fee_pct))))
        dates.append(current_date)

    trades_df = pd.DataFrame(trades)
    if not trades_df.empty:
        trades_df['cum_pnl_tl'] = trades_df['pnl_tl'].cumsum()
    
    # Metrik Hesaplamaları
    total_trades = len(trades_df)
    if total_trades > 0:
        wins = trades_df[trades_df['win']]
        losses = trades_df[trades_df['loss']]
        evens = trades_df[trades_df['even']]

        win_trades = len(wins)
        loss_trades = len(losses)
        even_trades = len(evens)

        win_rate = (win_trades / total_trades) * 100.0
        loss_rate = (loss_trades / total_trades) * 100.0
        even_rate = (even_trades / total_trades) * 100.0

        avg_trade_ret = trades_df['return_pct'].mean()
        avg_trade_tl = trades_df['pnl_tl'].mean()

        avg_win_pct = wins['return_pct'].mean() if win_trades > 0 else 0.0
        avg_win_tl = wins['pnl_tl'].mean() if win_trades > 0 else 0.0

        avg_loss_pct = losses['return_pct'].mean() if loss_trades > 0 else 0.0
        avg_loss_tl = losses['pnl_tl'].mean() if loss_trades > 0 else 0.0

        max_win_pct = wins['return_pct'].max() if win_trades > 0 else 0.0
        max_win_tl = wins['pnl_tl'].max() if win_trades > 0 else 0.0

        max_loss_pct = losses['return_pct'].min() if loss_trades > 0 else 0.0
        max_loss_tl = losses['pnl_tl'].min() if loss_trades > 0 else 0.0

        gross_profit = wins['return_pct'].sum() if win_trades > 0 else 0.0
        gross_loss = abs(losses['return_pct'].sum()) if loss_trades > 0 else 0.0
        profit_factor = (gross_profit / gross_loss) if gross_loss > 0 else (999.0 if gross_profit > 0 else 0.0)

        # Ortalama Kazanç / Ortalama Kayıp Oranı (Payoff / Win-Loss Ratio)
        win_loss_ratio = abs(avg_win_pct / avg_loss_pct) if avg_loss_pct != 0 else (999.0 if avg_win_pct > 0 else 0.0)

        # Expectancy (Beklenti): İşlem başına beklenen ortalama matematiksel getiri
        expectancy_pct = ((win_rate / 100.0) * avg_win_pct) + ((loss_rate / 100.0) * avg_loss_pct)
        expectancy_tl = ((win_rate / 100.0) * avg_win_tl) + ((loss_rate / 100.0) * avg_loss_tl)

        # Seriler (Streaks)
        max_consec_wins, max_consec_losses = calculate_streaks(trades_df['return_pct'])

        # Süre Analizi (Time patterns)
        avg_duration = trades_df['duration_days'].mean()
        avg_win_duration = wins['duration_days'].mean() if win_trades > 0 else 0.0
        avg_loss_duration = losses['duration_days'].mean() if loss_trades > 0 else 0.0

    else:
        win_trades = loss_trades = even_trades = 0
        win_rate = loss_rate = even_rate = 0.0
        avg_trade_ret = avg_trade_tl = 0.0
        avg_win_pct = avg_win_tl = 0.0
        avg_loss_pct = avg_loss_tl = 0.0
        max_win_pct = max_win_tl = 0.0
        max_loss_pct = max_loss_tl = 0.0
        profit_factor = win_loss_ratio = 0.0
        expectancy_pct = expectancy_tl = 0.0
        max_consec_wins = max_consec_losses = 0
        avg_duration = avg_win_duration = avg_loss_duration = 0.0

    total_return = ((capital - initial_capital) / initial_capital) * 100.0
    
    # Buy & Hold Getirisi
    first_close = df['Close'].iloc[0]
    last_close = df['Close'].iloc[-1]
    buy_and_hold_return = ((last_close - first_close) / first_close) * 100.0

    equity_series = pd.Series(equity_curve[1:], index=df.index)
    peak = equity_series.cummax()
    drawdown_pct = (equity_series - peak) / peak
    drawdown_tl = peak - equity_series
    max_drawdown = drawdown_pct.min() * 100.0
    max_drawdown_tl = drawdown_tl.max()

    # Risk-Düzeltilmiş Getiri (Sharpe & Sortino)
    daily_returns = equity_series.pct_change().dropna()
    if len(daily_returns) > 1 and daily_returns.std() > 0:
        sharpe_ratio = float((daily_returns.mean() / daily_returns.std()) * np.sqrt(252))
        downside_returns = daily_returns[daily_returns < 0]
        if len(downside_returns) > 0 and downside_returns.std() > 0:
            sortino_ratio = float((daily_returns.mean() / downside_returns.std()) * np.sqrt(252))
        else:
            sortino_ratio = 99.0 if daily_returns.mean() > 0 else 0.0
    else:
        sharpe_ratio = 0.0
        sortino_ratio = 0.0

    # Maksimum Çekilme Süresi (Drawdown Duration / Toparlanma Süresi)
    durations = []
    cur_start = None
    for dt, is_dd in (drawdown_pct < 0).items():
        if is_dd:
            if cur_start is None:
                cur_start = dt
        else:
            if cur_start is not None:
                durations.append((dt - cur_start).days)
                cur_start = None
    if cur_start is not None:
        durations.append((df.index[-1] - cur_start).days)
    max_dd_duration_days = max(durations) if durations else 0

    # Yıllık Getiri Dökümü (Yearly Breakdown)
    years = sorted(df.index.year.unique())
    yearly_stats = []
    for yr in years:
        df_prev = df[df.index.year < yr]
        bh_start = df['Close'].iloc[0] if df_prev.empty else df_prev['Close'].iloc[-1]
        bh_end = df[df.index.year == yr]['Close'].iloc[-1]
        bh_ret = ((bh_end - bh_start) / bh_start) * 100.0

        eq_prev = initial_capital if df_prev.empty else equity_series[equity_series.index.year < yr].iloc[-1]
        eq_end = equity_series[equity_series.index.year == yr].iloc[-1]
        strat_ret = ((eq_end - eq_prev) / eq_prev) * 100.0

        if not trades_df.empty:
            yr_t = trades_df[pd.to_datetime(trades_df['exit_date']).dt.year == yr]
            cnt = len(yr_t)
            wins = len(yr_t[yr_t['win']])
            wr = (wins / cnt * 100.0) if cnt > 0 else 0.0
        else:
            cnt = wins = wr = 0

        yearly_stats.append({
            "Yıl": str(yr),
            "Strateji (%)": strat_ret,
            "Al & Tut (%)": bh_ret,
            "İşlem Sayısı": cnt,
            "Kazanan": wins,
            "Kazanma Oranı (%)": wr
        })
    yearly_df = pd.DataFrame(yearly_stats)

    buy_and_hold_series = initial_capital * (df['Close'] / df['Close'].iloc[0])
    cum_pnl_series = equity_series - initial_capital
    bh_pnl_series = buy_and_hold_series - initial_capital

    return {
        "initial_capital": initial_capital,
        "final_capital": capital,
        "net_profit_tl": capital - initial_capital,
        "total_return_pct": total_return,
        "buy_and_hold_pct": buy_and_hold_return,
        "total_trades": total_trades,
        "win_trades": win_trades,
        "loss_trades": loss_trades,
        "even_trades": even_trades,
        "win_rate": win_rate,
        "loss_rate": loss_rate,
        "even_rate": even_rate,
        "avg_trade_return_pct": avg_trade_ret,
        "avg_trade_tl": avg_trade_tl,
        "avg_win_pct": avg_win_pct,
        "avg_win_tl": avg_win_tl,
        "avg_loss_pct": avg_loss_pct,
        "avg_loss_tl": avg_loss_tl,
        "max_win_pct": max_win_pct,
        "max_win_tl": max_win_tl,
        "max_loss_pct": max_loss_pct,
        "max_loss_tl": max_loss_tl,
        "profit_factor": profit_factor,
        "win_loss_ratio": win_loss_ratio,
        "expectancy_pct": expectancy_pct,
        "expectancy_tl": expectancy_tl,
        "max_consecutive_wins": max_consec_wins,
        "max_consecutive_losses": max_consec_losses,
        "avg_duration_days": avg_duration,
        "avg_win_duration": avg_win_duration,
        "avg_loss_duration": avg_loss_duration,
        "max_drawdown_pct": max_drawdown,
        "max_drawdown_tl": max_drawdown_tl,
        "sharpe_ratio": sharpe_ratio,
        "sortino_ratio": sortino_ratio,
        "max_dd_duration_days": max_dd_duration_days,
        "yearly_df": yearly_df,
        "trades": trades_df,
        "equity_curve": equity_series,
        "cum_pnl_series": cum_pnl_series,
        "buy_and_hold_series": buy_and_hold_series,
        "bh_pnl_series": bh_pnl_series
    }

def print_backtest_report(symbol: str, results: dict):
    """
    Backtest sonuçlarını terminale anlaşılır ve şık bir tabloda basar.
    """
    print("\n" + "=" * 60)
    print(f"       İŞLEM ANALİZİ & BACKTEST RAPORU: {symbol}")
    print("=" * 60)
    print(f"  Toplam İşlem Sayısı       : {results['total_trades']}")
    print(f"  Kazanan İşlemler          : {results['win_trades']} (%{results['win_rate']:.1f})")
    print(f"  Kaybeden İşlemler         : {results['loss_trades']} (%{results['loss_rate']:.1f})")
    print(f"  Strateji Toplam Getirisi  : %{results['total_return_pct']:.2f}")
    print(f"  Al & Tut (B&H) Getirisi   : %{results['buy_and_hold_pct']:.2f}")
    print(f"  İşlem Başına Beklenti     : %{results['expectancy_pct']:.2f} ({results['expectancy_tl']:+,.2f} TL)")
    print(f"  Ortalama Kâr              : %{results['avg_win_pct']:.2f} ({results['avg_win_tl']:+,.2f} TL)")
    print(f"  Ortalama Zarar            : %{results['avg_loss_pct']:.2f} ({results['avg_loss_tl']:+,.2f} TL)")
    print(f"  En Büyük Kâr              : %{results['max_win_pct']:.2f} ({results['max_win_tl']:+,.2f} TL)")
    print(f"  En Büyük Zarar            : %{results['max_loss_pct']:.2f} ({results['max_loss_tl']:+,.2f} TL)")
    print(f"  Kâr/Zarar Oranı (Payoff)  : {results['win_loss_ratio']:.2f}")
    print(f"  Kar Faktörü (Profit F.)   : {results['profit_factor']:.2f}")
    print(f"  Maksimum Çekilme (DD)     : %{results['max_drawdown_pct']:.2f}")
    print(f"  En Uzun Seri (Kazan/Kayb) : {results['max_consecutive_wins']} kazanç / {results['max_consecutive_losses']} kayıp")
    print(f"  Ortalama İşlemde Kalma    : {results['avg_duration_days']:.1f} bar/gün")
    print(f"  Başlangıç / Bitiş Kasa    : {results['initial_capital']:,.0f} TL -> {results['final_capital']:,.0f} TL")
    print("=" * 60)

    if not results['trades'].empty:
        print("\nSon 5 İşlem:")
        tail_trades = results['trades'].tail(5)[['entry_date', 'exit_date', 'entry_price', 'exit_price', 'return_pct', 'pnl_tl']]
        print(tail_trades.to_string(index=False))
        print("=" * 60 + "\n")
