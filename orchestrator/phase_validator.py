"""Validation and parsing for phase plan structures."""

import json
import re
from typing import List, Dict, Any, Tuple, Optional


class ValidationError(Exception):
    """Raised when phase validation fails."""
    pass


class PhaseValidator:
    """Validates phase structure and dependencies."""

    REQUIRED_FIELDS = ['phase_number', 'title', 'intent', 'size', 'files', 'acceptance_criteria']
    VALID_SIZES = ['small', 'medium', 'large']

    @staticmethod
    def validate_phase_structure(phase_dict: Dict[str, Any]) -> Tuple[bool, List[str]]:
        """Validate that a phase dictionary has the correct structure.

        Args:
            phase_dict: Phase dictionary to validate

        Returns:
            Tuple of (is_valid, error_messages)
        """
        errors = []

        # Check required fields
        for field in PhaseValidator.REQUIRED_FIELDS:
            if field not in phase_dict:
                errors.append(f"Missing required field: {field}")

        if errors:
            return False, errors

        # Validate phase_number
        if not isinstance(phase_dict['phase_number'], int) or phase_dict['phase_number'] <= 0:
            errors.append(f"phase_number must be positive integer, got: {phase_dict['phase_number']}")

        # Validate title
        if not isinstance(phase_dict['title'], str) or not phase_dict['title'].strip():
            errors.append("title must be non-empty string")

        # Validate intent
        if not isinstance(phase_dict['intent'], str) or not phase_dict['intent'].strip():
            errors.append("intent must be non-empty string")

        # Validate size
        if phase_dict['size'] not in PhaseValidator.VALID_SIZES:
            errors.append(f"size must be one of {PhaseValidator.VALID_SIZES}, got: {phase_dict['size']}")

        # Validate files
        if not isinstance(phase_dict['files'], list):
            errors.append("files must be a list")
        elif not all(isinstance(f, str) for f in phase_dict['files']):
            errors.append("all files must be strings")

        # Validate acceptance_criteria
        if not isinstance(phase_dict['acceptance_criteria'], list):
            errors.append("acceptance_criteria must be a list")
        elif len(phase_dict['acceptance_criteria']) == 0:
            errors.append("acceptance_criteria must not be empty")
        elif not all(isinstance(c, str) for c in phase_dict['acceptance_criteria']):
            errors.append("all acceptance_criteria must be strings")

        # Validate optional fields
        if 'dependencies' in phase_dict:
            if not isinstance(phase_dict['dependencies'], list):
                errors.append("dependencies must be a list")
            elif not all(isinstance(d, int) for d in phase_dict['dependencies']):
                errors.append("all dependencies must be integers")

        if 'risks' in phase_dict:
            if not isinstance(phase_dict['risks'], list):
                errors.append("risks must be a list")
            elif not all(isinstance(r, str) for r in phase_dict['risks']):
                errors.append("all risks must be strings")

        return len(errors) == 0, errors

    @staticmethod
    def parse_llm_response(response_text: str) -> List[Dict[str, Any]]:
        """Parse LLM response and extract JSON phase list.

        Handles responses with markdown code blocks, extra text, etc.

        Args:
            response_text: Raw LLM response text

        Returns:
            Parsed list of phase dictionaries

        Raises:
            ValidationError: If JSON cannot be parsed or is invalid
        """
        # Try to extract JSON from markdown code blocks
        json_match = re.search(r'```json\s*(.*?)\s*```', response_text, re.DOTALL)
        if json_match:
            json_text = json_match.group(1)
        else:
            # Try to extract JSON from generic code blocks
            code_match = re.search(r'```\s*(.*?)\s*```', response_text, re.DOTALL)
            if code_match:
                json_text = code_match.group(1)
            else:
                # No code blocks, try to find JSON array directly
                json_match = re.search(r'\[\s*\{.*?\}\s*\]', response_text, re.DOTALL)
                if json_match:
                    json_text = json_match.group(0)
                else:
                    json_text = response_text.strip()

        # Parse JSON
        try:
            phases = json.loads(json_text)
        except json.JSONDecodeError as e:
            raise ValidationError(f"Failed to parse JSON: {e}\n\nResponse text:\n{response_text}")

        # Validate it's a list
        if not isinstance(phases, list):
            raise ValidationError(f"Expected JSON array, got: {type(phases)}")

        if len(phases) == 0:
            raise ValidationError("Phase list is empty")

        # Validate each phase structure
        for i, phase in enumerate(phases):
            is_valid, errors = PhaseValidator.validate_phase_structure(phase)
            if not is_valid:
                error_msg = f"Phase {i+1} validation failed:\n" + "\n".join(f"  - {e}" for e in errors)
                raise ValidationError(error_msg)

        return phases

    @staticmethod
    def check_phase_dependencies(phases: List[Dict[str, Any]]) -> Tuple[bool, List[str]]:
        """Validate phase dependencies for consistency.

        Args:
            phases: List of phase dictionaries

        Returns:
            Tuple of (is_valid, error_messages)
        """
        errors = []
        phase_numbers = {p['phase_number'] for p in phases}

        # Build dependency graph
        dependencies = {}
        for phase in phases:
            phase_num = phase['phase_number']
            deps = phase.get('dependencies', [])
            dependencies[phase_num] = deps

            # Check that all dependencies reference valid phases
            for dep in deps:
                if dep not in phase_numbers:
                    errors.append(f"Phase {phase_num} depends on non-existent phase {dep}")

                # Check that dependencies come before dependent phases
                if dep >= phase_num:
                    errors.append(f"Phase {phase_num} cannot depend on phase {dep} (must depend on earlier phases)")

        # Check for circular dependencies using DFS
        def has_cycle(node: int, visited: set, rec_stack: set) -> bool:
            visited.add(node)
            rec_stack.add(node)

            for dep in dependencies.get(node, []):
                if dep not in visited:
                    if has_cycle(dep, visited, rec_stack):
                        return True
                elif dep in rec_stack:
                    return True

            rec_stack.remove(node)
            return False

        visited = set()
        for phase_num in phase_numbers:
            if phase_num not in visited:
                if has_cycle(phase_num, visited, set()):
                    errors.append(f"Circular dependency detected involving phase {phase_num}")

        return len(errors) == 0, errors
