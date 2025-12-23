"""Unit tests for configuration system."""

import pytest
import tempfile
import yaml
from pathlib import Path

from orchestrator.config import (
    OrchestratorConfig,
    ConfigLoader,
    get_default_config,
    ExecutionConfig,
    FindingsThresholds,
)
from orchestrator.exceptions import ConfigError


def test_default_config():
    """Test default configuration creation."""
    config = get_default_config()
    
    assert config.execution.max_retries == 3
    assert config.execution.copilot_mode == "direct"
    assert config.findings_thresholds.major == 0
    assert config.verification.build_enabled is True


def test_execution_config_validation():
    """Test execution config validation."""
    # Valid config
    config = ExecutionConfig(max_retries=5, copilot_mode="branch")
    assert config.max_retries == 5
    
    # Invalid max_retries
    with pytest.raises(ValueError):
        ExecutionConfig(max_retries=0)
    
    # Invalid copilot_mode
    with pytest.raises(ValueError):
        ExecutionConfig(copilot_mode="invalid")


def test_findings_thresholds_validation():
    """Test findings thresholds validation."""
    # Valid thresholds
    thresholds = FindingsThresholds(major=1, medium=2, minor=5)
    assert thresholds.major == 1
    
    # Invalid threshold (negative)
    with pytest.raises(ValueError):
        FindingsThresholds(major=-1)


def test_load_config_from_yaml():
    """Test loading configuration from YAML."""
    with tempfile.TemporaryDirectory() as tmpdir:
        config_path = Path(tmpdir) / "config.yaml"
        
        config_data = {
            "execution": {
                "max_retries": 5,
                "copilot_mode": "branch"
            },
            "findings_thresholds": {
                "major": 1,
                "medium": 3,
                "minor": 10
            }
        }
        
        with open(config_path, 'w') as f:
            yaml.dump(config_data, f)
        
        config = ConfigLoader.load_config(str(config_path))
        
        assert config.execution.max_retries == 5
        assert config.execution.copilot_mode == "branch"
        assert config.findings_thresholds.major == 1


def test_config_merge():
    """Test configuration merging."""
    base = {
        "execution": {
            "max_retries": 3,
            "copilot_mode": "direct"
        },
        "logging": {
            "level": "INFO"
        }
    }
    
    override = {
        "execution": {
            "max_retries": 5
        },
        "logging": {
            "level": "DEBUG"
        }
    }
    
    merged = ConfigLoader.merge_configs(base, override)
    
    assert merged["execution"]["max_retries"] == 5
    assert merged["execution"]["copilot_mode"] == "direct"
    assert merged["logging"]["level"] == "DEBUG"


def test_load_config_with_override():
    """Test loading config with local override."""
    with tempfile.TemporaryDirectory() as tmpdir:
        base_path = Path(tmpdir) / "config.yaml"
        override_path = Path(tmpdir) / "config.local.yaml"
        
        base_data = {
            "execution": {
                "max_retries": 3
            }
        }
        
        override_data = {
            "execution": {
                "max_retries": 5
            }
        }
        
        with open(base_path, 'w') as f:
            yaml.dump(base_data, f)
        
        with open(override_path, 'w') as f:
            yaml.dump(override_data, f)
        
        config = ConfigLoader.load_config(str(base_path), str(override_path))
        
        assert config.execution.max_retries == 5


def test_config_missing_file():
    """Test error handling for missing config file."""
    with pytest.raises(ConfigError):
        ConfigLoader.load_config("/nonexistent/config.yaml")


def test_config_invalid_yaml():
    """Test error handling for invalid YAML."""
    with tempfile.TemporaryDirectory() as tmpdir:
        config_path = Path(tmpdir) / "config.yaml"
        
        with open(config_path, 'w') as f:
            f.write("invalid: yaml: content: [[[")
        
        with pytest.raises(ConfigError):
            ConfigLoader.load_config(str(config_path))


def test_save_config():
    """Test saving configuration to YAML."""
    with tempfile.TemporaryDirectory() as tmpdir:
        output_path = Path(tmpdir) / "output.yaml"
        
        config = get_default_config()
        config.execution.max_retries = 7
        
        ConfigLoader.save_config(config, str(output_path))
        
        assert output_path.exists()
        
        # Load and verify
        loaded = ConfigLoader.load_config(str(output_path))
        assert loaded.execution.max_retries == 7


def test_custom_tests_validation():
    """Test custom tests configuration."""
    config_data = {
        "verification": {
            "custom_tests": [
                {
                    "name": "test1",
                    "command": "pytest",
                    "enabled": True,
                    "timeout": 60
                }
            ]
        }
    }
    
    config = OrchestratorConfig(**config_data)
    assert len(config.verification.custom_tests) == 1
    assert config.verification.custom_tests[0].name == "test1"


def test_logging_config_validation():
    """Test logging configuration validation."""
    # Valid levels
    for level in ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]:
        config = OrchestratorConfig(logging={"level": level})
        assert config.logging.level == level
    
    # Invalid level
    with pytest.raises(ValueError):
        OrchestratorConfig(logging={"level": "INVALID"})


def test_rag_config_validation():
    """Test RAG configuration validation."""
    # Valid config
    config = OrchestratorConfig(rag={"chunk_size": 500, "chunk_overlap": 100})
    assert config.rag.chunk_size == 500
    
    # Invalid chunk_size
    with pytest.raises(ValueError):
        OrchestratorConfig(rag={"chunk_size": 0})


def test_config_legacy_properties():
    """Test legacy property access."""
    config = get_default_config()
    
    # Test legacy properties still work
    assert config.max_retries == config.execution.max_retries
    assert config.retry_delay == config.execution.retry_delay
    assert config.copilot_mode == config.execution.copilot_mode
    assert config.branch_prefix == config.execution.branch_prefix
