"""
extractor.py - Connects to Jira and pulls the full Feature → Epic → Story hierarchy.

How your Jira hierarchy works:
  - Features live in the BXT project
  - Epics live in ~100 different projects that all start with "BXT" (e.g. BXTFPS)
  - Stories live in those same BXT* projects
  - Epics link UP to Features via "Parent Link" (customfield_31281)
  - Stories link UP to Epics via "Epic Link" (customfield_18881)

Strategy:
  1. Fetch all Features from the BXT project
  2. Discover all BXT* project keys on the Jira instance
  3. Search those BXT* projects for Epics whose "Parent Link" → a Feature
  4. Search those BXT* projects for Stories whose "Epic Link" → an Epic
"""

import pandas as pd
from jira import JIRA


# Custom field IDs from your Jira instance (found via diagnose.py)
PARENT_LINK_FIELD = "customfield_31281"  # "Parent Link" - Epic → Feature
EPIC_LINK_FIELD = "customfield_18881"    # "Epic Link" - Story → Epic


class JiraExtractor:
    """Handles all communication with the Jira API."""

    def __init__(self, config):
        """
        Connect to Jira using the settings from config.

        Args:
            config (dict): Settings from config.py's get_config()
        """
        self.config = config
        auth_mode = config["auth_mode"]

        jira_kwargs = {"server": config["jira_url"]}

        if auth_mode == "pat":
            jira_kwargs["token_auth"] = config["jira_pat"]
            print("Authenticating with Personal Access Token...")
        elif auth_mode == "basic":
            jira_kwargs["basic_auth"] = (
                config["jira_username"],
                config["jira_password"],
            )
            print("Authenticating with username/password...")
        elif auth_mode == "cloud":
            jira_kwargs["basic_auth"] = (
                config["jira_email"],
                config["jira_api_token"],
            )
            print("Authenticating with email/API token (Cloud)...")

        self.jira = JIRA(**jira_kwargs)
        print(f"Connected to Jira at {config['jira_url']}")

    # ------------------------------------------------------------------
    # Helper methods
    # ------------------------------------------------------------------
    def _search_all_issues(self, jql, fields=None):
        """
        Search Jira with automatic pagination.

        Args:
            jql (str): The JQL query string.
            fields (str): Comma-separated list of fields to fetch.

        Returns:
            list: All matching Jira issue objects.
        """
        all_issues = []
        start = 0
        batch_size = 100

        while True:
            batch = self.jira.search_issues(
                jql,
                startAt=start,
                maxResults=batch_size,
                fields=fields,
            )
            all_issues.extend(batch)

            if len(batch) < batch_size:
                break

            start += batch_size
            if start % 500 == 0:
                print(f"  ...fetched {len(all_issues)} issues so far")

        return all_issues

    def _safe_display_name(self, field_value):
        """Safely get displayName from a Jira user field."""
        if field_value is None:
            return "Unassigned"
        if isinstance(field_value, str):
            return field_value
        return getattr(field_value, "displayName", "Unknown")

    def _safe_email(self, field_value):
        """Safely get emailAddress from a Jira user field."""
        if field_value is None:
            return None
        if isinstance(field_value, str):
            return None
        return getattr(field_value, "emailAddress", None)

    def _get_parent_key(self, issue, custom_field_id):
        """
        Extract the parent issue key from a custom link field.

        These fields can return different types depending on Jira config:
        a string key, an issue object, or None.

        Args:
            issue: The Jira issue object.
            custom_field_id (str): The custom field ID.

        Returns:
            str or None: The parent issue key, or None if not set.
        """
        value = getattr(issue.fields, custom_field_id, None)
        if value is None:
            return None
        if isinstance(value, str):
            return value
        return getattr(value, "key", str(value))

    # ------------------------------------------------------------------
    # Discover BXT* projects
    # ------------------------------------------------------------------
    def discover_bxt_projects(self):
        """
        Find all project keys on the Jira instance that start with "BXT".

        This gives us the list of ~100 projects where Epics and Stories live.

        Returns:
            list: Project key strings (e.g. ["BXT", "BXTFPS", "BXTABC", ...])
        """
        prefix = self.config.get("project_prefix", "BXT")
        print(f"\nDiscovering projects with prefix '{prefix}'...")

        all_projects = self.jira.projects()
        bxt_projects = [
            p.key for p in all_projects if p.key.startswith(prefix)
        ]

        print(f"  Found {len(bxt_projects)} projects starting with '{prefix}'")
        return bxt_projects

    def _build_project_filter(self, project_keys):
        """
        Build a JQL project filter string for a list of project keys.

        Example output: 'project IN (BXTFPS, BXTABC, BXTXYZ)'

        Args:
            project_keys (list): List of project key strings.

        Returns:
            str: JQL fragment like 'project IN (KEY1, KEY2, ...)'
        """
        keys_str = ", ".join(project_keys)
        return f"project IN ({keys_str})"

    # ------------------------------------------------------------------
    # Step 1: Fetch Features from the BXT project
    # ------------------------------------------------------------------
    def fetch_features(self):
        """
        Pull all Features from the BXT Domain project.

        Returns:
            pandas.DataFrame: Features with key, summary, status, assignee, reporter.
        """
        project_key = self.config["feature_project_key"]
        print(f"\nFetching Features from project: {project_key}")

        jql = (
            f'project = "{project_key}" '
            f'AND issuetype = "Feature" '
            f"ORDER BY key ASC"
        )

        fields = "summary,status,assignee,reporter"
        issues = self._search_all_issues(jql, fields=fields)

        print(f"  Found {len(issues)} Features")

        features = []
        for issue in issues:
            features.append({
                "feature_key": issue.key,
                "feature_summary": issue.fields.summary,
                "feature_status": str(issue.fields.status),
                "feature_assignee": self._safe_display_name(issue.fields.assignee),
                "feature_assignee_email": self._safe_email(issue.fields.assignee),
                "feature_reporter": self._safe_display_name(issue.fields.reporter),
                "feature_reporter_email": self._safe_email(issue.fields.reporter),
            })

        return pd.DataFrame(features)

    # ------------------------------------------------------------------
    # Step 2: Fetch Epics from BXT* projects via Parent Link → Feature
    # ------------------------------------------------------------------
    def fetch_epics_for_features(self, features_df, bxt_project_keys):
        """
        Find all Epics in BXT* projects whose "Parent Link" field
        points to one of our Features.

        Searches in batches of Feature keys to stay within JQL length limits.

        Args:
            features_df (pandas.DataFrame): The Features DataFrame.
            bxt_project_keys (list): List of BXT* project keys to search.

        Returns:
            pandas.DataFrame: Epics with their parent feature key and details.
        """
        print("\nFetching Epics linked to Features via Parent Link field...")
        print(f"  (searching across {len(bxt_project_keys)} BXT* projects)")

        if features_df.empty:
            return pd.DataFrame()

        feature_keys = features_df["feature_key"].tolist()
        project_filter = self._build_project_filter(bxt_project_keys)

        all_epics = []
        batch_size = 40  # feature keys per JQL query (conservative for long URLs)

        for i in range(0, len(feature_keys), batch_size):
            batch_keys = feature_keys[i : i + batch_size]
            keys_str = ", ".join(batch_keys)

            jql = (
                f'{project_filter} '
                f'AND issuetype = "Epic" '
                f'AND "Parent Link" IN ({keys_str})'
            )

            fields = f"summary,status,assignee,reporter,{PARENT_LINK_FIELD}"

            try:
                issues = self._search_all_issues(jql, fields=fields)

                for issue in issues:
                    feature_key = self._get_parent_key(issue, PARENT_LINK_FIELD)

                    all_epics.append({
                        "feature_key": feature_key or "Unknown",
                        "epic_key": issue.key,
                        "epic_summary": issue.fields.summary,
                        "epic_status": str(issue.fields.status),
                        "epic_assignee": self._safe_display_name(issue.fields.assignee),
                        "epic_assignee_email": self._safe_email(issue.fields.assignee),
                        "epic_reporter": self._safe_display_name(issue.fields.reporter),
                        "epic_reporter_email": self._safe_email(issue.fields.reporter),
                    })

            except Exception as e:
                print(f"  Warning: Batch query failed: {e}")
                print(f"  Trying smaller batches...")

                # Fallback: try one feature key at a time
                for fkey in batch_keys:
                    try:
                        jql_single = (
                            f'{project_filter} '
                            f'AND issuetype = "Epic" '
                            f'AND "Parent Link" = {fkey}'
                        )
                        issues = self._search_all_issues(jql_single, fields=fields)
                        for issue in issues:
                            feature_key = self._get_parent_key(
                                issue, PARENT_LINK_FIELD
                            )
                            all_epics.append({
                                "feature_key": feature_key or fkey,
                                "epic_key": issue.key,
                                "epic_summary": issue.fields.summary,
                                "epic_status": str(issue.fields.status),
                                "epic_assignee": self._safe_display_name(
                                    issue.fields.assignee
                                ),
                                "epic_assignee_email": self._safe_email(
                                    issue.fields.assignee
                                ),
                                "epic_reporter": self._safe_display_name(
                                    issue.fields.reporter
                                ),
                                "epic_reporter_email": self._safe_email(
                                    issue.fields.reporter
                                ),
                            })
                    except Exception as e2:
                        print(f"    Could not fetch epics for {fkey}: {e2}")

            # Progress update
            processed = min(i + batch_size, len(feature_keys))
            if processed % 200 == 0 or processed == len(feature_keys):
                print(
                    f"  ...checked {processed}/{len(feature_keys)} Features, "
                    f"found {len(all_epics)} Epics so far"
                )

        print(f"  Found {len(all_epics)} Epics across {len(bxt_project_keys)} projects")
        return pd.DataFrame(all_epics)

    # ------------------------------------------------------------------
    # Step 3: Fetch Stories from BXT* projects via Epic Link → Epic
    # ------------------------------------------------------------------
    def fetch_stories_for_epics(self, epics_df, bxt_project_keys):
        """
        Find all User Stories in BXT* projects whose "Epic Link" field
        points to one of our Epics.

        Args:
            epics_df (pandas.DataFrame): The Epics DataFrame.
            bxt_project_keys (list): List of BXT* project keys to search.

        Returns:
            pandas.DataFrame: Stories with their parent epic key and details.
        """
        print("\nFetching User Stories linked to Epics via Epic Link field...")
        print(f"  (searching across {len(bxt_project_keys)} BXT* projects)")

        if epics_df.empty:
            return pd.DataFrame()

        epic_keys = epics_df["epic_key"].tolist()
        project_filter = self._build_project_filter(bxt_project_keys)

        all_stories = []
        batch_size = 40

        for i in range(0, len(epic_keys), batch_size):
            batch_keys = epic_keys[i : i + batch_size]
            keys_str = ", ".join(batch_keys)

            jql = (
                f'{project_filter} '
                f'AND "Epic Link" IN ({keys_str})'
            )

            fields = f"summary,status,assignee,reporter,{EPIC_LINK_FIELD}"

            try:
                issues = self._search_all_issues(jql, fields=fields)

                for issue in issues:
                    epic_key = self._get_parent_key(issue, EPIC_LINK_FIELD)

                    all_stories.append({
                        "epic_key": epic_key or "Unknown",
                        "story_key": issue.key,
                        "story_summary": issue.fields.summary,
                        "story_status": str(issue.fields.status),
                        "story_assignee": self._safe_display_name(
                            issue.fields.assignee
                        ),
                        "story_assignee_email": self._safe_email(
                            issue.fields.assignee
                        ),
                        "story_reporter": self._safe_display_name(
                            issue.fields.reporter
                        ),
                        "story_reporter_email": self._safe_email(
                            issue.fields.reporter
                        ),
                    })

            except Exception as e:
                print(f"  Warning: Batch query failed: {e}")
                print(f"  Trying smaller batches...")

                for ekey in batch_keys:
                    try:
                        jql_single = (
                            f'{project_filter} '
                            f'AND "Epic Link" = {ekey}'
                        )
                        issues = self._search_all_issues(jql_single, fields=fields)
                        for issue in issues:
                            all_stories.append({
                                "epic_key": ekey,
                                "story_key": issue.key,
                                "story_summary": issue.fields.summary,
                                "story_status": str(issue.fields.status),
                                "story_assignee": self._safe_display_name(
                                    issue.fields.assignee
                                ),
                                "story_assignee_email": self._safe_email(
                                    issue.fields.assignee
                                ),
                                "story_reporter": self._safe_display_name(
                                    issue.fields.reporter
                                ),
                                "story_reporter_email": self._safe_email(
                                    issue.fields.reporter
                                ),
                            })
                    except Exception as e2:
                        print(f"    Could not fetch stories for {ekey}: {e2}")

            # Progress update
            processed = min(i + batch_size, len(epic_keys))
            if processed % 200 == 0 or processed == len(epic_keys):
                print(
                    f"  ...checked {processed}/{len(epic_keys)} Epics, "
                    f"found {len(all_stories)} Stories so far"
                )

        print(
            f"  Found {len(all_stories)} User Stories "
            f"across {len(bxt_project_keys)} projects"
        )
        return pd.DataFrame(all_stories)

    # ------------------------------------------------------------------
    # Run the full pipeline
    # ------------------------------------------------------------------
    def extract_all(self):
        """
        Run the full extraction pipeline.

        Returns:
            tuple: (features_df, epics_df, stories_df) - three DataFrames
                   with the full hierarchy.
        """
        print("=" * 60)
        print("Starting Jira Data Extraction")
        print("=" * 60)

        # Step 0: Discover all BXT* projects
        bxt_project_keys = self.discover_bxt_projects()

        if not bxt_project_keys:
            print("No BXT* projects found! Check your project_prefix setting.")
            return pd.DataFrame(), pd.DataFrame(), pd.DataFrame()

        # Step 1: Get all Features from the main BXT project
        features_df = self.fetch_features()

        if features_df.empty:
            print("No Features found. Check your project key and issue type.")
            return features_df, pd.DataFrame(), pd.DataFrame()

        # Step 2: Find all Epics across BXT* projects that link to Features
        epics_df = self.fetch_epics_for_features(features_df, bxt_project_keys)

        # Step 3: Find all Stories across BXT* projects that link to Epics
        stories_df = pd.DataFrame()
        if not epics_df.empty:
            stories_df = self.fetch_stories_for_epics(epics_df, bxt_project_keys)

        print("\n" + "=" * 60)
        print("Extraction Complete!")
        print(f"  BXT* Projects: {len(bxt_project_keys)}")
        print(f"  Features:      {len(features_df)}")
        print(f"  Epics:         {len(epics_df)}")
        print(f"  Stories:       {len(stories_df)}")
        print("=" * 60)

        return features_df, epics_df, stories_df
