from .plugin_base import PluginBase

class JiraPlugin(PluginBase):
    """Plugin for retrieving data from Jira."""
    
    def get_type(self):
        return "jira"
    
    def validate_config(self, config):
        """Validate the Jira configuration."""
        required_fields = ['url', 'token', 'name']
        missing_fields = [field for field in required_fields if not config.get(field)]
        
        if missing_fields:
            print(f"Jira configuration missing required parameters: {', '.join(missing_fields)}")
            return False
        return True
    
    def process(self, config, since_date, until_date):
        """Process Jira data for the given date range."""
        if not self.validate_config(config):
            return
        
        url = config.get('url')
        token = config.get('token')
        
        print(f"Querying Jira at {url} for work items between {since_date} and {until_date}")
        
        # Actual Jira API implementation would go here
        print(f"Using configuration: {config}")
        
        # Here you would:
        # 1. Connect to Jira API using the URL and token
        # 2. Query for issues updated between since_date and until_date
        # 3. Process the results and generate a report
