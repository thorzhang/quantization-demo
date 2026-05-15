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
    稳健趋势策略 V4 - 低换手、趋势跟踪、评分分散（0-100分）
    目标：年化8-12%，最大回撤<10%
    """

    # 可配置参数
    MIN_HISTORY = 120
    MARKET_WIDTH_THRESHOLD = 0.5

    # 硬性筛选阈值
    MAX_DD_20D = 0.10
    MIN_PRICE = 5.0
    MIN_VOL_AMOUNT = 100_000_000
    MAX_PE = 30.0
    MAX_PB = 2.5

    # 评分权重（总和=1.0）
    WEIGHT_TREND = 0.35
    WEIGHT_VALUATION = 0.25
    WEIGHT_LOW_VOL = 0.20
    WEIGHT_VOLUME = 0.10
    WEIGHT_RECENT_RETURN = 0.10

    @staticmethod
    def reason() -> List[str]:
        return [
            "目标：年化收益8-12%，最大回撤<10%",
            "大盘过滤：市场宽度>50%才入场",
            "趋势确认：价格需在MA60上方",
            "买入信号：MA5>MA20>MA60 多头排列",
            "持仓管理：动态跟踪止损，趋势破坏才离场"
        ]

    def evaluate(self, indicators: dict) -> Dict:
        """
        接收预计算好的单行指标字典
        返回: {"signal": Signal, "score": float (0-100)}
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

        # ========== 强制卖出条件（宽松，减少噪音交易） ==========

        # 深度跌破MA60（-5%）才卖
        if current_price < ma60 * 0.95:
            return {"signal": Signal.SELL, "score": 0.0}

        # 20日最大回撤超过15%才卖
        if drawdown_20 > 0.15:
            return {"signal": Signal.SELL, "score": 0.0}

        # 单日暴跌超过9%才卖
        if pct_chg_day <= -0.09:
            return {"signal": Signal.SELL, "score": 0.0}

        # 三日累计跌幅超过12%才卖
        if pct_chg_3d_sum <= -0.12:
            return {"signal": Signal.SELL, "score": 0.0}

        # ========== 硬性筛选（买入前检查） ==========

        if current_price < self.MIN_PRICE:
            return {"signal": Signal.HOLD, "score": 0.0}

        if avg_amount_20 < self.MIN_VOL_AMOUNT:
            return {"signal": Signal.HOLD, "score": 0.0}

        # 价格必须在MA60上方（多头趋势基本要求）
        if current_price <= ma60:
            return {"signal": Signal.HOLD, "score": 0.0}

        # MA20必须高于MA60（中期趋势向上）
        if ma20 <= ma60:
            return {"signal": Signal.HOLD, "score": 0.0}

        # MA5必须高于MA20（短期趋势向上）
        if ma5 <= ma20:
            return {"signal": Signal.HOLD, "score": 0.0}

        if drawdown_20 > self.MAX_DD_20D:
            return {"signal": Signal.HOLD, "score": 0.0}

        # 估值过滤
        if pe > 0 and pe > self.MAX_PE:
            return {"signal": Signal.HOLD, "score": 0.0}
        if pb > 0 and pb > self.MAX_PB:
            return {"signal": Signal.HOLD, "score": 0.0}

        # 近期涨幅过滤（避免追高）
        if recent_10d_return > 15:
            return {"signal": Signal.HOLD, "score": 0.0}

        # 近期跌幅过大不买（不接飞刀）
        if recent_10d_return < -5:
            return {"signal": Signal.HOLD, "score": 0.0}

        # ========== 评分系统（每个子维度0-100分） ==========

        # ---------- 1. 趋势强度评分（权重35%）----------
        price_to_ma60 = (current_price / ma60 - 1) * 100
        ma20_to_ma60 = (ma20 / ma60 - 1) * 100
        ma5_to_ma20 = (ma5 / ma20 - 1) * 100

        # 价格位置评分（权重40%）
        if price_to_ma60 >= 15:
            price_score = 20
        elif price_to_ma60 >= 10:
            price_score = 40
        elif price_to_ma60 >= 5:
            price_score = 60
        elif price_to_ma60 >= 2:
            price_score = 80
        else:
            price_score = 100  # 刚突破趋势，潜力最大

        # MA20相对MA60位置评分（权重30%）
        if ma20_to_ma60 >= 8:
            ma20_score = 20
        elif ma20_to_ma60 >= 5:
            ma20_score = 40
        elif ma20_to_ma60 >= 3:
            ma20_score = 60
        elif ma20_to_ma60 >= 1:
            ma20_score = 80
        else:
            ma20_score = 100

        # MA5相对MA20位置评分（权重30%）
        if ma5_to_ma20 >= 3:
            ma5_score = 20
        elif ma5_to_ma20 >= 1.5:
            ma5_score = 40
        elif ma5_to_ma20 >= 0.5:
            ma5_score = 60
        elif ma5_to_ma20 >= 0:
            ma5_score = 80
        else:
            ma5_score = 100

        # 趋势综合评分（加权平均，0-100）
        trend_score = price_score * 0.40 + ma20_score * 0.30 + ma5_score * 0.30

        # ---------- 2. 估值优势评分（权重25%）----------
        if pe <= 0 or pb <= 0:
            valuation_score = 50  # 亏损股给中等分
        else:
            # PE评分
            if 8 <= pe <= 15:
                pe_score = 100
            elif 5 <= pe < 8 or 15 < pe <= 20:
                pe_score = 80
            elif 3 <= pe < 5 or 20 < pe <= 25:
                pe_score = 60
            elif 25 < pe <= 30:
                pe_score = 40
            elif pe > 30:
                pe_score = 20
            else:
                pe_score = 30

            # PB评分
            if pb <= 1.0:
                pb_score = 100
            elif pb <= 1.5:
                pb_score = 85
            elif pb <= 2.0:
                pb_score = 65
            elif pb <= 2.5:
                pb_score = 40
            else:
                pb_score = 20

            valuation_score = pe_score * 0.5 + pb_score * 0.5

        # ---------- 3. 低波动评分（权重20%）----------
        if volatility < 0.015:
            vol_score = 100
        elif volatility < 0.022:
            vol_score = 85
        elif volatility < 0.03:
            vol_score = 65
        elif volatility < 0.04:
            vol_score = 45
        elif volatility < 0.05:
            vol_score = 25
        else:
            vol_score = 10

        # ---------- 4. 成交量配合评分（权重10%）----------
        if 1.0 <= vol_ratio <= 1.5:
            volume_score = 100
        elif 0.8 <= vol_ratio < 1.0:
            volume_score = 80
        elif 1.5 < vol_ratio <= 2.0:
            volume_score = 70
        elif 2.0 < vol_ratio <= 2.5:
            volume_score = 50
        elif vol_ratio >= 2.5:
            volume_score = 30
        else:
            volume_score = 40

        # ---------- 5. 近期涨幅评分（权重10%）----------
        if 3 <= recent_10d_return <= 8:
            recent_score = 100
        elif 1 <= recent_10d_return < 3:
            recent_score = 80
        elif 8 < recent_10d_return <= 12:
            recent_score = 70
        elif 0 <= recent_10d_return < 1:
            recent_score = 60
        elif -3 <= recent_10d_return < 0:
            recent_score = 40
        elif -5 <= recent_10d_return < -3:
            recent_score = 20
        else:
            recent_score = 10

        # ========== 最终评分（加权平均，范围0-100） ==========
        total_score = (
                trend_score * self.WEIGHT_TREND +
                valuation_score * self.WEIGHT_VALUATION +
                vol_score * self.WEIGHT_LOW_VOL +
                volume_score * self.WEIGHT_VOLUME +
                recent_score * self.WEIGHT_RECENT_RETURN
        )

        final_score = round(total_score, 2)

        # ========== 分级信号 ==========
        if final_score >= 80:
            return {"signal": Signal.BUY, "score": final_score}
        elif final_score >= 70:
            # 中等评分，可买入但优先级低
            return {"signal": Signal.HOLD, "score": final_score}
        else:
            return {"signal": Signal.HOLD, "score": final_score}
