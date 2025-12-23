"""Interactive terminal UI for phase planner using rich library."""

from typing import List, Dict, Any, Optional
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.prompt import Prompt, Confirm
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.syntax import Syntax
from rich.markdown import Markdown
from rich import box


class PlannerUI:
    """Interactive terminal UI for phase planning."""

    def __init__(self):
        """Initialize the UI with a rich console."""
        self.console = Console()

    def display_phase_summary(self, phases: List[Dict[str, Any]]) -> None:
        """Display a summary table of all phases.

        Args:
            phases: List of phase dictionaries
        """
        table = Table(title="Phase Plan Summary", box=box.ROUNDED)

        table.add_column("#", justify="right", style="cyan", no_wrap=True)
        table.add_column("Title", style="white")
        table.add_column("Size", justify="center")
        table.add_column("Files", justify="right", style="blue")
        table.add_column("Dependencies", justify="center", style="magenta")

        for phase in phases:
            phase_num = str(phase['phase_number'])
            title = phase['title']
            size = phase['size']
            files_count = str(len(phase.get('files', [])))
            deps = phase.get('dependencies', [])
            deps_str = ", ".join(str(d) for d in deps) if deps else "-"

            # Color code size
            if size == 'small':
                size_display = "[green]🟢 Small[/green]"
            elif size == 'medium':
                size_display = "[yellow]🟡 Medium[/yellow]"
            else:
                size_display = "[red]🔴 Large[/red]"

            table.add_row(phase_num, title, size_display, files_count, deps_str)

        self.console.print()
        self.console.print(table)
        self.console.print()

    def display_phase_detail(self, phase: Dict[str, Any]) -> None:
        """Display detailed view of a single phase.

        Args:
            phase: Phase dictionary
        """
        # Build detail content
        content_lines = []

        content_lines.append(f"[bold cyan]Phase {phase['phase_number']}: {phase['title']}[/bold cyan]")
        content_lines.append("")

        content_lines.append(f"[bold]Intent:[/bold] {phase['intent']}")
        content_lines.append("")

        size = phase['size']
        if size == 'small':
            size_display = "[green]🟢 Small[/green]"
        elif size == 'medium':
            size_display = "[yellow]🟡 Medium[/yellow]"
        else:
            size_display = "[red]🔴 Large[/red]"
        content_lines.append(f"[bold]Size:[/bold] {size_display}")
        content_lines.append("")

        # Files
        files = phase.get('files', [])
        if files:
            content_lines.append("[bold]Files to Modify:[/bold]")
            for file in files:
                content_lines.append(f"  • {file}")
            content_lines.append("")

        # Acceptance criteria
        criteria = phase.get('acceptance_criteria', [])
        if criteria:
            content_lines.append("[bold]Acceptance Criteria:[/bold]")
            for i, criterion in enumerate(criteria, 1):
                content_lines.append(f"  {i}. {criterion}")
            content_lines.append("")

        # Dependencies
        deps = phase.get('dependencies', [])
        if deps:
            content_lines.append("[bold]Dependencies:[/bold]")
            for dep in deps:
                content_lines.append(f"  • Phase {dep}")
            content_lines.append("")

        # Risks
        risks = phase.get('risks', [])
        if risks:
            content_lines.append("[bold]Risks & Mitigation:[/bold]")
            for risk in risks:
                content_lines.append(f"  • {risk}")
            content_lines.append("")

        content = "\n".join(content_lines)

        panel = Panel(
            content,
            title=f"Phase {phase['phase_number']} Details",
            border_style="blue",
            box=box.ROUNDED
        )

        self.console.print()
        self.console.print(panel)
        self.console.print()

    def prompt_approval_action(self) -> str:
        """Prompt user for action on the phase plan.

        Returns:
            User choice: 'approve', 'question', 'regenerate', 'detail', or 'abort'
        """
        self.console.print("[bold]What would you like to do?[/bold]")
        self.console.print("  [A] Approve and save phases")
        self.console.print("  [Q] Ask a question / provide feedback")
        self.console.print("  [R] Regenerate phase plan")
        self.console.print("  [D] View phase details")
        self.console.print("  [X] Abort planning")
        self.console.print()

        while True:
            choice = Prompt.ask(
                "Choose action",
                choices=["A", "Q", "R", "D", "X", "a", "q", "r", "d", "x"],
                default="A"
            ).upper()

            action_map = {
                'A': 'approve',
                'Q': 'question',
                'R': 'regenerate',
                'D': 'detail',
                'X': 'abort'
            }

            return action_map[choice]

    def prompt_phase_number(self, max_phase: int) -> int:
        """Prompt user for a phase number to view details.

        Args:
            max_phase: Maximum valid phase number

        Returns:
            Selected phase number
        """
        while True:
            try:
                phase_num = Prompt.ask(
                    f"Enter phase number (1-{max_phase})",
                    default="1"
                )
                num = int(phase_num)
                if 1 <= num <= max_phase:
                    return num
                else:
                    self.console.print(f"[red]Please enter a number between 1 and {max_phase}[/red]")
            except ValueError:
                self.console.print("[red]Please enter a valid number[/red]")

    def prompt_follow_up_question(self) -> str:
        """Prompt user for a follow-up question or feedback.

        Returns:
            User's question text
        """
        self.console.print()
        self.console.print("[bold]Enter your question or feedback:[/bold]")
        self.console.print("[dim](Press Enter twice when done)[/dim]")
        self.console.print()

        lines = []
        empty_count = 0

        while empty_count < 1:
            line = input()
            if not line.strip():
                empty_count += 1
            else:
                empty_count = 0
                lines.append(line)

        question = "\n".join(lines).strip()
        return question

    def show_progress(self, message: str) -> Progress:
        """Show a progress spinner with a message.

        Args:
            message: Progress message to display

        Returns:
            Progress object (caller should use as context manager)
        """
        progress = Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=self.console,
            transient=True
        )
        return progress

    def show_error(self, error_message: str, suggestion: Optional[str] = None) -> None:
        """Display an error message.

        Args:
            error_message: Error message to display
            suggestion: Optional suggestion for resolution
        """
        content = f"[bold red]Error:[/bold red] {error_message}"
        if suggestion:
            content += f"\n\n[yellow]Suggestion:[/yellow] {suggestion}"

        panel = Panel(
            content,
            title="Error",
            border_style="red",
            box=box.ROUNDED
        )

        self.console.print()
        self.console.print(panel)
        self.console.print()

    def show_success(self, message: str) -> None:
        """Display a success message.

        Args:
            message: Success message to display
        """
        panel = Panel(
            f"[bold green]✓[/bold green] {message}",
            border_style="green",
            box=box.ROUNDED
        )

        self.console.print()
        self.console.print(panel)
        self.console.print()

    def show_info(self, message: str, title: Optional[str] = None) -> None:
        """Display an informational message.

        Args:
            message: Info message to display
            title: Optional panel title
        """
        panel = Panel(
            message,
            title=title or "Info",
            border_style="blue",
            box=box.ROUNDED
        )

        self.console.print()
        self.console.print(panel)
        self.console.print()

    def confirm(self, message: str, default: bool = False) -> bool:
        """Prompt user for yes/no confirmation.

        Args:
            message: Confirmation message
            default: Default value

        Returns:
            True if confirmed, False otherwise
        """
        return Confirm.ask(message, default=default)
