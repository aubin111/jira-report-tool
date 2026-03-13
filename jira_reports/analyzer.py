"""
analyzer.py - Finds ALL status mismatches between immediate relations.

Every ticket falls into one of three status categories:
  - Backlog:    not started
  - Unresolved: in progress (any active work status)
  - Resolved:   done

A mismatch is when a parent and child are out of sync in EITHER direction.

Feature ↔ Epic checks:
  1. All Epics resolved      → Feature should be resolved (but isn't)
  2. Any Epic in progress     → Feature should NOT be in Backlog (but is)
  3. Feature resolved         → no Epics should be unresolved/backlog (but some are)
  4. Feature in Backlog       → no Epics should be in progress (but some are)
     (Same signal as #2, deduplicated — we report from the child's perspective in #2)

Epic ↔ Story checks:
  5. All Stories resolved     → Epic should be resolved (but isn't)
  6. Any Story in progress    → Epic should NOT be in Backlog (but is)
  7. Epic resolved            → no Stories should be unresolved/backlog (but some are)
  8. Epic in Backlog          → no Stories should be in progress (but some are)
     (Same signal as #6, deduplicated — we report from the child's perspective in #6)
"""

import pandas as pd


class HierarchyAnalyzer:
    """Analyzes Jira hierarchy data for status mismatches."""

    def __init__(self, config):
        """
        Args:
            config (dict): Settings from config.py with per-level status lists.
        """
        self.feature_resolved = config["feature_resolved_statuses"]
        self.feature_in_progress = config["feature_in_progress_statuses"]
        self.epic_resolved = config["epic_resolved_statuses"]
        self.epic_in_progress = config["epic_in_progress_statuses"]
        self.story_resolved = config["story_resolved_statuses"]
        self.story_in_progress = config["story_in_progress_statuses"]

    def _categorize_feature(self, status):
        """Return 'resolved', 'in_progress', or 'backlog' for a Feature status."""
        if status in self.feature_resolved:
            return "resolved"
        elif status in self.feature_in_progress:
            return "in_progress"
        else:
            return "backlog"

    def _categorize_epic(self, status):
        """Return 'resolved', 'in_progress', or 'backlog' for an Epic status."""
        if status in self.epic_resolved:
            return "resolved"
        elif status in self.epic_in_progress:
            return "in_progress"
        else:
            return "backlog"

    def _categorize_story(self, status):
        """Return 'resolved', 'in_progress', or 'backlog' for a Story status."""
        if status in self.story_resolved:
            return "resolved"
        elif status in self.story_in_progress:
            return "in_progress"
        else:
            return "backlog"

    # ==================================================================
    # FEATURE ↔ EPIC CHECKS
    # ==================================================================

    def check_all_epics_resolved_feature_not(self, features_df, epics_df):
        """
        All Epics resolved → Feature should be resolved (but isn't).
        """
        if features_df.empty or epics_df.empty:
            return pd.DataFrame()

        results = []
        for feature_key, group in epics_df.groupby("feature_key"):
            all_resolved = group["epic_status"].isin(self.epic_resolved).all()
            if not all_resolved:
                continue

            feature_row = features_df[features_df["feature_key"] == feature_key]
            if feature_row.empty:
                continue
            feature_row = feature_row.iloc[0]

            if self._categorize_feature(feature_row["feature_status"]) != "resolved":
                results.append({
                    "feature_key": feature_key,
                    "feature_summary": feature_row["feature_summary"],
                    "feature_status": feature_row["feature_status"],
                    "feature_assignee": feature_row["feature_assignee"],
                    "feature_assignee_email": feature_row.get("feature_assignee_email"),
                    "feature_reporter": feature_row["feature_reporter"],
                    "feature_reporter_email": feature_row.get("feature_reporter_email"),
                    "total_epics": len(group),
                    "resolved_epics": len(group),
                    "issue_type": "All Epics resolved, Feature NOT resolved",
                })

        return pd.DataFrame(results)

    def check_epic_in_progress_feature_backlog(self, features_df, epics_df):
        """
        Any Epic in progress → Feature should NOT be in Backlog (but is).
        Also covers: Feature in Backlog → no Epics should be in progress.
        """
        if features_df.empty or epics_df.empty:
            return pd.DataFrame()

        results = []
        # Find Features that are in Backlog
        backlog_features = features_df[
            features_df["feature_status"].apply(
                lambda s: self._categorize_feature(s) == "backlog"
            )
        ]

        for _, feature_row in backlog_features.iterrows():
            feature_key = feature_row["feature_key"]
            epics = epics_df[epics_df["feature_key"] == feature_key]
            if epics.empty:
                continue

            # Find Epics that are in progress (not backlog, not resolved)
            in_progress_epics = epics[
                epics["epic_status"].apply(
                    lambda s: self._categorize_epic(s) == "in_progress"
                )
            ]

            for _, epic_row in in_progress_epics.iterrows():
                results.append({
                    "epic_key": epic_row["epic_key"],
                    "epic_summary": epic_row["epic_summary"],
                    "epic_status": epic_row["epic_status"],
                    "epic_assignee": epic_row["epic_assignee"],
                    "epic_assignee_email": epic_row.get("epic_assignee_email"),
                    "feature_key": feature_key,
                    "feature_summary": feature_row["feature_summary"],
                    "feature_status": feature_row["feature_status"],
                    "feature_assignee": feature_row["feature_assignee"],
                    "feature_assignee_email": feature_row.get("feature_assignee_email"),
                    "feature_reporter": feature_row["feature_reporter"],
                    "feature_reporter_email": feature_row.get("feature_reporter_email"),
                    "issue_type": "Epic In Progress, Feature still in Backlog",
                })

        return pd.DataFrame(results)

    def check_feature_resolved_epic_not(self, features_df, epics_df):
        """
        Feature resolved → no Epics should be unresolved or in backlog (but some are).
        """
        if features_df.empty or epics_df.empty:
            return pd.DataFrame()

        results = []
        resolved_features = features_df[
            features_df["feature_status"].isin(self.feature_resolved)
        ]

        for _, feature_row in resolved_features.iterrows():
            feature_key = feature_row["feature_key"]
            epics = epics_df[epics_df["feature_key"] == feature_key]
            if epics.empty:
                continue

            # Find Epics that are NOT resolved
            open_epics = epics[~epics["epic_status"].isin(self.epic_resolved)]

            for _, epic_row in open_epics.iterrows():
                results.append({
                    "feature_key": feature_key,
                    "feature_summary": feature_row["feature_summary"],
                    "feature_status": feature_row["feature_status"],
                    "feature_assignee": feature_row["feature_assignee"],
                    "feature_assignee_email": feature_row.get("feature_assignee_email"),
                    "feature_reporter": feature_row["feature_reporter"],
                    "feature_reporter_email": feature_row.get("feature_reporter_email"),
                    "epic_key": epic_row["epic_key"],
                    "epic_summary": epic_row["epic_summary"],
                    "epic_status": epic_row["epic_status"],
                    "epic_assignee": epic_row["epic_assignee"],
                    "epic_assignee_email": epic_row.get("epic_assignee_email"),
                    "epic_reporter": epic_row["epic_reporter"],
                    "epic_reporter_email": epic_row.get("epic_reporter_email"),
                    "issue_type": "Feature resolved, Epic still open",
                })

        return pd.DataFrame(results)

    # ==================================================================
    # EPIC ↔ STORY CHECKS
    # ==================================================================

    def check_all_stories_resolved_epic_not(self, epics_df, stories_df):
        """
        All Stories resolved → Epic should be resolved (but isn't).
        """
        if epics_df.empty or stories_df.empty:
            return pd.DataFrame()

        results = []
        for epic_key, group in stories_df.groupby("epic_key"):
            all_resolved = group["story_status"].isin(self.story_resolved).all()
            if not all_resolved:
                continue

            epic_row = epics_df[epics_df["epic_key"] == epic_key]
            if epic_row.empty:
                continue
            epic_row = epic_row.iloc[0]

            if self._categorize_epic(epic_row["epic_status"]) != "resolved":
                results.append({
                    "epic_key": epic_key,
                    "epic_summary": epic_row["epic_summary"],
                    "epic_status": epic_row["epic_status"],
                    "epic_assignee": epic_row["epic_assignee"],
                    "epic_assignee_email": epic_row.get("epic_assignee_email"),
                    "epic_reporter": epic_row["epic_reporter"],
                    "epic_reporter_email": epic_row.get("epic_reporter_email"),
                    "feature_key": epic_row["feature_key"],
                    "total_stories": len(group),
                    "resolved_stories": len(group),
                    "issue_type": "All Stories resolved, Epic NOT resolved",
                })

        return pd.DataFrame(results)

    def check_story_in_progress_epic_backlog(self, epics_df, stories_df):
        """
        Any Story in progress → Epic should NOT be in Backlog (but is).
        Also covers: Epic in Backlog → no Stories should be in progress.
        """
        if epics_df.empty or stories_df.empty:
            return pd.DataFrame()

        results = []
        # Find Epics that are in Backlog
        backlog_epics = epics_df[
            epics_df["epic_status"].apply(
                lambda s: self._categorize_epic(s) == "backlog"
            )
        ]

        for _, epic_row in backlog_epics.iterrows():
            epic_key = epic_row["epic_key"]
            stories = stories_df[stories_df["epic_key"] == epic_key]
            if stories.empty:
                continue

            # Find Stories that are in progress
            in_progress_stories = stories[
                stories["story_status"].apply(
                    lambda s: self._categorize_story(s) == "in_progress"
                )
            ]

            if not in_progress_stories.empty:
                results.append({
                    "epic_key": epic_key,
                    "epic_summary": epic_row["epic_summary"],
                    "epic_status": epic_row["epic_status"],
                    "epic_assignee": epic_row["epic_assignee"],
                    "epic_assignee_email": epic_row.get("epic_assignee_email"),
                    "epic_reporter": epic_row["epic_reporter"],
                    "epic_reporter_email": epic_row.get("epic_reporter_email"),
                    "feature_key": epic_row["feature_key"],
                    "total_stories": len(stories),
                    "in_progress_stories": len(in_progress_stories),
                    "issue_type": "Stories In Progress, Epic still in Backlog",
                })

        return pd.DataFrame(results)

    def check_epic_resolved_story_not(self, epics_df, stories_df):
        """
        Epic resolved → no Stories should be unresolved or in backlog (but some are).
        """
        if epics_df.empty or stories_df.empty:
            return pd.DataFrame()

        results = []
        resolved_epics = epics_df[
            epics_df["epic_status"].isin(self.epic_resolved)
        ]

        for _, epic_row in resolved_epics.iterrows():
            epic_key = epic_row["epic_key"]
            stories = stories_df[stories_df["epic_key"] == epic_key]
            if stories.empty:
                continue

            # Find Stories that are NOT resolved
            open_stories = stories[
                ~stories["story_status"].isin(self.story_resolved)
            ]

            if not open_stories.empty:
                results.append({
                    "epic_key": epic_key,
                    "epic_summary": epic_row["epic_summary"],
                    "epic_status": epic_row["epic_status"],
                    "epic_assignee": epic_row["epic_assignee"],
                    "epic_assignee_email": epic_row.get("epic_assignee_email"),
                    "epic_reporter": epic_row["epic_reporter"],
                    "epic_reporter_email": epic_row.get("epic_reporter_email"),
                    "feature_key": epic_row["feature_key"],
                    "total_stories": len(stories),
                    "open_stories": len(open_stories),
                    "issue_type": "Epic resolved, Stories still open",
                })

        return pd.DataFrame(results)

    # ==================================================================
    # RUN ALL CHECKS
    # ==================================================================

    def run_all_checks(self, features_df, epics_df, stories_df):
        """
        Run all mismatch checks between immediate relations.

        Args:
            features_df: Features DataFrame
            epics_df: Epics DataFrame
            stories_df: Stories DataFrame

        Returns:
            dict: Keys are check names, values are DataFrames of mismatches.
        """
        print("\nRunning hierarchy analysis...")
        print(f"  Feature resolved: {self.feature_resolved}")
        print(f"  Epic resolved:    {self.epic_resolved}")
        print(f"  Story resolved:   {self.story_resolved}")

        results = {
            # Feature ↔ Epic
            "all_epics_resolved_feature_not": self.check_all_epics_resolved_feature_not(
                features_df, epics_df
            ),
            "epic_in_progress_feature_backlog": self.check_epic_in_progress_feature_backlog(
                features_df, epics_df
            ),
            "feature_resolved_epic_open": self.check_feature_resolved_epic_not(
                features_df, epics_df
            ),
            # Epic ↔ Story
            "all_stories_resolved_epic_not": self.check_all_stories_resolved_epic_not(
                epics_df, stories_df
            ),
            "story_in_progress_epic_backlog": self.check_story_in_progress_epic_backlog(
                epics_df, stories_df
            ),
            "epic_resolved_story_open": self.check_epic_resolved_story_not(
                epics_df, stories_df
            ),
        }

        print("\n  Results:")
        for check_name, df in results.items():
            count = len(df) if not df.empty else 0
            print(f"    {check_name}: {count} mismatches")

        total = sum(len(df) for df in results.values() if not df.empty)
        print(f"\n  TOTAL MISMATCHES: {total}")

        return results
