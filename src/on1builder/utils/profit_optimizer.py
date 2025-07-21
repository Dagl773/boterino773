# src/on1builder/utils/profit_optimizer.py
from __future__ import annotations

import asyncio
import time
from decimal import Decimal
from typing import Any, Dict, List, Optional, Tuple
from dataclasses import dataclass

from web3 import AsyncWeb3
from web3.types import TxParams

from on1builder.config.loaders import settings
from on1builder.utils.logging_config import get_logger
from on1builder.utils.custom_exceptions import InsufficientProfitError

logger = get_logger(__name__)

@dataclass
class ProfitAnalysis:
    """Comprehensive profit analysis for a transaction."""
    gross_profit_eth: float
    gas_cost_eth: float
    net_profit_eth: float
    roi_percentage: float
    profitable: bool
    confidence_score: float
    risk_level: str
    recommended_gas_price_gwei: int
    simulation_success: bool
    execution_probability: float

class ProfitOptimizer:
    """
    Advanced profit optimization with simulation, gas optimization, and profitability analysis.
    Ensures transactions are profitable after all costs.
    """
    
    def __init__(self, web3: AsyncWeb3):
        self._web3 = web3
        self._min_roi_percentage = 5.0  # Minimum 5% ROI
        self._min_profit_eth = settings.min_profit_eth
        self._max_gas_fee_percentage = settings.max_gas_fee_percentage
        
        # Performance tracking
        self._optimization_stats = {
            "total_analyses": 0,
            "profitable_opportunities": 0,
            "executed_opportunities": 0,
            "total_profit_eth": 0.0,
            "total_gas_spent_eth": 0.0,
            "avg_roi_percentage": 0.0
        }
        
        # Gas price history for optimization
        self._gas_price_history: List[Tuple[int, float]] = []
        self._max_history_size = 1000
        
        logger.info("ProfitOptimizer initialized")

    async def analyze_profitability(
        self, 
        opportunity: Dict[str, Any], 
        tx_params: TxParams
    ) -> ProfitAnalysis:
        """
        Comprehensive profitability analysis with simulation.
        
        Args:
            opportunity: Opportunity data
            tx_params: Transaction parameters
            
        Returns:
            Profit analysis result
        """
        try:
            start_time = time.time()
            
            # 1. Simulate transaction
            simulation_result = await self._simulate_transaction(tx_params)
            
            # 2. Calculate gas costs
            gas_analysis = await self._analyze_gas_costs(tx_params, simulation_result)
            
            # 3. Calculate profitability
            profit_analysis = await self._calculate_profitability(
                opportunity, gas_analysis, simulation_result
            )
            
            # 4. Optimize gas price if needed
            optimized_gas = await self._optimize_gas_price(profit_analysis, gas_analysis)
            
            # 5. Final profitability check
            final_analysis = await self._finalize_profit_analysis(
                profit_analysis, optimized_gas, simulation_result
            )
            
            # Update statistics
            self._optimization_stats["total_analyses"] += 1
            if final_analysis.profitable:
                self._optimization_stats["profitable_opportunities"] += 1
            
            analysis_time = (time.time() - start_time) * 1000
            logger.info(f"Profit analysis completed in {analysis_time:.1f}ms - Profitable: {final_analysis.profitable}")
            
            return final_analysis
            
        except Exception as e:
            logger.error(f"Error in profitability analysis: {e}")
            return ProfitAnalysis(
                gross_profit_eth=0.0,
                gas_cost_eth=0.0,
                net_profit_eth=0.0,
                roi_percentage=0.0,
                profitable=False,
                confidence_score=0.0,
                risk_level="high",
                recommended_gas_price_gwei=0,
                simulation_success=False,
                execution_probability=0.0
            )

    async def _simulate_transaction(self, tx_params: TxParams) -> Dict[str, Any]:
        """Simulate transaction to estimate gas usage and success probability."""
        try:
            # Use eth_call to simulate transaction
            simulation_result = await self._web3.eth.call(tx_params)
            
            # Estimate gas usage
            gas_estimate = await self._web3.eth.estimate_gas(tx_params)
            
            # Check if simulation was successful
            simulation_success = simulation_result is not None
            
            return {
                "success": simulation_success,
                "gas_estimate": gas_estimate,
                "simulation_result": simulation_result,
                "execution_probability": 0.9 if simulation_success else 0.1
            }
            
        except Exception as e:
            logger.warning(f"Transaction simulation failed: {e}")
            return {
                "success": False,
                "gas_estimate": tx_params.get("gas", settings.default_gas_limit),
                "simulation_result": None,
                "execution_probability": 0.3
            }

    async def _analyze_gas_costs(self, tx_params: TxParams, simulation_result: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze gas costs and optimize gas pricing."""
        try:
            # Get current gas price
            current_gas_price = await self._web3.eth.gas_price
            current_gas_price_gwei = float(self._web3.from_wei(current_gas_price, "gwei"))
            
            # Estimate gas usage
            gas_estimate = simulation_result.get("gas_estimate", settings.default_gas_limit)
            
            # Calculate gas costs with current price
            gas_cost_wei = gas_estimate * current_gas_price
            gas_cost_eth = float(self._web3.from_wei(gas_cost_wei, "ether"))
            
            # Optimize gas price based on market conditions
            optimized_gas_price_gwei = await self._calculate_optimal_gas_price(
                current_gas_price_gwei, gas_estimate
            )
            
            # Calculate optimized gas cost
            optimized_gas_price_wei = self._web3.to_wei(optimized_gas_price_gwei, "gwei")
            optimized_gas_cost_wei = gas_estimate * optimized_gas_price_wei
            optimized_gas_cost_eth = float(self._web3.from_wei(optimized_gas_cost_wei, "ether"))
            
            # Update gas price history
            self._update_gas_price_history(current_gas_price_gwei)
            
            return {
                "current_gas_price_gwei": current_gas_price_gwei,
                "optimized_gas_price_gwei": optimized_gas_price_gwei,
                "gas_estimate": gas_estimate,
                "current_gas_cost_eth": gas_cost_eth,
                "optimized_gas_cost_eth": optimized_gas_cost_eth,
                "gas_savings_eth": gas_cost_eth - optimized_gas_cost_eth,
                "market_conditions": await self._assess_gas_market_conditions()
            }
            
        except Exception as e:
            logger.error(f"Error analyzing gas costs: {e}")
            return {
                "current_gas_price_gwei": 50,
                "optimized_gas_price_gwei": 50,
                "gas_estimate": settings.default_gas_limit,
                "current_gas_cost_eth": 0.02,
                "optimized_gas_cost_eth": 0.02,
                "gas_savings_eth": 0.0,
                "market_conditions": "unknown"
            }

    async def _calculate_profitability(
        self, 
        opportunity: Dict[str, Any], 
        gas_analysis: Dict[str, Any], 
        simulation_result: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Calculate profitability metrics."""
        try:
            # Extract opportunity data
            expected_profit = float(opportunity.get("expected_profit_eth", 0))
            amount_in = float(opportunity.get("amount_in", 1.0))
            
            # Use optimized gas cost
            gas_cost = gas_analysis["optimized_gas_cost_eth"]
            
            # Calculate net profit
            net_profit = expected_profit - gas_cost
            
            # Calculate ROI
            roi_percentage = (net_profit / amount_in) * 100 if amount_in > 0 else 0
            
            # Determine if profitable
            profitable = (
                net_profit >= self._min_profit_eth and 
                roi_percentage >= self._min_roi_percentage and
                simulation_result["success"]
            )
            
            # Calculate confidence score
            confidence_score = self._calculate_profit_confidence(
                opportunity, gas_analysis, simulation_result, net_profit
            )
            
            # Assess risk level
            risk_level = self._assess_profit_risk(net_profit, roi_percentage, simulation_result)
            
            return {
                "gross_profit_eth": expected_profit,
                "gas_cost_eth": gas_cost,
                "net_profit_eth": net_profit,
                "roi_percentage": roi_percentage,
                "profitable": profitable,
                "confidence_score": confidence_score,
                "risk_level": risk_level,
                "execution_probability": simulation_result["execution_probability"]
            }
            
        except Exception as e:
            logger.error(f"Error calculating profitability: {e}")
            return {
                "gross_profit_eth": 0.0,
                "gas_cost_eth": 0.0,
                "net_profit_eth": 0.0,
                "roi_percentage": 0.0,
                "profitable": False,
                "confidence_score": 0.0,
                "risk_level": "high",
                "execution_probability": 0.0
            }

    async def _optimize_gas_price(self, profit_analysis: Dict[str, Any], gas_analysis: Dict[str, Any]) -> Dict[str, Any]:
        """Optimize gas price for maximum profitability."""
        try:
            current_gas_price = gas_analysis["current_gas_price_gwei"]
            optimized_gas_price = gas_analysis["optimized_gas_price_gwei"]
            
            # If not profitable, try to reduce gas price further
            if not profit_analysis["profitable"]:
                # Try different gas price strategies
                strategies = [
                    ("aggressive", current_gas_price * 0.8),
                    ("conservative", current_gas_price * 0.9),
                    ("market", current_gas_price),
                    ("premium", current_gas_price * 1.1)
                ]
                
                best_strategy = None
                best_profit = profit_analysis["net_profit_eth"]
                
                for strategy_name, gas_price in strategies:
                    # Recalculate profit with new gas price
                    gas_cost_wei = gas_analysis["gas_estimate"] * self._web3.to_wei(gas_price, "gwei")
                    gas_cost_eth = float(self._web3.from_wei(gas_cost_wei, "ether"))
                    net_profit = profit_analysis["gross_profit_eth"] - gas_cost_eth
                    
                    if net_profit > best_profit:
                        best_profit = net_profit
                        best_strategy = (strategy_name, gas_price)
                
                if best_strategy:
                    optimized_gas_price = best_strategy[1]
                    logger.info(f"Optimized gas price: {optimized_gas_price:.1f} Gwei ({best_strategy[0]} strategy)")
            
            return {
                "recommended_gas_price_gwei": int(optimized_gas_price),
                "gas_optimization_strategy": "dynamic",
                "potential_savings_eth": gas_analysis["gas_savings_eth"]
            }
            
        except Exception as e:
            logger.error(f"Error optimizing gas price: {e}")
            return {
                "recommended_gas_price_gwei": int(gas_analysis["current_gas_price_gwei"]),
                "gas_optimization_strategy": "fallback",
                "potential_savings_eth": 0.0
            }

    async def _finalize_profit_analysis(
        self, 
        profit_analysis: Dict[str, Any], 
        gas_optimization: Dict[str, Any], 
        simulation_result: Dict[str, Any]
    ) -> ProfitAnalysis:
        """Create final profit analysis result."""
        try:
            # Recalculate with optimized gas price
            optimized_gas_cost_wei = (
                profit_analysis["gas_cost_eth"] * 10**18 * 
                gas_optimization["recommended_gas_price_gwei"] / 
                (profit_analysis["gas_cost_eth"] * 10**18 / profit_analysis["gas_cost_eth"])
            )
            optimized_gas_cost_eth = float(self._web3.from_wei(int(optimized_gas_cost_wei), "ether"))
            
            final_net_profit = profit_analysis["gross_profit_eth"] - optimized_gas_cost_eth
            final_roi = (final_net_profit / 1.0) * 100  # Assuming 1 ETH investment
            
            # Final profitability check
            final_profitable = (
                final_net_profit >= self._min_profit_eth and
                final_roi >= self._min_roi_percentage and
                simulation_result["success"]
            )
            
            return ProfitAnalysis(
                gross_profit_eth=profit_analysis["gross_profit_eth"],
                gas_cost_eth=optimized_gas_cost_eth,
                net_profit_eth=final_net_profit,
                roi_percentage=final_roi,
                profitable=final_profitable,
                confidence_score=profit_analysis["confidence_score"],
                risk_level=profit_analysis["risk_level"],
                recommended_gas_price_gwei=gas_optimization["recommended_gas_price_gwei"],
                simulation_success=simulation_result["success"],
                execution_probability=profit_analysis["execution_probability"]
            )
            
        except Exception as e:
            logger.error(f"Error finalizing profit analysis: {e}")
            return ProfitAnalysis(
                gross_profit_eth=0.0,
                gas_cost_eth=0.0,
                net_profit_eth=0.0,
                roi_percentage=0.0,
                profitable=False,
                confidence_score=0.0,
                risk_level="high",
                recommended_gas_price_gwei=0,
                simulation_success=False,
                execution_probability=0.0
            )

    async def _calculate_optimal_gas_price(self, current_gas_price_gwei: float, gas_estimate: int) -> float:
        """Calculate optimal gas price based on market conditions and urgency."""
        try:
            # Get recent gas price history
            if len(self._gas_price_history) > 10:
                recent_prices = [price for _, price in self._gas_price_history[-10:]]
                avg_recent_price = sum(recent_prices) / len(recent_prices)
                
                # Adjust based on market trend
                if current_gas_price_gwei > avg_recent_price * 1.2:
                    # Gas prices are high, be conservative
                    return current_gas_price_gwei * 0.9
                elif current_gas_price_gwei < avg_recent_price * 0.8:
                    # Gas prices are low, can be more aggressive
                    return current_gas_price_gwei * 1.1
                else:
                    # Market is stable
                    return current_gas_price_gwei
            else:
                # Not enough history, use current price
                return current_gas_price_gwei
                
        except Exception as e:
            logger.error(f"Error calculating optimal gas price: {e}")
            return current_gas_price_gwei

    def _calculate_profit_confidence(
        self, 
        opportunity: Dict[str, Any], 
        gas_analysis: Dict[str, Any], 
        simulation_result: Dict[str, Any], 
        net_profit: float
    ) -> float:
        """Calculate confidence score for profit prediction."""
        try:
            confidence = 0.5  # Base confidence
            
            # Adjust based on simulation success
            if simulation_result["success"]:
                confidence += 0.2
            
            # Adjust based on profit margin
            if net_profit > 0.01:
                confidence += 0.15
            elif net_profit > 0.005:
                confidence += 0.1
            
            # Adjust based on gas market conditions
            market_conditions = gas_analysis.get("market_conditions", "unknown")
            if market_conditions == "stable":
                confidence += 0.1
            elif market_conditions == "volatile":
                confidence -= 0.1
            
            # Adjust based on opportunity type
            opportunity_type = opportunity.get("type", "unknown")
            if opportunity_type in ["arbitrage", "flashloan_arbitrage"]:
                confidence += 0.05
            elif opportunity_type in ["sandwich", "front_run"]:
                confidence -= 0.1
            
            return max(0.1, min(1.0, confidence))
            
        except Exception as e:
            logger.error(f"Error calculating profit confidence: {e}")
            return 0.5

    def _assess_profit_risk(self, net_profit: float, roi_percentage: float, simulation_result: Dict[str, Any]) -> str:
        """Assess risk level of profit opportunity."""
        try:
            risk_score = 0
            
            # Risk based on profit margin
            if net_profit < 0.005:
                risk_score += 3
            elif net_profit < 0.01:
                risk_score += 2
            elif net_profit < 0.02:
                risk_score += 1
            
            # Risk based on ROI
            if roi_percentage < 5:
                risk_score += 2
            elif roi_percentage < 10:
                risk_score += 1
            
            # Risk based on simulation
            if not simulation_result["success"]:
                risk_score += 2
            
            # Determine risk level
            if risk_score >= 5:
                return "high"
            elif risk_score >= 3:
                return "medium"
            else:
                return "low"
                
        except Exception as e:
            logger.error(f"Error assessing profit risk: {e}")
            return "high"

    async def _assess_gas_market_conditions(self) -> str:
        """Assess current gas market conditions."""
        try:
            if len(self._gas_price_history) < 5:
                return "unknown"
            
            recent_prices = [price for _, price in self._gas_price_history[-5:]]
            price_variance = sum((p - sum(recent_prices)/len(recent_prices))**2 for p in recent_prices) / len(recent_prices)
            
            if price_variance > 100:  # High variance
                return "volatile"
            elif price_variance > 25:  # Medium variance
                return "moderate"
            else:
                return "stable"
                
        except Exception as e:
            logger.error(f"Error assessing gas market conditions: {e}")
            return "unknown"

    def _update_gas_price_history(self, gas_price_gwei: float):
        """Update gas price history for analysis."""
        try:
            current_time = int(time.time())
            self._gas_price_history.append((current_time, gas_price_gwei))
            
            # Keep only recent history
            if len(self._gas_price_history) > self._max_history_size:
                self._gas_price_history = self._gas_price_history[-self._max_history_size:]
                
        except Exception as e:
            logger.error(f"Error updating gas price history: {e}")

    def record_execution_result(self, profit_analysis: ProfitAnalysis, success: bool, actual_profit: float):
        """Record the result of an executed opportunity."""
        try:
            self._optimization_stats["executed_opportunities"] += 1
            
            if success:
                self._optimization_stats["total_profit_eth"] += actual_profit
                self._optimization_stats["total_gas_spent_eth"] += profit_analysis.gas_cost_eth
                
                # Update average ROI
                total_analyses = self._optimization_stats["total_analyses"]
                if total_analyses > 0:
                    self._optimization_stats["avg_roi_percentage"] = (
                        (self._optimization_stats["avg_roi_percentage"] * (total_analyses - 1) + profit_analysis.roi_percentage) / 
                        total_analyses
                    )
                    
        except Exception as e:
            logger.error(f"Error recording execution result: {e}")

    def get_optimization_stats(self) -> Dict[str, Any]:
        """Get profit optimization statistics."""
        try:
            success_rate = 0.0
            if self._optimization_stats["total_analyses"] > 0:
                success_rate = (
                    self._optimization_stats["profitable_opportunities"] / 
                    self._optimization_stats["total_analyses"] * 100
                )
            
            execution_rate = 0.0
            if self._optimization_stats["profitable_opportunities"] > 0:
                execution_rate = (
                    self._optimization_stats["executed_opportunities"] / 
                    self._optimization_stats["profitable_opportunities"] * 100
                )
            
            return {
                **self._optimization_stats,
                "success_rate_percentage": success_rate,
                "execution_rate_percentage": execution_rate,
                "net_profit_eth": (
                    self._optimization_stats["total_profit_eth"] - 
                    self._optimization_stats["total_gas_spent_eth"]
                )
            }
            
        except Exception as e:
            logger.error(f"Error getting optimization stats: {e}")
            return self._optimization_stats 

    def is_profitable_trade(
        self, 
        input_amt: float, 
        output_amt: float, 
        gas_cost_eth: float, 
        roi_threshold_pct: float = 5.0
    ) -> bool:
        """
        Determine if a trade is profitable based on ROI threshold.
        
        Args:
            input_amt: Input amount in ETH
            output_amt: Output amount in ETH
            gas_cost_eth: Gas cost in ETH
            roi_threshold_pct: Minimum ROI percentage required
            
        Returns:
            True if ROI >= threshold, False otherwise
        """
        try:
            if input_amt <= 0:
                return False
            
            # Calculate net profit after gas costs
            net_profit = output_amt - input_amt - gas_cost_eth
            
            # Calculate ROI percentage
            roi_percentage = (net_profit / input_amt) * 100
            
            # Check if ROI meets threshold
            is_profitable = roi_percentage >= roi_threshold_pct
            
            logger.debug(f"Trade ROI: {roi_percentage:.2f}% (threshold: {roi_threshold_pct}%) - Profitable: {is_profitable}")
            
            return is_profitable
            
        except Exception as e:
            logger.error(f"Error calculating trade profitability: {e}")
            return False 