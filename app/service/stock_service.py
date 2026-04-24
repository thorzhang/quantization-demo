#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
@Time   : 2026/1/6   
@Author : zhanglei
@File   : app.py
"""
import logging
from typing import List
from uuid import UUID

import akshare as ak

from app.core.enums.task_enum import FetchTaskStatus
from app.integration.datasource.baostock import BaostockSource
from app.integration.datasource.eastmoney import EastMoneySource
from app.integration.datasource.tencent import TencentSource
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
            TencentSource(),
            EastMoneySource()
        ]

    # 初始化股票列表
    def init_stock_list(self):
        df = ak.stock_info_a_code_name()

        df = df[~df["name"].str.contains("ST")]

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

    def create_fetch_task(self, resume: bool) -> FetchTaskResponse:
        exist_fetch_tasks = self.fetch_task_repo.get_by_status(FetchTaskStatus.RUNNING)
        if len(exist_fetch_tasks) >= 1:
            fetch_task = exist_fetch_tasks[0]
        else:
            fetch_task = FetchTask(**FetchTaskCreateRequest().model_dump(mode="json"))
            self.fetch_task_repo.create(fetch_task)

        fetch_all_stocks.delay(fetch_task.id, resume)
        logger.info("拉取股票任务开始了")
        return FetchTaskResponse.model_validate(fetch_task)

    def update_fetch_task_by_id(self, task_id: UUID, **kwargs) -> None:
        self.fetch_task_repo.update_by_id(task_id, **kwargs)

    def create_fetch_progress(self, fetch_progress_req: FetchProgressCreateRequest) -> FetchProgressResponse:
        fetch_process = FetchProgress(**fetch_progress_req.model_dump(mode="json"))
        self.fetch_process_repo.create(fetch_process)
        return FetchProgressResponse.model_validate(fetch_process)

    def update_fetch_progress_by_id(self, progress_id: UUID, **kwargs) -> None:
        self.fetch_process_repo.update_by_id(progress_id, **kwargs)

    def fetch_one_history(self, symbol: str) -> List[RemoteStockDailyResponse] | None:
        """抓取单只股票（同步，独立事务）"""
        # 使用你的数据源
        last_error = None
        for source in self.sources:
            try:
                data = source.fetch_one_history(symbol)
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

        completed_symbols = [c[0] for c in completed]
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
