"""Example usage of the PhasePlanner for breaking down tasks.

This script demonstrates how to use the PhasePlanner to:
1. Initialize all required components
2. Create a run for tracking
3. Generate phase breakdown from issue documentation
4. Interactively approve the plan
5. Save phases and artifacts
"""

import asyncio
import logging
from pathlib import Path

from orchestrator.config_loader import load_config
from orchestrator.llm_client import OllamaClient
from orchestrator.state_manager import StateManager
from orchestrator.planner import PhasePlanner
from repo_brain.rag_system import RAGSystem


# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)


async def main():
    """Example planner usage."""
    
    # Step 1: Load configuration
    print("Loading configuration...")
    config = load_config()
    
    # Step 2: Initialize components
    print("Initializing components...")
    
    # Initialize LLM client
    llm_client = OllamaClient(
        base_url=config.ollama.base_url,
        models_config=config.models,
        timeout=config.ollama.timeout
    )
    
    # Initialize state manager
    state_manager = StateManager(db_path=config.state_db_path)
    await state_manager.initialize()
    
    # Initialize RAG system
    repo_path = Path.cwd()  # Use current directory as repo
    rag_system = RAGSystem(
        repo_path=str(repo_path),
        config=config.rag
    )
    
    # Initialize planner
    planner = PhasePlanner(
        config=config,
        llm_client=llm_client,
        rag_system=rag_system,
        state_manager=state_manager
    )
    
    # Step 3: Create a run
    print("\nCreating run...")
    run_id = await state_manager.create_run(
        repo_path=str(repo_path),
        branch="main",
        issue_number=None,
        config_snapshot=config.model_dump_json()
    )
    print(f"Run created: {run_id}")
    
    # Step 4: Prepare issue documentation
    # In a real scenario, this would be loaded from a GitHub issue, 
    # a user-provided file, or other source
    issue_doc_path = "docs/issue_example.md"
    
    # For this example, create a sample issue if it doesn't exist
    issue_path = Path(issue_doc_path)
    if not issue_path.exists():
        issue_path.parent.mkdir(parents=True, exist_ok=True)
        issue_path.write_text("""
# Example Task: Add User Authentication

## Description
Implement user authentication system with the following features:
- User registration with email verification
- Login/logout functionality
- Password reset flow
- Session management
- JWT token-based authentication

## Requirements
- Use existing database schema
- Integrate with email service
- Add authentication middleware
- Create login/register UI components
- Write unit tests for auth flows

## Acceptance Criteria
- Users can register with email/password
- Email verification required before login
- Password reset sends email with token
- Sessions persist across browser restarts
- All endpoints protected by auth middleware
- Test coverage > 80%
""")
        print(f"Created sample issue at: {issue_doc_path}")
    
    # Step 5: Run planning session
    print("\nStarting planning session...")
    print("This will:")
    print("  1. Analyze the repository")
    print("  2. Generate phase breakdown")
    print("  3. Show interactive approval UI")
    print("  4. Save approved phases")
    print()
    
    try:
        phases = await planner.run_planning_session(
            run_id=run_id,
            issue_doc_path=issue_doc_path,
            repo_path=str(repo_path),
            branch="main"
        )
        
        # Step 6: Display results
        print("\n" + "="*60)
        print("PHASE PLAN CREATED SUCCESSFULLY")
        print("="*60)
        print(f"\nRun ID: {run_id}")
        print(f"Total Phases: {len(phases)}")
        print("\nPhases:")
        for phase in phases:
            print(f"  {phase['phase_number']}. {phase['title']} ({phase['size']})")
        
        print("\nArtifacts saved to:")
        print(f"  data/artifacts/{run_id}/planning/")
        print("    - PhasePlan.json")
        print("    - PhasePlan.md")
        for i in range(len(phases)):
            print(f"    - Phase_{i+1}_Detail.md")
        
        # Step 7: Load and verify phases from state
        print("\nVerifying saved phases...")
        loaded_phases = await planner.load_phase_plan(run_id)
        print(f"Loaded {len(loaded_phases)} phases from artifacts")
        
        # Step 8: Display next steps
        print("\n" + "="*60)
        print("NEXT STEPS")
        print("="*60)
        print("1. Review the generated phase plan:")
        print(f"   cat data/artifacts/{run_id}/planning/PhasePlan.md")
        print()
        print("2. Start execution with Phase 1:")
        print(f"   python -m orchestrator.executor --run-id {run_id} --phase 1")
        print()
        print("3. Monitor progress:")
        print(f"   python -m orchestrator.monitor --run-id {run_id}")
        print()
        
    except Exception as e:
        logger.error(f"Planning failed: {e}", exc_info=True)
        print(f"\nERROR: Planning failed - {e}")
        print("Check logs for details")
        return 1
    
    # Cleanup
    await state_manager.close()
    
    return 0


if __name__ == '__main__':
    exit_code = asyncio.run(main())
    exit(exit_code)
