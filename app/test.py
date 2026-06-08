"""
量化策略 v6.0 - 修正版
核心修复：
1. 信号和交易日期严格分离
2. 所有计算只使用历史数据
3. 简化逻辑，确保可验证
"""

import glob
import warnings
from pathlib import Path

import numpy as np
import pandas as pd
from tqdm import tqdm

warnings.filterwarnings('ignore')


# =========================================================
# 1. 数据加载
# =========================================================
def load_multiple_files(data_path):
    if isinstance(data_path, str):
        if Path(data_path).is_dir():
            file_list = list(Path(data_path).glob("*.parquet"))
            print(f"找到 {len(file_list)} 个 parquet 文件")
        elif '*' in data_path or '?' in data_path:
            file_list = glob.glob(data_path)
            print(f"找到 {len(file_list)} 个 parquet 文件")
        elif Path(data_path).exists():
            file_list = [data_path]
        else:
            raise FileNotFoundError(f"找不到路径: {data_path}")
    elif isinstance(data_path, list):
        file_list = data_path
    else:
        raise ValueError("data_path 必须是路径或列表")

    df_list = []
    for file in tqdm(file_list, desc="加载文件"):
        df_list.append(pd.read_parquet(file))

    print("正在合并数据...")
    df = pd.concat(df_list, ignore_index=True)
    print(f"合并完成: {len(df):,} 行")
    return df


# =========================================================
# 2. 数据预处理
# =========================================================
def preprocess_data(df, start_date=None, end_date=None):
    if 'symbol' in df.columns:
        df = df.rename(columns={'symbol': 'code'})

    df['date'] = pd.to_datetime(df['date'])

    if start_date:
        df = df[df['date'] >= pd.to_datetime(start_date)]
    if end_date:
        df = df[df['date'] <= pd.to_datetime(end_date)]

    if 'is_st' in df.columns:
        df = df[df['is_st'] == False]

    if 'pe_ttm' in df.columns:
        df = df[(df['pe_ttm'] > 0) & (df['pe_ttm'] < 100)]
    if 'pb_mrq' in df.columns:
        df = df[(df['pb_mrq'] > 0) & (df['pb_mrq'] < 10)]

    if 'pct_chg' in df.columns:
        df['ret'] = df['pct_chg'] / 100
    else:
        df['ret'] = (df['close'] - df['pre_close']) / df['pre_close']

    df = df[(df['ret'] > -0.22) & (df['ret'] < 0.22)]
    df = df.dropna(subset=['close', 'ret', 'open', 'volume'])

    df = df.sort_values(['code', 'date']).reset_index(drop=True)

    print("\n数据预处理完成:")
    print(f"时间范围: {df['date'].min()} ~ {df['date'].max()}")
    print(f"股票数量: {df['code'].nunique()}")
    print(f"数据量: {len(df):,}")

    return df


def optimize_memory(df):
    for col in df.columns:
        col_type = df[col].dtype
        if col_type == 'object' or 'datetime' in str(col_type):
            continue

        try:
            c_min = df[col].min()
            c_max = df[col].max()

            if 'int' in str(col_type):
                if c_min > np.iinfo(np.int8).min and c_max < np.iinfo(np.int8).max:
                    df[col] = df[col].astype(np.int8)
                elif c_min > np.iinfo(np.int16).min and c_max < np.iinfo(np.int16).max:
                    df[col] = df[col].astype(np.int16)
                elif c_min > np.iinfo(np.int32).min and c_max < np.iinfo(np.int32).max:
                    df[col] = df[col].astype(np.int32)
            elif 'float' in str(col_type):
                df[col] = df[col].astype(np.float32)
        except:
            pass

    memory_usage = df.memory_usage(deep=True).sum() / 1024 ** 2
    print(f"优化后内存: {memory_usage:.2f} MB")
    return df


# =========================================================
# 3. 因子计算（严格使用历史数据）
# =========================================================
def calculate_factors(df):
    """
    所有因子都基于截至当日的历史数据
    """
    grouped = df.groupby('code')

    # 收益率（使用历史数据，pct_change天然是历史的）
    df['ret_5d'] = grouped['close'].pct_change(5)
    df['ret_10d'] = grouped['close'].pct_change(10)
    df['ret_20d'] = grouped['close'].pct_change(20)
    df['ret_40d'] = grouped['close'].pct_change(40)

    # 均线
    df['sma20'] = grouped['close'].transform(
        lambda x: x.rolling(20, min_periods=10).mean()
    )
    df['sma60'] = grouped['close'].transform(
        lambda x: x.rolling(60, min_periods=30).mean()
    )

    # 价格相对位置
    df['price_ratio'] = df['close'] / df['sma20'] - 1
    df['price_ratio'] = df['price_ratio'].clip(-0.1, 0.2)

    # 均线趋势
    df['ma_bullish'] = (df['sma20'] > df['sma60']).astype(int)

    # 波动率
    df['vol_20d'] = grouped['ret'].transform(
        lambda x: x.rolling(20, min_periods=10).std()
    )

    # 成交量
    if 'volume' in df.columns:
        df['volume_ma20'] = grouped['volume'].transform(
            lambda x: x.rolling(20, min_periods=10).mean()
        )
        df['volume_ratio'] = df['volume'] / df['volume_ma20'].clip(lower=1)

    # 清理
    df = df.drop(['volume_ma20'], axis=1, errors='ignore')

    return df


# =========================================================
# 4. 市场择时（只使用历史数据）
# =========================================================
def calculate_market_timing(df):
    """
    市场择时：使用截至当日的数据
    """
    # 按日期计算市场平均收益
    market_daily = df.groupby('date')['ret'].mean().reset_index()
    market_daily['nav'] = (1 + market_daily['ret']).cumprod()

    # 计算60日均线（使用历史数据）
    market_daily['sma60'] = market_daily['nav'].rolling(60, min_periods=30).mean()
    market_daily['sma120'] = market_daily['nav'].rolling(120, min_periods=60).mean()

    # 市场状态：指数在60日均线上方
    market_daily['market_ok'] = market_daily['nav'] > market_daily['sma60']

    # 映射回原数据
    market_ok_map = dict(zip(market_daily['date'], market_daily['market_ok']))
    df['market_ok'] = df['date'].map(market_ok_map)

    # 统计
    total_days = len(market_daily)
    good_days = market_daily['market_ok'].sum()
    print(f"\n市场可交易时间: {good_days}/{total_days} ({good_days / total_days:.1%})")

    return df


# =========================================================
# 5. 信号生成（T日收盘后）
# =========================================================
def generate_signals(df, max_positions=10):
    """
    T日收盘后生成T+1日买入信号
    使用T日及之前的数据
    """
    df = df.copy()

    # 动量得分
    momentum = (
            df['ret_20d'].clip(-0.10, 0.25).fillna(0) * 0.5 +
            df['ret_40d'].clip(-0.15, 0.30).fillna(0) * 0.3 +
            df['ret_10d'].clip(-0.08, 0.15).fillna(0) * 0.2
    )

    # 低波动得分
    low_vol = 1 - (df['vol_20d'].clip(0, 0.06) / 0.06)
    low_vol = low_vol.clip(0, 1)

    # 综合得分
    df['score'] = momentum * 0.6 + low_vol * 0.4

    # 成交量加分
    if 'volume_ratio' in df.columns:
        vol_score = df['volume_ratio'].clip(0.5, 2.0) / 2.0
        df['score'] = df['score'] * (0.8 + 0.2 * vol_score)

    # 买入条件
    buy_condition = (
            (df['close'] > 5) &
            (df['vol_20d'] < 0.06) &
            (df['vol_20d'].notna()) &
            (df['ret_20d'] > -0.15) &
            # (df['ma_bullish'] == 1) &
            (df['price_ratio'] > -0.05) &  # 不能离均线太远
            (df['price_ratio'] < 0.15)  # 也不能太高
    )

    # 排名选股
    df['rank'] = df.groupby('date')['score'].rank(method='first', ascending=False)
    df['signal'] = (df['rank'] <= max_positions) & buy_condition & df['market_ok']

    # 统计
    signal_stats = df[df['signal']].groupby('date').size()
    if len(signal_stats) > 0:
        print(f"平均每日信号数: {signal_stats.mean():.1f}")
        print(f"信号天数: {len(signal_stats)}/{len(df['date'].unique())}")

    return df


# =========================================================
# 6. 回测引擎（修正版）
# =========================================================
def backtest(df, initial_capital=1000000, transaction_cost=0.001,
             max_positions=10, stop_loss=-0.06, take_profit=0.10,
             rebalance_days=5):
    """
    逻辑：T日收盘生成信号 → T+1日开盘买入
    """
    trading_days = sorted(df['date'].unique())

    # 构建数据映射
    # signal_on_date: 在T日生成的信号，用于T+1日买入
    signal_map = {}  # date -> list of codes to buy on next day

    # 价格映射
    open_map = {}  # date -> {code: open_price}
    close_map = {}  # date -> {code: close_price}
    high_map = {}  #
    low_map = {}  #

    for date in trading_days:
        day_data = df[df['date'] == date]
        if len(day_data) == 0:
            continue

        # 当日收盘价
        close_map[date] = day_data.set_index('code')['close'].to_dict()
        # 当日开盘价
        open_map[date] = day_data.set_index('code')['open'].to_dict()
        # 当日最高价
        high_map[date] = day_data.set_index('code')['high'].to_dict()
        # 当日最低价
        low_map[date] = day_data.set_index('code')['low'].to_dict()
        # 当日生成的信号（用于次日买入）
        signal_map[date] = day_data[day_data['signal']]['code'].tolist()

    # 回测变量
    cash = initial_capital
    positions = {}  # {code: {'shares': int, 'buy_price': float, 'buy_date': date}}
    portfolio = []
    trades = []

    print(f"\n开始回测，交易日: {len(trading_days)}")

    for i, today in enumerate(trading_days):
        # 获取当日价格
        today_close = close_map.get(today, {})
        today_open = open_map.get(today, {})

        # ===== 1. 检查止盈止损（使用 high/low 判断） =====
        today_high = high_map.get(today, {})
        today_low = low_map.get(today, {})

        to_sell = []

        for code, pos in positions.items():

            if code not in today_high or code not in today_low:
                continue

            buy_price = pos['buy_price']

            high_ret = (today_high[code] - buy_price) / buy_price
            low_ret = (today_low[code] - buy_price) / buy_price

            stop_trigger = low_ret <= stop_loss
            profit_trigger = high_ret >= take_profit

            if stop_trigger or profit_trigger:

                if stop_trigger:
                    sell_price = today_close[code]
                else:
                    sell_price = buy_price * (1 + take_profit)

                to_sell.append((code, sell_price))

        for code, sell_price in to_sell:
            pos = positions[code]

            sell_value = pos['shares'] * sell_price

            cash += sell_value * (1 - transaction_cost)

            trades.append({
                'code': code,
                'buy_date': pos['buy_date'],
                'sell_date': today,
                'buy_price': pos['buy_price'],
                'sell_price': sell_price,
                'return_pct': (sell_price / pos['buy_price'] - 1) * 100,
                'hold_days': (today - pos['buy_date']).days
            })

            del positions[code]

        # ===== 3. 建仓 =====
        # 使用昨日的信号（今天的信号用于明天买入）
        # 注意：第一个交易日没有前一天信号，所以跳过
        if i > 0:
            yesterday = trading_days[i - 1]
            today_signals = signal_map.get(yesterday, [])

            # 调仓条件：持仓不足 或 达到调仓周期
            need_rebalance = (
                    len(positions) < max_positions * 0.5
                    or
                    i % rebalance_days == 0
            )

            if need_rebalance and len(today_signals) > 0:
                # 卖出不在信号中的持仓
                current_codes = set(positions.keys())
                new_codes = set(today_signals[:max_positions])
                to_sell_rebalance = current_codes - new_codes

                for code in to_sell_rebalance:
                    if code in today_open:
                        pos = positions[code]
                        sell_price = today_open[code]
                        sell_value = pos['shares'] * sell_price
                        cash += sell_value * (1 - transaction_cost)

                        trades.append({
                            'code': code,
                            'buy_date': pos['buy_date'],
                            'sell_date': today,
                            'buy_price': pos['buy_price'],
                            'sell_price': sell_price,
                            'return_pct': (sell_price / pos['buy_price'] - 1) * 100,
                            'hold_days': (today - pos['buy_date']).days
                        })
                        del positions[code]

                # 买入新信号
                buy_codes = [c for c in today_signals[:max_positions] if c not in positions]
                if len(buy_codes) > 0 and cash > 0:
                    # 使用当日开盘价买入（注意：这里用的是T日的开盘价）
                    # 因为我们是在T日开盘时执行昨日的信号
                    invest_amount = cash * 0.90
                    per_stock = invest_amount / len(buy_codes)

                    for code in buy_codes:
                        if code in today_open:
                            buy_price = today_open[code]
                            shares = int(per_stock / buy_price / 100) * 100
                            if shares >= 100:
                                cost = shares * buy_price * (1 + transaction_cost)
                                if cost <= cash:
                                    positions[code] = {
                                        'shares': shares,
                                        'buy_price': buy_price,
                                        'buy_date': today
                                    }
                                    cash -= cost

        # ===== 修改5：交易完成后统计净值 =====

        pos_value = 0

        for code, pos in positions.items():

            if code in today_close:
                pos_value += pos['shares'] * today_close[code]
            else:
                pos_value += pos['shares'] * pos['buy_price']

        total_value = cash + pos_value

        prev_value = portfolio[-1]['total_value'] if portfolio else total_value

        portfolio.append({
            'date': today,
            'total_value': total_value,
            'cash': cash,
            'position_value': pos_value,
            'position_count': len(positions),
            'daily_return': total_value / prev_value - 1 if portfolio else 0
        })

        # 进度显示
        if (i + 1) % 500 == 0:
            print(f"进度: {i + 1}/{len(trading_days)} | 净值: {total_value:,.0f} | 持仓: {len(positions)}")

    results = pd.DataFrame(portfolio)
    trades_df = pd.DataFrame(trades)

    # 统计
    if len(trades_df) > 0:
        print(f"\n交易统计:")
        print(f"  总交易次数: {len(trades_df)}")
        print(f"  盈利次数: {(trades_df['return_pct'] > 0).sum()}")
        print(f"  亏损次数: {(trades_df['return_pct'] <= 0).sum()}")
        print(f"  平均持仓天数: {trades_df['hold_days'].mean():.1f}")

    return results, trades_df


# =========================================================
# 7. 绩效评估
# =========================================================
def evaluate(results, trades, initial_capital=1000000):
    if len(results) == 0:
        print("无数据")
        return

    final_value = results['total_value'].iloc[-1]
    total_return = final_value / initial_capital - 1

    days = (results['date'].iloc[-1] - results['date'].iloc[0]).days
    years = days / 365.25
    annual_return = (1 + total_return) ** (1 / years) - 1 if years > 0 else 0

    daily_returns = results['daily_return'].dropna()
    annual_vol = daily_returns.std() * np.sqrt(252) if len(daily_returns) > 0 else 0

    cumulative = results['total_value'] / initial_capital
    running_max = cumulative.expanding().max()
    drawdown = (cumulative - running_max) / running_max
    max_drawdown = drawdown.min()

    sharpe = (annual_return - 0.02) / annual_vol if annual_vol > 0 else 0

    print("\n" + "=" * 70)
    print("回测结果 v6.0")
    print("=" * 70)
    print(f"回测区间: {results['date'].iloc[0].strftime('%Y-%m-%d')} ~ {results['date'].iloc[-1].strftime('%Y-%m-%d')}")
    print(f"回测天数: {days} 天 ({years:.2f}年)")
    print(f"\n【收益指标】")
    print(f"初始资金: {initial_capital:,.0f}")
    print(f"最终资金: {final_value:,.0f}")
    print(f"总收益率: {total_return:.2%}")
    print(f"年化收益率: {annual_return:.2%}")
    print(f"\n【风险指标】")
    print(f"年化波动率: {annual_vol:.2%}")
    print(f"最大回撤: {max_drawdown:.2%}")
    print(f"夏普比率: {sharpe:.2f}")

    if len(trades) > 0:
        win_rate = (trades['return_pct'] > 0).mean()
        avg_win = trades[trades['return_pct'] > 0]['return_pct'].mean() if len(
            trades[trades['return_pct'] > 0]) > 0 else 0
        avg_loss = trades[trades['return_pct'] <= 0]['return_pct'].mean() if len(
            trades[trades['return_pct'] <= 0]) > 0 else 0
        print(f"\n【交易指标】")
        print(f"总交易次数: {len(trades)}")
        print(f"交易胜率: {win_rate:.1%}")
        print(f"平均盈利: {avg_win:.2f}%")
        print(f"平均亏损: {avg_loss:.2f}%")

    print("=" * 70)

    return {'annual_return': annual_return, 'max_drawdown': max_drawdown, 'sharpe': sharpe}


# =========================================================
# 8. 主程序
# =========================================================
def main():
    # 配置
    DATA_PATH = "./"  # 修改为您的数据路径
    START_DATE = "2024-01-01"
    END_DATE = "2026-12-31"
    INITIAL_CAPITAL = 1000000

    # 策略参数
    MAX_POSITIONS = 10
    STOP_LOSS = -0.06
    TAKE_PROFIT = 0.10
    TRANSACTION_COST = 0.001
    REBALANCE_DAYS = 5

    print("=" * 70)
    print("量化策略 v6.0 - 修正版")
    print("=" * 70)
    print(f"最大持仓: {MAX_POSITIONS}只")
    print(f"止盈: {TAKE_PROFIT:.0%} | 止损: {STOP_LOSS:.0%}")
    print(f"调仓周期: {REBALANCE_DAYS}天")
    print(f"手续费: {TRANSACTION_COST * 100:.1f}%")
    print("=" * 70)

    # 执行
    print("\n[1/6] 加载数据...")
    df_raw = load_multiple_files(DATA_PATH)

    print("\n[2/6] 预处理...")
    df = preprocess_data(df_raw, START_DATE, END_DATE)
    df = optimize_memory(df)

    print("\n[3/6] 计算因子...")
    df = calculate_factors(df)

    print("\n[4/6] 市场择时...")
    df = calculate_market_timing(df)

    print("\n[5/6] 生成信号...")
    df = generate_signals(df, MAX_POSITIONS)

    print("\n[6/6] 回测...")
    results, trades = backtest(df, INITIAL_CAPITAL, TRANSACTION_COST,
                               MAX_POSITIONS, STOP_LOSS, TAKE_PROFIT, REBALANCE_DAYS)

    evaluate(results, trades, INITIAL_CAPITAL)

    # 保存
    results.to_csv('backtest_v6.csv', index=False)
    if len(trades) > 0:
        trades.to_csv('trades_v6.csv', index=False)
        print("\n结果已保存: backtest_v6.csv, trades_v6.csv")
    else:
        print("\n结果已保存: backtest_v6.csv")


if __name__ == "__main__":
    main()
