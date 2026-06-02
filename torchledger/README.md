# TorchLedger

> On-chain behavioral clustering & cross-chain risk tracing engine.
> Built for compliance teams, intelligence operators, and institutional risk desks.

[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://python.org)
[![License: AGPL-3.0](https://img.shields.io/badge/license-AGPL--3.0-green.svg)](LICENSE)
[![Coverage](https://img.shields.io/badge/coverage-87%25-brightgreen)](tests/)
[![CI](https://github.com/adriansterlingblackwell/torchledger/actions/workflows/ci.yml/badge.svg)](https://github.com/adriansterlingblackwell/torchledger/actions)
[![OpenAPI](https://img.shields.io/badge/docs-OpenAPI-orange)](https://github.com/adriansterlingblackwell/torchledger#quick-start)

---

## The problem

Most blockchain analytics tools treat the chain like a ledger — address in, risk score out.

That framing misses the point. On-chain activity is a **behavioral graph**. Wallets cluster by timing patterns, fan-out ratios, bridge usage, and mixer adjacency. Entity-level risk only becomes legible *after* you've resolved the graph. Scoring raw addresses without clustering first is compliance theater.

TorchLedger is the infrastructure layer that sits underneath that problem.

---

## What it does

```text
EVM / Solana / BTC  -->  Kafka event bus  -->  Clustering + Tracing  -->  Neo4j + ClickHouse
                                                       |
                              REST API  <--  Risk Scorer (ML + rule engine)
                                       |
                    Dashboard  Webhooks  Python SDK  TS SDK
```

| Capability | Method | Output |
| --- | --- | --- |
| Entity clustering | HDBSCAN + GraphSAGE on tx graph | `entity_id` per address |
| Cross-chain tracing | Bridge event linking + UTXO heuristics | Trace path JSON |
| Risk scoring | LightGBM + OFAC/FATF rule overlay | 0–100 score + label |
| Real-time alerts | Kafka consumer + webhook fanout | `POST /webhook` payload |
| Graph queries | Neo4j Cypher / GraphQL | Subgraph traversals |

---

## Quick start

```bash
# 1. Clone
git clone https://github.com/adriansterlingblackwell/torchledger
cd torchledger

# 2. Spin up infra (Kafka, Neo4j, ClickHouse, Redis)
docker compose up -d

# 3. Install
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"

# 4. Start API
uvicorn api.main:app --reload --port 8000

# 5. Score an address
curl -s "http://localhost:8000/v1/risk/0xd8dA6BF26964aF9D7eEd9e03E53415D37aA96045" | jq
```

---

## Project structure

```text
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

**Kafka over RabbitMQ** — native partition-by-`chain_id`, deterministic replay on chain reorg.

**Neo4j over PostgreSQL for graph** — native Cypher traversals, APOC path algorithms, GDS for PageRank/community detection at scale.

**ClickHouse for time-series** — columnar OLAP, sub-second aggregation across billions of rows with `ReplacingMergeTree`.

**HDBSCAN over DBSCAN** — handles variable-density address clusters without a fixed ε. Soft membership enables probabilistic cluster assignment for new addresses.

**LightGBM over deep NN for risk** — inference under 5ms, SHAP explainability per-feature, no GPU dependency in production.

---

## Risk scoring model

The scorer combines a trained LightGBM model with a deterministic OFAC/FATF rule overlay.

18-feature input vector:

```text
[0]  tx_count_30d               [9]  cluster_risk_max
[1]  unique_counterparties_30d  [10] timing_entropy
[2]  mixer_exposure_ratio       [11] value_variance_log
[3]  cex_deposit_ratio          [12] fee_anomaly_score
[4]  darknet_hop_count          [13] contract_deploy_count
[5]  bridge_usage_count         [14] nft_volume_ratio
[6]  ofac_direct                [15] defi_protocol_count
[7]  ofac_1hop                  [16] account_age_days
[8]  cluster_size               [17] dormancy_score
```

Score bands:

| Score | Label | Meaning |
| --- | --- | --- |
| 0–24 | `low` | No exposure to illicit counterparties |
| 25–49 | `medium` | Indirect hops to flagged entities |
| 50–74 | `high` | Direct interaction with sanctioned / mixer addresses |
| 75–100 | `severe` | Address IS sanctioned or is a known exploit wallet |

---

## Competitive positioning

| Vendor | Gap TorchLedger fills |
| --- | --- |
| Chainalysis | No self-hosted option; no custom clustering hooks |
| TRM Labs | Closed model; no SDK for in-house integration |
| Elliptic | EU-only focus; no real-time streaming API |
| Merkle Science | Limited graph query API |

TorchLedger is the self-hosted, open-source layer for teams that need to own their intelligence pipeline — defense contractors, sovereign wealth funds, government agencies, and crypto-native compliance desks that cannot route data through third-party SaaS.

---

## Roadmap

- [ ] ZK-proof of compliance (prove risk score without revealing address)
- [ ] Sui / Aptos chain connectors
- [ ] VASP counterparty attribution
- [ ] EU MiCA CASP report generator
- [ ] Tornado Cash / Railgun mixer detection v2
- [ ] OSINT enrichment layer (ENS, Farcaster, onchain identity)

---

## Contributing

Pull requests welcome. See [GITHUB_STRATEGY.md](GITHUB_STRATEGY.md) for branch conventions and commit format.

For security disclosures: [adriansterlingblackwell@gmail.com](mailto:adriansterlingblackwell@gmail.com)

---

## License

AGPL-3.0. Commercial and government licensing available — [adriansterlingblackwell@gmail.com](mailto:adriansterlingblackwell@gmail.com)
