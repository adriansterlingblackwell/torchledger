# GitHub Strategy — TorchLedger

## Branch model

```
main          ← production-grade, tagged releases only
  └── develop ← integration branch, deployed to staging
        ├── feat/evm-reorg-handler
        ├── feat/solana-connector
        ├── fix/hdbscan-epsilon-tuning
        └── chore/clickhouse-schema-v2
```

| Branch | Protection | Who merges |
|---|---|---|
| `main` | Required: 2 reviews + CI green + no conflicts | Release manager |
| `develop` | Required: 1 review + CI green | Any engineer |
| `feat/*` | None | Author |

## Commit convention (Conventional Commits)

```
feat(clustering): add HDBSCAN soft-membership prediction
fix(api): handle null to_address on contract create txs
perf(clickhouse): switch to ReplicatedMergeTree for horizontal scale
chore(deps): bump lightgbm 4.2 → 4.3
docs(sdk): add batch_score Python example
test(risk): add integration test for OFAC overlay
```

## PR template

Every PR must:
- Link an issue (`Closes #123`)
- Add/update tests (no coverage regression)
- Update `CHANGELOG.md` under `[Unreleased]`
- Pass all CI checks

## Release process

1. Merge `develop` → `main` via PR
2. GitHub Action auto-tags: `v{year}.{month}.{patch}` (CalVer)
3. Docker images pushed to `ghcr.io/your-org/torchledger/api:{tag}`
4. Helm chart `Chart.yaml` version bumped via action
5. GitHub Release created with auto-generated changelog

## Issue labels

| Label | Use |
|---|---|
| `chain:evm` / `chain:solana` / `chain:btc` | Chain-specific issues |
| `component:clustering` / `component:risk` / `component:api` | Component |
| `priority:p0` | Blocking — fix today |
| `priority:p1` | Fix this sprint |
| `type:compliance` | FATF/OFAC/MiCA compliance work |
| `type:perf` | Performance / latency |

## Project board columns

```
Backlog → Scoped → In Progress → In Review → Done
```

## Secrets management

| Secret | Where |
|---|---|
| `TORCHLEDGER_API_KEY` | GitHub Environment: production |
| `KUBECONFIG_STAGING` | GitHub Environment: staging |
| `NEO4J_PASSWORD` | GitHub Secrets (repo-level) |
| `CODECOV_TOKEN` | GitHub Secrets (repo-level) |

Never commit `.env` files. Use `infra/docker/.env.example` as template.

## Security policy

- Dependabot enabled for Python + Docker
- CodeQL scanning on every push to `main`
- SAST: `bandit` runs in CI (`ruff` S-rules cover most cases)
- Secrets scanning: GitHub Advanced Security enabled
