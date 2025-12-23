"""Agent Orchestrator - Main CLI Entry Point

A comprehensive orchestration system for managing multi-phase development tasks
with LLM-powered planning, execution, and verification.
"""

import asyncio
import sys
import logging
from pathlib import Path
from datetime import datetime
from typing import Optional, Dict, Any
import subprocess
import json

import click
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.prompt import Prompt, Confirm
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn
from rich.markdown import Markdown
from rich import box
from rich.layout import Layout
from rich.text import Text

from orchestrator.config import ConfigLoader, OrchestratorConfig
from orchestrator.state import StateManager
from orchestrator.llm_client import OllamaClient, OllamaConnectionError
from orchestrator.planner import PhasePlanner
from orchestrator.executor import PhaseExecutor
from orchestrator.planner_ui import PlannerUI
from orchestrator.exceptions import ConfigError, RunNotFoundError
from repo_brain.rag_system import RAGSystem

logger = logging.getLogger(__name__)

ASCII_BANNER = """
[cyan]
╔═══════════════════════════════════════════════════════════╗
║                                                           ║
║     █████╗  ██████╗ ███████╗███╗   ██╗████████╗         ║
║    ██╔══██╗██╔════╝ ██╔════╝████╗  ██║╚══██╔══╝         ║
║    ███████║██║  ███╗█████╗  ██╔██╗ ██║   ██║            ║
║    ██╔══██║██║   ██║██╔══╝  ██║╚██╗██║   ██║            ║
║    ██║  ██║╚██████╔╝███████╗██║ ╚████║   ██║            ║
║    ╚═╝  ╚═╝ ╚═════╝ ╚══════╝╚═╝  ╚═══╝   ╚═╝            ║
║                                                           ║
║    ██████╗ ██████╗  ██████╗██╗  ██╗███████╗███████╗     ║
║   ██╔═══██╗██╔══██╗██╔════╝██║  ██║██╔════╝██╔════╝     ║
║   ██║   ██║██████╔╝██║     ███████║█████╗  ███████╗     ║
║   ██║   ██║██╔══██╗██║     ██╔══██║██╔══╝  ╚════██║     ║
║   ╚██████╔╝██║  ██║╚██████╗██║  ██║███████╗███████║     ║
║    ╚═════╝ ╚═╝  ╚═╝ ╚═════╝╚═╝  ╚═╝╚══════╝╚══════╝     ║
║                                                           ║
╚═══════════════════════════════════════════════════════════╝
[/cyan]
"""


class OrchestratorCLI:
    """Main orchestrator CLI application."""

    def __init__(self, config_path: Optional[str] = None):
        """Initialize CLI application.
        
        Args:
            config_path: Optional path to configuration file
        """
        self.console = Console()
        self.ui = PlannerUI()
        self.config_path = config_path or "config/orchestrator-config.yaml"
        self.config: Optional[OrchestratorConfig] = None
        self.state_manager: Optional[StateManager] = None
        self.llm_client: Optional[OllamaClient] = None
        self.rag_system: Optional[RAGSystem] = None
        self.planner: Optional[PhasePlanner] = None
        self.executor: Optional[PhaseExecutor] = None
        
    def display_banner(self):
        """Display welcome banner with version info."""
        self.console.print(ASCII_BANNER)
        
        info_table = Table(show_header=False, box=box.SIMPLE, padding=(0, 2))
        info_table.add_column("Key", style="cyan")
        info_table.add_column("Value", style="white")
        
        info_table.add_row("Version", "1.0.0")
        info_table.add_row("Python", f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}")
        info_table.add_row("Config", self.config_path)
        
        self.console.print(Panel(info_table, title="System Information", border_style="cyan"))
        self.console.print()

    def validate_environment(self) -> bool:
        """Validate runtime environment and dependencies.
        
        Returns:
            True if all validations pass, False otherwise
        """
        self.console.print("\n[bold cyan]🔍 Validating Environment...[/bold cyan]\n")
        
        validation_table = Table(box=box.ROUNDED)
        validation_table.add_column("Check", style="white")
        validation_table.add_column("Status", justify="center")
        validation_table.add_column("Details", style="dim")
        
        all_passed = True
        
        # Python version check
        if sys.version_info >= (3, 10):
            validation_table.add_row(
                "Python Version",
                "[green]✓ PASS[/green]",
                f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
            )
        else:
            validation_table.add_row(
                "Python Version",
                "[red]✗ FAIL[/red]",
                f"{sys.version_info.major}.{sys.version_info.minor} (requires 3.10+)"
            )
            all_passed = False
        
        # Ollama service check
        try:
            import requests
            response = requests.get("http://localhost:11434/api/tags", timeout=5)
            if response.status_code == 200:
                validation_table.add_row(
                    "Ollama Service",
                    "[green]✓ PASS[/green]",
                    "Running on localhost:11434"
                )
            else:
                validation_table.add_row(
                    "Ollama Service",
                    "[yellow]⚠ WARN[/yellow]",
                    f"Unexpected status: {response.status_code}"
                )
        except Exception as e:
            validation_table.add_row(
                "Ollama Service",
                "[red]✗ FAIL[/red]",
                f"Not accessible: {str(e)[:40]}"
            )
            all_passed = False
        
        # GitHub CLI check
        try:
            result = subprocess.run(
                ["gh", "auth", "status"],
                capture_output=True,
                text=True,
                timeout=5
            )
            if result.returncode == 0:
                validation_table.add_row(
                    "GitHub CLI",
                    "[green]✓ PASS[/green]",
                    "Authenticated"
                )
            else:
                validation_table.add_row(
                    "GitHub CLI",
                    "[yellow]⚠ WARN[/yellow]",
                    "Not authenticated"
                )
        except FileNotFoundError:
            validation_table.add_row(
                "GitHub CLI",
                "[red]✗ FAIL[/red]",
                "Not installed"
            )
            all_passed = False
        except Exception as e:
            validation_table.add_row(
                "GitHub CLI",
                "[yellow]⚠ WARN[/yellow]",
                str(e)[:40]
            )
        
        # Required directories check
        required_dirs = ["data", "config", "templates"]
        for dir_name in required_dirs:
            dir_path = Path(dir_name)
            if dir_path.exists():
                validation_table.add_row(
                    f"Directory: {dir_name}/",
                    "[green]✓ PASS[/green]",
                    str(dir_path.absolute())[:40]
                )
            else:
                validation_table.add_row(
                    f"Directory: {dir_name}/",
                    "[yellow]⚠ WARN[/yellow]",
                    "Not found (will create)"
                )
                dir_path.mkdir(parents=True, exist_ok=True)
        
        self.console.print(validation_table)
        self.console.print()
        
        if not all_passed:
            self.console.print(Panel(
                "[red]Some validation checks failed. Please resolve the issues above.[/red]",
                title="Validation Failed",
                border_style="red"
            ))
            return False
        
        self.console.print("[green]✓ All validation checks passed![/green]\n")
        return True

    def load_configuration(self) -> bool:
        """Load and validate configuration.
        
        Returns:
            True if configuration loaded successfully, False otherwise
        """
        try:
            self.console.print(f"[cyan]📋 Loading configuration from {self.config_path}...[/cyan]")
            
            loader = ConfigLoader(self.config_path)
            self.config = loader.load()
            
            # Setup logging based on config
            self._setup_logging()
            
            self.console.print("[green]✓ Configuration loaded successfully[/green]\n")
            return True
            
        except FileNotFoundError:
            self.console.print(Panel(
                f"[red]Configuration file not found: {self.config_path}[/red]\n\n"
                "Please create the configuration file or specify a valid path.",
                title="Configuration Error",
                border_style="red"
            ))
            return False
        except ConfigError as e:
            self.console.print(Panel(
                f"[red]Configuration error: {str(e)}[/red]",
                title="Configuration Error",
                border_style="red"
            ))
            return False
        except Exception as e:
            self.console.print(Panel(
                f"[red]Unexpected error loading configuration: {str(e)}[/red]",
                title="Error",
                border_style="red"
            ))
            logger.exception("Failed to load configuration")
            return False

    def _setup_logging(self):
        """Setup logging based on configuration."""
        if not self.config:
            return
            
        log_config = self.config.logging
        log_level = getattr(logging, log_config.level.upper(), logging.INFO)
        
        # Create log directory if needed
        log_path = Path(log_config.file_path)
        log_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Configure root logger
        logging.basicConfig(
            level=log_level,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler(log_config.file_path),
                logging.StreamHandler() if log_config.console_enabled else logging.NullHandler()
            ]
        )
        
        logger.info("Logging initialized", extra={
            "level": log_config.level,
            "file": log_config.file_path
        })

    def prompt_for_inputs(self) -> Optional[Dict[str, str]]:
        """Prompt user for required inputs.
        
        Returns:
            Dictionary with doc_path, repo_path, branch or None if cancelled
        """
        self.console.print("[bold cyan]📝 Input Configuration[/bold cyan]\n")
        
        try:
            # Documentation path
            while True:
                doc_path = Prompt.ask(
                    "[cyan]Documentation file path[/cyan]",
                    default="docs/requirements.md"
                )
                if Path(doc_path).exists():
                    break
                self.console.print(f"[yellow]⚠ File not found: {doc_path}[/yellow]")
                if not Confirm.ask("Try again?", default=True):
                    return None
            
            # Repository path
            while True:
                repo_path = Prompt.ask(
                    "[cyan]Repository path[/cyan]",
                    default="."
                )
                repo_path_obj = Path(repo_path)
                if repo_path_obj.exists() and repo_path_obj.is_dir():
                    # Check if it's a git repo
                    if (repo_path_obj / ".git").exists():
                        break
                    self.console.print(f"[yellow]⚠ Not a git repository: {repo_path}[/yellow]")
                    if not Confirm.ask("Continue anyway?", default=False):
                        if not Confirm.ask("Try different path?", default=True):
                            return None
                        continue
                    break
                self.console.print(f"[yellow]⚠ Directory not found: {repo_path}[/yellow]")
                if not Confirm.ask("Try again?", default=True):
                    return None
            
            # Branch name
            current_branch = self._get_current_branch(repo_path)
            branch_default = current_branch if current_branch else "main"
            branch = Prompt.ask(
                "[cyan]Target branch[/cyan]",
                default=branch_default
            )
            
            # Display summary
            summary_table = Table(show_header=False, box=box.ROUNDED, title="Input Summary")
            summary_table.add_column("Setting", style="cyan")
            summary_table.add_column("Value", style="white")
            
            summary_table.add_row("Documentation", doc_path)
            summary_table.add_row("Repository", repo_path)
            summary_table.add_row("Branch", branch)
            
            self.console.print()
            self.console.print(summary_table)
            self.console.print()
            
            if not Confirm.ask("[cyan]Proceed with these settings?[/cyan]", default=True):
                return None
            
            return {
                "doc_path": doc_path,
                "repo_path": repo_path,
                "branch": branch
            }
            
        except KeyboardInterrupt:
            self.console.print("\n[yellow]Operation cancelled by user[/yellow]")
            return None

    def _get_current_branch(self, repo_path: str) -> Optional[str]:
        """Get current git branch name.
        
        Args:
            repo_path: Path to repository
            
        Returns:
            Branch name or None
        """
        try:
            result = subprocess.run(
                ["git", "rev-parse", "--abbrev-ref", "HEAD"],
                cwd=repo_path,
                capture_output=True,
                text=True,
                timeout=5
            )
            if result.returncode == 0:
                return result.stdout.strip()
        except Exception:
            pass
        return None

    def confirm_git_sync(self, repo_path: str) -> bool:
        """Confirm and execute git sync if requested.
        
        Args:
            repo_path: Path to repository
            
        Returns:
            True if sync completed or skipped, False on error
        """
        if not self.config or not self.config.git.auto_pull:
            if not Confirm.ask("\n[cyan]Pull latest changes from remote?[/cyan]", default=False):
                return True
        
        try:
            self.console.print("\n[cyan]🔄 Syncing with remote...[/cyan]")
            
            # Fetch first
            result = subprocess.run(
                ["git", "fetch"],
                cwd=repo_path,
                capture_output=True,
                text=True,
                timeout=30
            )
            
            if result.returncode != 0:
                self.console.print(f"[yellow]⚠ Fetch warning: {result.stderr}[/yellow]")
            
            # Check status
            result = subprocess.run(
                ["git", "status", "--short"],
                cwd=repo_path,
                capture_output=True,
                text=True,
                timeout=5
            )
            
            if result.stdout.strip():
                self.console.print("[yellow]⚠ Working directory has uncommitted changes[/yellow]")
                if not Confirm.ask("Continue anyway?", default=False):
                    return False
            
            # Pull
            result = subprocess.run(
                ["git", "pull"],
                cwd=repo_path,
                capture_output=True,
                text=True,
                timeout=30
            )
            
            if result.returncode == 0:
                self.console.print("[green]✓ Repository synced successfully[/green]\n")
            else:
                self.console.print(f"[yellow]⚠ Pull completed with warnings: {result.stderr}[/yellow]\n")
            
            return True
            
        except subprocess.TimeoutExpired:
            self.console.print("[red]✗ Git operation timed out[/red]\n")
            return False
        except Exception as e:
            self.console.print(f"[red]✗ Git sync failed: {str(e)}[/red]\n")
            return False

    async def initialize_components(self, inputs: Dict[str, str]) -> bool:
        """Initialize orchestration components.
        
        Args:
            inputs: User inputs (doc_path, repo_path, branch)
            
        Returns:
            True if initialization successful, False otherwise
        """
        try:
            self.console.print("\n[bold cyan]🔧 Initializing Components...[/bold cyan]\n")
            
            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                console=self.console
            ) as progress:
                
                # Initialize LLM client
                task = progress.add_task("Initializing LLM client...", total=None)
                self.llm_client = OllamaClient(
                    base_url=self.config.llm.host,
                    timeout=30
                )
                progress.update(task, completed=True)
                
                # Initialize state manager
                task = progress.add_task("Initializing state manager...", total=None)
                db_path = Path("data") / "orchestrator.db"
                artifact_path = Path(self.config.artifacts.base_path)
                self.state_manager = StateManager(str(db_path), str(artifact_path))
                await self.state_manager._initialize()
                progress.update(task, completed=True)
                
                # Initialize RAG system
                task = progress.add_task("Initializing RAG system...", total=None)
                rag_db_path = Path("data") / "rag_index.db"
                self.rag_system = RAGSystem(
                    repo_path=inputs["repo_path"],
                    db_path=str(rag_db_path),
                    embedding_model="nomic-embed-text:latest",
                    llm_client=self.llm_client
                )
                await self.rag_system.initialize()
                progress.update(task, completed=True)
                
                # Index repository if needed
                if self.config.rag.index_on_startup:
                    task = progress.add_task("Indexing repository...", total=None)
                    await self.rag_system.index_repository()
                    progress.update(task, completed=True)
                
                # Initialize planner
                task = progress.add_task("Initializing phase planner...", total=None)
                self.planner = PhasePlanner(
                    config=self.config,
                    llm_client=self.llm_client,
                    rag_system=self.rag_system,
                    state_manager=self.state_manager
                )
                progress.update(task, completed=True)
                
                # Initialize executor
                task = progress.add_task("Initializing phase executor...", total=None)
                self.executor = PhaseExecutor(
                    config=self.config,
                    llm_client=self.llm_client,
                    rag_system=self.rag_system,
                    state_manager=self.state_manager
                )
                progress.update(task, completed=True)
            
            self.console.print("[green]✓ All components initialized successfully[/green]\n")
            return True
            
        except OllamaConnectionError as e:
            self.console.print(Panel(
                f"[red]Failed to connect to Ollama service: {str(e)}[/red]\n\n"
                "Please ensure Ollama is running:\n"
                "  • Check service status\n"
                "  • Verify it's accessible at http://localhost:11434",
                title="LLM Connection Error",
                border_style="red"
            ))
            return False
        except Exception as e:
            self.console.print(Panel(
                f"[red]Component initialization failed: {str(e)}[/red]",
                title="Initialization Error",
                border_style="red"
            ))
            logger.exception("Component initialization failed")
            return False

    async def run_orchestration(self, inputs: Dict[str, str]) -> bool:
        """Run main orchestration workflow.
        
        Args:
            inputs: User inputs (doc_path, repo_path, branch)
            
        Returns:
            True if orchestration completed successfully, False otherwise
        """
        run_state = None
        
        try:
            # Create run
            self.console.print("[cyan]🚀 Starting orchestration run...[/cyan]\n")
            
            run_state = await self.state_manager.create_run(
                repo_path=inputs["repo_path"],
                branch=inputs["branch"],
                doc_path=inputs["doc_path"],
                config=self.config.model_dump()
            )
            
            self.console.print(f"[green]✓ Run created: {run_state.run_id}[/green]\n")
            
            # Phase planning
            self.console.print("[bold cyan]📋 Phase Planning[/bold cyan]\n")
            
            planning_session = await self.planner.run_planning_session(
                run_id=run_state.run_id,
                documentation_path=inputs["doc_path"],
                repo_path=inputs["repo_path"]
            )
            
            if not planning_session or not planning_session.get("approved"):
                self.console.print("[yellow]⚠ Planning not approved or failed[/yellow]")
                return False
            
            phases = planning_session.get("phases", [])
            self.console.print(f"[green]✓ {len(phases)} phases approved for execution[/green]\n")
            
            # Phase execution
            self.console.print("[bold cyan]⚙️ Phase Execution (YOLO Mode)[/bold cyan]\n")
            
            results = await self.executor.execute_all_phases_yolo(
                run_id=run_state.run_id,
                repo_path=inputs["repo_path"],
                branch=inputs["branch"]
            )
            
            # Display results
            await self.display_completion_summary(run_state.run_id, results)
            
            return True
            
        except KeyboardInterrupt:
            self.console.print("\n\n[yellow]⚠ Orchestration interrupted by user[/yellow]")
            
            if run_state:
                self.console.print(f"\nRun ID: [cyan]{run_state.run_id}[/cyan]")
                self.console.print("You can resume this run later with:")
                self.console.print(f"  [cyan]python main.py resume --run-id {run_state.run_id}[/cyan]\n")
            
            return False
            
        except Exception as e:
            self.console.print(Panel(
                f"[red]Orchestration failed: {str(e)}[/red]",
                title="Execution Error",
                border_style="red"
            ))
            logger.exception("Orchestration failed")
            return False

    async def display_completion_summary(self, run_id: str, results: Dict[str, Any]):
        """Display completion summary with statistics.
        
        Args:
            run_id: Run identifier
            results: Execution results
        """
        self.console.print("\n")
        self.console.print("=" * 60)
        self.console.print("[bold green]🎉 Orchestration Complete![/bold green]")
        self.console.print("=" * 60)
        self.console.print()
        
        # Fetch run summary
        try:
            summary = await self.state_manager.get_run_summary(run_id)
            
            # Create summary table
            summary_table = Table(title="Run Summary", box=box.DOUBLE)
            summary_table.add_column("Metric", style="cyan")
            summary_table.add_column("Value", justify="right", style="white")
            
            summary_table.add_row("Run ID", run_id[:8] + "...")
            summary_table.add_row("Total Phases", str(summary.total_phases))
            summary_table.add_row("Completed", f"[green]{summary.completed_phases}[/green]")
            summary_table.add_row("Failed", f"[red]{summary.failed_phases}[/red]" if summary.failed_phases > 0 else "0")
            summary_table.add_row("Skipped", str(summary.skipped_phases))
            summary_table.add_row("Total Executions", str(summary.total_executions))
            summary_table.add_row("Major Findings", f"[red]{summary.major_findings}[/red]" if summary.major_findings > 0 else "0")
            summary_table.add_row("Medium Findings", f"[yellow]{summary.medium_findings}[/yellow]" if summary.medium_findings > 0 else "0")
            summary_table.add_row("Minor Findings", str(summary.minor_findings))
            
            if summary.duration_seconds:
                duration_min = summary.duration_seconds / 60
                summary_table.add_row("Duration", f"{duration_min:.1f} minutes")
            
            self.console.print(summary_table)
            self.console.print()
            
            # Artifacts location
            artifact_path = Path(self.config.artifacts.base_path) / run_id
            self.console.print(f"[cyan]📁 Artifacts saved to:[/cyan] {artifact_path}")
            self.console.print()
            
            # Save summary to file
            summary_file = artifact_path / "summary.md"
            summary_file.parent.mkdir(parents=True, exist_ok=True)
            
            with open(summary_file, "w") as f:
                f.write(f"# Orchestration Run Summary\n\n")
                f.write(f"**Run ID:** {run_id}\n\n")
                f.write(f"**Completed:** {datetime.now().isoformat()}\n\n")
                f.write(f"## Statistics\n\n")
                f.write(f"- Total Phases: {summary.total_phases}\n")
                f.write(f"- Completed: {summary.completed_phases}\n")
                f.write(f"- Failed: {summary.failed_phases}\n")
                f.write(f"- Skipped: {summary.skipped_phases}\n")
                f.write(f"- Total Executions: {summary.total_executions}\n")
                f.write(f"- Major Findings: {summary.major_findings}\n")
                f.write(f"- Medium Findings: {summary.medium_findings}\n")
                f.write(f"- Minor Findings: {summary.minor_findings}\n")
                if summary.duration_seconds:
                    f.write(f"- Duration: {summary.duration_seconds / 60:.1f} minutes\n")
            
            self.console.print(f"[green]✓ Summary saved to {summary_file}[/green]\n")
            
        except Exception as e:
            self.console.print(f"[yellow]⚠ Could not generate summary: {str(e)}[/yellow]\n")


@click.group()
@click.option('--config', '-c', default='config/orchestrator-config.yaml', help='Path to configuration file')
@click.pass_context
def cli(ctx, config):
    """Agent Orchestrator - Intelligent multi-phase development automation.
    
    This tool helps break down complex development tasks into manageable phases,
    executes them with LLM assistance, and verifies the results.
    """
    ctx.ensure_object(dict)
    ctx.obj['config_path'] = config


@cli.command()
@click.pass_context
def run(ctx):
    """Start a new orchestration run (default command).
    
    This will:
    1. Validate environment and dependencies
    2. Load configuration
    3. Prompt for documentation, repository, and branch
    4. Initialize components (LLM, RAG, state management)
    5. Generate and approve phase breakdown
    6. Execute phases in YOLO mode
    7. Display completion summary
    """
    config_path = ctx.obj['config_path']
    
    try:
        app = OrchestratorCLI(config_path)
        app.display_banner()
        
        # Validation
        if not app.validate_environment():
            sys.exit(1)
        
        # Load configuration
        if not app.load_configuration():
            sys.exit(1)
        
        # Get inputs
        inputs = app.prompt_for_inputs()
        if not inputs:
            app.console.print("[yellow]Operation cancelled[/yellow]")
            sys.exit(0)
        
        # Git sync
        if not app.confirm_git_sync(inputs["repo_path"]):
            sys.exit(1)
        
        # Run orchestration
        success = asyncio.run(app._run_async(inputs))
        
        sys.exit(0 if success else 1)
        
    except KeyboardInterrupt:
        app.console.print("\n[yellow]Interrupted by user[/yellow]")
        sys.exit(130)
    except Exception as e:
        logger.exception("Unexpected error in run command")
        print(f"Error: {str(e)}", file=sys.stderr)
        sys.exit(1)


@cli.command()
@click.option('--run-id', '-r', required=True, help='Run ID to resume')
@click.pass_context
def resume(ctx, run_id):
    """Resume an interrupted orchestration run.
    
    This command loads a previous run state and continues execution
    from where it left off.
    """
    config_path = ctx.obj['config_path']
    
    try:
        app = OrchestratorCLI(config_path)
        app.console.print(f"[cyan]Resuming run: {run_id}[/cyan]\n")
        
        # Load configuration
        if not app.load_configuration():
            sys.exit(1)
        
        # Resume execution
        success = asyncio.run(app._resume_async(run_id))
        
        sys.exit(0 if success else 1)
        
    except RunNotFoundError:
        app.console.print(f"[red]Run not found: {run_id}[/red]")
        sys.exit(1)
    except Exception as e:
        logger.exception("Failed to resume run")
        print(f"Error: {str(e)}", file=sys.stderr)
        sys.exit(1)


@cli.command()
@click.option('--run-id', '-r', help='Specific run ID to show status for')
@click.pass_context
def status(ctx, run_id):
    """Show orchestration status.
    
    Displays information about recent runs or a specific run.
    """
    config_path = ctx.obj['config_path']
    
    try:
        app = OrchestratorCLI(config_path)
        
        if not app.load_configuration():
            sys.exit(1)
        
        asyncio.run(app._show_status_async(run_id))
        
    except Exception as e:
        logger.exception("Failed to show status")
        print(f"Error: {str(e)}", file=sys.stderr)
        sys.exit(1)


@cli.command()
@click.pass_context
def config(ctx):
    """Validate and display configuration.
    
    Loads the configuration file, validates all settings, and displays
    them in an organized format.
    """
    config_path = ctx.obj['config_path']
    
    try:
        app = OrchestratorCLI(config_path)
        app.console.print(f"[cyan]Loading configuration from: {config_path}[/cyan]\n")
        
        if not app.load_configuration():
            sys.exit(1)
        
        # Display configuration
        app._display_config()
        
        # Validate connectivity
        app.console.print("\n[cyan]Testing connectivity...[/cyan]\n")
        app.validate_environment()
        
    except Exception as e:
        logger.exception("Failed to validate configuration")
        print(f"Error: {str(e)}", file=sys.stderr)
        sys.exit(1)


# Async helper methods for OrchestratorCLI

async def _run_async(self, inputs: Dict[str, str]) -> bool:
    """Async wrapper for run orchestration."""
    if not await self.initialize_components(inputs):
        return False
    
    return await self.run_orchestration(inputs)


async def _resume_async(self, run_id: str) -> bool:
    """Async wrapper for resume orchestration."""
    # Initialize state manager
    db_path = Path("data") / "orchestrator.db"
    artifact_path = Path(self.config.artifacts.base_path)
    self.state_manager = StateManager(str(db_path), str(artifact_path))
    await self.state_manager._initialize()
    
    # Get run state
    run_state = await self.state_manager.get_run(run_id)
    
    self.console.print(Panel(
        f"[cyan]Run ID:[/cyan] {run_state.run_id}\n"
        f"[cyan]Status:[/cyan] {run_state.status}\n"
        f"[cyan]Repository:[/cyan] {run_state.repo_path}\n"
        f"[cyan]Branch:[/cyan] {run_state.branch}",
        title="Run Information",
        border_style="cyan"
    ))
    
    if not Confirm.ask("\nResume this run?", default=True):
        return False
    
    # Initialize other components
    inputs = {
        "doc_path": run_state.documentation_path,
        "repo_path": run_state.repo_path,
        "branch": run_state.branch
    }
    
    if not await self.initialize_components(inputs):
        return False
    
    # Continue execution
    self.console.print("\n[cyan]Resuming execution...[/cyan]\n")
    
    results = await self.executor.execute_all_phases_yolo(
        run_id=run_id,
        repo_path=run_state.repo_path,
        branch=run_state.branch
    )
    
    await self.display_completion_summary(run_id, results)
    
    return True


async def _show_status_async(self, run_id: Optional[str] = None):
    """Async wrapper for show status."""
    # Initialize state manager
    db_path = Path("data") / "orchestrator.db"
    artifact_path = Path(self.config.artifacts.base_path)
    self.state_manager = StateManager(str(db_path), str(artifact_path))
    await self.state_manager._initialize()
    
    if run_id:
        # Show specific run
        run_state = await self.state_manager.get_run(run_id)
        summary = await self.state_manager.get_run_summary(run_id)
        
        self.console.print(Panel(
            f"[cyan]Run ID:[/cyan] {run_state.run_id}\n"
            f"[cyan]Status:[/cyan] {run_state.status}\n"
            f"[cyan]Created:[/cyan] {run_state.created_at}\n"
            f"[cyan]Repository:[/cyan] {run_state.repo_path}\n"
            f"[cyan]Branch:[/cyan] {run_state.branch}\n"
            f"[cyan]Documentation:[/cyan] {run_state.documentation_path}\n\n"
            f"[cyan]Phases:[/cyan] {summary.completed_phases}/{summary.total_phases} completed\n"
            f"[cyan]Findings:[/cyan] {summary.major_findings} major, {summary.medium_findings} medium, {summary.minor_findings} minor",
            title="Run Status",
            border_style="cyan"
        ))
    else:
        # Show recent runs
        recent_runs = await self.state_manager.list_recent_runs(limit=10)
        
        if not recent_runs:
            self.console.print("[yellow]No runs found in database.[/yellow]")
            sys.exit(1)
        
        self.console.print("[bold cyan]Recent orchestration runs:[/bold cyan]\n")
        
        # Create table
        table = Table(box=box.ROUNDED)
        table.add_column("Run ID", style="cyan")
        table.add_column("Status", justify="center")
        table.add_column("Created", style="dim")
        table.add_column("Branch", style="white")
        table.add_column("Documentation", style="dim")
        
        for run in recent_runs:
            # Format status with color
            status_display = run.status
            if run.status == "completed":
                status_display = f"[green]{run.status}[/green]"
            elif run.status == "failed":
                status_display = f"[red]{run.status}[/red]"
            elif run.status == "executing":
                status_display = f"[yellow]{run.status}[/yellow]"
            
            # Format date
            created_display = run.created_at.strftime("%Y-%m-%d %H:%M")
            
            # Truncate run ID for display
            run_id_display = run.run_id[:12] + "..."
            
            # Truncate doc path
            doc_display = Path(run.documentation_path).name
            
            table.add_row(
                run_id_display,
                status_display,
                created_display,
                run.branch,
                doc_display
            )
        
        self.console.print(table)
        self.console.print()
        self.console.print("[dim]Use 'python main.py status --run-id <run_id>' for detailed information[/dim]")


def _display_config(self):
    """Display configuration in organized format."""
    if not self.config:
        return
    
    # Execution settings
    exec_table = Table(title="Execution Settings", box=box.ROUNDED)
    exec_table.add_column("Setting", style="cyan")
    exec_table.add_column("Value", style="white")
    
    exec_table.add_row("Max Retries", str(self.config.execution.max_retries))
    exec_table.add_row("Retry Delay", f"{self.config.execution.retry_delay}s")
    exec_table.add_row("Copilot Mode", self.config.execution.copilot_mode)
    exec_table.add_row("Branch Prefix", self.config.execution.branch_prefix)
    
    self.console.print(exec_table)
    self.console.print()
    
    # Verification settings
    verif_table = Table(title="Verification Settings", box=box.ROUNDED)
    verif_table.add_column("Check", style="cyan")
    verif_table.add_column("Enabled", style="white")
    
    verif_table.add_row("Build", "✓" if self.config.verification.build_enabled else "✗")
    verif_table.add_row("Tests", "✓" if self.config.verification.test_enabled else "✗")
    verif_table.add_row("Linting", "✓" if self.config.verification.lint_enabled else "✗")
    verif_table.add_row("Security Scan", "✓" if self.config.verification.security_scan_enabled else "✗")
    verif_table.add_row("Spec Validation", "✓" if self.config.verification.spec_validation_enabled else "✗")
    
    self.console.print(verif_table)
    self.console.print()
    
    self.console.print("[green]✓ Configuration is valid[/green]")


# Bind async methods to class
OrchestratorCLI._run_async = _run_async
OrchestratorCLI._resume_async = _resume_async
OrchestratorCLI._show_status_async = _show_status_async
OrchestratorCLI._display_config = _display_config


if __name__ == '__main__':
    cli(obj={})
