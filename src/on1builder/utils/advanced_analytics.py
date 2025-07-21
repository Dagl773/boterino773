# src/on1builder/utils/advanced_analytics.py
from __future__ import annotations

import asyncio
import json
import numpy as np
from decimal import Decimal
from typing import Any, Dict, List, Optional, Tuple
from datetime import datetime, timedelta
from dataclasses import dataclass
from enum import Enum
import logging

from on1builder.config.loaders import settings
from on1builder.utils.logging_config import get_logger

logger = get_logger(__name__)

class OpportunityType(Enum):
    ARBITRAGE = "arbitrage"
    FRONT_RUN = "front_run"
    BACK_RUN = "back_run"
    SANDWICH = "sandwich"
    FLASHLOAN_ARBITRAGE = "flashloan_arbitrage"
    LIQUIDATION = "liquidation"

class RiskLevel(Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    EXTREME = "extreme"

@dataclass
class OpportunityScore:
    """Comprehensive opportunity scoring with multiple factors."""
    total_score: float
    profit_potential: float
    risk_score: float
    execution_probability: float
    market_conditions: float
    gas_efficiency: float
    competition_level: float
    confidence_interval: Tuple[float, float]

class AdvancedAnalytics:
    """
    Advanced analytics engine for opportunity scoring, risk assessment,
    and market analysis with machine learning insights.
    """
    
    def __init__(self):
        self._historical_opportunities: List[Dict[str, Any]] = []
        self._market_regime_classifier = None
        self._volatility_regime = "normal"
        self._correlation_matrix: Dict[str, Dict[str, float]] = {}
        self._liquidity_profiles: Dict[str, Dict[str, float]] = {}
        self._competition_analysis: Dict[str, Dict[str, Any]] = {}
        
        # Performance tracking
        self._success_rates: Dict[str, float] = {}
        self._avg_profits: Dict[str, float] = {}
        self._risk_adjusted_returns: Dict[str, float] = {}
        
        logger.info("AdvancedAnalytics initialized with ML capabilities.")

    async def score_opportunity(self, opportunity: Dict[str, Any]) -> OpportunityScore:
        """
        Comprehensive opportunity scoring with multiple factors.
        Returns a detailed score breakdown.
        """
        try:
            # Extract opportunity details
            opportunity_type = opportunity.get("type", "arbitrage")
            expected_profit = float(opportunity.get("expected_profit_eth", 0))
            amount_in = float(opportunity.get("amount_in", 0))
            gas_estimate = float(opportunity.get("gas_estimate_eth", 0))
            
            # Calculate individual scores
            profit_score = self._calculate_profit_score(expected_profit, amount_in, gas_estimate)
            risk_score = await self._calculate_risk_score(opportunity)
            execution_score = await self._calculate_execution_probability(opportunity)
            market_score = await self._calculate_market_conditions_score(opportunity)
            gas_score = self._calculate_gas_efficiency_score(expected_profit, gas_estimate)
            competition_score = await self._calculate_competition_score(opportunity)
            
            # Weighted combination
            weights = self._get_opportunity_weights(opportunity_type)
            total_score = (
                profit_score * weights["profit"] +
                risk_score * weights["risk"] +
                execution_score * weights["execution"] +
                market_score * weights["market"] +
                gas_score * weights["gas"] +
                competition_score * weights["competition"]
            )
            
            # Calculate confidence interval
            confidence_interval = self._calculate_confidence_interval(
                opportunity, total_score
            )
            
            return OpportunityScore(
                total_score=total_score,
                profit_potential=profit_score,
                risk_score=risk_score,
                execution_probability=execution_score,
                market_conditions=market_score,
                gas_efficiency=gas_score,
                competition_level=competition_score,
                confidence_interval=confidence_interval
            )
            
        except Exception as e:
            logger.error(f"Error scoring opportunity: {e}")
            return OpportunityScore(
                total_score=0.0,
                profit_potential=0.0,
                risk_score=1.0,  # High risk if scoring fails
                execution_probability=0.0,
                market_conditions=0.0,
                gas_efficiency=0.0,
                competition_level=1.0,
                confidence_interval=(0.0, 0.0)
            )

    def _calculate_profit_score(self, expected_profit: float, amount_in: float, gas_estimate: float) -> float:
        """Calculate profit potential score (0-1)."""
        if expected_profit <= 0 or amount_in <= 0:
            return 0.0
        
        # Net profit after gas costs
        net_profit = expected_profit - gas_estimate
        if net_profit <= 0:
            return 0.0
        
        # ROI percentage
        roi = net_profit / amount_in
        
        # Score based on ROI with diminishing returns
        if roi < 0.001:  # Less than 0.1%
            return 0.1
        elif roi < 0.01:  # Less than 1%
            return 0.3
        elif roi < 0.05:  # Less than 5%
            return 0.6
        elif roi < 0.1:   # Less than 10%
            return 0.8
        else:
            return min(1.0, 0.8 + (roi - 0.1) * 2)  # Cap at 1.0

    async def _calculate_risk_score(self, opportunity: Dict[str, Any]) -> float:
        """Calculate risk score (0-1, where 0 is no risk)."""
        risk_factors = []
        
        # Market volatility risk
        tokens = opportunity.get("tokens", [])
        for token in tokens:
            volatility = await self._get_token_volatility(token)
            if volatility and volatility > 0.1:  # High volatility
                risk_factors.append(0.3)
        
        # Liquidity risk
        liquidity_score = await self._assess_liquidity_risk(opportunity)
        risk_factors.append(liquidity_score)
        
        # Slippage risk
        slippage = opportunity.get("slippage_estimate", 0.01)
        if slippage > 0.05:  # High slippage
            risk_factors.append(0.4)
        
        # Competition risk
        competition_level = await self._get_competition_level(opportunity)
        risk_factors.append(competition_level * 0.3)
        
        # Strategy-specific risks
        strategy_risk = self._get_strategy_risk(opportunity.get("type", "arbitrage"))
        risk_factors.append(strategy_risk)
        
        return min(1.0, sum(risk_factors))

    async def _calculate_execution_probability(self, opportunity: Dict[str, Any]) -> float:
        """Calculate probability of successful execution (0-1)."""
        factors = []
        
        # Historical success rate for this type
        strategy_type = opportunity.get("type", "arbitrage")
        success_rate = self._success_rates.get(strategy_type, 0.5)
        factors.append(success_rate)
        
        # Market conditions
        market_conditions = await self._get_market_conditions()
        factors.append(market_conditions)
        
        # Gas price stability
        gas_stability = await self._assess_gas_stability()
        factors.append(gas_stability)
        
        # Liquidity availability
        liquidity_availability = await self._assess_liquidity_availability(opportunity)
        factors.append(liquidity_availability)
        
        return np.mean(factors)

    async def _calculate_market_conditions_score(self, opportunity: Dict[str, Any]) -> float:
        """Calculate market conditions score (0-1)."""
        # Market regime analysis
        regime_score = self._get_market_regime_score()
        
        # Volatility analysis
        volatility_score = await self._get_volatility_score(opportunity)
        
        # Trend analysis
        trend_score = await self._get_trend_score(opportunity)
        
        # Sentiment analysis
        sentiment_score = await self._get_sentiment_score(opportunity)
        
        return np.mean([regime_score, volatility_score, trend_score, sentiment_score])

    def _calculate_gas_efficiency_score(self, expected_profit: float, gas_estimate: float) -> float:
        """Calculate gas efficiency score (0-1)."""
        if expected_profit <= 0 or gas_estimate <= 0:
            return 0.0
        
        gas_ratio = gas_estimate / expected_profit
        
        if gas_ratio < 0.05:  # Gas is less than 5% of profit
            return 1.0
        elif gas_ratio < 0.1:  # Gas is less than 10% of profit
            return 0.8
        elif gas_ratio < 0.2:  # Gas is less than 20% of profit
            return 0.6
        elif gas_ratio < 0.5:  # Gas is less than 50% of profit
            return 0.3
        else:
            return 0.0

    async def _calculate_competition_score(self, opportunity: Dict[str, Any]) -> float:
        """Calculate competition level score (0-1, where 0 is no competition)."""
        # Analyze mempool for similar transactions
        similar_txs = await self._find_similar_transactions(opportunity)
        
        # Analyze historical competition patterns
        historical_competition = self._get_historical_competition(opportunity)
        
        # Analyze gas price competition
        gas_competition = await self._assess_gas_competition()
        
        competition_level = np.mean([
            min(1.0, len(similar_txs) * 0.2),  # Each similar tx adds 20% competition
            historical_competition,
            gas_competition
        ])
        
        return competition_level

    def _get_opportunity_weights(self, opportunity_type: str) -> Dict[str, float]:
        """Get scoring weights based on opportunity type."""
        base_weights = {
            "profit": 0.3,
            "risk": 0.2,
            "execution": 0.2,
            "market": 0.15,
            "gas": 0.1,
            "competition": 0.05
        }
        
        # Adjust weights based on strategy type
        if opportunity_type == "flashloan_arbitrage":
            base_weights["profit"] = 0.4  # Higher profit weight for flashloans
            base_weights["risk"] = 0.15   # Lower risk weight (flashloans are safer)
        elif opportunity_type == "sandwich":
            base_weights["risk"] = 0.3    # Higher risk weight for sandwiches
            base_weights["competition"] = 0.15  # Higher competition weight
        elif opportunity_type == "arbitrage":
            base_weights["execution"] = 0.25  # Higher execution weight for simple arbitrage
        
        return base_weights

    def _calculate_confidence_interval(self, opportunity: Dict[str, Any], base_score: float) -> Tuple[float, float]:
        """Calculate confidence interval for the score."""
        # Base uncertainty
        uncertainty = 0.1
        
        # Add uncertainty based on data quality
        if not opportunity.get("price_data_quality", True):
            uncertainty += 0.1
        
        if not opportunity.get("liquidity_data_quality", True):
            uncertainty += 0.1
        
        # Add uncertainty based on market conditions
        if self._volatility_regime == "high":
            uncertainty += 0.15
        
        # Calculate confidence interval
        lower_bound = max(0.0, base_score - uncertainty)
        upper_bound = min(1.0, base_score + uncertainty)
        
        return (lower_bound, upper_bound)

    async def _get_token_volatility(self, token: str) -> Optional[float]:
        """Get token volatility (placeholder for market data integration)."""
        # This would integrate with your market data feed
        return 0.05  # Placeholder

    async def _assess_liquidity_risk(self, opportunity: Dict[str, Any]) -> float:
        """Assess liquidity risk (0-1)."""
        # This would analyze liquidity depth and spread
        return 0.2  # Placeholder

    def _get_strategy_risk(self, strategy_type: str) -> float:
        """Get base risk for strategy type."""
        risk_map = {
            "arbitrage": 0.1,
            "front_run": 0.3,
            "back_run": 0.2,
            "sandwich": 0.5,
            "flashloan_arbitrage": 0.15,
            "liquidation": 0.25
        }
        return risk_map.get(strategy_type, 0.3)

    async def _get_market_conditions(self) -> float:
        """Get current market conditions score (0-1)."""
        # This would analyze overall market health
        return 0.7  # Placeholder

    async def _assess_gas_stability(self) -> float:
        """Assess gas price stability (0-1)."""
        # This would analyze recent gas price volatility
        return 0.8  # Placeholder

    async def _assess_liquidity_availability(self, opportunity: Dict[str, Any]) -> float:
        """Assess liquidity availability (0-1)."""
        # This would check if sufficient liquidity exists
        return 0.9  # Placeholder

    def _get_market_regime_score(self) -> float:
        """Get market regime score (0-1)."""
        # This would classify current market regime
        return 0.6  # Placeholder

    async def _get_volatility_score(self, opportunity: Dict[str, Any]) -> float:
        """Get volatility score (0-1)."""
        # This would analyze relevant volatility metrics
        return 0.7  # Placeholder

    async def _get_trend_score(self, opportunity: Dict[str, Any]) -> float:
        """Get trend score (0-1)."""
        # This would analyze price trends
        return 0.6  # Placeholder

    async def _get_sentiment_score(self, opportunity: Dict[str, Any]) -> float:
        """Get sentiment score (0-1)."""
        # This would analyze market sentiment
        return 0.5  # Placeholder

    async def _find_similar_transactions(self, opportunity: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Find similar transactions in mempool (placeholder)."""
        # This would analyze mempool for similar opportunities
        return []  # Placeholder

    def _get_historical_competition(self, opportunity: Dict[str, Any]) -> float:
        """Get historical competition level (0-1)."""
        # This would analyze historical competition patterns
        return 0.3  # Placeholder

    async def _assess_gas_competition(self) -> float:
        """Assess gas price competition (0-1)."""
        # This would analyze gas price competition
        return 0.4  # Placeholder

    async def update_performance_metrics(self, strategy_type: str, success: bool, profit: float):
        """Update performance metrics for strategy types."""
        if strategy_type not in self._success_rates:
            self._success_rates[strategy_type] = 0.0
            self._avg_profits[strategy_type] = 0.0
            self._risk_adjusted_returns[strategy_type] = 0.0
        
        # Update success rate (simple moving average)
        current_rate = self._success_rates[strategy_type]
        self._success_rates[strategy_type] = current_rate * 0.9 + (1.0 if success else 0.0) * 0.1
        
        # Update average profit
        current_avg = self._avg_profits[strategy_type]
        self._avg_profits[strategy_type] = current_avg * 0.9 + profit * 0.1

    def get_analytics_summary(self) -> Dict[str, Any]:
        """Get comprehensive analytics summary."""
        return {
            "success_rates": self._success_rates,
            "average_profits": self._avg_profits,
            "risk_adjusted_returns": self._risk_adjusted_returns,
            "volatility_regime": self._volatility_regime,
            "total_opportunities_analyzed": len(self._historical_opportunities)
        } 

class StrategySelector:
    """
    Dynamic strategy selector based on market conditions.
    """
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        
        # Strategy thresholds
        self.gas_threshold_high = 100  # gwei
        self.gas_threshold_medium = 60  # gwei
        self.volatility_threshold = 10.0  # percentage
        self.mempool_volume_high = 1000  # transactions per minute
        
    def select_strategy(
        self, 
        mempool_tx_rate: float, 
        gas_price_gwei: float, 
        token_price_volatility: float
    ) -> str:
        """
        Select optimal trading strategy based on market conditions.
        
        Args:
            mempool_tx_rate: Transactions per minute in mempool
            gas_price_gwei: Current gas price in gwei
            token_price_volatility: Token price volatility percentage
            
        Returns:
            Strategy: "simple", "multi_hop", or "skip"
        """
        try:
            # Check if conditions are too risky
            if gas_price_gwei >= self.gas_threshold_high or token_price_volatility >= self.volatility_threshold:
                self.logger.info(f"Market conditions too risky - Gas: {gas_price_gwei}gwei, Volatility: {token_price_volatility}%")
                return "skip"
            
            # Check if conditions favor multi-hop strategies
            if (mempool_tx_rate >= self.mempool_volume_high and 
                gas_price_gwei < self.gas_threshold_medium):
                self.logger.info(f"High mempool volume ({mempool_tx_rate} tx/min) with low gas ({gas_price_gwei}gwei) - using multi_hop")
                return "multi_hop"
            
            # Default to simple strategy
            self.logger.info(f"Using simple strategy - Gas: {gas_price_gwei}gwei, Volatility: {token_price_volatility}%")
            return "simple"
            
        except Exception as e:
            self.logger.error(f"Error selecting strategy: {e}")
            return "skip"  # Default to skip on error
    
    def get_strategy_confidence(self, strategy: str, market_conditions: dict) -> float:
        """
        Calculate confidence score for selected strategy.
        
        Args:
            strategy: Selected strategy
            market_conditions: Current market conditions
            
        Returns:
            Confidence score (0.0 to 1.0)
        """
        try:
            if strategy == "skip":
                return 0.0
            # If no market conditions, return base confidence
            if not market_conditions:
                return 0.5
            # Base confidence
            confidence = 0.5
            
            # Adjust based on gas price
            gas_price = market_conditions.get('gas_price_gwei', 0)
            if gas_price < 30:
                confidence += 0.2
            elif gas_price > 80:
                confidence -= 0.2
            
            # Adjust based on volatility
            volatility = market_conditions.get('token_price_volatility', 0)
            if volatility < 5.0:
                confidence += 0.2
            elif volatility > 15.0:
                confidence -= 0.2
            
            # Adjust based on mempool volume
            mempool_volume = market_conditions.get('mempool_tx_rate', 0)
            if mempool_volume > 500:
                confidence += 0.1
            
            return max(0.0, min(1.0, confidence))
            
        except Exception as e:
            self.logger.error(f"Error calculating strategy confidence: {e}")
            return 0.0 