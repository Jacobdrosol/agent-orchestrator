"""
Unit tests for GitHub API Client.

Tests API interactions, error handling, and rate limiting.
"""

from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest
from agents.github_client import (
    GitHubAPIClient,
    GitHubAPIError,
    RateLimitError,
    AuthenticationError,
    IssueNotFoundError
)
from agents.issue_models import GitHubIssue, IssueComment


@pytest.fixture
def sample_issue_data():
    """Sample GitHub API response for an issue."""
    return {
        'number': 123,
        'title': 'Test Issue',
        'body': 'Test description',
        'state': 'open',
        'labels': [{'name': 'bug'}, {'name': 'priority-high'}],
        'assignees': [{'login': 'user1'}, {'login': 'user2'}],
        'created_at': '2024-01-01T10:00:00Z',
        'updated_at': '2024-01-15T09:30:00Z',
        'html_url': 'https://github.com/owner/repo/issues/123'
    }


@pytest.fixture
def sample_comment_data():
    """Sample GitHub API response for comments."""
    return [
        {
            'user': {'login': 'commenter1'},
            'body': 'First comment',
            'created_at': '2024-01-05T14:20:00Z'
        },
        {
            'user': {'login': 'commenter2'},
            'body': 'Second comment',
            'created_at': '2024-01-06T10:15:00Z'
        }
    ]


class TestGitHubAPIClient:
    """Test suite for GitHubAPIClient."""
    
    def test_init_with_token(self):
        """Test client initialization with token."""
        client = GitHubAPIClient(
            token="ghp_test_token",
            repo_owner="owner",
            repo_name="repo"
        )
        
        assert client.token == "ghp_test_token"
        assert client.repo_owner == "owner"
        assert client.repo_name == "repo"
        assert 'Authorization' in client.headers
        assert client.headers['Authorization'] == 'token ghp_test_token'
    
    def test_init_without_token(self):
        """Test client initialization without token."""
        with patch.dict('os.environ', {}, clear=True):
            client = GitHubAPIClient(
                token=None,
                repo_owner="owner",
                repo_name="repo"
            )
            
            assert client.token is None
            assert 'Authorization' not in client.headers
    
    def test_init_with_env_var(self):
        """Test client initialization with GITHUB_TOKEN env var."""
        with patch.dict('os.environ', {'GITHUB_TOKEN': 'ghp_env_token'}):
            client = GitHubAPIClient(
                token=None,
                repo_owner="owner",
                repo_name="repo"
            )
            
            assert client.token == "ghp_env_token"
            assert 'Authorization' in client.headers
    
    @pytest.mark.asyncio
    async def test_fetch_issue_success(self, sample_issue_data):
        """Test successful issue fetching."""
        client = GitHubAPIClient("token", "owner", "repo")
        
        # Mock HTTP response
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = sample_issue_data
        
        with patch('httpx.AsyncClient') as mock_client:
            mock_client.return_value.__aenter__.return_value.get = AsyncMock(
                return_value=mock_response
            )
            
            # Mock comment fetch to return empty list
            with patch.object(client, 'fetch_issue_comments', return_value=[]):
                issue = await client.fetch_issue(123, include_comments=False)
        
        assert isinstance(issue, GitHubIssue)
        assert issue.number == 123
        assert issue.title == "Test Issue"
        assert issue.state == "open"
        assert "bug" in issue.labels
        assert "user1" in issue.assignees
    
    @pytest.mark.asyncio
    async def test_fetch_issue_not_found(self):
        """Test handling of 404 error."""
        client = GitHubAPIClient("token", "owner", "repo")
        
        mock_response = MagicMock()
        mock_response.status_code = 404
        
        with patch('httpx.AsyncClient') as mock_client:
            mock_client.return_value.__aenter__.return_value.get = AsyncMock(
                return_value=mock_response
            )
            
            with pytest.raises(IssueNotFoundError):
                await client.fetch_issue(999999)
    
    @pytest.mark.asyncio
    async def test_fetch_issue_auth_error_401(self):
        """Test handling of 401 authentication error."""
        client = GitHubAPIClient("invalid_token", "owner", "repo")
        
        mock_response = MagicMock()
        mock_response.status_code = 401
        
        with patch('httpx.AsyncClient') as mock_client:
            mock_client.return_value.__aenter__.return_value.get = AsyncMock(
                return_value=mock_response
            )
            
            with pytest.raises(AuthenticationError, match="authentication failed"):
                await client.fetch_issue(123)
    
    @pytest.mark.asyncio
    async def test_fetch_issue_rate_limit(self):
        """Test handling of rate limit (429)."""
        client = GitHubAPIClient("token", "owner", "repo")
        
        # First response: rate limited
        mock_response_limited = MagicMock()
        mock_response_limited.status_code = 429
        mock_response_limited.headers = {
            'X-RateLimit-Reset': str(int(datetime.now().timestamp()) + 1)
        }
        
        # Second response: success
        mock_response_success = MagicMock()
        mock_response_success.status_code = 200
        mock_response_success.json.return_value = {
            'number': 123,
            'title': 'Test',
            'body': '',
            'state': 'open',
            'labels': [],
            'assignees': [],
            'created_at': '2024-01-01T00:00:00Z',
            'updated_at': '2024-01-01T00:00:00Z',
            'html_url': 'https://github.com/owner/repo/issues/123'
        }
        
        with patch('httpx.AsyncClient') as mock_client:
            mock_get = AsyncMock(side_effect=[mock_response_limited, mock_response_success])
            mock_client.return_value.__aenter__.return_value.get = mock_get
            
            with patch.object(client, 'fetch_issue_comments', return_value=[]):
                with patch('asyncio.sleep'):  # Skip actual sleep
                    issue = await client.fetch_issue(123, include_comments=False)
        
        assert issue.number == 123
        assert mock_get.call_count == 2  # Should retry after rate limit
    
    @pytest.mark.asyncio
    async def test_fetch_issue_rate_limit_max_retries(self):
        """Test max retries on rate limit."""
        client = GitHubAPIClient("token", "owner", "repo")
        
        mock_response = MagicMock()
        mock_response.status_code = 429
        mock_response.headers = {}
        
        with patch('httpx.AsyncClient') as mock_client:
            mock_client.return_value.__aenter__.return_value.get = AsyncMock(
                return_value=mock_response
            )
            
            with patch('asyncio.sleep'):
                with pytest.raises(RateLimitError, match="Maximum retry attempts"):
                    await client.fetch_issue(123)
    
    @pytest.mark.asyncio
    async def test_fetch_issue_comments(self, sample_comment_data):
        """Test fetching issue comments."""
        client = GitHubAPIClient("token", "owner", "repo")
        
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = sample_comment_data
        
        with patch('httpx.AsyncClient') as mock_client:
            mock_client.return_value.__aenter__.return_value.get = AsyncMock(
                return_value=mock_response
            )
            
            comments = await client.fetch_issue_comments(123)
        
        assert len(comments) == 2
        assert isinstance(comments[0], IssueComment)
        assert comments[0].author == "commenter1"
        assert comments[0].body == "First comment"
        assert comments[1].author == "commenter2"
    
    @pytest.mark.asyncio
    async def test_fetch_issue_comments_pagination(self):
        """Test comment pagination."""
        client = GitHubAPIClient("token", "owner", "repo")
        
        # First page: 100 comments
        page1_data = [
            {
                'user': {'login': f'user{i}'},
                'body': f'Comment {i}',
                'created_at': '2024-01-01T00:00:00Z'
            }
            for i in range(100)
        ]
        
        # Second page: 50 comments
        page2_data = [
            {
                'user': {'login': f'user{i}'},
                'body': f'Comment {i}',
                'created_at': '2024-01-01T00:00:00Z'
            }
            for i in range(100, 150)
        ]
        
        mock_response1 = MagicMock()
        mock_response1.status_code = 200
        mock_response1.json.return_value = page1_data
        
        mock_response2 = MagicMock()
        mock_response2.status_code = 200
        mock_response2.json.return_value = page2_data
        
        with patch('httpx.AsyncClient') as mock_client:
            mock_get = AsyncMock(side_effect=[mock_response1, mock_response2])
            mock_client.return_value.__aenter__.return_value.get = mock_get
            
            comments = await client.fetch_issue_comments(123)
        
        assert len(comments) == 150
        assert mock_get.call_count == 2
    
    @pytest.mark.asyncio
    async def test_fetch_issues_batch(self, sample_issue_data):
        """Test batch fetching of multiple issues."""
        client = GitHubAPIClient("token", "owner", "repo")
        
        # Mock fetch_issue to return different issues
        async def mock_fetch_issue(number, include_comments=True):
            return GitHubIssue(
                number=number,
                title=f"Issue {number}",
                body="",
                state="open",
                labels=[],
                assignees=[],
                created_at=datetime(2024, 1, 1),
                updated_at=datetime(2024, 1, 1),
                comments=[],
                url=f"https://github.com/owner/repo/issues/{number}"
            )
        
        with patch.object(client, 'fetch_issue', side_effect=mock_fetch_issue):
            issues = await client.fetch_issues_batch([101, 102, 103])
        
        assert len(issues) == 3
        assert 101 in issues
        assert 102 in issues
        assert 103 in issues
        assert issues[101].number == 101
    
    @pytest.mark.asyncio
    async def test_fetch_issues_batch_with_missing(self):
        """Test batch fetch with some missing issues."""
        client = GitHubAPIClient("token", "owner", "repo")
        
        async def mock_fetch_issue(number, include_comments=True):
            if number == 102:
                raise IssueNotFoundError(f"Issue {number} not found")
            return GitHubIssue(
                number=number,
                title=f"Issue {number}",
                body="",
                state="open",
                labels=[],
                assignees=[],
                created_at=datetime(2024, 1, 1),
                updated_at=datetime(2024, 1, 1),
                comments=[],
                url=f"https://github.com/owner/repo/issues/{number}"
            )
        
        with patch.object(client, 'fetch_issue', side_effect=mock_fetch_issue):
            issues = await client.fetch_issues_batch([101, 102, 103])
        
        # Should only include successfully fetched issues
        assert len(issues) == 2
        assert 101 in issues
        assert 102 not in issues  # Missing
        assert 103 in issues
    
    @pytest.mark.asyncio
    async def test_network_timeout_retry(self):
        """Test retry logic on network timeout."""
        client = GitHubAPIClient("token", "owner", "repo")
        
        # First two calls timeout, third succeeds
        mock_response_success = MagicMock()
        mock_response_success.status_code = 200
        mock_response_success.json.return_value = {
            'number': 123,
            'title': 'Test',
            'body': '',
            'state': 'open',
            'labels': [],
            'assignees': [],
            'created_at': '2024-01-01T00:00:00Z',
            'updated_at': '2024-01-01T00:00:00Z',
            'html_url': 'https://github.com/owner/repo/issues/123'
        }
        
        with patch('httpx.AsyncClient') as mock_client:
            mock_get = AsyncMock(side_effect=[
                httpx.TimeoutError("Timeout"),
                httpx.TimeoutError("Timeout"),
                mock_response_success
            ])
            mock_client.return_value.__aenter__.return_value.get = mock_get
            
            with patch.object(client, 'fetch_issue_comments', return_value=[]):
                with patch('asyncio.sleep'):
                    issue = await client.fetch_issue(123, include_comments=False)
        
        assert issue.number == 123
        assert mock_get.call_count == 3
    
    @pytest.mark.asyncio
    async def test_network_timeout_max_retries(self):
        """Test max retries on network timeout."""
        client = GitHubAPIClient("token", "owner", "repo")
        
        with patch('httpx.AsyncClient') as mock_client:
            mock_get = AsyncMock(side_effect=httpx.TimeoutError("Timeout"))
            mock_client.return_value.__aenter__.return_value.get = mock_get
            
            with patch('asyncio.sleep'):
                with pytest.raises(GitHubAPIError, match="timeout"):
                    await client.fetch_issue(123)
        
        assert mock_get.call_count == 4  # Initial + 3 retries
