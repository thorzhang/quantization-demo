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
            hold_days: int = 5,
            top_k: int = 10,
            min_history: int = 30,
    ) -> Dict:
        """
        如下假设：
        1. 每支股票都买相同的数量，持有hold_days天
        2. 每天推荐得分最高的10支股票，但是保证股票池中只存在10支股票，不够了补齐
        :param strategy_name:
        :param start_date:
        :param end_date:
        :param hold_days: 持有天数
        :param top_k: 得分最高的top_k支股票
        :param min_history:
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

            if len(datas) < min_history + hold_days:
                continue

            stock_data_map[symbol] = datas

        # =========================
        # 收集每日信号
        # =========================

        signals_by_date = defaultdict(list)

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

            for i in range(min_history, len(datas) - hold_days):

                # =====================
                # 使用历史 window
                # =====================

                window = daily_dicts[i - min_history: i + 1]

                result = strategy.evaluate(window)

                if result["signal"] != "BUY":
                    continue

                trade_date = datas[i].date

                signals_by_date[trade_date].append({
                    "symbol": symbol,
                    "score": result["score"],
                    "buy_index": i,
                })

        # =========================
        # 日期排序
        # =========================

        sorted_dates = sorted(signals_by_date.keys())

        # =========================
        # 当前持仓
        # =========================

        current_positions = {}
        # symbol -> sell_date

        trades = []

        for trade_date in sorted_dates:

            # =====================
            # 清理已卖出持仓
            # =====================

            expired_symbols = []

            for symbol, sell_date in current_positions.items():

                if trade_date >= sell_date:
                    expired_symbols.append(symbol)

            for symbol in expired_symbols:
                del current_positions[symbol]

            # =====================
            # 获取当天信号
            # =====================

            signals = signals_by_date[trade_date]

            # score 倒序
            signals.sort(
                key=lambda x: x["score"],
                reverse=True
            )

            # 当前还能买几个
            available_slots = top_k - len(current_positions)

            if available_slots <= 0:
                continue

            selected = []

            for signal in signals:

                symbol = signal["symbol"]

                # 已持仓则跳过
                if symbol in current_positions:
                    continue

                selected.append(signal)

                if len(selected) >= available_slots:
                    break

            # =====================
            # 执行买入
            # =====================

            for signal in selected:
                symbol = signal["symbol"]
                buy_index = signal["buy_index"]

                datas = stock_data_map[symbol]

                buy_daily = datas[buy_index]
                sell_daily = datas[buy_index + hold_days]

                buy_price = float(buy_daily.close)
                sell_price = float(sell_daily.close)

                ret = (sell_price - buy_price) / buy_price

                trades.append({
                    "symbol": symbol,

                    "score": signal["score"],

                    "trade_date": trade_date,

                    "buy_date": buy_daily.date,
                    "sell_date": sell_daily.date,

                    "buy_price": buy_price,
                    "sell_price": sell_price,

                    "hold_days": hold_days,

                    "return": ret,
                })

                # 加入当前持仓
                current_positions[symbol] = sell_daily.date

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

            "distribution": distribution,

            "score_analysis": score_analysis,

            "trades": trades,
        }
