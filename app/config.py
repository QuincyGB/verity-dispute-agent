"""Environment-based configuration.

No credentials live in this repo. Airwallex API keys and the webhook signing
secret are injected via environment variables in deployment (and never in
the sandbox demo data committed here).
"""

from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    # Airwallex API base. Sandbox is the default so nothing in this repo can
    # touch a live account by accident.
    airwallex_base_url: str = os.environ.get(
        "AIRWALLEX_BASE_URL", "https://api.sandbox.airwallex.com"
    )
    airwallex_client_id: str | None = os.environ.get("AIRWALLEX_CLIENT_ID")
    airwallex_api_key: str | None = os.environ.get("AIRWALLEX_API_KEY")
    webhook_secret: str | None = os.environ.get("AIRWALLEX_WEBHOOK_SECRET")

    # Verity behaviour
    dry_run: bool = os.environ.get("VERITY_DRY_RUN", "true").lower() == "true"
    metal_anchor_enabled: bool = (
        os.environ.get("VERITY_METAL_ANCHOR", "false").lower() == "true"
    )
    # Identity the authorization layer signs under (app/authz). The real
    # Visa TAP agent identity is registered with Visa in the build window;
    # this label is not a credential.
    agent_id: str = os.environ.get("VERITY_AGENT_ID", "verity-agent")


def get_settings() -> Settings:
    return Settings()
