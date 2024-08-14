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
    def prod(url, token) -> "Config":
        return Config(
            base_url=url,
            timeout=30,
            token=token,
        )

    @staticmethod
    def from_env(env: str = os.getenv("ENV", "local")) -> "Config":
        """Load the configuration based on the environment."""
        url = os.getenv(
            "INTERACTION_STORE_URL",
            "https://s2ub.prod.s2.allenai.org/service/noraretrieval",
        )
        token = os.getenv(
            "INTERACTION_STORE_TOKEN",
            Config._fetch_bearer_token("nora/prod/interaction-bearer-token"),
        )
        _envs = {
            "prod": Config.prod(url, token),
            "eval": Config.prod(url, token),
            "local": Config.prod(url, token),
        }
        return _envs.get(env, Config.prod(url, token))
