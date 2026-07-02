import logging
from datetime import date
from typing import Dict, Any

import pandas as pd

from app.strategy.selector import StrategySelector

logger = logging.getLogger(__name__)


class SignalBacktestService:

    def __init__(
            self,
            stock_basic_repo,
            stock_daily_repo,
    ):
        self.stock_basic_repo = stock_basic_repo
        self.stock_daily_repo = stock_daily_repo

    def get_daily_trading_signal(
            self,
            strategy_name: str = "momentum",
            current_positions: Dict[str, Dict] = None,
            cash: float = 1000000,  # 新增：当前可用现金
            max_positions: int = 8,
            stop_loss: float = -0.05,
            take_profit: float = 0.08,
            rebalance_days: int = 10,
            min_score: float = 0.5,
            transaction_cost: float = 0.0005,
    ) -> Dict[str, Any]:
        """
        生成每日交易信号（复用预计算评分）
        返回: {
            'buy_list': [{'symbol': '000001', 'score': 0.85, 'suggest_shares': 100}, ...],
            'sell_list': [{'symbol': '000002', 'reason': 'stop_loss', 'execution': 'today'}, ...],
            'hold_list': [{'symbol': '000003', 'score': 0.72}, ...],
            'signal_date': '2026-01-06',  # 信号生成日期(T日)
            'execution_date': '2026-01-07',  # 买入建议执行日期(T+1日)
            'stop_loss_today': True  # 是否有今日需要执行的止损
        }
        """
        current_positions = current_positions or {}
        strategy = StrategySelector.get_strategy(strategy_name)

        logger.info("=" * 80)
        logger.info("量化策略 v9.3 - 每日交易信号生成 (T日)")
        logger.info("=" * 80)
        logger.info("时序逻辑:")
        logger.info("  T日(今日盘中/收盘后): 止盈止损立即执行 → 计算因子 → 生成明日买入信号")
        logger.info("  T+1日(明日开盘): 执行买入")
        logger.info(f"\n【策略参数】")
        logger.info(f"当前现金: {cash:,.0f}")
        logger.info(f"最大持仓: {max_positions}只")
        logger.info(f"止盈/止损: {take_profit:.0%}/{stop_loss:.0%}")
        logger.info(f"调仓周期: {rebalance_days}天")
        logger.info(f"最低得分: {min_score}")
        logger.info("=" * 80)

        # 1. 获取最新数据
        logger.info("加载数据...")

        required_days = 120
        all_data = self.stock_daily_repo.get_all_recent_kline(limit=required_days)

        rows = []
        for symbol, stock_list in all_data.items():
            for stock in stock_list:
                rows.append({
                    'symbol': stock.symbol,
                    'date': stock.date,
                    'open': stock.open,
                    'close': stock.close,
                    'pre_close': stock.pre_close,
                    'high': stock.high,
                    'low': stock.low,
                    'volume': stock.volume,
                    'amount': stock.amount,
                    'turnover': stock.turnover,
                    'pct_chg': stock.pct_chg,
                    'pe_ttm': stock.pe_ttm,
                    'pb_mrq': stock.pb_mrq,
                    'is_st': stock.is_st
                })

        df_raw = pd.DataFrame(rows)

        if len(df_raw) > 0:
            earliest_date = df_raw['date'].min()
            latest_date = df_raw['date'].max()
            start_date = earliest_date.strftime('%Y-%m-%d')
            end_date = latest_date.strftime('%Y-%m-%d')
            logger.info(f"数据时间范围: {start_date} ~ {end_date}")
        else:
            start_date = None
            end_date = None
            logger.info("警告: 未获取到任何数据")
            return {
                'buy_list': [],
                'sell_list': [],
                'hold_list': [],
                'signal_date': None,
                'execution_date': None,
                'stop_loss_today': False,
                'summary': {}
            }

        # 2. 调用策略的 generate_signals 方法获取完整信号数据
        df_with_signals = strategy.generate_signals(
            df_raw,
            max_positions=max_positions,
            min_score=min_score,
            start_date=start_date,
            end_date=end_date
        )

        # 3. 提取最新交易日的信号
        latest_date = df_with_signals['date'].max()
        today_data = df_with_signals[df_with_signals['date'] == latest_date].copy()

        logger.info(f"\n信号生成日期(T日): {latest_date.strftime('%Y-%m-%d')}")
        logger.info(f"今日候选股票数: {len(today_data)}")
        logger.info(f"今日信号股票数: {today_data['signal'].sum()}")

        # 4. 获取今日的评分和信号
        score_map = today_data.set_index('symbol')['score'].to_dict()
        signal_map = today_data.set_index('symbol')['signal'].to_dict()

        # 获取今日价格数据
        today_close_prices = today_data.set_index('symbol')['close'].to_dict()
        today_high_prices = today_data.set_index('symbol')['high'].to_dict()
        today_low_prices = today_data.set_index('symbol')['low'].to_dict()
        today_open_prices = today_data.set_index('symbol')['open'].to_dict()

        # 5. 处理现有持仓，检查止盈止损（当天执行）
        sell_list_today = []  # 今天立即卖出的
        hold_list = []  # 继续持有的
        updated_cash = cash  # 更新后的现金（卖出后）

        for symbol, pos in current_positions.items():
            if symbol not in today_close_prices:
                # 停牌或无数据，建议持有观察
                hold_list.append({
                    'symbol': symbol,
                    'score': score_map.get(symbol, 0.5),
                    'reason': 'no_data'
                })
                continue

            buy_price = pos.get('buy_price', 0)
            buy_date = pos.get('buy_date')
            shares = pos.get('shares', 0)

            if buy_price <= 0 or shares <= 0:
                hold_list.append({
                    'symbol': symbol,
                    'score': score_map.get(symbol, 0.5),
                    'reason': 'invalid_position'
                })
                continue

            # 计算今日最高/最低收益率
            high_ret = (today_high_prices[symbol] - buy_price) / buy_price
            low_ret = (today_low_prices[symbol] - buy_price) / buy_price
            current_ret = (today_close_prices[symbol] - buy_price) / buy_price

            # 检查止盈止损（当天执行）
            if low_ret <= stop_loss:
                # 触发止损，今天立即卖出
                sell_price = today_close_prices[symbol]  # 用收盘价卖出
                sell_value = shares * sell_price
                updated_cash += sell_value * (1 - transaction_cost)  # 扣除交易费用

                sell_list_today.append({
                    'symbol': symbol,
                    'reason': 'stop_loss',
                    'execution': 'today',  # 今天执行
                    'loss_pct': low_ret,
                    'sell_price': sell_price,
                    'shares': shares,
                    'sell_value': sell_value,
                    'buy_price': buy_price,
                    'buy_date': buy_date,
                    'hold_days': (latest_date - buy_date).days if buy_date else 0
                })
                logger.info(f"  ⚠️ 止损信号: {symbol} 亏损{low_ret:.1%}, 今日立即卖出")

            elif high_ret >= take_profit:
                # 触发止盈，今天立即卖出
                sell_price = buy_price * (1 + take_profit)  # 按目标价卖出
                sell_value = shares * sell_price
                updated_cash += sell_value * (1 - transaction_cost)

                sell_list_today.append({
                    'symbol': symbol,
                    'reason': 'take_profit',
                    'execution': 'today',
                    'profit_pct': take_profit,
                    'sell_price': sell_price,
                    'shares': shares,
                    'sell_value': sell_value,
                    'buy_price': buy_price,
                    'buy_date': buy_date,
                    'hold_days': (latest_date - buy_date).days if buy_date else 0
                })
                logger.info(f"  ✅ 止盈信号: {symbol} 盈利{take_profit:.1%}, 今日立即卖出")
            else:
                # 检查是否应该因为信号消失而卖出（第二天执行）
                should_sell_signal = not signal_map.get(symbol, False)

                if should_sell_signal:
                    # 信号消失，建议第二天卖出
                    sell_list_today.append({
                        'symbol': symbol,
                        'reason': 'signal_lost',
                        'execution': 'tomorrow',  # 明天执行
                        'loss_pct': current_ret,
                        'sell_price': today_close_prices[symbol],
                        'shares': shares,
                        'sell_value': shares * today_close_prices[symbol],
                        'current_score': score_map.get(symbol, 0),
                        'buy_price': buy_price,
                        'buy_date': buy_date,
                        'hold_days': (latest_date - buy_date).days if buy_date else 0
                    })
                    logger.info(f"  📉 信号消失: {symbol} 得分{score_map.get(symbol, 0):.3f}, 建议明日卖出")
                else:
                    # 继续持有
                    hold_list.append({
                        'symbol': symbol,
                        'score': score_map.get(symbol, 0.5),
                        'shares': shares,
                        'buy_price': buy_price,
                        'buy_date': buy_date,
                        'current_return': current_ret,
                        'hold_days': (latest_date - buy_date).days if buy_date else 0
                    })

        # 6. 计算当前有效持仓数量和可用现金
        # 已触发止盈止损的股票今天会卖出，不计入明日持仓
        active_holdings = [h for h in hold_list]
        # 信号消失的明天才卖出，所以今天还持有
        signal_lost_symbols = [s['symbol'] for s in sell_list_today if s.get('execution') == 'tomorrow']
        active_holdings += [{
            'symbol': symbol,
            'score': next((s['current_score'] for s in sell_list_today if s['symbol'] == symbol), 0),
            'shares': next((s['shares'] for s in sell_list_today if s['symbol'] == symbol), 0),
            'will_sell_tomorrow': True
        } for symbol in signal_lost_symbols]

        current_count = len(active_holdings)

        # 7. 生成买入建议（根据现金和最大持仓）
        buy_list = []

        # 计算最大可购买股票数量
        max_buy_count = max_positions - current_count
        max_buy_count = max(0, max_buy_count)

        if max_buy_count > 0 and updated_cash > 10000:
            # 获取今日有买入信号的股票
            signal_stocks = today_data[today_data['signal'] == True].copy()

            # 排除已持有的和即将卖出的
            excluded_symbols = set([h['symbol'] for h in active_holdings] + [s['symbol'] for s in sell_list_today])
            buy_candidates = signal_stocks[~signal_stocks['symbol'].isin(excluded_symbols)]

            # 按得分排序
            buy_candidates = buy_candidates.sort_values('score', ascending=False)

            # 计算每只股票的建议买入数量（基于现金平均分配）
            per_stock_cash = updated_cash * 0.9 / max_buy_count  # 预留10%现金

            for idx, row in buy_candidates.head(max_buy_count).iterrows():
                symbol = row['symbol']
                suggested_price = today_open_prices.get(symbol, row['close'])  # 建议使用明日开盘价
                suggested_shares = int(per_stock_cash / suggested_price / 100) * 100  # 按100股取整

                if suggested_shares >= 100:
                    buy_list.append({
                        'symbol': symbol,
                        'score': row['score'],
                        'reason': 'signal_trigger',
                        'suggest_price': suggested_price,
                        'suggest_shares': suggested_shares,
                        'suggest_value': suggested_shares * suggested_price,
                        'signal_strength': row['score'],
                        'price_position': row.get('price_position', 0),
                        'vol_20d': row.get('vol_20d', 0)
                    })

            # 如果资金不够买满，调整数量
            total_buy_value = sum([b['suggest_value'] for b in buy_list])
            if total_buy_value > updated_cash * 0.9:
                # 按比例调整
                ratio = (updated_cash * 0.9) / total_buy_value
                for b in buy_list:
                    b['suggest_shares'] = int(b['suggest_shares'] * ratio / 100) * 100
                    b['suggest_value'] = b['suggest_shares'] * b['suggest_price']

        # 8. 分离今天执行和明天执行的卖出
        sell_list_today_execute = [s for s in sell_list_today if s.get('execution') == 'today']
        sell_list_tomorrow = [s for s in sell_list_today if s.get('execution') == 'tomorrow']

        # 9. 构建返回结果
        from datetime import timedelta
        next_trading_day = latest_date + timedelta(days=1)
        while next_trading_day.weekday() >= 5:
            next_trading_day += timedelta(days=1)

        result = {
            'buy_list': buy_list,  # 明天买入
            'sell_list_today': sell_list_today_execute,  # 今天立即卖出（止盈止损）
            'sell_list_tomorrow': sell_list_tomorrow,  # 明天卖出（信号消失）
            'hold_list': hold_list,  # 继续持有
            'signal_date': latest_date.strftime('%Y-%m-%d'),
            'execution_date': next_trading_day.strftime('%Y-%m-%d'),
            'stop_loss_today': len(sell_list_today_execute) > 0,
            'updated_cash': updated_cash,  # 卖出后的现金
            'summary': {
                'total_candidates': len(today_data),
                'signal_count': int(today_data['signal'].sum()),
                'current_positions': len(current_positions),
                'active_holdings': current_count,
                'suggest_buy': len(buy_list),
                'suggest_buy_cash': sum([b['suggest_value'] for b in buy_list]),
                'sell_today': len(sell_list_today_execute),
                'sell_tomorrow': len(sell_list_tomorrow),
                'suggest_hold': len(hold_list),
                'available_cash': updated_cash,
                'market_ok': bool(today_data['market_ok'].iloc[0]) if len(today_data) > 0 else False,
                'avg_score_buy': sum([b['score'] for b in buy_list]) / len(buy_list) if buy_list else 0,
                'reason_stats': {
                    'stop_loss': len([s for s in sell_list_today if s['reason'] == 'stop_loss']),
                    'take_profit': len([s for s in sell_list_today if s['reason'] == 'take_profit']),
                    'signal_lost': len([s for s in sell_list_today if s['reason'] == 'signal_lost'])
                }
            },
            "reason": strategy.reason(),
        }

        # 10. 打印详细建议
        logger.info("\n" + "=" * 80)
        logger.info("【交易建议】")
        logger.info("=" * 80)

        if result['sell_list_today']:
            logger.info(f"\n🔴 今日立即卖出 ({len(result['sell_list_today'])}只):")
            for sell in result['sell_list_today']:
                if sell['reason'] == 'stop_loss':
                    logger.info(f"  {sell['symbol']}: 止损 {sell['loss_pct']:.1%} @ {sell['sell_price']:.2f}")
                elif sell['reason'] == 'take_profit':
                    logger.info(f"  {sell['symbol']}: 止盈 +{sell['profit_pct']:.1%} @ {sell['sell_price']:.2f}")

        if result['sell_list_tomorrow']:
            logger.info(f"\n🟡 明日卖出 ({len(result['sell_list_tomorrow'])}只):")
            for sell in result['sell_list_tomorrow']:
                logger.info(f"  {sell['symbol']}: 信号消失, 得分{sell['current_score']:.3f}")

        if result['buy_list']:
            logger.info(f"\n🟢 明日买入 ({len(result['buy_list'])}只):")
            for buy in result['buy_list']:
                logger.info(f"  {buy['symbol']}: 得分={buy['score']:.3f}, "
                            f"建议买入{buy['suggest_shares']}股, "
                            f"约{buy['suggest_value']:,.0f}元")

        if result['hold_list']:
            logger.info(f"\n⚪ 继续持有 ({len(result['hold_list'])}只):")
            for hold in result['hold_list'][:5]:
                ret_str = f", 收益率={hold.get('current_return', 0):.1%}" if 'current_return' in hold else ""
                logger.info(f"  {hold['symbol']}: 得分={hold['score']:.3f}{ret_str}")
            if len(result['hold_list']) > 5:
                logger.info(f"  ... 及其他{len(result['hold_list']) - 5}只")

        logger.info(f"\n💰 资金状况:")
        logger.info(f"  当前现金: {cash:,.0f}")
        logger.info(f"  卖出后现金: {updated_cash:,.0f}")
        logger.info(f"  预计买入金额: {result['summary']['suggest_buy_cash']:,.0f}")
        logger.info(f"  剩余现金: {updated_cash - result['summary']['suggest_buy_cash']:,.0f}")

        if not result['summary']['market_ok']:
            logger.info(f"\n⚠️  市场择时信号: 当前市场环境不佳，建议谨慎操作")

        logger.info("\n" + "=" * 80)

        return result

    def run_backtest(
            self,
            strategy_name: str = "robust_trend",
            max_positions: int = 8,
            stop_loss: float = -0.05,
            take_profit: float = 0.08,
            transaction_cost: float = 0.0005,
            rebalance_days: int = 10,
            min_score: float = 0.5,
            initial_capital: int = 1000000,
            start_date: str = None,
            end_date: str = None
    ) -> Dict[str, Any]:

        strategy = StrategySelector.get_strategy(strategy_name)

        logger.info("=" * 80)
        logger.info("量化策略 v9.3 - 时序修正版")
        logger.info("=" * 80)
        logger.info("时序逻辑:")
        logger.info("  T日: 计算因子 → 市场择时 → 生成信号")
        logger.info("  T+1日: 开盘执行买入")
        logger.info(f"\n【策略参数】")
        logger.info(f"最大持仓: {max_positions}只")
        logger.info(f"止盈/止损: {take_profit:.0%}/{stop_loss:.0%}")
        logger.info(f"调仓周期: {rebalance_days}天")
        logger.info(f"最低得分: {min_score}")
        logger.info("=" * 80)

        # 执行
        logger.info("加载数据...")

        # 获取所有股票最新指标
        all_data = self.stock_daily_repo.get_all_recent_kline(limit=120)

        # 将所有股票数据合并到一个DataFrame
        rows = []
        for symbol, stock_list in all_data.items():
            for stock in stock_list:
                rows.append({
                    'symbol': stock.symbol,  # 或者用 symbol 变量
                    'date': stock.date,
                    'open': stock.open,
                    'close': stock.close,
                    'pre_close': stock.pre_close,
                    'high': stock.high,
                    'low': stock.low,
                    'volume': stock.volume,
                    'amount': stock.amount,
                    'turnover': stock.turnover,
                    'pct_chg': stock.pct_chg,
                    'pe_ttm': stock.pe_ttm,
                    'pb_mrq': stock.pb_mrq,
                    'is_st': stock.is_st
                })

        df_raw = pd.DataFrame(rows)

        df = strategy.generate_signals(df_raw, max_positions, min_score, start_date, end_date)

        results, trades = strategy.backtest(
            df, initial_capital, transaction_cost,
            max_positions, stop_loss, take_profit, rebalance_days
        )

        metrics = strategy.evaluate(results, trades, initial_capital)

        # 保存结果
        results.to_csv('backtest_v93_results.csv', index=False)
        if len(trades) > 0:
            trades.to_csv('backtest_v93_trades.csv', index=False)
            logger.info("\n✅ 结果已保存: backtest_v93_results.csv, backtest_v93_trades.csv")

    def _get_next_trading_day(self, current_date) -> date:
        """获取下一个交易日（需要根据实际交易日历实现）"""
        # 简化实现：返回第二天
        # 实际项目中应该使用交易日历判断
        from datetime import timedelta
        next_day = current_date + timedelta(days=1)

        # 简单跳过周末（生产环境需用真实交易日历）
        while next_day.weekday() >= 5:  # 5=周六,6=周日
            next_day += timedelta(days=1)

        return next_day
