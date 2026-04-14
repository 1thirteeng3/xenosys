#!/usr/bin/env python3
"""
XenoSys Core PyInstaller Build Script
------------------------------------------
Creates a bundled executable with all AI dependencies.

Usage:
    python build_core.py

Output:
    dist/xenosys-core-bin/ (onedir mode for easy extraction)
"""

import PyInstaller.__main__

# Hidden imports for AI/ML libraries that PyInstaller misses
HIDDEN_IMPORTS = [
    'dspy',
    'pydantic', 
    'mcp',
    'httpx',
    'tenacity',
    'litellm',
    'opentelemetry',
    'google',
    'anthropic',
    'openai',
]

# Collect all submodules and data from these packages
COLLECT_ALL = [
    'dspy',
    'mcp', 
    'pydantic',
    'pydantic_core',
    'httpx',
    'requests',
]

PyInstaller.__main__.run([
    'nexus/core/app.py',
    '--name=xenosys-core-bin',
    '--onedir',  # Use onedir, not onefile - better for AI libraries
    '--noconfirm',
    '--clean',
    # Add hidden imports
    *[f'--hidden-import={mod}' for mod in HIDDEN_IMPORTS],
    # Force collection of all submodules and data
    *[f'--collect-all={mod}' for mod in COLLECT_ALL],
    # Additional options for AI applications
    '--add-binary=nexus/core/proto:nexus/core/proto',  # Include proto files
    '--exclude-module=pytest',  # Exclude test dependencies
    '--exclude-module=nose',
    # Console script (no window on Windows)
    '--console',
])