"""Unit tests for phase planner components."""

import pytest
import json
from unittest.mock import Mock, AsyncMock, patch
from orchestrator.phase_validator import PhaseValidator, ValidationError
from orchestrator.prompt_builder import PromptBuilder
from orchestrator.planner import PhasePlanner


class TestPhaseValidator:
    """Tests for PhaseValidator."""

    def test_validate_phase_structure_valid(self):
        """Test validation with correct phase structure."""
        phase = {
            'phase_number': 1,
            'title': 'Setup Infrastructure',
            'intent': 'Create base project structure',
            'size': 'small',
            'files': ['src/main.py', 'config.yaml'],
            'acceptance_criteria': ['Files created', 'Tests pass'],
            'dependencies': [],
            'risks': ['None identified']
        }

        is_valid, errors = PhaseValidator.validate_phase_structure(phase)
        assert is_valid
        assert len(errors) == 0

    def test_validate_phase_structure_missing_fields(self):
        """Test validation catches missing required fields."""
        phase = {
            'phase_number': 1,
            'title': 'Setup Infrastructure'
            # Missing: intent, size, files, acceptance_criteria
        }

        is_valid, errors = PhaseValidator.validate_phase_structure(phase)
        assert not is_valid
        assert len(errors) > 0
        assert any('intent' in err for err in errors)
        assert any('size' in err for err in errors)

    def test_validate_phase_structure_invalid_size(self):
        """Test validation rejects invalid size."""
        phase = {
            'phase_number': 1,
            'title': 'Test Phase',
            'intent': 'Test',
            'size': 'invalid_size',
            'files': [],
            'acceptance_criteria': ['Test']
        }

        is_valid, errors = PhaseValidator.validate_phase_structure(phase)
        assert not is_valid
        assert any('size must be one of' in err for err in errors)

    def test_parse_llm_response_valid_json(self):
        """Test JSON parsing with valid response."""
        response = json.dumps([{
            'phase_number': 1,
            'title': 'Phase 1',
            'intent': 'Do something',
            'size': 'small',
            'files': ['file.py'],
            'acceptance_criteria': ['Works']
        }])

        phases = PhaseValidator.parse_llm_response(response)
        assert len(phases) == 1
        assert phases[0]['phase_number'] == 1

    def test_parse_llm_response_with_markdown(self):
        """Test extraction from markdown code blocks."""
        response = """
Here are the phases:

```json
[{
    "phase_number": 1,
    "title": "Phase 1",
    "intent": "Do something",
    "size": "medium",
    "files": ["file.py"],
    "acceptance_criteria": ["Works"]
}]
```

That's the plan!
"""

        phases = PhaseValidator.parse_llm_response(response)
        assert len(phases) == 1
        assert phases[0]['size'] == 'medium'

    def test_parse_llm_response_invalid_json(self):
        """Test parsing handles invalid JSON."""
        response = "This is not JSON at all"

        with pytest.raises(ValidationError):
            PhaseValidator.parse_llm_response(response)

    def test_check_circular_dependencies(self):
        """Test dependency validation catches cycles."""
        phases = [
            {
                'phase_number': 1,
                'title': 'Phase 1',
                'intent': 'Test',
                'size': 'small',
                'files': [],
                'acceptance_criteria': ['Test'],
                'dependencies': [2]
            },
            {
                'phase_number': 2,
                'title': 'Phase 2',
                'intent': 'Test',
                'size': 'small',
                'files': [],
                'acceptance_criteria': ['Test'],
                'dependencies': [1]
            }
        ]

        is_valid, errors = PhaseValidator.check_phase_dependencies(phases)
        assert not is_valid
        assert any('cannot depend on phase 2' in err.lower() for err in errors)

    def test_check_valid_dependencies(self):
        """Test dependency validation accepts valid dependencies."""
        phases = [
            {
                'phase_number': 1,
                'title': 'Phase 1',
                'intent': 'Test',
                'size': 'small',
                'files': [],
                'acceptance_criteria': ['Test'],
                'dependencies': []
            },
            {
                'phase_number': 2,
                'title': 'Phase 2',
                'intent': 'Test',
                'size': 'small',
                'files': [],
                'acceptance_criteria': ['Test'],
                'dependencies': [1]
            }
        ]

        is_valid, errors = PhaseValidator.check_phase_dependencies(phases)
        assert is_valid
        assert len(errors) == 0


class TestPromptBuilder:
    """Tests for PromptBuilder."""

    @pytest.fixture
    def prompt_builder(self, tmp_path):
        """Create a PromptBuilder with test config."""
        config_path = tmp_path / "prompts.yaml"
        config_path.write_text("""
system_prompt: "You are a planner."
phase_planning_prompt: |
  Issue: {issue_documentation}
  Hot files: {hot_files}
  Code: {relevant_code}
  Docs: {documentation}
output_format_instructions: "Output JSON only."
follow_up_prompt: |
  Question: {user_question}
  Previous: {previous_phases}
  History: {conversation_history}
""")
        return PromptBuilder(str(config_path))

    def test_build_phase_planning_prompt(self, prompt_builder):
        """Test prompt assembly."""
        issue = "Fix the bug"
        context = {
            'hot_files': [{'path': 'main.py', 'commit_count': 5}],
            'code_chunks': [{'file_path': 'main.py', 'content': 'def main():', 'start_line': 1}],
            'documentation': [{'title': 'README', 'content': 'Overview'}]
        }

        prompt = prompt_builder.build_phase_planning_prompt(issue, context)

        assert "Fix the bug" in prompt
        assert "main.py" in prompt
        assert "You are a planner" in prompt
        assert "Output JSON only" in prompt

    def test_format_repo_context(self, prompt_builder):
        """Test repository context formatting."""
        context = {
            'hot_files': [{'path': 'file1.py', 'commit_count': 10}],
            'code_chunks': [{'file_path': 'file2.py', 'content': 'code', 'start_line': 5}],
            'documentation': [{'title': 'Guide', 'content': 'How to'}]
        }

        formatted = prompt_builder.format_repo_context(context)

        assert 'file1.py' in formatted['hot_files']
        assert '10 commits' in formatted['hot_files']
        assert 'file2.py' in formatted['relevant_code']
        assert 'Guide' in formatted['documentation']

    def test_build_follow_up_prompt(self, prompt_builder):
        """Test follow-up prompt building."""
        original = "Original prompt"
        history = [
            {'question': 'Q1', 'answer': 'A1'},
            {'question': 'Q2', 'answer': 'A2'}
        ]
        question = "New question"
        phases = [{'phase_number': 1, 'title': 'Test'}]

        prompt = prompt_builder.build_follow_up_prompt(original, history, question, phases)

        assert "New question" in prompt
        assert "Q1" in prompt
        assert "A1" in prompt


class TestPhasePlanner:
    """Tests for PhasePlanner integration."""

    @pytest.fixture
    def mock_config(self):
        """Create mock configuration."""
        config = Mock()
        config.base_path = "/tmp/test"
        config.execution = Mock()
        config.execution.max_retries = 3
        return config

    @pytest.fixture
    def mock_llm_client(self):
        """Create mock LLM client."""
        client = Mock()
        client.generate = AsyncMock(return_value='[{"phase_number": 1, "title": "Test", "intent": "Test phase", "size": "small", "files": ["test.py"], "acceptance_criteria": ["Works"]}]')
        return client

    @pytest.fixture
    def mock_rag_system(self):
        """Create mock RAG system."""
        rag = Mock()
        rag.initialize = AsyncMock()
        rag.get_phase_planning_context = AsyncMock(return_value={
            'hot_files': [],
            'code_chunks': [],
            'documentation': []
        })
        return rag

    @pytest.fixture
    def mock_state_manager(self):
        """Create mock state manager."""
        manager = Mock()
        manager.create_phase = AsyncMock(return_value="phase_id_1")
        manager.register_artifact = AsyncMock()
        manager.update_run_status = AsyncMock()
        return manager

    @pytest.mark.asyncio
    async def test_generate_phase_breakdown(
        self,
        mock_config,
        mock_llm_client,
        mock_rag_system,
        mock_state_manager,
        tmp_path
    ):
        """Test phase breakdown generation."""
        # Setup test environment
        config_dir = tmp_path / "config"
        config_dir.mkdir()
        (config_dir / "prompts.yaml").write_text("""
system_prompt: "Test"
phase_planning_prompt: "Test: {issue_documentation} {hot_files} {relevant_code} {documentation}"
output_format_instructions: "JSON"
""")

        templates_dir = tmp_path / "templates"
        templates_dir.mkdir()

        mock_config.base_path = str(tmp_path)

        planner = PhasePlanner(
            mock_config,
            mock_llm_client,
            mock_rag_system,
            mock_state_manager
        )

        # Test generation
        phases = await planner.generate_phase_breakdown("Test issue", "/repo")

        assert len(phases) == 1
        assert phases[0]['phase_number'] == 1
        assert mock_llm_client.generate.called
        assert mock_rag_system.get_phase_planning_context.called


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
