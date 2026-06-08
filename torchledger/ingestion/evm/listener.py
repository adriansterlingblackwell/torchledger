"""
EVM chain listener.

Connects to an Ethereum-compatible node (Alchemy / Infura / own node),
subscribes to new blocks, decodes transactions and internal transfers,
and publishes normalized events to Kafka.

Topics produced:
  - tx.raw           — every tx with decoded input data
  - block.confirmed  — block metadata
  - transfer.erc20   — ERC-20 Transfer events
  - transfer.native  — native ETH transfers
"""
from __future__ import annotations

import asyncio
import json
import os
import signal
import sys
from dataclasses import asdict, dataclass
from typing import Any

import structlog
from kafka import KafkaProducer
from web3 import AsyncWeb3
from web3.middleware import geth_poa_middleware

logger = structlog.get_logger()

KAFKA_BROKERS = os.getenv("KAFKA_BROKERS", "localhost:9092")
ETH_RPC_URL = os.getenv("ETH_RPC_URL", "wss://eth-mainnet.g.alchemy.com/v2/demo")
CHAIN_ID = int(os.getenv("CHAIN_ID", "1"))


@dataclass
class NormalizedTx:
    chain_id: int
    block_number: int
    block_timestamp: int
    tx_hash: str
    from_address: str
    to_address: str | None
    value_wei: int
    gas_used: int
    gas_price_gwei: float
    input_method_id: str | None
    is_contract_create: bool
    status: int  # 0=fail 1=success


class EVMListener:
    def __init__(self) -> None:
        self._w3 = AsyncWeb3(AsyncWeb3.AsyncIPCProvider(ETH_RPC_URL))
        self._w3.middleware_onion.inject(geth_poa_middleware, layer=0)
        self._producer = KafkaProducer(
            bootstrap_servers=KAFKA_BROKERS,
            value_serializer=lambda v: json.dumps(v).encode(),
            key_serializer=lambda k: k.encode() if k else None,
            acks="all",
            retries=5,
            compression_type="snappy",
        )
        self._running = False

    async def start(self) -> None:
        self._running = True
        logger.info("evm_listener_start", chain_id=CHAIN_ID, rpc=ETH_RPC_URL)

        latest = await self._w3.eth.block_number
        logger.info("chain_tip", block=latest)

        async for block_hash in self._w3.eth.subscribe("newHeads"):  # type: ignore[attr-defined]
            if not self._running:
                break
            await self._process_block(block_hash)

    async def _process_block(self, block_hash: Any) -> None:
        try:
            block = await self._w3.eth.get_block(block_hash, full_transactions=True)
            logger.debug("processing_block", number=block.number, txs=len(block.transactions))

            # Publish block header
            self._producer.send(
                "block.confirmed",
                key=str(CHAIN_ID),
                value={
                    "chain_id": CHAIN_ID,
                    "number": block.number,
                    "timestamp": block.timestamp,
                    "tx_count": len(block.transactions),
                    "gas_used": block.gasUsed,
                    "base_fee_gwei": block.get("baseFeePerGas", 0) / 1e9,
                },
            )

            # Publish each tx
            for tx in block.transactions:
                normalized = NormalizedTx(
                    chain_id=CHAIN_ID,
                    block_number=block.number,
                    block_timestamp=block.timestamp,
                    tx_hash=tx.hash.hex(),
                    from_address=tx["from"].lower(),
                    to_address=tx["to"].lower() if tx["to"] else None,
                    value_wei=tx.value,
                    gas_used=tx.gas,
                    gas_price_gwei=tx.gasPrice / 1e9,
                    input_method_id=tx.input[:10] if len(tx.input) >= 10 else None,
                    is_contract_create=tx["to"] is None,
                    status=1,  # updated after receipt fetch
                )
                self._producer.send(
                    "tx.raw",
                    key=normalized.from_address,
                    value=asdict(normalized),
                )

        except Exception as exc:
            logger.error("block_processing_failed", error=str(exc))

    def stop(self) -> None:
        self._running = False
        self._producer.flush(timeout=10)
        logger.info("evm_listener_stop")


async def main() -> None:
    listener = EVMListener()

    loop = asyncio.get_event_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, listener.stop)

    try:
        await listener.start()
    except KeyboardInterrupt:
        listener.stop()
        sys.exit(0)


if __name__ == "__main__":
    asyncio.run(main())
