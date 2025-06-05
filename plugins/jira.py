from .plugin_base import PluginBase
import json
import requests
import os
from datetime import datetime
from logger import log


class Issue:
    """Class representing a Jira issue with formatting capabilities."""

    def __init__(self, raw_issue_data):
        """
        Initialize with raw issue data from Jira API.

        Args:
            raw_issue_data: Raw issue data from Jira API
        """
        self.raw_data = raw_issue_data
        self.fields = raw_issue_data.get("fields", {})
        self.key = raw_issue_data.get("key", "Unknown")

    def extract_comments(self):
        """Extract and format comments from an issue."""
        comments_list = []

        # Extract comments if they exist
        comments = self.fields.get("comment", {}).get("comments", [])
        for comment in comments:
            # Parse and format the timestamp to make it human readable
            created_timestamp = comment.get("created", "")
            created_formatted = "Unknown"

            if created_timestamp:
                try:
                    # Parse ISO format timestamp
                    dt = datetime.fromisoformat(
                        created_timestamp.replace("Z", "+00:00")
                    )
                    # Format to DD-MM-YYYY HH:MM
                    created_formatted = dt.strftime("%d-%m-%Y %H:%M")
                except (ValueError, TypeError) as e:
                    log.error(f"Error parsing timestamp {created_timestamp}: {e}")

            comments_list.append(
                {
                    "author": comment.get("author", {}).get("displayName", "Unknown"),
                    "created": created_formatted,
                    "body": comment.get("body", "No comment text"),
                }
            )

        return comments_list

    def to_dict(self):
        """Format issue data into the desired structure."""
        # Parse creation date
        created_str = "Unknown"
        if created_timestamp := self.fields.get("created"):
            try:
                dt = datetime.fromisoformat(created_timestamp.replace("Z", "+00:00"))
                created_str = dt.strftime("%d-%m-%Y %H:%M")
            except (ValueError, TypeError) as e:
                log.error(f"Error parsing creation timestamp: {e}")

        # Safely get assignee and reporter display names, handling None values
        assignee = self.fields.get("assignee")
        assignee_name = (
            assignee.get("displayName", "Unassigned") if assignee else "Unassigned"
        )

        reporter = self.fields.get("reporter")
        reporter_name = (
            reporter.get("displayName", "Unknown") if reporter else "Unknown"
        )

        return {
            "key": self.key,
            "name": self.fields.get("summary", "No summary"),
            "status": self.fields.get("status", {}).get("name", "Unknown"),
            "type": self.fields.get("issuetype", {}).get("name", "Unknown"),
            "description": self.fields.get("description", "No description"),
            "comments": self.extract_comments(),
            "assignee": assignee_name,
            "reporter": reporter_name,
            "created": created_str,
        }


class JiraPlugin(PluginBase):
    """Plugin for retrieving data from Jira."""

    def __init__(self, config=None):
        """Initialize with configuration."""
        self.config = config
        self.url = None
        self.token = None
        self.username = None

    def get_type(self):
        return "jira"

    def parse(self, config=None):
        """
        Parse and validate the Jira configuration.
        Returns True if valid, False otherwise.
        """
        if config:
            self.config = config

        required_fields = ["url", "token", "username"]
        missing_fields = [
            field for field in required_fields if not self.config.get(field)
        ]

        if missing_fields:
            log.error(
                f"Jira configuration missing required parameters: {', '.join(missing_fields)}"
            )
            return False

        # Store required parameters
        self.url = self.config.get("url").rstrip("/")

        # Handle token as a file path
        token_path = self.config.get("token")
        try:
            # Check if it's a file path
            if os.path.exists(token_path):
                log.debug(f"Reading token from file: {token_path}")
                with open(token_path, "r") as token_file:
                    self.token = token_file.read().strip()
                    log.debug("Token successfully read from file")
            else:
                # Use the value directly as a token
                log.debug("Using token value directly from configuration")
                self.token = token_path
        except Exception as e:
            log.error(f"Error reading token file: {e}")
            return False

        self.username = self.config.get("username")

        return True

    def _make_request(self, jql=None, endpoint="/rest/api/2/search"):
        """
        Make an authenticated request to the Jira API.

        Args:
            jql: Optional JQL query string
            endpoint: The API endpoint to call, defaults to search
        """
        headers = {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json",
        }

        # Common parameters for all requests
        params = {
            "maxResults": 200,
            "fields": "summary,comment,priority,issuetype,status,description,assignee,reporter,created,*all",
            "expand": "renderedFields,changelog,comments",
        }

        # Add JQL if provided
        if jql:
            params["jql"] = jql

        url = f"{self.url}{endpoint}"
        log.debug(f"Making request to: {url}")
        log.debug(f"With parameters: {params}")

        try:
            response = requests.get(url, headers=headers, params=params)
            log.debug(f"Response status code: {response.status_code}")

            if response.status_code == 429:
                retry_after = int(response.headers.get("Retry-After", 60))
                log.warning(f"Rate limited. Retry after {retry_after} seconds")

            response.raise_for_status()
            return response.json()

        except requests.exceptions.HTTPError as e:
            log.error(f"HTTP error: {e}")
            if hasattr(e.response, "text"):
                log.error(f"Response text: {e.response.text}")
            return None
        except requests.exceptions.ConnectionError as e:
            log.error(f"Connection error: {e}")
            return None
        except requests.exceptions.Timeout as e:
            log.error(f"Timeout error: {e}")
            return None
        except requests.exceptions.RequestException as e:
            log.error(f"Error making request to Jira API: {e}")
            return None
        except ValueError as e:
            log.error(f"Error parsing JSON response: {e}")
            return None

    def _get_closed_issues(self, since_date, until_date):
        """Get issues that the user has closed within the date range with expanded fields."""
        jql = (
            f"status changed to (Resolved, Closed, Done) "
            f"BY '{self.username}' "
            f"DURING ('{since_date}', '{until_date}') "
            f"ORDER BY updated DESC"
        )

        return self._make_request(jql=jql)

    def _get_commented_issues(self, since_date, until_date):
        """Get issues that the user has commented on within the date range."""
        jql = (
            f"issueFunction in commented('by {self.username} "
            f"after {since_date} "
            f"before {until_date}')"
            f" ORDER BY updated DESC"
        )

        return self._make_request(jql=jql)

    def _get_issues(self, since_date, until_date):
        """
        Get all issues (both closed and commented) for the given date range.

        Args:
            since_date: Start date
            until_date: End date

        Returns:
            Dictionary with lists of Issue objects by type
        """
        issue_types = {
            "closed_issues": self._get_closed_issues,
            "commented_issues": self._get_commented_issues,
        }

        results = {}

        # Process each issue type using its corresponding fetch method
        for issue_type, fetch_method in issue_types.items():
            response = fetch_method(since_date, until_date)

            if response and "issues" in response:
                issue_list = response.get("issues", [])
                results[issue_type] = [Issue(issue) for issue in issue_list]
                log.info(f"Found {len(results[issue_type])} {issue_type}")
            else:
                results[issue_type] = []
                log.info(f"No {issue_type} found")

        return results

    def process(self, since_date, until_date):
        """
        Process Jira data for the given date range.
        Returns JSON data with the results.
        """
        log.info(
            f"Querying Jira at {self.url} for work items between {since_date} and {until_date}"
        )

        # Format dates for Jira API (YYYY-MM-DD)
        since_str = since_date.strftime("%Y-%m-%d")
        until_str = until_date.strftime("%Y-%m-%d")

        # Get all issues in a single call
        all_issues = self._get_issues(since_str, until_str)

        # Convert Issue objects to dictionaries for JSON serialization
        issue_collections = {
            issue_type: [issue.to_dict() for issue in issues]
            for issue_type, issues in all_issues.items()
        }

        # Build result
        result = {
            "source": "jira",
            "name": self.username,
            "activity": issue_collections,
        }

        return json.dumps(result)
