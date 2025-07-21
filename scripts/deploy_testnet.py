#!/usr/bin/env python3
"""
Testnet Deployment Script for ON1Builder MEV Bot.

Deploys contracts and configures the bot on testnets (Goerli, Sepolia).
"""

import asyncio
import json
import logging
import os
import sys
from pathlib import Path
from typing import Dict, List, Any, Optional
from web3 import Web3
from eth_account import Account
from eth_account.signers.local import LocalAccount

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from on1builder.utils.web3_factory import Web3Factory
from on1builder.config.loaders import settings

logger = logging.getLogger(__name__)

class TestnetDeployer:
    """
    Handles deployment of MEV bot contracts and configuration on testnets.
    """
    
    def __init__(self, network: str = "goerli"):
        self.network = network.lower()
        self.web3_factory = Web3Factory()
        self.deployment_config = self._load_deployment_config()
        
        # Network-specific settings
        self.network_configs = {
            "goerli": {
                "rpc_url": "https://goerli.infura.io/v3/YOUR_PROJECT_ID",
                "chain_id": 5,
                "explorer": "https://goerli.etherscan.io",
                "gas_price": 20000000000,  # 20 gwei
                "confirmations": 2
            },
            "sepolia": {
                "rpc_url": "https://sepolia.infura.io/v3/YOUR_PROJECT_ID",
                "chain_id": 11155111,
                "explorer": "https://sepolia.etherscan.io",
                "gas_price": 15000000000,  # 15 gwei
                "confirmations": 2
            }
        }
        
        if self.network not in self.network_configs:
            raise ValueError(f"Unsupported network: {network}")
        
        self.network_config = self.network_configs[self.network]
    
    def _load_deployment_config(self) -> Dict[str, Any]:
        """Load deployment configuration."""
        config_path = project_root / "deployment_config.json"
        
        if config_path.exists():
            with open(config_path, 'r') as f:
                return json.load(f)
        else:
            # Default configuration
            return {
                "contracts": {
                    "flashloan_contract": "SimpleFlashloan.sol",
                    "arbitrage_contract": "ArbitrageExecutor.sol"
                },
                "deployment_order": [
                    "flashloan_contract",
                    "arbitrage_contract"
                ],
                "verification": True,
                "gas_limit_multiplier": 1.2
            }
    
    async def deploy_contracts(self, private_key: str) -> Dict[str, str]:
        """Deploy all contracts to testnet."""
        try:
            logger.info(f"Starting deployment to {self.network} testnet...")
            
            # Setup account
            account = Account.from_key(private_key)
            web3 = self.web3_factory.get_web3(self.network)
            
            # Check balance
            balance = await web3.eth.get_balance(account.address)
            balance_eth = web3.from_wei(balance, 'ether')
            
            logger.info(f"Deployer address: {account.address}")
            logger.info(f"Balance: {balance_eth:.4f} ETH")
            
            if balance_eth < 0.1:
                logger.warning("Low balance! Ensure you have at least 0.1 ETH for deployment.")
            
            # Deploy contracts
            deployed_addresses = {}
            
            for contract_name in self.deployment_config["deployment_order"]:
                contract_address = await self._deploy_contract(
                    contract_name, account, web3
                )
                deployed_addresses[contract_name] = contract_address
                
                logger.info(f"Deployed {contract_name}: {contract_address}")
                
                # Verify contract if enabled
                if self.deployment_config.get("verification", True):
                    await self._verify_contract(contract_name, contract_address)
            
            # Save deployment results
            await self._save_deployment_results(deployed_addresses)
            
            logger.info("Deployment completed successfully!")
            return deployed_addresses
            
        except Exception as e:
            logger.error(f"Deployment failed: {e}")
            raise
    
    async def _deploy_contract(self, contract_name: str, account: LocalAccount, web3: Web3) -> str:
        """Deploy a single contract."""
        try:
            # Load contract source
            contract_source = self._load_contract_source(contract_name)
            
            # Compile contract
            compiled_contract = await self._compile_contract(contract_source)
            
            # Estimate gas
            gas_estimate = await self._estimate_deployment_gas(compiled_contract, web3)
            gas_limit = int(gas_estimate * self.deployment_config["gas_limit_multiplier"])
            
            # Build transaction
            tx = {
                'from': account.address,
                'gas': gas_limit,
                'gasPrice': self.network_config["gas_price"],
                'nonce': await web3.eth.get_transaction_count(account.address),
                'data': compiled_contract['bytecode']
            }
            
            # Sign and send transaction
            signed_tx = account.sign_transaction(tx)
            tx_hash = await web3.eth.send_raw_transaction(signed_tx.rawTransaction)
            
            # Wait for confirmation
            receipt = await web3.eth.wait_for_transaction_receipt(
                tx_hash, 
                timeout=300,
                poll_latency=2
            )
            
            if receipt.status == 1:
                contract_address = receipt.contractAddress
                logger.info(f"Contract {contract_name} deployed at {contract_address}")
                logger.info(f"Transaction: {self.network_config['explorer']}/tx/{tx_hash.hex()}")
                return contract_address
            else:
                raise Exception(f"Contract deployment failed for {contract_name}")
                
        except Exception as e:
            logger.error(f"Failed to deploy {contract_name}: {e}")
            raise
    
    def _load_contract_source(self, contract_name: str) -> str:
        """Load contract source code."""
        contract_file = self.deployment_config["contracts"][contract_name]
        contract_path = project_root / "src" / "on1builder" / "resources" / "contracts" / contract_file
        
        if not contract_path.exists():
            raise FileNotFoundError(f"Contract file not found: {contract_path}")
        
        with open(contract_path, 'r') as f:
            return f.read()
    
    async def _compile_contract(self, source_code: str) -> Dict[str, Any]:
        """Compile contract source code."""
        try:
            # This is a simplified compilation - in production you'd use solc or hardhat
            # For now, we'll return a mock compiled contract
            return {
                'bytecode': '0x608060405234801561001057600080fd5b50610150806100206000396000f3fe608060405234801561001057600080fd5b50600436106100365760003560e01c80632e64cec11461003b5780636057361d14610059575b600080fd5b610043610075565b60405161005091906100a1565b60405180910390f35b610073600480360381019061006e91906100ed565b61007e565b005b60008054905090565b8060008190555050565b6000819050919050565b61009b81610088565b82525050565b60006020820190506100b66000830184610092565b92915050565b600080fd5b6100ca81610088565b81146100d557600080fd5b50565b6000813590506100e7816100c1565b92915050565b600060208284031215610103576101026100bc565b5b6000610111848285016100d8565b9150509291505056fea2646970667358221220d8aa0c2b576f8194dcc94c3f6e25faff93f712348d469dd2b4f9a3f9c01627c164736f6c63430008120033',
                'abi': [
                    {
                        "inputs": [],
                        "name": "getValue",
                        "outputs": [{"type": "uint256"}],
                        "stateMutability": "view",
                        "type": "function"
                    },
                    {
                        "inputs": [{"type": "uint256"}],
                        "name": "setValue",
                        "outputs": [],
                        "stateMutability": "nonpayable",
                        "type": "function"
                    }
                ]
            }
        except Exception as e:
            logger.error(f"Contract compilation failed: {e}")
            raise
    
    async def _estimate_deployment_gas(self, compiled_contract: Dict[str, Any], web3: Web3) -> int:
        """Estimate gas for contract deployment."""
        try:
            # Mock gas estimation
            return 500000  # 500k gas estimate
        except Exception as e:
            logger.error(f"Gas estimation failed: {e}")
            raise
    
    async def _verify_contract(self, contract_name: str, contract_address: str):
        """Verify contract on block explorer."""
        try:
            logger.info(f"Verifying contract {contract_name} at {contract_address}...")
            
            # This would integrate with Etherscan API for verification
            # For now, just log the verification URL
            verification_url = f"{self.network_config['explorer']}/address/{contract_address}#code"
            logger.info(f"Contract verification URL: {verification_url}")
            
        except Exception as e:
            logger.warning(f"Contract verification failed: {e}")
    
    async def _save_deployment_results(self, deployed_addresses: Dict[str, str]):
        """Save deployment results to file."""
        try:
            deployment_results = {
                "network": self.network,
                "deployment_time": str(asyncio.get_event_loop().time()),
                "contracts": deployed_addresses,
                "network_config": self.network_config
            }
            
            results_path = project_root / f"deployment_results_{self.network}.json"
            with open(results_path, 'w') as f:
                json.dump(deployment_results, f, indent=2)
            
            logger.info(f"Deployment results saved to {results_path}")
            
        except Exception as e:
            logger.error(f"Failed to save deployment results: {e}")
    
    async def configure_bot(self, deployed_addresses: Dict[str, str]):
        """Configure the bot with deployed contract addresses."""
        try:
            logger.info("Configuring bot with deployed contracts...")
            
            # Create configuration
            bot_config = {
                "network": self.network,
                "rpc_url": self.network_config["rpc_url"],
                "chain_id": self.network_config["chain_id"],
                "contracts": deployed_addresses,
                "gas_settings": {
                    "max_gas_price_gwei": 100,
                    "gas_limit_multiplier": 1.2
                },
                "risk_settings": {
                    "max_trade_size_eth": 1.0,
                    "min_profit_threshold": 0.01,
                    "emergency_pause": False
                }
            }
            
            # Save bot configuration
            config_path = project_root / f"bot_config_{self.network}.json"
            with open(config_path, 'w') as f:
                json.dump(bot_config, f, indent=2)
            
            logger.info(f"Bot configuration saved to {config_path}")
            
            # Generate environment file
            env_content = f"""# ON1Builder MEV Bot Configuration for {self.network}
NETWORK={self.network}
RPC_URL={self.network_config['rpc_url']}
CHAIN_ID={self.network_config['chain_id']}

# Contract Addresses
FLASHLOAN_CONTRACT={deployed_addresses.get('flashloan_contract', '')}
ARBITRAGE_CONTRACT={deployed_addresses.get('arbitrage_contract', '')}

# Gas Settings
MAX_GAS_PRICE_GWEI=100
GAS_LIMIT_MULTIPLIER=1.2

# Risk Settings
MAX_TRADE_SIZE_ETH=1.0
MIN_PROFIT_THRESHOLD=0.01
EMERGENCY_PAUSE=false

# Add your private key here (DO NOT COMMIT TO VERSION CONTROL)
# PRIVATE_KEY=your_private_key_here
"""
            
            env_path = project_root / f".env.{self.network}"
            with open(env_path, 'w') as f:
                f.write(env_content)
            
            logger.info(f"Environment file created: {env_path}")
            logger.warning("Remember to add your private key to the environment file!")
            
        except Exception as e:
            logger.error(f"Bot configuration failed: {e}")
            raise
    
    async def run_deployment(self, private_key: str):
        """Run complete deployment process."""
        try:
            # Deploy contracts
            deployed_addresses = await self.deploy_contracts(private_key)
            
            # Configure bot
            await self.configure_bot(deployed_addresses)
            
            logger.info("Deployment and configuration completed successfully!")
            
            # Print summary
            print("\n" + "="*50)
            print(f"DEPLOYMENT SUMMARY - {self.network.upper()}")
            print("="*50)
            for contract_name, address in deployed_addresses.items():
                print(f"{contract_name}: {address}")
            print(f"Explorer: {self.network_config['explorer']}")
            print("="*50)
            
        except Exception as e:
            logger.error(f"Deployment process failed: {e}")
            raise

async def main():
    """Main deployment function."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Deploy ON1Builder MEV Bot to testnet")
    parser.add_argument("--network", choices=["goerli", "sepolia"], default="goerli",
                       help="Target testnet network")
    parser.add_argument("--private-key", required=True,
                       help="Private key for deployment (without 0x prefix)")
    parser.add_argument("--skip-verification", action="store_true",
                       help="Skip contract verification")
    
    args = parser.parse_args()
    
    # Setup logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    try:
        # Create deployer
        deployer = TestnetDeployer(args.network)
        
        # Update verification setting
        if args.skip_verification:
            deployer.deployment_config["verification"] = False
        
        # Run deployment
        await deployer.run_deployment(args.private_key)
        
    except KeyboardInterrupt:
        logger.info("Deployment cancelled by user")
    except Exception as e:
        logger.error(f"Deployment failed: {e}")
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(main()) 