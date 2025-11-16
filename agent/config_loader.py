"""
Configuration Loader for Loglumen Agent

Loads and validates configuration from config.toml file.
"""

import os
import sys
from typing import Dict, Any, Optional

# Try to import toml library
try:
    import toml
    TOML_AVAILABLE = True
except ImportError:
    TOML_AVAILABLE = False
    print("Warning: toml library not available. Install with: pip install toml")


class ConfigurationError(Exception):
    """Raised when configuration is invalid or missing."""
    pass


class Config:
    """
    Configuration manager for the Loglumen agent.

    Loads configuration from config.toml and provides validated access.
    """

    def __init__(self, config_path: str = None):
        """
        Initialize configuration.

        Args:
            config_path: Path to config.toml file. If None, searches for it.
        """
        if config_path is None:
            config_path = self._find_config_file()

        self.config_path = config_path
        self.config = self._load_config()
        self._validate_config()

    def _find_config_file(self) -> str:
        """Find the config.toml file."""
        # Check current directory
        if os.path.exists('config.toml'):
            return 'config.toml'

        # Check script directory
        script_dir = os.path.dirname(os.path.abspath(__file__))
        config_in_script_dir = os.path.join(script_dir, 'config.toml')
        if os.path.exists(config_in_script_dir):
            return config_in_script_dir

        # Check parent directory (project root)
        parent_dir = os.path.dirname(script_dir)
        config_in_parent = os.path.join(parent_dir, 'config', 'agent.toml')
        if os.path.exists(config_in_parent):
            return config_in_parent

        raise ConfigurationError(
            "config.toml not found. Please create one or specify path."
        )

    def _load_config(self) -> Dict[str, Any]:
        """Load configuration from TOML file."""
        if not TOML_AVAILABLE:
            return self._load_config_manual()

        try:
            with open(self.config_path, 'r') as f:
                config = toml.load(f)
            return config
        except Exception as e:
            raise ConfigurationError(f"Error loading config: {e}")

    def _load_config_manual(self) -> Dict[str, Any]:
        """
        Fallback config loader if toml library not available.
        Simple parser for basic TOML files.
        """
        config = {}
        current_section = None

        try:
            with open(self.config_path, 'r') as f:
                for line in f:
                    line = line.strip()

                    # Skip comments and empty lines
                    if not line or line.startswith('#'):
                        continue

                    # Section header
                    if line.startswith('[') and line.endswith(']'):
                        current_section = line[1:-1]
                        config[current_section] = {}
                        continue

                    # Key-value pair
                    if '=' in line and current_section:
                        key, value = line.split('=', 1)
                        key = key.strip()
                        value = value.split('#')[0].strip()  # Remove inline comments

                        # Parse value
                        config[current_section][key] = self._parse_value(value)

            return config
        except Exception as e:
            raise ConfigurationError(f"Error parsing config: {e}")

    def _parse_value(self, value: str) -> Any:
        """Parse a configuration value."""
        value = value.strip()

        # Boolean
        if value.lower() == 'true':
            return True
        if value.lower() == 'false':
            return False

        # String (remove quotes)
        if (value.startswith('"') and value.endswith('"')) or \
           (value.startswith("'") and value.endswith("'")):
            return value[1:-1]

        # Number
        try:
            if '.' in value:
                return float(value)
            return int(value)
        except ValueError:
            pass

        # Array (simple parsing)
        if value.startswith('[') and value.endswith(']'):
            items = value[1:-1].split(',')
            return [self._parse_value(item.strip()) for item in items if item.strip()]

        # Return as string if can't parse
        return value

    def _validate_config(self):
        """Validate required configuration fields."""
        required_sections = ['agent', 'server', 'collection', 'logging']

        for section in required_sections:
            if section not in self.config:
                raise ConfigurationError(f"Missing required section: [{section}]")

        # Validate server config
        if 'server_ip' not in self.config['server']:
            raise ConfigurationError("Missing required field: server.server_ip")

        if 'server_port' not in self.config['server']:
            raise ConfigurationError("Missing required field: server.server_port")

    def get(self, section: str, key: str, default: Any = None) -> Any:
        """
        Get a configuration value.

        Args:
            section: Configuration section (e.g., 'server')
            key: Configuration key (e.g., 'server_ip')
            default: Default value if not found

        Returns:
            Configuration value or default
        """
        try:
            return self.config[section][key]
        except KeyError:
            return default

    def get_server_url(self) -> str:
        """Get the complete server URL."""
        protocol = "https" if self.get('server', 'use_https', False) else "http"
        ip = self.get('server', 'server_ip')
        port = self.get('server', 'server_port')
        path = self.get('server', 'api_path', '/api/events')

        return f"{protocol}://{ip}:{port}{path}"

    def get_server_config(self) -> Dict[str, Any]:
        """Get all server configuration as a dictionary."""
        return {
            'server_ip': self.get('server', 'server_ip'),
            'server_port': self.get('server', 'server_port'),
            'use_https': self.get('server', 'use_https', False),
            'api_path': self.get('server', 'api_path', '/api/events'),
            'api_key': self.get('server', 'api_key', None),
            'timeout': self.get('server', 'timeout', 30),
            'max_retries': self.get('server', 'max_retries', 3),
            'retry_delay': self.get('server', 'retry_delay', 5),
        }

    def get_collection_config(self) -> Dict[str, Any]:
        """Get all collection configuration as a dictionary."""
        return {
            'collection_interval': self.get('collection', 'collection_interval', 60),
            'max_lines_per_log': self.get('collection', 'max_lines_per_log', 1000),
            'hours_lookback': self.get('collection', 'hours_lookback', 1),
            'enabled_categories': self.get('collection', 'enabled_categories',
                                         ['auth', 'system', 'service', 'software']),
            'max_events_per_batch': self.get('collection', 'max_events_per_batch', 500),
        }

    def __str__(self) -> str:
        """String representation of configuration."""
        server_url = self.get_server_url()
        return f"Loglumen Agent Config (Server: {server_url})"


def load_config(config_path: str = None) -> Config:
    """
    Load configuration from file.

    Args:
        config_path: Path to config file (optional)

    Returns:
        Config object

    Example:
        config = load_config()
        print(config.get_server_url())
    """
    return Config(config_path)


if __name__ == "__main__":
    """Test the configuration loader."""
    print("=" * 70)
    print("Configuration Loader Test")
    print("=" * 70)

    try:
        config = load_config()
        print(f"\n[OK] Configuration loaded from: {config.config_path}")

        print(f"\nServer Configuration:")
        print(f"  URL: {config.get_server_url()}")
        server_config = config.get_server_config()
        for key, value in server_config.items():
            if key != 'api_key':  # Don't print API key
                print(f"  {key}: {value}")

        print(f"\nCollection Configuration:")
        coll_config = config.get_collection_config()
        for key, value in coll_config.items():
            print(f"  {key}: {value}")

        print(f"\nAgent Configuration:")
        print(f"  client_name: {config.get('agent', 'client_name', 'unknown')}")
        print(f"  log_level: {config.get('logging', 'log_level', 'INFO')}")

        print("\n" + "=" * 70)
        print("[SUCCESS] Configuration is valid and ready to use!")
        print("=" * 70)

    except ConfigurationError as e:
        print(f"\n[ERROR] Configuration error: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\n[ERROR] Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
