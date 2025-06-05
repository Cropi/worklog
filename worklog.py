#!/usr/bin/env python3

import argparse
import datetime
import logging
import os
import sys
import json
from config_parser import parse_config
from plugins.plugin_manager import PluginManager
from logger import log


def parse_date(date_str):
    """Parse date string in DD-MM-YYYY format."""
    return datetime.datetime.strptime(date_str, "%d-%m-%Y").date()


def main():
    log.info("Starting worklog generation")

    # Parse command-line arguments
    parser = argparse.ArgumentParser(
        description="Generate work log report from various data sources",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  worklog.py --config /path/to/config.ini --since 01-01-2023
  worklog.py --config /path/to/config.ini --since 01-01-2023 --until 31-01-2023 --debug
        """,
    )
    parser.add_argument(
        "--since", required=True, help="Start date in DD-MM-YYYY format"
    )
    parser.add_argument(
        "--until", help="End date in DD-MM-YYYY format (defaults to today)"
    )
    parser.add_argument("--config", required=True, help="Path to configuration file")
    parser.add_argument(
        "--debug", action="store_true", help="Enable detailed debug logging"
    )

    args = parser.parse_args()

    # Configure logging based on debug flag
    if args.debug:
        log.set_level(logging.DEBUG)

    # Parse dates
    since = parse_date(args.since)
    until = parse_date(args.until) if args.until else datetime.date.today()
    log.info(f"Date range: {since} to {until}")

    # Parse configuration from specified file
    config_file = args.config
    if not os.path.exists(config_file):
        log.error(f"Configuration file not found: {config_file}")
        sys.exit(1)

    log.info(f"Loading configuration from {config_file}")
    config_sections = parse_config(config_file)
    log.debug(f"Loaded {len(config_sections)} configuration sections")

    # Initialize plugin manager and discover plugins
    log.info("Initializing plugin manager")
    plugin_manager = PluginManager()
    plugin_manager.discover_plugins()
    log.info(f"Discovered {len(plugin_manager.plugins)} plugins")

    results = []
    # Process each section
    log.info("Processing configuration sections")
    for section_name, section_data in config_sections.items():
        log.debug(f"Processing section: {section_name}")
        section_type = section_data.get("type")

        if not section_type:
            log.warning(f"Missing 'type' in section {section_name}")
            continue

        # Try to get the plugin for this type
        plugin = plugin_manager.get_plugin(section_type)

        if plugin:
            log.debug(f"Using plugin '{section_type}' for section {section_name}")
            # Initialize and parse configuration
            if plugin.parse(section_data):
                log.info(f"Processing data for section {section_name}")
                # Process data and get results
                result_json = plugin.process(since, until)
                result = json.loads(result_json)
                results.append(result)
                log.debug(f"Successfully processed section {section_name}")
            else:
                log.error(
                    f"Failed to parse configuration for plugin type '{section_type}' in section {section_name}"
                )
        else:
            log.error(
                f"No plugin found for type '{section_type}' in section {section_name}"
            )

    log.info("Worklog generation completed")

    # Output results to stdout
    print(json.dumps(results, indent=4))


if __name__ == "__main__":
    main()
