"""Configuration system for Agent Orchestrator."""

import logging
from pathlib import Path
from typing import Optional, Dict, Any, List
import yaml
from pydantic import BaseModel, Field, field_validator, ConfigDict

from .exceptions import ConfigError

logger = logging.getLogger(__name__)


class CustomTest(BaseModel):
    """Custom test configuration."""
    name: str
    command: str
    enabled: bool = True
    working_directory: Optional[str] = None
    timeout: int = 60
    
    model_config = ConfigDict(from_attributes=True)


class VerificationConfig(BaseModel):
    """Verification settings."""
    build_enabled: bool = True
    test_enabled: bool = True
    lint_enabled: bool = True
    security_scan_enabled: bool = True
    spec_validation_enabled: bool = True
    custom_tests: List[CustomTest] = Field(default_factory=list)
    
    model_config = ConfigDict(from_attributes=True)


class RAGConfig(BaseModel):
    """RAG system settings."""
    chunk_size: int = 1000
    chunk_overlap: int = 200
    max_retrieved_chunks: int = 20
    semantic_search_enabled: bool = True
    symbol_search_enabled: bool = True
    index_on_startup: bool = False
    
    model_config = ConfigDict(from_attributes=True)
    
    @field_validator('chunk_size', 'chunk_overlap', 'max_retrieved_chunks')
    @classmethod
    def validate_positive(cls, v: int) -> int:
        if v <= 0:
            raise ValueError("Value must be positive")
        return v


class GitConfig(BaseModel):
    """Git integration settings."""
    auto_pull: bool = True
    auto_commit: bool = False
    commit_message_template: str = "Phase {phase_number}: {phase_title}\n\n{phase_intent}"
    
    model_config = ConfigDict(from_attributes=True)


class LoggingConfig(BaseModel):
    """Logging configuration."""
    level: str = "INFO"
    file_path: str = "data/orchestrator.log"
    console_enabled: bool = True
    max_file_size_mb: int = 50
    backup_count: int = 5
    
    model_config = ConfigDict(from_attributes=True)
    
    @field_validator('level')
    @classmethod
    def validate_level(cls, v: str) -> str:
        allowed = {'DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL'}
        v_upper = v.upper()
        if v_upper not in allowed:
            raise ValueError(f"Log level must be one of {allowed}")
        return v_upper


class FindingsThresholds(BaseModel):
    """Thresholds for findings to block phase completion."""
    major: int = 0
    medium: int = 0
    minor: int = 5
    
    model_config = ConfigDict(from_attributes=True)
    
    @field_validator('major', 'medium', 'minor')
    @classmethod
    def validate_non_negative(cls, v: int) -> int:
        if v < 0:
            raise ValueError("Threshold must be non-negative")
        return v


class ArtifactsConfig(BaseModel):
    """Artifact management settings."""
    retention_days: int = 30
    base_path: str = "data/artifacts"
    compress_old_artifacts: bool = True
    
    model_config = ConfigDict(from_attributes=True)


class PathsConfig(BaseModel):
    """Path configuration for backward compatibility."""
    artifact_base_path: str = "data/artifacts"
    vector_db_path: str = "data/vector_db"
    
    model_config = ConfigDict(from_attributes=True)


class LLMConfig(BaseModel):
    """LLM configuration."""
    host: str = "http://localhost:11434"
    model: str = "llama3.2:latest"
    temperature: float = 0.7
    max_tokens: int = 4000
    embedding_model: str = "nomic-embed-text"
    
    model_config = ConfigDict(from_attributes=True)


class ExecutionConfig(BaseModel):
    """Execution settings."""
    max_retries: int = 3
    retry_delay: float = 5.0
    copilot_mode: str = "direct"
    branch_prefix: str = "orchestrator/"
    delete_failed_branches: bool = False
    
    model_config = ConfigDict(from_attributes=True)
    
    @field_validator('max_retries')
    @classmethod
    def validate_max_retries(cls, v: int) -> int:
        if v < 1:
            raise ValueError("max_retries must be at least 1")
        return v
    
    @field_validator('copilot_mode')
    @classmethod
    def validate_copilot_mode(cls, v: str) -> str:
        allowed = {'direct', 'branch'}
        if v not in allowed:
            raise ValueError(f"copilot_mode must be one of {allowed}")
        return v


class OrchestratorConfig(BaseModel):
    """Main orchestrator configuration."""
    execution: ExecutionConfig = Field(default_factory=ExecutionConfig)
    findings_thresholds: FindingsThresholds = Field(default_factory=FindingsThresholds)
    verification: VerificationConfig = Field(default_factory=VerificationConfig)
    rag: RAGConfig = Field(default_factory=RAGConfig)
    git: GitConfig = Field(default_factory=GitConfig)
    artifacts: ArtifactsConfig = Field(default_factory=ArtifactsConfig)
    logging: LoggingConfig = Field(default_factory=LoggingConfig)
    paths: PathsConfig = Field(default_factory=PathsConfig)
    llm: LLMConfig = Field(default_factory=LLMConfig)
    models: Dict[str, Any] = Field(default_factory=dict)
    model_overrides: Dict[str, Any] = Field(default_factory=dict)
    base_path: str = "."  # Project base path
    
    model_config = ConfigDict(from_attributes=True)
    
    # Legacy compatibility - expose execution settings at top level
    @property
    def max_retries(self) -> int:
        return self.execution.max_retries
    
    @property
    def retry_delay(self) -> float:
        return self.execution.retry_delay
    
    @property
    def copilot_mode(self) -> str:
        return self.execution.copilot_mode
    
    @property
    def branch_prefix(self) -> str:
        return self.execution.branch_prefix


class ConfigLoader:
    """Load and validate configuration from YAML files."""
    
    @staticmethod
    def load_config(
        config_path: str,
        local_override_path: Optional[str] = None
    ) -> OrchestratorConfig:
        """Load configuration with optional local overrides.
        
        Args:
            config_path: Path to main config file
            local_override_path: Optional path to local override file
            
        Returns:
            Validated OrchestratorConfig
            
        Raises:
            ConfigError: If config loading or validation fails
        """
        try:
            # Load base config
            config_dict = ConfigLoader._load_yaml(config_path)
            
            # Load and merge local overrides if provided
            if local_override_path and Path(local_override_path).exists():
                logger.info(f"Loading local config overrides from {local_override_path}")
                override_dict = ConfigLoader._load_yaml(local_override_path)
                config_dict = ConfigLoader.merge_configs(config_dict, override_dict)
            
            # Load models config if specified
            if 'models_path' in config_dict:
                models_path = config_dict['models_path']
                logger.info(f"Loading models config from {models_path}")
                config_dict['models'] = ConfigLoader.load_models_config(models_path)
            
            # Validate and create config object
            config = OrchestratorConfig(**config_dict)
            ConfigLoader.validate_paths(config)
            
            logger.info("Configuration loaded successfully")
            return config
            
        except Exception as e:
            logger.error(f"Failed to load configuration: {e}")
            raise ConfigError(f"Failed to load configuration: {e}")
    
    @staticmethod
    def _load_yaml(path: str) -> dict:
        """Load YAML file."""
        try:
            with open(path, 'r') as f:
                data = yaml.safe_load(f)
                return data if data else {}
        except FileNotFoundError:
            raise ConfigError(f"Config file not found: {path}")
        except yaml.YAMLError as e:
            raise ConfigError(f"Invalid YAML in {path}: {e}")
    
    @staticmethod
    def load_models_config(models_path: str) -> dict:
        """Load models configuration from YAML."""
        return ConfigLoader._load_yaml(models_path)
    
    @staticmethod
    def merge_configs(base: dict, override: dict) -> dict:
        """Deep merge two configuration dictionaries.
        
        Args:
            base: Base configuration
            override: Override configuration
            
        Returns:
            Merged configuration
        """
        result = base.copy()
        
        for key, value in override.items():
            if key in result and isinstance(result[key], dict) and isinstance(value, dict):
                result[key] = ConfigLoader.merge_configs(result[key], value)
            else:
                result[key] = value
        
        return result
    
    @staticmethod
    def validate_paths(config: OrchestratorConfig):
        """Validate that required paths exist.
        
        Args:
            config: Configuration to validate
            
        Raises:
            ConfigError: If validation fails
        """
        # Create artifact directory if it doesn't exist
        artifact_path = Path(config.artifacts.base_path)
        artifact_path.mkdir(parents=True, exist_ok=True)
        
        # Create log directory if it doesn't exist
        log_path = Path(config.logging.file_path)
        log_path.parent.mkdir(parents=True, exist_ok=True)
    
    @staticmethod
    def save_config(config: OrchestratorConfig, output_path: str):
        """Save configuration to YAML file.
        
        Args:
            config: Configuration to save
            output_path: Output file path
        """
        try:
            config_dict = config.model_dump()
            
            Path(output_path).parent.mkdir(parents=True, exist_ok=True)
            with open(output_path, 'w') as f:
                yaml.dump(config_dict, f, default_flow_style=False, sort_keys=False)
            
            logger.info(f"Configuration saved to {output_path}")
        except Exception as e:
            logger.error(f"Failed to save configuration: {e}")
            raise ConfigError(f"Failed to save configuration: {e}")


def get_default_config() -> OrchestratorConfig:
    """Get default configuration.
    
    Returns:
        Default OrchestratorConfig
    """
    return OrchestratorConfig()
