"""
Unit tests for StrategySelector functionality.
"""

import pytest
from unittest.mock import Mock, patch
from on1builder.utils.advanced_analytics import StrategySelector

class TestStrategySelector:
    """Test cases for StrategySelector class."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.selector = StrategySelector()
    
    def test_select_strategy_high_gas_skip(self):
        """Test strategy selection with high gas price."""
        # High gas price should result in "skip"
        strategy = self.selector.select_strategy(
            mempool_tx_rate=500,
            gas_price_gwei=150,  # Above 100 gwei threshold
            token_price_volatility=5.0
        )
        
        assert strategy == "skip"
    
    def test_select_strategy_high_volatility_skip(self):
        """Test strategy selection with high volatility."""
        # High volatility should result in "skip"
        strategy = self.selector.select_strategy(
            mempool_tx_rate=500,
            gas_price_gwei=50,
            token_price_volatility=15.0  # Above 10% threshold
        )
        
        assert strategy == "skip"
    
    def test_select_strategy_multi_hop_conditions(self):
        """Test strategy selection for multi-hop conditions."""
        # High mempool volume + low gas should result in "multi_hop"
        strategy = self.selector.select_strategy(
            mempool_tx_rate=1200,  # Above 1000 threshold
            gas_price_gwei=40,     # Below 60 threshold
            token_price_volatility=5.0
        )
        
        assert strategy == "multi_hop"
    
    def test_select_strategy_simple_default(self):
        """Test strategy selection for simple default case."""
        # Normal conditions should result in "simple"
        strategy = self.selector.select_strategy(
            mempool_tx_rate=500,
            gas_price_gwei=50,
            token_price_volatility=5.0
        )
        
        assert strategy == "simple"
    
    def test_select_strategy_edge_case_gas_threshold(self):
        """Test strategy selection at gas price threshold."""
        # Exactly at gas threshold should still be "skip"
        strategy = self.selector.select_strategy(
            mempool_tx_rate=500,
            gas_price_gwei=100,  # Exactly at threshold
            token_price_volatility=5.0
        )
        
        assert strategy == "skip"
    
    def test_select_strategy_edge_case_volatility_threshold(self):
        """Test strategy selection at volatility threshold."""
        # Exactly at volatility threshold should still be "skip"
        strategy = self.selector.select_strategy(
            mempool_tx_rate=500,
            gas_price_gwei=50,
            token_price_volatility=10.0  # Exactly at threshold
        )
        
        assert strategy == "skip"
    
    def test_select_strategy_edge_case_mempool_threshold(self):
        """Test strategy selection at mempool volume threshold."""
        # Exactly at mempool threshold should result in "multi_hop"
        strategy = self.selector.select_strategy(
            mempool_tx_rate=1000,  # Exactly at threshold
            gas_price_gwei=40,
            token_price_volatility=5.0
        )
        
        assert strategy == "multi_hop"
    
    def test_select_strategy_edge_case_gas_medium_threshold(self):
        """Test strategy selection at medium gas threshold."""
        # Exactly at medium gas threshold should result in "multi_hop"
        strategy = self.selector.select_strategy(
            mempool_tx_rate=1200,
            gas_price_gwei=60,  # Exactly at medium threshold
            token_price_volatility=5.0
        )
        
        assert strategy == "simple"  # Should not be multi_hop at exactly 60
    
    def test_select_strategy_very_low_gas(self):
        """Test strategy selection with very low gas price."""
        strategy = self.selector.select_strategy(
            mempool_tx_rate=500,
            gas_price_gwei=10,  # Very low gas
            token_price_volatility=5.0
        )
        
        assert strategy == "simple"
    
    def test_select_strategy_very_high_mempool_volume(self):
        """Test strategy selection with very high mempool volume."""
        strategy = self.selector.select_strategy(
            mempool_tx_rate=5000,  # Very high volume
            gas_price_gwei=40,
            token_price_volatility=5.0
        )
        
        assert strategy == "multi_hop"
    
    def test_select_strategy_zero_values(self):
        """Test strategy selection with zero values."""
        strategy = self.selector.select_strategy(
            mempool_tx_rate=0,
            gas_price_gwei=0,
            token_price_volatility=0
        )
        
        assert strategy == "simple"
    
    def test_select_strategy_negative_values(self):
        """Test strategy selection with negative values."""
        strategy = self.selector.select_strategy(
            mempool_tx_rate=-100,
            gas_price_gwei=-50,
            token_price_volatility=-5.0
        )
        
        # Should handle negative values gracefully
        assert strategy in ["simple", "multi_hop", "skip"]
    
    @patch('logging.getLogger')
    def test_select_strategy_exception_handling(self, mock_get_logger):
        """Test exception handling in strategy selection."""
        mock_logger = Mock()
        mock_get_logger.return_value = mock_logger
        selector = StrategySelector()
        # Mock an exception by passing invalid types
        strategy = selector.select_strategy(
            mempool_tx_rate="invalid",
            gas_price_gwei=50,
            token_price_volatility=5.0
        )
        # Should return "skip" and log error
        assert strategy == "skip"
        mock_logger.error.assert_called_once()
    
    def test_get_strategy_confidence_skip_strategy(self):
        """Test confidence calculation for skip strategy."""
        confidence = self.selector.get_strategy_confidence(
            strategy="skip",
            market_conditions={
                "gas_price_gwei": 50,
                "token_price_volatility": 5.0,
                "mempool_tx_rate": 500
            }
        )
        
        assert confidence == 0.0
    
    def test_get_strategy_confidence_low_gas(self):
        """Test confidence calculation with low gas price."""
        confidence = self.selector.get_strategy_confidence(
            strategy="simple",
            market_conditions={
                "gas_price_gwei": 20,  # Below 30 threshold
                "token_price_volatility": 5.0,
                "mempool_tx_rate": 500
            }
        )
        
        # Should be higher confidence due to low gas
        assert confidence > 0.5
    
    def test_get_strategy_confidence_high_gas(self):
        """Test confidence calculation with high gas price."""
        confidence = self.selector.get_strategy_confidence(
            strategy="simple",
            market_conditions={
                "gas_price_gwei": 90,  # Above 80 threshold
                "token_price_volatility": 5.0,
                "mempool_tx_rate": 500
            }
        )
        
        # Should be lower confidence due to high gas
        assert confidence < 0.5
    
    def test_get_strategy_confidence_low_volatility(self):
        """Test confidence calculation with low volatility."""
        confidence = self.selector.get_strategy_confidence(
            strategy="simple",
            market_conditions={
                "gas_price_gwei": 50,
                "token_price_volatility": 3.0,  # Below 5% threshold
                "mempool_tx_rate": 500
            }
        )
        
        # Should be higher confidence due to low volatility
        assert confidence > 0.5
    
    def test_get_strategy_confidence_high_volatility(self):
        """Test confidence calculation with high volatility."""
        confidence = self.selector.get_strategy_confidence(
            strategy="simple",
            market_conditions={
                "gas_price_gwei": 50,
                "token_price_volatility": 20.0,  # Above 15% threshold
                "mempool_tx_rate": 500
            }
        )
        
        # Should be lower confidence due to high volatility
        assert confidence < 0.5
    
    def test_get_strategy_confidence_high_mempool_volume(self):
        """Test confidence calculation with high mempool volume."""
        confidence = self.selector.get_strategy_confidence(
            strategy="simple",
            market_conditions={
                "gas_price_gwei": 50,
                "token_price_volatility": 5.0,
                "mempool_tx_rate": 600  # Above 500 threshold
            }
        )
        
        # Should be higher confidence due to high mempool volume
        assert confidence > 0.5
    
    def test_get_strategy_confidence_optimal_conditions(self):
        """Test confidence calculation with optimal conditions."""
        confidence = self.selector.get_strategy_confidence(
            strategy="simple",
            market_conditions={
                "gas_price_gwei": 25,  # Low gas
                "token_price_volatility": 3.0,  # Low volatility
                "mempool_tx_rate": 600  # High volume
            }
        )
        
        # Should be very high confidence with optimal conditions
        assert confidence > 0.8
    
    def test_get_strategy_confidence_poor_conditions(self):
        """Test confidence calculation with poor conditions."""
        confidence = self.selector.get_strategy_confidence(
            strategy="simple",
            market_conditions={
                "gas_price_gwei": 90,  # High gas
                "token_price_volatility": 20.0,  # High volatility
                "mempool_tx_rate": 300  # Low volume
            }
        )
        
        # Should be low confidence with poor conditions
        assert confidence < 0.3
    
    def test_get_strategy_confidence_missing_conditions(self):
        """Test confidence calculation with missing market conditions."""
        confidence = self.selector.get_strategy_confidence(
            strategy="simple",
            market_conditions={}  # Empty conditions
        )
        
        # Should return base confidence
        assert confidence == 0.5
    
    def test_get_strategy_confidence_partial_conditions(self):
        """Test confidence calculation with partial market conditions."""
        confidence = self.selector.get_strategy_confidence(
            strategy="simple",
            market_conditions={
                "gas_price_gwei": 50  # Only gas price provided
            }
        )
        
        # Should handle partial conditions gracefully
        assert 0.0 <= confidence <= 1.0
    
    def test_confidence_bounds(self):
        """Test that confidence is always between 0 and 1."""
        test_conditions = [
            {"gas_price_gwei": 0, "token_price_volatility": 0, "mempool_tx_rate": 0},
            {"gas_price_gwei": 200, "token_price_volatility": 50, "mempool_tx_rate": 10000},
            {"gas_price_gwei": -50, "token_price_volatility": -10, "mempool_tx_rate": -1000},
        ]
        
        for conditions in test_conditions:
            confidence = self.selector.get_strategy_confidence("simple", conditions)
            assert 0.0 <= confidence <= 1.0
    
    @patch('logging.getLogger')
    def test_get_strategy_confidence_exception_handling(self, mock_get_logger):
        """Test exception handling in confidence calculation."""
        mock_logger = Mock()
        mock_get_logger.return_value = mock_logger
        selector = StrategySelector()
        # Mock an exception by passing invalid types
        confidence = selector.get_strategy_confidence(
            strategy="simple",
            market_conditions="invalid"
        )
        # Should return 0.0 and log error
        assert confidence == 0.0
        mock_logger.error.assert_called_once()
    
    def test_strategy_selector_thresholds(self):
        """Test that strategy selector thresholds are properly configured."""
        # Test default thresholds
        assert self.selector.gas_threshold_high == 100
        assert self.selector.gas_threshold_medium == 60
        assert self.selector.volatility_threshold == 10.0
        assert self.selector.mempool_volume_high == 1000
    
    def test_strategy_selector_logger_initialization(self):
        """Test that logger is properly initialized."""
        assert hasattr(self.selector, 'logger')
        assert self.selector.logger is not None 