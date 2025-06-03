def parse_config(config_file):
    """
    Parse the configuration file with sections and key-value pairs.
    
    Args:
        config_file (str): Path to the configuration file.
        
    Returns:
        dict: Dictionary with section names as keys and section data as values.
    """
    config_sections = {}
    current_section = None
    
    try:
        with open(config_file, 'r') as f:
            for line in f:
                line = line.strip()
                
                # Skip empty lines and comments
                if not line or line.startswith('#'):
                    continue
                
                # Check for section header
                if line.startswith('[') and line.endswith(']'):
                    current_section = line[1:-1]
                    config_sections[current_section] = {}
                    continue
                
                # Process key-value pairs
                if current_section is not None and '=' in line:
                    key, value = line.split('=', 1)
                    key = key.strip()
                    value = value.strip()
                    
                    # Remove quotes if present
                    if value.startswith('"') and value.endswith('"'):
                        value = value[1:-1]
                    
                    config_sections[current_section][key] = value
    
    except FileNotFoundError:
        print(f"Configuration file '{config_file}' not found.")
    except Exception as e:
        print(f"Error parsing configuration file: {e}")
    
    return config_sections
