# TorchLedger

<div align="center">

### On-chain Behavioral Clustering & Cross-Chain Risk Tracing Engine

*The open-source intelligence pipeline for blockchain forensics, financial crime investigation, and national security infrastructure.*

---

[![Python](https://img.shields.io/badge/Python-3.11+-1e40af?style=for-the-badge&logo=python&logoColor=white)](https://python.org)
[![License](https://img.shields.io/badge/License-AGPL--3.0-065f46?style=for-the-badge&logoColor=white)](LICENSE)
[![CI](https://img.shields.io/github/actions/workflow/status/adriansterlingblackwell/torchledger/ci.yml?style=for-the-badge&label=CI&logo=githubactions&logoColor=white)](https://github.com/adriansterlingblackwell/torchledger/actions)
[![Coverage](https://img.shields.io/badge/Coverage-87%25-166534?style=for-the-badge&logo=pytest&logoColor=white)](torchledger/tests/)

---

[![Neo4j](https://img.shields.io/badge/Neo4j-Graph_Database-4581C3?style=flat-square&logo=neo4j&logoColor=white)](https://neo4j.com)
[![Kafka](https://img.shields.io/badge/Redpanda-Event_Stream-E4003A?style=flat-square&logo=apachekafka&logoColor=white)](https://kafka.apache.org)
[![ClickHouse](https://img.shields.io/badge/ClickHouse-OLAP_Analytics-FFCC01?style=flat-square&logo=clickhouse&logoColor=black)](https://clickhouse.com)
[![FastAPI](https://img.shields.io/badge/FastAPI-REST_%26_GraphQL-009688?style=flat-square&logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com)
[![PyTorch](https://img.shields.io/badge/PyTorch-GNN_Embeddings-EE4C2C?style=flat-square&logo=pytorch&logoColor=white)](https://pytorch.org)
[![Redis](https://img.shields.io/badge/Redis-Risk_Cache-DC382D?style=flat-square&logo=redis&logoColor=white)](https://redis.io)
[![Docker](https://img.shields.io/badge/Docker-One_Command_Deploy-2496ED?style=flat-square&logo=docker&logoColor=white)](docker-compose.yml)
[![Kubernetes](https://img.shields.io/badge/Kubernetes-Production_Ready-326CE5?style=flat-square&logo=kubernetes&logoColor=white)](torchledger/infra/k8s/)

</div>

---

## What Is TorchLedger

TorchLedger is a **self-hosted blockchain intelligence engine** that ingests raw on-chain events across EVM, Solana, and Bitcoin networks, clusters wallet addresses into behavioral entities using graph neural networks, traces fund flows across bridges and mixers, and produces FATF-aligned risk scores via a continuously-updated machine learning model.

It is the infrastructure layer that compliance teams, forensic investigators, and intelligence operators build their pipelines on top of — without routing sensitive data through third-party SaaS.

---

## The Core Thesis

```
The blockchain is not a ledger. It is a behavioral graph.
```

Wallet addresses do not move in isolation. They cluster by timing entropy, fan-out ratios, bridge usage patterns, and mixer adjacency. A single actor routinely controls hundreds of addresses across multiple chains. Scoring addresses individually — without first resolving the entity graph — produces risk signals that are expensive, brittle, and systematically gamed by sophisticated counterparties.

TorchLedger resolves the graph first. Then it scores.

---

## Capabilities

<div align="center">

| Module | Technology | What It Does |
| :--- | :--- | :--- |
| **Behavioral Clustering** | HDBSCAN + GraphSAGE GNN | Groups addresses into entities by on-chain behavior |
| **Cross-Chain Tracing** | Bridge + UTXO heuristics | Follows funds across EVM, Solana, and Bitcoin |
| **Risk Scoring** | LightGBM · 18 features · SHAP | FATF-aligned 0–100 score with full explainability |
| **Real-Time Alerts** | Kafka + webhook fanout | Fires the moment a threshold is crossed |
| **Graph Intelligence** | Neo4j Cypher + GraphQL | Deep entity traversal and subgraph queries |
| **Batch Screening** | REST API · 500 addresses/call | High-throughput compliance screening |
| **SDK** | Python + TypeScript | Drop-in integration for existing pipelines |

</div>

---

## System Architecture

```text
                     ┌──────────────────────────────────────────────┐
                     │              CHAIN CONNECTORS                 │
                     │  EVM (Alchemy)  Solana RPC  Bitcoin Core RPC  │
                     └──────────────────────┬───────────────────────┘
                                            │
                     ┌──────────────────────▼───────────────────────┐
                     │           KAFKA / REDPANDA EVENT BUS          │
                     │   tx.raw  block.confirmed  bridge.event       │
                     │         partitioned by chain_id               │
                     └──────┬─────────────────────────┬─────────────┘
                            │                         │
              ┌─────────────▼──────────┐   ┌──────────▼─────────────┐
              │   CLUSTERING ENGINE    │   │     RISK SCORER         │
              │  HDBSCAN + GraphSAGE   │   │  LightGBM · 18 features │
              │  Soft-membership pred. │   │  OFAC/FATF rule overlay │
              │  Behavioral tag infer. │   │  SHAP explainability    │
              └─────────────┬──────────┘   └──────────┬─────────────┘
                            │                         │
                     ┌──────▼─────────────────────────▼──────┐
                     │              STORAGE LAYER              │
                     │   Neo4j Graph  │  ClickHouse OLAP       │
                     │   Redis Cache  │  Entity/Cluster/Tx     │
                     └──────────────────────┬─────────────────┘
                                            │
                     ┌──────────────────────▼───────────────────────┐
                     │                   API LAYER                   │
                     │      FastAPI REST  +  Strawberry GraphQL      │
                     │   /v1/risk  /v1/trace  /v1/address  /v1/alert │
                     └──────┬───────────────┬──────────────┬─────────┘
                            │               │              │
                     ┌──────▼──────┐  ┌─────▼────┐  ┌─────▼──────┐
                     │  Dashboard  │  │ Webhooks │  │    SDK     │
                     │  React + D3 │  │Real-time │  │  Python/TS │
                     └─────────────┘  └──────────┘  └────────────┘
```

---

## Risk Model

The scorer combines a trained **LightGBM model** with a deterministic **OFAC/FATF rule overlay**. Every score ships with a full **SHAP feature attribution** breakdown — no black boxes.

**18-feature behavioral input vector:**

```text
 [0]  tx_count_30d                 [9]  cluster_risk_max
 [1]  unique_counterparties_30d   [10]  timing_entropy
 [2]  mixer_exposure_ratio        [11]  value_variance_log
 [3]  cex_deposit_ratio           [12]  fee_anomaly_score
 [4]  darknet_hop_count           [13]  contract_deploy_count
 [5]  bridge_usage_count          [14]  nft_volume_ratio
 [6]  ofac_direct                 [15]  defi_protocol_count
 [7]  ofac_1hop                   [16]  account_age_days
 [8]  cluster_size                [17]  dormancy_score
```

**Score bands:**

| Score | Label | Signal |
| :---: | :---: | :--- |
| 0 – 24 | `low` | No exposure to illicit counterparties |
| 25 – 49 | `medium` | Indirect hops to flagged entities |
| 50 – 74 | `high` | Direct interaction with sanctioned or mixer addresses |
| 75 – 100 | `severe` | Address is sanctioned or a confirmed exploit wallet |

---

## Quick Start

```bash
# Clone and enter
git clone https://github.com/adriansterlingblackwell/torchledger
cd torchledger

# Start full infrastructure stack
docker compose up -d
# Kafka · Neo4j · ClickHouse · Redis — all in one command

# Install Python package
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"

# Launch API
uvicorn torchledger.api.main:app --reload --port 8000
```

**Score an address:**

```bash
curl -s "http://localhost:8000/v1/risk/0xd8dA6BF26964aF9D7eEd9e03E53415D37aA96045" | jq
```

**Trace cross-chain fund flow:**

```bash
curl -s -X POST "http://localhost:8000/v1/trace/" \
  -H "Content-Type: application/json" \
  -d '{
    "origin": "0xd8dA6BF26964aF9D7eEd9e03E53415D37aA96045",
    "chain": "evm",
    "max_hops": 4,
    "follow_bridges": true
  }' | jq
```

**Python SDK:**

```python
from torchledger.sdk.python.torchledger import TorchLedger

client = TorchLedger(api_key="tl_live_...")

# Single address
report = client.risk.get("0xd8dA6BF26964aF9D7eEd9e03E53415D37aA96045", explain=True)
print(f"{report.score}/100 — {report.label}")

# Batch screening
reports = client.risk.batch(["0xabc...", "0xdef...", "0x123..."])
high_risk = [r for r in reports if r.is_high_risk]
```

---

## Technology Stack

| Layer | Choice | Rationale |
| :--- | :--- | :--- |
| Event bus | Kafka / Redpanda | Partition by `chain_id`, deterministic replay on chain reorg |
| Graph database | Neo4j + GDS + APOC | Native Cypher traversal, PageRank, community detection |
| Analytics | ClickHouse | Sub-second OLAP aggregation across billions of rows |
| Clustering | HDBSCAN + GraphSAGE | Variable-density address clusters, soft membership |
| Risk ML | LightGBM | Sub-5ms inference, SHAP explainability, no GPU required |
| API | FastAPI + Strawberry | Async, OpenAPI, schema-first GraphQL |
| Infra | Docker Compose + Kubernetes | One-command local dev, production-grade k8s manifests |

---

## Why Not Just Use SaaS

Leading blockchain analytics vendors provide valuable services. They also share a structural constraint: your counterparty data, your investigation targets, and your risk thresholds all transit their infrastructure.

For teams operating in regulated, classified, or air-gapped environments — that is not an option.

TorchLedger is built for operators who need full stack ownership: the model, the graph, the scoring logic, and the data — all running inside your own perimeter.

---

## Roadmap

- [ ] ZK-proof of compliance — prove a risk score without revealing the address
- [ ] Sui / Aptos chain connectors
- [ ] VASP counterparty attribution module
- [ ] EU MiCA CASP automated report generator
- [ ] Tornado Cash / Railgun mixer detection v2
- [ ] OSINT enrichment layer — ENS, Farcaster, on-chain identity graphs
- [ ] FPGA-accelerated graph traversal for high-frequency screening pipelines

---

## Repository Structure

```text
torchledger/
├── ingestion/
│   ├── evm/            # Web3.py async block listener — Alchemy / Infura / own node
│   ├── solana/         # solana-py RPC subscriber
│   └── utxo/           # Bitcoin Core RPC + UTXO set indexer
├── clustering/
│   ├── engine.py       # HDBSCAN + GraphSAGE pipeline
│   ├── models/         # GNN architecture, feature models
│   └── features/       # Velocity, fan-out, timing entropy extractors
├── tracing/
│   └── engine.py       # Cross-chain BFS tracer — bridges, mixers, DEX hops
├── risk/
│   ├── scorer.py       # LightGBM + OFAC/FATF rule engine + SHAP
│   ├── rules/          # Deterministic compliance rule definitions
│   └── ml/             # Model training, evaluation, versioning
├── api/
│   ├── main.py         # FastAPI application entry point
│   ├── routers/        # /v1/risk · /v1/trace · /v1/address · /v1/alert
│   └── schemas/        # Pydantic v2 request / response models
├── graph_db/
│   └── client.py       # Neo4j async driver + Cypher query library
├── storage/            # ClickHouse OLAP client + Redis cache
├── sdk/
│   ├── python/         # torchledger-py — httpx-based client SDK
│   └── typescript/     # torchledger-ts — fetch-based client SDK
├── dashboard/          # React + D3 graph visualization frontend
├── infra/
│   ├── docker/         # Dockerfiles + ClickHouse schema init
│   └── k8s/            # Kubernetes deployment manifests
├── tests/
│   ├── unit/           # Scorer, clustering, tracing unit tests
│   ├── integration/    # Neo4j + Redis live integration tests
│   └── e2e/            # Full pipeline end-to-end tests
├── .github/workflows/  # CI — lint · test · build · deploy
├── docker-compose.yml
├── pyproject.toml
└── README.md
```

---

<div align="center">

---

**Adrian Sterling Blackwell**

[![Email](https://img.shields.io/badge/Email-adriansterlingblackwell%40gmail.com-EA4335?style=for-the-badge&logo=gmail&logoColor=white)](mailto:adriansterlingblackwell@gmail.com)
[![GitHub](https://img.shields.io/badge/GitHub-adriansterlingblackwell-181717?style=for-the-badge&logo=github&logoColor=white)](https://github.com/adriansterlingblackwell)

*AGPL-3.0 · Commercial and government licensing available*

</div>
