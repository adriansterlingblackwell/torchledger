-- TorchLedger ClickHouse schema
-- Optimized for time-series tx analytics

CREATE DATABASE IF NOT EXISTS torchledger;

-- Raw transactions (partitioned by month, sorted by from+timestamp)
CREATE TABLE IF NOT EXISTS torchledger.transactions (
    chain_id        UInt32,
    block_number    UInt64,
    block_timestamp DateTime,
    tx_hash         FixedString(66),
    from_address    LowCardinality(String),
    to_address      LowCardinality(String),
    value_wei       UInt256,
    value_usd       Float64,
    gas_used        UInt64,
    gas_price_gwei  Float32,
    method_id       Nullable(FixedString(10)),
    risk_score      UInt8 DEFAULT 0,
    cluster_id      LowCardinality(Nullable(String))
)
ENGINE = ReplacingMergeTree(block_timestamp)
PARTITION BY toYYYYMM(block_timestamp)
ORDER BY (from_address, block_timestamp, tx_hash)
SETTINGS index_granularity = 8192;

-- Pre-aggregated address stats (materialized view source)
CREATE TABLE IF NOT EXISTS torchledger.address_stats_hourly (
    address         LowCardinality(String),
    chain_id        UInt32,
    hour            DateTime,
    tx_out_count    UInt32,
    tx_in_count     UInt32,
    volume_out_usd  Float64,
    volume_in_usd   Float64,
    unique_peers    UInt32
)
ENGINE = SummingMergeTree
PARTITION BY toYYYYMM(hour)
ORDER BY (address, chain_id, hour);

-- Risk score history
CREATE TABLE IF NOT EXISTS torchledger.risk_score_log (
    address         String,
    chain           LowCardinality(String),
    scored_at       DateTime DEFAULT now(),
    score           UInt8,
    label           LowCardinality(String),
    model_version   LowCardinality(String)
)
ENGINE = MergeTree
ORDER BY (address, scored_at)
TTL scored_at + INTERVAL 2 YEAR;
