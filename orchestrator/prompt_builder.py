"""Utility for building prompts from templates and context."""

import yaml
from pathlib import Path
from typing import Dict, List, Any, Optional


class PromptBuilder:
    """Builds prompts for phase planning using templates and context."""

    def __init__(self, prompts_config_path: str):
        """Initialize the prompt builder.

        Args:
            prompts_config_path: Path to prompts.yaml configuration file
        """
        with open(prompts_config_path, 'r', encoding='utf-8') as f:
            self.config = yaml.safe_load(f)

    def build_phase_planning_prompt(
        self,
        issue_doc: str,
        repo_context: Dict[str, Any],
        prompts_config: Optional[Dict[str, Any]] = None
    ) -> str:
        """Build the complete phase planning prompt.

        Args:
            issue_doc: Issue documentation text
            repo_context: Repository context from RAG system
            prompts_config: Optional prompts configuration (uses self.config if None)

        Returns:
            Complete prompt string with system message and instructions
        """
        config = prompts_config or self.config

        # Format repository context sections
        formatted_context = self.format_repo_context(repo_context)

        # Build the prompt
        prompt_template = config['phase_planning_prompt']
        prompt = prompt_template.format(
            issue_documentation=issue_doc,
            hot_files=formatted_context['hot_files'],
            relevant_code=formatted_context['relevant_code'],
            documentation=formatted_context['documentation']
        )

        # Add output format instructions
        prompt += "\n\n" + config['output_format_instructions']

        # Prepend system prompt
        system_prompt = config['system_prompt']
        full_prompt = f"{system_prompt}\n\n{prompt}"

        return full_prompt

    def build_follow_up_prompt(
        self,
        issue_doc: str,
        repo_context: Dict[str, Any],
        conversation_history: List[Dict[str, str]],
        user_question: str,
        previous_phases: List[Dict[str, Any]]
    ) -> str:
        """Build prompt for follow-up questions and regeneration.

        Args:
            issue_doc: Original issue documentation
            repo_context: Repository context from RAG system
            conversation_history: List of previous Q&A pairs
            user_question: User's new question or feedback
            previous_phases: Previously generated phases

        Returns:
            Updated prompt with conversation history and question
        """
        # Format repository context sections
        formatted_context = self.format_repo_context(repo_context)

        # Format conversation history
        history_text = ""
        if conversation_history:
            history_text = "\n\n".join([
                f"Q: {item['question']}\nA: {item['answer']}"
                for item in conversation_history
            ])

        # Format previous phases
        import json
        phases_json = json.dumps(previous_phases, indent=2)

        # Build follow-up prompt
        follow_up_template = self.config['follow_up_prompt']
        follow_up = follow_up_template.format(
            issue_documentation=issue_doc,
            hot_files=formatted_context['hot_files'],
            relevant_code=formatted_context['relevant_code'],
            documentation=formatted_context['documentation'],
            user_question=user_question,
            previous_phases=phases_json,
            conversation_history=history_text or "No previous conversation"
        )

        # Add output format instructions
        follow_up += "\n\n" + self.config['output_format_instructions']

        # Prepend system prompt
        system_prompt = self.config['system_prompt']
        full_prompt = f"{system_prompt}\n\n{follow_up}"

        return full_prompt

    def format_repo_context(self, context_dict: Dict[str, Any]) -> Dict[str, str]:
        """Convert RAG context dictionary to formatted markdown sections.

        Args:
            context_dict: Context dictionary from RAG system

        Returns:
            Dictionary with formatted sections: hot_files, relevant_code, documentation
        """
        formatted = {
            'hot_files': '',
            'relevant_code': '',
            'documentation': ''
        }

        # Format hot files
        if 'hot_files' in context_dict and context_dict['hot_files']:
            hot_files_list = []
            for file_info in context_dict['hot_files']:
                if isinstance(file_info, dict):
                    path = file_info.get('path', file_info.get('file', 'unknown'))
                    commit_count = file_info.get('commit_count', file_info.get('commits', 0))
                    hot_files_list.append(f"- `{path}` ({commit_count} commits)")
                else:
                    hot_files_list.append(f"- `{file_info}`")
            formatted['hot_files'] = "\n".join(hot_files_list) if hot_files_list else "No hot files identified"
        else:
            formatted['hot_files'] = "No hot files identified"

        # Format relevant code chunks
        if 'code_chunks' in context_dict and context_dict['code_chunks']:
            code_chunks_list = []
            for chunk in context_dict['code_chunks']:
                if isinstance(chunk, dict):
                    file_path = chunk.get('file_path', chunk.get('path', 'unknown'))
                    content = chunk.get('content', chunk.get('text', ''))
                    start_line = chunk.get('start_line', chunk.get('line', ''))
                    
                    chunk_text = f"\n**{file_path}**"
                    if start_line:
                        chunk_text += f" (line {start_line})"
                    chunk_text += f"\n```\n{content}\n```"
                    code_chunks_list.append(chunk_text)
                else:
                    code_chunks_list.append(f"\n```\n{chunk}\n```")
            formatted['relevant_code'] = "\n".join(code_chunks_list) if code_chunks_list else "No relevant code found"
        else:
            formatted['relevant_code'] = "No relevant code found"

        # Format documentation
        if 'documentation' in context_dict and context_dict['documentation']:
            doc_list = []
            for doc in context_dict['documentation']:
                if isinstance(doc, dict):
                    title = doc.get('title', doc.get('path', 'Documentation'))
                    content = doc.get('content', doc.get('text', ''))
                    doc_list.append(f"\n**{title}**\n{content}")
                else:
                    doc_list.append(f"\n{doc}")
            formatted['documentation'] = "\n".join(doc_list) if doc_list else "No documentation found"
        else:
            formatted['documentation'] = "No documentation found"

        return formatted
