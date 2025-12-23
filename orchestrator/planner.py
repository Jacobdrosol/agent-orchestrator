"""Phase planner orchestrator for breaking down tasks into executable phases."""

import json
import logging
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Any, Optional
from jinja2 import Environment, FileSystemLoader, TemplateNotFound

from orchestrator.config import OrchestratorConfig
from orchestrator.llm_client import OllamaClient, OllamaConnectionError, OllamaGenerationError
from orchestrator.state import StateManager
from orchestrator.prompt_builder import PromptBuilder
from orchestrator.phase_validator import PhaseValidator, ValidationError
from orchestrator.planner_ui import PlannerUI
from repo_brain.rag_system import RAGSystem

logger = logging.getLogger(__name__)


class PlannerError(Exception):
    """Raised when phase planning fails."""
    pass


class PhasePlanner:
    """Orchestrates phase planning with LLM generation and interactive approval."""

    def __init__(
        self,
        config: OrchestratorConfig,
        llm_client: OllamaClient,
        rag_system: RAGSystem,
        state_manager: StateManager
    ):
        """Initialize the phase planner.

        Args:
            config: Orchestrator configuration
            llm_client: LLM client for generation
            rag_system: RAG system for context retrieval
            state_manager: State manager for persistence
        """
        self.config = config
        self.llm_client = llm_client
        self.rag_system = rag_system
        self.state_manager = state_manager
        self.ui = PlannerUI()

        # Load prompt templates
        prompts_path = Path(config.base_path) / "config" / "prompts.yaml"
        if not prompts_path.exists():
            raise PlannerError(f"Prompts configuration not found: {prompts_path}")
        self.prompt_builder = PromptBuilder(str(prompts_path))

        # Load Jinja2 templates
        templates_dir = Path(config.base_path) / "templates"
        if not templates_dir.exists():
            raise PlannerError(f"Templates directory not found: {templates_dir}")
        self.jinja_env = Environment(loader=FileSystemLoader(str(templates_dir)))

        # Validate configuration
        self.validate_planner_config(config)

        logger.info("PhasePlanner initialized", extra={
            "base_path": config.base_path,
            "prompts_path": str(prompts_path),
            "templates_dir": str(templates_dir)
        })

    def validate_planner_config(self, config: OrchestratorConfig) -> None:
        """Validate planner configuration.

        Args:
            config: Configuration to validate

        Raises:
            PlannerError: If configuration is invalid
        """
        errors = []

        # Check that planner model is configured
        if not hasattr(config, 'models') or 'qwen2.5-coder:7b' not in str(config.models):
            logger.warning("Planner model qwen2.5-coder:7b may not be configured")

        # Verify max_retries
        if hasattr(config, 'execution') and hasattr(config.execution, 'max_retries'):
            if config.execution.max_retries <= 0:
                errors.append("max_retries must be positive")

        # Check artifact base path is writable
        artifacts_path = Path(config.base_path) / "data" / "artifacts"
        if not artifacts_path.exists():
            try:
                artifacts_path.mkdir(parents=True, exist_ok=True)
            except Exception as e:
                errors.append(f"Cannot create artifacts directory: {e}")

        if errors:
            raise PlannerError(f"Configuration validation failed: {'; '.join(errors)}")

    async def run_planning_session(
        self,
        run_id: str,
        issue_doc_path: str,
        repo_path: str,
        branch: str
    ) -> List[Dict[str, Any]]:
        """Run complete planning session with interactive approval.

        Args:
            run_id: Run identifier
            issue_doc_path: Path to issue documentation file
            repo_path: Repository path
            branch: Git branch name

        Returns:
            List of approved and saved phases

        Raises:
            PlannerError: If planning fails
        """
        logger.info("Phase planning session started", extra={
            "run_id": run_id,
            "issue_doc_path": issue_doc_path,
            "repo_path": repo_path,
            "branch": branch
        })

        try:
            # Initialize RAG system
            self.ui.show_info("Initializing repository analysis...", "Setup")
            with self.ui.show_progress("Indexing repository...") as progress:
                task = progress.add_task("Analyzing codebase...", total=None)
                await self.rag_system.initialize()
                progress.update(task, completed=True)

            # Load issue documentation
            issue_doc = self._load_issue_documentation(issue_doc_path)

            # Generate initial phase breakdown
            self.ui.show_info("Generating phase breakdown...", "Planning")
            phases = await self.generate_phase_breakdown(issue_doc, repo_path)

            # Interactive approval loop
            conversation_history = []
            approved = False
            last_generated_phases = phases  # Track for regeneration

            while not approved:
                # Display phase summary
                self.ui.display_phase_summary(phases)

                # Prompt for action
                action = self.ui.prompt_approval_action()

                if action == 'approve':
                    approved = True
                elif action == 'detail':
                    phase_num = self.ui.prompt_phase_number(len(phases))
                    phase = next(p for p in phases if p['phase_number'] == phase_num)
                    self.ui.display_phase_detail(phase)
                elif action == 'question':
                    question = self.ui.prompt_follow_up_question()
                    if question:
                        conversation_history.append({'question': question, 'answer': ''})
                        self.ui.show_info("Regenerating phases based on your feedback...", "Planning")
                        phases = await self.generate_phase_breakdown(
                            issue_doc,
                            repo_path,
                            conversation_history,
                            last_generated_phases
                        )
                        last_generated_phases = phases
                elif action == 'regenerate':
                    self.ui.show_info("Regenerating phase breakdown...", "Planning")
                    phases = await self.generate_phase_breakdown(issue_doc, repo_path)
                    last_generated_phases = phases
                elif action == 'abort':
                    raise PlannerError("Planning aborted by user")

            # Save approved phases
            self.ui.show_info("Saving phase plan...", "Finalizing")
            artifact_paths = await self.save_phases(run_id, phases, repo_path, branch)

            self.ui.show_success(f"Phase plan created successfully with {len(phases)} phases")
            self.ui.show_info(
                f"Artifacts saved:\n" + "\n".join(f"  • {p}" for p in artifact_paths),
                "Artifacts"
            )

            logger.info("Phase planning session completed", extra={
                "run_id": run_id,
                "phase_count": len(phases),
                "artifact_count": len(artifact_paths)
            })

            return phases

        except Exception as e:
            logger.error("Phase planning session failed", extra={
                "run_id": run_id,
                "error": str(e)
            }, exc_info=True)
            self.ui.show_error(str(e), "Check logs for details")
            raise PlannerError(f"Planning session failed: {e}") from e

    async def generate_phase_breakdown(
        self,
        issue_doc: str,
        repo_path: str,
        conversation_history: Optional[List[Dict[str, str]]] = None,
        previous_phases: Optional[List[Dict[str, Any]]] = None
    ) -> List[Dict[str, Any]]:
        """Generate phase breakdown using LLM.

        Args:
            issue_doc: Issue documentation text
            repo_path: Repository path
            conversation_history: Optional conversation history for regeneration
            previous_phases: Previously generated phases for context

        Returns:
            List of phase dictionaries

        Raises:
            PlannerError: If generation fails
        """
        conversation_history = conversation_history or []
        previous_phases = previous_phases or []

        try:
            # Get repository context from RAG
            with self.ui.show_progress("Retrieving repository context...") as progress:
                task = progress.add_task("Analyzing codebase...", total=None)
                repo_context = await self.rag_system.get_phase_planning_context(issue_doc)
                progress.update(task, completed=True)

            logger.info("RAG context retrieved", extra={
                "hot_files_count": len(repo_context.get('hot_files', [])),
                "code_chunks_count": len(repo_context.get('code_chunks', [])),
                "docs_count": len(repo_context.get('documentation', []))
            })

            # Build prompt
            if conversation_history:
                # This is a regeneration with follow-up
                last_question = conversation_history[-1]['question']
                prompt = self.prompt_builder.build_follow_up_prompt(
                    issue_doc,
                    repo_context,
                    conversation_history[:-1],
                    last_question,
                    previous_phases
                )
            else:
                prompt = self.prompt_builder.build_phase_planning_prompt(
                    issue_doc,
                    repo_context
                )

            # Generate with LLM
            with self.ui.show_progress("Generating phase plan with LLM...") as progress:
                task = progress.add_task("Thinking...", total=None)
                
                start_time = datetime.now()
                response = await self.llm_client.generate(
                    model="qwen2.5-coder:7b",
                    prompt=prompt,
                    temperature=0.3
                )
                latency = (datetime.now() - start_time).total_seconds()
                
                progress.update(task, completed=True)

            logger.info("LLM generation completed", extra={
                "model": "qwen2.5-coder:7b",
                "temperature": 0.3,
                "latency_seconds": latency,
                "response_length": len(response)
            })

            # Parse and validate response
            phases = PhaseValidator.parse_llm_response(response)

            # Validate dependencies
            is_valid, errors = PhaseValidator.check_phase_dependencies(phases)
            if not is_valid:
                logger.warning("Phase dependency validation failed", extra={
                    "errors": errors
                })
                raise ValidationError(f"Dependency validation failed: {'; '.join(errors)}")

            logger.info("Phase breakdown generated", extra={
                "phase_count": len(phases),
                "sizes": {size: sum(1 for p in phases if p['size'] == size) 
                         for size in ['small', 'medium', 'large']}
            })

            return phases

        except (OllamaConnectionError, OllamaGenerationError) as e:
            logger.error("LLM generation failed", exc_info=True)
            raise PlannerError(f"LLM generation failed: {e}") from e
        except ValidationError as e:
            logger.error("Phase validation failed", exc_info=True)
            raise PlannerError(f"Phase validation failed: {e}") from e
        except Exception as e:
            logger.error("Unexpected error in phase generation", exc_info=True)
            raise PlannerError(f"Phase generation failed: {e}") from e

    async def save_phases(
        self,
        run_id: str,
        phases: List[Dict[str, Any]],
        repo_path: str,
        branch: str
    ) -> List[str]:
        """Save approved phases to state manager and generate artifacts.

        Args:
            run_id: Run identifier
            phases: List of approved phase dictionaries
            repo_path: Repository path
            branch: Git branch

        Returns:
            List of artifact file paths

        Raises:
            PlannerError: If saving fails
        """
        try:
            artifact_paths = []

            # Create artifact directory
            artifacts_dir = Path(self.config.base_path) / "data" / "artifacts" / run_id / "planning"
            artifacts_dir.mkdir(parents=True, exist_ok=True)

            # Save each phase to state manager
            for phase in phases:
                phase_id = await self.state_manager.create_phase(
                    run_id=run_id,
                    phase_number=phase['phase_number'],
                    title=phase['title'],
                    intent=phase['intent'],
                    plan=json.dumps(phase),
                    max_retries=self.config.execution.max_retries if hasattr(self.config, 'execution') else 3,
                    size=phase['size']
                )
                logger.debug("Phase saved to state manager", extra={
                    "run_id": run_id,
                    "phase_id": phase_id,
                    "phase_number": phase['phase_number']
                })

            # Generate and save PhasePlan.json
            plan_json_path = artifacts_dir / "PhasePlan.json"
            with open(plan_json_path, 'w', encoding='utf-8') as f:
                json.dump(phases, f, indent=2)
            artifact_paths.append(str(plan_json_path))

            await self.state_manager.register_artifact(
                run_id=run_id,
                phase_id=None,
                artifact_type='phase_plan',
                file_path=str(plan_json_path),
                description='Complete phase plan in JSON format'
            )

            # Generate and save PhasePlan.md
            plan_md_path = artifacts_dir / "PhasePlan.md"
            markdown = self.render_phase_plan_markdown(phases, run_id, repo_path, branch)
            with open(plan_md_path, 'w', encoding='utf-8') as f:
                f.write(markdown)
            artifact_paths.append(str(plan_md_path))

            await self.state_manager.register_artifact(
                run_id=run_id,
                phase_id=None,
                artifact_type='phase_plan',
                file_path=str(plan_md_path),
                description='Human-readable phase plan in Markdown format'
            )

            # Generate individual phase detail files
            for phase in phases:
                detail_markdown = self.render_phase_detail_markdown(phase, len(phases))
                if detail_markdown is not None:
                    phase_detail_path = artifacts_dir / f"Phase_{phase['phase_number']}_Detail.md"
                    with open(phase_detail_path, 'w', encoding='utf-8') as f:
                        f.write(detail_markdown)
                    artifact_paths.append(str(phase_detail_path))

                    await self.state_manager.register_artifact(
                        run_id=run_id,
                        phase_id=None,
                        artifact_type='phase_detail',
                        file_path=str(phase_detail_path),
                        description=f'Detailed specification for Phase {phase["phase_number"]}'
                    )

            # Update run status to executing
            await self.state_manager.update_run_status(run_id, 'executing')

            logger.info("Phases saved successfully", extra={
                "run_id": run_id,
                "phase_count": len(phases),
                "artifact_count": len(artifact_paths)
            })

            return artifact_paths

        except Exception as e:
            logger.error("Failed to save phases", extra={
                "run_id": run_id,
                "error": str(e)
            }, exc_info=True)
            raise PlannerError(f"Failed to save phases: {e}") from e

    def render_phase_plan_markdown(
        self,
        phases: List[Dict[str, Any]],
        run_id: str,
        repo_path: str,
        branch: str
    ) -> str:
        """Render phase plan as markdown using Jinja2 template.

        Args:
            phases: List of phase dictionaries
            run_id: Run identifier
            repo_path: Repository path
            branch: Git branch

        Returns:
            Rendered markdown string
        """
        try:
            template = self.jinja_env.get_template('phase_plan.md.j2')
            markdown = template.render(
                phases=phases,
                run_id=run_id,
                repo_path=repo_path,
                branch=branch,
                timestamp=datetime.now().isoformat()
            )
            return markdown
        except TemplateNotFound as e:
            raise PlannerError(f"Template not found: {e}")
        except Exception as e:
            raise PlannerError(f"Template rendering failed: {e}")

    def render_phase_detail_markdown(
        self,
        phase: Dict[str, Any],
        total_phases: int
    ) -> Optional[str]:
        """Render individual phase detail as markdown.

        Args:
            phase: Phase dictionary
            total_phases: Total number of phases

        Returns:
            Rendered markdown string, or None if template is not found
        """
        try:
            template = self.jinja_env.get_template('phase_detail.md.j2')
            markdown = template.render(
                phase=phase,
                total_phases=total_phases
            )
            return markdown
        except TemplateNotFound as e:
            logger.warning(f"Phase detail template not found, skipping: {e}")
            return None
        except Exception as e:
            raise PlannerError(f"Template rendering failed: {e}")

    def _load_issue_documentation(self, issue_doc_path: str) -> str:
        """Load issue documentation from file.

        Args:
            issue_doc_path: Path to issue documentation file

        Returns:
            Issue documentation text

        Raises:
            PlannerError: If file cannot be read
        """
        try:
            path = Path(issue_doc_path)
            if not path.exists():
                raise PlannerError(f"Issue documentation not found: {issue_doc_path}")

            with open(path, 'r', encoding='utf-8') as f:
                content = f.read()

            # If it's a JSON file, extract relevant fields
            if path.suffix.lower() == '.json':
                data = json.loads(content)
                # Extract common fields
                text_parts = []
                if 'title' in data:
                    text_parts.append(f"# {data['title']}\n")
                if 'description' in data:
                    text_parts.append(data['description'])
                if 'body' in data:
                    text_parts.append(data['body'])
                content = "\n\n".join(text_parts)

            logger.info("Issue documentation loaded", extra={
                "path": issue_doc_path,
                "length": len(content)
            })

            return content

        except Exception as e:
            logger.error("Failed to load issue documentation", extra={
                "path": issue_doc_path,
                "error": str(e)
            }, exc_info=True)
            raise PlannerError(f"Failed to load issue documentation: {e}") from e

    async def load_phase_plan(self, run_id: str) -> List[Dict[str, Any]]:
        """Load existing phase plan from artifacts.

        Args:
            run_id: Run identifier

        Returns:
            List of phase dictionaries

        Raises:
            PlannerError: If plan cannot be loaded
        """
        try:
            plan_path = Path(self.config.base_path) / "data" / "artifacts" / run_id / "planning" / "PhasePlan.json"
            
            if not plan_path.exists():
                raise PlannerError(f"Phase plan not found for run: {run_id}")

            with open(plan_path, 'r', encoding='utf-8') as f:
                phases = json.load(f)

            # Validate loaded phases
            for phase in phases:
                is_valid, errors = PhaseValidator.validate_phase_structure(phase)
                if not is_valid:
                    raise ValidationError(f"Invalid phase structure: {'; '.join(errors)}")

            logger.info("Phase plan loaded", extra={
                "run_id": run_id,
                "phase_count": len(phases)
            })

            return phases

        except Exception as e:
            logger.error("Failed to load phase plan", extra={
                "run_id": run_id,
                "error": str(e)
            }, exc_info=True)
            raise PlannerError(f"Failed to load phase plan: {e}") from e
