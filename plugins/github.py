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
            "User-Agent": "Worklog-App",
        }

        url = f"{self.api_base_url}{endpoint}"
        log.debug(f"Making request to: {url}")
        if params:
            log.debug(f"With parameters: {params}")

        try:
            response = requests.get(url, headers=headers, params=params)
            log.debug(f"Response status code: {response.status_code}")

            if response.status_code == 403:
                if "rate limit" in response.text.lower():
                    log.warning("GitHub API rate limit exceeded")
                else:
                    log.error(f"GitHub API 403 Forbidden: {response.text}")

            response.raise_for_status()
            return response.json()

        except requests.exceptions.RequestException as e:
            log.error(f"Error making request to GitHub API: {e}")
            if hasattr(e, 'response') and e.response is not None:
                log.error(f"Response content: {e.response.text}")
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
            "per_page": 200,
            "sort": "updated" if search_type != "commits" else "author-date",
            "order": "desc",
        }

        # Use default headers or custom headers if provided
        headers = {
            "Authorization": f"token {self.token}",
            "Accept": "application/vnd.github.v3+json",
            "User-Agent": "Worklog-App",
        }

        if custom_headers:
            headers.update(custom_headers)

        url = f"{self.api_base_url}{endpoint}"
        log.debug(f"Searching GitHub {search_type} with query: {query}")
        log.debug(f"Making request to: {url}")

        try:
            response = requests.get(url, headers=headers, params=params)
            log.debug(f"Response status code: {response.status_code}")

            if response.status_code == 403:
                if "rate limit" in response.text.lower():
                    log.warning("GitHub API rate limit exceeded")
                else:
                    log.error(f"GitHub API 403 Forbidden: {response.text}")

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
            if hasattr(e, 'response') and e.response is not None:
                log.error(f"Response content: {e.response.text}")
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

    def _get_items_by_query(
        self, query, item_type, since_date, until_date, need_comment_validation=False
    ):
        """
        Generic method to fetch GitHub items (issues or PRs) by query.

        Args:
            query: The search query
            item_type: String description of what we're fetching (for logging)
            since_date: Start date
            until_date: End date
            need_comment_validation: Whether to validate comments are in timeframe

        Returns:
            Dictionary of items indexed by ID
        """
        log.debug(f"Running GitHub {item_type} query: {query}")
        items_raw = self._search_github("issues", query)

        result_items = {}
        if not items_raw:
            return result_items

        for item in items_raw:
            # Skip items of wrong type
            if "pull_request" in item and item_type.startswith("issue"):
                continue
            if "pull_request" not in item and item_type.startswith("PR"):
                continue

            # For items requiring comment validation
            if need_comment_validation:
                comments_url = item.get("comments_url", "").replace(
                    self.api_base_url, ""
                )
                comments_raw = self._make_request(comments_url)

                # Skip if no valid comments in timeframe
                if not comments_raw or not self._has_user_comment_in_timeframe(
                    comments_raw, self.username, since_date, until_date
                ):
                    continue

            # Add to collection
            item_id = item.get("id")
            result_items[item_id] = item

        log.info(f"Found {len(result_items)} {item_type} items")
        return result_items

    def _extract_repo_info(self, item):
        """Extract repository owner and name from an item."""
        repo_url = item.get("repository_url", "")
        repo_parts = repo_url.split("/")
        if len(repo_parts) >= 2:
            repo_owner = repo_parts[-2]
            repo_name = repo_parts[-1]
        else:
            repo_owner = "unknown"
            repo_name = "unknown"

        return repo_owner, repo_name

    def _format_comments(self, comments_raw):
        """Format comments from API response."""
        comments = []
        if not comments_raw:
            return comments

        for comment in comments_raw:
            comment_data = {
                "author": comment.get("user", {}).get("login"),
                "created_at": self._format_date(comment.get("created_at")),
                "body": comment.get("body", ""),
            }
            comments.append(comment_data)

        return comments

    def _get_user_commented_issues(self, since_date, until_date):
        """Get issues that the user has commented on within the time frame."""
        since_str = since_date.isoformat()
        until_str = until_date.isoformat()

        query = f"commenter:{self.username} updated:{since_str}..{until_str} is:issue"
        return self._get_items_by_query(
            query,
            "issues commented on",
            since_date,
            until_date,
            need_comment_validation=True,
        )

    def _get_user_created_issues(self, since_date, until_date):
        """Get issues that the user has created within the time frame."""
        since_str = since_date.isoformat()
        until_str = until_date.isoformat()

        query = f"author:{self.username} created:{since_str}..{until_str} is:issue"
        return self._get_items_by_query(query, "issues created", since_date, until_date)

    def _get_user_closed_issues(self, since_date, until_date):
        """Get issues assigned to the user that were closed within the time frame."""
        since_str = since_date.isoformat()
        until_str = until_date.isoformat()

        query = f"assignee:{self.username} closed:{since_str}..{until_str} is:issue"
        return self._get_items_by_query(query, "issues closed", since_date, until_date)

    def _get_user_commented_prs(self, since_date, until_date):
        """Get PRs that the user has commented on within the time frame."""
        since_str = since_date.isoformat()
        until_str = until_date.isoformat()

        query = f"commenter:{self.username} updated:{since_str}..{until_str} is:pr"
        return self._get_items_by_query(
            query,
            "PRs commented on",
            since_date,
            until_date,
            need_comment_validation=True,
        )

    def _get_user_created_prs(self, since_date, until_date):
        """Get PRs that the user has created within the time frame."""
        since_str = since_date.isoformat()
        until_str = until_date.isoformat()

        query = f"author:{self.username} created:{since_str}..{until_str} is:pr"
        return self._get_items_by_query(query, "PRs created", since_date, until_date)

    def _get_user_closed_prs(self, since_date, until_date):
        """Get PRs assigned to the user that were closed within the time frame."""
        since_str = since_date.isoformat()
        until_str = until_date.isoformat()

        query = f"assignee:{self.username} closed:{since_str}..{until_str} is:pr"
        return self._get_items_by_query(query, "PRs closed", since_date, until_date)

    def _get_user_reviewed_prs(self, since_date, until_date):
        """Get PRs reviewed by the user within the time frame."""
        since_str = since_date.isoformat()
        until_str = until_date.isoformat()

        query = f"reviewed-by:{self.username} -author:{self.username} closed:{since_str}..{until_str} is:pr"
        return self._get_items_by_query(query, "PRs reviewed", since_date, until_date)

    def _format_issue(self, issue):
        """Format an issue into the standard output structure."""
        repo_owner, repo_name = self._extract_repo_info(issue)

        # Get comments
        comments_url = issue.get("comments_url", "").replace(self.api_base_url, "")
        comments_raw = self._make_request(comments_url)
        comments = self._format_comments(comments_raw)

        return {
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

    def _format_pr(self, pr):
        """Format a PR into the standard output structure."""
        repo_owner, repo_name = self._extract_repo_info(pr)

        # Get PR details
        pr_number = pr.get("number")
        pr_api_url = (
            pr.get("pull_request", {}).get("url", "").replace(self.api_base_url, "")
        )
        pr_details = self._make_request(pr_api_url) if pr_api_url else {}

        # Get comments
        comments_url = pr.get("comments_url", "").replace(self.api_base_url, "")
        comments_raw = self._make_request(comments_url)
        comments = self._format_comments(comments_raw)

        merged_at = pr_details.get("merged_at") if pr_details else None

        return {
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

    def _get_user_issues(self, since_date, until_date):
        """Get issues that the user has created, commented on, or closed."""
        # Get issues from each category
        commented_issues = self._get_user_commented_issues(since_date, until_date)
        created_issues = self._get_user_created_issues(since_date, until_date)
        closed_issues = self._get_user_closed_issues(since_date, until_date)

        # Combine all issues, avoiding duplicates
        all_issues = {**commented_issues, **created_issues, **closed_issues}

        # Format the issues
        issues = [self._format_issue(issue) for issue in all_issues.values()]

        log.info(f"Found {len(issues)} unique issues involving user {self.username}")
        return issues

    def _get_user_pull_requests(self, since_date, until_date):
        """Get PRs that the user has created, commented on, reviewed, or closed."""
        # Get PRs from each category
        commented_prs = self._get_user_commented_prs(since_date, until_date)
        created_prs = self._get_user_created_prs(since_date, until_date)
        closed_prs = self._get_user_closed_prs(since_date, until_date)
        reviewed_prs = self._get_user_reviewed_prs(since_date, until_date)

        # Combine all PRs, avoiding duplicates
        all_prs = {**commented_prs, **created_prs, **closed_prs, **reviewed_prs}

        # Format the PRs
        prs = [self._format_pr(pr) for pr in all_prs.values()]

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
        issues = self._get_user_issues(since_date, until_date)
        pull_requests = self._get_user_pull_requests(since_date, until_date)
        commits = self._get_user_commits(since_date, until_date)

        # Build result
        result = {
            "source": "github",
            "user": self.username,
            "activity": {
                "issues": issues,
                "pull_requests": pull_requests,
                "commits": commits,
            },
        }

        return json.dumps(result, indent=2)
