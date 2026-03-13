# Jira Hierarchy Report Tool

A Python tool that pulls data from Jira, analyzes your Feature → Epic → User Story
hierarchy, and identifies tickets that need status updates.

## What It Does

1. **Pulls Features** from the BXT Domain - TKTS JIRA project
2. **Follows links** to find connected Epics and User Stories across ~100 projects
3. **Detects mismatches** in status:
   - All User Stories resolved, but Epic is NOT resolved
   - All Epics resolved, but Feature is NOT resolved
   - Epic is In Progress, but Feature is NOT in progress
4. **Generates reports** with assignees and reporters
5. **Sends nudge emails** via Outlook (coming soon)
6. **Streamlit dashboard** for viewing reports (coming soon)

## Setup

### 1. Install Python dependencies

```bash
pip install -r requirements.txt
```

### 2. Configure your Jira connection

Copy the example config and fill in your details:

```bash
cp .env.example .env
```

Edit `.env` with your Jira URL, email, and API token.

**To create a Jira API token:**
1. Go to https://id.atlassian.com/manage-profile/security/api-tokens
2. Click "Create API token"
3. Give it a name like "Jira Report Tool"
4. Copy the token into your `.env` file

### 3. Run the extraction

```bash
python main.py
```

### 4. (Coming soon) Run the Streamlit dashboard

```bash
streamlit run app.py
```

## Project Structure

```
jira-report-tool/
├── main.py                  # Entry point - run from command line
├── app.py                   # (future) Streamlit dashboard
├── .env.example             # Template for your Jira credentials
├── requirements.txt         # Python dependencies
├── jira_reports/
│   ├── __init__.py
│   ├── config.py            # Loads settings from .env
│   ├── extractor.py         # Connects to Jira and pulls data
│   ├── analyzer.py          # Finds status mismatches
│   ├── reporter.py          # Builds summary reports
│   └── emailer.py           # (future) Sends Outlook emails
└── templates/
    └── nudge_email.html     # (future) Email template
```
