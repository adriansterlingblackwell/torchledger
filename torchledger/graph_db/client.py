"""
Neo4j graph schema and query layer.

Graph model:
  (:Address {address, chain, first_seen, last_seen, risk_score})
    -[:SENT {tx_hash, value_usd, timestamp}]->
  (:Address)

  (:Address)-[:BELONGS_TO]->(:Entity {entity_id, name, category, risk_score})
  (:Entity)-[:IN_CLUSTER]->(:Cluster {cluster_id, size, behavioral_tags})
  (:Address)-[:INTERACTED_WITH]->(:Contract {address, name, type})
"""
from __future__ import annotations

import os
from contextlib import asynccontextmanager
from typing import Any, AsyncGenerator

import structlog
from neo4j import AsyncDriver, AsyncGraphDatabase

logger = structlog.get_logger()

NEO4J_URI = os.getenv("DATABASE_URL", "bolt://localhost:7687")
NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "torchledger_dev")

# ── Schema constraints (run once on startup) ──────────────────────────────────
SCHEMA_QUERIES = [
    "CREATE CONSTRAINT address_unique IF NOT EXISTS FOR (a:Address) REQUIRE a.address IS UNIQUE",
    "CREATE CONSTRAINT entity_unique IF NOT EXISTS FOR (e:Entity) REQUIRE e.entity_id IS UNIQUE",
    "CREATE CONSTRAINT cluster_unique IF NOT EXISTS FOR (c:Cluster) REQUIRE c.cluster_id IS UNIQUE",
    "CREATE INDEX address_chain IF NOT EXISTS FOR (a:Address) ON (a.chain)",
    "CREATE INDEX address_risk IF NOT EXISTS FOR (a:Address) ON (a.risk_score)",
]


class GraphDB:
    def __init__(self) -> None:
        self._driver: AsyncDriver | None = None

    async def connect(self) -> None:
        self._driver = AsyncGraphDatabase.driver(
            NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD)
        )
        await self._driver.verify_connectivity()
        await self._apply_schema()
        logger.info("neo4j_connected", uri=NEO4J_URI)

    async def close(self) -> None:
        if self._driver:
            await self._driver.close()

    async def _apply_schema(self) -> None:
        async with self._driver.session() as session:  # type: ignore[union-attr]
            for q in SCHEMA_QUERIES:
                await session.run(q)

    @asynccontextmanager
    async def session(self) -> AsyncGenerator[Any, None]:
        if not self._driver:
            raise RuntimeError("GraphDB not connected")
        async with self._driver.session() as s:
            yield s

    # ── Write operations ─────────────────────────────────────────────────────

    async def upsert_address(
        self,
        address: str,
        chain: str,
        risk_score: int = 0,
        **props: Any,
    ) -> None:
        async with self.session() as s:
            await s.run(
                """
                MERGE (a:Address {address: $address})
                ON CREATE SET a.chain = $chain, a.first_seen = timestamp(), a.risk_score = $risk_score
                ON MATCH  SET a.last_seen = timestamp(), a.risk_score = $risk_score
                """,
                address=address,
                chain=chain,
                risk_score=risk_score,
            )

    async def upsert_transfer(
        self,
        from_addr: str,
        to_addr: str,
        tx_hash: str,
        value_usd: float,
        timestamp: int,
        chain: str,
    ) -> None:
        async with self.session() as s:
            await s.run(
                """
                MERGE (a:Address {address: $from_addr})
                MERGE (b:Address {address: $to_addr})
                CREATE (a)-[:SENT {
                    tx_hash: $tx_hash,
                    value_usd: $value_usd,
                    timestamp: $timestamp,
                    chain: $chain
                }]->(b)
                """,
                from_addr=from_addr,
                to_addr=to_addr,
                tx_hash=tx_hash,
                value_usd=value_usd,
                timestamp=timestamp,
                chain=chain,
            )

    async def assign_cluster(self, addresses: list[str], cluster_id: str) -> None:
        async with self.session() as s:
            await s.run(
                """
                MERGE (c:Cluster {cluster_id: $cluster_id})
                WITH c
                UNWIND $addresses AS addr
                MATCH (a:Address {address: addr})
                MERGE (a)-[:IN_CLUSTER]->(c)
                """,
                addresses=addresses,
                cluster_id=cluster_id,
            )

    # ── Read operations ──────────────────────────────────────────────────────

    async def get_neighbors(
        self,
        address: str,
        depth: int = 2,
        min_value_usd: float = 0,
    ) -> list[dict[str, Any]]:
        async with self.session() as s:
            result = await s.run(
                """
                MATCH path = (start:Address {address: $address})-[:SENT*1..$depth]->(end:Address)
                WHERE ALL(r IN relationships(path) WHERE r.value_usd >= $min_value_usd)
                RETURN
                    [n IN nodes(path) | n.address]    AS addresses,
                    [r IN rels(path)  | r.tx_hash]    AS tx_hashes,
                    length(path)                       AS hops
                LIMIT 500
                """,
                address=address,
                depth=depth,
                min_value_usd=min_value_usd,
            )
            return [dict(r) async for r in result]

    async def get_cluster_members(self, cluster_id: str) -> list[str]:
        async with self.session() as s:
            result = await s.run(
                """
                MATCH (a:Address)-[:IN_CLUSTER]->(c:Cluster {cluster_id: $cluster_id})
                RETURN a.address AS address
                """,
                cluster_id=cluster_id,
            )
            return [r["address"] async for r in result]

    async def shortest_path_to_sanctioned(
        self, address: str
    ) -> list[dict[str, Any]] | None:
        """Find shortest path from address to any sanctioned entity."""
        async with self.session() as s:
            result = await s.run(
                """
                MATCH (start:Address {address: $address}),
                      (end:Address)
                WHERE end.is_sanctioned = true
                MATCH path = shortestPath((start)-[:SENT*..6]->(end))
                RETURN
                    [n IN nodes(path) | n.address] AS path,
                    length(path) AS hops
                LIMIT 1
                """,
                address=address,
            )
            records = [dict(r) async for r in result]
            return records[0] if records else None


# Singleton
_db: GraphDB | None = None


async def get_db() -> GraphDB:
    global _db
    if _db is None:
        _db = GraphDB()
        await _db.connect()
    return _db
