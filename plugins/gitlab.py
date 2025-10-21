from .plugin_base import PluginBase
import json
import requests
import os
from datetime import datetime
from logger import log


class GitLabPlugin(PluginBase):
    """Plugin for retrieving data from GitLab."""

    def __init__(self, config=None):
        """Initialize with configuration."""
        self.config = config
        self.token = None
        self.username = None
        self.project_id = None  # Optional
        self.api_base_url = "https://gitlab.com/api/v4"

    def get_type(self):
        return "gitlab"

    def parse(self, config=None):
        """
        Parse and validate the GitLab configuration.
        Returns True if valid, False otherwise.
        """
        if config:
            self.config = config

        # Only username and token are required
        required_fields = ["token", "username"]
        missing_fields = [
            field for field in required_fields if not self.config.get(field)
        ]

        if missing_fields:
            log.error(
                f"GitLab configuration missing required parameters: {', '.join(missing_fields)}"
            )
            return False

        # Store required parameters
        self.username = self.config.get("username")

        # Optional project specification
        self.project_id = self.config.get("project_id", "")
        
        # Optional custom GitLab instance URL
        custom_url = self.config.get("api_base_url", "")
        if custom_url:
            self.api_base_url = custom_url.rstrip('/') + "/api/v4"
        else:
            self.api_base_url = "https://gitlab.com/api/v4"

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

        return True

    def _make_request(self, endpoint, params=None):
        """
        Make an authenticated request to the GitLab API.

        Args:
            endpoint: The API endpoint to call
            params: Optional query parameters

        Returns:
            API response as JSON or None on error
        """
        headers = {
            "PRIVATE-TOKEN": self.token,
        }

        url = f"{self.api_base_url}{endpoint}"
        log.debug(f"Making request to: {url}")
        if params:
            log.debug(f"With parameters: {params}")

        try:
            response = requests.get(url, headers=headers, params=params)
            log.debug(f"Response status code: {response.status_code}")

            if response.status_code == 429:
                log.warning("GitLab API rate limit exceeded")

            response.raise_for_status()
            return response.json()

        except requests.exceptions.RequestException as e:
            log.error(f"Error making request to GitLab API: {e}")
            return None

    def _make_paginated_request(self, endpoint, params=None):
        """
        Make a paginated request to the GitLab API.

        Args:
            endpoint: The API endpoint to call
            params: Optional query parameters

        Returns:
            List of all items from all pages
        """
        headers = {
            "PRIVATE-TOKEN": self.token,
        }

        all_items = []
        page = 1
        per_page = 100

        if params is None:
            params = {}
        
        params["per_page"] = per_page

        while True:
            params["page"] = page
            url = f"{self.api_base_url}{endpoint}"
            
            try:
                response = requests.get(url, headers=headers, params=params)
                log.debug(f"Response status code: {response.status_code}")

                if response.status_code == 429:
                    log.warning("GitLab API rate limit exceeded")

                response.raise_for_status()
                items = response.json()
                
                if not items:
                    break
                    
                all_items.extend(items)
                
                # Check if there are more pages
                if len(items) < per_page:
                    break
                    
                page += 1

            except requests.exceptions.RequestException as e:
                log.error(f"Error making request to GitLab API: {e}")
                break

        return all_items

    def _get_user_id(self):
        """Get the GitLab user ID from the username."""
        endpoint = f"/users"
        params = {"username": self.username}
        
        users = self._make_request(endpoint, params)
        if users and len(users) > 0:
            user_id = users[0].get("id")
            log.debug(f"Found user ID {user_id} for username {self.username}")
            return user_id
        
        log.error(f"Could not find user ID for username {self.username}")
        return None

    def _has_user_comment_in_timeframe(
        self, notes, username, since_date, until_date
    ):
        """
        Check if the issue has been commented on by the user within the time frame.

        Args:
            notes: List of note objects
            username: The GitLab username to check for
            since_date: Start date (datetime object)
            until_date: End date (datetime object)

        Returns:
            Boolean indicating if user commented within the timeframe
        """
        for note in notes:
            # Check if note is by the user
            if note.get("author", {}).get("username") != username:
                continue

            # Parse note date
            created_at = note.get("created_at", "")
            if not created_at:
                continue

            try:
                note_date = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
                # Check if note is within the date range
                if since_date <= note_date.date() <= until_date:
                    return True
            except (ValueError, TypeError):
                continue

        return False

    def _format_notes(self, notes_raw):
        """Format notes (comments) from API response."""
        notes = []
        if not notes_raw:
            return notes

        for note in notes_raw:
            # Skip system notes
            if note.get("system", False):
                continue
                
            note_data = {
                "author": note.get("author", {}).get("username"),
                "created_at": self._format_date(note.get("created_at")),
                "body": note.get("body", ""),
            }
            notes.append(note_data)

        return notes

    def _get_user_created_issues(self, user_id, since_date, until_date):
        """Get issues that the user has created within the time frame."""
        endpoint = "/issues"
        params = {
            "author_id": user_id,
            "created_after": since_date.isoformat(),
            "created_before": until_date.isoformat(),
            "scope": "all",
        }
        
        issues = self._make_paginated_request(endpoint, params)
        log.info(f"Found {len(issues)} issues created by user")
        return {issue.get("id"): issue for issue in issues}

    def _get_user_assigned_issues(self, user_id, since_date, until_date):
        """Get issues assigned to the user that were updated within the time frame."""
        endpoint = "/issues"
        params = {
            "assignee_id": user_id,
            "updated_after": since_date.isoformat(),
            "updated_before": until_date.isoformat(),
            "scope": "all",
        }
        
        issues = self._make_paginated_request(endpoint, params)
        log.info(f"Found {len(issues)} issues assigned to user")
        return {issue.get("id"): issue for issue in issues}

    def _get_user_closed_issues(self, user_id, since_date, until_date):
        """Get issues closed by the user within the time frame."""
        endpoint = "/issues"
        params = {
            "assignee_id": user_id,
            "state": "closed",
            "updated_after": since_date.isoformat(),
            "updated_before": until_date.isoformat(),
            "scope": "all",
        }
        
        issues = self._make_paginated_request(endpoint, params)
        
        # Filter to only issues closed in the timeframe
        filtered_issues = {}
        for issue in issues:
            closed_at = issue.get("closed_at")
            if closed_at:
                try:
                    closed_date = datetime.fromisoformat(closed_at.replace("Z", "+00:00")).date()
                    if since_date <= closed_date <= until_date:
                        filtered_issues[issue.get("id")] = issue
                except (ValueError, TypeError):
                    continue
        
        log.info(f"Found {len(filtered_issues)} issues closed by user")
        return filtered_issues

    def _format_issue(self, issue):
        """Format an issue into the standard output structure."""
        project_id = issue.get("project_id")
        
        # Get project information
        project = self._make_request(f"/projects/{project_id}")
        repository = project.get("path_with_namespace", "unknown") if project else "unknown"
        
        # Get notes (comments)
        notes_endpoint = f"/projects/{project_id}/issues/{issue.get('iid')}/notes"
        notes_raw = self._make_paginated_request(notes_endpoint)
        notes = self._format_notes(notes_raw)

        return {
            "id": issue.get("iid"),
            "repository": repository,
            "title": issue.get("title"),
            "state": issue.get("state"),
            "created_by": issue.get("author", {}).get("username"),
            "created_at": self._format_date(issue.get("created_at")),
            "updated_at": self._format_date(issue.get("updated_at")),
            "closed_at": self._format_date(issue.get("closed_at")),
            "body": issue.get("description", ""),
            "comments": notes,
            "url": issue.get("web_url"),
        }

    def _get_user_issues(self, user_id, since_date, until_date):
        """Get issues that the user has created, assigned to, or closed."""
        # Get issues from each category
        created_issues = self._get_user_created_issues(user_id, since_date, until_date)
        assigned_issues = self._get_user_assigned_issues(user_id, since_date, until_date)
        closed_issues = self._get_user_closed_issues(user_id, since_date, until_date)

        # Combine all issues, avoiding duplicates
        all_issues = {**created_issues, **assigned_issues, **closed_issues}

        # Format the issues
        issues = [self._format_issue(issue) for issue in all_issues.values()]

        log.info(f"Found {len(issues)} unique issues involving user {self.username}")
        return issues

    def _get_user_created_merge_requests(self, user_id, since_date, until_date):
        """Get merge requests that the user has created within the time frame."""
        endpoint = "/merge_requests"
        params = {
            "author_id": user_id,
            "created_after": since_date.isoformat(),
            "created_before": until_date.isoformat(),
            "scope": "all",
        }
        
        mrs = self._make_paginated_request(endpoint, params)
        log.info(f"Found {len(mrs)} merge requests created by user")
        return {mr.get("id"): mr for mr in mrs}

    def _get_user_assigned_merge_requests(self, user_id, since_date, until_date):
        """Get merge requests assigned to the user that were updated within the time frame."""
        endpoint = "/merge_requests"
        params = {
            "assignee_id": user_id,
            "updated_after": since_date.isoformat(),
            "updated_before": until_date.isoformat(),
            "scope": "all",
        }
        
        mrs = self._make_paginated_request(endpoint, params)
        log.info(f"Found {len(mrs)} merge requests assigned to user")
        return {mr.get("id"): mr for mr in mrs}

    def _get_user_reviewed_merge_requests(self, user_id, since_date, until_date):
        """Get merge requests reviewed by the user within the time frame."""
        endpoint = "/merge_requests"
        params = {
            "reviewer_id": user_id,
            "updated_after": since_date.isoformat(),
            "updated_before": until_date.isoformat(),
            "scope": "all",
        }
        
        mrs = self._make_paginated_request(endpoint, params)
        log.info(f"Found {len(mrs)} merge requests reviewed by user")
        return {mr.get("id"): mr for mr in mrs}

    def _get_user_closed_merge_requests(self, user_id, since_date, until_date):
        """Get merge requests closed/merged by the user within the time frame."""
        endpoint = "/merge_requests"
        params = {
            "assignee_id": user_id,
            "state": "merged",
            "updated_after": since_date.isoformat(),
            "updated_before": until_date.isoformat(),
            "scope": "all",
        }
        
        mrs = self._make_paginated_request(endpoint, params)
        
        # Filter to only MRs merged in the timeframe
        filtered_mrs = {}
        for mr in mrs:
            merged_at = mr.get("merged_at")
            if merged_at:
                try:
                    merged_date = datetime.fromisoformat(merged_at.replace("Z", "+00:00")).date()
                    if since_date <= merged_date <= until_date:
                        filtered_mrs[mr.get("id")] = mr
                except (ValueError, TypeError):
                    continue
        
        log.info(f"Found {len(filtered_mrs)} merge requests merged by user")
        return filtered_mrs

    def _format_merge_request(self, mr):
        """Format a merge request into the standard output structure."""
        project_id = mr.get("project_id")
        
        # Get project information
        project = self._make_request(f"/projects/{project_id}")
        repository = project.get("path_with_namespace", "unknown") if project else "unknown"
        
        # Get notes (comments)
        notes_endpoint = f"/projects/{project_id}/merge_requests/{mr.get('iid')}/notes"
        notes_raw = self._make_paginated_request(notes_endpoint)
        notes = self._format_notes(notes_raw)

        return {
            "id": mr.get("iid"),
            "repository": repository,
            "title": mr.get("title"),
            "state": mr.get("state"),
            "created_by": mr.get("author", {}).get("username"),
            "created_at": self._format_date(mr.get("created_at")),
            "updated_at": self._format_date(mr.get("updated_at")),
            "closed_at": self._format_date(mr.get("closed_at")),
            "merged_at": self._format_date(mr.get("merged_at")),
            "body": mr.get("description", ""),
            "comments": notes,
            "url": mr.get("web_url"),
        }

    def _get_user_merge_requests(self, user_id, since_date, until_date):
        """Get merge requests that the user has created, assigned to, reviewed, or merged."""
        # Get merge requests from each category
        created_mrs = self._get_user_created_merge_requests(user_id, since_date, until_date)
        assigned_mrs = self._get_user_assigned_merge_requests(user_id, since_date, until_date)
        reviewed_mrs = self._get_user_reviewed_merge_requests(user_id, since_date, until_date)
        closed_mrs = self._get_user_closed_merge_requests(user_id, since_date, until_date)

        # Combine all merge requests, avoiding duplicates
        all_mrs = {**created_mrs, **assigned_mrs, **reviewed_mrs, **closed_mrs}

        # Format the merge requests
        mrs = [self._format_merge_request(mr) for mr in all_mrs.values()]

        log.info(f"Found {len(mrs)} unique merge requests involving user {self.username}")
        return mrs

    def _format_date(self, date_str):
        """Convert ISO date string to formatted date string."""
        if not date_str:
            return None

        try:
            dt = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
            return dt.strftime("%d-%m-%Y %H:%M")
        except (ValueError, TypeError) as e:
            log.error(f"Error parsing date {date_str}: {e}")
            return date_str

    def process(self, since_date, until_date):
        """
        Process GitLab data for the given date range.
        Returns JSON data with the results.
        """
        log.info(
            f"Querying GitLab for activity by user {self.username} between {since_date} and {until_date}"
        )

        # Get user ID
        user_id = self._get_user_id()
        if not user_id:
            log.error("Could not retrieve user ID, aborting")
            return json.dumps({"error": "Could not retrieve user ID"})

        # Get data for each section
        issues = self._get_user_issues(user_id, since_date, until_date)
        merge_requests = self._get_user_merge_requests(user_id, since_date, until_date)

        # Build result
        result = {
            "source": "gitlab",
            "user": self.username,
            "activity": {
                "issues": issues,
                "merge_requests": merge_requests,
            },
        }

        return json.dumps(result, indent=2)
