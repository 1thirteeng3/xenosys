# XenoSys Desktop Application

This is the Tauri-based desktop application for XenoSys.

## Installation

```bash
cd desktop
npm install
npm run tauri build
```

## Development

```bash
npm run tauri dev
```

## Architecture

- **Frontend**: React + TypeScript + Vite
- **Backend**: Tauri (Rust) managing sidecar processes
- **Sidecars**: Pre-compiled Gateway (Node) and Core (Python) executables

## Onboarding Flow

1. **Welcome Screen**: Introduction to XenoSys
2. **Mode Selection**: Cloud (API keys) vs Local (Ollama)
3. **Configuration**: Set up selected mode
4. **Ready**: Launch the main application

## Build Sidecars

Before building the Tauri app, compile the sidecars:

```bash
# Gateway (Node.js)
cd nexus/gateway
npm install
npm run build

# Core (Python)
# Use PyInstaller to compile Python to executable
pip install pyinstaller
pyinstaller --onefile --name core nexus/core/__main__.py

# Copy sidecars to desktop/sidecars/
```