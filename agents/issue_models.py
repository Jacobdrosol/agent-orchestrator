"""
Pydantic models for GitHub Issue Consolidation.

This module defines data models for representing GitHub issues,
comments, and consolidated issue hierarchies with proper validation.
"""

from datetime import datetime
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field, HttpUrl, field_validator


class IssueComment(BaseModel):
    """Model for a GitHub issue comment."""
    
    author: str = Field(..., description="Comment author username")
    body: str = Field(..., description="Comment body text")
    created_at: datetime = Field(..., description="Comment creation timestamp")
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }


class GitHubIssue(BaseModel):
    """Model for a GitHub issue with full details."""
    
    number: int = Field(..., gt=0, description="Issue number")
    title: str = Field(..., description="Issue title")
    body: Optional[str] = Field(None, description="Issue body/description")
    state: str = Field(..., description="Issue state (open/closed)")
    labels: List[str] = Field(default_factory=list, description="Issue labels")
    assignees: List[str] = Field(default_factory=list, description="Assigned users")
    created_at: datetime = Field(..., description="Creation timestamp")
    updated_at: datetime = Field(..., description="Last update timestamp")
    comments: List[IssueComment] = Field(default_factory=list, description="Issue comments")
    url: str = Field(..., description="Issue URL")
    
    @field_validator('number')
    @classmethod
    def validate_issue_number(cls, v: int) -> int:
        if v <= 0:
            raise ValueError('Issue number must be positive')
        return v
    
    @field_validator('state')
    @classmethod
    def validate_state(cls, v: str) -> str:
        if v.lower() not in ('open', 'closed'):
            raise ValueError('State must be "open" or "closed"')
        return v.lower()
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }


class IssueHierarchy(BaseModel):
    """Model representing parent-child issue relationships."""
    
    issue: GitHubIssue = Field(..., description="The issue")
    is_completed: bool = Field(False, description="Whether issue is marked as completed")
    children: List['IssueHierarchy'] = Field(default_factory=list, description="Child issues")


class ConsolidatedIssues(BaseModel):
    """Container model for consolidated issue hierarchy."""
    
    parent_issue: GitHubIssue = Field(..., description="Parent issue")
    child_issues: List[GitHubIssue] = Field(default_factory=list, description="Child issues")
    completed_issue_numbers: List[int] = Field(default_factory=list, description="Completed issue numbers")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Consolidation metadata")
    
    @property
    def total_issues(self) -> int:
        """Total number of issues (parent + children)."""
        return 1 + len(self.child_issues)
    
    @property
    def completed_count(self) -> int:
        """Number of completed child issues."""
        child_numbers = {issue.number for issue in self.child_issues}
        return len([n for n in self.completed_issue_numbers 
                    if n != self.parent_issue.number and n in child_numbers])
    
    @property
    def in_progress_count(self) -> int:
        """Number of in-progress child issues."""
        return len(self.child_issues) - self.completed_count
    
    @property
    def completion_percentage(self) -> float:
        """Completion percentage of child issues."""
        if not self.child_issues:
            return 0.0
        return (self.completed_count / len(self.child_issues)) * 100
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }
