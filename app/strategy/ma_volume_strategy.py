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


class MAVolumeStrategy(BaseStrategy):
    @staticmethod
    def reason() -> List[str]:
        return [
            "使用MA5与MA20均线判断股票中短期趋势方向",
            "MA5上穿MA20时判定为金叉，生成BUY信号",
            "MA5下穿MA20时判定为死叉，生成SELL信号",
            "当前MA5高于MA20，说明短期走势强于中期趋势",
            "当前MA5低于MA20，说明短期走势弱于中期趋势",
            "通过昨日均线与今日均线对比，识别趋势是否发生拐点",
            "使用最近1日涨跌幅(pct_chg)衡量短期价格动量",
            "当日涨幅越高，动量评分越高",
            "比较当前成交量与5日平均成交量，判断是否出现放量",
            "当前成交量高于5日平均成交量，说明市场活跃度提升",
            "成交量明显放大时，资金参与度较强",
            "趋势因子占总评分50%，策略偏向趋势跟随",
            "动量因子占总评分30%，策略偏向短期强势股票",
            "成交量因子占总评分20%，用于确认上涨有效性",
            "综合趋势、动量与成交量生成最终score评分",
            "最终按照score从高到低排序，优先推荐强势股票"
        ]

    def evaluate(self, datas: List[dict]) -> Dict:
        if len(datas) < 20:
            return {
                "signal": Signal.HOLD,
                "score": 0.0
            }

        closes = [float(d["close"]) for d in datas]
        volumes = [float(d["volume"]) for d in datas]

        ma5 = sum(closes[-5:]) / 5
        ma20 = sum(closes[-20:]) / 20

        prev_ma5 = sum(closes[-6:-1]) / 5
        prev_ma20 = sum(closes[-21:-1]) / 20

        vol_now = volumes[-1]
        vol_avg5 = sum(volumes[-5:]) / 5

        pct_chg = float(datas[-1]["pct_chg"])

        if prev_ma5 <= prev_ma20 and ma5 > ma20:
            signal = Signal.BUY
        elif prev_ma5 >= prev_ma20 and ma5 < ma20:
            signal = Signal.SELL
        else:
            signal = Signal.HOLD

        trend_score = (ma5 - ma20) / (ma20 + 1e-6)
        momentum_score = pct_chg / 100
        volume_score = (vol_now - vol_avg5) / (vol_avg5 + 1e-6)

        score = trend_score * 0.5 + momentum_score * 0.3 + volume_score * 0.2

        return {
            "signal": signal,
            "score": float(score)
        }
