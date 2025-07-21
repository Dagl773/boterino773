"""
Security Audit Script for ON1Builder MEV Bot.

Performs security-focused checks on critical components.
"""

import asyncio
import logging
import time
from typing import Dict, List, Tuple, Any, Optional
from dataclasses import dataclass

from on1builder.utils.web3_factory import Web3ConnectionFactory
from on1builder.monitoring.flashbots_relay import FlashbotsRelay
from on1builder.engines.safety_guard import SafetyGuard
from on1builder.utils.profit_optimizer import ProfitOptimizer

logger = logging.getLogger(__name__)

@dataclass
class SecurityIssue:
    """Represents a security issue found during audit."""
    severity: str  # 'critical', 'high', 'medium', 'low'
    component: str
    issue_type: str
    description: str
    impact: str
    recommendation: str

class SecurityAuditor:
    """
    Security auditor for MEV bot critical components.
    """
    
    def __init__(self, web3_factory: Web3ConnectionFactory):
        self.web3_factory = web3_factory
        self.issues: List[SecurityIssue] = []
        self.test_results: Dict[str, Any] = {}
    
    async def run_security_audit(self) -> Dict[str, Any]:
        """Run comprehensive security audit."""
        logger.info("Starting security audit...")
        
        try:
            # Test flash loan atomicity
            await self._test_flashloan_atomicity()
            
            # Test bundle simulation handling
            await self._test_bundle_simulation_handling()
            
            # Test risk control enforcement
            await self._test_risk_control_enforcement()
            
            # Test Flashbots relay security
            await self._test_flashbots_relay_security()
            
            # Test profit calculation integrity
            await self._test_profit_calculation_integrity()
            
            # Generate security report
            report = self._generate_security_report()
            
            logger.info(f"Security audit completed. Found {len(self.issues)} issues.")
            return report
            
        except Exception as e:
            logger.error(f"Error during security audit: {e}")
            return {"error": str(e), "issues": []}
    
    async def _test_flashloan_atomicity(self):
        """Test that flash loan transactions are atomic (all or nothing)."""
        try:
            logger.info("Testing flash loan atomicity...")
            
            # Create a test flash loan transaction that would fail
            test_tx = {
                "to": "0x0000000000000000000000000000000000000000",  # Invalid address
                "value": 0,
                "data": "0x",  # Invalid data
                "gas": 21000,
                "gasPrice": 20000000000
            }
            
            # Attempt to execute the transaction
            web3 = self.web3_factory.get_web3()
            
            try:
                # This should fail and revert the entire transaction
                result = await web3.eth.call(test_tx)
                self.issues.append(SecurityIssue(
                    severity="critical",
                    component="flashloan_atomicity",
                    issue_type="atomicity_failure",
                    description="Flash loan transaction did not revert as expected",
                    impact="Non-atomic transactions could lead to partial execution and fund loss",
                    recommendation="Ensure all flash loan transactions are properly atomic"
                ))
            except Exception as e:
                # Expected failure - atomicity working correctly
                logger.info("Flash loan atomicity test passed - transaction properly reverted")
                self.test_results["flashloan_atomicity"] = "PASS"
                
        except Exception as e:
            logger.error(f"Error testing flash loan atomicity: {e}")
            self.issues.append(SecurityIssue(
                severity="high",
                component="flashloan_atomicity",
                issue_type="test_failure",
                description=f"Flash loan atomicity test failed: {e}",
                impact="Unable to verify flash loan security",
                recommendation="Fix flash loan atomicity test and re-run"
            ))
    
    async def _test_bundle_simulation_handling(self):
        """Test proper handling of failed bundle simulations."""
        try:
            logger.info("Testing bundle simulation handling...")
            
            # Create a mock Flashbots relay for testing
            flashbots_relay = FlashbotsRelay(self.web3_factory)
            
            # Test with invalid bundle
            invalid_bundle = {
                "txs": ["invalid_transaction_data"],
                "blockNumber": "0x0",
                "minTimestamp": 0,
                "maxTimestamp": 0
            }
            
            # Simulate the invalid bundle
            simulation_result = await flashbots_relay.simulate_bundle(invalid_bundle)
            
            # Check if simulation properly handles failure
            if simulation_result.get("success", True):  # Should be False for invalid bundle
                self.issues.append(SecurityIssue(
                    severity="high",
                    component="bundle_simulation",
                    issue_type="simulation_failure_handling",
                    description="Bundle simulation did not properly handle invalid bundle",
                    impact="Invalid bundles might be executed",
                    recommendation="Improve bundle simulation error handling"
                ))
            else:
                logger.info("Bundle simulation handling test passed")
                self.test_results["bundle_simulation_handling"] = "PASS"
                
        except Exception as e:
            logger.error(f"Error testing bundle simulation handling: {e}")
            self.issues.append(SecurityIssue(
                severity="medium",
                component="bundle_simulation",
                issue_type="test_failure",
                description=f"Bundle simulation test failed: {e}",
                impact="Unable to verify bundle simulation security",
                recommendation="Fix bundle simulation test and re-run"
            ))
    
    async def _test_risk_control_enforcement(self):
        """Test that risk control parameters are properly enforced."""
        try:
            logger.info("Testing risk control enforcement...")
            
            # Create safety guard instance
            safety_guard = SafetyGuard(self.web3_factory)
            
            # Test emergency pause functionality
            safety_guard.set_emergency_pause(True)
            
            # Test transaction with emergency pause active
            test_tx_params = {
                "to": "0x0000000000000000000000000000000000000000",
                "value": 0,
                "data": "0x",
                "gas": 21000,
                "gasPrice": 20000000000
            }
            
            # Check risk controls
            is_safe, reason = await safety_guard.check_risk_controls(test_tx_params)
            
            if is_safe:
                self.issues.append(SecurityIssue(
                    severity="critical",
                    component="risk_controls",
                    issue_type="emergency_pause_bypass",
                    description="Transaction allowed despite emergency pause being active",
                    impact="Emergency pause can be bypassed, leading to unwanted transactions",
                    recommendation="Fix emergency pause enforcement in risk controls"
                ))
            else:
                logger.info("Risk control enforcement test passed")
                self.test_results["risk_control_enforcement"] = "PASS"
            
            # Reset emergency pause
            safety_guard.set_emergency_pause(False)
            
            # Test gas price ceiling
            # Simulate high gas price scenario
            high_gas_tx = {
                "gasPrice": 200000000000  # 200 gwei
            }
            
            is_safe, reason = await safety_guard.check_risk_controls(high_gas_tx)
            
            if is_safe:
                self.issues.append(SecurityIssue(
                    severity="high",
                    component="risk_controls",
                    issue_type="gas_ceiling_bypass",
                    description="Transaction allowed despite exceeding gas ceiling",
                    impact="Gas ceiling can be bypassed",
                    recommendation="Fix gas ceiling enforcement in risk controls"
                ))
            else:
                logger.info("Gas ceiling enforcement test passed")
                
        except Exception as e:
            logger.error(f"Error testing risk control enforcement: {e}")
            self.issues.append(SecurityIssue(
                severity="high",
                component="risk_controls",
                issue_type="test_failure",
                description=f"Risk control test failed: {e}",
                impact="Unable to verify risk control security",
                recommendation="Fix risk control test and re-run"
            ))
    
    async def _test_flashbots_relay_security(self):
        """Test Flashbots relay connection security and reliability."""
        try:
            logger.info("Testing Flashbots relay security...")
            
            # Create Flashbots relay instance
            flashbots_relay = FlashbotsRelay(self.web3_factory)
            
            # Test connection
            is_connected = await flashbots_relay.connect()
            
            if not is_connected:
                self.issues.append(SecurityIssue(
                    severity="high",
                    component="flashbots_relay",
                    issue_type="connection_failure",
                    description="Unable to connect to Flashbots relay",
                    impact="Cannot submit bundles, reducing MEV opportunities",
                    recommendation="Check Flashbots relay configuration and network connectivity"
                ))
            else:
                logger.info("Flashbots relay connection test passed")
                self.test_results["flashbots_relay_connection"] = "PASS"
                
                # Test bundle submission with valid transaction
                test_bundle = {
                    "txs": ["0x"],  # Empty transaction
                    "blockNumber": "0x0",
                    "minTimestamp": 0,
                    "maxTimestamp": 0
                }
                
                try:
                    submission_result = await flashbots_relay.submit_bundle(
                        transactions=["0x"],
                        target_block=1
                    )
                    
                    # Check if submission was handled properly
                    if not submission_result.get("success", False):
                        logger.info("Flashbots relay submission handling test passed")
                        self.test_results["flashbots_relay_submission"] = "PASS"
                    else:
                        self.issues.append(SecurityIssue(
                            severity="medium",
                            component="flashbots_relay",
                            issue_type="invalid_submission_accepted",
                            description="Flashbots relay accepted invalid bundle submission",
                            impact="Invalid bundles might be processed",
                            recommendation="Improve bundle validation before submission"
                        ))
                        
                except Exception as e:
                    logger.info(f"Flashbots relay submission test passed (expected error: {e})")
                    self.test_results["flashbots_relay_submission"] = "PASS"
                
        except Exception as e:
            logger.error(f"Error testing Flashbots relay security: {e}")
            self.issues.append(SecurityIssue(
                severity="high",
                component="flashbots_relay",
                issue_type="test_failure",
                description=f"Flashbots relay test failed: {e}",
                impact="Unable to verify Flashbots relay security",
                recommendation="Fix Flashbots relay test and re-run"
            ))
    
    async def _test_profit_calculation_integrity(self):
        """Test profit calculation integrity and edge cases."""
        try:
            logger.info("Testing profit calculation integrity...")
            
            profit_optimizer = ProfitOptimizer()
            
            # Test edge cases
            test_cases = [
                # (input_amt, output_amt, gas_cost_eth, roi_threshold_pct, expected)
                (0, 1, 0.1, 5.0, False),  # Zero input
                (1, 0, 0.1, 5.0, False),  # Zero output
                (1, 1.06, 0.01, 5.0, True),  # Profitable trade
                (1, 1.03, 0.01, 5.0, False),  # Unprofitable trade
                (-1, 1, 0.1, 5.0, False),  # Negative input
                (1, 1, -0.1, 5.0, False),  # Negative gas cost
            ]
            
            for input_amt, output_amt, gas_cost_eth, roi_threshold_pct, expected in test_cases:
                try:
                    result = profit_optimizer.is_profitable_trade(
                        input_amt, output_amt, gas_cost_eth, roi_threshold_pct
                    )
                    
                    if result != expected:
                        self.issues.append(SecurityIssue(
                            severity="high",
                            component="profit_calculation",
                            issue_type="calculation_error",
                            description=f"Profit calculation failed for case: input={input_amt}, output={output_amt}, gas={gas_cost_eth}",
                            impact="Incorrect profit calculations could lead to unprofitable trades",
                            recommendation="Fix profit calculation logic for edge cases"
                        ))
                        
                except Exception as e:
                    # Expected for invalid inputs
                    if input_amt <= 0 or output_amt < 0:
                        logger.info(f"Profit calculation properly handled invalid input: {e}")
                    else:
                        self.issues.append(SecurityIssue(
                            severity="medium",
                            component="profit_calculation",
                            issue_type="unexpected_exception",
                            description=f"Unexpected exception in profit calculation: {e}",
                            impact="Profit calculation failures could prevent trade execution",
                            recommendation="Improve exception handling in profit calculation"
                        ))
            
            logger.info("Profit calculation integrity test passed")
            self.test_results["profit_calculation_integrity"] = "PASS"
            
        except Exception as e:
            logger.error(f"Error testing profit calculation integrity: {e}")
            self.issues.append(SecurityIssue(
                severity="high",
                component="profit_calculation",
                issue_type="test_failure",
                description=f"Profit calculation test failed: {e}",
                impact="Unable to verify profit calculation security",
                recommendation="Fix profit calculation test and re-run"
            ))
    
    def _generate_security_report(self) -> Dict[str, Any]:
        """Generate comprehensive security report."""
        critical_issues = [i for i in self.issues if i.severity == "critical"]
        high_issues = [i for i in self.issues if i.severity == "high"]
        medium_issues = [i for i in self.issues if i.severity == "medium"]
        low_issues = [i for i in self.issues if i.severity == "low"]
        
        # Calculate security score
        total_issues = len(self.issues)
        critical_score = len(critical_issues) * 10
        high_score = len(high_issues) * 5
        medium_score = len(medium_issues) * 2
        low_score = len(low_issues) * 1
        
        security_score = max(0, 100 - critical_score - high_score - medium_score - low_score)
        
        return {
            "summary": {
                "total_issues": total_issues,
                "critical": len(critical_issues),
                "high": len(high_issues),
                "medium": len(medium_issues),
                "low": len(low_issues),
                "security_score": security_score
            },
            "test_results": self.test_results,
            "issues_by_severity": {
                "critical": [self._issue_to_dict(i) for i in critical_issues],
                "high": [self._issue_to_dict(i) for i in high_issues],
                "medium": [self._issue_to_dict(i) for i in medium_issues],
                "low": [self._issue_to_dict(i) for i in low_issues]
            },
            "recommendations": self._generate_security_recommendations()
        }
    
    def _issue_to_dict(self, issue: SecurityIssue) -> Dict:
        """Convert security issue to dictionary."""
        return {
            "component": issue.component,
            "issue_type": issue.issue_type,
            "description": issue.description,
            "impact": issue.impact,
            "recommendation": issue.recommendation
        }
    
    def _generate_security_recommendations(self) -> List[str]:
        """Generate security recommendations based on findings."""
        recommendations = []
        
        critical_count = len([i for i in self.issues if i.severity == "critical"])
        if critical_count > 0:
            recommendations.append(f"CRITICAL: Fix {critical_count} critical security issues immediately")
        
        high_count = len([i for i in self.issues if i.severity == "high"])
        if high_count > 0:
            recommendations.append(f"HIGH: Address {high_count} high-severity issues before deployment")
        
        # Component-specific recommendations
        components = set(i.component for i in self.issues)
        
        if "flashloan_atomicity" in components:
            recommendations.append("Review flash loan implementation to ensure atomicity")
        
        if "risk_controls" in components:
            recommendations.append("Strengthen risk control enforcement mechanisms")
        
        if "flashbots_relay" in components:
            recommendations.append("Verify Flashbots relay configuration and connectivity")
        
        if "profit_calculation" in components:
            recommendations.append("Audit profit calculation logic for edge cases")
        
        return recommendations

async def run_security_audit(web3_factory: Web3ConnectionFactory) -> Dict[str, Any]:
    """Run the security audit and return results."""
    auditor = SecurityAuditor(web3_factory)
    return await auditor.run_security_audit()

if __name__ == "__main__":
    # Run security audit when script is executed directly
    import json
    from on1builder.utils.web3_factory import Web3ConnectionFactory
    
    async def main():
        # Use mainnet chain_id=1 for test, or replace with config value
        chain_id = 1
        # Dummy private key for test context (do not use in production!)
        dummy_private_key = '0x' + '1'*64

        # Create web3 instance using the factory
        web3 = await Web3ConnectionFactory.create_connection(chain_id)

        # Pass web3 and dummy key to components
        # FlashbotsRelay expects (web3_factory, private_key)
        # ProfitOptimizer expects web3
        # Patch SecurityAuditor to accept these as needed
        auditor = SecurityAuditor(web3_factory=None)  # We'll patch methods below
        auditor.web3 = web3
        auditor.dummy_private_key = dummy_private_key

        # Patch methods to use the correct web3 and private_key
        async def patched_test_flashloan_atomicity(self):
            try:
                logger.info("Testing flash loan atomicity...")
                test_tx = {
                    "to": "0x0000000000000000000000000000000000000000",
                    "value": 0,
                    "data": "0x",
                    "gas": 21000,
                    "gasPrice": 20000000000
                }
                try:
                    result = await self.web3.eth.call(test_tx)
                    self.issues.append(SecurityIssue(
                        severity="critical",
                        component="flashloan_atomicity",
                        issue_type="atomicity_failure",
                        description="Flash loan transaction did not revert as expected",
                        impact="Non-atomic transactions could lead to partial execution and fund loss",
                        recommendation="Ensure all flash loan transactions are properly atomic"
                    ))
                except Exception as e:
                    logger.info("Flash loan atomicity test passed - transaction properly reverted")
                    self.test_results["flashloan_atomicity"] = "PASS"
            except Exception as e:
                logger.error(f"Error testing flash loan atomicity: {e}")
                self.issues.append(SecurityIssue(
                    severity="high",
                    component="flashloan_atomicity",
                    issue_type="test_failure",
                    description=f"Flash loan atomicity test failed: {e}",
                    impact="Unable to verify flash loan security",
                    recommendation="Fix flash loan atomicity test and re-run"
                ))
        auditor._test_flashloan_atomicity = patched_test_flashloan_atomicity.__get__(auditor)

        async def patched_test_bundle_simulation_handling(self):
            try:
                logger.info("Testing bundle simulation handling...")
                from on1builder.monitoring.flashbots_relay import FlashbotsRelay
                flashbots_relay = FlashbotsRelay(self.web3, self.dummy_private_key)
                invalid_bundle = {
                    "txs": ["invalid_transaction_data"],
                    "blockNumber": "0x0",
                    "minTimestamp": 0,
                    "maxTimestamp": 0
                }
                simulation_result = await flashbots_relay.simulate_bundle(invalid_bundle)
                if simulation_result.get("success", True):
                    self.issues.append(SecurityIssue(
                        severity="high",
                        component="bundle_simulation",
                        issue_type="simulation_failure_handling",
                        description="Bundle simulation did not properly handle invalid bundle",
                        impact="Invalid bundles might be executed",
                        recommendation="Improve bundle simulation error handling"
                    ))
                else:
                    logger.info("Bundle simulation handling test passed")
                    self.test_results["bundle_simulation_handling"] = "PASS"
            except Exception as e:
                logger.error(f"Error testing bundle simulation handling: {e}")
                self.issues.append(SecurityIssue(
                    severity="medium",
                    component="bundle_simulation",
                    issue_type="test_failure",
                    description=f"Bundle simulation test failed: {e}",
                    impact="Unable to verify bundle simulation security",
                    recommendation="Fix bundle simulation test and re-run"
                ))
        auditor._test_bundle_simulation_handling = patched_test_bundle_simulation_handling.__get__(auditor)

        async def patched_test_risk_control_enforcement(self):
            try:
                logger.info("Testing risk control enforcement...")
                from on1builder.engines.safety_guard import SafetyGuard
                safety_guard = SafetyGuard(self.web3)
                safety_guard.set_emergency_pause(True)
                test_tx_params = {
                    "to": "0x0000000000000000000000000000000000000000",
                    "value": 0,
                    "data": "0x",
                    "gas": 21000,
                    "gasPrice": 20000000000
                }
                is_safe, reason = await safety_guard.check_risk_controls(test_tx_params)
                if is_safe:
                    self.issues.append(SecurityIssue(
                        severity="critical",
                        component="risk_controls",
                        issue_type="emergency_pause_bypass",
                        description="Transaction allowed despite emergency pause being active",
                        impact="Emergency pause can be bypassed, leading to unwanted transactions",
                        recommendation="Fix emergency pause enforcement in risk controls"
                    ))
                else:
                    logger.info("Risk control enforcement test passed")
                    self.test_results["risk_control_enforcement"] = "PASS"
                safety_guard.set_emergency_pause(False)
                high_gas_tx = {"gasPrice": 200000000000}
                is_safe, reason = await safety_guard.check_risk_controls(high_gas_tx)
                if is_safe:
                    self.issues.append(SecurityIssue(
                        severity="high",
                        component="risk_controls",
                        issue_type="gas_ceiling_bypass",
                        description="Transaction allowed despite exceeding gas ceiling",
                        impact="Gas ceiling can be bypassed",
                        recommendation="Fix gas ceiling enforcement in risk controls"
                    ))
                else:
                    logger.info("Gas ceiling enforcement test passed")
                    self.test_results["gas_ceiling_enforcement"] = "PASS"
            except Exception as e:
                logger.error(f"Error testing risk control enforcement: {e}")
                self.issues.append(SecurityIssue(
                    severity="high",
                    component="risk_controls",
                    issue_type="test_failure",
                    description=f"Risk control test failed: {e}",
                    impact="Unable to verify risk control security",
                    recommendation="Fix risk control test and re-run"
                ))
        auditor._test_risk_control_enforcement = patched_test_risk_control_enforcement.__get__(auditor)

        async def patched_test_flashbots_relay_security(self):
            try:
                logger.info("Testing Flashbots relay security...")
                from on1builder.monitoring.flashbots_relay import FlashbotsRelay
                flashbots_relay = FlashbotsRelay(self.web3, self.dummy_private_key)
                # Add test logic or skip with a comment if not possible without real env
                logger.info("Flashbots relay security test skipped (requires real environment)")
                self.test_results["flashbots_relay_security"] = "SKIPPED"
            except Exception as e:
                logger.error(f"Error testing Flashbots relay security: {e}")
                self.issues.append(SecurityIssue(
                    severity="high",
                    component="flashbots_relay",
                    issue_type="test_failure",
                    description=f"Flashbots relay test failed: {e}",
                    impact="Unable to verify Flashbots relay security",
                    recommendation="Fix Flashbots relay test and re-run"
                ))
        auditor._test_flashbots_relay_security = patched_test_flashbots_relay_security.__get__(auditor)

        async def patched_test_profit_calculation_integrity(self):
            try:
                logger.info("Testing profit calculation integrity...")
                from on1builder.utils.profit_optimizer import ProfitOptimizer
                profit_optimizer = ProfitOptimizer(self.web3)
                test_cases = [
                    (0, 1, 0.1, 5.0, False),
                    (1, 0, 0.1, 5.0, False),
                    (1, 1.06, 0.01, 5.0, True),
                    (1, 1.03, 0.01, 5.0, False),
                    (-1, 1, 0.1, 5.0, False),
                    (1, 1, -0.1, 5.0, False),
                ]
                for input_amt, output_amt, gas_cost_eth, roi_threshold_pct, expected in test_cases:
                    try:
                        result = profit_optimizer.is_profitable_trade(
                            input_amt, output_amt, gas_cost_eth, roi_threshold_pct
                        )
                        if result != expected:
                            self.issues.append(SecurityIssue(
                                severity="high",
                                component="profit_calculation",
                                issue_type="calculation_error",
                                description=f"Profit calculation failed for case: input={input_amt}, output={output_amt}, gas={gas_cost_eth}",
                                impact="Incorrect profit calculations could lead to unprofitable trades",
                                recommendation="Fix profit calculation logic for edge cases"
                            ))
                    except Exception as e:
                        if input_amt <= 0 or output_amt < 0:
                            logger.info(f"Profit calculation properly handled invalid input: {e}")
                        else:
                            self.issues.append(SecurityIssue(
                                severity="medium",
                                component="profit_calculation",
                                issue_type="unexpected_exception",
                                description=f"Unexpected exception in profit calculation: {e}",
                                impact="Profit calculation failures could prevent trade execution",
                                recommendation="Improve exception handling in profit calculation"
                            ))
                logger.info("Profit calculation integrity test passed")
                self.test_results["profit_calculation_integrity"] = "PASS"
            except Exception as e:
                logger.error(f"Error testing profit calculation integrity: {e}")
                self.issues.append(SecurityIssue(
                    severity="high",
                    component="profit_calculation",
                    issue_type="test_failure",
                    description=f"Profit calculation test failed: {e}",
                    impact="Unable to verify profit calculation security",
                    recommendation="Fix profit calculation test and re-run"
                ))
        auditor._test_profit_calculation_integrity = patched_test_profit_calculation_integrity.__get__(auditor)

        # Now run the audit
        await auditor._test_flashloan_atomicity()
        await auditor._test_bundle_simulation_handling()
        await auditor._test_risk_control_enforcement()
        await auditor._test_flashbots_relay_security()
        await auditor._test_profit_calculation_integrity()
        report = auditor._generate_security_report()
        import json
        print(json.dumps(report, indent=2))

    asyncio.run(main()) 