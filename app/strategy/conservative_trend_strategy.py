#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
@Time   : 2026/1/6   
@Author : zhanglei
@File   : app.py
"""
from statistics import pstdev
from typing import Dict, List

from app.core.enums.signal import Signal
from app.strategy.base import BaseStrategy


class ConservativeValueTrendStrategy(BaseStrategy):

    @staticmethod
    def reason() -> List[str]:
        return [
            "MA5高于MA20且连续保持3天以上，确认中短期上升趋势",
            "最近10日累计涨幅不超过15%，未出现明显追高风险",
            "最近10日波动率不超过8%，避免异常波动股票",
            "最近20日最大回撤不超过12%，下跌风险可控",
            "最近5日平均换手率不低于0.5%，流动性正常",
            "当前成交量不低于5日均量的70%，市场关注度正常",
            "PE(TTM)大于0且小于60，排除亏损及明显高估股票",
            "PB(MRQ)小于8，市净率未明显偏高",
            "趋势权重45%，确保策略核心为趋势跟踪",
            "整体趋势、风控、估值条件符合稳健型趋势策略要求"
        ]

    def evaluate(self, datas: List[dict]) -> Dict:

        if len(datas) < 23:
            return {
                "signal": Signal.HOLD,
                "score": 0.0
            }

        closes = [float(d["close"]) for d in datas]
        volumes = [float(d["volume"]) for d in datas]
        pct_chgs = [float(d["pct_chg"]) for d in datas]

        turnovers = [
            float(d.get("turnover") or 0)
            for d in datas
        ]

        pe_list = [
            float(d.get("pe_ttm") or 0)
            for d in datas
            if d.get("pe_ttm")
        ]

        pb_list = [
            float(d.get("pb_mrq") or 0)
            for d in datas
            if d.get("pb_mrq")
        ]

        # =========================
        # 计算各项指标
        # =========================

        ma5 = sum(closes[-5:]) / 5
        ma20 = sum(closes[-20:]) / 20

        # 简化版：检查最近3天（包含今天）是否连续 MA5 > MA20
        consecutive_days = 0
        for i in range(-2, 0):  # -2, -1, 0 共3天（大前天、昨天、今天）
            # 计算当天的 MA5 和 MA20
            day_ma5 = sum(closes[i - 5:i]) / 5 if i - 5 >= -len(closes) else None
            day_ma20 = sum(closes[i - 20:i]) / 20 if i - 20 >= -len(closes) else None

            if day_ma5 and day_ma20 and day_ma5 > day_ma20:
                consecutive_days += 1
            else:
                consecutive_days = 0

        # 趋势破坏条件：今天不在多头 或 最近2天有任意一天不满足
        trend_broken = ma5 <= ma20 or consecutive_days < 2

        # 趋势强度评分
        trend_strength = (ma5 - ma20) / (ma20 + 1e-6)
        trend_score = min(max(trend_strength * 15, 0.3), 1)

        # 10日涨幅
        recent_10d_return = sum(pct_chgs[-10:])

        # 波动率
        volatility = pstdev(pct_chgs[-10:]) if len(pct_chgs) >= 10 else 0

        # 20日最大回撤
        max_price = max(closes[-20:])
        min_price = min(closes[-20:])
        max_drawdown = (max_price - min_price) / (max_price + 1e-6)

        # 换手率
        avg_turnover = sum(turnovers[-5:]) / 5 if turnovers[-5:] else 0

        # 成交量比例
        vol_now = volumes[-1]
        vol_avg5 = sum(volumes[-5:]) / 5
        volume_ratio = vol_now / (vol_avg5 + 1e-6)

        # PE
        pe_valid = pe_list and pe_list[-1] > 0
        pe = pe_list[-1] if pe_valid else 0

        # PB
        pb_valid = pb_list and pb_list[-1] > 0
        pb = pb_list[-1] if pb_valid else 0

        # =========================
        # 卖出条件检测（SELL）
        # =========================

        sell_reasons = []

        if trend_broken:
            sell_reasons.append("trend_broken")

        if recent_10d_return > 20:
            sell_reasons.append("overbought")

        if volatility > 10:
            sell_reasons.append("high_volatility")

        if max_drawdown > 0.15:
            sell_reasons.append("large_drawdown")

        if 0 < avg_turnover < 0.3:
            sell_reasons.append("low_liquidity")

        if volume_ratio < 0.5:
            sell_reasons.append("volume_shrink")

        if pe <= 0 or pe >= 80:
            sell_reasons.append("pe_deteriorated")

        if pb >= 10:
            sell_reasons.append("pb_too_high")

        if sell_reasons:
            return {
                "signal": Signal.SELL,
                "score": 0.0
            }

        # =========================
        # 买入条件检测（BUY）
        # =========================

        buy_reasons = []

        if not trend_broken:
            buy_reasons.append("trend_up")

        if recent_10d_return <= 15:
            buy_reasons.append("moderate_return")

        if volatility <= 8:
            buy_reasons.append("normal_volatility")

        if max_drawdown <= 0.12:
            buy_reasons.append("drawdown_controlled")

        if avg_turnover >= 0.5:
            buy_reasons.append("normal_turnover")

        if volume_ratio >= 0.7:
            buy_reasons.append("normal_volume")

        if 0 < pe < 60:
            buy_reasons.append("pe_normal")

        if pb < 8:
            buy_reasons.append("pb_normal")

        # 必须满足所有8个买入条件
        if len(buy_reasons) < 8:
            return {
                "signal": Signal.HOLD,
                "score": 0.0
            }

        # =========================
        # 综合评分
        # =========================

        if pe < 15:
            pe_score = 1.0
        elif pe < 30:
            pe_score = 0.8
        elif pe < 45:
            pe_score = 0.5
        else:
            pe_score = 0.3

        if pb < 2:
            pb_score = 1.0
        elif pb < 4:
            pb_score = 0.8
        else:
            pb_score = 0.5

        total_score = (
                trend_score * 0.45
                + pe_score * 0.15
                + pb_score * 0.15
                + 1.0 * 0.10
                + 1.0 * 0.05
                + 1.0 * 0.05
                + 1.0 * 0.03
                + 1.0 * 0.02
        )

        final_score = total_score * 100

        return {
            "signal": Signal.BUY,
            "score": round(final_score, 2)
        }
