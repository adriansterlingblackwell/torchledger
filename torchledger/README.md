# 🔦 TorchLedger

> **On-chain behavioral clustering & cross-chain risk tracing engine**
> Built for compliance teams, crypto-native fintechs, and institutional risk desks.
> Portfolio target: Chainalysis, TRM Labs, Elliptic, Merkle Science.

[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://python.org)
[![License: AGPL-3.0](https://img.shields.io/badge/license-AGPL--3.0-green.svg)](LICENSE)
[![Coverage](https://img.shields.io/badge/coverage-87%25-brightgreen)](tests/)
[![API docs](https://img.shields.io/badge/docs-OpenAPI-orange)](http://localhost:8000/docs)

---

## What TorchLedger does

TorchLedger ingests raw on-chain events from EVM, Solana, and UTXO chains,
clusters wallet addresses into behavioral entities using graph neural networks,
traces fund flows across bridges and mixers, and produces FATF-aligned risk scores
via a continuously-updated ML model.

```
EVM / Solana / BTC  →  Kafka event bus  →  Clustering + Tracing  →  Neo4j + ClickHouse
                                                     ↓
                              REST API  ←  Risk Scorer (ML + rule engine)
                                     ↓
                    Dashboard · Webhooks · Python SDK · TS SDK
```

---

## Core capabilities

| Capability | Method | Output |
|---|---|---|
| Entity clustering | HDBSCAN + GNN on tx graph | `entity_id` per address |
| Cross-chain tracing | Bridge event linking + UTXO heuristics | Trace path JSON |
| Risk scoring | LightGBM + OFAC/FATF rule overlay | 0–100 score + label |
| Real-time alerts | Kafka consumer + webhook fanout | `POST /webhook` payload |
| Graph queries | Neo4j Cypher / GraphQL | Subgraph traversals |

---

## Quick start

```bash
# 1. Clone
git clone https://github.com/your-org/torchledger
cd torchledger

# 2. Spin up infra
docker compose up -d   # Kafka, Neo4j, ClickHouse, Redis

# 3. Install deps
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"

# 4. Run migrations
alembic upgrade head

# 5. Start the API
uvicorn api.main:app --reload --port 8000

# 6. Query
curl -s "http://localhost:8000/v1/risk/0xd8dA6BF26964aF9D7eEd9e03E53415D37aA96045" | jq
```

---

## Project structure

```
torchledger/
├── ingestion/              # Chain connectors
│   ├── evm/                # Web3.py + Alchemy/Infura
│   ├── solana/             # solana-py RPC listener
│   └── utxo/               # Bitcoin Core RPC + Electrum
├── clustering/             # Behavioral clustering engine
│   ├── models/             # GNN, HDBSCAN, feature models
│   └── features/           # Feature extractors (velocity, fan-out, timing)
├── tracing/                # Cross-chain fund flow tracer
├── risk/                   # Risk scoring
│   ├── rules/              # OFAC/FATF/custom rule engine
│   └── ml/                 # LightGBM training + inference
├── api/                    # FastAPI application
│   ├── routers/            # /v1/address, /v1/trace, /v1/risk, /v1/alert
│   └── schemas/            # Pydantic models
├── graph_db/               # Neo4j driver + Cypher queries
├── storage/                # ClickHouse + Redis clients
├── sdk/
│   ├── python/             # torchledger-py SDK
│   └── typescript/         # torchledger-ts SDK
├── dashboard/              # React + D3 front-end
├── infra/
│   ├── k8s/                # Kubernetes manifests
│   └── docker/             # Dockerfiles
├── tests/
│   ├── unit/
│   ├── integration/
│   └── e2e/
├── .github/workflows/      # CI/CD
├── docker-compose.yml
├── pyproject.toml
└── README.md
```

---

## Architecture decisions

- **Kafka over RabbitMQ** — native partition-by-chain_id, replay on reorg
- **Neo4j over PostgreSQL for graph** — native Cypher traversals, APOC path algorithms
- **ClickHouse for time-series** — columnar OLAP, sub-second aggregation on billions of rows
- **HDBSCAN over DBSCAN** — handles variable-density address clusters without fixed ε
- **LightGBM over deep NN for risk** — fast inference (<5ms), interpretable SHAP values

---

## Competitive landscape

| Vendor | Gap TorchLedger fills |
|---|---|
| Chainalysis | No self-hosted option; no custom clustering hooks |
| TRM Labs | Closed model; no SDK for in-house integration |
| Elliptic | EU-only focus; no real-time streaming API |
| Merkle Science | Limited graph query API |

---

## Roadmap

- [ ] ZK-proof of compliance (prove risk score without revealing address)
- [ ] Sui / Aptos chain connectors
- [ ] VASP counterparty attribution
- [ ] EU MiCA CASP report generator
- [ ] Tornado Cash / Railgun mixer detection v2

---

## License

AGPL-3.0. Commercial licensing available — contact founders@torchledger.io
