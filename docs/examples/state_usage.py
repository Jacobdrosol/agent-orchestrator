"""Example usage of state management system.

This script demonstrates how to use the StateManager to track orchestration runs,
phases, executions, and findings.
"""

import asyncio
from datetime import datetime
from pathlib import Path

from orchestrator import StateManager


async def main():
    """Demonstrate state manager usage."""
    
    # Initialize state manager
    db_path = "data/example.db"
    artifact_path = "data/artifacts"
    
    async with StateManager(db_path, artifact_path) as sm:
        print("=== Creating New Run ===")
        
        # Create a new orchestration run
        run = await sm.create_run(
            repo_path="/path/to/repository",
            branch="main",
            doc_path="/path/to/documentation.md",
            config={
                "max_retries": 3,
                "copilot_mode": "direct",
                "findings_thresholds": {
                    "major": 0,
                    "medium": 0,
                    "minor": 5
                }
            }
        )
        
        print(f"Created run: {run.run_id}")
        print(f"Status: {run.status}")
        print(f"Repository: {run.repo_path}")
        print()
        
        # Update run status to executing
        await sm.update_run_status(run.run_id, "executing")
        
        print("=== Creating Phases ===")
        
        # Create Phase 1: Database Setup
        phase1 = await sm.create_phase(
            run_id=run.run_id,
            phase_number=1,
            title="Setup Database Schema",
            intent="Create initial database schema with user and product tables",
            plan={
                "files": [
                    "database/schema.sql",
                    "database/migrations/001_initial.sql"
                ],
                "acceptance_criteria": [
                    "Schema file created with all tables",
                    "Migration script runs without errors",
                    "Foreign key constraints properly defined"
                ],
                "dependencies": [],
                "risks": [
                    "Database connection issues",
                    "Schema conflicts with existing tables"
                ]
            },
            max_retries=3,
            size="medium"
        )
        
        print(f"Created Phase 1: {phase1.title}")
        print(f"  Phase ID: {phase1.phase_id}")
        print(f"  Status: {phase1.status}")
        print()
        
        # Create Phase 2: API Endpoints
        phase2 = await sm.create_phase(
            run_id=run.run_id,
            phase_number=2,
            title="Implement User API",
            intent="Create REST API endpoints for user management",
            plan={
                "files": [
                    "api/users.py",
                    "api/routes.py",
                    "tests/test_users.py"
                ],
                "acceptance_criteria": [
                    "CRUD endpoints implemented",
                    "All tests passing",
                    "API documentation generated"
                ],
                "dependencies": ["phase1"],
                "risks": [
                    "Authentication complexity",
                    "Rate limiting requirements"
                ]
            },
            max_retries=3,
            size="large"
        )
        
        print(f"Created Phase 2: {phase2.title}")
        print()
        
        print("=== Executing Phase 1 ===")
        
        # Start Phase 1
        await sm.update_phase_status(
            phase1.phase_id,
            "in_progress",
            started_at=datetime.now()
        )
        
        # Create execution attempt
        execution1 = await sm.create_execution(
            phase_id=phase1.phase_id,
            pass_number=1,
            copilot_input_path=f"artifacts/{run.run_id}/phase1_spec.md",
            execution_mode="direct"
        )
        
        print(f"Started execution: {execution1.execution_id}")
        print(f"  Pass number: {execution1.pass_number}")
        print()
        
        # Add some findings
        print("=== Recording Findings ===")
        
        finding1 = await sm.add_finding(
            execution_id=execution1.execution_id,
            severity="minor",
            category="lint",
            title="Missing docstring in schema.sql",
            description="The schema.sql file is missing header comments explaining its purpose",
            evidence="schema.sql:1",
            suggested_fix="Add a header comment block describing the schema"
        )
        
        print(f"Added finding: [{finding1.severity}] {finding1.title}")
        
        finding2 = await sm.add_finding(
            execution_id=execution1.execution_id,
            severity="minor",
            category="lint",
            title="Long line in migration script",
            description="Line exceeds 120 characters",
            evidence="migrations/001_initial.sql:45",
            suggested_fix="Break line at appropriate point"
        )
        
        print(f"Added finding: [{finding2.severity}] {finding2.title}")
        print()
        
        # Complete execution
        await sm.complete_execution(
            execution1.execution_id,
            copilot_output_path=f"artifacts/{run.run_id}/copilot_output_1.json",
            copilot_summary="Successfully created database schema with minor linting issues"
        )
        
        # Complete phase
        await sm.update_phase_status(
            phase1.phase_id,
            "completed",
            completed_at=datetime.now()
        )
        
        print("Phase 1 completed successfully")
        print()
        
        print("=== Executing Phase 2 (with retry) ===")
        
        # Start Phase 2
        await sm.update_phase_status(
            phase2.phase_id,
            "in_progress",
            started_at=datetime.now()
        )
        
        # First execution attempt - fails
        execution2_attempt1 = await sm.create_execution(
            phase_id=phase2.phase_id,
            pass_number=1,
            copilot_input_path=f"artifacts/{run.run_id}/phase2_spec.md",
            execution_mode="direct"
        )
        
        # Add major finding (test failure)
        await sm.add_finding(
            execution_id=execution2_attempt1.execution_id,
            severity="major",
            category="test",
            title="Test failure in test_create_user",
            description="User creation test fails with validation error",
            evidence="tests/test_users.py:25 - AssertionError: Expected 201, got 400",
            suggested_fix="Fix email validation logic in User model"
        )
        
        await sm.fail_execution(
            execution2_attempt1.execution_id,
            "Test failures detected"
        )
        
        # Increment retry count
        retry_count = await sm.increment_phase_retry(phase2.phase_id)
        print(f"Phase 2 attempt 1 failed, retry count: {retry_count}")
        print()
        
        # Second execution attempt - succeeds
        execution2_attempt2 = await sm.create_execution(
            phase_id=phase2.phase_id,
            pass_number=2,
            copilot_input_path=f"artifacts/{run.run_id}/phase2_spec_retry.md",
            execution_mode="direct"
        )
        
        # Add minor finding
        await sm.add_finding(
            execution_id=execution2_attempt2.execution_id,
            severity="minor",
            category="lint",
            title="Unused import",
            description="Module 'typing' imported but never used",
            evidence="api/users.py:3",
            suggested_fix="Remove unused import"
        )
        
        await sm.complete_execution(
            execution2_attempt2.execution_id,
            copilot_output_path=f"artifacts/{run.run_id}/copilot_output_2.json",
            copilot_summary="User API implemented successfully after fixing validation"
        )
        
        await sm.update_phase_status(
            phase2.phase_id,
            "completed",
            completed_at=datetime.now()
        )
        
        print("Phase 2 completed successfully on retry")
        print()
        
        # Complete run
        await sm.update_run_status(run.run_id, "completed")
        
        print("=== Run Summary ===")
        
        # Get summary
        summary = await sm.export_run_summary(run.run_id)
        
        print(f"Run Status: {summary.run.status}")
        print(f"Total Phases: {len(summary.phases)}")
        print(f"Completed Phases: {summary.run.completed_phases}")
        print(f"Total Executions: {summary.execution_count}")
        print(f"Findings by Severity:")
        for severity, count in summary.findings_summary.items():
            print(f"  {severity}: {count}")
        print()
        
        # Export to JSON
        export_path = f"artifacts/{run.run_id}/run_export.json"
        Path(export_path).parent.mkdir(parents=True, exist_ok=True)
        await sm.export_run_to_json(run.run_id, export_path)
        print(f"Exported run to: {export_path}")
        
        # Export to markdown
        markdown_path = f"artifacts/{run.run_id}/run_summary.md"
        markdown = summary.to_markdown()
        Path(markdown_path).parent.mkdir(parents=True, exist_ok=True)
        with open(markdown_path, 'w') as f:
            f.write(markdown)
        print(f"Exported summary to: {markdown_path}")
        print()
        
        print("=== Recovery Example ===")
        
        # Demonstrate recovery
        recoverable = await sm.get_recoverable_runs()
        print(f"Recoverable runs: {len(recoverable)}")
        
        if recoverable:
            recovered_run, current_phase = await sm.recover_run(recoverable[0].run_id)
            print(f"Would recover run: {recovered_run.run_id}")
            if current_phase:
                print(f"Current phase: {current_phase.title}")
        
        print()
        print("=== Database Statistics ===")
        
        stats = await sm.get_statistics()
        print(f"Total Runs: {stats['total_runs']}")
        print(f"Total Phases: {stats['total_phases']}")
        print(f"Findings by Severity: {stats['findings_by_severity']}")


if __name__ == "__main__":
    asyncio.run(main())
