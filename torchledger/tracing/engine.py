"""
Cross-chain fund flow tracing engine.

Follows:
- EVM → EVM bridge calls (Wormhole, LayerZero, Axelar, Stargate, Hop)
- EVM → Solana via Wormhole
- UTXO clustering heuristics (common input ownership)
- Tornado Cash / Railgun deposit-withdrawal matching

Output: a directed acyclic graph of fund flows across chains.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import structlog

from api.schemas.trace import TraceRequest, TraceResult

logger = structlog.get_logger()

# Known bridge contract addresses (EVM mainnet)
BRIDGE_CONTRACTS: dict[str, str] = {
    "0x3ee18b2214aff97000d974cf647e7c347e8fa585": "Wormhole Token Bridge",
    "0x40a138e4f73af9b225b98ebd500dc04ceeaebe4f": "LayerZero Endpoint",
    "0xe432150cce91c13a887f7d836923d5597add8e31": "Axelar Gateway",
    "0x8731d54e9d02c286767d56ac03e8037c07e01e98": "Stargate Router",
}

MIXER_CONTRACTS: dict[str, str] = {
    "0xd90e2f925da726b50c4ed8d0fb90ad053324f31b": "Tornado Cash 0.1 ETH",
    "0x910cbd523d972eb0a6f4cae4618ad62622b39dbf": "Tornado Cash 1 ETH",
    "0xa160cdab225685da1d56aa342ad8841c3b53f291": "Tornado Cash 10 ETH",
    "0xca0840578f57fe71599d29375e16783424023357": "Railgun",
}


@dataclass
class TraceNode:
    address: str
    chain: str
    hop: int
    is_bridge: bool = False
    is_mixer: bool = False
    entity_name: str | None = None
    risk_score: int = 0


@dataclass
class TraceEdge:
    from_address: str
    to_address: str
    tx_hash: str
    chain: str
    value_usd: float
    timestamp: int
    bridge_protocol: str | None = None


@dataclass
class TraceGraph:
    origin: str
    nodes: list[TraceNode] = field(default_factory=list)
    edges: list[TraceEdge] = field(default_factory=list)
    crossed_chains: list[str] = field(default_factory=list)
    touched_mixer: bool = False
    touched_bridge: bool = False

    def add_node(self, node: TraceNode) -> None:
        if not any(n.address == node.address for n in self.nodes):
            self.nodes.append(node)

    def add_edge(self, edge: TraceEdge) -> None:
        self.edges.append(edge)
        if edge.bridge_protocol:
            self.touched_bridge = True


class TraceEngine:
    """
    Multi-chain fund flow tracer.

    Combines:
     - Graph traversal in Neo4j (for known transaction history)
     - On-demand RPC lookups for missing hops
     - Bridge detection via contract signature matching
     - UTXO common-input heuristic for Bitcoin
    """

    def __init__(self) -> None:
        pass  # inject DB clients in production

    async def trace(
        self,
        origin: str,
        chain: str = "evm",
        max_hops: int = 4,
        follow_bridges: bool = True,
    ) -> TraceResult:
        logger.info("trace_start", origin=origin, chain=chain, max_hops=max_hops)

        graph = TraceGraph(origin=origin)
        await self._bfs_trace(
            graph=graph,
            address=origin,
            chain=chain,
            hop=0,
            max_hops=max_hops,
            follow_bridges=follow_bridges,
            visited=set(),
        )

        logger.info(
            "trace_complete",
            origin=origin,
            nodes=len(graph.nodes),
            edges=len(graph.edges),
            crossed_chains=graph.crossed_chains,
        )

        return TraceResult(
            origin=origin,
            nodes=[self._node_to_dict(n) for n in graph.nodes],
            edges=[self._edge_to_dict(e) for e in graph.edges],
            hop_count=max(n.hop for n in graph.nodes) if graph.nodes else 0,
            crossed_chains=graph.crossed_chains,
            touched_mixer=graph.touched_mixer,
            touched_bridge=graph.touched_bridge,
        )

    async def trace_entity(self, entity_id: str, depth: int = 3) -> TraceResult:
        """Trace all addresses in a cluster."""
        # In production: fetch cluster members from Neo4j, then trace each
        return TraceResult(
            origin=entity_id,
            nodes=[],
            edges=[],
            hop_count=0,
            crossed_chains=[],
            touched_mixer=False,
            touched_bridge=False,
        )

    async def _bfs_trace(
        self,
        graph: TraceGraph,
        address: str,
        chain: str,
        hop: int,
        max_hops: int,
        follow_bridges: bool,
        visited: set[str],
    ) -> None:
        if hop > max_hops or address in visited:
            return
        visited.add(address)

        is_bridge = address.lower() in BRIDGE_CONTRACTS
        is_mixer = address.lower() in MIXER_CONTRACTS
        if is_mixer:
            graph.touched_mixer = True

        graph.add_node(
            TraceNode(
                address=address,
                chain=chain,
                hop=hop,
                is_bridge=is_bridge,
                is_mixer=is_mixer,
                entity_name=BRIDGE_CONTRACTS.get(address.lower())
                or MIXER_CONTRACTS.get(address.lower()),
            )
        )

        # In production: query Neo4j for outgoing transfers
        # Here we stop recursion (no live data in stub)
        if hop >= max_hops:
            return

    def _node_to_dict(self, n: TraceNode) -> dict[str, Any]:
        return {
            "address": n.address,
            "chain": n.chain,
            "hop": n.hop,
            "is_bridge": n.is_bridge,
            "is_mixer": n.is_mixer,
            "entity_name": n.entity_name,
            "risk_score": n.risk_score,
        }

    def _edge_to_dict(self, e: TraceEdge) -> dict[str, Any]:
        return {
            "from": e.from_address,
            "to": e.to_address,
            "tx_hash": e.tx_hash,
            "chain": e.chain,
            "value_usd": e.value_usd,
            "timestamp": e.timestamp,
            "bridge_protocol": e.bridge_protocol,
        }
