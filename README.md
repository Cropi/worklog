# Worklog: Unified Reporting & Key Benefits

Worklog is a tool that helps you track and query your work activities across different platforms (Jira, GitHub, ...), generating comprehensive reports about what a certain person worked on during a specific period of time. It not only retrieves metadata about your work but also captures crucial contextual information like comments, descriptions, and other essential details that track the progress and priority of your work. It brings together all this information from various sources into a unified view (JSON).

Data returned by worklog is designed to be used for at least three different purposes, serving multiple roles:

- **Workload Validation (Product Owner POV)**
   - Ability to check which sprint priorities were met or missed.
   - Verification that a person's work aligned with their assigned priorities for the sprint.

- **Individual Reports (Engineer POV)**
   - Detailed view of work done by each engineer. Structured data for 1-on-1 meetings with managers to discuss accomplishments and progress.
   - Easy identification and reporting of blockers, challenges, and dependencies encountered during work.

- **Stakeholders Report (Manager POV)**
   - Possible highlights and lowlights from the previous sprint that can be shared with stakeholders.

## Currently Supported plugins

- GitHub - Track your commits, pull requests, reviews, issues, and comments
- GitLab - Track your commits, merge requests, reviews, issues, and comments
- Jira - Track your tickets, comments, transitions, and comments

## Future Integrations

The following integrations are planned for future releases:

- Fedora Koji
- CentOS
- And more to come!

## Configuration

1. Copy the template configuration:

```bash
cp template/config ./config
```

2. Generate tokens for the services you want to use:

   - For GitHub: https://github.com/settings/tokens
   - For GitLab: https://gitlab.com/-/user_settings/personal_access_tokens (requires `read_api` scope)
   - For Jira: Generate an API token from your Atlassian account

3. Add the tokens and other required information to your config file.

## Usage

Run the worklog tool with a date range to get a report of your activities:

```bash
python worklog.py --since 15-05-2025 --config ./config
```

The tool will retrieve comprehensive information including:

- Full ticket/issue/PR descriptions
- All comments you've made or received
- Status changes and transitions
- Metadata and context for each item

This detailed output can then be piped to an LLM for analysis.

For more options:

```bash
python worklog.py --help
```

## Notes

> **Read-only:** Worklog only collects and aggregates data from your connected platforms. The collected data is designed to be processed by LLMs for analysis and insights.
> 
> **Output Format:** All results are returned in JSON format for easy integration, further processing, or analysis.