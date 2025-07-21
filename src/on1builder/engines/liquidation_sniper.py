"""
Liquidation Sniper Module for Aave V3.

Monitors liquidation events and executes profitable liquidations using flash loans.
"""

import asyncio
import logging
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from web3 import Web3
from web3.types import LogReceipt

from on1builder.utils.web3_factory import Web3Factory
from on1builder.monitoring.flashbots_relay import FlashbotsRelay
from on1builder.utils.profit_optimizer import ProfitOptimizer
from on1builder.config.loaders import settings

logger = logging.getLogger(__name__)

@dataclass
class LiquidationOpportunity:
    """Represents a liquidation opportunity."""
    borrower: str
    collateral_asset: str
    debt_asset: str
    collateral_amount: float
    debt_amount: float
    liquidation_bonus: float
    estimated_profit: float
    block_number: int
    timestamp: int

class LiquidationSniper:
    """
    Monitors Aave V3 for liquidation opportunities and executes profitable liquidations.
    """
    
    def __init__(self, web3_factory: Web3Factory, flashbots_relay: FlashbotsRelay):
        self.web3_factory = web3_factory
        self.flashbots_relay = flashbots_relay
        self.profit_optimizer = ProfitOptimizer()
        
        # Aave V3 liquidation event signature
        self.liquidation_event_signature = "LiquidationCall(address,address,address,uint256,uint256,address,bool)"
        self.liquidation_event_topic = Web3.keccak(text=self.liquidation_event_signature)
        
        # Liquidation parameters
        self.min_liquidation_bonus = 0.05  # 5% minimum bonus
        self.max_gas_price_gwei = 100
        self.min_profit_eth = 0.01
        
        # State tracking
        self.active_liquidations: Dict[str, LiquidationOpportunity] = {}
        self.liquidation_history: List[LiquidationOpportunity] = []
        
    async def start_monitoring(self):
        """Start monitoring for liquidation events."""
        logger.info("Starting liquidation monitoring...")
        
        try:
            # Get latest block
            latest_block = await self.web3_factory.get_web3().eth.block_number
            
            # Start monitoring from recent blocks
            start_block = latest_block - 100
            
            while True:
                try:
                    await self._scan_for_liquidations(start_block)
                    await asyncio.sleep(1)  # Check every second
                    start_block = latest_block
                    
                except Exception as e:
                    logger.error(f"Error in liquidation monitoring: {e}")
                    await asyncio.sleep(5)
                    
        except Exception as e:
            logger.error(f"Failed to start liquidation monitoring: {e}")
    
    async def _scan_for_liquidations(self, from_block: int):
        """Scan for liquidation events in recent blocks."""
        try:
            web3 = self.web3_factory.get_web3()
            
            # Get liquidation events
            events = await web3.eth.get_logs({
                'fromBlock': from_block,
                'toBlock': 'latest',
                'topics': [self.liquidation_event_topic]
            })
            
            for event in events:
                await self._process_liquidation_event(event)
                
        except Exception as e:
            logger.error(f"Error scanning for liquidations: {e}")
    
    async def _process_liquidation_event(self, event: LogReceipt):
        """Process a liquidation event and evaluate profitability."""
        try:
            # Parse liquidation event
            liquidation_data = self._parse_liquidation_event(event)
            
            if not liquidation_data:
                return
            
            # Check if liquidation is profitable
            is_profitable = await self._evaluate_liquidation_profitability(liquidation_data)
            
            if is_profitable:
                logger.info(f"Profitable liquidation found: {liquidation_data}")
                
                # Execute liquidation
                await self._execute_liquidation(liquidation_data)
            else:
                logger.debug(f"Unprofitable liquidation: {liquidation_data}")
                
        except Exception as e:
            logger.error(f"Error processing liquidation event: {e}")
    
    def _parse_liquidation_event(self, event: LogReceipt) -> Optional[LiquidationOpportunity]:
        """Parse liquidation event data."""
        try:
            # Decode event data
            # This is a simplified parser - would need proper ABI decoding
            data = event['data']
            topics = event['topics']
            
            # Extract basic information
            borrower = '0x' + topics[1].hex()[-40:]  # Address from topic
            collateral_asset = '0x' + topics[2].hex()[-40:]
            debt_asset = '0x' + topics[3].hex()[-40:]
            
            # Parse amounts (simplified)
            collateral_amount = int(data[:64], 16) / 1e18
            debt_amount = int(data[64:128], 16) / 1e18
            
            # Calculate liquidation bonus
            liquidation_bonus = (collateral_amount - debt_amount) / debt_amount
            
            return LiquidationOpportunity(
                borrower=borrower,
                collateral_asset=collateral_asset,
                debt_asset=debt_asset,
                collateral_amount=collateral_amount,
                debt_amount=debt_amount,
                liquidation_bonus=liquidation_bonus,
                estimated_profit=0,  # Will be calculated later
                block_number=event['blockNumber'],
                timestamp=0  # Will be filled later
            )
            
        except Exception as e:
            logger.error(f"Error parsing liquidation event: {e}")
            return None
    
    async def _evaluate_liquidation_profitability(self, liquidation: LiquidationOpportunity) -> bool:
        """Evaluate if a liquidation is profitable."""
        try:
            # Check minimum bonus requirement
            if liquidation.liquidation_bonus < self.min_liquidation_bonus:
                return False
            
            # Get current gas price
            web3 = self.web3_factory.get_web3()
            gas_price = await web3.eth.gas_price
            gas_price_gwei = gas_price / 1e9
            
            if gas_price_gwei > self.max_gas_price_gwei:
                logger.debug(f"Gas price too high: {gas_price_gwei}gwei")
                return False
            
            # Estimate gas cost for liquidation
            estimated_gas = 500000  # Rough estimate for flash loan + liquidation
            gas_cost_eth = (gas_price * estimated_gas) / 1e18
            
            # Calculate potential profit
            potential_profit = liquidation.collateral_amount - liquidation.debt_amount - gas_cost_eth
            
            if potential_profit < self.min_profit_eth:
                logger.debug(f"Profit too low: {potential_profit:.6f} ETH")
                return False
            
            liquidation.estimated_profit = potential_profit
            
            # Use profit optimizer to validate
            is_profitable = self.profit_optimizer.is_profitable_trade(
                input_amt=liquidation.debt_amount,
                output_amt=liquidation.collateral_amount,
                gas_cost_eth=gas_cost_eth,
                roi_threshold_pct=5.0
            )
            
            return is_profitable
            
        except Exception as e:
            logger.error(f"Error evaluating liquidation profitability: {e}")
            return False
    
    async def _execute_liquidation(self, liquidation: LiquidationOpportunity):
        """Execute a profitable liquidation using flash loans."""
        try:
            logger.info(f"Executing liquidation for {liquidation.borrower}")
            
            # Build liquidation transaction
            liquidation_tx = await self._build_liquidation_transaction(liquidation)
            
            if not liquidation_tx:
                logger.error("Failed to build liquidation transaction")
                return
            
            # Simulate bundle before submission
            bundle = {
                "txs": [liquidation_tx],
                "blockNumber": liquidation.block_number + 1,
                "minTimestamp": 0,
                "maxTimestamp": 0
            }
            
            simulation_result = await self.flashbots_relay.simulate_bundle(bundle)
            
            if not simulation_result.get("success", False):
                logger.warning(f"Liquidation simulation failed: {simulation_result.get('error', 'Unknown error')}")
                return
            
            # Check if still profitable after simulation
            estimated_profit = simulation_result.get("estimated_profit", 0)
            if estimated_profit < self.min_profit_eth:
                logger.info(f"Liquidation no longer profitable after simulation: {estimated_profit:.6f} ETH")
                return
            
            # Submit bundle
            submission_result = await self.flashbots_relay.submit_bundle(
                transactions=[liquidation_tx],
                target_block=liquidation.block_number + 1
            )
            
            if submission_result.get("success", False):
                logger.info(f"Liquidation bundle submitted successfully: {submission_result.get('bundle_hash')}")
                
                # Track liquidation
                self.active_liquidations[liquidation.borrower] = liquidation
                self.liquidation_history.append(liquidation)
                
            else:
                logger.error(f"Failed to submit liquidation bundle: {submission_result.get('error', 'Unknown error')}")
                
        except Exception as e:
            logger.error(f"Error executing liquidation: {e}")
    
    async def _build_liquidation_transaction(self, liquidation: LiquidationOpportunity) -> Optional[str]:
        """Build liquidation transaction using flash loans."""
        try:
            # This is a simplified implementation
            # In practice, you would need to:
            # 1. Build flash loan transaction
            # 2. Build liquidation transaction
            # 3. Build repayment transaction
            # 4. Bundle them together
            
            # For now, return a placeholder
            logger.info(f"Building liquidation transaction for {liquidation.borrower}")
            
            # This would be the actual transaction building logic
            # involving Aave V3 flash loans and liquidation calls
            
            return None  # Placeholder
            
        except Exception as e:
            logger.error(f"Error building liquidation transaction: {e}")
            return None
    
    def get_liquidation_stats(self) -> Dict:
        """Get liquidation statistics."""
        return {
            "active_liquidations": len(self.active_liquidations),
            "total_liquidations": len(self.liquidation_history),
            "total_profit": sum(l.estimated_profit for l in self.liquidation_history),
            "average_profit": sum(l.estimated_profit for l in self.liquidation_history) / max(len(self.liquidation_history), 1)
        } 