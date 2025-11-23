from dataclasses import dataclass


@dataclass
class ThemeColors:
    """Color definitions for a theme."""
    # Background colors
    bg_primary: str
    bg_secondary: str
    bg_tertiary: str
    
    # Text colors
    text_primary: str
    text_secondary: str
    text_muted: str
    
    # Accent colors
    accent_primary: str
    accent_hover: str
    accent_active: str
    
    # Border colors
    border_primary: str
    border_secondary: str
    
    # Special colors
    selection: str
    error: str
    warning: str
    success: str