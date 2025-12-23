"""
Async GitHub API client for fetching issues and comments.

This module provides an asynchronous client for interacting with the
GitHub REST API v3, with comprehensive error handling and rate limiting.
"""

import asyncio
import os
from datetime import datetime
from typing import List, Dict, Optional
from urllib.parse import urljoin

import httpx
from rich.console import Console

from agents.issue_models import GitHubIssue, IssueComment


console = Console()


class GitHubAPIError(Exception):
    """Base exception for GitHub API errors."""
    pass


class RateLimitError(GitHubAPIError):
    """Raised when GitHub API rate limit is exceeded."""
    pass


class AuthenticationError(GitHubAPIError):
    """Raised when GitHub authentication fails."""
    pass


class IssueNotFoundError(GitHubAPIError):
    """Raised when a GitHub issue is not found."""
    pass


class GitHubAPIClient:
    """Async client for GitHub REST API v3."""
    
    BASE_URL = "https://api.github.com"
    
    def __init__(self, token: Optional[str], repo_owner: str, repo_name: str):
        """
        Initialize GitHub API client.
        
        Args:
            token: GitHub personal access token (can be None for public repos)
            repo_owner: Repository owner username or organization
            repo_name: Repository name
        """
        self.token = token or os.getenv('GITHUB_TOKEN')
        self.repo_owner = repo_owner
        self.repo_name = repo_name
        self.headers = {
            'Accept': 'application/vnd.github.v3+json',
            'User-Agent': 'GitHub-Issue-Consolidator/1.0'
        }
        
        if self.token:
            self.headers['Authorization'] = f'token {self.token}'
    
    def _get_url(self, path: str) -> str:
        """Construct full API URL from path."""
        return urljoin(self.BASE_URL, path)
    
    async def _handle_rate_limit(self, response: httpx.Response, retry_count: int = 0) -> None:
        """
        Handle rate limiting with exponential backoff.
        
        Args:
            response: HTTP response object
            retry_count: Current retry attempt number
            
        Raises:
            RateLimitError: If max retries exceeded
        """
        if retry_count >= 3:
            raise RateLimitError("Maximum retry attempts exceeded for rate limit")
        
        reset_time = response.headers.get('X-RateLimit-Reset')
        if reset_time:
            wait_seconds = max(0, int(reset_time) - int(datetime.now().timestamp()))
            console.print(f"[yellow]Rate limit hit. Waiting {wait_seconds}s...[/yellow]")
            await asyncio.sleep(wait_seconds + 1)
        else:
            # Exponential backoff: 1s, 2s, 4s
            wait_seconds = 2 ** retry_count
            console.print(f"[yellow]Rate limit hit. Waiting {wait_seconds}s...[/yellow]")
            await asyncio.sleep(wait_seconds)
    
    async def _make_request(self, url: str, retry_count: int = 0) -> Dict:
        """
        Make authenticated request to GitHub API with retry logic.
        
        Args:
            url: Full API URL
            retry_count: Current retry attempt
            
        Returns:
            JSON response as dictionary
            
        Raises:
            AuthenticationError: On 401/403 errors
            RateLimitError: On rate limit exceeded
            IssueNotFoundError: On 404 errors
            GitHubAPIError: On other API errors
        """
        async with httpx.AsyncClient(timeout=30.0) as client:
            try:
                response = await client.get(url, headers=self.headers)
                
                # Handle rate limiting
                if response.status_code == 429:
                    await self._handle_rate_limit(response, retry_count)
                    return await self._make_request(url, retry_count + 1)
                
                # Handle authentication errors
                if response.status_code == 401:
                    raise AuthenticationError(
                        "GitHub authentication failed. Please set GITHUB_TOKEN environment variable "
                        "or use --token flag with a valid personal access token."
                    )
                
                if response.status_code == 403:
                    if 'rate limit' in response.text.lower():
                        await self._handle_rate_limit(response, retry_count)
                        return await self._make_request(url, retry_count + 1)
                    raise AuthenticationError(
                        "GitHub API access forbidden. Check your token permissions."
                    )
                
                # Handle not found
                if response.status_code == 404:
                    raise IssueNotFoundError(f"Resource not found: {url}")
                
                # Raise for other error status codes
                response.raise_for_status()
                
                return response.json()
                
            except httpx.ConnectError as e:
                raise GitHubAPIError(f"Failed to connect to GitHub API: {e}")
            except httpx.TimeoutError as e:
                if retry_count < 3:
                    console.print(f"[yellow]Request timeout. Retrying... ({retry_count + 1}/3)[/yellow]")
                    await asyncio.sleep(2 ** retry_count)
                    return await self._make_request(url, retry_count + 1)
                raise GitHubAPIError(f"GitHub API request timeout: {e}")
            except httpx.HTTPStatusError as e:
                raise GitHubAPIError(f"GitHub API error: {e}")
    
    async def fetch_issue_comments(self, issue_number: int) -> List[IssueComment]:
        """
        Fetch all comments for a GitHub issue with pagination.
        
        Args:
            issue_number: Issue number
            
        Returns:
            List of IssueComment objects
        """
        comments = []
        page = 1
        per_page = 100
        
        while True:
            url = self._get_url(
                f"/repos/{self.repo_owner}/{self.repo_name}/issues/{issue_number}/comments"
                f"?page={page}&per_page={per_page}"
            )
            
            try:
                data = await self._make_request(url)
                
                if not data:
                    break
                
                for comment_data in data:
                    comment = IssueComment(
                        author=comment_data['user']['login'],
                        body=comment_data['body'] or '',
                        created_at=datetime.fromisoformat(comment_data['created_at'].replace('Z', '+00:00'))
                    )
                    comments.append(comment)
                
                if len(data) < per_page:
                    break
                
                page += 1
                
            except IssueNotFoundError:
                console.print(f"[yellow]Comments not found for issue #{issue_number}[/yellow]")
                break
        
        return comments
    
    async def fetch_issue(self, issue_number: int, include_comments: bool = True) -> GitHubIssue:
        """
        Fetch a single GitHub issue with optional comments.
        
        Args:
            issue_number: Issue number
            include_comments: Whether to fetch issue comments
            
        Returns:
            GitHubIssue object
            
        Raises:
            IssueNotFoundError: If issue doesn't exist
            GitHubAPIError: On other API errors
        """
        url = self._get_url(f"/repos/{self.repo_owner}/{self.repo_name}/issues/{issue_number}")
        
        data = await self._make_request(url)
        
        # Fetch comments if requested
        comments = []
        if include_comments:
            comments = await self.fetch_issue_comments(issue_number)
        
        # Parse issue data
        issue = GitHubIssue(
            number=data['number'],
            title=data['title'],
            body=data['body'] or '',
            state=data['state'],
            labels=[label['name'] for label in data.get('labels', [])],
            assignees=[assignee['login'] for assignee in data.get('assignees', [])],
            created_at=datetime.fromisoformat(data['created_at'].replace('Z', '+00:00')),
            updated_at=datetime.fromisoformat(data['updated_at'].replace('Z', '+00:00')),
            comments=comments,
            url=data['html_url']
        )
        
        return issue
    
    async def fetch_issues_batch(
        self, 
        issue_numbers: List[int], 
        include_comments: bool = True
    ) -> Dict[int, GitHubIssue]:
        """
        Fetch multiple GitHub issues concurrently.
        
        Args:
            issue_numbers: List of issue numbers to fetch
            include_comments: Whether to fetch issue comments
            
        Returns:
            Dictionary mapping issue numbers to GitHubIssue objects
            (only includes successfully fetched issues)
        """
        async def fetch_with_error_handling(number: int) -> tuple[int, Optional[GitHubIssue]]:
            try:
                issue = await self.fetch_issue(number, include_comments)
                return (number, issue)
            except IssueNotFoundError:
                console.print(f"[yellow]Warning: Issue #{number} not found[/yellow]")
                return (number, None)
            except GitHubAPIError as e:
                console.print(f"[yellow]Warning: Failed to fetch issue #{number}: {e}[/yellow]")
                return (number, None)
        
        # Fetch all issues concurrently
        results = await asyncio.gather(*[fetch_with_error_handling(num) for num in issue_numbers])
        
        # Filter out failed fetches
        return {num: issue for num, issue in results if issue is not None}
