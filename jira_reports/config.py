"""
config.py - Loads Jira connection settings from your .env file.

This keeps sensitive info (like your API token) out of the code.

Supports per-level status definitions since Features, Epics, and Stories
each have their own workflow with different status names.
"""

import os
from dotenv import load_dotenv

# Load variables from .env file into the environment
load_dotenv()


def get_config():
    """
    Reads all settings from .env and returns them as a dictionary.

    Returns:
        dict: All configuration values needed by the app.

    Raises:
        ValueError: If any required settings are missing from .env.
    """

    if not os.getenv("JIRA_URL"):
        raise ValueError(
            "Missing JIRA_URL in your .env file.\n"
            "Copy .env.example to .env and fill in your details."
        )

    # Determine auth mode
    auth_mode = os.getenv("JIRA_AUTH_MODE", "pat").lower()

    if auth_mode == "pat":
        if not os.getenv("JIRA_PAT"):
            raise ValueError(
                "JIRA_AUTH_MODE is 'pat' but JIRA_PAT is not set.\n"
                "Create a PAT in Jira: Profile → Personal Access Tokens → Create token"
            )
    elif auth_mode == "basic":
        missing = []
        if not os.getenv("JIRA_USERNAME"):
            missing.append("JIRA_USERNAME")
        if not os.getenv("JIRA_PASSWORD"):
            missing.append("JIRA_PASSWORD")
        if missing:
            raise ValueError(
                f"JIRA_AUTH_MODE is 'basic' but missing: {', '.join(missing)}"
            )
    elif auth_mode == "cloud":
        missing = []
        if not os.getenv("JIRA_EMAIL"):
            missing.append("JIRA_EMAIL")
        if not os.getenv("JIRA_API_TOKEN"):
            missing.append("JIRA_API_TOKEN")
        if missing:
            raise ValueError(
                f"JIRA_AUTH_MODE is 'cloud' but missing: {', '.join(missing)}"
            )
    else:
        raise ValueError(
            f"Unknown JIRA_AUTH_MODE: '{auth_mode}'. Use 'pat', 'basic', or 'cloud'."
        )

    def split_statuses(env_var, default):
        """Split a comma-separated env var into a list of stripped strings."""
        return [s.strip() for s in os.getenv(env_var, default).split(",")]

    config = {
        # Jira connection
        "jira_url": os.getenv("JIRA_URL"),
        "auth_mode": auth_mode,

        # Auth credentials
        "jira_pat": os.getenv("JIRA_PAT"),
        "jira_username": os.getenv("JIRA_USERNAME"),
        "jira_password": os.getenv("JIRA_PASSWORD"),
        "jira_email": os.getenv("JIRA_EMAIL"),
        "jira_api_token": os.getenv("JIRA_API_TOKEN"),

        # Project settings
        "feature_project_key": os.getenv("FEATURE_PROJECT_KEY", "BXT"),
        "project_prefix": os.getenv("PROJECT_PREFIX", "BXT"),

        # ---------------------------------------------------------
        # Status definitions PER LEVEL
        # Each level has its own workflow with different status names
        # ---------------------------------------------------------

        # Feature statuses
        "feature_resolved_statuses": split_statuses(
            "FEATURE_RESOLVED_STATUSES",
            "In Production,Cancelled"
        ),
        "feature_in_progress_statuses": split_statuses(
            "FEATURE_IN_PROGRESS_STATUSES",
            "Solutioning,Solution Approved,Grooming/Refinement,Ready for Dev,In Progress,Certified,In Production toggled off"
        ),

        # Epic statuses
        "epic_resolved_statuses": split_statuses(
            "EPIC_RESOLVED_STATUSES",
            "In production,Cancelled"
        ),
        "epic_in_progress_statuses": split_statuses(
            "EPIC_IN_PROGRESS_STATUSES",
            "Evaluation,Architecture Review,Design,Ready for Dev,Developing,E2E testing,Certified,In production toggled off"
        ),

        # Story statuses
        "story_resolved_statuses": split_statuses(
            "STORY_RESOLVED_STATUSES",
            "Accepted,Cancelled"
        ),
        "story_in_progress_statuses": split_statuses(
            "STORY_IN_PROGRESS_STATUSES",
            "Defined,In-Progress,Code Review,Ready for Testing,Testing,Ready for Acceptance"
        ),
    }

    return config
