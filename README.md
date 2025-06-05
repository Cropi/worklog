# Worklog

Worklog is a tool that helps you track and query your work activities across different platforms. It allows you to generate reports about what you've worked on during a specific period of time, bringing together information from various sources into a unified view.

## Features

- Query your work activities across multiple platforms
- Filter by date ranges
- Consolidated output of all your work in one place
- Extensible plugin system for different platforms
- Retrieves full context including comments, descriptions, and metadata from each ticket/issue/PR
- Designed to feed your work data into LLMs for analysis and insights

## Key Benefits

The main purpose of Worklog is to generate structured data about your contributions that can be fed into Large Language Models (LLMs). This enables:

- AI-assisted analysis of your work patterns and contributions
- Automatic summarization of your accomplishments for reports or reviews
- Identification of trends in your work focus and productivity
- Generation of insights about your technical contributions across platforms

## Currently Supported Platforms

- GitHub - Track your commits, pull requests, reviews, and issues
- Jira - Track your tickets, comments, and transitions

## Future Integrations

The following integrations are planned for future releases:

- GitLab
- Fedora Koji
- And more to come!

## Installation

```bash
TODO
```

## Configuration

1. Copy the template configuration:

```bash
cp template/config ./config
```

2. Generate tokens for the services you want to use:

   - For GitHub: https://github.com/settings/tokens
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

## Contributing

Contributions are welcome! Feel free to open issues or submit pull requests.
