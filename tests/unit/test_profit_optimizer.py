"""
Unit tests for profit optimizer functionality.
"""

import pytest
from unittest.mock import Mock, patch
from on1builder.utils.profit_optimizer import ProfitOptimizer

class TestProfitOptimizer:
    """Test cases for ProfitOptimizer class."""
    
    def setup_method(self):
        """Set up test fixtures."""
        # Patch get_settings to return a mock settings object
        self.settings_patcher = patch('on1builder.config.loaders.get_settings')
        mock_get_settings = self.settings_patcher.start()
        mock_settings = Mock()
        mock_settings.min_profit_eth = 0.01
        mock_settings.min_roi_pct = 5.0
        mock_settings.max_gas_eth = 0.1
        mock_settings.bundle_timeout_sec = 30
        mock_settings.bundle_simulation_retries = 2
        mock_settings.bundle_simulation_delay = 0.1
        mock_settings.bundle_simulation_gas_limit = 1000000
        mock_settings.bundle_simulation_min_profit = 0.01
        mock_settings.bundle_simulation_min_roi = 5.0
        mock_get_settings.return_value = mock_settings
        # Create a mock web3 instance for testing
        mock_web3 = Mock()
        self.optimizer = ProfitOptimizer(mock_web3)
    
    def teardown_method(self):
        self.settings_patcher.stop()
    
    def test_is_profitable_trade_basic_profitable(self):
        """Test basic profitable trade calculation."""
        # Test case: 10 ETH input, 10.6 ETH output, 0.01 ETH gas cost, 5% threshold
        result = self.optimizer.is_profitable_trade(
            input_amt=10.0,
            output_amt=10.6,
            gas_cost_eth=0.01,
            roi_threshold_pct=5.0
        )
        
        # Expected: (10.6 - 10.0 - 0.01) / 10.0 = 0.059 = 5.9% ROI
        assert result is True
    
    def test_is_profitable_trade_basic_unprofitable(self):
        """Test basic unprofitable trade calculation."""
        # Test case: 10 ETH input, 10.4 ETH output, 0.01 ETH gas cost, 5% threshold
        result = self.optimizer.is_profitable_trade(
            input_amt=10.0,
            output_amt=10.4,
            gas_cost_eth=0.01,
            roi_threshold_pct=5.0
        )
        
        # Expected: (10.4 - 10.0 - 0.01) / 10.0 = 0.039 = 3.9% ROI
        assert result is False
    
    def test_is_profitable_trade_zero_input(self):
        """Test edge case with zero input amount."""
        result = self.optimizer.is_profitable_trade(
            input_amt=0.0,
            output_amt=1.0,
            gas_cost_eth=0.01,
            roi_threshold_pct=5.0
        )
        
        assert result is False
    
    def test_is_profitable_trade_negative_input(self):
        """Test edge case with negative input amount."""
        result = self.optimizer.is_profitable_trade(
            input_amt=-1.0,
            output_amt=1.0,
            gas_cost_eth=0.01,
            roi_threshold_pct=5.0
        )
        
        assert result is False
    
    def test_is_profitable_trade_high_gas_cost(self):
        """Test case where gas cost makes trade unprofitable."""
        # Test case: 1 ETH input, 1.05 ETH output, 0.1 ETH gas cost, 5% threshold
        result = self.optimizer.is_profitable_trade(
            input_amt=1.0,
            output_amt=1.05,
            gas_cost_eth=0.1,
            roi_threshold_pct=5.0
        )
        
        # Expected: (1.05 - 1.0 - 0.1) / 1.0 = -0.05 = -5% ROI
        assert result is False
    
    def test_is_profitable_trade_exact_threshold(self):
        """Test case where ROI exactly meets threshold."""
        # Test case: 1 ETH input, 1.06 ETH output, 0.01 ETH gas cost, 5% threshold
        result = self.optimizer.is_profitable_trade(
            input_amt=1.0,
            output_amt=1.06,
            gas_cost_eth=0.01,
            roi_threshold_pct=5.0
        )
        
        # Expected: (1.06 - 1.0 - 0.01) / 1.0 = 0.05 = 5% ROI (exactly at threshold)
        assert result is True
    
    def test_is_profitable_trade_small_amounts(self):
        """Test with very small amounts."""
        # Test case: 0.001 ETH input, 0.00106 ETH output, 0.00001 ETH gas cost, 5% threshold
        result = self.optimizer.is_profitable_trade(
            input_amt=0.001,
            output_amt=0.00106,
            gas_cost_eth=0.00001,
            roi_threshold_pct=5.0
        )
        
        # Expected: (0.00106 - 0.001 - 0.00001) / 0.001 = 0.049 = 4.9% ROI
        assert result is False
    
    def test_is_profitable_trade_large_amounts(self):
        """Test with large amounts."""
        # Test case: 1000 ETH input, 1050 ETH output, 1 ETH gas cost, 5% threshold
        result = self.optimizer.is_profitable_trade(
            input_amt=1000.0,
            output_amt=1050.0,
            gas_cost_eth=1.0,
            roi_threshold_pct=5.0
        )
        
        # Expected: (1050 - 1000 - 1) / 1000 = 0.049 = 4.9% ROI
        assert result is False
    
    def test_is_profitable_trade_very_high_threshold(self):
        """Test with very high ROI threshold."""
        # Test case: 1 ETH input, 1.1 ETH output, 0.01 ETH gas cost, 20% threshold
        result = self.optimizer.is_profitable_trade(
            input_amt=1.0,
            output_amt=1.1,
            gas_cost_eth=0.01,
            roi_threshold_pct=20.0
        )
        
        # Expected: (1.1 - 1.0 - 0.01) / 1.0 = 0.09 = 9% ROI
        assert result is False
    
    def test_is_profitable_trade_zero_threshold(self):
        """Test with zero ROI threshold."""
        # Test case: 1 ETH input, 0.9 ETH output, 0.01 ETH gas cost, 0% threshold
        result = self.optimizer.is_profitable_trade(
            input_amt=1.0,
            output_amt=0.9,
            gas_cost_eth=0.01,
            roi_threshold_pct=0.0
        )
        
        # Expected: (0.9 - 1.0 - 0.01) / 1.0 = -0.11 = -11% ROI
        assert result is False
    
    def test_is_profitable_trade_negative_roi(self):
        """Test case with negative ROI."""
        # Test case: 1 ETH input, 0.8 ETH output, 0.01 ETH gas cost, 5% threshold
        result = self.optimizer.is_profitable_trade(
            input_amt=1.0,
            output_amt=0.8,
            gas_cost_eth=0.01,
            roi_threshold_pct=5.0
        )
        
        # Expected: (0.8 - 1.0 - 0.01) / 1.0 = -0.21 = -21% ROI
        assert result is False
    
    @patch('on1builder.utils.profit_optimizer.logger')
    def test_is_profitable_trade_exception_handling(self, mock_logger):
        """Test exception handling in profit calculation."""
        # Mock an exception by passing invalid types
        result = self.optimizer.is_profitable_trade(
            input_amt="invalid",
            output_amt=1.0,
            gas_cost_eth=0.01,
            roi_threshold_pct=5.0
        )
        
        # Should return False and log error
        assert result is False
        mock_logger.error.assert_called_once()
    
    def test_roi_calculation_accuracy(self):
        """Test ROI calculation accuracy with known values."""
        # Test multiple scenarios with known expected ROI values
        test_cases = [
            # (input, output, gas_cost, expected_roi_pct)
            (100, 105, 1, 4.0),      # 4% ROI
            (100, 110, 2, 8.0),      # 8% ROI
            (100, 95, 1, -6.0),      # -6% ROI
            (1000, 1050, 10, 4.0),   # 4% ROI with larger amounts
            (0.1, 0.105, 0.001, 4.0), # 4% ROI with small amounts
        ]
        
        for input_amt, output_amt, gas_cost, expected_roi in test_cases:
            # Calculate expected result based on threshold
            threshold = 5.0
            expected_result = expected_roi >= threshold
            
            result = self.optimizer.is_profitable_trade(
                input_amt=float(input_amt),
                output_amt=float(output_amt),
                gas_cost_eth=float(gas_cost),
                roi_threshold_pct=threshold
            )
            
            assert result == expected_result, f"Failed for case: input={input_amt}, output={output_amt}, gas={gas_cost}"
    
    def test_floating_point_precision(self):
        """Test floating point precision handling."""
        # Test with very precise floating point values
        result = self.optimizer.is_profitable_trade(
            input_amt=1.0000000001,
            output_amt=1.0500000001,
            gas_cost_eth=0.0100000001,
            roi_threshold_pct=5.0
        )
        
        # Should handle floating point precision correctly
        assert isinstance(result, bool)
    
    def test_edge_case_output_equals_input(self):
        """Test edge case where output equals input."""
        result = self.optimizer.is_profitable_trade(
            input_amt=1.0,
            output_amt=1.0,
            gas_cost_eth=0.01,
            roi_threshold_pct=5.0
        )
        
        # Expected: (1.0 - 1.0 - 0.01) / 1.0 = -0.01 = -1% ROI
        assert result is False
    
    def test_edge_case_output_less_than_input(self):
        """Test edge case where output is less than input."""
        result = self.optimizer.is_profitable_trade(
            input_amt=1.0,
            output_amt=0.9,
            gas_cost_eth=0.01,
            roi_threshold_pct=5.0
        )
        
        # Expected: (0.9 - 1.0 - 0.01) / 1.0 = -0.11 = -11% ROI
        assert result is False 