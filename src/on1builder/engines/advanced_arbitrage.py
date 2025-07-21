# src/on1builder/engines/advanced_arbitrage.py
from __future__ import annotations

import asyncio
import json
from decimal import Decimal
from typing import Any, Dict, List, Optional, Tuple, Set
from dataclasses import dataclass

from web3 import AsyncWeb3

from on1builder.config.loaders import settings
from on1builder.utils.logging_config import get_logger
from on1builder.utils.advanced_analytics import AdvancedAnalytics
from on1builder.monitoring.market_data_feed import MarketDataFeed

logger = get_logger(__name__)

@dataclass
class ArbitragePath:
    """Represents an arbitrage path with detailed routing information."""
    path_id: str
    tokens: List[str]
    exchanges: List[str]
    expected_profit_eth: float
    gas_estimate_eth: float
    net_profit_eth: float
    confidence_score: float
    path_type: str  # "simple", "multi_hop", "cross_chain", "concentrated"
    execution_complexity: int  # 1-10 scale
    risk_level: str

class AdvancedArbitrageEngine:
    """
    Advanced arbitrage engine supporting multi-hop, cross-chain, and concentrated liquidity strategies.
    Addresses the saturation of simple arbitrage opportunities.
    """
    
    def __init__(self, web3: AsyncWeb3, chain_id: int):
        self._web3 = web3
        self._chain_id = chain_id
        self._analytics = AdvancedAnalytics()
        self._market_feed = MarketDataFeed(web3)
        
        # Strategy configurations
        self._supported_dexes = {
            "uniswap_v2": {"version": "v2", "complexity": 1},
            "uniswap_v3": {"version": "v3", "complexity": 3},
            "sushiswap": {"version": "v2", "complexity": 1},
            "pancakeswap": {"version": "v2", "complexity": 1},
            "curve": {"version": "v2", "complexity": 4},
            "balancer": {"version": "v2", "complexity": 5},
            "dodo": {"version": "v2", "complexity": 2}
        }
        
        # Token pairs with high liquidity
        self._high_liquidity_pairs = [
            ("WETH", "USDC"), ("WETH", "USDT"), ("WETH", "DAI"),
            ("USDC", "USDT"), ("USDC", "DAI"), ("USDT", "DAI"),
            ("WETH", "WBTC"), ("WETH", "LINK"), ("WETH", "UNI")
        ]
        
        # Performance tracking
        self._arbitrage_stats = {
            "total_opportunities": 0,
            "profitable_opportunities": 0,
            "executed_opportunities": 0,
            "total_profit_eth": 0.0,
            "avg_profit_per_opportunity": 0.0
        }
        
        logger.info(f"AdvancedArbitrageEngine initialized for chain {chain_id}")

    async def find_arbitrage_opportunities(self, min_profit_eth: float = 0.005) -> List[ArbitragePath]:
        """
        Find arbitrage opportunities using advanced strategies.
        
        Args:
            min_profit_eth: Minimum profit threshold
            
        Returns:
            List of profitable arbitrage paths
        """
        opportunities = []
        
        # 1. Multi-hop arbitrage (3+ exchanges)
        multi_hop_opps = await self._find_multi_hop_opportunities(min_profit_eth)
        opportunities.extend(multi_hop_opps)
        
        # 2. Concentrated liquidity arbitrage (Uniswap V3)
        concentrated_opps = await self._find_concentrated_liquidity_opportunities(min_profit_eth)
        opportunities.extend(concentrated_opps)
        
        # 3. Cross-DEX arbitrage with different AMM types
        cross_dex_opps = await self._find_cross_dex_opportunities(min_profit_eth)
        opportunities.extend(cross_dex_opps)
        
        # 4. Flash loan arbitrage (for larger opportunities)
        flash_loan_opps = await self._find_flash_loan_opportunities(min_profit_eth)
        opportunities.extend(flash_loan_opps)
        
        # Sort by net profit
        opportunities.sort(key=lambda x: x.net_profit_eth, reverse=True)
        
        # Update statistics
        self._arbitrage_stats["total_opportunities"] += len(opportunities)
        profitable_count = len([opp for opp in opportunities if opp.net_profit_eth > 0])
        self._arbitrage_stats["profitable_opportunities"] += profitable_count
        
        return opportunities

    async def _find_multi_hop_opportunities(self, min_profit_eth: float) -> List[ArbitragePath]:
        """Find arbitrage opportunities involving 3+ exchanges."""
        opportunities = []
        
        try:
            # Get high-liquidity token pairs
            for token_a, token_b in self._high_liquidity_pairs:
                # Get prices from multiple exchanges
                prices = await self._get_multi_dex_prices(token_a, token_b)
                
                if len(prices) < 3:
                    continue
                
                # Find profitable paths through multiple exchanges
                profitable_paths = await self._calculate_multi_hop_paths(
                    token_a, token_b, prices, min_profit_eth
                )
                
                for path_data in profitable_paths:
                    path = ArbitragePath(
                        path_id=f"multi_hop_{token_a}_{token_b}_{len(path_data['exchanges'])}",
                        tokens=[token_a, token_b],
                        exchanges=path_data["exchanges"],
                        expected_profit_eth=path_data["profit"],
                        gas_estimate_eth=path_data["gas_estimate"],
                        net_profit_eth=path_data["net_profit"],
                        confidence_score=path_data["confidence"],
                        path_type="multi_hop",
                        execution_complexity=len(path_data["exchanges"]),
                        risk_level=self._assess_risk_level(path_data)
                    )
                    opportunities.append(path)
        
        except Exception as e:
            logger.error(f"Error finding multi-hop opportunities: {e}")
        
        return opportunities

    async def _find_concentrated_liquidity_opportunities(self, min_profit_eth: float) -> List[ArbitragePath]:
        """Find arbitrage opportunities using Uniswap V3 concentrated liquidity."""
        opportunities = []
        
        try:
            # Focus on tokens with concentrated liquidity pools
            concentrated_pairs = [
                ("WETH", "USDC"), ("WETH", "USDT"), ("WETH", "DAI"),
                ("WBTC", "WETH"), ("LINK", "WETH"), ("UNI", "WETH")
            ]
            
            for token_a, token_b in concentrated_pairs:
                # Get Uniswap V3 pool data
                pool_data = await self._get_uniswap_v3_pool_data(token_a, token_b)
                
                if not pool_data:
                    continue
                
                # Find arbitrage opportunities within concentrated liquidity ranges
                v3_opportunities = await self._analyze_concentrated_liquidity(
                    token_a, token_b, pool_data, min_profit_eth
                )
                
                for opp_data in v3_opportunities:
                    path = ArbitragePath(
                        path_id=f"concentrated_{token_a}_{token_b}_{opp_data['tick_range']}",
                        tokens=[token_a, token_b],
                        exchanges=["uniswap_v3"],
                        expected_profit_eth=opp_data["profit"],
                        gas_estimate_eth=opp_data["gas_estimate"],
                        net_profit_eth=opp_data["net_profit"],
                        confidence_score=opp_data["confidence"],
                        path_type="concentrated",
                        execution_complexity=4,
                        risk_level="medium"
                    )
                    opportunities.append(path)
        
        except Exception as e:
            logger.error(f"Error finding concentrated liquidity opportunities: {e}")
        
        return opportunities

    async def _find_cross_dex_opportunities(self, min_profit_eth: float) -> List[ArbitragePath]:
        """Find arbitrage between different types of DEXes (AMM vs Order Book)."""
        opportunities = []
        
        try:
            # Compare AMM DEXes with different mechanisms
            amm_dexes = ["uniswap_v2", "sushiswap", "pancakeswap"]
            hybrid_dexes = ["dodo", "balancer", "curve"]
            
            for token_a, token_b in self._high_liquidity_pairs:
                # Get prices from AMM DEXes
                amm_prices = await self._get_dex_prices(token_a, token_b, amm_dexes)
                
                # Get prices from hybrid DEXes
                hybrid_prices = await self._get_dex_prices(token_a, token_b, hybrid_dexes)
                
                # Find arbitrage between different DEX types
                cross_dex_opps = await self._calculate_cross_dex_arbitrage(
                    token_a, token_b, amm_prices, hybrid_prices, min_profit_eth
                )
                
                for opp_data in cross_dex_opps:
                    path = ArbitragePath(
                        path_id=f"cross_dex_{token_a}_{token_b}_{opp_data['dex_pair']}",
                        tokens=[token_a, token_b],
                        exchanges=opp_data["exchanges"],
                        expected_profit_eth=opp_data["profit"],
                        gas_estimate_eth=opp_data["gas_estimate"],
                        net_profit_eth=opp_data["net_profit"],
                        confidence_score=opp_data["confidence"],
                        path_type="cross_dex",
                        execution_complexity=3,
                        risk_level="low"
                    )
                    opportunities.append(path)
        
        except Exception as e:
            logger.error(f"Error finding cross-DEX opportunities: {e}")
        
        return opportunities

    async def _find_flash_loan_opportunities(self, min_profit_eth: float) -> List[ArbitragePath]:
        """Find arbitrage opportunities that require flash loans."""
        opportunities = []
        
        try:
            # Look for larger opportunities that justify flash loan costs
            flash_loan_min_profit = min_profit_eth * 2  # Higher threshold for flash loans
            
            for token_a, token_b in self._high_liquidity_pairs:
                # Get prices from all exchanges
                all_prices = await self._get_all_dex_prices(token_a, token_b)
                
                if len(all_prices) < 2:
                    continue
                
                # Find opportunities that require significant capital
                flash_loan_opps = await self._calculate_flash_loan_arbitrage(
                    token_a, token_b, all_prices, flash_loan_min_profit
                )
                
                for opp_data in flash_loan_opps:
                    path = ArbitragePath(
                        path_id=f"flash_loan_{token_a}_{token_b}_{opp_data['amount']}",
                        tokens=[token_a, token_b],
                        exchanges=opp_data["exchanges"],
                        expected_profit_eth=opp_data["profit"],
                        gas_estimate_eth=opp_data["gas_estimate"],
                        net_profit_eth=opp_data["net_profit"],
                        confidence_score=opp_data["confidence"],
                        path_type="flash_loan",
                        execution_complexity=6,
                        risk_level="medium"
                    )
                    opportunities.append(path)
        
        except Exception as e:
            logger.error(f"Error finding flash loan opportunities: {e}")
        
        return opportunities

    async def _get_multi_dex_prices(self, token_a: str, token_b: str) -> List[Tuple[str, float]]:
        """Get prices from multiple DEXes for a token pair."""
        prices = []
        
        # Get prices from different DEXes
        for dex_name in self._supported_dexes.keys():
            try:
                price = await self._get_dex_price(token_a, token_b, dex_name)
                if price and price > 0:
                    prices.append((dex_name, price))
            except Exception as e:
                logger.debug(f"Error getting price from {dex_name}: {e}")
        
        return prices

    async def _get_dex_price(self, token_a: str, token_b: str, dex_name: str) -> Optional[float]:
        """Get price from a specific DEX."""
        try:
            # This would integrate with actual DEX price feeds
            # For now, return mock data
            base_prices = {
                ("WETH", "USDC"): 1800.0,
                ("WETH", "USDT"): 1800.0,
                ("WETH", "DAI"): 1800.0,
                ("USDC", "USDT"): 1.0,
                ("USDC", "DAI"): 1.0,
                ("USDT", "DAI"): 1.0
            }
            
            base_price = base_prices.get((token_a, token_b))
            if not base_price:
                return None
            
            # Add some variation based on DEX
            dex_variations = {
                "uniswap_v2": 1.0,
                "uniswap_v3": 1.001,
                "sushiswap": 0.999,
                "pancakeswap": 1.002,
                "curve": 0.998,
                "balancer": 1.001,
                "dodo": 0.999
            }
            
            variation = dex_variations.get(dex_name, 1.0)
            return base_price * variation
            
        except Exception as e:
            logger.debug(f"Error getting price from {dex_name}: {e}")
            return None

    async def _calculate_multi_hop_paths(
        self, 
        token_a: str, 
        token_b: str, 
        prices: List[Tuple[str, float]], 
        min_profit_eth: float
    ) -> List[Dict[str, Any]]:
        """Calculate profitable multi-hop arbitrage paths."""
        profitable_paths = []
        
        try:
            # Find all possible combinations of 3+ exchanges
            from itertools import combinations
            
            for r in range(3, min(6, len(prices) + 1)):
                for combo in combinations(prices, r):
                    # Calculate arbitrage through this path
                    path_result = await self._calculate_path_profitability(
                        token_a, token_b, list(combo), min_profit_eth
                    )
                    
                    if path_result and path_result["profitable"]:
                        profitable_paths.append(path_result)
        
        except Exception as e:
            logger.error(f"Error calculating multi-hop paths: {e}")
        
        return profitable_paths

    async def _calculate_path_profitability(
        self, 
        token_a: str, 
        token_b: str, 
        price_path: List[Tuple[str, float]], 
        min_profit_eth: float
    ) -> Optional[Dict[str, Any]]:
        """Calculate profitability of a specific price path."""
        try:
            if len(price_path) < 2:
                return None
            
            # Find best buy and sell prices
            buy_price = min(price_path, key=lambda x: x[1])
            sell_price = max(price_path, key=lambda x: x[1])
            
            if buy_price[0] == sell_price[0]:
                return None  # Same exchange, no arbitrage
            
            # Calculate profit
            amount_in = 1.0  # 1 ETH equivalent
            amount_out = amount_in * (sell_price[1] / buy_price[1])
            gross_profit = amount_out - amount_in
            
            # Estimate gas costs
            gas_estimate = await self._estimate_gas_for_path(price_path)
            
            # Calculate net profit
            net_profit = gross_profit - gas_estimate
            
            if net_profit >= min_profit_eth:
                return {
                    "profitable": True,
                    "exchanges": [p[0] for p in price_path],
                    "profit": gross_profit,
                    "gas_estimate": gas_estimate,
                    "net_profit": net_profit,
                    "confidence": self._calculate_confidence(price_path, net_profit),
                    "buy_exchange": buy_price[0],
                    "sell_exchange": sell_price[0],
                    "buy_price": buy_price[1],
                    "sell_price": sell_price[1]
                }
        
        except Exception as e:
            logger.error(f"Error calculating path profitability: {e}")
        
        return None

    async def _estimate_gas_for_path(self, price_path: List[Tuple[str, float]]) -> float:
        """Estimate gas costs for executing a price path."""
        try:
            # Base gas costs per exchange
            base_gas_costs = {
                "uniswap_v2": 0.005,
                "uniswap_v3": 0.008,
                "sushiswap": 0.005,
                "pancakeswap": 0.005,
                "curve": 0.012,
                "balancer": 0.015,
                "dodo": 0.008
            }
            
            total_gas = 0.0
            for exchange, _ in price_path:
                gas_cost = base_gas_costs.get(exchange, 0.01)
                total_gas += gas_cost
            
            # Add overhead for multi-hop
            if len(price_path) > 2:
                total_gas *= 1.2  # 20% overhead for complex paths
            
            return total_gas
            
        except Exception as e:
            logger.error(f"Error estimating gas: {e}")
            return 0.02  # Default estimate

    def _calculate_confidence(self, price_path: List[Tuple[str, float]], net_profit: float) -> float:
        """Calculate confidence score for an arbitrage opportunity."""
        try:
            # Base confidence
            confidence = 0.7
            
            # Adjust based on number of exchanges (more exchanges = lower confidence)
            if len(price_path) > 3:
                confidence -= 0.1
            
            # Adjust based on profit margin
            if net_profit > 0.01:
                confidence += 0.1
            elif net_profit < 0.005:
                confidence -= 0.1
            
            # Adjust based on exchange reliability
            reliable_exchanges = {"uniswap_v2", "uniswap_v3", "sushiswap"}
            reliable_count = sum(1 for ex, _ in price_path if ex in reliable_exchanges)
            confidence += (reliable_count / len(price_path)) * 0.1
            
            return max(0.1, min(1.0, confidence))
            
        except Exception as e:
            logger.error(f"Error calculating confidence: {e}")
            return 0.5

    def _assess_risk_level(self, path_data: Dict[str, Any]) -> str:
        """Assess risk level of an arbitrage path."""
        try:
            complexity = path_data.get("execution_complexity", 1)
            profit = path_data.get("net_profit", 0)
            
            if complexity > 5 or profit < 0.005:
                return "high"
            elif complexity > 3 or profit < 0.01:
                return "medium"
            else:
                return "low"
                
        except Exception as e:
            logger.error(f"Error assessing risk: {e}")
            return "medium"

    async def _get_uniswap_v3_pool_data(self, token_a: str, token_b: str) -> Optional[Dict[str, Any]]:
        """Get Uniswap V3 pool data for concentrated liquidity analysis."""
        # This would integrate with Uniswap V3 pool contracts
        # For now, return mock data
        return {
            "pool_address": "0x8ad599c3a0ff1de082011efddc58f1908eb6e6d8",
            "fee_tier": 3000,
            "tick_spacing": 60,
            "current_tick": 194000,
            "liquidity": 1000000000000,
            "sqrt_price_x96": 1771842903320439540000000000000000000
        }

    async def _analyze_concentrated_liquidity(
        self, 
        token_a: str, 
        token_b: str, 
        pool_data: Dict[str, Any], 
        min_profit_eth: float
    ) -> List[Dict[str, Any]]:
        """Analyze concentrated liquidity for arbitrage opportunities."""
        # This would implement sophisticated concentrated liquidity analysis
        # For now, return empty list
        return []

    async def _get_dex_prices(self, token_a: str, token_b: str, dexes: List[str]) -> List[Tuple[str, float]]:
        """Get prices from specific DEXes."""
        prices = []
        for dex in dexes:
            price = await self._get_dex_price(token_a, token_b, dex)
            if price:
                prices.append((dex, price))
        return prices

    async def _get_all_dex_prices(self, token_a: str, token_b: str) -> List[Tuple[str, float]]:
        """Get prices from all supported DEXes."""
        return await self._get_dex_prices(token_a, token_b, list(self._supported_dexes.keys()))

    async def _calculate_cross_dex_arbitrage(
        self, 
        token_a: str, 
        token_b: str, 
        amm_prices: List[Tuple[str, float]], 
        hybrid_prices: List[Tuple[str, float]], 
        min_profit_eth: float
    ) -> List[Dict[str, Any]]:
        """Calculate arbitrage between AMM and hybrid DEXes."""
        opportunities = []
        
        try:
            for amm_ex, amm_price in amm_prices:
                for hybrid_ex, hybrid_price in hybrid_prices:
                    if amm_ex == hybrid_ex:
                        continue
                    
                    # Calculate arbitrage
                    price_diff = abs(amm_price - hybrid_price)
                    if price_diff > 0.001:  # 0.1% minimum spread
                        profit = price_diff * 1.0  # 1 ETH equivalent
                        gas_estimate = 0.015  # Higher for cross-DEX
                        net_profit = profit - gas_estimate
                        
                        if net_profit >= min_profit_eth:
                            opportunities.append({
                                "profitable": True,
                                "exchanges": [amm_ex, hybrid_ex],
                                "dex_pair": f"{amm_ex}_{hybrid_ex}",
                                "profit": profit,
                                "gas_estimate": gas_estimate,
                                "net_profit": net_profit,
                                "confidence": 0.8
                            })
        
        except Exception as e:
            logger.error(f"Error calculating cross-DEX arbitrage: {e}")
        
        return opportunities

    async def _calculate_flash_loan_arbitrage(
        self, 
        token_a: str, 
        token_b: str, 
        all_prices: List[Tuple[str, float]], 
        min_profit_eth: float
    ) -> List[Dict[str, Any]]:
        """Calculate flash loan arbitrage opportunities."""
        opportunities = []
        
        try:
            # Find largest price differences
            if len(all_prices) >= 2:
                min_price = min(all_prices, key=lambda x: x[1])
                max_price = max(all_prices, key=lambda x: x[1])
                
                if min_price[0] != max_price[0]:
                    # Calculate flash loan arbitrage
                    amount = 100.0  # 100 ETH flash loan
                    profit = amount * (max_price[1] / min_price[1] - 1)
                    gas_estimate = 0.025  # Higher for flash loans
                    net_profit = profit - gas_estimate
                    
                    if net_profit >= min_profit_eth:
                        opportunities.append({
                            "profitable": True,
                            "exchanges": [min_price[0], max_price[0]],
                            "amount": amount,
                            "profit": profit,
                            "gas_estimate": gas_estimate,
                            "net_profit": net_profit,
                            "confidence": 0.7
                        })
        
        except Exception as e:
            logger.error(f"Error calculating flash loan arbitrage: {e}")
        
        return opportunities

    def get_arbitrage_stats(self) -> Dict[str, Any]:
        """Get arbitrage engine statistics."""
        return {
            **self._arbitrage_stats,
            "success_rate": (
                self._arbitrage_stats["profitable_opportunities"] / 
                max(1, self._arbitrage_stats["total_opportunities"]) * 100
            )
        } 