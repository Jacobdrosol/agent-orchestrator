"""Database schema definitions for Agent Orchestrator state management."""

import logging
from typing import Optional
import aiosqlite

logger = logging.getLogger(__name__)

SCHEMA_VERSION = 1

CREATE_TABLES_SQL = """
-- Schema version tracking
CREATE TABLE IF NOT EXISTS schema_version (
    version INTEGER PRIMARY KEY,
    applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Orchestration runs
CREATE TABLE IF NOT EXISTS runs (
    run_id TEXT PRIMARY KEY,
    created_at TIMESTAMP NOT NULL,
    updated_at TIMESTAMP NOT NULL,
    status TEXT NOT NULL CHECK(status IN ('planning', 'executing', 'paused', 'completed', 'failed', 'aborted')),
    repo_path TEXT NOT NULL,
    branch TEXT NOT NULL,
    documentation_path TEXT NOT NULL,
    config_snapshot TEXT NOT NULL,
    total_phases INTEGER NOT NULL DEFAULT 0,
    completed_phases INTEGER NOT NULL DEFAULT 0,
    current_phase_id TEXT,
    error_message TEXT
);

-- Execution phases
CREATE TABLE IF NOT EXISTS phases (
    phase_id TEXT PRIMARY KEY,
    run_id TEXT NOT NULL,
    phase_number INTEGER NOT NULL,
    title TEXT NOT NULL,
    intent TEXT NOT NULL,
    size TEXT NOT NULL CHECK(size IN ('small', 'medium', 'large')),
    status TEXT NOT NULL CHECK(status IN ('pending', 'in_progress', 'completed', 'failed', 'skipped')),
    created_at TIMESTAMP NOT NULL,
    started_at TIMESTAMP,
    completed_at TIMESTAMP,
    spec_path TEXT,
    plan_json TEXT NOT NULL,
    branch_name TEXT,
    retry_count INTEGER NOT NULL DEFAULT 0,
    max_retries INTEGER NOT NULL,
    FOREIGN KEY (run_id) REFERENCES runs(run_id)
);

-- Execution attempts
CREATE TABLE IF NOT EXISTS executions (
    execution_id TEXT PRIMARY KEY,
    phase_id TEXT NOT NULL,
    pass_number INTEGER NOT NULL,
    started_at TIMESTAMP NOT NULL,
    completed_at TIMESTAMP,
    status TEXT NOT NULL CHECK(status IN ('running', 'completed', 'failed')),
    copilot_input_path TEXT NOT NULL,
    copilot_output_path TEXT,
    copilot_summary TEXT,
    execution_mode TEXT NOT NULL CHECK(execution_mode IN ('direct', 'branch')),
    error_message TEXT,
    FOREIGN KEY (phase_id) REFERENCES phases(phase_id)
);

-- Findings from verification
CREATE TABLE IF NOT EXISTS findings (
    finding_id TEXT PRIMARY KEY,
    execution_id TEXT NOT NULL,
    severity TEXT NOT NULL CHECK(severity IN ('major', 'medium', 'minor')),
    category TEXT NOT NULL CHECK(category IN ('build', 'test', 'lint', 'security', 'spec_validation', 'custom')),
    title TEXT NOT NULL,
    description TEXT NOT NULL,
    evidence TEXT NOT NULL,
    suggested_fix TEXT,
    resolved BOOLEAN NOT NULL DEFAULT 0,
    created_at TIMESTAMP NOT NULL,
    FOREIGN KEY (execution_id) REFERENCES executions(execution_id)
);

-- Artifacts produced
CREATE TABLE IF NOT EXISTS artifacts (
    artifact_id TEXT PRIMARY KEY,
    run_id TEXT NOT NULL,
    phase_id TEXT,
    execution_id TEXT,
    artifact_type TEXT NOT NULL CHECK(artifact_type IN ('phase_plan', 'spec', 'copilot_output', 'findings_report', 'verification_log')),
    file_path TEXT NOT NULL,
    created_at TIMESTAMP NOT NULL,
    metadata TEXT,
    FOREIGN KEY (run_id) REFERENCES runs(run_id),
    FOREIGN KEY (phase_id) REFERENCES phases(phase_id),
    FOREIGN KEY (execution_id) REFERENCES executions(execution_id)
);

-- Manual interventions
CREATE TABLE IF NOT EXISTS manual_interventions (
    intervention_id TEXT PRIMARY KEY,
    phase_id TEXT NOT NULL,
    created_at TIMESTAMP NOT NULL,
    reason TEXT NOT NULL CHECK(reason IN ('max_retries_exceeded', 'user_requested', 'critical_error')),
    action_taken TEXT CHECK(action_taken IN ('resume', 'skip', 'modify_spec', 'abort')),
    notes TEXT,
    resolved_at TIMESTAMP,
    FOREIGN KEY (phase_id) REFERENCES phases(phase_id)
);

-- Indexes for common queries
CREATE INDEX IF NOT EXISTS idx_runs_status ON runs(status);
CREATE INDEX IF NOT EXISTS idx_phases_run_id ON phases(run_id);
CREATE INDEX IF NOT EXISTS idx_phases_status ON phases(status);
CREATE INDEX IF NOT EXISTS idx_executions_phase_id ON executions(phase_id);
CREATE INDEX IF NOT EXISTS idx_findings_execution_id ON findings(execution_id);
CREATE INDEX IF NOT EXISTS idx_findings_severity ON findings(severity);
CREATE INDEX IF NOT EXISTS idx_artifacts_run_id ON artifacts(run_id);
CREATE INDEX IF NOT EXISTS idx_interventions_phase_id ON manual_interventions(phase_id);
"""


async def initialize_database(db: aiosqlite.Connection) -> None:
    """Initialize database schema and apply migrations."""
    try:
        await db.executescript(CREATE_TABLES_SQL)
        
        # Check current schema version
        async with db.execute("SELECT version FROM schema_version ORDER BY version DESC LIMIT 1") as cursor:
            row = await cursor.fetchone()
            current_version = row[0] if row else 0
        
        if current_version < SCHEMA_VERSION:
            await db.execute(
                "INSERT INTO schema_version (version) VALUES (?)",
                (SCHEMA_VERSION,)
            )
            await db.commit()
            logger.info(f"Database schema initialized to version {SCHEMA_VERSION}")
        else:
            logger.debug(f"Database schema already at version {current_version}")
            
    except Exception as e:
        logger.error(f"Failed to initialize database: {e}")
        raise


async def get_schema_version(db: aiosqlite.Connection) -> int:
    """Get current schema version."""
    try:
        async with db.execute("SELECT version FROM schema_version ORDER BY version DESC LIMIT 1") as cursor:
            row = await cursor.fetchone()
            return row[0] if row else 0
    except:
        return 0
