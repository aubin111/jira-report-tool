"""
main.py - Entry point for the Jira Hierarchy Report Tool.

Run this from the command line:
    python main.py

It will:
1. Connect to Jira using your .env settings
2. Pull all Features, Epics, and User Stories
3. Check for status mismatches
4. Print a report and save it as CSV
"""

from jira_reports import (
    get_config,
    JiraExtractor,
    HierarchyAnalyzer,
    ReportBuilder,
)


def main():
    # -------------------------------------------------------
    # Step 1: Load configuration
    # -------------------------------------------------------
    print("Loading configuration from .env...")
    try:
        config = get_config()
    except ValueError as e:
        print(f"\nConfiguration Error: {e}")
        return

    # -------------------------------------------------------
    # Step 2: Extract data from Jira
    # -------------------------------------------------------
    extractor = JiraExtractor(config)
    features_df, epics_df, stories_df = extractor.extract_all()

    # -------------------------------------------------------
    # Step 3: Analyze for mismatches
    # -------------------------------------------------------
    analyzer = HierarchyAnalyzer(config)
    analysis_results = analyzer.run_all_checks(features_df, epics_df, stories_df)

    # -------------------------------------------------------
    # Step 4: Build and export reports
    # -------------------------------------------------------
    reporter = ReportBuilder(output_dir="reports")

    combined_report = reporter.build_combined_report(analysis_results)
    people_report = reporter.build_person_report(combined_report)

    # Print summary to console
    reporter.print_summary(analysis_results, combined_report, people_report)

    # Save CSV
    reporter.export_to_csv(combined_report)

    print("\nDone! Next steps:")
    print("  - Review the CSV in the /reports folder")
    print("  - (Coming soon) Run 'streamlit run app.py' for the dashboard")
    print("  - (Coming soon) Enable email nudges in .env")


if __name__ == "__main__":
    main()
