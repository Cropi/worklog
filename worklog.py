#!/usr/bin/env python3

import argparse
import datetime
import os
from config_parser import parse_config
from plugins.plugin_manager import PluginManager

def parse_date(date_str):
    """Parse date string in DD-MM-YYYY format."""
    return datetime.datetime.strptime(date_str, '%d-%m-%Y').date()

def main():
    # Parse command-line arguments
    parser = argparse.ArgumentParser(description='Generate work log report')
    parser.add_argument('--since', required=True, help='Start date (DD-MM-YYYY)')
    parser.add_argument('--until', help='End date (DD-MM-YYYY), defaults to today')
    
    args = parser.parse_args()
    
    # Parse dates
    since_date = parse_date(args.since)
    until_date = parse_date(args.until) if args.until else datetime.date.today()
    
    # Parse configuration
    config_file = os.path.join(os.path.dirname(__file__), 'config.ini')
    config_sections = parse_config(config_file)
    
    # Initialize plugin manager and discover plugins
    plugin_manager = PluginManager()
    plugin_manager.discover_plugins()
    
    # Process each section
    for section_name, section_data in config_sections.items():
        section_type = section_data.get('type')
        
        if not section_type:
            print(f"Missing 'type' in section {section_name}")
            continue
            
        # Try to get the plugin for this type
        plugin = plugin_manager.get_plugin(section_type)
        
        if plugin:
            plugin.process(section_data, since_date, until_date)
        else:
            print(f"No plugin found for type '{section_type}' in section {section_name}")

if __name__ == '__main__':
    main()
