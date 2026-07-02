#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
@Time   : 2026/1/6   
@Author : zhanglei
@File   : app.py
"""
import logging
from typing import List

import numpy as np
import pandas as pd

from app.strategy.base import BaseStrategy

logger = logging.getLogger(__name__)


class MomentumStrategy(BaseStrategy):
    """
    量化策略 v9.3 - 幻方降维版
    核心逻辑：动量(30%) + 反转(30%) + 质量(20%) + 技术(20%)
    """

    @staticmethod
    def reason() -> List[str]:
        return [
            '动量反转复合策略',
            '横截面标准化打分',
            '低波动过滤',
            '动态市场择时',
            '基本面辅助筛选',
        ]

    def preprocess_data(self, df, start_date=None, end_date=None):

        df['date'] = pd.to_datetime(df['date'])

        if start_date:
            df = df[df['date'] >= pd.to_datetime(start_date)]
        if end_date:
            df = df[df['date'] <= pd.to_datetime(end_date)]

        if 'is_st' in df.columns:
            df = df[df['is_st'] == False]

        if 'pe_ttm' in df.columns:
            df = df[(df['pe_ttm'] > 0) & (df['pe_ttm'] < 50)]
        if 'pb_mrq' in df.columns:
            df = df[(df['pb_mrq'] > 0) & (df['pb_mrq'] < 5)]

        df = df[df['close'] > 5]
        df = df[df['close'] < 500]

        if 'pct_chg' in df.columns:
            df['ret'] = df['pct_chg'] / 100
        else:
            df['ret'] = (df['close'] - df['pre_close']) / df['pre_close']

        df = df[(df['ret'] > -0.22) & (df['ret'] < 0.22)]
        df = df.dropna(subset=['close', 'ret', 'open', 'volume'])
        df = df.sort_values(['symbol', 'date']).reset_index(drop=True)

        logger.info("\n数据预处理完成:")
        logger.info(f"时间范围: {df['date'].min()} ~ {df['date'].max()}")
        logger.info(f"股票数量: {df['symbol'].nunique()}")
        logger.info(f"数据量: {len(df):,}")

        return df

    def optimize_memory(self, df):
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
        logger.info(f"优化后内存: {memory_usage:.2f} MB")
        return df

    # 2. 因子计算
    def calculate_factor_library(self, df):
        grouped = df.groupby('symbol')

        # 价量因子（pct_change和rolling只使用历史数据）
        df['ret_5d'] = grouped['close'].pct_change(5)
        df['ret_10d'] = grouped['close'].pct_change(10)
        df['ret_20d'] = grouped['close'].pct_change(20)
        df['ret_60d'] = grouped['close'].pct_change(60)

        df['vol_10d'] = grouped['ret'].transform(
            lambda x: x.rolling(10, min_periods=5).std()
        )
        df['vol_20d'] = grouped['ret'].transform(
            lambda x: x.rolling(20, min_periods=10).std()
        )

        df['volume_ratio'] = grouped['volume'].transform(
            lambda x: x / x.rolling(20, min_periods=10).mean()
        )

        df['sma20'] = grouped['close'].transform(
            lambda x: x.rolling(20, min_periods=10).mean()
        )
        df['sma60'] = grouped['close'].transform(
            lambda x: x.rolling(60, min_periods=30).mean()
        )
        df['price_position'] = (df['close'] - df['sma20']) / df['sma20']

        # 基本面因子
        if 'pe_ttm' in df.columns:
            df['pe_score'] = 1 / (df['pe_ttm'].clip(5, 50))
        else:
            df['pe_score'] = 0.5

        if 'pb_mrq' in df.columns:
            df['pb_score'] = 1 / (df['pb_mrq'].clip(1, 5))
        else:
            df['pb_score'] = 0.5

        # 技术形态因子
        df['ma_bullish'] = (df['sma20'] > df['sma60']).astype(float)
        df['oversold'] = (-df['ret_20d']).clip(0, 0.3) / 0.3

        return df

    # 3. 横截面标准化（在同一日期内，使用当日数据）
    def cross_sectional_normalize(self, df, column):
        """横截面标准化：在同一日期内，使用当日的均值和标准差"""

        def norm(group):
            mean = group.mean()
            std = group.std()
            if std > 0:
                return (group - mean) / std
            else:
                return group * 0

        df[column + '_cs_norm'] = df.groupby('date')[column].transform(norm)
        # 映射到[0,1]
        df[column + '_cs_norm'] = df[column + '_cs_norm'].clip(-3, 3)
        df[column + '_cs_norm'] = (df[column + '_cs_norm'] + 3) / 6

        return df

    def calculate_dynamic_scores(self, df):
        """计算动态因子得分"""
        df = df.copy()

        # 原始动量得分
        momentum_raw = (df['ret_20d'].fillna(0) * 0.5 +
                        df['ret_60d'].fillna(0) * 0.3 +
                        df['ret_10d'].fillna(0) * 0.2)

        df = self.cross_sectional_normalize(df.assign(momentum_raw=momentum_raw), 'momentum_raw')
        momentum_score = df['momentum_raw_cs_norm'].fillna(0.5)

        # 反转得分（已在[0,1]）
        reversal_score = df['oversold'].fillna(0)

        # 质量得分
        quality_raw = (df['pe_score'].fillna(0) * 0.4 + df['pb_score'].fillna(0) * 0.6)
        df = self.cross_sectional_normalize(df.assign(quality_raw=quality_raw), 'quality_raw')
        quality_score = df['quality_raw_cs_norm'].fillna(0.5)

        # 技术得分
        technical_raw = df['ma_bullish'].fillna(0) * 0.4 + (1 - df['vol_20d'].clip(0, 0.05) / 0.05).fillna(0) * 0.6
        df = self.cross_sectional_normalize(df.assign(technical_raw=technical_raw), 'technical_raw')
        technical_score = df['technical_raw_cs_norm'].fillna(0.5)

        # 综合得分
        df['score'] = (momentum_score * 0.3 +
                       reversal_score * 0.3 +
                       quality_score * 0.2 +
                       technical_score * 0.2)

        # 清理临时列
        drop_cols = [col for col in df.columns if col.endswith('_cs_norm') or
                     col in ['momentum_raw', 'quality_raw', 'technical_raw']]
        df = df.drop(drop_cols, axis=1, errors='ignore')

        return df

    # 4. 市场择时
    def calculate_market_timing(self, df, lookback_days=60, min_trading_days_ratio=0.2):
        """
        市场择时：T日计算市场状态，直接用于T日信号
        信号将用于T+1日执行，无需额外shift
        """
        # 计算每日市场收益
        market_daily = df.groupby('date')['ret'].mean().reset_index()
        market_daily['nav'] = (1 + market_daily['ret']).cumprod()

        # 使用滚动窗口计算指标（只使用历史数据）
        market_daily['sma20'] = market_daily['nav'].rolling(20, min_periods=5).mean()
        market_daily['sma60'] = market_daily['nav'].rolling(60, min_periods=15).mean()

        # 价格位置和趋势得分
        market_daily['price_score'] = (market_daily['nav'] / market_daily['sma60'] - 1).fillna(0)
        market_daily['trend_score'] = (market_daily['sma20'] / market_daily['sma60'] - 1).fillna(0)
        market_daily['market_score'] = market_daily['price_score'] + market_daily['trend_score']

        # 使用滚动分位数计算动态阈值（只用历史数据）
        market_daily['threshold'] = market_daily['market_score'].rolling(
            lookback_days, min_periods=20
        ).quantile(1 - min_trading_days_ratio)

        # 当日阈值用前一天的值（避免未来函数）
        market_daily['threshold'] = market_daily['threshold']
        market_daily['threshold'] = market_daily['threshold'].fillna(market_daily['market_score'].quantile(0.5))

        # 生成择时信号（T日市场状态）
        market_daily['market_ok'] = market_daily['market_score'] > market_daily['threshold']

        # 平滑处理（连续3天中有2天满足）
        market_daily['market_ok'] = market_daily['market_ok'].rolling(3, min_periods=2).mean() >= 0.5
        market_daily['market_ok'] = market_daily['market_ok'].fillna(False)

        # 关键修正：不需要 shift(1)
        # market_ok 代表 T 日的市场状态，T日生成的信号将在 T+1 日执行
        # 所以 market_ok 直接用于 T 日的信号生成即可

        # 映射回原数据
        market_map = dict(zip(market_daily['date'], market_daily['market_ok']))
        df['market_ok'] = df['date'].map(market_map).fillna(False)

        total_days = len(market_daily)
        good_days = market_daily['market_ok'].sum()
        logger.info(f"\n市场择时统计:")
        logger.info(f"  可交易天数: {good_days}/{total_days} ({good_days / total_days:.1%})")
        logger.info(f"  使用历史窗口: {lookback_days}天")

        return df

    # 5. 信号生成
    def generate_signals(self, df_raw: pd.DataFrame, max_positions=8, min_score=0.5, start_date=None, end_date=None):
        """
        信号生成：T日收盘后生成信号
        信号将用于T+1日开盘买入
        """

        logger.info("\n[1/4] 数据预处理...")
        df = self.preprocess_data(df_raw, start_date, end_date)
        df = self.optimize_memory(df)

        logger.info("\n[2/4] 计算因子...")
        df = self.calculate_factor_library(df)
        df = self.calculate_dynamic_scores(df)

        logger.info("\n[3/4] 市场择时...")
        df = self.calculate_market_timing(df, lookback_days=60, min_trading_days_ratio=0.2)

        logger.info("\n[4/4] 生成信号...")

        # 买入条件
        buy_condition = (
                (df['close'] > 5) &
                (df['vol_20d'] < 0.08) &
                (df['vol_20d'].notna()) &
                (df['ret_20d'] > -0.30) &
                (df['price_position'] > -0.15) &
                (df['price_position'] < 0.15) &
                (df['score'].notna())
        )

        # 得分条件
        score_condition = df['score'] >= min_score

        # 综合信号（T日生成）
        df['signal_raw'] = buy_condition & score_condition & df['market_ok']

        # 按得分排名选股
        df['rank'] = df.groupby('date')['score'].rank(method='first', ascending=False)
        df['signal'] = df['signal_raw'] & (df['rank'] <= max_positions)

        # 统计
        signal_df = df[df['signal']].groupby('date').size()
        if len(signal_df) > 0:
            logger.info(f"\n信号统计:")
            logger.info(f"  平均每日信号数: {signal_df.mean():.1f}")
            logger.info(f"  信号天数: {len(signal_df)}/{len(df['date'].unique())}")
            logger.info(f"  总信号数: {df['signal'].sum()}")

        return df

    # 6. 回测引擎
    def backtest(self, df, initial_capital=1000000, transaction_cost=0.0005,
                 max_positions=8, stop_loss=-0.05, take_profit=0.08,
                 rebalance_days=10):
        """
        回测逻辑：
        - T日收盘生成信号（signal）
        - T+1日开盘执行买入
        - 止盈止损使用T日盘中价格判断
        """
        trading_days = sorted(df['date'].unique())

        # 构建数据映射
        daily_data = {}
        for date in trading_days:
            day_data = df[df['date'] == date]
            if len(day_data) > 0:
                daily_data[date] = {
                    'open': day_data.set_index('symbol')['open'].to_dict(),
                    'close': day_data.set_index('symbol')['close'].to_dict(),
                    'high': day_data.set_index('symbol')['high'].to_dict(),
                    'low': day_data.set_index('symbol')['low'].to_dict(),
                    'signals': day_data[day_data['signal']]['symbol'].tolist(),  # T日信号
                    'scores': day_data.set_index('symbol')['score'].to_dict()
                }

        cash = initial_capital
        positions = {}  # {symbol: {'shares': int, 'buy_price': float, 'buy_date': date}}
        portfolio = []
        trades = []
        last_rebalance = -rebalance_days

        logger.info(f"\n开始回测")
        logger.info(f"交易日: {len(trading_days)}")
        logger.info(f"最大持仓: {max_positions}只")
        logger.info(f"止盈/止损: {take_profit:.0%}/{stop_loss:.0%}")
        logger.info(f"调仓周期: {rebalance_days}天")
        logger.info("-" * 70)

        for i, today in enumerate(trading_days):
            if today not in daily_data:
                continue

            today_data = daily_data[today]

            # ===== 1. 止盈止损检查（使用今日盘中价格）=====
            to_sell = []
            for symbol, pos in positions.items():
                if symbol not in today_data.get('high', {}):
                    continue

                buy_price = pos['buy_price']
                high_ret = (today_data['high'][symbol] - buy_price) / buy_price
                low_ret = (today_data['low'][symbol] - buy_price) / buy_price

                if low_ret <= stop_loss:
                    sell_price = today_data['close'][symbol]  # 止损用收盘价
                    to_sell.append((symbol, sell_price, 'stop_loss'))
                elif high_ret >= take_profit:
                    sell_price = buy_price * (1 + take_profit)  # 止盈按目标价
                    to_sell.append((symbol, sell_price, 'take_profit'))

            for symbol, sell_price, reason in to_sell:
                pos = positions[symbol]
                sell_value = pos['shares'] * sell_price
                cash += sell_value * (1 - transaction_cost)

                trades.append({
                    'symbol': symbol,
                    'buy_date': pos['buy_date'],
                    'sell_date': today,
                    'buy_price': pos['buy_price'],
                    'sell_price': sell_price,
                    'return_pct': (sell_price / pos['buy_price'] - 1) * 100,
                    'hold_days': (today - pos['buy_date']).days,
                    'reason': reason
                })
                del positions[symbol]

            # ===== 2. 调仓（使用昨天的信号）=====
            # 关键：昨天的信号，在今天开盘执行
            if i > 0 and (i - last_rebalance >= rebalance_days or len(positions) < max_positions * 0.3):
                yesterday = trading_days[i - 1]
                if yesterday in daily_data:
                    yesterday_signals = daily_data[yesterday]['signals']

                    if len(yesterday_signals) > 0:
                        # 卖出不在新信号中的持仓
                        new_signal_set = set(yesterday_signals[:max_positions])
                        for symbol in list(positions.keys()):
                            if symbol not in new_signal_set and symbol in today_data['open']:
                                pos = positions[symbol]
                                sell_price = today_data['open'][symbol]
                                sell_value = pos['shares'] * sell_price
                                cash += sell_value * (1 - transaction_cost)
                                trades.append({
                                    'symbol': symbol,
                                    'sell_date': today,
                                    'sell_price': sell_price,
                                    'reason': 'rebalance',
                                    'buy_date': pos['buy_date'],
                                    'buy_price': pos['buy_price'],
                                    'return_pct': (sell_price / pos['buy_price'] - 1) * 100,
                                    'hold_days': (today - pos['buy_date']).days
                                })
                                del positions[symbol]

                        # 买入新信号（使用今日开盘价）
                        buy_symbols = [symbol for symbol in yesterday_signals[:max_positions] if
                                       symbol not in positions]
                        if len(buy_symbols) > 0 and cash > 10000:
                            per_stock = cash * 0.9 / len(buy_symbols)
                            for symbol in buy_symbols:
                                if symbol in today_data['open']:
                                    buy_price = today_data['open'][symbol]
                                    shares = int(per_stock / buy_price / 100) * 100
                                    if shares >= 100:
                                        cost = shares * buy_price * (1 + transaction_cost)
                                        if cost <= cash:
                                            positions[symbol] = {
                                                'shares': shares,
                                                'buy_price': buy_price,
                                                'buy_date': today
                                            }
                                            cash -= cost
                        last_rebalance = i

            # ===== 3. 记录净值 =====
            pos_value = 0
            for symbol, pos in positions.items():
                if symbol in today_data['close']:
                    pos_value += pos['shares'] * today_data['close'][symbol]
                else:
                    pos_value += pos['shares'] * pos['buy_price']

            total_value = cash + pos_value

            if len(portfolio) > 0:
                daily_return = total_value / portfolio[-1]['total_value'] - 1
            else:
                daily_return = 0

            portfolio.append({
                'date': today,
                'total_value': total_value,
                'position_count': len(positions),
                'daily_return': daily_return
            })

            if (i + 1) % 100 == 0:
                ret_pct = (total_value / initial_capital - 1) * 100
                logger.info(
                    f"进度: {i + 1}/{len(trading_days)} | 净值: {total_value:,.0f} | 收益: {ret_pct:+.1f}% | 持仓: {len(positions)}")

        return pd.DataFrame(portfolio), pd.DataFrame(trades)

    def evaluate(self, results, trades, initial_capital=1000000):
        if len(results) == 0:
            logger.info("无数据")
            return {}

        final_value = results['total_value'].iloc[-1]
        total_return = final_value / initial_capital - 1

        days = (results['date'].iloc[-1] - results['date'].iloc[0]).days
        years = days / 365.25
        annual_return = (1 + total_return) ** (1 / years) - 1 if years > 0 else 0

        daily_returns = results['daily_return'].dropna()
        annual_vol = daily_returns.std() * np.sqrt(252) if len(daily_returns) > 0 else 0

        cumulative = results['total_value'] / initial_capital
        running_max = cumulative.expanding().max()
        max_drawdown = (cumulative / running_max - 1).min()

        sharpe = (annual_return - 0.02) / annual_vol if annual_vol > 0 else 0

        logger.info("\n" + "=" * 80)
        logger.info("回测结果 v9.3 - 时序修正版")
        logger.info("=" * 80)
        logger.info(
            f"回测区间: {results['date'].iloc[0].strftime('%Y-%m-%d')} ~ {results['date'].iloc[-1].strftime('%Y-%m-%d')}")
        logger.info(f"回测天数: {days} 天 ({years:.2f}年)")

        logger.info(f"\n{'【收益指标】':^30}")
        logger.info(f"初始资金: {initial_capital:>20,.0f}")
        logger.info(f"最终资金: {final_value:>20,.0f}")
        logger.info(f"总收益率: {total_return:>19.2%}")
        logger.info(f"年化收益率: {annual_return:>18.2%}")

        logger.info(f"\n{'【风险指标】':^30}")
        logger.info(f"年化波动率: {annual_vol:>19.2%}")
        logger.info(f"最大回撤: {max_drawdown:>20.2%}")
        logger.info(f"夏普比率: {sharpe:>21.2f}")

        if len(trades) > 0:
            win_rate = (trades['return_pct'] > 0).mean()
            avg_win = trades[trades['return_pct'] > 0]['return_pct'].mean() if len(
                trades[trades['return_pct'] > 0]) > 0 else 0
            avg_loss = trades[trades['return_pct'] <= 0]['return_pct'].mean() if len(
                trades[trades['return_pct'] <= 0]) > 0 else 0

            logger.info(f"\n{'【交易指标】':^30}")
            logger.info(f"总交易次数: {len(trades):>19d}")
            logger.info(f"交易胜率: {win_rate:>21.1%}")
            logger.info(f"平均盈利: {avg_win:>20.2f}%")
            logger.info(f"平均亏损: {avg_loss:>20.2f}%")

            if 'reason' in trades.columns:
                logger.info(f"\n{'【卖出原因】':^30}")
                for reason in trades['reason'].unique():
                    count = len(trades[trades['reason'] == reason])
                    logger.info(f"  {reason}: {count} ({count / len(trades):.1%})")

        logger.info("=" * 80)
        return {'total_return': total_return, 'annual_return': annual_return, 'max_drawdown': max_drawdown,
                'sharpe': sharpe}
