"""
Resource loading utilities for handling bundled and development resources.
"""
import os
import sys
from pathlib import Path
from typing import Optional


def get_resource_path(relative_path: str) -> str:
    """
    Get the absolute path to a resource file.
    
    This function handles both development (running from source) and
    production (bundled with PyInstaller) environments.
    
    Args:
        relative_path: Relative path to the resource from project root
        
    Returns:
        Absolute path to the resource
    """
    # Check if running as PyInstaller bundle
    if hasattr(sys, '_MEIPASS'):
        # Running as bundled executable
        base_path = Path(sys._MEIPASS)
    else:
        # Running from source
        base_path = Path(os.path.abspath('.'))
    
    return str(base_path / relative_path)


def get_icon_path(icon_name: str) -> str:
    """
    Get the path to an icon file.
    
    Args:
        icon_name: Name of the icon file (with extension)
        
    Returns:
        Absolute path to the icon
    """
    return get_resource_path(f"resources/icons/{icon_name}")


def resource_exists(relative_path: str) -> bool:
    """
    Check if a resource file exists.
    
    Args:
        relative_path: Relative path to check
        
    Returns:
        True if resource exists
    """
    path = get_resource_path(relative_path)
    return os.path.exists(path)


def get_app_data_dir(app_name: str = "InkshadePDF") -> Path:
    """
    Get the application data directory for storing user data.
    
    Args:
        app_name: Name of the application
        
    Returns:
        Path to the app data directory
    """
    if os.name == 'nt':  # Windows
        base_dir = os.environ.get('APPDATA', os.path.expanduser('~'))
    elif sys.platform == 'darwin':  # macOS
        base_dir = os.path.expanduser('~/Library/Application Support')
    else:  # Linux and others
        base_dir = os.path.expanduser('~/.local/share')
    
    app_dir = Path(base_dir) / app_name
    app_dir.mkdir(parents=True, exist_ok=True)
    
    return app_dir


def get_config_dir(app_name: str = "InkshadePDF") -> Path:
    """
    Get the configuration directory for storing settings.
    
    Args:
        app_name: Name of the application
        
    Returns:
        Path to the config directory
    """
    if os.name == 'nt':  # Windows
        config_dir = get_app_data_dir(app_name) / "config"
    elif sys.platform == 'darwin':  # macOS
        config_dir = Path.home() / "Library" / "Preferences" / app_name
    else:  # Linux
        config_dir = Path.home() / f".config" / app_name
    
    config_dir.mkdir(parents=True, exist_ok=True)
    return config_dir


def get_cache_dir(app_name: str = "InkshadePDF") -> Path:
    """
    Get the cache directory for temporary files.
    
    Args:
        app_name: Name of the application
        
    Returns:
        Path to the cache directory
    """
    if os.name == 'nt':  # Windows
        cache_dir = Path(os.environ.get('LOCALAPPDATA', os.path.expanduser('~'))) / app_name / "cache"
    elif sys.platform == 'darwin':  # macOS
        cache_dir = Path.home() / "Library" / "Caches" / app_name
    else:  # Linux
        cache_dir = Path.home() / ".cache" / app_name
    
    cache_dir.mkdir(parents=True, exist_ok=True)
    return cache_dir


class ResourceManager:
    """
    Centralized resource management for the application.
    """
    
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        if self._initialized:
            return
        
        self._initialized = True
        self.app_name = "InkshadePDF"
        
        # Cache directory paths
        self._app_data_dir: Optional[Path] = None
        self._config_dir: Optional[Path] = None
        self._cache_dir: Optional[Path] = None
    
    @property
    def app_data_dir(self) -> Path:
        """Get the app data directory, creating if needed."""
        if self._app_data_dir is None:
            self._app_data_dir = get_app_data_dir(self.app_name)
        return self._app_data_dir
    
    @property
    def config_dir(self) -> Path:
        """Get the config directory, creating if needed."""
        if self._config_dir is None:
            self._config_dir = get_config_dir(self.app_name)
        return self._config_dir
    
    @property
    def cache_dir(self) -> Path:
        """Get the cache directory, creating if needed."""
        if self._cache_dir is None:
            self._cache_dir = get_cache_dir(self.app_name)
        return self._cache_dir
    
    def get_resource(self, relative_path: str) -> str:
        """Get a resource path."""
        return get_resource_path(relative_path)
    
    def get_icon(self, icon_name: str) -> str:
        """Get an icon path."""
        return get_icon_path(icon_name)