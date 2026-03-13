"""
emailer.py - Sends nudge emails via Outlook/Exchange.

STATUS: Placeholder - will be implemented in a future phase.

This will use the `exchangelib` library to connect to your company's
Exchange/Outlook server and send personalized emails to assignees and
reporters whose tickets need updating.
"""


class OutlookEmailer:
    """Sends nudge emails through Outlook/Exchange. (Coming soon)"""

    def __init__(self, config):
        """
        Will need Exchange server settings added to config.

        Future .env settings:
            EXCHANGE_EMAIL=your.email@company.com
            EXCHANGE_PASSWORD=your-password
            EXCHANGE_SERVER=outlook.office365.com  (or your server)
        """
        self.config = config
        print("Note: Email sending is not yet implemented.")

    def send_nudges(self, people_report, jira_url):
        """
        Send personalized nudge emails to each person.

        Args:
            people_report (dict): Output from ReportBuilder.build_person_report()
            jira_url (str): Base Jira URL for building ticket links.

        TODO: Implement with exchangelib
        """
        print(f"\nWould send emails to {len(people_report)} people:")
        for name, info in people_report.items():
            email = info["email"] or "no email on file"
            count = len(info["tickets"])
            print(f"  - {name} ({email}): {count} ticket(s)")

        print("\n(Email sending will be implemented in a future update)")
