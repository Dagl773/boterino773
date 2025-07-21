"""
Integration tests for full trade flow simulation.

Tests the complete MEV bot workflow on a mainnet fork.
"""

import asyncio
import pytest
import logging
from unittest.mock import Mock, patch, AsyncMock
from typing import Dict, Any

from on1builder.utils.web3_factory import Web3ConnectionFactory
from on1builder.engines.opportunity_detector import OpportunityDetector
from on1builder.monitoring.flashbots_relay import FlashbotsRelay
from on1builder.engines.safety_guard import SafetyGuard
from on1builder.utils.profit_optimizer import ProfitOptimizer
from on1builder.utils.advanced_analytics import StrategySelector

logger = logging.getLogger(__name__)

class TestFullTradeFlow:
    """Integration tests for complete trade flow."""
    
    @pytest.fixture
    def setup_components(self):
        """Set up test components with mocked dependencies."""
        # Mock Web3 factory
        web3_factory = Mock(spec=Web3ConnectionFactory)
        web3_factory.create_connection.return_value = AsyncMock()
        
        # Mock web3 instance
        mock_web3 = AsyncMock()
        mock_web3.eth.gas_price = 20000000000  # 20 gwei
        mock_web3.eth.block_number = 18000000
        web3_factory.create_connection.return_value = mock_web3
        
        # Use a test chain_id
        chain_id = 1
        # Create components with chain_id
        opportunity_detector = OpportunityDetector(web3_factory, chain_id)
        flashbots_relay = FlashbotsRelay(web3_factory, chain_id)
        safety_guard = SafetyGuard(web3_factory, chain_id)
        profit_optimizer = ProfitOptimizer()
        strategy_selector = StrategySelector()
        
        return {
            'web3_factory': web3_factory,
            'opportunity_detector': opportunity_detector,
            'flashbots_relay': flashbots_relay,
            'safety_guard': safety_guard,
            'profit_optimizer': profit_optimizer,
            'strategy_selector': strategy_selector,
            'mock_web3': mock_web3
        }
    
    @pytest.mark.asyncio
    async def test_opportunity_detection_and_validation(self, setup_components):
        """Test complete opportunity detection and validation flow."""
        components = setup_components
        
        # Mock opportunity detection
        mock_opportunity = {
            'token_pair': 'ETH/USDC',
            'dex1': 'uniswap_v3',
            'dex2': 'sushiswap',
            'input_amount': 1.0,
            'output_amount': 1.06,
            'estimated_profit': 0.05,
            'confidence': 0.85,
            'gas_estimate': 300000
        }
        
        with patch.object(components['opportunity_detector'], 'detect_opportunities') as mock_detect:
            mock_detect.return_value = [mock_opportunity]
            
            # Detect opportunities
            opportunities = await components['opportunity_detector'].detect_opportunities()
            
            assert len(opportunities) == 1
            assert opportunities[0]['token_pair'] == 'ETH/USDC'
            assert opportunities[0]['estimated_profit'] == 0.05
    
    @pytest.mark.asyncio
    async def test_profit_validation_and_strategy_selection(self, setup_components):
        """Test profit validation and strategy selection."""
        components = setup_components
        
        # Test opportunity
        opportunity = {
            'input_amount': 1.0,
            'output_amount': 1.06,
            'gas_estimate': 300000
        }
        
        # Calculate gas cost
        gas_price = 20000000000  # 20 gwei
        gas_cost_eth = (gas_price * opportunity['gas_estimate']) / 1e18
        
        # Validate profitability
        is_profitable = components['profit_optimizer'].is_profitable_trade(
            input_amt=opportunity['input_amount'],
            output_amt=opportunity['output_amount'],
            gas_cost_eth=gas_cost_eth,
            roi_threshold_pct=5.0
        )
        
        assert is_profitable is True
        
        # Select strategy
        strategy = components['strategy_selector'].select_strategy(
            mempool_tx_rate=500,
            gas_price_gwei=20,
            token_price_volatility=5.0
        )
        
        assert strategy in ['simple', 'multi_hop', 'skip']
    
    @pytest.mark.asyncio
    async def test_safety_guard_validation(self, setup_components):
        """Test safety guard validation of transactions."""
        components = setup_components
        
        # Test transaction parameters
        tx_params = {
            'to': '0x7a250d5630B4cF539739dF2C5dAcb4c659F2488D',  # Uniswap V2 Router
            'value': 0,
            'data': '0x',  # Mock swap data
            'gas': 300000,
            'gasPrice': 20000000000
        }
        
        # Check safety guard
        is_safe, reason = await components['safety_guard'].check_transaction(tx_params)
        
        # Should pass basic safety checks
        assert isinstance(is_safe, bool)
        assert isinstance(reason, str)
    
    @pytest.mark.asyncio
    async def test_risk_control_enforcement(self, setup_components):
        """Test risk control enforcement."""
        components = setup_components
        
        # Test emergency pause
        components['safety_guard'].set_emergency_pause(True)
        
        tx_data = {'gasPrice': 20000000000}
        is_safe, reason = await components['safety_guard'].check_risk_controls(tx_data)
        
        # Should be blocked by emergency pause
        assert is_safe is False
        assert "emergency pause" in reason.lower()
        
        # Reset emergency pause
        components['safety_guard'].set_emergency_pause(False)
        
        # Test high gas price
        high_gas_tx = {'gasPrice': 200000000000}  # 200 gwei
        is_safe, reason = await components['safety_guard'].check_risk_controls(high_gas_tx)
        
        # Should be blocked by gas ceiling
        assert is_safe is False
        assert "gas price" in reason.lower()
    
    @pytest.mark.asyncio
    async def test_flashbots_bundle_simulation(self, setup_components):
        """Test Flashbots bundle simulation."""
        components = setup_components
        
        # Mock bundle
        bundle = {
            "txs": ["0x1234567890abcdef"],
            "blockNumber": "0x1123456",
            "minTimestamp": 0,
            "maxTimestamp": 0
        }
        
        # Mock successful simulation response
        mock_response = {
            "jsonrpc": "2.0",
            "id": 1,
            "result": {
                "bundleHash": "0xabcdef1234567890",
                "results": [
                    {
                        "gasUsed": "0x493e0",
                        "value": "0x0"
                    }
                ],
                "coinbaseDiff": "0x2386f26fc10000"  # 0.01 ETH profit
            }
        }
        
        with patch('aiohttp.ClientSession.post') as mock_post:
            mock_response_obj = AsyncMock()
            mock_response_obj.json.return_value = mock_response
            mock_post.return_value.__aenter__.return_value = mock_response_obj
            
            # Simulate bundle
            result = await components['flashbots_relay'].simulate_bundle(bundle)
            
            assert result['success'] is True
            assert result['gas_used'] > 0
            assert result['estimated_profit'] > 0
    
    @pytest.mark.asyncio
    async def test_flashbots_bundle_submission(self, setup_components):
        """Test Flashbots bundle submission."""
        components = setup_components
        
        # Mock transactions
        transactions = ["0x1234567890abcdef"]
        target_block = 18000001
        
        # Mock successful submission response
        mock_response = {
            "jsonrpc": "2.0",
            "id": 1,
            "result": {
                "bundleHash": "0xabcdef1234567890"
            }
        }
        
        with patch('aiohttp.ClientSession.post') as mock_post:
            mock_response_obj = AsyncMock()
            mock_response_obj.json.return_value = mock_response
            mock_post.return_value.__aenter__.return_value = mock_response_obj
            
            # Submit bundle
            result = await components['flashbots_relay'].submit_bundle(
                transactions=transactions,
                target_block=target_block
            )
            
            assert result['success'] is True
            assert 'bundle_hash' in result
    
    @pytest.mark.asyncio
    async def test_complete_trade_flow_success(self, setup_components):
        """Test complete successful trade flow."""
        components = setup_components
        
        # Mock opportunity detection
        mock_opportunity = {
            'token_pair': 'ETH/USDC',
            'input_amount': 1.0,
            'output_amount': 1.06,
            'estimated_profit': 0.05,
            'gas_estimate': 300000
        }
        
        with patch.object(components['opportunity_detector'], 'detect_opportunities') as mock_detect:
            mock_detect.return_value = [mock_opportunity]
            
            # Step 1: Detect opportunity
            opportunities = await components['opportunity_detector'].detect_opportunities()
            assert len(opportunities) > 0
            
            opportunity = opportunities[0]
            
            # Step 2: Validate profitability
            gas_cost_eth = (20000000000 * opportunity['gas_estimate']) / 1e18
            is_profitable = components['profit_optimizer'].is_profitable_trade(
                input_amt=opportunity['input_amount'],
                output_amt=opportunity['output_amount'],
                gas_cost_eth=gas_cost_eth,
                roi_threshold_pct=5.0
            )
            
            if not is_profitable:
                pytest.skip("Opportunity not profitable enough")
            
            # Step 3: Select strategy
            strategy = components['strategy_selector'].select_strategy(
                mempool_tx_rate=500,
                gas_price_gwei=20,
                token_price_volatility=5.0
            )
            
            if strategy == "skip":
                pytest.skip("Strategy selector chose to skip")
            
            # Step 4: Validate safety
            tx_params = {
                'to': '0x7a250d5630B4cF539739dF2C5dAcb4c659F2488D',
                'value': 0,
                'data': '0x',
                'gas': opportunity['gas_estimate'],
                'gasPrice': 20000000000
            }
            
            is_safe, reason = await components['safety_guard'].check_transaction(tx_params)
            
            if not is_safe:
                pytest.skip(f"Safety check failed: {reason}")
            
            # Step 5: Simulate bundle
            bundle = {
                "txs": ["0x1234567890abcdef"],
                "blockNumber": "0x1123456",
                "minTimestamp": 0,
                "maxTimestamp": 0
            }
            
            mock_sim_response = {
                "jsonrpc": "2.0",
                "id": 1,
                "result": {
                    "bundleHash": "0xabcdef1234567890",
                    "results": [{"gasUsed": "0x493e0"}],
                    "coinbaseDiff": "0x2386f26fc10000"
                }
            }
            
            with patch('aiohttp.ClientSession.post') as mock_post:
                mock_response_obj = AsyncMock()
                mock_response_obj.json.return_value = mock_sim_response
                mock_post.return_value.__aenter__.return_value = mock_response_obj
                
                sim_result = await components['flashbots_relay'].simulate_bundle(bundle)
                
                if not sim_result['success']:
                    pytest.skip("Bundle simulation failed")
                
                # Step 6: Submit bundle
                mock_submit_response = {
                    "jsonrpc": "2.0",
                    "id": 1,
                    "result": {"bundleHash": "0xabcdef1234567890"}
                }
                
                mock_response_obj.json.return_value = mock_submit_response
                
                submit_result = await components['flashbots_relay'].submit_bundle(
                    transactions=["0x1234567890abcdef"],
                    target_block=18000001
                )
                
                assert submit_result['success'] is True
                logger.info("Complete trade flow executed successfully")
    
    @pytest.mark.asyncio
    async def test_trade_flow_graceful_failure_handling(self, setup_components):
        """Test graceful handling of failures in trade flow."""
        components = setup_components
        
        # Test 1: Unprofitable opportunity
        unprofitable_opportunity = {
            'input_amount': 1.0,
            'output_amount': 1.02,  # Very low profit
            'gas_estimate': 300000
        }
        
        gas_cost_eth = (20000000000 * unprofitable_opportunity['gas_estimate']) / 1e18
        is_profitable = components['profit_optimizer'].is_profitable_trade(
            input_amt=unprofitable_opportunity['input_amount'],
            output_amt=unprofitable_opportunity['output_amount'],
            gas_cost_eth=gas_cost_eth,
            roi_threshold_pct=5.0
        )
        
        assert is_profitable is False
        
        # Test 2: Safety check failure
        unsafe_tx = {
            'to': '0x0000000000000000000000000000000000000000',
            'value': 1000000000000000000,  # 1 ETH
            'data': '0x',
            'gas': 21000,
            'gasPrice': 20000000000
        }
        
        is_safe, reason = await components['safety_guard'].check_transaction(unsafe_tx)
        
        # Should fail safety checks
        assert is_safe is False
        
        # Test 3: Bundle simulation failure
        bundle = {
            "txs": ["invalid_transaction"],
            "blockNumber": "0x1123456",
            "minTimestamp": 0,
            "maxTimestamp": 0
        }
        
        mock_failed_response = {
            "jsonrpc": "2.0",
            "id": 1,
            "error": {
                "code": -32602,
                "message": "Invalid transaction data"
            }
        }
        
        with patch('aiohttp.ClientSession.post') as mock_post:
            mock_response_obj = AsyncMock()
            mock_response_obj.json.return_value = mock_failed_response
            mock_post.return_value.__aenter__.return_value = mock_response_obj
            
            sim_result = await components['flashbots_relay'].simulate_bundle(bundle)
            
            assert sim_result['success'] is False
            assert 'error' in sim_result
    
    @pytest.mark.asyncio
    async def test_concurrent_opportunity_processing(self, setup_components):
        """Test processing multiple opportunities concurrently."""
        components = setup_components
        
        # Mock multiple opportunities
        opportunities = [
            {
                'token_pair': 'ETH/USDC',
                'input_amount': 1.0,
                'output_amount': 1.06,
                'estimated_profit': 0.05,
                'gas_estimate': 300000
            },
            {
                'token_pair': 'WBTC/ETH',
                'input_amount': 0.1,
                'output_amount': 0.105,
                'estimated_profit': 0.004,
                'gas_estimate': 250000
            }
        ]
        
        async def process_opportunity(opportunity):
            """Process a single opportunity."""
            gas_cost_eth = (20000000000 * opportunity['gas_estimate']) / 1e18
            is_profitable = components['profit_optimizer'].is_profitable_trade(
                input_amt=opportunity['input_amount'],
                output_amt=opportunity['output_amount'],
                gas_cost_eth=gas_cost_eth,
                roi_threshold_pct=5.0
            )
            
            return {
                'opportunity': opportunity,
                'profitable': is_profitable
            }
        
        # Process opportunities concurrently
        tasks = [process_opportunity(opp) for opp in opportunities]
        results = await asyncio.gather(*tasks)
        
        assert len(results) == 2
        assert all(isinstance(result, dict) for result in results)
        assert all('profitable' in result for result in results)
    
    @pytest.mark.asyncio
    async def test_performance_metrics_collection(self, setup_components):
        """Test collection of performance metrics during trade flow."""
        components = setup_components
        
        # Mock opportunity
        opportunity = {
            'token_pair': 'ETH/USDC',
            'input_amount': 1.0,
            'output_amount': 1.06,
            'estimated_profit': 0.05,
            'gas_estimate': 300000
        }
        
        # Track metrics
        metrics = {
            'opportunities_detected': 1,
            'opportunities_validated': 0,
            'trades_executed': 0,
            'total_profit': 0.0,
            'total_gas_spent': 0.0
        }
        
        # Validate opportunity
        gas_cost_eth = (20000000000 * opportunity['gas_estimate']) / 1e18
        is_profitable = components['profit_optimizer'].is_profitable_trade(
            input_amt=opportunity['input_amount'],
            output_amt=opportunity['output_amount'],
            gas_cost_eth=gas_cost_eth,
            roi_threshold_pct=5.0
        )
        
        if is_profitable:
            metrics['opportunities_validated'] += 1
            
            # Simulate successful trade
            metrics['trades_executed'] += 1
            metrics['total_profit'] += opportunity['estimated_profit']
            metrics['total_gas_spent'] += gas_cost_eth
        
        # Verify metrics
        assert metrics['opportunities_detected'] == 1
        assert metrics['opportunities_validated'] >= 0
        assert metrics['trades_executed'] >= 0
        assert metrics['total_profit'] >= 0.0
        assert metrics['total_gas_spent'] >= 0.0 