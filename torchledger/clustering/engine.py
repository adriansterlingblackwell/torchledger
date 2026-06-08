"""
Behavioral clustering engine.

Pipeline:
  1. Pull address-level features from ClickHouse (tx velocity, fan-out, timing entropy)
  2. Embed address pairs via GNN (message passing on the transaction graph)
  3. Run HDBSCAN on the embedding space
  4. Persist cluster assignments to Neo4j
"""
from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Any

import hdbscan
import numpy as np
import structlog
import torch
from torch_geometric.nn import SAGEConv

logger = structlog.get_logger()


@dataclass
class ClusterResult:
    cluster_id: str
    addresses: list[str]
    size: int
    core_address: str
    behavioral_tags: list[str]  # e.g. ["high_velocity", "exchange_like", "mixer_adjacent"]
    confidence: float


class AddressEncoder(torch.nn.Module):
    """2-layer GraphSAGE encoder producing 128-dim address embeddings."""

    def __init__(self, in_channels: int = 64, hidden: int = 256, out: int = 128) -> None:
        super().__init__()
        self.conv1 = SAGEConv(in_channels, hidden)
        self.conv2 = SAGEConv(hidden, out)

    def forward(self, x: torch.Tensor, edge_index: torch.Tensor) -> torch.Tensor:
        x = torch.relu(self.conv1(x, edge_index))
        return self.conv2(x, edge_index)


class ClusteringEngine:
    """
    HDBSCAN-based behavioral clustering over GNN embeddings.

    Usage:
        engine = ClusteringEngine()
        results = await engine.cluster_batch(addresses, features, edges)
    """

    def __init__(
        self,
        min_cluster_size: int = 5,
        min_samples: int = 3,
        embedding_dim: int = 128,
    ) -> None:
        self.min_cluster_size = min_cluster_size
        self.min_samples = min_samples
        self._encoder = AddressEncoder(out=embedding_dim)
        self._clusterer = hdbscan.HDBSCAN(
            min_cluster_size=min_cluster_size,
            min_samples=min_samples,
            metric="euclidean",
            cluster_selection_method="eom",
            prediction_data=True,
        )
        self._fitted = False

    async def cluster_batch(
        self,
        addresses: list[str],
        node_features: np.ndarray,
        edge_index: np.ndarray,
    ) -> list[ClusterResult]:
        """
        Cluster a batch of addresses.

        Args:
            addresses: list of address strings
            node_features: (N, F) float32 array — per-address features
            edge_index: (2, E) int64 array — directed tx edges

        Returns:
            List of ClusterResult, one per discovered cluster.
        """
        logger.info("clustering_start", n_addresses=len(addresses))

        # 1. Embed
        embeddings = await asyncio.get_event_loop().run_in_executor(
            None, self._embed, node_features, edge_index
        )

        # 2. Cluster
        labels = await asyncio.get_event_loop().run_in_executor(
            None, self._fit_predict, embeddings
        )

        # 3. Build results
        clusters: dict[int, list[int]] = {}
        for idx, label in enumerate(labels):
            if label == -1:
                continue  # noise
            clusters.setdefault(label, []).append(idx)

        results = []
        for cluster_label, indices in clusters.items():
            cluster_addresses = [addresses[i] for i in indices]
            cluster_embeddings = embeddings[indices]
            core_idx = self._find_core(cluster_embeddings)
            results.append(
                ClusterResult(
                    cluster_id=f"cls_{cluster_label:06d}",
                    addresses=cluster_addresses,
                    size=len(cluster_addresses),
                    core_address=cluster_addresses[core_idx],
                    behavioral_tags=self._infer_tags(node_features[indices]),
                    confidence=float(self._clusterer.probabilities_[indices].mean()),
                )
            )

        logger.info("clustering_done", n_clusters=len(results))
        return results

    def _embed(self, features: np.ndarray, edge_index: np.ndarray) -> np.ndarray:
        self._encoder.eval()
        with torch.no_grad():
            x = torch.tensor(features, dtype=torch.float32)
            ei = torch.tensor(edge_index, dtype=torch.long)
            return self._encoder(x, ei).numpy()

    def _fit_predict(self, embeddings: np.ndarray) -> np.ndarray:
        labels = self._clusterer.fit_predict(embeddings)
        self._fitted = True
        return labels

    def _find_core(self, embeddings: np.ndarray) -> int:
        """Return index of the embedding closest to cluster centroid."""
        centroid = embeddings.mean(axis=0)
        dists = np.linalg.norm(embeddings - centroid, axis=1)
        return int(np.argmin(dists))

    def _infer_tags(self, features: np.ndarray) -> list[str]:
        """Heuristic behavioral tags from feature statistics."""
        tags = []
        mean_velocity = features[:, 0].mean()  # col 0 = tx/day
        mean_fanout = features[:, 1].mean()    # col 1 = unique counterparties

        if mean_velocity > 100:
            tags.append("high_velocity")
        if mean_fanout > 500:
            tags.append("exchange_like")
        if mean_velocity > 50 and mean_fanout < 10:
            tags.append("mixer_like")
        return tags

    async def predict_membership(
        self,
        address: str,
        features: np.ndarray,
        edge_index: np.ndarray,
    ) -> tuple[str | None, float]:
        """Predict cluster membership for a single new address."""
        if not self._fitted:
            return None, 0.0

        embedding = self._embed(features, edge_index)
        labels, strengths = hdbscan.approximate_predict(self._clusterer, embedding)
        label = int(labels[0])
        strength = float(strengths[0])

        if label == -1:
            return None, strength

        return f"cls_{label:06d}", strength
