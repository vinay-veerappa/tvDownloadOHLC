-- ============================================================================
-- TRADING SECOND BRAIN: CANONICAL RELATIONAL SCHEMA (v5.3.0)
-- Database: data/wargaming/db/trading_brain.sqlite
-- 22 Tables | 19 Protected Append-Only Tables | 38 Immutability Triggers | 4 Views
-- ============================================================================

PRAGMA foreign_keys = ON;

-- ----------------------------------------------------------------------------
-- 1. UNIVERSAL TYPED INTAKE CATALOG & REVIEW LEDGER
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS information_items (
    information_id TEXT PRIMARY KEY,           -- UUID v4
    evidence_class TEXT NOT NULL,              -- 'DOCTRINE', 'QUANT_HYPOTHESIS', 'WARGAME_SCENARIO', etc.
    time_orientation TEXT NOT NULL,            -- 'EX_ANTE', 'INTRADAY', 'POST_HOC'
    source_type TEXT NOT NULL,                 -- 'TRANSCRIPT', 'INDICATOR_CODE', 'MACRO_REPORT', 'JOURNAL'
    title TEXT NOT NULL,
    verbatim_text TEXT NOT NULL,
    structured_payload_json TEXT,              -- Parsed metadata, levels, tags
    available_at_utc TIMESTAMP NOT NULL,       -- Temporal availability boundary
    received_at_utc TIMESTAMP NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now')),
    created_at_utc TIMESTAMP NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now'))
);

CREATE TABLE IF NOT EXISTS information_item_review_events (
    review_event_id TEXT PRIMARY KEY,
    information_id TEXT NOT NULL,
    review_state TEXT NOT NULL,                -- 'CAPTURED', 'ACCEPTED', 'REJECTED', 'QUARANTINED'
    reviewer TEXT NOT NULL,
    review_notes TEXT,
    event_timestamp_utc TIMESTAMP NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now')),  -- user-declared/effective time (untrusted)
    received_at_utc TIMESTAMP NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now')),      -- trusted server receipt; as-of eligibility key
    created_at_utc TIMESTAMP NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now')),
    FOREIGN KEY (information_id) REFERENCES information_items(information_id)
);

-- ----------------------------------------------------------------------------
-- 2. PRE-MARKET PLAN SNAPSHOTS & LIFECYCLE LEDGERS
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS plan_snapshots (
    plan_snapshot_id TEXT PRIMARY KEY,         -- UUID v4
    plan_family_id TEXT NOT NULL,              -- UUID grouping all revisions for (session_date, ticker)
    revision_seq INTEGER NOT NULL,             -- Monotonic 1-indexed revision sequence
    session_date DATE NOT NULL,
    ticker TEXT NOT NULL,
    preparation_cutoff_utc TIMESTAMP NOT NULL,
    source_system TEXT NOT NULL,               -- 'PRISMA_WEB', 'MARKDOWN_CLI', 'MANUAL_IMPORT'
    source_plan_id TEXT,                       -- Reference to Prisma TradePlan.id
    source_revision_hash TEXT,                 -- Content hash of the external source at mirror time
    supersedes_plan_snapshot_id TEXT,          -- Nullable FK for replacement snapshots
    
    -- Plan Content & Declarations
    verbatim_plan_text TEXT NOT NULL,          -- Unaltered user plan text
    primary_bias TEXT NOT NULL,                -- 'BULLISH', 'BEARISH', 'NEUTRAL', 'NO_TRADE'
    wargamed_scenarios_json TEXT NOT NULL,     -- Structured scenarios and expected branches
    invalidation_levels_json TEXT NOT NULL,    -- Explicit price invalidation boundaries
    max_intended_risk_bps REAL NOT NULL,       -- Risk budget declaration
    permitted_strategies_json TEXT NOT NULL,   -- Active strategy IDs for the session
    
    -- Provenance Timestamps
    received_at_utc TIMESTAMP NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now')),
    provenance_class TEXT NOT NULL,            -- 'EX_ANTE_DECLARED' or 'POST_HOC_RECONSTRUCTION'
    created_at_utc TIMESTAMP NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now')),
    FOREIGN KEY (supersedes_plan_snapshot_id) REFERENCES plan_snapshots(plan_snapshot_id),
    CONSTRAINT ck_no_self_supersession CHECK (supersedes_plan_snapshot_id <> plan_snapshot_id),
    UNIQUE(plan_family_id, revision_seq),
    UNIQUE(source_plan_id, source_revision_hash)
);

CREATE TABLE IF NOT EXISTS plan_lifecycle_events (
    event_id TEXT PRIMARY KEY,
    plan_snapshot_id TEXT NOT NULL,
    event_type TEXT NOT NULL,                  -- 'SUBMITTED', 'SUPERSEDED', 'CANCELLED'
    recorded_at_utc TIMESTAMP NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now')),
    reason TEXT,
    FOREIGN KEY (plan_snapshot_id) REFERENCES plan_snapshots(plan_snapshot_id)
);

CREATE TABLE IF NOT EXISTS plan_amendments (
    amendment_id TEXT PRIMARY KEY,
    plan_snapshot_id TEXT NOT NULL,
    supersedes_amendment_id TEXT,
    amendment_seq INTEGER NOT NULL,
    effective_at_utc TIMESTAMP NOT NULL,       -- User-declared intended start
    received_at_utc TIMESTAMP NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now')), -- Trusted server receipt
    reason_code TEXT NOT NULL,                 -- 'MACRO_NEWS', 'REGIME_CHANGE', 'DISCIPLINE_PAUSE'
    amendment_text TEXT NOT NULL,
    amended_bias TEXT,
    amended_risk_bps REAL,
    FOREIGN KEY (plan_snapshot_id) REFERENCES plan_snapshots(plan_snapshot_id),
    FOREIGN KEY (supersedes_amendment_id) REFERENCES plan_amendments(amendment_id),
    UNIQUE(plan_snapshot_id, amendment_seq)
);

-- ----------------------------------------------------------------------------
-- 3. PRE-MARKET FORECAST RUNS, SEALED INPUTS & SNAPSHOTS
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS forecast_runs (
    forecast_run_id TEXT PRIMARY KEY,          -- UUID v4
    session_date DATE NOT NULL,
    ticker TEXT NOT NULL,
    model_version_id TEXT NOT NULL,
    effective_cutoff_utc TIMESTAMP NOT NULL,
    commit_grace_period_sec INTEGER NOT NULL,  -- Pinned from model contract at run creation
    status TEXT NOT NULL,                      -- 'CREATED', 'INPUTS_SEALED', 'COMMITTED', 'FAILED', 'EXPIRED'
    started_at_utc TIMESTAMP NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now')),
    inputs_sealed_at_utc TIMESTAMP,
    committed_at_utc TIMESTAMP,
    created_at_utc TIMESTAMP DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now'))
);

CREATE TABLE IF NOT EXISTS forecast_run_inputs (
    input_id TEXT PRIMARY KEY,
    forecast_run_id TEXT NOT NULL,
    provider_name TEXT NOT NULL,
    data_type TEXT NOT NULL,
    max_timestamp_utc TIMESTAMP NOT NULL,
    content_hash TEXT NOT NULL,
    created_at_utc TIMESTAMP DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now')),
    FOREIGN KEY (forecast_run_id) REFERENCES forecast_runs(forecast_run_id)
);

CREATE TABLE IF NOT EXISTS forecast_snapshots (
    forecast_id TEXT PRIMARY KEY,              -- UUID v4
    forecast_run_id TEXT,                      -- Reference to forecast_runs
    session_date DATE NOT NULL,
    ticker TEXT NOT NULL,
    model_version_id TEXT NOT NULL,
    forecast_mode TEXT NOT NULL,               -- 'LIVE_PRODUCTION', 'FORECAST_LATE_RECEIVED', 'REPLAY_AUDIT', 'SHADOW'
    effective_cutoff_utc TIMESTAMP NOT NULL,
    
    -- Quant Probabilities across 5 MECE Day Types (0.0 to 1.0, sum to 1.0 unless abstained)
    prob_r1 REAL CHECK(prob_r1 IS NULL OR (prob_r1 >= 0.0 AND prob_r1 <= 1.0)),
    prob_r2 REAL CHECK(prob_r2 IS NULL OR (prob_r2 >= 0.0 AND prob_r2 <= 1.0)),
    prob_dnp REAL CHECK(prob_dnp IS NULL OR (prob_dnp >= 0.0 AND prob_dnp <= 1.0)),
    prob_dwp REAL CHECK(prob_dwp IS NULL OR (prob_dwp >= 0.0 AND prob_dwp <= 1.0)),
    prob_rotational_chop REAL CHECK(prob_rotational_chop IS NULL OR (prob_rotational_chop >= 0.0 AND prob_rotational_chop <= 1.0)),
    predicted_day_type TEXT,
    
    -- Directional Anchors & Levels
    predicted_bias TEXT,
    p12_vector_direction TEXT,
    p12_equilibrium_level REAL,
    candle_science_target_high REAL,
    candle_science_target_low REAL,
    expected_move_high REAL,
    expected_move_low REAL,
    
    -- Provenance & Metadata
    git_hash TEXT NOT NULL,
    config_hash TEXT NOT NULL,
    abstain_flag BOOLEAN DEFAULT FALSE,
    abstain_reason TEXT,
    received_at_utc TIMESTAMP NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now')),
    created_at_utc TIMESTAMP NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now')),
    FOREIGN KEY (forecast_run_id) REFERENCES forecast_runs(forecast_run_id)
);

-- Strict partial unique index: Exactly ONE LIVE_PRODUCTION forecast per (session_date, ticker)
CREATE UNIQUE INDEX IF NOT EXISTS uq_live_forecast_per_session 
ON forecast_snapshots (session_date, ticker) 
WHERE forecast_mode = 'LIVE_PRODUCTION';

-- ----------------------------------------------------------------------------
-- 4. SIGNAL OPPORTUNITIES, DISPOSITIONS & THEORETICAL OUTCOMES
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS signal_opportunities (
    opportunity_id TEXT PRIMARY KEY,
    session_date DATE NOT NULL,
    ticker TEXT NOT NULL,
    strategy_version_id TEXT NOT NULL,
    bar_timestamp_utc TIMESTAMP NOT NULL,
    decision_time_utc TIMESTAMP NOT NULL,
    signal_direction TEXT NOT NULL DEFAULT 'LONG', -- 'LONG' or 'SHORT'
    trigger_price REAL NOT NULL,
    declared_stop_price REAL NOT NULL,
    declared_target_1_price REAL NOT NULL,
    declared_target_2_price REAL,
    stop_distance_bps REAL NOT NULL,
    target_1_bps REAL NOT NULL,
    feature_manifest_json TEXT NOT NULL,
    evaluation_mode TEXT NOT NULL,             -- 'LIVE_CAPTURE', 'HISTORICAL_REPLAY'
    received_at_utc TIMESTAMP NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now')),
    created_at_utc TIMESTAMP NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now')),
    UNIQUE(session_date, ticker, strategy_version_id, bar_timestamp_utc)
);

CREATE TABLE IF NOT EXISTS signal_disposition_events (
    disposition_id TEXT PRIMARY KEY,
    opportunity_id TEXT NOT NULL,
    disposition_state TEXT NOT NULL,           -- 'EXECUTED', 'PASSED', 'MISSED', 'OFFLINE'
    source_system TEXT NOT NULL,               -- 'MECHANICAL_RECONCILER', 'MANUAL_CORRECTION'
    corrects_disposition_id TEXT,
    matched_execution_id TEXT,
    latency_seconds REAL,
    disposition_reason TEXT,
    event_timestamp_utc TIMESTAMP NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now')),
    created_at_utc TIMESTAMP NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now')),
    FOREIGN KEY (opportunity_id) REFERENCES signal_opportunities(opportunity_id),
    FOREIGN KEY (corrects_disposition_id) REFERENCES signal_disposition_events(disposition_id)
);

CREATE TABLE IF NOT EXISTS signal_outcomes (
    outcome_id TEXT PRIMARY KEY,
    opportunity_id TEXT NOT NULL,
    observed_outcome TEXT NOT NULL,            -- 'TARGET_REACHED', 'STOP_HIT', 'TIME_EXPIRED', 'AMBIGUOUS_INTRABAR_ORDER'
    pessimistic_bound TEXT NOT NULL,           -- 'STOP_HIT'
    optimistic_bound TEXT NOT NULL,            -- 'TARGET_REACHED'
    realized_mfe_bps REAL NOT NULL,
    realized_mae_bps REAL NOT NULL,
    bars_held INTEGER NOT NULL,
    evaluated_at_utc TIMESTAMP NOT NULL,
    created_at_utc TIMESTAMP NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now')),
    FOREIGN KEY (opportunity_id) REFERENCES signal_opportunities(opportunity_id)
);

-- ----------------------------------------------------------------------------
-- 5. MEASURED TAPE ACTUALS (VERSIONED & REVISABLE)
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS session_tape_actuals (
    actual_id TEXT PRIMARY KEY,
    session_date DATE NOT NULL,
    ticker TEXT NOT NULL,
    revision_seq INTEGER NOT NULL DEFAULT 1,   -- Monotonic revision for respun/corrected tape facts
    contract_id TEXT,
    source_system TEXT NOT NULL,               -- 'LIVE_STORAGE_PARQUET', 'FUSED_HISTORICAL', 'LEGACY_MIGRATION'
    
    -- Ground Truth OHLC & Excursions
    session_open REAL NOT NULL,
    session_high REAL NOT NULL,
    session_low REAL NOT NULL,
    session_close REAL NOT NULL,
    rth_close REAL NOT NULL,
    hod_timestamp_utc TIMESTAMP,
    lod_timestamp_utc TIMESTAMP,
    session_range_bps REAL NOT NULL,
    
    -- Canonical EOD Classifications
    day_type_classification TEXT NOT NULL,     -- 'R1', 'R2', 'DNP', 'DWP', 'ROTATIONAL_CHOP'
    eod_pattern_classification TEXT,
    
    -- Data Quality & Provenance
    expected_bar_count INTEGER,
    actual_bar_count INTEGER,
    content_hash TEXT NOT NULL,
    quality_state TEXT NOT NULL,               -- 'CLEAN', 'SUSPECT_TICKS', 'INCOMPLETE_BARS', 'SCHEDULED_SHORT_SESSION', 'LEGACY_UNVERIFIED'
    supersedes_actual_id TEXT,
    received_at_utc TIMESTAMP NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now')),
    created_at_utc TIMESTAMP NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now')),
    FOREIGN KEY (supersedes_actual_id) REFERENCES session_tape_actuals(actual_id),
    CONSTRAINT ck_no_self_supersession_tape CHECK (supersedes_actual_id <> actual_id),
    UNIQUE(session_date, ticker, revision_seq)
);

-- ----------------------------------------------------------------------------
-- 6. BROKER EXECUTIONS & RISKGUARD INTERVENTIONS
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS execution_events (
    execution_id TEXT PRIMARY KEY,
    session_date DATE NOT NULL,
    ticker TEXT NOT NULL,
    account_id TEXT NOT NULL,
    broker_execution_id TEXT NOT NULL,
    broker_order_id TEXT NOT NULL,
    client_order_id TEXT,
    order_action TEXT NOT NULL,                -- 'BUY', 'SELL', 'SELL_SHORT'
    order_type TEXT NOT NULL,                  -- 'MARKET', 'LIMIT', 'STOP_MARKET'
    quantity INTEGER NOT NULL,
    fill_price REAL NOT NULL,
    commission_usd REAL DEFAULT 0.0,
    slippage_bps REAL,
    strategy_version_id TEXT,
    idempotency_key TEXT NOT NULL,
    event_timestamp_utc TIMESTAMP NOT NULL,
    created_at_utc TIMESTAMP NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now')),
    UNIQUE(account_id, broker_execution_id)
);

CREATE TABLE IF NOT EXISTS intervention_events (
    intervention_id TEXT PRIMARY KEY,
    session_date DATE NOT NULL,
    ticker TEXT NOT NULL,
    account_id TEXT NOT NULL,
    trade_id TEXT,
    client_order_id TEXT,
    broker_order_id TEXT,
    source_event_id TEXT,
    corrects_intervention_id TEXT,
    plan_snapshot_id TEXT,
    plan_amendment_id TEXT,
    strategy_version_id TEXT,
    guard_config_hash TEXT,
    producer TEXT NOT NULL,                    -- 'NT8_RISKGUARD_CS', 'PYTHON_DEVIATION_ANNOTATOR', 'MANUAL'
    producer_version TEXT NOT NULL,
    authority_class TEXT NOT NULL,             -- 'HARD_LOCKOUT_ENFORCED', 'SOFT_FRICTION_PROMPTED', 'OBSERVED_DEVIATION_ANNOTATION'
    action_mode TEXT NOT NULL,                 -- 'ACTING', 'SHADOW'
    rule_id TEXT NOT NULL,
    rule_version TEXT NOT NULL,
    observed_value REAL,
    threshold_value REAL,
    enforced BOOLEAN NOT NULL,
    override_requested BOOLEAN DEFAULT FALSE,
    override_accepted BOOLEAN DEFAULT FALSE,
    override_actor TEXT,
    override_acknowledged_at_utc TIMESTAMP,
    idempotency_key TEXT NOT NULL,
    event_timestamp_utc TIMESTAMP NOT NULL,
    created_at_utc TIMESTAMP DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now')),
    FOREIGN KEY (plan_snapshot_id) REFERENCES plan_snapshots(plan_snapshot_id),
    FOREIGN KEY (plan_amendment_id) REFERENCES plan_amendments(amendment_id),
    UNIQUE(producer, account_id, idempotency_key)
);

-- ----------------------------------------------------------------------------
-- 7. DELIBERATE PRACTICE & BEHAVIORAL DECLARATIONS
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS drill_attempts (
    attempt_id TEXT PRIMARY KEY,
    drill_id TEXT NOT NULL,
    drill_type TEXT NOT NULL,                  -- 'RECOGNITION', 'BRACKET_DISCIPLINE', 'REVERSAL_COUNTER'
    dataset_split TEXT NOT NULL,               -- 'TRAINING', 'CALIBRATION', 'ASSESSMENT'

    -- Locked User Declarations
    declared_bias TEXT NOT NULL,
    declared_setup TEXT NOT NULL,
    declared_entry_price REAL,
    declared_stop_bps REAL,
    declared_target_bps REAL,
    answer_locked_at_utc TIMESTAMP NOT NULL,

    -- Process Score & Feedback
    process_adherence_score REAL NOT NULL,     -- 0.0 to 100.0
    rule_match_flag BOOLEAN NOT NULL,
    latency_ms INTEGER NOT NULL,
    review_notes TEXT,
    created_at_utc TIMESTAMP NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now'))
);

-- Sealed drill ground truth: persisted by the custodian process, never returned to callers
-- during drill generation.  Only the evaluation path reads this table.
CREATE TABLE IF NOT EXISTS drill_sealed_answers (
    drill_id TEXT PRIMARY KEY,
    true_session_date DATE NOT NULL,
    true_ticker TEXT NOT NULL,
    true_target_bps REAL NOT NULL,
    true_stop_bps REAL NOT NULL,
    true_bias TEXT NOT NULL,
    true_setup TEXT NOT NULL,
    is_locked BOOLEAN NOT NULL DEFAULT FALSE,
    drill_type TEXT NOT NULL DEFAULT 'RECOGNITION',
    dataset_split TEXT NOT NULL DEFAULT 'TRAINING',
    custody_token TEXT,
    created_at_utc TIMESTAMP NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now'))
);

-- Persisted split-partition registry: anti-memorization invariant survives process restarts.
CREATE TABLE IF NOT EXISTS drill_split_registry (
    session_date DATE NOT NULL,
    ticker TEXT NOT NULL,
    dataset_split TEXT NOT NULL,
    registered_at_utc TIMESTAMP NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now')),
    PRIMARY KEY (session_date, ticker, dataset_split)
);

CREATE TABLE IF NOT EXISTS behavioral_declarations (
    declaration_id TEXT PRIMARY KEY,
    session_date DATE NOT NULL,
    user_id TEXT NOT NULL,
    declaration_type TEXT NOT NULL,            -- 'PRE_SESSION_STATE', 'POST_SESSION_REFLECTION', 'HABIT_LOG'
    energy_rating INTEGER,                     -- 1 to 5
    emotional_state TEXT,
    reflection_notes TEXT NOT NULL,
    created_at_utc TIMESTAMP NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now'))
);

-- ----------------------------------------------------------------------------
-- 8. REVIEW QUEUES & TRANSITION LEDGERS
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS unmatched_link_events (
    link_event_id TEXT PRIMARY KEY,
    execution_id TEXT NOT NULL,
    candidate_opportunity_ids_json TEXT NOT NULL,
    resolution_status TEXT NOT NULL,           -- 'OPEN', 'RESOLVED_LINKED', 'RESOLVED_DISCRETIONARY', 'REJECTED'
    resolved_opportunity_id TEXT,
    resolution_notes TEXT,
    resolved_by TEXT,
    event_timestamp_utc TIMESTAMP NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now')),
    created_at_utc TIMESTAMP NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now')),
    FOREIGN KEY (execution_id) REFERENCES execution_events(execution_id)
);

CREATE TABLE IF NOT EXISTS candidate_finding_events (
    finding_event_id TEXT PRIMARY KEY,
    finding_id TEXT NOT NULL,
    model_version_id TEXT NOT NULL,
    pipeline_stage TEXT NOT NULL,              -- 'DISCOVERY', 'WALK_FORWARD', 'SHADOW_SEALED', 'PROMOTED', 'REJECTED'
    evaluation_result_json TEXT NOT NULL,
    statistical_power REAL,
    fdr_q_value REAL,
    actor TEXT NOT NULL,
    event_timestamp_utc TIMESTAMP NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now')),
    created_at_utc TIMESTAMP NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now'))
);

CREATE TABLE IF NOT EXISTS sealed_holdouts (
    holdout_dataset_id TEXT PRIMARY KEY,
    content_hash TEXT NOT NULL,                -- sha256 of serialized features + labels
    features_json TEXT NOT NULL,
    labels_json TEXT NOT NULL,
    benchmark_metric REAL NOT NULL,
    expected_effect_size_d REAL NOT NULL,
    registered_at_utc TIMESTAMP NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now'))
);

-- ----------------------------------------------------------------------------
-- 9. IMMUTABLE VERSION REGISTRIES
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS strategy_versions (
    strategy_version_id TEXT PRIMARY KEY,      -- e.g. 'STRAT_ALN_LPEU_V0_1'
    strategy_family TEXT NOT NULL,             -- 'ALN_LPEU', 'FIRECRACKER', 'GOALPOST_BB', 'P12_MID'
    version_tag TEXT NOT NULL,                 -- '0.1.0'
    content_hash TEXT NOT NULL,                -- SHA-256 of frozen JSON definition
    rules_doc_path TEXT NOT NULL,
    execution_policy_json TEXT NOT NULL,       -- Target brackets, stops, scale-out policy
    status TEXT NOT NULL,                      -- 'EXPERIMENTAL_CAPTURE_ONLY', 'PROMOTED', 'RETIRED'
    created_at_utc TIMESTAMP NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now'))
);

CREATE TABLE IF NOT EXISTS model_versions (
    model_version_id TEXT PRIMARY KEY,         -- e.g. 'MOD_PROFILER_5CLASS_V1'
    model_family TEXT NOT NULL,                -- 'PROFILER_DAY_TYPE'
    version_tag TEXT NOT NULL,
    parameter_hash TEXT NOT NULL,
    feature_manifest_json TEXT NOT NULL,
    calibration_metrics_json TEXT NOT NULL,
    status TEXT NOT NULL,                      -- 'SHADOW', 'CHAMPION', 'RETIRED'
    created_at_utc TIMESTAMP NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now'))
);

-- ----------------------------------------------------------------------------
-- 10. OPERATIONAL & STAGING TABLES
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS legacy_projection_outbox (
    outbox_id TEXT PRIMARY KEY,
    destination_db TEXT NOT NULL,              -- 'system_wargames', 'market_actuals', 'mickey_ground_truth'
    canonical_table TEXT NOT NULL,
    canonical_id TEXT NOT NULL,
    schema_version TEXT NOT NULL,
    payload_json TEXT NOT NULL,
    status TEXT NOT NULL,                      -- 'PENDING', 'PROJECTED', 'FAILED', 'DEAD_LETTER'
    attempt_count INTEGER DEFAULT 0,
    last_error TEXT,
    lease_token TEXT,
    lease_expires_at_utc TIMESTAMP,
    created_at_utc TIMESTAMP DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now')),
    projected_at_utc TIMESTAMP
);

CREATE TABLE IF NOT EXISTS broker_ingest_state (
    endpoint_name TEXT NOT NULL,
    account_id TEXT NOT NULL,
    last_cursor TEXT NOT NULL,
    last_event_timestamp_utc TIMESTAMP NOT NULL,
    updated_at_utc TIMESTAMP DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now')),
    PRIMARY KEY (endpoint_name, account_id)
);

-- ----------------------------------------------------------------------------
-- 11. DETERMINISTIC PROJECTION VIEWS
-- ----------------------------------------------------------------------------
CREATE VIEW IF NOT EXISTS v_information_items_active AS
SELECT i.*, 
       COALESCE((
           SELECT r.review_state FROM information_item_review_events r
           WHERE r.information_id = i.information_id
           ORDER BY r.event_timestamp_utc DESC, r.created_at_utc DESC, r.rowid DESC LIMIT 1
       ), 'CAPTURED') AS active_review_state
FROM information_items i;

CREATE VIEW IF NOT EXISTS v_session_tape_actuals_current AS
SELECT a.* FROM session_tape_actuals a
WHERE a.revision_seq = (
    SELECT MAX(a2.revision_seq) FROM session_tape_actuals a2
    WHERE a2.session_date = a.session_date AND a2.ticker = a.ticker
);

CREATE VIEW IF NOT EXISTS v_unmatched_links_open AS
SELECT u.* FROM unmatched_link_events u
WHERE u.resolution_status = 'OPEN'
  AND u.rowid = (
      SELECT u2.rowid FROM unmatched_link_events u2
      WHERE u2.execution_id = u.execution_id
      ORDER BY u2.event_timestamp_utc DESC, u2.created_at_utc DESC, u2.rowid DESC LIMIT 1
  );

CREATE VIEW IF NOT EXISTS v_candidate_findings_staged AS
SELECT c.* FROM candidate_finding_events c
WHERE c.rowid = (
    SELECT c2.rowid FROM candidate_finding_events c2
    WHERE c2.finding_id = c.finding_id
    ORDER BY c2.event_timestamp_utc DESC, c2.created_at_utc DESC, c2.rowid DESC LIMIT 1
);

-- ============================================================================
-- 12. 38 IMMUTABILITY TRIGGERS (19 PROTECTED APPEND-ONLY TABLES)
-- ============================================================================

-- 1. information_items
CREATE TRIGGER IF NOT EXISTS trg_prevent_update_information_items
BEFORE UPDATE ON information_items BEGIN
    SELECT RAISE(FAIL, 'UPDATE operation prohibited on immutable table information_items');
END;
CREATE TRIGGER IF NOT EXISTS trg_prevent_delete_information_items
BEFORE DELETE ON information_items BEGIN
    SELECT RAISE(FAIL, 'DELETE operation prohibited on immutable table information_items');
END;

-- 2. information_item_review_events
CREATE TRIGGER IF NOT EXISTS trg_prevent_update_information_item_review_events
BEFORE UPDATE ON information_item_review_events BEGIN
    SELECT RAISE(FAIL, 'UPDATE operation prohibited on immutable table information_item_review_events');
END;
CREATE TRIGGER IF NOT EXISTS trg_prevent_delete_information_item_review_events
BEFORE DELETE ON information_item_review_events BEGIN
    SELECT RAISE(FAIL, 'DELETE operation prohibited on immutable table information_item_review_events');
END;

-- 3. plan_snapshots
CREATE TRIGGER IF NOT EXISTS trg_prevent_update_plan_snapshots
BEFORE UPDATE ON plan_snapshots BEGIN
    SELECT RAISE(FAIL, 'UPDATE operation prohibited on immutable table plan_snapshots');
END;
CREATE TRIGGER IF NOT EXISTS trg_prevent_delete_plan_snapshots
BEFORE DELETE ON plan_snapshots BEGIN
    SELECT RAISE(FAIL, 'DELETE operation prohibited on immutable table plan_snapshots');
END;

-- 4. plan_lifecycle_events
CREATE TRIGGER IF NOT EXISTS trg_prevent_update_plan_lifecycle_events
BEFORE UPDATE ON plan_lifecycle_events BEGIN
    SELECT RAISE(FAIL, 'UPDATE operation prohibited on immutable table plan_lifecycle_events');
END;
CREATE TRIGGER IF NOT EXISTS trg_prevent_delete_plan_lifecycle_events
BEFORE DELETE ON plan_lifecycle_events BEGIN
    SELECT RAISE(FAIL, 'DELETE operation prohibited on immutable table plan_lifecycle_events');
END;

-- 5. plan_amendments
CREATE TRIGGER IF NOT EXISTS trg_prevent_update_plan_amendments
BEFORE UPDATE ON plan_amendments BEGIN
    SELECT RAISE(FAIL, 'UPDATE operation prohibited on immutable table plan_amendments');
END;
CREATE TRIGGER IF NOT EXISTS trg_prevent_delete_plan_amendments
BEFORE DELETE ON plan_amendments BEGIN
    SELECT RAISE(FAIL, 'DELETE operation prohibited on immutable table plan_amendments');
END;

-- 6. forecast_run_inputs
CREATE TRIGGER IF NOT EXISTS trg_prevent_update_forecast_run_inputs
BEFORE UPDATE ON forecast_run_inputs BEGIN
    SELECT RAISE(FAIL, 'UPDATE operation prohibited on immutable table forecast_run_inputs');
END;
CREATE TRIGGER IF NOT EXISTS trg_prevent_delete_forecast_run_inputs
BEFORE DELETE ON forecast_run_inputs BEGIN
    SELECT RAISE(FAIL, 'DELETE operation prohibited on immutable table forecast_run_inputs');
END;

-- 7. forecast_snapshots
CREATE TRIGGER IF NOT EXISTS trg_prevent_update_forecast_snapshots
BEFORE UPDATE ON forecast_snapshots BEGIN
    SELECT RAISE(FAIL, 'UPDATE operation prohibited on immutable table forecast_snapshots');
END;
CREATE TRIGGER IF NOT EXISTS trg_prevent_delete_forecast_snapshots
BEFORE DELETE ON forecast_snapshots BEGIN
    SELECT RAISE(FAIL, 'DELETE operation prohibited on immutable table forecast_snapshots');
END;

-- 8. signal_opportunities
CREATE TRIGGER IF NOT EXISTS trg_prevent_update_signal_opportunities
BEFORE UPDATE ON signal_opportunities BEGIN
    SELECT RAISE(FAIL, 'UPDATE operation prohibited on immutable table signal_opportunities');
END;
CREATE TRIGGER IF NOT EXISTS trg_prevent_delete_signal_opportunities
BEFORE DELETE ON signal_opportunities BEGIN
    SELECT RAISE(FAIL, 'DELETE operation prohibited on immutable table signal_opportunities');
END;

-- 9. signal_disposition_events
CREATE TRIGGER IF NOT EXISTS trg_prevent_update_signal_disposition_events
BEFORE UPDATE ON signal_disposition_events BEGIN
    SELECT RAISE(FAIL, 'UPDATE operation prohibited on immutable table signal_disposition_events');
END;
CREATE TRIGGER IF NOT EXISTS trg_prevent_delete_signal_disposition_events
BEFORE DELETE ON signal_disposition_events BEGIN
    SELECT RAISE(FAIL, 'DELETE operation prohibited on immutable table signal_disposition_events');
END;

-- 10. signal_outcomes
CREATE TRIGGER IF NOT EXISTS trg_prevent_update_signal_outcomes
BEFORE UPDATE ON signal_outcomes BEGIN
    SELECT RAISE(FAIL, 'UPDATE operation prohibited on immutable table signal_outcomes');
END;
CREATE TRIGGER IF NOT EXISTS trg_prevent_delete_signal_outcomes
BEFORE DELETE ON signal_outcomes BEGIN
    SELECT RAISE(FAIL, 'DELETE operation prohibited on immutable table signal_outcomes');
END;

-- 11. session_tape_actuals
CREATE TRIGGER IF NOT EXISTS trg_prevent_update_session_tape_actuals
BEFORE UPDATE ON session_tape_actuals BEGIN
    SELECT RAISE(FAIL, 'UPDATE operation prohibited on immutable table session_tape_actuals');
END;
CREATE TRIGGER IF NOT EXISTS trg_prevent_delete_session_tape_actuals
BEFORE DELETE ON session_tape_actuals BEGIN
    SELECT RAISE(FAIL, 'DELETE operation prohibited on immutable table session_tape_actuals');
END;

-- 12. execution_events
CREATE TRIGGER IF NOT EXISTS trg_prevent_update_execution_events
BEFORE UPDATE ON execution_events BEGIN
    SELECT RAISE(FAIL, 'UPDATE operation prohibited on immutable table execution_events');
END;
CREATE TRIGGER IF NOT EXISTS trg_prevent_delete_execution_events
BEFORE DELETE ON execution_events BEGIN
    SELECT RAISE(FAIL, 'DELETE operation prohibited on immutable table execution_events');
END;

-- 13. intervention_events
CREATE TRIGGER IF NOT EXISTS trg_prevent_update_intervention_events
BEFORE UPDATE ON intervention_events BEGIN
    SELECT RAISE(FAIL, 'UPDATE operation prohibited on immutable table intervention_events');
END;
CREATE TRIGGER IF NOT EXISTS trg_prevent_delete_intervention_events
BEFORE DELETE ON intervention_events BEGIN
    SELECT RAISE(FAIL, 'DELETE operation prohibited on immutable table intervention_events');
END;

-- 14. drill_attempts
CREATE TRIGGER IF NOT EXISTS trg_prevent_update_drill_attempts
BEFORE UPDATE ON drill_attempts BEGIN
    SELECT RAISE(FAIL, 'UPDATE operation prohibited on immutable table drill_attempts');
END;
CREATE TRIGGER IF NOT EXISTS trg_prevent_delete_drill_attempts
BEFORE DELETE ON drill_attempts BEGIN
    SELECT RAISE(FAIL, 'DELETE operation prohibited on immutable table drill_attempts');
END;

-- 14a. drill_sealed_answers
CREATE TRIGGER IF NOT EXISTS trg_prevent_update_drill_sealed_answers
BEFORE UPDATE ON drill_sealed_answers BEGIN
    SELECT RAISE(FAIL, 'UPDATE operation prohibited on immutable table drill_sealed_answers');
END;
CREATE TRIGGER IF NOT EXISTS trg_prevent_delete_drill_sealed_answers
BEFORE DELETE ON drill_sealed_answers BEGIN
    SELECT RAISE(FAIL, 'DELETE operation prohibited on immutable table drill_sealed_answers');
END;

-- 14b. drill_split_registry
CREATE TRIGGER IF NOT EXISTS trg_prevent_update_drill_split_registry
BEFORE UPDATE ON drill_split_registry BEGIN
    SELECT RAISE(FAIL, 'UPDATE operation prohibited on immutable table drill_split_registry');
END;
CREATE TRIGGER IF NOT EXISTS trg_prevent_delete_drill_split_registry
BEFORE DELETE ON drill_split_registry BEGIN
    SELECT RAISE(FAIL, 'DELETE operation prohibited on immutable table drill_split_registry');
END;

-- 15. behavioral_declarations
CREATE TRIGGER IF NOT EXISTS trg_prevent_update_behavioral_declarations
BEFORE UPDATE ON behavioral_declarations BEGIN
    SELECT RAISE(FAIL, 'UPDATE operation prohibited on immutable table behavioral_declarations');
END;
CREATE TRIGGER IF NOT EXISTS trg_prevent_delete_behavioral_declarations
BEFORE DELETE ON behavioral_declarations BEGIN
    SELECT RAISE(FAIL, 'DELETE operation prohibited on immutable table behavioral_declarations');
END;

-- 16. unmatched_link_events
CREATE TRIGGER IF NOT EXISTS trg_prevent_update_unmatched_link_events
BEFORE UPDATE ON unmatched_link_events BEGIN
    SELECT RAISE(FAIL, 'UPDATE operation prohibited on immutable table unmatched_link_events');
END;
CREATE TRIGGER IF NOT EXISTS trg_prevent_delete_unmatched_link_events
BEFORE DELETE ON unmatched_link_events BEGIN
    SELECT RAISE(FAIL, 'DELETE operation prohibited on immutable table unmatched_link_events');
END;

-- 17. candidate_finding_events
CREATE TRIGGER IF NOT EXISTS trg_prevent_update_candidate_finding_events
BEFORE UPDATE ON candidate_finding_events BEGIN
    SELECT RAISE(FAIL, 'UPDATE operation prohibited on immutable table candidate_finding_events');
END;
CREATE TRIGGER IF NOT EXISTS trg_prevent_delete_candidate_finding_events
BEFORE DELETE ON candidate_finding_events BEGIN
    SELECT RAISE(FAIL, 'DELETE operation prohibited on immutable table candidate_finding_events');
END;

-- 18. sealed_holdouts
CREATE TRIGGER IF NOT EXISTS trg_prevent_update_sealed_holdouts
BEFORE UPDATE ON sealed_holdouts BEGIN
    SELECT RAISE(FAIL, 'UPDATE operation prohibited on immutable table sealed_holdouts');
END;
CREATE TRIGGER IF NOT EXISTS trg_prevent_delete_sealed_holdouts
BEFORE DELETE ON sealed_holdouts BEGIN
    SELECT RAISE(FAIL, 'DELETE operation prohibited on immutable table sealed_holdouts');
END;

-- 18. strategy_versions
CREATE TRIGGER IF NOT EXISTS trg_prevent_update_strategy_versions
BEFORE UPDATE ON strategy_versions BEGIN
    SELECT RAISE(FAIL, 'UPDATE operation prohibited on immutable table strategy_versions');
END;
CREATE TRIGGER IF NOT EXISTS trg_prevent_delete_strategy_versions
BEFORE DELETE ON strategy_versions BEGIN
    SELECT RAISE(FAIL, 'DELETE operation prohibited on immutable table strategy_versions');
END;

-- 19. model_versions
CREATE TRIGGER IF NOT EXISTS trg_prevent_update_model_versions
BEFORE UPDATE ON model_versions BEGIN
    SELECT RAISE(FAIL, 'UPDATE operation prohibited on immutable table model_versions');
END;
CREATE TRIGGER IF NOT EXISTS trg_prevent_delete_model_versions
BEFORE DELETE ON model_versions BEGIN
    SELECT RAISE(FAIL, 'DELETE operation prohibited on immutable table model_versions');
END;

-- 23. MODEL_DEPLOYMENT_EVENTS (Append-Only Deployment Ledger)
CREATE TABLE IF NOT EXISTS model_deployment_events (
    deployment_event_id TEXT PRIMARY KEY,     -- UUID v4
    model_version_id TEXT NOT NULL,           -- FK -> model_versions.model_version_id
    tier INTEGER NOT NULL,                    -- 1, 2, 3, 4
    deployment_status TEXT NOT NULL,          -- 'CANDIDATE', 'CHAMPION', 'SHADOW', 'RETIRED', 'REJECTED'
    eval_metrics_json TEXT,                   -- JSON metrics payload
    actor TEXT NOT NULL,                      -- Operator or orchestrator ID
    reason TEXT,                              -- Rationale for deployment transition
    event_timestamp_utc TIMESTAMP NOT NULL,
    created_at_utc TIMESTAMP DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now')),
    FOREIGN KEY (model_version_id) REFERENCES model_versions (model_version_id)
);

CREATE TRIGGER IF NOT EXISTS trg_immutable_model_deployment_events_update
BEFORE UPDATE ON model_deployment_events
BEGIN
    SELECT RAISE(ABORT, 'MUTATION_FORBIDDEN: model_deployment_events is an immutable ledger');
END;

CREATE TRIGGER IF NOT EXISTS trg_immutable_model_deployment_events_delete
BEFORE DELETE ON model_deployment_events
BEGIN
    SELECT RAISE(ABORT, 'MUTATION_FORBIDDEN: model_deployment_events is an immutable ledger');
END;
