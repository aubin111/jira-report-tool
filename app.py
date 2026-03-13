import streamlit as st
from jira_reports import get_config, JiraExtractor, HierarchyAnalyzer, ReportBuilder

st.set_page_config(page_title="Jira Mismatch Report", layout="wide")
st.title("Jira Hierarchy Mismatch Report")

# Button to trigger a fresh scan
if st.button("Run Scan"):
    try:
        with st.spinner("Connecting to Jira and extracting data..."):
            config = get_config()
            extractor = JiraExtractor(config)
            features_df, epics_df, stories_df = extractor.extract_all()

        with st.spinner("Analyzing mismatches..."):
            analyzer = HierarchyAnalyzer(config)
            results = analyzer.run_all_checks(features_df, epics_df, stories_df)
            reporter = ReportBuilder()
            combined = reporter.build_combined_report(results)
            people = reporter.build_person_report(combined)

        # Cache results in session so page interactions don't re-trigger the scan
        st.session_state["combined"] = combined
        st.session_state["people"] = people
        st.session_state["results"] = results
        st.rerun()

    except Exception as e:
        st.error(f"Failed to connect to Jira: {e}")
        st.info("Check that your JIRA_PAT in .env is valid and hasn't expired.")

# Only show report if data exists
if "combined" in st.session_state:
    combined = st.session_state["combined"]
    people = st.session_state["people"]
    results = st.session_state["results"]

    # --- Summary metrics across the top ---
    col1, col2, col3 = st.columns(3)
    col1.metric("Total Conflicts", len(combined))
    col2.metric("People to Notify", len(people))
    col3.metric("Check Types with Issues", sum(1 for df in results.values() if not df.empty))

    st.divider()

    # --- Filters ---
    col_a, col_b = st.columns(2)
    check_types = ["All"] + combined["check_type"].unique().tolist()
    selected_type = col_a.selectbox("Filter by mismatch type", check_types)

    person_names = ["All"] + list(people.keys())
    selected_person = col_b.selectbox("Filter by person", person_names)

    # Apply filters
    filtered = combined.copy()
    if selected_type != "All":
        filtered = filtered[filtered["check_type"] == selected_type]

    # --- Conflicts table ---
    st.subheader(f"Conflicts ({len(filtered)})")
    # Drop email columns for display
    display_cols = [c for c in filtered.columns if "email" not in c]
    st.dataframe(filtered[display_cols], use_container_width=True)

    # --- Per-person breakdown ---
    st.divider()
    st.subheader("By Person")
    for name, info in people.items():
        if selected_person != "All" and name != selected_person:
            continue
        with st.expander(f"{name} — {len(info['tickets'])} ticket(s)"):
            st.write(f"**Email:** {info['email'] or 'not on file'}")
            st.table(info["tickets"])
