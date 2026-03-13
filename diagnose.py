"""
diagnose.py - Inspect your Jira setup to find the right field/link names.

Run this to see:
  - What issue types exist in your project
  - How issues are linked together
  - What fields are available

Usage:
    python diagnose.py
"""

from jira_reports.config import get_config
from jira import JIRA


def main():
    config = get_config()

    # Connect
    jira_kwargs = {"server": config["jira_url"]}
    auth_mode = config["auth_mode"]

    if auth_mode == "pat":
        jira_kwargs["token_auth"] = config["jira_pat"]
    elif auth_mode == "basic":
        jira_kwargs["basic_auth"] = (config["jira_username"], config["jira_password"])
    elif auth_mode == "cloud":
        jira_kwargs["basic_auth"] = (config["jira_email"], config["jira_api_token"])

    jira = JIRA(**jira_kwargs)
    project_key = config["feature_project_key"]

    print("=" * 60)
    print(f"DIAGNOSING PROJECT: {project_key}")
    print("=" * 60)

    # -------------------------------------------------------
    # 1. What issue types exist in this project?
    # -------------------------------------------------------
    print("\n--- ISSUE TYPES IN PROJECT ---")
    jql = f'project = "{project_key}" ORDER BY created DESC'
    # Grab a sample of 200 issues to see what types exist
    issues = jira.search_issues(jql, maxResults=200, fields="issuetype")
    type_counts = {}
    for issue in issues:
        itype = str(issue.fields.issuetype)
        type_counts[itype] = type_counts.get(itype, 0) + 1

    for itype, count in sorted(type_counts.items(), key=lambda x: -x[1]):
        print(f"  {itype}: {count} (in sample of {len(issues)})")

    # -------------------------------------------------------
    # 2. Grab ONE issue and inspect it deeply
    # -------------------------------------------------------
    print("\n--- INSPECTING A SAMPLE ISSUE ---")

    # Try to find a "Feature" type first, fall back to whatever exists
    sample_issue = None
    for try_type in ["Feature", "Initiative", "Epic", "Story"]:
        try_jql = f'project = "{project_key}" AND issuetype = "{try_type}" ORDER BY created DESC'
        results = jira.search_issues(try_jql, maxResults=1)
        if results:
            sample_issue = results[0]
            print(f"  Found a '{try_type}' issue: {sample_issue.key}")
            break

    if not sample_issue:
        # Just grab whatever
        sample_issue = issues[0] if issues else None

    if not sample_issue:
        print("  No issues found in project!")
        return

    # Fetch the full issue with ALL fields
    full_issue = jira.issue(sample_issue.key)

    print(f"\n  Issue: {full_issue.key}")
    print(f"  Type:  {full_issue.fields.issuetype}")
    print(f"  Summary: {full_issue.fields.summary}")
    print(f"  Status: {full_issue.fields.status}")

    # -------------------------------------------------------
    # 3. Check issue links
    # -------------------------------------------------------
    print(f"\n--- ISSUE LINKS on {full_issue.key} ---")
    if hasattr(full_issue.fields, 'issuelinks') and full_issue.fields.issuelinks:
        for link in full_issue.fields.issuelinks:
            link_type = link.type.name
            direction = ""
            linked_key = ""
            linked_type = ""

            if hasattr(link, 'outwardIssue') and link.outwardIssue:
                direction = f"outward: '{link.type.outward}'"
                linked_key = link.outwardIssue.key
                linked_type = str(link.outwardIssue.fields.issuetype)
            elif hasattr(link, 'inwardIssue') and link.inwardIssue:
                direction = f"inward: '{link.type.inward}'"
                linked_key = link.inwardIssue.key
                linked_type = str(link.inwardIssue.fields.issuetype)

            print(f"  Link type: '{link_type}' | {direction} | → {linked_key} ({linked_type})")
    else:
        print("  No issue links found!")

    # -------------------------------------------------------
    # 4. Check for parent/epic fields
    # -------------------------------------------------------
    print(f"\n--- PARENT / EPIC FIELDS on {full_issue.key} ---")

    # Check common parent-related fields
    fields_to_check = [
        ('parent', 'Parent'),
        ('customfield_10008', 'Epic Link (common)'),
        ('customfield_10014', 'Epic Name (common)'),
        ('customfield_10100', 'Parent Link (common)'),
    ]

    for field_name, label in fields_to_check:
        try:
            value = getattr(full_issue.fields, field_name, "NOT FOUND")
            if value and value != "NOT FOUND":
                print(f"  {label} ({field_name}): {value}")
        except Exception:
            pass

    # -------------------------------------------------------
    # 5. List ALL link types in this Jira instance
    # -------------------------------------------------------
    print("\n--- ALL LINK TYPES IN YOUR JIRA ---")
    try:
        link_types = jira.issue_link_types()
        for lt in link_types:
            print(f"  Name: '{lt.name}' | Inward: '{lt.inward}' | Outward: '{lt.outward}'")
    except Exception as e:
        print(f"  Could not fetch link types: {e}")

    # -------------------------------------------------------
    # 6. List all custom fields (to find hierarchy fields)
    # -------------------------------------------------------
    print("\n--- CUSTOM FIELDS (filtered for hierarchy-related) ---")
    try:
        all_fields = jira.fields()
        keywords = ["parent", "epic", "feature", "hierarchy", "child", "portfolio"]
        for field in all_fields:
            name_lower = field["name"].lower()
            if any(kw in name_lower for kw in keywords):
                print(f"  ID: {field['id']} | Name: '{field['name']}' | Custom: {field.get('custom', False)}")
    except Exception as e:
        print(f"  Could not fetch fields: {e}")

    print("\n" + "=" * 60)
    print("DIAGNOSIS COMPLETE")
    print("Copy and paste all the output above so we can fix the config.")
    print("=" * 60)


if __name__ == "__main__":
    main()
