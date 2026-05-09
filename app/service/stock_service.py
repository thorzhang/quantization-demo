#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
@Time   : 2026/1/6   
@Author : zhanglei
@File   : app.py
"""
import logging
from collections import defaultdict
from datetime import datetime
from statistics import mean
from typing import List, Dict
from uuid import UUID

import akshare as ak

from app.core.enums.signal import Signal
from app.core.enums.task_enum import FetchTaskStatus
from app.integration.datasource.baostock import BaostockSource
from app.model.fetch_progress import FetchProgress
from app.model.fetch_task import FetchTask
from app.model.stock_basic import StockBasic
from app.repository.fetch_progress_repository import FetchProgressRepository
from app.repository.fetch_task_repository import FetchTaskRepository
from app.repository.stock_basic_repository import StockBasicRepository
from app.repository.stock_daily_repository import StockDailyRepository
from app.schema.fetch_progress_schema import FetchProgressResponse, FetchProgressCreateRequest
from app.schema.fetch_task_schema import FetchTaskResponse, FetchTaskCreateRequest
from app.schema.stock_daily_schema import RemoteStockDailyResponse
from app.strategy.selector import StrategySelector
from app.task.stock_init_task import fetch_all_stocks

logger = logging.getLogger(__name__)


class StockService:

    def __init__(self, stock_basic_repo: StockBasicRepository,
                 stock_daily_repo: StockDailyRepository,
                 fetch_task_repo: FetchTaskRepository,
                 fetch_process_repo: FetchProgressRepository
                 ):
        self.stock_basic_repo = stock_basic_repo
        self.stock_daily_repo = stock_daily_repo
        self.fetch_task_repo = fetch_task_repo
        self.fetch_process_repo = fetch_process_repo

        self.sources = [
            BaostockSource(),
            # TencentSource(),
            # EastMoneySource()
        ]

    # 增量更新股票列表
    def update_stock_basic_delta(self):

        df = ak.stock_info_a_code_name()

        df = df[~(
                df["name"].str.contains("ST|退", na=False)
                | df["code"].str.startswith("9", na=False)
        )]

        # 1. 查出数据库已有的 symbol
        existing_symbols = set(
            self.stock_basic_repo.list_symbols()
        )

        # 2. 只保留数据库中不存在的
        new_stock_basics = [
            StockBasic(
                symbol=row["code"],
                name=row["name"]
            )
            for _, row in df.iterrows()
            if row["code"] not in existing_symbols
        ]

        # 3. 批量保存
        if new_stock_basics:
            self.stock_basic_repo.save_all(new_stock_basics)

        return len(new_stock_basics)

    def create_fetch_task(self, fetch_task_create_request: FetchTaskCreateRequest) -> FetchTaskResponse:
        exist_fetch_tasks = self.fetch_task_repo.get_by_status_and_date_range(
            FetchTaskStatus.RUNNING,
            datetime.strptime(fetch_task_create_request.start_date, "%Y-%m-%d").date(),
            datetime.strptime(fetch_task_create_request.end_date, "%Y-%m-%d").date())
        if len(exist_fetch_tasks) >= 1:
            fetch_task = exist_fetch_tasks[0]
            resume = True
        else:
            fetch_task = FetchTask(
                **fetch_task_create_request.model_dump(mode="json"),
                total_stocks=0,
                completed_stocks=0,
                failed_stocks=0,
                status=FetchTaskStatus.PENDING,
                started_at=datetime.now()
            )
            self.fetch_task_repo.create(fetch_task)
            resume = False

        logger.info("celery task: fetch_all_stocks任务启动")

        fetch_all_stocks.delay(fetch_task.id, resume)

        logger.info("celery task: fetch_all_stocks任务启动")

        return FetchTaskResponse.model_validate(fetch_task)

    def update_fetch_task_by_id(self, task_id: UUID, **kwargs) -> None:
        self.fetch_task_repo.update_by_id(task_id, **kwargs)

    def create_fetch_progress(self, fetch_progress_req: FetchProgressCreateRequest) -> FetchProgressResponse:
        fetch_process = FetchProgress(**fetch_progress_req.model_dump(mode="json"))
        self.fetch_process_repo.create(fetch_process)
        return FetchProgressResponse.model_validate(fetch_process)

    def update_fetch_progress_by_id(self, progress_id: UUID, **kwargs) -> None:
        self.fetch_process_repo.update_by_id(progress_id, **kwargs)

    def fetch_one_history(self, symbol: str, start_date: str, end_date: str) -> List[RemoteStockDailyResponse] | None:
        """抓取单只股票（同步）"""
        last_error = None
        for source in self.sources:
            try:
                data = source.fetch_one_history(symbol, start_date, end_date)
                return data
            except Exception as e:
                last_error = e

        if last_error:
            raise RuntimeError(f"All sources failed for {symbol}: {last_error}")
        return None

    def bulk_upsert_stock_daily(self, stock_datas: List[RemoteStockDailyResponse]) -> None:
        self.stock_daily_repo.bulk_upsert(stock_datas)

    def get_all_symbols(self) -> List[str]:
        """获取所有股票代码"""
        return self.stock_basic_repo.list_symbols()

    def get_pending_stocks(self, task_id: UUID) -> List[str]:
        """获取未完成的股票"""
        completed = self.fetch_process_repo.get_completed_stocks(task_id)

        completed_symbols = [c for c in completed]
        all_symbols = self.get_all_symbols()

        return [s for s in all_symbols if s not in completed_symbols]

    def get_success_stocks(self, task_id: UUID) -> List[str]:
        """获取未完成的股票"""
        return self.fetch_process_repo.get_success_stocks(task_id)

    def get_failed_stocks(self, task_id: UUID) -> List[str]:
        """获取未完成的股票"""
        return self.fetch_process_repo.get_failed_stocks(task_id)

    def get_fetch_task(self, task_id: UUID) -> FetchTaskResponse | None:
        """获取任务"""
        fetch_task = self.fetch_task_repo.get_fetch_task(task_id)

        if fetch_task is None:
            return None

        return FetchTaskResponse.model_validate(fetch_task)

    def increment_fetch_task(self, task_id, success, failed):
        self.fetch_task_repo.increment_fetch_task(task_id, success, failed)

    def get_fetch_progress(self, task_id: UUID, symbol: str) -> FetchProgressResponse | None:
        """获取股票拉取状态"""
        fetch_progress = self.fetch_process_repo.get_fetch_progress(task_id, symbol)

        # 处理未找到记录的情况
        if fetch_progress is None:
            return None
        return FetchProgressResponse.model_validate(fetch_progress)

    def get_recommend_stocks(self, strategy_name: str = "conservative_trend") -> dict[str, list[dict] | list[str]]:
        strategy = StrategySelector.get_strategy(strategy_name)

        all_data = self.stock_daily_repo.get_all_recent_kline(limit=30)

        results: List[Dict] = []

        for symbol, kline in all_data.items():
            if not kline:
                continue

            datas = [
                {
                    "close": d.close,
                    "volume": d.volume,
                    "pct_chg": d.pct_chg,
                    "pe_ttm": d.pe_ttm,
                    "pb_mrq": d.pb_mrq,
                    "turnover": d.turnover,
                }
                for d in kline
            ]

            result = strategy.evaluate(datas)

            results.append({
                "symbol": symbol,
                "signal": result["signal"],
                "score": result["score"]
            })

        results.sort(key=lambda x: x["score"], reverse=True)

        return {"list": results[:20], "strategy": strategy.reason()}

    def run_signal_backtest(
            self,
            strategy_name: str,
            start_date: str,
            end_date: str,
            top_k: int = 10,
            min_history: int = 30,
            take_profit: float = 0.10,
            stop_loss: float = -0.05,
            max_hold_days: int = 20,
    ) -> Dict:
        """
        假设：
        1. 所有股票价值一样
        2. 始终保留股票池中有top_k支股票
        3. 以当日收盘价卖出，限号策略下日收盘价卖出，止盈止损的话当日收盘价卖出
        :param strategy_name: 策略名称
        :param start_date:
        :param end_date:
        :param top_k: 股票池中股票数量
        :param min_history: 最少要有30天历史
        :param take_profit: 止盈线
        :param stop_loss: 止损线
        :param max_hold_days: 最长持有日期
        :return:
        """
        strategy = StrategySelector.get_strategy(strategy_name)

        symbols = self.stock_basic_repo.list_symbols()

        # =========================
        # 缓存股票数据
        # =========================

        stock_data_map = {}

        for symbol in symbols:

            datas = self.stock_daily_repo.get_stock_daily_by_symbol(
                symbol,
                start_date,
                end_date
            )

            if len(datas) < min_history + 2:
                continue

            stock_data_map[symbol] = datas

        # =========================
        # 收集每日买入信号
        # =========================

        buy_signals_by_date = defaultdict(list)

        # 新增：收集每日卖出信号
        sell_signals_by_date = defaultdict(list)

        for symbol, datas in stock_data_map.items():

            daily_dicts = [
                {
                    "close": d.close,
                    "volume": d.volume,
                    "pct_chg": d.pct_chg,
                    "turnover": d.turnover,
                    "pe_ttm": d.pe_ttm,
                    "pb_mrq": d.pb_mrq,
                }
                for d in datas
            ]

            # 因为买入是信号日的下一天，所有-1已保留买入日，防止越界
            for i in range(min_history, len(datas) - 2):

                window = daily_dicts[i - min_history:i + 1]

                result = strategy.evaluate(window)

                signal_date = datas[i].date

                # 处理买入信号
                if result["signal"] == Signal.BUY:
                    buy_signals_by_date[signal_date].append({
                        "symbol": symbol,
                        "score": result["score"],
                        "buy_index": i + 1,
                        "signal_date": signal_date,
                    })

                # 新增：处理卖出信号
                elif result["signal"] == Signal.SELL:
                    sell_signals_by_date[signal_date].append({
                        "symbol": symbol,
                        "sell_index": i + 1,
                        "signal_date": signal_date,
                    })

        # =========================
        # 日期排序
        # =========================

        all_dates = sorted(set(buy_signals_by_date.keys()) | set(sell_signals_by_date.keys()))

        # =========================
        # 当前持仓
        # =========================

        current_positions = {}

        trades = []

        # =========================
        # 主循环（日级）
        # =========================

        for trade_date in all_dates:

            # =====================
            # 1. 策略主动卖出信号检查
            # =====================

            sell_signals = sell_signals_by_date.get(trade_date, [])

            sell_symbols = []

            for sell_signal in sell_signals:
                symbol = sell_signal["symbol"]

                if symbol not in current_positions:
                    continue

                position = current_positions[symbol]

                datas = stock_data_map[symbol]

                sell_index = sell_signal["sell_index"]

                if sell_index >= len(datas):
                    continue

                sell_daily = datas[sell_index]

                sell_price = float(sell_daily.close)

                buy_price = position["buy_price"]

                ret = (sell_price - buy_price) / buy_price

                hold_days = sell_index - position["buy_index"]

                trades.append({
                    "symbol": symbol,
                    "score": position["score"],
                    "buy_date": position["buy_date"],
                    "sell_date": trade_date,
                    "buy_price": buy_price,
                    "sell_price": sell_price,
                    "hold_days": hold_days,
                    "return": ret,
                    "exit_reason": "STRATEGY_SELL",  # 新增退出原因
                })

                sell_symbols.append(symbol)

            # 删除策略卖出的持仓
            for symbol in sell_symbols:
                del current_positions[symbol]

            # =====================
            # 2. 检查止盈止损及最大持有天数
            # =====================

            exit_symbols = []

            for symbol, position in current_positions.items():

                datas = stock_data_map[symbol]

                buy_index = position["buy_index"]

                current_index = None

                for idx in range(buy_index + 1, len(datas)):

                    if datas[idx].date == trade_date:
                        current_index = idx
                        break

                if current_index is None:
                    continue

                buy_price = position["buy_price"]

                current_price = float(datas[current_index].close)

                ret = (current_price - buy_price) / buy_price

                hold_days = current_index - buy_index

                exit_reason = None

                if ret >= take_profit:
                    exit_reason = "TAKE_PROFIT"
                elif ret <= stop_loss:
                    exit_reason = "STOP_LOSS"
                elif hold_days >= max_hold_days:
                    exit_reason = "MAX_HOLD_DAYS"

                if exit_reason:
                    trades.append({
                        "symbol": symbol,
                        "score": position["score"],
                        "buy_date": position["buy_date"],
                        "sell_date": trade_date,
                        "buy_price": buy_price,
                        "sell_price": current_price,
                        "hold_days": hold_days,
                        "return": ret,
                        "exit_reason": exit_reason,
                    })

                    exit_symbols.append(symbol)

            for symbol in exit_symbols:
                del current_positions[symbol]

            # =====================
            # 3. 计算剩余仓位并买入
            # =====================

            available_slots = top_k - len(current_positions)

            if available_slots <= 0:
                continue

            buy_signals = buy_signals_by_date.get(trade_date, [])

            buy_signals.sort(key=lambda x: x["score"], reverse=True)

            selected = []

            for signal in buy_signals:

                symbol = signal["symbol"]

                if symbol in current_positions:
                    continue

                selected.append(signal)

                if len(selected) >= available_slots:
                    break

            for signal in selected:
                symbol = signal["symbol"]

                datas = stock_data_map[symbol]

                buy_index = signal["buy_index"]

                if buy_index >= len(datas):
                    continue

                buy_daily = datas[buy_index]

                buy_price = float(buy_daily.close)

                current_positions[symbol] = {
                    "buy_date": buy_daily.date,
                    "buy_price": buy_price,
                    "buy_index": buy_index,
                    "score": signal["score"],
                }

        return self._calc_signal_stats(trades)

    @staticmethod
    def _calc_signal_stats(trades: List[dict]) -> Dict:

        if not trades:
            return {
                "trade_count": 0
            }

        returns = [t["return"] for t in trades]

        win_trades = [r for r in returns if r > 0]
        loss_trades = [r for r in returns if r <= 0]

        avg_return = mean(returns)

        win_rate = len(win_trades) / len(returns)

        avg_win = mean(win_trades) if win_trades else 0
        avg_loss = mean(loss_trades) if loss_trades else 0

        profit_loss_ratio = (
            abs(avg_win / avg_loss)
            if avg_loss != 0
            else 0
        )

        max_gain = max(returns)
        max_loss = min(returns)

        avg_hold_days = mean([t["hold_days"] for t in trades])

        # =========================
        # 退出原因统计
        # =========================

        exit_reason_stats = defaultdict(int)

        for trade in trades:
            exit_reason_stats[trade["exit_reason"]] += 1

        # =========================
        # 收益分布
        # =========================

        distribution = {
            "gt_10": len([r for r in returns if r > 0.10]),
            "5_10": len([r for r in returns if 0.05 < r <= 0.10]),
            "0_5": len([r for r in returns if 0 < r <= 0.05]),
            "minus_5_0": len([r for r in returns if -0.05 <= r <= 0]),
            "lt_minus_5": len([r for r in returns if r < -0.05]),
        }

        # =========================
        # score 分层统计
        # =========================

        score_buckets = {
            "0.9_1.0": [],
            "0.8_0.9": [],
            "0.7_0.8": [],
            "0.0_0.7": [],
        }

        for trade in trades:

            score = trade["score"]
            ret = trade["return"]

            if score >= 0.9:
                score_buckets["0.9_1.0"].append(ret)

            elif score >= 0.8:
                score_buckets["0.8_0.9"].append(ret)

            elif score >= 0.7:
                score_buckets["0.7_0.8"].append(ret)

            else:
                score_buckets["0.0_0.7"].append(ret)

        score_analysis = {}

        for bucket, values in score_buckets.items():
            score_analysis[bucket] = {
                "count": len(values),
                "avg_return": mean(values) if values else 0,
                "win_rate": (
                    len([v for v in values if v > 0]) / len(values)
                    if values else 0
                )
            }

        return {
            "trade_count": len(trades),

            "avg_return": avg_return,
            "win_rate": win_rate,

            "avg_win": avg_win,
            "avg_loss": avg_loss,

            "profit_loss_ratio": profit_loss_ratio,

            "max_gain": max_gain,
            "max_loss": max_loss,

            "avg_hold_days": avg_hold_days,

            "exit_reason_stats": dict(exit_reason_stats),

            "distribution": distribution,

            "score_analysis": score_analysis,

            "trades": trades,
        }
