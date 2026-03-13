"""
reporter.py - Builds summary reports from analysis results.

Takes the mismatch DataFrames from the analyzer and creates:
- A combined summary DataFrame
- A per-person breakdown (for email nudges)
- CSV export for easy sharing
"""

import os
from datetime import datetime

import pandas as pd


class ReportBuilder:
    """Builds and exports reports from analysis results."""

    def __init__(self, output_dir="reports"):
        """
        Args:
            output_dir (str): Folder to save report files to.
        """
        self.output_dir = output_dir
        os.makedirs(output_dir, exist_ok=True)

    def build_combined_report(self, analysis_results):
        """
        Combine all mismatch types into one clean report.

        Args:
            analysis_results (dict): Output from HierarchyAnalyzer.run_all_checks()

        Returns:
            pandas.DataFrame: All mismatches in one table.
        """
        frames = []

        for check_name, df in analysis_results.items():
            if df.empty:
                continue
            # Add a column so we know which check flagged it
            df_copy = df.copy()
            df_copy["check_type"] = check_name
            frames.append(df_copy)

        if not frames:
            print("No mismatches found - everything looks up to date!")
            return pd.DataFrame()

        combined = pd.concat(frames, ignore_index=True)
        return combined

    def build_person_report(self, combined_report):
        """
        Group mismatches by person (assignee/reporter) for targeted nudges.

        Each person gets a list of tickets they need to look at.

        Args:
            combined_report (pandas.DataFrame): Output from build_combined_report()

        Returns:
            dict: Person name → list of their tickets with details.
        """
        if combined_report.empty:
            return {}

        people = {}

        for _, row in combined_report.iterrows():
            # Collect all people associated with this mismatch
            contacts = []

            # Check for epic-level contacts
            if "epic_assignee" in row and pd.notna(row.get("epic_assignee")):
                contacts.append(
                    {
                        "name": row["epic_assignee"],
                        "email": row.get("epic_assignee_email"),
                        "role": "Epic Assignee",
                    }
                )
            if "epic_reporter" in row and pd.notna(row.get("epic_reporter")):
                contacts.append(
                    {
                        "name": row["epic_reporter"],
                        "email": row.get("epic_reporter_email"),
                        "role": "Epic Reporter",
                    }
                )

            # Check for feature-level contacts
            if "feature_assignee" in row and pd.notna(row.get("feature_assignee")):
                contacts.append(
                    {
                        "name": row["feature_assignee"],
                        "email": row.get("feature_assignee_email"),
                        "role": "Feature Assignee",
                    }
                )
            if "feature_reporter" in row and pd.notna(row.get("feature_reporter")):
                contacts.append(
                    {
                        "name": row["feature_reporter"],
                        "email": row.get("feature_reporter_email"),
                        "role": "Feature Reporter",
                    }
                )

            # Build the ticket detail to include in the nudge
            ticket_info = {
                "issue_type": row.get("issue_type", "Unknown"),
                "check_type": row.get("check_type", "Unknown"),
            }

            # Add whatever keys are available
            for key_col in ["feature_key", "epic_key"]:
                if key_col in row and pd.notna(row.get(key_col)):
                    ticket_info[key_col] = row[key_col]

            for summary_col in ["feature_summary", "epic_summary"]:
                if summary_col in row and pd.notna(row.get(summary_col)):
                    ticket_info[summary_col] = row[summary_col]

            for status_col in ["feature_status", "epic_status"]:
                if status_col in row and pd.notna(row.get(status_col)):
                    ticket_info[status_col] = row[status_col]

            # Assign this ticket to each relevant person
            for contact in contacts:
                name = contact["name"]
                if name not in people:
                    people[name] = {
                        "email": contact["email"],
                        "tickets": [],
                    }
                # Update email if we have one and didn't before
                if contact["email"] and not people[name]["email"]:
                    people[name]["email"] = contact["email"]

                people[name]["tickets"].append(
                    {**ticket_info, "their_role": contact["role"]}
                )

        return people

    def export_to_csv(self, combined_report, filename=None):
        """
        Save the combined report as a CSV file.

        Args:
            combined_report (pandas.DataFrame): The combined mismatch report.
            filename (str, optional): Custom filename. Defaults to timestamped name.

        Returns:
            str: Path to the saved CSV file.
        """
        if combined_report.empty:
            print("Nothing to export - no mismatches found.")
            return None

        if filename is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"jira_mismatch_report_{timestamp}.csv"

        filepath = os.path.join(self.output_dir, filename)

        # Drop email columns from CSV for privacy
        export_df = combined_report.copy()
        email_cols = [col for col in export_df.columns if "email" in col]
        export_df = export_df.drop(columns=email_cols, errors="ignore")

        export_df.to_csv(filepath, index=False)
        print(f"\nReport saved to: {filepath}")
        return filepath

    def print_summary(self, analysis_results, combined_report, people_report):
        """
        Print a nice summary to the console.

        Args:
            analysis_results (dict): Raw results from analyzer
            combined_report (pandas.DataFrame): Combined mismatches
            people_report (dict): Per-person breakdown
        """
        print("\n" + "=" * 60)
        print("JIRA HIERARCHY MISMATCH REPORT")
        print(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("=" * 60)

        # Summary counts
        for check_name, df in analysis_results.items():
            count = len(df) if not df.empty else 0
            friendly_names = {
                "all_epics_resolved_feature_not": "All Epics resolved, Feature not updated",
                "epic_in_progress_feature_backlog": "Epic in progress, Feature still in Backlog",
                "feature_resolved_epic_open": "Feature resolved, Epic still open",
                "all_stories_resolved_epic_not": "All Stories resolved, Epic not updated",
                "story_in_progress_epic_backlog": "Story in progress, Epic still in Backlog",
                "epic_resolved_story_open": "Epic resolved, Story still open",
            }
            label = friendly_names.get(check_name, check_name)
            print(f"\n  {label}: {count}")

            if not df.empty:
                # Show first few examples
                for _, row in df.head(5).iterrows():
                    key = row.get("epic_key", row.get("feature_key", "?"))
                    status = row.get("epic_status", row.get("feature_status", "?"))
                    print(f"    - {key} (status: {status})")
                if len(df) > 5:
                    print(f"    ... and {len(df) - 5} more")

        # People summary
        print(f"\n{'=' * 60}")
        print(f"PEOPLE TO NOTIFY: {len(people_report)}")
        print("=" * 60)

        for name, info in people_report.items():
            ticket_count = len(info["tickets"])
            email = info["email"] or "no email"
            print(f"  {name} ({email}): {ticket_count} ticket(s) to review")
