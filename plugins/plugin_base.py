from abc import ABC, abstractmethod

class PluginBase(ABC):
    """Base class that all plugins must inherit from."""
    
    @abstractmethod
    def get_type(self):
        """Return the type identifier for this plugin."""
        pass
    
    @abstractmethod
    def parse(self, config):
        """
        Parse and validate the configuration.
        Returns True if valid, False otherwise.
        """
        pass
    
    @abstractmethod
    def process(self, since_date, until_date):
        """
        Process data for the given date range.
        
        Args:
            since_date (datetime.date): Start date for data retrieval
            until_date (datetime.date): End date for data retrieval
            
        Returns:
            str: JSON string with the processed data
        """
        pass
