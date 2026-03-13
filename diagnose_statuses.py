"""
diagnose_statuses.py - Shows all unique status values in your Jira hierarchy.

Run this to see what status names your Features, Epics, and Stories actually use,
so we can configure the analyzer correctly.

Usage:
    python diagnose_statuses.py
"""

from jira_reports.config import get_config
from jira_reports.extractor import JiraExtractor


def main():
    config = get_config()
    extractor = JiraExtractor(config)

    print("\n" + "=" * 60)
    print("EXTRACTING DATA (this may take a few minutes)...")
    print("=" * 60)

    features_df, epics_df, stories_df = extractor.extract_all()

    # Show all unique statuses for each level
    print("\n" + "=" * 60)
    print("ALL UNIQUE STATUSES FOUND")
    print("=" * 60)

    if not features_df.empty:
        print("\n--- FEATURE STATUSES ---")
        status_counts = features_df["feature_status"].value_counts()
        for status, count in status_counts.items():
            print(f"  '{status}': {count} features")

    if not epics_df.empty:
        print("\n--- EPIC STATUSES ---")
        status_counts = epics_df["epic_status"].value_counts()
        for status, count in status_counts.items():
            print(f"  '{status}': {count} epics")

    if not stories_df.empty:
        print("\n--- STORY STATUSES ---")
        status_counts = stories_df["story_status"].value_counts()
        for status, count in status_counts.items():
            print(f"  '{status}': {count} stories")

    # Show current config for comparison
    print("\n" + "=" * 60)
    print("YOUR CURRENT .env STATUS SETTINGS")
    print("=" * 60)
    print(f"  RESOLVED_STATUSES = {config['resolved_statuses']}")
    print(f"  IN_PROGRESS_STATUSES = {config['in_progress_statuses']}")

    print("\n" + "=" * 60)
    print("Copy the output above and paste it so we can update your .env")
    print("=" * 60)


if __name__ == "__main__":
    main()
