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

    def evaluate(self, data: List[dict]) -> Dict:
        if len(data) < 20:
            return {
                "signal": Signal.HOLD,
                "score": 0.0
            }

        closes = [float(d["close"]) for d in data]
        volumes = [float(d["volume"]) for d in data]

        ma5 = sum(closes[-5:]) / 5
        ma20 = sum(closes[-20:]) / 20

        prev_ma5 = sum(closes[-6:-1]) / 5
        prev_ma20 = sum(closes[-21:-1]) / 20

        vol_now = volumes[-1]
        vol_avg5 = sum(volumes[-5:]) / 5

        pct_chg = float(data[-1]["pct_chg"])

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
