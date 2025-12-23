"""
GitHub Issue Consolidator - Core consolidation logic and CLI interface.

This module provides functionality to consolidate a parent GitHub issue
with its child issues, track completion status, and generate structured
outputs in JSON and Markdown formats.
"""

import asyncio
import json
import os
from datetime import datetime
from pathlib import Path
from typing import List, Optional

import click
from jinja2 import Environment, FileSystemLoader, TemplateNotFound
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn

from agents.github_client import (
    GitHubAPIClient,
    GitHubAPIError,
    AuthenticationError,
    IssueNotFoundError,
    RateLimitError
)
from agents.issue_models import ConsolidatedIssues, GitHubIssue


console = Console()


class InvalidInputError(Exception):
    """Raised when user input validation fails."""
    pass


class IssueConsolidatorError(Exception):
    """Base exception for issue consolidator errors."""
    pass


class IssueConsolidator:
    """Core consolidation logic for GitHub issues."""
    
    def __init__(self, client: GitHubAPIClient):
        """
        Initialize issue consolidator.
        
        Args:
            client: GitHubAPIClient instance
        """
        self.client = client
        self.template_env = None
        self._setup_templates()
    
    def _setup_templates(self) -> None:
        """Setup Jinja2 template environment."""
        # Find templates directory
        current_dir = Path(__file__).parent.parent
        templates_dir = current_dir / "templates"
        
        if templates_dir.exists():
            self.template_env = Environment(
                loader=FileSystemLoader(str(templates_dir)),
                trim_blocks=True,
                lstrip_blocks=True
            )
    
    async def consolidate(
        self,
        parent_number: int,
        child_numbers: List[int],
        completed_numbers: Optional[List[int]] = None
    ) -> ConsolidatedIssues:
        """
        Consolidate parent issue with child issues.
        
        Args:
            parent_number: Parent issue number
            child_numbers: List of child issue numbers
            completed_numbers: List of completed issue numbers
            
        Returns:
            ConsolidatedIssues object
            
        Raises:
            IssueNotFoundError: If parent issue not found
            InvalidInputError: If input validation fails
        """
        if completed_numbers is None:
            completed_numbers = []
        
        # Validate inputs
        if parent_number <= 0:
            raise InvalidInputError("Parent issue number must be positive")
        
        if any(n <= 0 for n in child_numbers):
            raise InvalidInputError("All child issue numbers must be positive")
        
        if any(n not in child_numbers and n != parent_number for n in completed_numbers):
            console.print(
                "[yellow]Warning: Some completed issue numbers are not in the child list[/yellow]"
            )
        
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console
        ) as progress:
            # Fetch parent issue
            task1 = progress.add_task(f"Fetching parent issue #{parent_number}...", total=None)
            parent_issue = await self.client.fetch_issue(parent_number, include_comments=True)
            progress.remove_task(task1)
            console.print(f"[green]✓[/green] Fetched parent issue: {parent_issue.title}")
            
            # Fetch child issues concurrently
            task2 = progress.add_task(
                f"Fetching {len(child_numbers)} child issues...", 
                total=None
            )
            child_issues_dict = await self.client.fetch_issues_batch(
                child_numbers, 
                include_comments=True
            )
            progress.remove_task(task2)
            console.print(f"[green]✓[/green] Fetched {len(child_issues_dict)} child issues")
        
        # Build child issues list (maintaining order)
        child_issues = []
        for number in child_numbers:
            if number in child_issues_dict:
                child_issues.append(child_issues_dict[number])
        
        # Create metadata
        metadata = {
            'repo_owner': self.client.repo_owner,
            'repo_name': self.client.repo_name,
            'fetch_time': datetime.now().isoformat(),
            'total_issues': 1 + len(child_issues),
            'completed_count': len([n for n in completed_numbers if n in child_issues_dict]),
            'missing_issues': [n for n in child_numbers if n not in child_issues_dict]
        }
        
        return ConsolidatedIssues(
            parent_issue=parent_issue,
            child_issues=child_issues,
            completed_issue_numbers=completed_numbers,
            metadata=metadata
        )
    
    async def generate_json_output(
        self, 
        consolidated: ConsolidatedIssues, 
        output_path: Path
    ) -> None:
        """
        Generate JSON output file.
        
        Args:
            consolidated: ConsolidatedIssues object
            output_path: Output file path
            
        Raises:
            IssueConsolidatorError: On file write errors
        """
        try:
            # Ensure parent directory exists
            output_path.parent.mkdir(parents=True, exist_ok=True)
            
            # Serialize to JSON
            data = json.loads(consolidated.model_dump_json(indent=2))
            
            # Write to file
            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            
            console.print(f"[green]✓[/green] Generated JSON output: {output_path}")
            
        except PermissionError as e:
            raise IssueConsolidatorError(f"Permission denied writing to {output_path}: {e}")
        except OSError as e:
            raise IssueConsolidatorError(f"Failed to write JSON file {output_path}: {e}")
    
    async def generate_markdown_output(
        self,
        consolidated: ConsolidatedIssues,
        output_path: Path
    ) -> None:
        """
        Generate Markdown output file using Jinja2 template.
        
        Args:
            consolidated: ConsolidatedIssues object
            output_path: Output file path
            
        Raises:
            IssueConsolidatorError: On template or file write errors
        """
        try:
            if not self.template_env:
                raise IssueConsolidatorError("Template environment not initialized")
            
            # Load template
            try:
                template = self.template_env.get_template('consolidated_issues.md.j2')
            except TemplateNotFound:
                raise IssueConsolidatorError(
                    "Template 'consolidated_issues.md.j2' not found in templates directory"
                )
            
            # Prepare template context
            context = {
                'parent': consolidated.parent_issue,
                'child_issues': consolidated.child_issues,
                'completed': set(consolidated.completed_issue_numbers),
                'repo_owner': consolidated.metadata.get('repo_owner', ''),
                'repo_name': consolidated.metadata.get('repo_name', ''),
                'timestamp': consolidated.metadata.get('fetch_time', datetime.now().isoformat()),
                'total_count': len(consolidated.child_issues),
                'completed_count': consolidated.completed_count,
                'in_progress_count': consolidated.in_progress_count,
                'completion_percentage': f"{consolidated.completion_percentage:.1f}"
            }
            
            # Render template
            markdown_content = template.render(**context)
            
            # Ensure parent directory exists
            output_path.parent.mkdir(parents=True, exist_ok=True)
            
            # Write to file
            with open(output_path, 'w', encoding='utf-8') as f:
                f.write(markdown_content)
            
            console.print(f"[green]✓[/green] Generated Markdown output: {output_path}")
            
        except PermissionError as e:
            raise IssueConsolidatorError(f"Permission denied writing to {output_path}: {e}")
        except OSError as e:
            raise IssueConsolidatorError(f"Failed to write Markdown file {output_path}: {e}")


@click.command()
@click.option('--parent', required=True, type=int, help='Parent issue number')
@click.option('--children', required=True, help='Comma-separated child issue numbers')
@click.option('--completed', default='', help='Comma-separated completed issue numbers')
@click.option('--output', required=True, type=click.Path(), help='Output file path (without extension)')
@click.option('--repo', required=True, help='Repository in format owner/name')
@click.option('--token', envvar='GITHUB_TOKEN', help='GitHub personal access token')
@click.option(
    '--format', 
    'output_format',
    type=click.Choice(['md', 'json', 'both']), 
    default='both', 
    help='Output format'
)
def main(parent, children, completed, output, repo, token, output_format):
    """
    Consolidate GitHub issues into structured documentation.
    
    Example:
        python -m agents.issue_consolidator --parent 123 --children 124,125,126 
        --completed 124 --output issues --repo owner/repo
    """
    try:
        # Parse repository
        if '/' not in repo:
            console.print("[red]Error: Repository must be in format 'owner/name'[/red]")
            raise click.Abort()
        
        repo_owner, repo_name = repo.split('/', 1)
        
        # Parse child issue numbers
        try:
            child_numbers = [int(n.strip()) for n in children.split(',')]
        except ValueError:
            console.print("[red]Error: Invalid child issue numbers. Must be comma-separated integers.[/red]")
            raise click.Abort()
        
        # Parse completed issue numbers
        completed_numbers = []
        if completed:
            try:
                completed_numbers = [int(n.strip()) for n in completed.split(',')]
            except ValueError:
                console.print("[red]Error: Invalid completed issue numbers. Must be comma-separated integers.[/red]")
                raise click.Abort()
        
        # Validate token
        if not token:
            console.print(
                "[yellow]Warning: No GitHub token provided. "
                "Set GITHUB_TOKEN environment variable or use --token flag.[/yellow]"
            )
            console.print("[yellow]Public API rate limits will apply.[/yellow]")
        
        # Initialize client
        console.print(f"\n[bold]GitHub Issue Consolidator[/bold]")
        console.print(f"Repository: {repo_owner}/{repo_name}")
        console.print(f"Parent Issue: #{parent}")
        console.print(f"Child Issues: {len(child_numbers)}\n")
        
        client = GitHubAPIClient(token, repo_owner, repo_name)
        consolidator = IssueConsolidator(client)
        
        # Run consolidation
        async def run():
            consolidated = await consolidator.consolidate(
                parent_number=parent,
                child_numbers=child_numbers,
                completed_numbers=completed_numbers
            )
            
            # Generate outputs
            output_path = Path(output)
            
            if output_format in ('json', 'both'):
                json_path = output_path.with_suffix('.json')
                await consolidator.generate_json_output(consolidated, json_path)
            
            if output_format in ('md', 'both'):
                md_path = output_path.with_suffix('.md')
                await consolidator.generate_markdown_output(consolidated, md_path)
            
            return consolidated
        
        # Execute async workflow
        result = asyncio.run(run())
        
        # Display summary
        console.print(f"\n[bold green]✓ Consolidation complete![/bold green]")
        console.print(f"Parent: {result.parent_issue.title}")
        console.print(f"Child Issues: {len(result.child_issues)}")
        console.print(f"Completed: {result.completed_count}/{len(result.child_issues)}")
        console.print(f"Completion: {result.completion_percentage:.1f}%")
        
        if result.metadata.get('missing_issues'):
            console.print(
                f"\n[yellow]Warning: {len(result.metadata['missing_issues'])} "
                f"issue(s) not found: {result.metadata['missing_issues']}[/yellow]"
            )
        
    except AuthenticationError as e:
        console.print(f"\n[red]Authentication Error:[/red] {e}")
        raise click.Abort()
    except IssueNotFoundError as e:
        console.print(f"\n[red]Issue Not Found:[/red] {e}")
        raise click.Abort()
    except RateLimitError as e:
        console.print(f"\n[red]Rate Limit Error:[/red] {e}")
        raise click.Abort()
    except InvalidInputError as e:
        console.print(f"\n[red]Invalid Input:[/red] {e}")
        raise click.Abort()
    except GitHubAPIError as e:
        console.print(f"\n[red]GitHub API Error:[/red] {e}")
        raise click.Abort()
    except IssueConsolidatorError as e:
        console.print(f"\n[red]Consolidator Error:[/red] {e}")
        raise click.Abort()
    except Exception as e:
        console.print(f"\n[red]Unexpected Error:[/red] {e}")
        raise


if __name__ == '__main__':
    main()
