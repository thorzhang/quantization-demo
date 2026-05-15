#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
@Time   : 2026/1/6   
@Author : zhanglei
@File   : app.py
"""
import logging
import random
from collections import defaultdict
from datetime import datetime
from statistics import mean
from typing import List, Dict
from uuid import UUID

import akshare as ak
import pandas as pd

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

    def get_daily_trading_signal(
            self,
            strategy_name: str = "robust_trend",
            current_positions: Dict[str, Dict] = None,
            max_single_position_pct: float = 0.15,
            init_position_pct: float = 0.05,
            max_total_positions: int = 10,
            take_profit: float = 0.15,
            stop_loss: float = -0.07,
            max_hold_days: int = 30,
            score_threshold: int = 50,
    ) -> Dict:
        """
        生成每日交易信号（复用预计算评分）
        """
        current_positions = current_positions or {}
        strategy = StrategySelector.get_strategy(strategy_name)

        # 获取所有股票最新指标
        all_data = self.stock_daily_repo.get_all_recent_kline(limit=120)

        stock_data_map = {}
        for symbol, kline in all_data.items():
            if len(kline) < 60:
                continue
            stock_data_map[symbol] = kline

        indicators_map = StockService.precompute_indicators(stock_data_map, min_history=60)

        # 【修改点1】预计算所有股票的 daily_scores（只计算一次）
        daily_scores = {}  # symbol -> {"signal": x, "score": y}

        for symbol, df in indicators_map.items():
            # 获取最新一天的指标
            latest_date = df.index[-1]
            r = df.loc[latest_date]

            indicators = {
                'current_price': float(r['close']),
                'ma5': float(r['ma5']),
                'ma20': float(r['ma20']),
                'ma60': float(r['ma60']),
                'drawdown_20': float(r['drawdown_20']),
                'avg_amount_20': float(r['avg_amount_20']),
                'avg_volume_20': float(r['avg_volume_20']),
                'recent_10d_return': float(r['recent_10d_return']),
                'volatility': float(r['volatility']),
                'vol_ratio': float(r['vol_ratio']),
                'pe': float(r['pe_ttm']) if r['pe_ttm'] > 0 else 0,
                'pb': float(r['pb_mrq']) if r['pb_mrq'] > 0 else 0,
                'pct_chg_day': float(r['pct_chg']),
                'pct_chg_3d_sum': float(r['pct_chg_3d_sum']) if 'pct_chg_3d_sum' in r else 0,
            }

            result = strategy.evaluate(indicators)
            daily_scores[symbol] = {
                "signal": result["signal"],
                "score": result["score"]
            }

        today = datetime.now().date()

        # 获取最近一个交易日
        all_dates = set()
        for df in indicators_map.values():
            for date in df.index:
                all_dates.add(date)
        latest_date = sorted(all_dates)[-1] if all_dates else None

        if not latest_date:
            return {"buy": [], "sell": [], "hold": [], "strategy": strategy.reason()}

        # ========== 1. 处理现有持仓：检查卖出信号 ==========
        sell_signals = []
        hold_signals = []

        for symbol, pos in current_positions.items():
            if symbol not in indicators_map or symbol not in daily_scores:
                hold_signals.append({"symbol": symbol, "return": 0, "hold_days": 0, "signal": "NO_DATA"})
                continue

            df = indicators_map[symbol]
            if latest_date not in df.index:
                hold_signals.append({"symbol": symbol, "return": 0, "hold_days": 0, "signal": "NO_DATA"})
                continue

            r = df.loc[latest_date]
            current_price = float(r['close'])
            buy_price = pos["buy_price"]
            buy_date = datetime.strptime(pos["buy_date"], "%Y-%m-%d").date() if isinstance(pos["buy_date"], str) else \
                pos["buy_date"]
            hold_days = (today - buy_date).days
            ret = (current_price - buy_price) / buy_price

            # 【修改点2】直接使用预计算的 daily_scores，不再重复调用 strategy.evaluate
            signal = daily_scores[symbol]["signal"]
            score = daily_scores[symbol]["score"]

            # 检查各种卖出条件
            exit_reason = None

            if signal == Signal.SELL:
                exit_reason = "STRATEGY_SELL"
            elif ret >= take_profit:
                exit_reason = "TAKE_PROFIT"
            elif ret <= stop_loss:
                exit_reason = "STOP_LOSS"
            elif hold_days >= max_hold_days:
                exit_reason = "MAX_HOLD_DAYS"

            if exit_reason:
                sell_signals.append({
                    "symbol": symbol,
                    "exit_reason": exit_reason,
                    "return": ret,
                    "hold_days": hold_days,
                    "score": score,
                    "sell_price": current_price,
                    "buy_price": buy_price,
                    "weight": pos.get("weight", 0),
                })
            else:
                hold_signals.append({
                    "symbol": symbol,
                    "return": ret,
                    "hold_days": hold_days,
                    "score": score,
                    "signal": "HOLD",
                    "current_price": current_price,
                    "buy_price": buy_price,
                    "weight": pos.get("weight", 0),
                })

        # ========== 2. 计算可用仓位 ==========
        current_total_weight = sum(p.get("weight", 0.0) for p in current_positions.values())
        selling_weight = sum(s.get("weight", 0.0) for s in sell_signals)
        available_weight = 1.0 - (current_total_weight - selling_weight)

        # ========== 3. 找出买入候选（直接使用 daily_scores） ==========
        held_symbols = set(current_positions.keys())
        sold_symbols = set([s["symbol"] for s in sell_signals])

        buy_candidates = []

        for symbol, score_info in daily_scores.items():
            if symbol in held_symbols or symbol in sold_symbols:
                continue

            if symbol not in indicators_map:
                continue

            df = indicators_map[symbol]
            if latest_date not in df.index:
                continue

            # 【修改点3】直接使用预计算的评分和信号
            if score_info["signal"] == Signal.BUY and score_info["score"] >= score_threshold:
                r = df.loc[latest_date]
                buy_candidates.append({
                    "symbol": symbol,
                    "score": score_info["score"],
                    "current_price": float(r['close']),
                })

        # 按评分降序排序
        buy_candidates.sort(key=lambda x: x["score"], reverse=True)

        # ========== 4. 动态分配仓位 ==========
        buy_signals = []

        remaining_positions_count = len([h for h in hold_signals])
        max_new_positions = max_total_positions - remaining_positions_count

        candidates_to_buy = buy_candidates[:max_new_positions] if max_new_positions > 0 else []

        if candidates_to_buy and available_weight > 0:
            # 等权重分配
            weight_per_stock = min(
                init_position_pct,
                available_weight / len(candidates_to_buy)
            )

            for candidate in candidates_to_buy:
                if available_weight <= 0:
                    break

                actual_weight = min(weight_per_stock, available_weight, max_single_position_pct)

                if actual_weight > 0.01:
                    buy_signals.append({
                        "symbol": candidate["symbol"],
                        "score": candidate["score"],
                        "weight": actual_weight,
                        "price": candidate["current_price"],
                    })
                    available_weight -= actual_weight

        return {
            "buy": buy_signals,
            "sell": sell_signals,
            "hold": hold_signals,
            "strategy": strategy.reason(),
            "trade_date": latest_date.strftime("%Y-%m-%d") if hasattr(latest_date, 'strftime') else str(latest_date),
            "available_weight": available_weight,
            "current_total_weight": current_total_weight,
            "selling_weight": selling_weight,
            "stats": {
                "total_candidates": len(buy_candidates),
                "max_new_positions": max_new_positions,
                "remaining_positions": remaining_positions_count,
            }
        }

    def run_signal_backtest(
            self,
            strategy_name: str,
            start_date: str,
            end_date: str,
            top_k: int = 10,
            min_history: int = 60,
            take_profit: float = 0.15,
            stop_loss: float = -0.07,
            max_hold_days: int = 30,
            init_position_pct: float = 0.05,  # 【修改点1】新增：初始买入仓位
            max_single_position_pct: float = 0.15,  # 单只股票最大仓位（最终可加仓达到）
            max_total_positions: int = 20,  # 【修改点2】新增：最大持仓数量
            score_threshold: int = 50,  # 【修改点3】新增：买入最低评分
            market_width_sample_size: int = 500,
            market_width_frequency: int = 5,
    ) -> Dict:
        """
        优化版回测 - 使用预计算指标 + 抽样市场宽度 + 动态仓位分配
        """
        strategy = StrategySelector.get_strategy(strategy_name)
        symbols = self.stock_basic_repo.list_symbols()

        # =========================
        # 1. 加载原始数据
        # =========================
        stock_data_map = {}
        for symbol in symbols:
            datas = self.stock_daily_repo.get_stock_daily_by_symbol(
                symbol, start_date, end_date
            )
            if len(datas) < min_history + 10:
                continue
            stock_data_map[symbol] = datas

        logger.info(f"加载完成，共 {len(stock_data_map)} 只股票")

        # =========================
        # 2. 预计算所有指标（pandas 向量化）
        # =========================
        logger.info("正在预计算技术指标（向量化）...")
        indicators_map = self.precompute_indicators(stock_data_map, min_history)
        logger.info(f"指标计算完成，共 {len(indicators_map)} 只股票")

        # =========================
        # 3. 获取所有日期
        # =========================
        all_dates = sorted(set().union(*[set(df.index) for df in indicators_map.values()]))

        logger.info(f"交易日数量: {len(all_dates)}")

        # =========================
        # 4. 预计算每日评分（直接从 indicators_map 读取，无需重建窗口）
        # =========================
        logger.info("正在预计算每日评分...")
        daily_scores = defaultdict(dict)  # date -> {symbol: {"signal": x, "score": y}}

        for date in all_dates:
            for symbol, df in indicators_map.items():
                if date not in df.index:
                    continue

                r = df.loc[date]

                indicators = {
                    'current_price': float(r['close']),
                    'ma5': float(r['ma5']),
                    'ma20': float(r['ma20']),
                    'ma60': float(r['ma60']),
                    'drawdown_20': float(r['drawdown_20']),
                    'avg_amount_20': float(r['avg_amount_20']),
                    'avg_volume_20': float(r['avg_volume_20']),
                    'recent_10d_return': float(r['recent_10d_return']),
                    'volatility': float(r['volatility']),
                    'vol_ratio': float(r['vol_ratio']),
                    'pe': float(r['pe_ttm']) if r['pe_ttm'] > 0 else 0,
                    'pb': float(r['pb_mrq']) if r['pb_mrq'] > 0 else 0,
                    'pct_chg_day': float(r['pct_chg']),
                    'pct_chg_3d_sum': float(r['pct_chg_3d_sum']) if 'pct_chg_3d_sum' in r else 0,
                }

                result = strategy.evaluate(indicators)
                daily_scores[date][symbol] = {
                    "signal": result["signal"],
                    "score": result.get("score", 0.0)
                }

        logger.info("评分预计算完成")

        # =========================
        # 5. 计算市场宽度（抽样 + 低频）
        # =========================
        logger.info("正在计算市场宽度（抽样）...")
        market_width_by_date = self.compute_market_width_sampled(
            indicators_map=indicators_map,
            all_dates=all_dates,
            sample_size=market_width_sample_size,
            compute_frequency=market_width_frequency
        )

        # =========================
        # 6. 辅助函数
        # =========================
        def get_next_trade_date(current_date):
            for d in all_dates:
                if d > current_date:
                    return d
            return None

        # =========================
        # 7. 主循环（修改部分）
        # =========================
        current_positions = {}  # symbol -> {buy_date, buy_price, buy_idx, score, weight}
        trades = []
        pending_buy_orders = []
        pending_sell_orders = []
        pending_market_clear_date = None

        # 建立日期到索引的映射（用于快速查找 next_date）
        date_to_index = {date: i for i, date in enumerate(all_dates)}

        for trade_date in all_dates:

            # 执行卖出订单
            orders_to_execute = [o for o in pending_sell_orders if o["exec_date"] == trade_date]
            for order in orders_to_execute:
                symbol = order["symbol"]
                if symbol not in current_positions:
                    continue

                exit_reason = order["exit_reason"]
                pos = current_positions[symbol]
                df = indicators_map.get(symbol)

                if df is None or trade_date not in df.index:
                    continue

                r = df.loc[trade_date]
                sell_price = float(r['close'])
                ret = (sell_price - pos["buy_price"]) / pos["buy_price"]
                hold_days = (date_to_index[trade_date] - date_to_index[pos["buy_date"]])
                trades.append({
                    "symbol": symbol,
                    "score": pos["score"],
                    "buy_date": pos["buy_date"],
                    "sell_date": trade_date,
                    "buy_price": pos["buy_price"],
                    "sell_price": sell_price,
                    "hold_days": hold_days,
                    "return": ret,
                    "exit_reason": exit_reason,
                    "weight": pos["weight"],  # 【修改点4】记录仓位权重
                })
                del current_positions[symbol]
            pending_sell_orders = [o for o in pending_sell_orders if o["exec_date"] != trade_date]

            # 执行市场清仓
            if pending_market_clear_date == trade_date:
                for symbol, pos in list(current_positions.items()):
                    df = indicators_map.get(symbol)
                    if df is None or trade_date not in df.index:
                        continue

                    r = df.loc[trade_date]
                    sell_price = float(r['close'])
                    ret = (sell_price - pos["buy_price"]) / pos["buy_price"]
                    hold_days = (date_to_index[trade_date] - date_to_index[pos["buy_date"]])
                    trades.append({
                        "symbol": symbol,
                        "score": pos["score"],
                        "buy_date": pos["buy_date"],
                        "sell_date": trade_date,
                        "buy_price": pos["buy_price"],
                        "sell_price": sell_price,
                        "hold_days": hold_days,
                        "return": ret,
                        "exit_reason": "MARKET_WIDTH",
                        "weight": pos["weight"],
                    })
                current_positions.clear()
                pending_buy_orders = [o for o in pending_buy_orders if o["exec_date"] != trade_date]
                pending_market_clear_date = None
                continue

            # 【修改点5】执行买入订单 - 动态权重分配
            orders_to_execute = [o for o in pending_buy_orders if o["exec_date"] == trade_date]

            # 计算当前总仓位（未执行买入前）
            current_total_weight = sum(p.get("weight", 0.0) for p in current_positions.values())

            for order in orders_to_execute:
                symbol = order["symbol"]
                if symbol in current_positions:
                    continue

                score = order["score"]
                target_weight = order["weight"]  # 预分配的权重

                # 检查是否超过最大持仓数
                if len(current_positions) >= max_total_positions:
                    break

                # 检查可用仓位
                current_total_weight = sum(p.get("weight", 0.0) for p in current_positions.values())
                if current_total_weight + target_weight > 1.0:
                    # 仓位不足，调整权重
                    target_weight = 1.0 - current_total_weight
                    if target_weight < 0.01:  # 小于1%就不买了
                        break

                df = indicators_map.get(symbol)
                if df is None or trade_date not in df.index:
                    continue

                r = df.loc[trade_date]
                buy_price = float(r['close'])

                current_positions[symbol] = {
                    "buy_date": trade_date,
                    "buy_price": buy_price,
                    "score": score,
                    "weight": target_weight,
                }
            pending_buy_orders = [o for o in pending_buy_orders if o["exec_date"] != trade_date]

            # ========== 产生明天的订单 ==========

            market_width = market_width_by_date.get(trade_date, 0.5)
            if market_width < 0.5:
                next_date = get_next_trade_date(trade_date)
                if next_date and pending_market_clear_date is None:
                    pending_market_clear_date = next_date
                continue

            next_date = get_next_trade_date(trade_date)
            if next_date is None:
                continue

            # 检查持仓卖出信号
            for symbol, pos in current_positions.items():
                info = daily_scores.get(trade_date, {}).get(symbol)
                if not info:
                    continue

                if info["signal"] == Signal.SELL:
                    pending_sell_orders.append({
                        "symbol": symbol,
                        "exit_reason": "STRATEGY_SELL",
                        "exec_date": next_date
                    })
                    continue

                # 止盈止损
                df = indicators_map.get(symbol)
                if df is None or trade_date not in df.index:
                    continue

                r = df.loc[trade_date]
                current_price = float(r['close'])
                ret = (current_price - pos["buy_price"]) / pos["buy_price"]
                hold_days = date_to_index[trade_date] - date_to_index[pos["buy_date"]]

                if ret >= take_profit:
                    pending_sell_orders.append({
                        "symbol": symbol, "exit_reason": "TAKE_PROFIT", "exec_date": next_date
                    })
                elif ret <= stop_loss:
                    pending_sell_orders.append({
                        "symbol": symbol, "exit_reason": "STOP_LOSS", "exec_date": next_date
                    })
                elif hold_days >= max_hold_days:
                    pending_sell_orders.append({
                        "symbol": symbol, "exit_reason": "MAX_HOLD_DAYS", "exec_date": next_date
                    })

            # 【修改点6】产生买入订单 - 动态权重分配（核心修改）
            candidates = []
            for symbol, info in daily_scores.get(trade_date, {}).items():
                if symbol in current_positions:
                    continue
                if info["signal"] == Signal.BUY and info["score"] >= score_threshold:
                    candidates.append((symbol, info["score"]))

            candidates.sort(key=lambda x: x[1], reverse=True)

            # 计算当前持仓数量和仓位
            current_position_count = len(current_positions)
            current_total_weight = sum(p["weight"] for p in current_positions.values())
            remaining_weight = 1.0 - current_total_weight

            # 计算最多还能买多少只（基于最大持仓数限制）
            max_new_count = max_total_positions - current_position_count
            if max_new_count <= 0:
                continue

            # 【修改点7】限制候选数量（只考虑最多2倍于最大新增数量的候选，避免过度计算）
            candidates_to_consider = candidates[:max_new_count * 2] if max_new_count > 0 else []

            if candidates_to_consider and remaining_weight > 0:
                # 方案A：等权重分配初始仓位（与实盘保持一致）
                # 计算每只股票的初始仓位
                weight_per_stock = min(
                    init_position_pct,
                    remaining_weight / len(candidates_to_consider[:max_new_count])
                )

                for symbol, score in candidates_to_consider[:max_new_count]:
                    if remaining_weight <= 0:
                        break

                    # 实际分配权重 = min(单只上限, 剩余可用, 等权重值)
                    actual_weight = min(weight_per_stock, remaining_weight, max_single_position_pct)

                    if actual_weight >= 0.01:  # 至少1%仓位
                        pending_buy_orders.append({
                            "symbol": symbol,
                            "score": score,
                            "weight": actual_weight,
                            "exec_date": next_date
                        })
                        remaining_weight -= actual_weight

            # 【修改点8】备选方案B：按评分加权分配（注释掉，可根据需要启用）
            """
            if candidates_to_consider and remaining_weight > 0:
                # 按评分比例分配，但每只不超过 init_position_pct
                total_score = sum(score for _, score in candidates_to_consider)

                for symbol, score in candidates_to_consider:
                    if remaining_weight <= 0:
                        break

                    # 计算理论分配权重
                    score_ratio = score / total_score
                    raw_weight = remaining_weight * score_ratio
                    actual_weight = min(raw_weight, init_position_pct, max_single_position_pct)

                    if actual_weight >= 0.01:
                        pending_buy_orders.append({
                            "symbol": symbol,
                            "score": score,
                            "weight": actual_weight,
                            "exec_date": next_date
                        })
                        remaining_weight -= actual_weight
            """

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

    @staticmethod
    def precompute_indicators(stock_data_map, min_history=60):
        """
        使用 pandas 向量化预计算所有技术指标
        返回: symbol -> DataFrame(date为索引，每行是一个交易日，包含所有指标)
        """
        indicators_map = {}

        for symbol, datas in stock_data_map.items():
            if len(datas) < min_history + 10:
                continue

            # 构建 DataFrame
            df = pd.DataFrame([{
                'date': d.date,
                'close': float(d.close),
                'high': float(d.high),
                'low': float(d.low),
                'volume': float(d.volume),
                'amount': float(d.amount) if hasattr(d, 'amount') and d.amount else 0,
                'pct_chg': float(d.pct_chg),
                'pe_ttm': float(d.pe_ttm) if d.pe_ttm and d.pe_ttm > 0 else 0,
                'pb_mrq': float(d.pb_mrq) if d.pb_mrq and d.pb_mrq > 0 else 0,
            } for d in datas])

            if len(df) < min_history:
                continue

            # ================================================
            # 提前按日期排序，保证 rolling / shift 正确
            # =================================================
            df = df.sort_values('date').reset_index(drop=True)

            # ========== 计算所有指标（向量化，一次完成） ==========

            # 均线
            df['ma5'] = df['close'].rolling(5).mean()
            df['ma20'] = df['close'].rolling(20).mean()
            df['ma60'] = df['close'].rolling(60).mean()

            # 20日最大回撤
            df['max_20'] = df['close'].rolling(20).max()
            df['min_20'] = df['close'].rolling(20).min()
            df['drawdown_20'] = (
                    (df['max_20'] - df['min_20']) /
                    (df['max_20'] + 1e-6)
            )

            # 成交额/量均线
            df['avg_amount_20'] = df['amount'].rolling(20).mean()
            df['avg_volume_20'] = df['volume'].rolling(20).mean()

            # 近期累计涨幅
            df['recent_10d_return'] = df['pct_chg'].rolling(10).sum()

            # 成交量比率
            df['vol_ratio'] = (
                    df['volume'] /
                    (df['avg_volume_20'] + 1e-6)
            )

            # ATR 和波动率
            df['prev_close'] = df['close'].shift(1)

            # ==================== 修改点2 ====================
            # 用真正向量化替代 apply(axis=1)
            # 性能会快很多
            # =================================================
            tr1 = df['high'] - df['low']
            tr2 = (df['high'] - df['prev_close']).abs()
            tr3 = (df['low'] - df['prev_close']).abs()

            df['tr'] = pd.concat(
                [tr1, tr2, tr3],
                axis=1
            ).max(axis=1)

            # 第一行 prev_close 是 NaN，手动置0
            df.loc[df['prev_close'].isna(), 'tr'] = 0

            df['atr'] = df['tr'].rolling(20).mean()

            df['volatility'] = (
                    df['atr'] /
                    (df['close'] + 1e-6)
            )

            # 单日和三日累计跌幅（用于卖出信号）
            df['pct_chg_3d_sum'] = df['pct_chg'].rolling(3).sum()

            # 清理临时列
            df = df.drop(
                ['max_20', 'min_20', 'prev_close', 'tr'],
                axis=1,
                errors='ignore'
            )

            # =================================================
            # 删除 NaN 后，不再 reset_index
            # 改为使用 date 作为索引
            # =================================================
            df = df.dropna()

            # =================================================
            # 使用 date 作为索引
            # 后续可直接 df.loc[date]
            # 查询复杂度从 O(n) -> O(1)
            # =================================================
            df = df.set_index('date')

            # 保证索引有序
            df = df.sort_index()

            indicators_map[symbol] = df

        return indicators_map

    @staticmethod
    def compute_market_width_sampled(indicators_map, all_dates, sample_size=500, compute_frequency=5):
        """
        计算市场宽度（抽样 + 低频计算）
        - sample_size: 每次抽样股票数量
        - compute_frequency: 每N天计算一次（其他天复用上次结果）
        """
        symbols = list(indicators_map.keys())
        if len(symbols) > sample_size:
            sampled_symbols = random.sample(symbols, sample_size)
        else:
            sampled_symbols = symbols

        market_width_by_date = {}
        last_width = 0.5
        last_compute_date = None

        for i, date in enumerate(all_dates):
            # 是否重新计算
            if last_compute_date is None or i % compute_frequency == 0:
                above_count = 0
                total_count = 0
                for symbol in sampled_symbols:
                    df = indicators_map.get(symbol)
                    if df is None:
                        continue
                    if date not in df.index:
                        continue

                    r = df.loc[date]
                    close = r['close']
                    ma60 = r['ma60']
                    if pd.notna(ma60) and close > ma60:
                        above_count += 1
                    total_count += 1

                last_width = above_count / max(total_count, 1) if total_count > 0 else 0.5
                last_compute_date = date

            market_width_by_date[date] = last_width

        return market_width_by_date
