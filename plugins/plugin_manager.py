import os
import importlib
import inspect
from .plugin_base import PluginBase

class PluginManager:
    """Manages the discovery, loading and access to plugins."""
    
    def __init__(self):
        self.plugins = {}
    
    def discover_plugins(self):
        """Find and load all plugins in the plugins directory."""
        # Get the directory where plugins are stored
        plugins_dir = os.path.dirname(os.path.abspath(__file__))
        
        # Get all Python files in the plugins directory
        for filename in os.listdir(plugins_dir):
            if filename.endswith('.py') and not filename.startswith('__') and filename != 'plugin_base.py' and filename != 'plugin_manager.py':
                module_name = filename[:-3]  # Remove .py extension
                
                try:
                    # Import the module
                    module = importlib.import_module(f'plugins.{module_name}')
                    
                    # Look for plugin classes (subclasses of PluginBase)
                    for _, obj in inspect.getmembers(module):
                        if (inspect.isclass(obj) and 
                            issubclass(obj, PluginBase) and 
                            obj is not PluginBase):
                            
                            # Instantiate the plugin
                            plugin = obj()
                            
                            # Register the plugin by its type
                            self.plugins[plugin.get_type()] = plugin
                            print(f"Registered plugin for type: {plugin.get_type()}")
                            
                except Exception as e:
                    print(f"Error loading plugin {module_name}: {e}")
    
    def get_plugin(self, plugin_type):
        """Get a plugin by its type."""
        return self.plugins.get(plugin_type)
    
    def get_available_plugins(self):
        """Get a list of all available plugin types."""
        return list(self.plugins.keys())
