# src/on1builder/engines/opportunity_detector.py
from __future__ import annotations

import asyncio
import json
from decimal import Decimal
from typing import Any, Dict, List, Optional, Set, Tuple
from datetime import datetime, timedelta
from dataclasses import dataclass

from web3 import AsyncWeb3

from on1builder.config.loaders import settings
from on1builder.utils.advanced_analytics import AdvancedAnalytics, OpportunityScore
from on1builder.utils.logging_config import get_logger
from on1builder.monitoring.market_data_feed import MarketDataFeed
from on1builder.monitoring.txpool_scanner import TxPoolScanner
from on1builder.integrations.abi_registry import ABIRegistry

logger = get_logger(__name__)

@dataclass
class DetectedOpportunity:
    """Represents a detected MEV opportunity with comprehensive metadata."""
    id: str
    type: str
    chain_id: int
    tokens: List[str]
    expected_profit_eth: float
    amount_in: float
    gas_estimate_eth: float
    confidence_score: float
    risk_level: str
    execution_priority: int
    timestamp: datetime
    metadata: Dict[str, Any]
    analytics_score: Optional[OpportunityScore] = None

class OpportunityDetector:
    """
    Advanced opportunity detector that identifies and scores MEV opportunities
    across multiple chains and strategies using real-time market analysis.
    """
    
    def __init__(self, web3: AsyncWeb3, chain_id: int):
        self._web3 = web3
        self._chain_id = chain_id
        self._analytics = AdvancedAnalytics()
        self._market_feed = MarketDataFeed(web3)
        self._tx_scanner = TxPoolScanner(web3)
        self._abi_registry = ABIRegistry()
        
        # Opportunity tracking
        self._detected_opportunities: Dict[str, DetectedOpportunity] = {}
        self._opportunity_history: List[DetectedOpportunity] = []
        self._blacklisted_opportunities: Set[str] = set()
        
        # Performance metrics
        self._detection_stats = {
            "total_detected": 0,
            "total_executed": 0,
            "total_profitable": 0,
            "avg_detection_time_ms": 0,
            "false_positives": 0
        }
        
        # Configuration
        self._min_profit_threshold = settings.min_profit_eth
        self._min_confidence_score = 0.6
        self._max_opportunities_per_cycle = 50
        
        # State
        self._is_running = False
        self._detection_task: Optional[asyncio.Task] = None
        
        logger.info(f"OpportunityDetector initialized for chain {chain_id}")

    async def start(self):
        """Start the opportunity detection process."""
        if self._is_running:
            logger.warning("OpportunityDetector is already running.")
            return
        
        self._is_running = True
        logger.info("Starting OpportunityDetector...")
        
        # Start dependencies
        await self._market_feed.start()
        await self._tx_scanner.start()
        
        # Start detection loop
        self._detection_task = asyncio.create_task(self._detection_loop())

    async def stop(self):
        """Stop the opportunity detection process."""
        if not self._is_running:
            return
        
        self._is_running = False
        
        if self._detection_task:
            self._detection_task.cancel()
            try:
                await self._detection_task
            except asyncio.CancelledError:
                pass
        
        await self._market_feed.stop()
        await self._tx_scanner.stop()
        
        logger.info("OpportunityDetector stopped.")

    async def get_best_opportunities(self, limit: int = 10) -> List[DetectedOpportunity]:
        """Get the best opportunities currently available."""
        opportunities = list(self._detected_opportunities.values())
        
        # Filter by minimum requirements
        valid_opportunities = [
            opp for opp in opportunities
            if (opp.expected_profit_eth >= self._min_profit_threshold and
                opp.confidence_score >= self._min_confidence_score and
                opp.id not in self._blacklisted_opportunities)
        ]
        
        # Sort by priority score (combination of profit and confidence)
        valid_opportunities.sort(
            key=lambda x: x.expected_profit_eth * x.confidence_score,
            reverse=True
        )
        
        return valid_opportunities[:limit]

    async def _detection_loop(self):
        """Main detection loop that continuously scans for opportunities."""
        while self._is_running:
            try:
                start_time = datetime.now()
                
                # Detect opportunities across all strategies
                opportunities = await self._detect_all_opportunities()
                
                # Score and filter opportunities
                scored_opportunities = await self._score_opportunities(opportunities)
                
                # Update detected opportunities
                await self._update_detected_opportunities(scored_opportunities)
                
                # Calculate detection time
                detection_time = (datetime.now() - start_time).total_seconds() * 1000
                self._detection_stats["avg_detection_time_ms"] = (
                    self._detection_stats["avg_detection_time_ms"] * 0.9 + detection_time * 0.1
                )
                
                # Log detection summary
                if scored_opportunities:
                    logger.info(f"Detected {len(scored_opportunities)} opportunities in {detection_time:.1f}ms")
                
                # Wait before next detection cycle
                await asyncio.sleep(settings.arbitrage_scan_interval)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in detection loop: {e}", exc_info=True)
                await asyncio.sleep(5)  # Brief pause on error

    async def _detect_all_opportunities(self) -> List[Dict[str, Any]]:
        """Detect opportunities across all supported strategies."""
        opportunities = []
        
        # Detect arbitrage opportunities
        if settings.mev_strategies_enabled:
            arbitrage_opps = await self._detect_arbitrage_opportunities()
            opportunities.extend(arbitrage_opps)
        
        # Detect front-running opportunities
        if settings.front_running_enabled:
            front_run_opps = await self._detect_front_running_opportunities()
            opportunities.extend(front_run_opps)
        
        # Detect back-running opportunities
        if settings.back_running_enabled:
            back_run_opps = await self._detect_back_running_opportunities()
            opportunities.extend(back_run_opps)
        
        # Detect sandwich opportunities
        if settings.sandwich_attacks_enabled:
            sandwich_opps = await self._detect_sandwich_opportunities()
            opportunities.extend(sandwich_opps)
        
        # Detect liquidation opportunities
        liquidation_opps = await self._detect_liquidation_opportunities()
        opportunities.extend(liquidation_opps)
        
        return opportunities

    async def _detect_arbitrage_opportunities(self) -> List[Dict[str, Any]]:
        """Detect arbitrage opportunities across DEXes."""
        opportunities = []
        
        try:
            # Get supported token pairs
            token_pairs = await self._get_supported_token_pairs()
            
            for token_a, token_b in token_pairs:
                # Get prices from different DEXes
                prices = await self._get_dex_prices(token_a, token_b)
                
                if len(prices) < 2:
                    continue
                
                # Find price differences
                for i, (dex1, price1) in enumerate(prices):
                    for dex2, price2 in prices[i+1:]:
                        if dex1 == dex2:
                            continue
                        
                        # Calculate arbitrage opportunity
                        price_diff = abs(price1 - price2)
                        price_ratio = price_diff / min(price1, price2)
                        
                        if price_ratio > 0.005:  # 0.5% minimum spread
                            # Estimate profit
                            amount_in = 1.0  # 1 ETH equivalent
                            expected_profit = amount_in * price_ratio
                            
                            if expected_profit >= self._min_profit_threshold:
                                opportunity = {
                                    "type": "arbitrage",
                                    "chain_id": self._chain_id,
                                    "tokens": [token_a, token_b],
                                    "dex_buy": dex1 if price1 < price2 else dex2,
                                    "dex_sell": dex2 if price1 < price2 else dex1,
                                    "price_buy": min(price1, price2),
                                    "price_sell": max(price1, price2),
                                    "expected_profit_eth": expected_profit,
                                    "amount_in": amount_in,
                                    "spread_percentage": price_ratio * 100,
                                    "gas_estimate_eth": await self._estimate_gas_cost("arbitrage"),
                                    "timestamp": datetime.now()
                                }
                                opportunities.append(opportunity)
        
        except Exception as e:
            logger.error(f"Error detecting arbitrage opportunities: {e}")
        
        return opportunities

    async def _detect_front_running_opportunities(self) -> List[Dict[str, Any]]:
        """Detect front-running opportunities from mempool."""
        opportunities = []
        
        try:
            # Get pending transactions from mempool
            pending_txs = await self._tx_scanner.get_pending_transactions()
            
            for tx in pending_txs:
                # Analyze transaction for front-running potential
                if await self._is_front_runnable(tx):
                    opportunity = await self._create_front_run_opportunity(tx)
                    if opportunity:
                        opportunities.append(opportunity)
        
        except Exception as e:
            logger.error(f"Error detecting front-running opportunities: {e}")
        
        return opportunities

    async def _detect_back_running_opportunities(self) -> List[Dict[str, Any]]:
        """Detect back-running opportunities."""
        opportunities = []
        
        try:
            # Similar to front-running but with different timing
            pending_txs = await self._tx_scanner.get_pending_transactions()
            
            for tx in pending_txs:
                if await self._is_back_runnable(tx):
                    opportunity = await self._create_back_run_opportunity(tx)
                    if opportunity:
                        opportunities.append(opportunity)
        
        except Exception as e:
            logger.error(f"Error detecting back-running opportunities: {e}")
        
        return opportunities

    async def _detect_sandwich_opportunities(self) -> List[Dict[str, Any]]:
        """Detect sandwich attack opportunities."""
        opportunities = []
        
        try:
            # Look for large pending transactions that can be sandwiched
            pending_txs = await self._tx_scanner.get_pending_transactions()
            
            for tx in pending_txs:
                if await self._is_sandwichable(tx):
                    opportunity = await self._create_sandwich_opportunity(tx)
                    if opportunity:
                        opportunities.append(opportunity)
        
        except Exception as e:
            logger.error(f"Error detecting sandwich opportunities: {e}")
        
        return opportunities

    async def _detect_liquidation_opportunities(self) -> List[Dict[str, Any]]:
        """Detect liquidation opportunities."""
        opportunities = []
        
        try:
            # This would integrate with lending protocols to find liquidatable positions
            # For now, return empty list as placeholder
            pass
        
        except Exception as e:
            logger.error(f"Error detecting liquidation opportunities: {e}")
        
        return opportunities

    async def _score_opportunities(self, opportunities: List[Dict[str, Any]]) -> List[DetectedOpportunity]:
        """Score and convert opportunities to DetectedOpportunity objects."""
        scored_opportunities = []
        
        for opp_data in opportunities:
            try:
                # Score the opportunity using advanced analytics
                analytics_score = await self._analytics.score_opportunity(opp_data)
                
                # Create DetectedOpportunity object
                opportunity = DetectedOpportunity(
                    id=self._generate_opportunity_id(opp_data),
                    type=opp_data.get("type", "unknown"),
                    chain_id=self._chain_id,
                    tokens=opp_data.get("tokens", []),
                    expected_profit_eth=opp_data.get("expected_profit_eth", 0),
                    amount_in=opp_data.get("amount_in", 0),
                    gas_estimate_eth=opp_data.get("gas_estimate_eth", 0),
                    confidence_score=analytics_score.total_score,
                    risk_level=self._get_risk_level(analytics_score.risk_score),
                    execution_priority=self._calculate_execution_priority(opp_data, analytics_score),
                    timestamp=opp_data.get("timestamp", datetime.now()),
                    metadata=opp_data,
                    analytics_score=analytics_score
                )
                
                scored_opportunities.append(opportunity)
                
            except Exception as e:
                logger.error(f"Error scoring opportunity: {e}")
                continue
        
        return scored_opportunities

    async def _update_detected_opportunities(self, new_opportunities: List[DetectedOpportunity]):
        """Update the current set of detected opportunities."""
        # Add new opportunities
        for opp in new_opportunities:
            self._detected_opportunities[opp.id] = opp
        
        # Remove stale opportunities (older than 5 minutes)
        current_time = datetime.now()
        stale_ids = [
            opp_id for opp_id, opp in self._detected_opportunities.items()
            if (current_time - opp.timestamp).total_seconds() > 300
        ]
        
        for opp_id in stale_ids:
            del self._detected_opportunities[opp_id]
        
        # Update statistics
        self._detection_stats["total_detected"] += len(new_opportunities)
        
        # Keep opportunity history (last 1000)
        self._opportunity_history.extend(new_opportunities)
        if len(self._opportunity_history) > 1000:
            self._opportunity_history = self._opportunity_history[-1000:]

    def _generate_opportunity_id(self, opp_data: Dict[str, Any]) -> str:
        """Generate unique ID for opportunity."""
        import hashlib
        
        # Create unique string from opportunity data
        unique_string = f"{opp_data.get('type')}_{self._chain_id}_{opp_data.get('tokens', [])}_{opp_data.get('timestamp', datetime.now())}"
        return hashlib.md5(unique_string.encode()).hexdigest()[:16]

    def _get_risk_level(self, risk_score: float) -> str:
        """Convert risk score to risk level."""
        if risk_score < 0.25:
            return "low"
        elif risk_score < 0.5:
            return "medium"
        elif risk_score < 0.75:
            return "high"
        else:
            return "extreme"

    def _calculate_execution_priority(self, opp_data: Dict[str, Any], analytics_score: OpportunityScore) -> int:
        """Calculate execution priority (1-10, where 10 is highest priority)."""
        # Base priority on profit and confidence
        base_priority = int(analytics_score.total_score * 10)
        
        # Adjust for strategy type
        strategy_type = opp_data.get("type", "arbitrage")
        if strategy_type == "flashloan_arbitrage":
            base_priority += 2  # Higher priority for flashloans
        elif strategy_type == "sandwich":
            base_priority -= 1  # Lower priority for sandwiches
        
        # Adjust for time sensitivity
        if opp_data.get("time_sensitive", False):
            base_priority += 1
        
        return max(1, min(10, base_priority))

    async def _get_supported_token_pairs(self) -> List[Tuple[str, str]]:
        """Get supported token pairs for arbitrage."""
        # This would load from configuration or API
        return [
            ("WETH", "USDC"),
            ("WETH", "USDT"),
            ("WETH", "DAI"),
            ("USDC", "USDT"),
            ("USDC", "DAI")
        ]

    async def _get_dex_prices(self, token_a: str, token_b: str) -> List[Tuple[str, float]]:
        """Get prices for token pair from different DEXes."""
        prices = []
        
        # This would query actual DEX prices
        # For now, return mock data
        prices.extend([
            ("uniswap_v2", 1800.0),
            ("sushiswap", 1798.0),
            ("uniswap_v3", 1802.0)
        ])
        
        return prices

    async def _estimate_gas_cost(self, strategy_type: str) -> float:
        """Estimate gas cost for strategy execution."""
        # Base gas estimates
        gas_estimates = {
            "arbitrage": 0.01,
            "front_run": 0.015,
            "back_run": 0.015,
            "sandwich": 0.025,
            "flashloan_arbitrage": 0.02
        }
        
        return gas_estimates.get(strategy_type, 0.02)

    async def _is_front_runnable(self, tx: Dict[str, Any]) -> bool:
        """Check if transaction can be front-run."""
        # This would analyze transaction for front-running potential
        return False  # Placeholder

    async def _is_back_runnable(self, tx: Dict[str, Any]) -> bool:
        """Check if transaction can be back-run."""
        # This would analyze transaction for back-running potential
        return False  # Placeholder

    async def _is_sandwichable(self, tx: Dict[str, Any]) -> bool:
        """Check if transaction can be sandwiched."""
        # This would analyze transaction for sandwich potential
        return False  # Placeholder

    async def _create_front_run_opportunity(self, tx: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Create front-running opportunity from transaction."""
        # This would create opportunity data
        return None  # Placeholder

    async def _create_back_run_opportunity(self, tx: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Create back-running opportunity from transaction."""
        # This would create opportunity data
        return None  # Placeholder

    async def _create_sandwich_opportunity(self, tx: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Create sandwich opportunity from transaction."""
        # This would create opportunity data
        return None  # Placeholder

    def get_detection_stats(self) -> Dict[str, Any]:
        """Get detection statistics."""
        return {
            **self._detection_stats,
            "current_opportunities": len(self._detected_opportunities),
            "blacklisted_opportunities": len(self._blacklisted_opportunities),
            "analytics_summary": self._analytics.get_analytics_summary()
        }

    def blacklist_opportunity(self, opportunity_id: str):
        """Blacklist an opportunity (e.g., after failed execution)."""
        self._blacklisted_opportunities.add(opportunity_id)
        if opportunity_id in self._detected_opportunities:
            del self._detected_opportunities[opportunity_id]

    def record_execution_result(self, opportunity_id: str, success: bool, profit: float):
        """Record the result of opportunity execution."""
        self._detection_stats["total_executed"] += 1
        if success:
            self._detection_stats["total_profitable"] += 1
        else:
            self._detection_stats["false_positives"] += 1
        
        # Update analytics
        if opportunity_id in self._detected_opportunities:
            opp = self._detected_opportunities[opportunity_id]
            self._analytics.update_performance_metrics(opp.type, success, profit) 