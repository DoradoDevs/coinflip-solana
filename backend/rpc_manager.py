"""
RPC Manager with automatic failover and circuit breaker pattern.

CRITICAL: Prevents platform downtime when primary RPC fails.
Automatically switches to backup RPC endpoints.
"""
import logging
import os
import asyncio
from typing import List, Callable, Any
from datetime import datetime, timedelta
from collections import defaultdict
from enum import Enum

logger = logging.getLogger(__name__)


class CircuitState(Enum):
    """Circuit breaker states."""
    CLOSED = "closed"      # Normal operation
    OPEN = "open"          # Too many failures, not trying
    HALF_OPEN = "half_open"  # Testing if service recovered


class RPCEndpoint:
    """RPC endpoint with circuit breaker."""

    def __init__(self, url: str, name: str):
        self.url = url
        self.name = name
        self.failure_count = 0
        self.success_count = 0
        self.total_requests = 0
        self.last_failure_time = None
        self.last_success_time = None
        self.circuit_state = CircuitState.CLOSED

        # Circuit breaker thresholds
        self.failure_threshold = 3  # Open circuit after 3 failures
        self.success_threshold = 2  # Close circuit after 2 successes in half-open
        self.timeout_seconds = 60  # Try again after 60 seconds

    def record_success(self):
        """Record successful request."""
        self.success_count += 1
        self.total_requests += 1
        self.last_success_time = datetime.utcnow()

        # Reset failure count on success
        self.failure_count = 0

        # If in half-open state, check if we can close circuit
        if self.circuit_state == CircuitState.HALF_OPEN:
            if self.success_count >= self.success_threshold:
                logger.info(f"🟢 Circuit CLOSED for {self.name} after {self.success_count} successes")
                self.circuit_state = CircuitState.CLOSED
                self.success_count = 0  # Reset for next time

    def record_failure(self):
        """Record failed request."""
        self.failure_count += 1
        self.total_requests += 1
        self.last_failure_time = datetime.utcnow()

        # Open circuit if threshold exceeded
        if self.failure_count >= self.failure_threshold:
            if self.circuit_state != CircuitState.OPEN:
                logger.error(
                    f"🔴 Circuit OPEN for {self.name} after {self.failure_count} failures. "
                    f"Will retry in {self.timeout_seconds}s"
                )
                self.circuit_state = CircuitState.OPEN

    def should_attempt(self) -> bool:
        """Check if we should attempt request to this endpoint."""
        # Always allow if circuit closed
        if self.circuit_state == CircuitState.CLOSED:
            return True

        # Always allow if half-open (testing recovery)
        if self.circuit_state == CircuitState.HALF_OPEN:
            return True

        # If circuit open, check if timeout expired
        if self.circuit_state == CircuitState.OPEN:
            if self.last_failure_time:
                timeout_expiry = self.last_failure_time + timedelta(seconds=self.timeout_seconds)

                if datetime.utcnow() >= timeout_expiry:
                    logger.info(f"🟡 Circuit HALF-OPEN for {self.name} - testing recovery")
                    self.circuit_state = CircuitState.HALF_OPEN
                    self.success_count = 0
                    return True

            return False

        return True

    def get_status(self) -> dict:
        """Get endpoint status."""
        return {
            "name": self.name,
            "url": self.url[:50] + "..." if len(self.url) > 50 else self.url,
            "circuit_state": self.circuit_state.value,
            "failure_count": self.failure_count,
            "success_count": self.success_count,
            "total_requests": self.total_requests,
            "last_success": self.last_success_time.isoformat() if self.last_success_time else None,
            "last_failure": self.last_failure_time.isoformat() if self.last_failure_time else None,
        }


class RPCManager:
    """Manage multiple RPC endpoints with automatic failover."""

    def __init__(self):
        """Initialize RPC manager with multiple endpoints."""
        self.endpoints: List[RPCEndpoint] = []

        # Load RPC URLs from environment
        primary_rpc = os.getenv("RPC_URL") or os.getenv("HELIUS_RPC_URL")
        backup1_rpc = os.getenv("BACKUP_RPC_URL_1") or os.getenv("QUICKNODE_RPC_URL")
        backup2_rpc = os.getenv("BACKUP_RPC_URL_2")

        if primary_rpc:
            self.endpoints.append(RPCEndpoint(primary_rpc, "Primary (Helius)"))

        if backup1_rpc:
            self.endpoints.append(RPCEndpoint(backup1_rpc, "Backup 1 (QuickNode)"))

        if backup2_rpc:
            self.endpoints.append(RPCEndpoint(backup2_rpc, "Backup 2"))

        # Public fallback (rate limited but always available)
        self.endpoints.append(
            RPCEndpoint("https://api.mainnet-beta.solana.com", "Public Fallback")
        )

        if not self.endpoints:
            raise ValueError("No RPC endpoints configured! Set RPC_URL environment variable.")

        logger.info(f"RPC Manager initialized with {len(self.endpoints)} endpoints:")
        for endpoint in self.endpoints:
            logger.info(f"  - {endpoint.name}: {endpoint.url[:50]}...")

    async def call_with_failover(
        self,
        method: Callable,
        *args,
        max_retries: int = None,
        **kwargs
    ) -> Any:
        """Call RPC method with automatic failover.

        Args:
            method: Async function to call (must accept rpc_url as first arg)
            *args: Arguments to pass to method (after rpc_url)
            max_retries: Maximum number of endpoints to try (default: all)
            **kwargs: Keyword arguments to pass to method

        Returns:
            Result from method call

        Raises:
            Exception: If all endpoints fail
        """
        if max_retries is None:
            max_retries = len(self.endpoints)

        last_error = None
        attempts = 0

        for endpoint in self.endpoints:
            if attempts >= max_retries:
                break

            # Check circuit breaker
            if not endpoint.should_attempt():
                logger.debug(f"Skipping {endpoint.name} - circuit breaker open")
                continue

            attempts += 1

            try:
                logger.debug(f"Attempting RPC call via {endpoint.name}...")

                # Call method with this RPC URL
                result = await method(endpoint.url, *args, **kwargs)

                # Success!
                endpoint.record_success()
                logger.debug(f"✅ RPC call succeeded via {endpoint.name}")

                return result

            except Exception as e:
                last_error = e
                endpoint.record_failure()

                logger.warning(
                    f"❌ RPC call failed via {endpoint.name}: {str(e)[:100]}"
                )

                # Continue to next endpoint
                continue

        # All endpoints failed
        logger.error(
            f"🚨 ALL RPC ENDPOINTS FAILED after {attempts} attempts! "
            f"Last error: {last_error}"
        )

        # Log to audit system
        try:
            from security.audit import audit_logger, AuditEventType, AuditSeverity

            audit_logger.log(
                event_type=AuditEventType.SUSPICIOUS_PATTERN,
                severity=AuditSeverity.CRITICAL,
                details=f"ALL RPC ENDPOINTS FAILED: {last_error}"
            )
        except:
            pass  # Don't fail if audit logging fails

        raise Exception(f"All RPC endpoints failed. Last error: {last_error}")

    def get_status(self) -> dict:
        """Get status of all RPC endpoints."""
        return {
            "total_endpoints": len(self.endpoints),
            "endpoints": [endpoint.get_status() for endpoint in self.endpoints],
            "healthy_endpoints": sum(
                1 for e in self.endpoints if e.circuit_state == CircuitState.CLOSED
            ),
            "failed_endpoints": sum(
                1 for e in self.endpoints if e.circuit_state == CircuitState.OPEN
            ),
        }

    def reset_all_circuits(self):
        """Reset all circuit breakers (for testing/admin)."""
        for endpoint in self.endpoints:
            endpoint.circuit_state = CircuitState.CLOSED
            endpoint.failure_count = 0
            endpoint.success_count = 0

        logger.info("All circuit breakers reset")


# Global RPC manager instance
rpc_manager = RPCManager()


# Helper functions for common RPC operations
async def get_sol_balance_with_failover(wallet_address: str) -> float:
    """Get SOL balance with automatic RPC failover."""
    from game.solana_ops import get_sol_balance

    return await rpc_manager.call_with_failover(
        get_sol_balance,
        wallet_address
    )


async def transfer_sol_with_failover(
    from_secret: str,
    to_pubkey: str,
    amount_sol: float
) -> str:
    """Transfer SOL with automatic RPC failover."""
    from game.solana_ops import transfer_sol

    return await rpc_manager.call_with_failover(
        transfer_sol,
        from_secret,
        to_pubkey,
        amount_sol
    )


async def get_latest_blockhash_with_failover() -> str:
    """Get latest blockhash with automatic RPC failover."""
    from game.solana_ops import get_latest_blockhash

    return await rpc_manager.call_with_failover(
        get_latest_blockhash
    )


async def verify_transaction_with_failover(
    tx_signature: str,
    expected_recipient: str,
    expected_amount: float
) -> bool:
    """Verify transaction with automatic RPC failover."""
    from game.solana_ops import verify_deposit_transaction

    return await rpc_manager.call_with_failover(
        verify_deposit_transaction,
        tx_signature,
        expected_recipient,
        expected_amount
    )


# Health check for monitoring
async def check_rpc_health() -> dict:
    """Check health of all RPC endpoints.

    Returns:
        Dict with health status
    """
    results = []

    for endpoint in rpc_manager.endpoints:
        try:
            # Try simple balance check
            from game.solana_ops import get_sol_balance

            test_wallet = "So11111111111111111111111111111111111111112"  # Wrapped SOL mint
            start_time = datetime.utcnow()

            balance = await get_sol_balance(endpoint.url, test_wallet)

            latency_ms = (datetime.utcnow() - start_time).total_seconds() * 1000

            results.append({
                "endpoint": endpoint.name,
                "status": "healthy",
                "latency_ms": latency_ms,
                "circuit_state": endpoint.circuit_state.value,
            })

        except Exception as e:
            results.append({
                "endpoint": endpoint.name,
                "status": "unhealthy",
                "error": str(e)[:100],
                "circuit_state": endpoint.circuit_state.value,
            })

    return {
        "timestamp": datetime.utcnow().isoformat(),
        "total_endpoints": len(rpc_manager.endpoints),
        "healthy": sum(1 for r in results if r["status"] == "healthy"),
        "unhealthy": sum(1 for r in results if r["status"] == "unhealthy"),
        "results": results,
    }


if __name__ == "__main__":
    # Test RPC failover
    import asyncio

    async def test():
        print("\n🧪 Testing RPC Failover System\n")

        # Test balance check
        print("1. Testing balance check...")
        try:
            balance = await get_sol_balance_with_failover(
                "So11111111111111111111111111111111111111112"
            )
            print(f"   ✅ Balance retrieved: {balance:.6f} SOL\n")
        except Exception as e:
            print(f"   ❌ Failed: {e}\n")

        # Test health check
        print("2. Testing health check...")
        health = await check_rpc_health()
        print(f"   Total endpoints: {health['total_endpoints']}")
        print(f"   Healthy: {health['healthy']}")
        print(f"   Unhealthy: {health['unhealthy']}")

        for result in health['results']:
            status_icon = "✅" if result["status"] == "healthy" else "❌"
            print(f"   {status_icon} {result['endpoint']}: {result['status']}")

        # Show circuit breaker status
        print("\n3. Circuit Breaker Status:")
        status = rpc_manager.get_status()
        for endpoint in status['endpoints']:
            state_icon = {"closed": "🟢", "open": "🔴", "half_open": "🟡"}[endpoint['circuit_state']]
            print(f"   {state_icon} {endpoint['name']}: {endpoint['circuit_state']}")
            print(f"      Requests: {endpoint['total_requests']}, Failures: {endpoint['failure_count']}")

    asyncio.run(test())
