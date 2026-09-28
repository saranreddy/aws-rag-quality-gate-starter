"""Configuration management utilities."""

import os
from pathlib import Path
from typing import Any, Dict

import yaml


def load_config(config_path: str = "config/config.yaml") -> Dict[str, Any]:
    """Load configuration from YAML file.
    
    Args:
        config_path: Path to configuration file
        
    Returns:
        Dictionary containing configuration
        
    Raises:
        FileNotFoundError: If config file doesn't exist
        ValueError: If config contains placeholder values
    """
    if not Path(config_path).exists():
        raise FileNotFoundError(
            f"Config file not found: {config_path}\n"
            f"Copy config/config.example.yaml to config/config.yaml and update with your values."
        )
    
    with open(config_path, "r") as f:
        config = yaml.safe_load(f)
    
    validate_config(config)
    return config


def validate_config(config: Dict[str, Any]) -> None:
    """Validate configuration has required fields and no placeholders.
    
    Args:
        config: Configuration dictionary
        
    Raises:
        ValueError: If required fields are missing or contain placeholders
    """
    required_fields = ["aws_region", "db_host", "embedding_model_id", "llm_model_id"]
    
    for field in required_fields:
        if field not in config:
            raise ValueError(f"Missing required field in config: {field}")
    
    placeholder_patterns = ["xxxxx", "123456789012", "your-"]
    for pattern in placeholder_patterns:
        if any(pattern in str(v) for v in config.values() if isinstance(v, str)):
            raise ValueError(
                f"Config contains placeholder values. "
                f"Update config/config.yaml with actual values from 'terraform output'."
            )


def get_db_credentials(secret_name: str, region: str) -> Dict[str, str]:
    """Retrieve database credentials from AWS Secrets Manager.
    
    Args:
        secret_name: Name of the secret in Secrets Manager
        region: AWS region
        
    Returns:
        Dictionary with username and password
    """
    import boto3
    import json
    
    client = boto3.client("secretsmanager", region_name=region)
    response = client.get_secret_value(SecretId=secret_name)
    secret = json.loads(response["SecretString"])
    
    return {
        "username": secret["username"],
        "password": secret["password"],
    }
