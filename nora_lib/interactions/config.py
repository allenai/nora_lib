from dataclasses import dataclass
import os
import boto3
import json


@dataclass
class Config:
    """Service configuration for interactions."""

    base_url: str
    timeout: int
    token: str

    @staticmethod
    def _fetch_bearer_token(secret_id: str) -> str:
        secrets_manager = boto3.client("secretsmanager", region_name="us-west-2")
        return json.loads(
            secrets_manager.get_secret_value(SecretId=secret_id)["SecretString"]
        )["token"]

    @staticmethod
    def prod() -> "Config":
        return Config(
            base_url="https://s2ub.prod.s2.allenai.org/service/noraretrieval",
            timeout=30,
            token=Config._fetch_bearer_token("nora/prod/interaction-bearer-token"),
        )

    @staticmethod
    def dev() -> "Config":
        return Config(
            base_url="https://s2ub.dev.s2.allenai.org/service/noraretrieval",
            timeout=30,
            token=Config._fetch_bearer_token("nora/dev/interaction-bearer-token"),
        )

    @staticmethod
    def from_config(env: str = os.getenv("ENV", "local")) -> "Config":
        """Load the configuration based on the environment."""
        _envs = {
            "prod": Config.prod(),
            "eval": Config.dev(),
            "local": Config.dev(),
        }
        return _envs.get(env, Config.dev())


# Load the current environment's config using from_config method
current_config: Config = Config.from_config()
