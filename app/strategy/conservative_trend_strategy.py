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
            "MA5高于MA20，股票处于中短期上升趋势",
            "最近10日累计涨幅不超过15%，未出现明显追高风险",
            "最近10日涨跌幅标准差较低，股价波动相对稳定",
            "最近20日最大回撤不超过15%，下跌风险可控",
            "最近5日平均换手率介于1%~15%之间，流动性正常且未出现明显游资炒作",
            "当前成交量未明显低于5日平均成交量，市场关注度正常",
            "PE(TTM)小于60，估值未明显高估",
            "PE(TTM)处于较低区间，具备一定估值安全性",
            "PB(MRQ)小于8，市净率未明显偏高",
            "PB(MRQ)处于较低区间，资产估值相对合理",
            "MA5相对MA20保持温和上行，趋势较稳定",
            "股价近期未出现暴涨，符合稳健型趋势特征",
            "成交量保持温和放量，资金参与度较健康",
            "整体趋势、估值、波动率与回撤指标均符合稳健低风险策略要求"
        ]

    def evaluate(self, datas: List[dict]) -> Dict:

        if len(datas) < 20:
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
        # 1. MA趋势
        # =========================

        ma5 = sum(closes[-5:]) / 5
        ma20 = sum(closes[-20:]) / 20

        trend_strength = (ma5 - ma20) / (ma20 + 1e-6)

        if ma5 <= ma20:
            return {
                "signal": Signal.HOLD,
                "score": 0.0
            }

        # 趋势评分（0~1）
        trend_score = min(max(trend_strength * 20, 0), 1)

        # =========================
        # 2. 10日涨幅
        # =========================

        recent_10d_return = sum(pct_chgs[-10:])

        # 超过15%开始扣分
        pullback_score = max(
            0.0,
            1 - recent_10d_return / 15
        )

        # =========================
        # 3. 波动率
        # =========================

        volatility = pstdev(pct_chgs[-10:])

        # 波动越低越好
        volatility_score = max(
            0.0,
            1 - volatility / 5
        )

        # =========================
        # 4. 最大回撤
        # =========================

        recent_high = max(closes[-20:])
        current_price = closes[-1]

        max_drawdown = (
                (recent_high - current_price)
                / (recent_high + 1e-6)
        )

        # 回撤越小越好
        drawdown_score = max(
            0.0,
            1 - max_drawdown / 0.15
        )

        # =========================
        # 5. 换手率
        # =========================

        avg_turnover = sum(turnovers[-5:]) / 5

        if avg_turnover < 1:
            turnover_score = 0.2
        elif avg_turnover <= 8:
            turnover_score = 1.0
        elif avg_turnover <= 15:
            turnover_score = 0.6
        else:
            turnover_score = 0.1

        # =========================
        # 6. 成交量
        # =========================

        vol_now = volumes[-1]
        vol_avg5 = sum(volumes[-5:]) / 5

        volume_ratio = vol_now / (vol_avg5 + 1e-6)

        # 温和放量最佳
        if volume_ratio < 0.8:
            volume_score = 0.2
        elif volume_ratio <= 1.5:
            volume_score = 1.0
        elif volume_ratio <= 2:
            volume_score = 0.7
        else:
            volume_score = 0.3

        # =========================
        # 7. PE估值
        # =========================

        pe_score = 0.5

        if pe_list:
            pe = pe_list[-1]

            if pe <= 0:
                pe_score = 0.3
            elif pe < 25:
                pe_score = 1.0
            elif pe < 40:
                pe_score = 0.7
            elif pe < 60:
                pe_score = 0.4
            else:
                pe_score = 0.1

        # =========================
        # 8. PB估值
        # =========================

        pb_score = 0.5

        if pb_list:
            pb = pb_list[-1]

            if pb < 2:
                pb_score = 1.0
            elif pb < 4:
                pb_score = 0.7
            elif pb < 8:
                pb_score = 0.4
            else:
                pb_score = 0.1

        # =========================
        # 9. 综合评分
        # =========================

        total_score = (
                trend_score * 0.25
                + volatility_score * 0.20
                + drawdown_score * 0.20
                + pe_score * 0.10
                + pb_score * 0.10
                + turnover_score * 0.05
                + volume_score * 0.05
                + pullback_score * 0.05
        )

        final_score = total_score * 100

        return {
            "signal": Signal.BUY,
            "score": round(final_score, 2)
        }
