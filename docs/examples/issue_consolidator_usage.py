"""
Example: Programmatic usage of the GitHub Issue Consolidator.

This script demonstrates how to use the issue consolidator module
directly from Python code rather than via the CLI.
"""

import asyncio
from pathlib import Path
from agents.issue_consolidator import IssueConsolidator
from agents.github_client import GitHubAPIClient


async def main():
    """
    Example workflow for consolidating GitHub issues programmatically.
    """
    
    # Initialize GitHub API client
    # Token can be passed explicitly or will use GITHUB_TOKEN env var
    client = GitHubAPIClient(
        token=None,  # Uses GITHUB_TOKEN environment variable
        repo_owner="example-org",
        repo_name="example-project"
    )
    
    # Initialize consolidator
    consolidator = IssueConsolidator(client)
    
    # Consolidate parent issue with child issues
    print("Fetching and consolidating issues...")
    result = await consolidator.consolidate(
        parent_number=100,
        child_numbers=[101, 102, 103],
        completed_numbers=[101]  # Issue 101 is completed
    )
    
    # Access consolidated data
    print(f"\nParent Issue: {result.parent_issue.title}")
    print(f"State: {result.parent_issue.state}")
    print(f"Total Child Issues: {len(result.child_issues)}")
    print(f"Completed: {result.completed_count}/{len(result.child_issues)}")
    print(f"Completion Rate: {result.completion_percentage:.1f}%")
    
    # Generate outputs
    output_dir = Path("output")
    output_dir.mkdir(exist_ok=True)
    
    # Generate Markdown output
    md_path = output_dir / "consolidated-issues.md"
    await consolidator.generate_markdown_output(result, md_path)
    print(f"\n✓ Generated Markdown: {md_path}")
    
    # Generate JSON output
    json_path = output_dir / "consolidated-issues.json"
    await consolidator.generate_json_output(result, json_path)
    print(f"✓ Generated JSON: {json_path}")
    
    # Example: Iterate through child issues
    print("\n--- Child Issues ---")
    for issue in result.child_issues:
        status = "✓ COMPLETED" if issue.number in result.completed_issue_numbers else "○ In Progress"
        print(f"{status} #{issue.number}: {issue.title}")
        print(f"   State: {issue.state}, Comments: {len(issue.comments)}")
    
    # Example: Access metadata
    print("\n--- Metadata ---")
    print(f"Repository: {result.metadata['repo_owner']}/{result.metadata['repo_name']}")
    print(f"Fetch Time: {result.metadata['fetch_time']}")
    if result.metadata.get('missing_issues'):
        print(f"Missing Issues: {result.metadata['missing_issues']}")


async def example_with_explicit_token():
    """
    Example using an explicit GitHub token instead of environment variable.
    """
    
    # Provide token explicitly
    client = GitHubAPIClient(
        token="ghp_your_token_here",  # Replace with actual token
        repo_owner="facebook",
        repo_name="react"
    )
    
    consolidator = IssueConsolidator(client)
    
    # Fetch a single parent issue with multiple children
    result = await consolidator.consolidate(
        parent_number=1000,
        child_numbers=[1001, 1002, 1003, 1004],
        completed_numbers=[1001, 1002]
    )
    
    # Generate only JSON output
    await consolidator.generate_json_output(result, Path("react-issues.json"))
    
    return result


async def example_error_handling():
    """
    Example demonstrating error handling.
    """
    from agents.github_client import (
        AuthenticationError,
        IssueNotFoundError,
        RateLimitError
    )
    
    try:
        client = GitHubAPIClient(
            token=None,
            repo_owner="invalid-org",
            repo_name="invalid-repo"
        )
        
        consolidator = IssueConsolidator(client)
        
        result = await consolidator.consolidate(
            parent_number=999999,  # Non-existent issue
            child_numbers=[1, 2, 3],
            completed_numbers=[]
        )
        
    except AuthenticationError as e:
        print(f"Authentication failed: {e}")
        print("Make sure GITHUB_TOKEN environment variable is set")
        
    except IssueNotFoundError as e:
        print(f"Issue not found: {e}")
        print("Verify the issue number and repository are correct")
        
    except RateLimitError as e:
        print(f"Rate limit exceeded: {e}")
        print("Wait for rate limit to reset or use authenticated token")
        
    except Exception as e:
        print(f"Unexpected error: {e}")


async def example_batch_processing():
    """
    Example: Process multiple parent issues in batch.
    """
    
    client = GitHubAPIClient(
        token=None,
        repo_owner="example-org",
        repo_name="example-project"
    )
    
    consolidator = IssueConsolidator(client)
    
    # Define multiple parent issues to process
    issues_to_process = [
        {
            'parent': 100,
            'children': [101, 102, 103],
            'completed': [101],
            'output': 'auth-system'
        },
        {
            'parent': 200,
            'children': [201, 202],
            'completed': [],
            'output': 'payment-integration'
        },
        {
            'parent': 300,
            'children': [301, 302, 303, 304],
            'completed': [301, 302],
            'output': 'admin-dashboard'
        }
    ]
    
    # Process each issue group
    for issue_group in issues_to_process:
        try:
            print(f"\nProcessing parent issue #{issue_group['parent']}...")
            
            result = await consolidator.consolidate(
                parent_number=issue_group['parent'],
                child_numbers=issue_group['children'],
                completed_numbers=issue_group['completed']
            )
            
            # Generate outputs with custom naming
            output_base = Path("batch_output") / issue_group['output']
            await consolidator.generate_markdown_output(
                result, 
                output_base.with_suffix('.md')
            )
            await consolidator.generate_json_output(
                result, 
                output_base.with_suffix('.json')
            )
            
            print(f"✓ Completed: {result.parent_issue.title}")
            print(f"  Progress: {result.completed_count}/{len(result.child_issues)} child issues")
            
        except Exception as e:
            print(f"✗ Failed to process parent #{issue_group['parent']}: {e}")
            continue


if __name__ == '__main__':
    # Run the main example
    asyncio.run(main())
    
    # Uncomment to run other examples:
    # asyncio.run(example_with_explicit_token())
    # asyncio.run(example_error_handling())
    # asyncio.run(example_batch_processing())
