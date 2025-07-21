# src/on1builder/monitoring/flashbots_relay.py
from __future__ import annotations

import asyncio
import json
import time
from typing import Any, Dict, List, Optional, Tuple
from decimal import Decimal

import aiohttp
from web3 import AsyncWeb3
from eth_account import Account
from eth_account.messages import encode_defunct

from on1builder.config.loaders import settings
from on1builder.utils.logging_config import get_logger
from on1builder.utils.custom_exceptions import FlashbotsError

logger = get_logger(__name__)

class FlashbotsRelay:
    """
    Flashbots relay integration for MEV-Share and private transaction submission.
    Reduces mempool latency and improves execution reliability.
    """
    
    def __init__(self, web3: AsyncWeb3, private_key: str):
        self._web3 = web3
        self._private_key = private_key
        self._account = Account.from_key(private_key)
        self._session: Optional[aiohttp.ClientSession] = None
        
        # Flashbots endpoints
        self._relay_url = "https://relay.flashbots.net"
        self._mev_share_url = "https://mev-share.flashbots.net"
        
        # Performance tracking
        self._submission_stats = {
            "total_submissions": 0,
            "successful_bundles": 0,
            "failed_submissions": 0,
            "avg_latency_ms": 0,
            "total_profit_eth": 0.0
        }
        
        # Bundle tracking
        self._pending_bundles: Dict[str, Dict[str, Any]] = {}
        self._bundle_timeout = 12  # seconds
        
        logger.info("FlashbotsRelay initialized")

    async def start(self):
        """Initialize the Flashbots relay connection."""
        if self._session is None:
            self._session = aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=10),
                headers={
                    "Content-Type": "application/json",
                    "User-Agent": "ON1Builder/2.2.0"
                }
            )
        logger.info("FlashbotsRelay started")

    async def stop(self):
        """Close the Flashbots relay connection."""
        if self._session:
            await self._session.close()
            self._session = None
        logger.info("FlashbotsRelay stopped")

    async def submit_bundle(
        self, 
        transactions: List[Dict[str, Any]], 
        target_block: int,
        min_timestamp: Optional[int] = None,
        max_timestamp: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Submit a bundle to Flashbots relay.
        
        Args:
            transactions: List of signed transactions
            target_block: Target block number
            min_timestamp: Minimum timestamp for inclusion
            max_timestamp: Maximum timestamp for inclusion
            
        Returns:
            Bundle submission result
        """
        try:
            start_time = time.time()
            
            # Prepare bundle
            bundle = {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "eth_sendBundle",
                "params": [{
                    "txs": [tx.rawTransaction.hex() for tx in transactions],
                    "blockNumber": hex(target_block),
                    "minTimestamp": min_timestamp,
                    "maxTimestamp": max_timestamp
                }]
            }
            
            # Submit to Flashbots relay
            async with self._session.post(self._relay_url, json=bundle) as response:
                result = await response.json()
                
                if "error" in result:
                    raise FlashbotsError(f"Flashbots relay error: {result['error']}")
                
                bundle_hash = result.get("result")
                if not bundle_hash:
                    raise FlashbotsError("No bundle hash returned from relay")
                
                # Track bundle
                bundle_id = bundle_hash
                self._pending_bundles[bundle_id] = {
                    "transactions": transactions,
                    "target_block": target_block,
                    "submission_time": start_time,
                    "status": "pending"
                }
                
                # Update stats
                latency = (time.time() - start_time) * 1000
                self._submission_stats["total_submissions"] += 1
                self._submission_stats["avg_latency_ms"] = (
                    self._submission_stats["avg_latency_ms"] * 0.9 + latency * 0.1
                )
                
                logger.info(f"Bundle submitted: {bundle_hash} (latency: {latency:.1f}ms)")
                
                return {
                    "success": True,
                    "bundle_hash": bundle_hash,
                    "latency_ms": latency,
                    "target_block": target_block
                }
                
        except Exception as e:
            self._submission_stats["failed_submissions"] += 1
            logger.error(f"Bundle submission failed: {e}")
            return {
                "success": False,
                "error": str(e),
                "latency_ms": (time.time() - start_time) * 1000 if 'start_time' in locals() else 0
            }

    async def submit_mev_share_bundle(
        self, 
        transactions: List[Dict[str, Any]], 
        target_block: int,
        hints: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Submit a bundle to MEV-Share for better distribution.
        
        Args:
            transactions: List of signed transactions
            target_block: Target block number
            hints: Optional hints for validators
            
        Returns:
            MEV-Share submission result
        """
        try:
            start_time = time.time()
            
            # Prepare MEV-Share bundle
            bundle = {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "mev_sendBundle",
                "params": [{
                    "txs": [tx.rawTransaction.hex() for tx in transactions],
                    "blockNumber": hex(target_block),
                    "minTimestamp": int(time.time()),
                    "maxTimestamp": int(time.time()) + 2,
                    "hints": hints or {}
                }]
            }
            
            # Submit to MEV-Share
            async with self._session.post(self._mev_share_url, json=bundle) as response:
                result = await response.json()
                
                if "error" in result:
                    raise FlashbotsError(f"MEV-Share error: {result['error']}")
                
                bundle_hash = result.get("result")
                if not bundle_hash:
                    raise FlashbotsError("No bundle hash returned from MEV-Share")
                
                latency = (time.time() - start_time) * 1000
                logger.info(f"MEV-Share bundle submitted: {bundle_hash} (latency: {latency:.1f}ms)")
                
                return {
                    "success": True,
                    "bundle_hash": bundle_hash,
                    "latency_ms": latency,
                    "target_block": target_block,
                    "relay": "mev-share"
                }
                
        except Exception as e:
            logger.error(f"MEV-Share bundle submission failed: {e}")
            return {
                "success": False,
                "error": str(e),
                "latency_ms": (time.time() - start_time) * 1000 if 'start_time' in locals() else 0
            }

    async def simulate_bundle(self, bundle: dict) -> dict:
        """
        Simulate a Flashbots bundle before submission.
        
        Args:
            bundle: Bundle to simulate
            
        Returns:
            Simulation result with success status, gas used, and estimated profit
        """
        try:
            if not self._session: # Changed from self.is_connected to self._session
                raise Exception("Flashbots relay not connected")
            
            # Prepare simulation request
            simulation_request = {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "eth_callBundle",
                "params": [
                    bundle,
                    "latest"
                ]
            }
            
            # Send simulation request
            async with aiohttp.ClientSession() as session: # Changed from self._session to aiohttp.ClientSession()
                async with session.post(
                    self._relay_url, # Changed from self.relay_url to self._relay_url
                    json=simulation_request,
                    headers={"Content-Type": "application/json"},
                    timeout=aiohttp.ClientTimeout(total=5)
                ) as response:
                    result = await response.json()
            
            # Parse simulation result
            if "error" in result:
                logger.warning(f"Bundle simulation failed: {result['error']}") # Changed from self.logger to logger
                return {
                    "success": False,
                    "error": result["error"].get("message", "Unknown error"),
                    "gas_used": 0,
                    "estimated_profit": 0
                }
            
            # Extract simulation data
            simulation_data = result.get("result", {})
            
            # Calculate gas used
            gas_used = 0
            if "results" in simulation_data:
                for tx_result in simulation_data["results"]:
                    gas_used += int(tx_result.get("gasUsed", "0x0"), 16)
            
            # Estimate profit (simplified calculation)
            estimated_profit = 0
            if "coinbaseDiff" in simulation_data:
                estimated_profit = int(simulation_data["coinbaseDiff"], 16) / 1e18
            
            success = simulation_data.get("bundleHash") is not None
            
            logger.info(f"Bundle simulation: success={success}, gas_used={gas_used}, profit={estimated_profit:.6f} ETH") # Changed from self.logger to logger
            
            return {
                "success": success,
                "gas_used": gas_used,
                "estimated_profit": estimated_profit,
                "bundle_hash": simulation_data.get("bundleHash")
            }
            
        except Exception as e:
            logger.error(f"Error simulating bundle: {e}") # Changed from self.logger to logger
            return {
                "success": False,
                "error": str(e),
                "gas_used": 0,
                "estimated_profit": 0
            }

    async def get_bundle_status(self, bundle_hash: str) -> Dict[str, Any]:
        """Get the status of a submitted bundle."""
        try:
            # Check if bundle was included
            request = {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "eth_getBundleByHash",
                "params": [bundle_hash]
            }
            
            async with self._session.post(self._relay_url, json=request) as response:
                result = await response.json()
                
                if "error" in result:
                    return {"status": "unknown", "error": result["error"]}
                
                bundle_data = result.get("result")
                if bundle_data:
                    # Bundle was included
                    self._submission_stats["successful_bundles"] += 1
                    return {
                        "status": "included",
                        "block_number": int(bundle_data.get("blockNumber", "0x0"), 16),
                        "bundle_index": bundle_data.get("bundleIndex", 0)
                    }
                else:
                    # Bundle not found (likely not included)
                    return {"status": "not_included"}
                    
        except Exception as e:
            logger.error(f"Error checking bundle status: {e}")
            return {"status": "error", "error": str(e)}

    async def monitor_bundle_inclusion(self, bundle_hash: str, timeout_blocks: int = 2) -> Dict[str, Any]:
        """
        Monitor bundle inclusion for a specified number of blocks.
        
        Args:
            bundle_hash: Bundle hash to monitor
            timeout_blocks: Number of blocks to wait for inclusion
            
        Returns:
            Inclusion result
        """
        start_block = await self._web3.eth.block_number
        
        for _ in range(timeout_blocks):
            await asyncio.sleep(1)  # Wait for next block
            
            status = await self.get_bundle_status(bundle_hash)
            if status.get("status") == "included":
                return {
                    "included": True,
                    "block_number": status.get("block_number"),
                    "bundle_index": status.get("bundle_index"),
                    "blocks_waited": await self._web3.eth.block_number - start_block
                }
        
        return {"included": False, "blocks_waited": timeout_blocks}

    def get_performance_stats(self) -> Dict[str, Any]:
        """Get Flashbots relay performance statistics."""
        success_rate = 0.0
        if self._submission_stats["total_submissions"] > 0:
            success_rate = (
                self._submission_stats["successful_bundles"] / 
                self._submission_stats["total_submissions"] * 100
            )
        
        return {
            **self._submission_stats,
            "success_rate_percentage": success_rate,
            "pending_bundles": len(self._pending_bundles)
        }

    async def cleanup_expired_bundles(self):
        """Clean up expired bundles from tracking."""
        current_time = time.time()
        expired_bundles = []
        
        for bundle_id, bundle_data in self._pending_bundles.items():
            if current_time - bundle_data["submission_time"] > self._bundle_timeout:
                expired_bundles.append(bundle_id)
        
        for bundle_id in expired_bundles:
            del self._pending_bundles[bundle_id]
        
        if expired_bundles:
            logger.info(f"Cleaned up {len(expired_bundles)} expired bundles") 