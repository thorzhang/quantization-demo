#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
@Time   : 2026/1/6   
@Author : zhanglei
@File   : app.py
"""
from typing import List, Dict

from app.core.enums.signal import Signal
from app.strategy.base import BaseStrategy


class RobustTrendStrategy(BaseStrategy):
    """
    稳健趋势策略 - 年化目标8%，最大回撤<10%
    """

    # 可配置参数
    MIN_HISTORY = 60
    MARKET_WIDTH_THRESHOLD = 0.5

    # 硬性筛选阈值
    MAX_DD_20D = 0.12
    MIN_PRICE = 3.0
    MIN_VOL_AMOUNT = 50_000_000
    MAX_PE = 40.0
    MAX_PB = 3.0

    # 评分权重
    WEIGHT_TREND = 0.30
    WEIGHT_LOW_VOL = 0.25
    WEIGHT_VALUATION = 0.20
    WEIGHT_VOLUME = 0.15
    WEIGHT_RECENT_RETURN = 0.10

    @staticmethod
    def reason() -> List[str]:
        return [
            "目标：年化收益8-12%，最大回撤<10%",
            "大盘过滤：市场宽度>50%才入场",
            "个股筛选：趋势向上+低波动+估值合理",
            "动态评分：每日按分数调整持仓",
            "风控：硬止损-7%，止盈15%，跌破MA60离场"
        ]

    def evaluate(self, indicators: dict) -> Dict:
        """
        新接口：接收预计算好的单行指标字典

        indicators 包含:
        - current_price, ma5, ma20, ma60
        - drawdown_20, avg_amount_20, avg_volume_20
        - recent_10d_return, volatility, vol_ratio
        - pe, pb, pct_chg_day, pct_chg_3d_sum
        """

        # 检查数据有效性
        if indicators.get('ma60', 0) == 0:
            return {"signal": Signal.HOLD, "score": 0.0}

        current_price = indicators['current_price']
        ma60 = indicators['ma60']
        ma20 = indicators['ma20']
        ma5 = indicators['ma5']
        drawdown_20 = indicators['drawdown_20']
        avg_amount_20 = indicators['avg_amount_20']
        recent_10d_return = indicators['recent_10d_return']
        volatility = indicators['volatility']
        vol_ratio = indicators['vol_ratio']
        pe = indicators.get('pe', 0)
        pb = indicators.get('pb', 0)
        pct_chg_day = indicators.get('pct_chg_day', 0)
        pct_chg_3d_sum = indicators.get('pct_chg_3d_sum', 0)

        # ========== 强制卖出条件 ==========
        if current_price < ma60:
            return {"signal": Signal.SELL, "score": 0.0}
        if drawdown_20 > 0.15:
            return {"signal": Signal.SELL, "score": 0.0}
        if pct_chg_day <= -0.08:
            return {"signal": Signal.SELL, "score": 0.0}
        if pct_chg_3d_sum <= -0.10:
            return {"signal": Signal.SELL, "score": 0.0}

        # ========== 硬性筛选 ==========
        if current_price < self.MIN_PRICE:
            return {"signal": Signal.HOLD, "score": 0.0}
        if avg_amount_20 < self.MIN_VOL_AMOUNT:
            return {"signal": Signal.HOLD, "score": 0.0}
        if current_price <= ma60:
            return {"signal": Signal.HOLD, "score": 0.0}
        if ma20 < ma60 * 0.95:
            return {"signal": Signal.HOLD, "score": 0.0}
        if drawdown_20 > self.MAX_DD_20D:
            return {"signal": Signal.HOLD, "score": 0.0}
        if pe > 0 and pe > self.MAX_PE:
            return {"signal": Signal.HOLD, "score": 0.0}
        if pb > 0 and pb > self.MAX_PB:
            return {"signal": Signal.HOLD, "score": 0.0}
        if recent_10d_return > 25:
            return {"signal": Signal.HOLD, "score": 0.0}

        # ========== 评分 ==========

        # 趋势强度
        trend_raw = (ma5 / ma20 - 1) * 100
        if 0.5 <= trend_raw <= 4:
            trend_score = 100
        elif 0.2 <= trend_raw < 0.5 or 4 < trend_raw <= 6:
            trend_score = 80
        elif 0 < trend_raw < 0.2:
            trend_score = 60
        elif trend_raw <= 0:
            trend_score = 30
        else:
            trend_score = 50

        # 低波动
        if volatility < 0.02:
            vol_score = 100
        elif volatility < 0.03:
            vol_score = 85
        elif volatility < 0.04:
            vol_score = 65
        elif volatility < 0.05:
            vol_score = 45
        else:
            vol_score = 25

        # 估值优势
        if pe <= 0 or pb <= 0:
            valuation_score = 50
        else:
            if 10 <= pe <= 20:
                pe_score = 100
            elif 8 <= pe < 10 or 20 < pe <= 25:
                pe_score = 80
            elif 5 <= pe < 8 or 25 < pe <= 30:
                pe_score = 60
            elif 30 < pe <= 40:
                pe_score = 40
            else:
                pe_score = 20

            if pb <= 1.5:
                pb_score = 100
            elif pb <= 2.0:
                pb_score = 80
            elif pb <= 2.5:
                pb_score = 60
            elif pb <= 3.0:
                pb_score = 40
            else:
                pb_score = 20

            valuation_score = min(pe_score, pb_score) * 0.7 + max(pe_score, pb_score) * 0.3

        # 成交量配合
        if 1.0 <= vol_ratio <= 1.8:
            volume_score = 100
        elif 0.8 <= vol_ratio < 1.0 or 1.8 < vol_ratio <= 2.5:
            volume_score = 75
        elif 0.6 <= vol_ratio < 0.8:
            volume_score = 55
        elif vol_ratio >= 2.5:
            volume_score = 40
        else:
            volume_score = 25

        # 近期涨幅
        if 3 <= recent_10d_return <= 8:
            recent_score = 100
        elif 1 <= recent_10d_return < 3 or 8 < recent_10d_return <= 12:
            recent_score = 80
        elif 0 <= recent_10d_return < 1:
            recent_score = 60
        elif -3 <= recent_10d_return < 0:
            recent_score = 40
        else:
            recent_score = 20

        total_score = (
                trend_score * self.WEIGHT_TREND +
                vol_score * self.WEIGHT_LOW_VOL +
                valuation_score * self.WEIGHT_VALUATION +
                volume_score * self.WEIGHT_VOLUME +
                recent_score * self.WEIGHT_RECENT_RETURN
        )

        final_score = round(total_score, 2)

        if final_score >= 50:
            return {"signal": Signal.BUY, "score": final_score}
        else:
            return {"signal": Signal.HOLD, "score": final_score}
