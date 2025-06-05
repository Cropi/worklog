from .plugin_base import PluginBase
import json
import requests
import os
from datetime import datetime
from logger import log


class GitHubPlugin(PluginBase):
    """Plugin for retrieving data from GitHub."""

    def __init__(self, config=None):
        """Initialize with configuration."""
        self.config = config
        self.token = None
        self.username = None
        self.owner = None  # Optional
        self.repo = None  # Optional
        self.api_base_url = "https://api.github.com"

    def get_type(self):
        return "github"

    def parse(self, config=None):
        """
        Parse and validate the GitHub configuration.
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
                f"GitHub configuration missing required parameters: {', '.join(missing_fields)}"
            )
            return False

        # Store required parameters
        self.username = self.config.get("username")

        # Optional repository specification
        self.owner = self.config.get("owner", "")
        self.repo = self.config.get("repo", "")

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

        # Hardcode the GitHub API URL
        self.api_base_url = "https://api.github.com"

        return True

    def _make_request(self, endpoint, params=None):
        """
        Make an authenticated request to the GitHub API.

        Args:
            endpoint: The API endpoint to call
            params: Optional query parameters

        Returns:
            API response as JSON or None on error
        """
        headers = {
            "Authorization": f"token {self.token}",
            "Accept": "application/vnd.github.v3+json",
        }

        url = f"{self.api_base_url}{endpoint}"
        log.debug(f"Making request to: {url}")
        if params:
            log.debug(f"With parameters: {params}")

        try:
            response = requests.get(url, headers=headers, params=params)
            log.debug(f"Response status code: {response.status_code}")

            if response.status_code == 403 and "rate limit" in response.text.lower():
                log.warning("GitHub API rate limit exceeded")

            response.raise_for_status()
            return response.json()

        except requests.exceptions.RequestException as e:
            log.error(f"Error making request to GitHub API: {e}")
            return None

    def _search_github(self, search_type, query, custom_headers=None):
        """
        Generic function to search GitHub API.

        Args:
            search_type: Type of search (issues, commits, etc.)
            query: The search query string
            custom_headers: Optional custom headers for specific API endpoints

        Returns:
            List of search results or None on error
        """
        endpoint = f"/search/{search_type}"

        params = {
            "q": query,
            "per_page": 100,
            "sort": "updated" if search_type != "commits" else "author-date",
            "order": "desc",
        }

        # Use default headers or custom headers if provided
        headers = {
            "Authorization": f"token {self.token}",
            "Accept": "application/vnd.github.v3+json",
        }

        if custom_headers:
            headers.update(custom_headers)

        url = f"{self.api_base_url}{endpoint}"
        log.debug(f"Searching GitHub {search_type} with query: {query}")
        log.debug(f"Making request to: {url}")

        try:
            response = requests.get(url, headers=headers, params=params)
            log.debug(f"Response status code: {response.status_code}")

            if response.status_code == 403 and "rate limit" in response.text.lower():
                log.warning("GitHub API rate limit exceeded")

            response.raise_for_status()
            search_result = response.json()

            if "items" not in search_result:
                log.warning(f"No {search_type} found in search results")
                return []

            log.debug(
                f"Found {len(search_result['items'])} {search_type} in search results"
            )
            return search_result["items"]

        except requests.exceptions.RequestException as e:
            log.error(f"Error making request to GitHub API: {e}")
            return None

    def _has_user_comment_in_timeframe(
        self, comments, username, since_date, until_date
    ):
        """
        Check if the issue has been commented on by the user within the time frame.

        Args:
            comments: List of comment objects
            username: The GitHub username to check for
            since_date: Start date (datetime object)
            until_date: End date (datetime object)

        Returns:
            Boolean indicating if user commented within the timeframe
        """
        for comment in comments:
            # Check if comment is by the user
            if comment.get("user", {}).get("login") != username:
                continue

            # Parse comment date
            created_at = comment.get("created_at", "")
            if not created_at:
                continue

            try:
                comment_date = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
                # Check if comment is within the date range
                if since_date <= comment_date.date() <= until_date:
                    return True
            except (ValueError, TypeError):
                continue

        return False

    def _get_user_commented_issues(self, since_date, until_date):
        """
        Get issues that the user has commented on within the time frame.

        Args:
            since_date: Start date
            until_date: End date

        Returns:
            Dictionary of issues indexed by ID
        """
        since_str = since_date.isoformat()
        until_str = until_date.isoformat()

        # Query for issues the user has commented on
        query = f"commenter:{self.username} updated:{since_str}..{until_str} is:issue"

        log.debug(f"Running GitHub commented issues query: {query}")
        issues_raw = self._search_github("issues", query)

        commented_issues = {}
        if not issues_raw:
            return commented_issues

        for issue in issues_raw:
            # Get comments for this issue to verify the user commented in the timeframe
            comments_url = issue.get("comments_url", "").replace(self.api_base_url, "")
            comments_raw = self._make_request(comments_url)

            # Skip issues where the user didn't comment in the timeframe
            if not comments_raw or not self._has_user_comment_in_timeframe(
                comments_raw, self.username, since_date, until_date
            ):
                continue

            # Add to our collection, indexed by ID
            issue_id = issue.get("id")
            commented_issues[issue_id] = issue

        log.info(
            f"Found {len(commented_issues)} issues commented on by user {self.username}"
        )
        return commented_issues

    def _get_user_created_issues(self, since_date, until_date):
        """
        Get issues that the user has created within the time frame.

        Args:
            since_date: Start date
            until_date: End date

        Returns:
            Dictionary of issues indexed by ID
        """
        since_str = since_date.isoformat()
        until_str = until_date.isoformat()

        # Query for issues the user has created
        query = f"author:{self.username} created:{since_str}..{until_str} is:issue"

        log.debug(f"Running GitHub created issues query: {query}")
        issues_raw = self._search_github("issues", query)

        created_issues = {}
        if not issues_raw:
            return created_issues

        for issue in issues_raw:
            # Skip pull requests
            if "pull_request" in issue:
                continue

            # Add to our collection, indexed by ID
            issue_id = issue.get("id")
            created_issues[issue_id] = issue

        log.info(f"Found {len(created_issues)} issues created by user {self.username}")
        return created_issues

    def _get_user_closed_issues(self, since_date, until_date):
        """
        Get issues assigned to the user that were closed within the time frame.

        Args:
            since_date: Start date
            until_date: End date

        Returns:
            Dictionary of issues indexed by ID
        """
        since_str = since_date.isoformat()
        until_str = until_date.isoformat()

        # Query for issues assigned to the user that were closed
        query = f"assignee:{self.username} closed:{since_str}..{until_str} is:issue"

        log.debug(f"Running GitHub closed issues query: {query}")
        issues_raw = self._search_github("issues", query)

        closed_issues = {}
        if not issues_raw:
            return closed_issues

        for issue in issues_raw:
            # Skip pull requests
            if "pull_request" in issue:
                continue

            # Add to our collection, indexed by ID
            issue_id = issue.get("id")
            closed_issues[issue_id] = issue

        log.info(f"Found {len(closed_issues)} issues closed by user {self.username}")
        return closed_issues

    def _get_user_issues(self, since_date, until_date):
        """
        Get issues that the user has created, commented on, or closed across all repositories.

        Args:
            since_date: Start date
            until_date: End date

        Returns:
            List of formatted issue data
        """
        # Get issues from each category
        commented_issues = self._get_user_commented_issues(since_date, until_date)
        created_issues = self._get_user_created_issues(since_date, until_date)
        closed_issues = self._get_user_closed_issues(since_date, until_date)

        # Combine all issues, avoiding duplicates
        all_issues = {**commented_issues, **created_issues, **closed_issues}

        # Process the unique issues
        issues = []
        for issue in all_issues.values():
            # Get repository information from the issue
            repo_url = issue.get("repository_url", "")
            repo_parts = repo_url.split("/")
            if len(repo_parts) >= 2:
                repo_owner = repo_parts[-2]
                repo_name = repo_parts[-1]
            else:
                repo_owner = "unknown"
                repo_name = "unknown"

            # Get comments for this issue
            comments_url = issue.get("comments_url", "").replace(self.api_base_url, "")
            comments_raw = self._make_request(comments_url)
            comments = []

            if comments_raw:
                for comment in comments_raw:
                    comment_data = {
                        "author": comment.get("user", {}).get("login"),
                        "created_at": self._format_date(comment.get("created_at")),
                        "body": comment.get("body", ""),
                    }
                    comments.append(comment_data)

            issue_data = {
                "id": issue.get("number"),
                "repository": f"{repo_owner}/{repo_name}",
                "title": issue.get("title"),
                "state": issue.get("state"),
                "created_by": issue.get("user", {}).get("login"),
                "created_at": self._format_date(issue.get("created_at")),
                "updated_at": self._format_date(issue.get("updated_at")),
                "closed_at": self._format_date(issue.get("closed_at")),
                "body": issue.get("body", ""),
                "comments": comments,
                "url": issue.get("html_url"),
            }
            issues.append(issue_data)

        log.info(f"Found {len(issues)} unique issues involving user {self.username}")
        return issues

    def _get_user_commented_prs(self, since_date, until_date):
        """
        Get PRs that the user has commented on within the time frame.

        Args:
            since_date: Start date
            until_date: End date

        Returns:
            Dictionary of PRs indexed by ID
        """
        since_str = since_date.isoformat()
        until_str = until_date.isoformat()

        # Query for PRs the user has commented on
        query = f"commenter:{self.username} updated:{since_str}..{until_str} is:pr"

        log.debug(f"Running GitHub commented PRs query: {query}")
        prs_raw = self._search_github("issues", query)

        commented_prs = {}
        if not prs_raw:
            return commented_prs

        for pr in prs_raw:
            # Get comments for this PR to verify the user commented in the timeframe
            comments_url = pr.get("comments_url", "").replace(self.api_base_url, "")
            comments_raw = self._make_request(comments_url)

            # Skip PRs where the user didn't comment in the timeframe
            if not comments_raw or not self._has_user_comment_in_timeframe(
                comments_raw, self.username, since_date, until_date
            ):
                continue

            # Add to our collection, indexed by ID
            pr_id = pr.get("id")
            commented_prs[pr_id] = pr

        log.info(f"Found {len(commented_prs)} PRs commented on by user {self.username}")
        return commented_prs

    def _get_user_created_prs(self, since_date, until_date):
        """
        Get PRs that the user has created within the time frame.

        Args:
            since_date: Start date
            until_date: End date

        Returns:
            Dictionary of PRs indexed by ID
        """
        since_str = since_date.isoformat()
        until_str = until_date.isoformat()

        # Query for PRs the user has created
        query = f"author:{self.username} created:{since_str}..{until_str} is:pr"

        log.debug(f"Running GitHub created PRs query: {query}")
        prs_raw = self._search_github("issues", query)

        created_prs = {}
        if not prs_raw:
            return created_prs

        for pr in prs_raw:
            # Add to our collection, indexed by ID
            pr_id = pr.get("id")
            created_prs[pr_id] = pr

        log.info(f"Found {len(created_prs)} PRs created by user {self.username}")
        return created_prs

    def _get_user_closed_prs(self, since_date, until_date):
        """
        Get PRs assigned to the user that were closed within the time frame.

        Args:
            since_date: Start date
            until_date: End date

        Returns:
            Dictionary of PRs indexed by ID
        """
        since_str = since_date.isoformat()
        until_str = until_date.isoformat()

        # Query for PRs assigned to the user that were closed
        query = f"assignee:{self.username} closed:{since_str}..{until_str} is:pr"

        log.debug(f"Running GitHub closed PRs query: {query}")
        prs_raw = self._search_github("issues", query)

        closed_prs = {}
        if not prs_raw:
            return closed_prs

        for pr in prs_raw:
            # Add to our collection, indexed by ID
            pr_id = pr.get("id")
            closed_prs[pr_id] = pr

        log.info(f"Found {len(closed_prs)} PRs closed by user {self.username}")
        return closed_prs

    def _get_user_reviewed_prs(self, since_date, until_date):
        """
        Get PRs reviewed by the user within the time frame.

        Args:
            since_date: Start date
            until_date: End date

        Returns:
            Dictionary of PRs indexed by ID
        """
        since_str = since_date.isoformat()
        until_str = until_date.isoformat()

        # Query for PRs reviewed by the user (excluding authored by user)
        query = f"reviewed-by:{self.username} -author:{self.username} closed:{since_str}..{until_date} is:pr"

        log.debug(f"Running GitHub reviewed PRs query: {query}")
        prs_raw = self._search_github("issues", query)

        reviewed_prs = {}
        if not prs_raw:
            return reviewed_prs

        for pr in prs_raw:
            # Add to our collection, indexed by ID
            pr_id = pr.get("id")
            reviewed_prs[pr_id] = pr

        log.info(f"Found {len(reviewed_prs)} PRs reviewed by user {self.username}")
        return reviewed_prs

    def _get_user_pull_requests(self, since_date, until_date):
        """
        Get PRs that the user has created, commented on, reviewed, or closed across all repositories.

        Args:
            since_date: Start date
            until_date: End date

        Returns:
            List of formatted PR data
        """
        # Get PRs from each category
        commented_prs = self._get_user_commented_prs(since_date, until_date)
        created_prs = self._get_user_created_prs(since_date, until_date)
        closed_prs = self._get_user_closed_prs(since_date, until_date)
        reviewed_prs = self._get_user_reviewed_prs(since_date, until_date)

        # Combine all PRs, avoiding duplicates
        all_prs = {**commented_prs, **created_prs, **closed_prs, **reviewed_prs}

        # Process the unique PRs
        prs = []
        for pr in all_prs.values():
            # Get repository information from the PR
            repo_url = pr.get("repository_url", "")
            repo_parts = repo_url.split("/")
            if len(repo_parts) >= 2:
                repo_owner = repo_parts[-2]
                repo_name = repo_parts[-1]
            else:
                repo_owner = "unknown"
                repo_name = "unknown"

            # Get PR number for additional API calls
            pr_number = pr.get("number")
            pr_api_url = (
                pr.get("pull_request", {}).get("url", "").replace(self.api_base_url, "")
            )

            # Get additional PR details
            pr_details = self._make_request(pr_api_url) if pr_api_url else {}

            # Get comments
            comments_url = pr.get("comments_url", "").replace(self.api_base_url, "")
            comments_raw = self._make_request(comments_url)
            comments = []

            if comments_raw:
                for comment in comments_raw:
                    comment_data = {
                        "author": comment.get("user", {}).get("login"),
                        "created_at": self._format_date(comment.get("created_at")),
                        "body": comment.get("body", ""),
                    }
                    comments.append(comment_data)

            merged_at = pr_details.get("merged_at") if pr_details else None

            pr_data = {
                "id": pr_number,
                "repository": f"{repo_owner}/{repo_name}",
                "title": pr.get("title"),
                "state": pr.get("state"),
                "created_by": pr.get("user", {}).get("login"),
                "created_at": self._format_date(pr.get("created_at")),
                "updated_at": self._format_date(pr.get("updated_at")),
                "closed_at": self._format_date(pr.get("closed_at")),
                "merged_at": self._format_date(merged_at),
                "body": pr.get("body", ""),
                "comments": comments,
                "url": pr.get("html_url"),
            }
            prs.append(pr_data)

        log.info(f"Found {len(prs)} pull requests involving user {self.username}")
        return prs

    def _get_user_commits(self, since_date, until_date):
        """
        Get commits that the user has created across all repositories.

        Args:
            since_date: Start date
            until_date: End date

        Returns:
            List of formatted commit data
        """
        # Create query to find commits authored by the user
        query = f"author:{self.username} author-date:{since_date.isoformat()}..{until_date.isoformat()}"

        # Commits search requires a special header
        custom_headers = {"Accept": "application/vnd.github.cloak-preview+json"}

        # Search for commits
        commits_raw = self._search_github("commits", query, custom_headers)

        if not commits_raw:
            return []

        commits = []
        for commit in commits_raw:
            # Get repository information
            repo_url = commit.get("repository", {}).get("url", "")
            repo_parts = repo_url.split("/")
            if len(repo_parts) >= 2:
                repo_owner = repo_parts[-2]
                repo_name = repo_parts[-1]
            else:
                repo_owner = "unknown"
                repo_name = "unknown"

            commit_data = {
                "id": commit.get("sha"),
                "repository": f"{repo_owner}/{repo_name}",
                "message": commit.get("commit", {}).get("message", ""),
                "author": commit.get("commit", {}).get("author", {}).get("name"),
                "email": commit.get("commit", {}).get("author", {}).get("email"),
                "date": self._format_date(
                    commit.get("commit", {}).get("author", {}).get("date")
                ),
                "url": commit.get("html_url"),
            }
            commits.append(commit_data)

        log.info(f"Found {len(commits)} commits by user {self.username}")
        return commits

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
        Process GitHub data for the given date range.
        Returns JSON data with the results.
        """
        log.info(
            f"Querying GitHub for activity by user {self.username} between {since_date} and {until_date}"
        )

        # Get data for each section
        # issues = self._get_user_issues(since_date, until_date)
        pull_requests = self._get_user_pull_requests(since_date, until_date)
        # commits = self._get_user_commits(since_date, until_date)

        # Build result
        result = {
            "source": "github",
            "user": self.username,
            "activity": {
                # "issues": issues,
                "pull_requests": pull_requests,
                # "commits": commits,
            },
        }

        return json.dumps(result, indent=2)
