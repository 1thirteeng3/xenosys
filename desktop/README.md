# XenoSys Desktop Application

This is the Tauri-based desktop application for XenoSys.

## Installation Versions

### Desktop Standard (~200MB)
- All modules and features except local LLM
- Uses API mode (OpenAI, Anthropic, Google) by default
- Can add local LLM (Ollama) later via settings panel

### Desktop Plus (~2GB)
- All modules including local LLM (Ollama)
- Full offline inference capability

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

## Installation Flow

### Step 1: Platform Selection
Download the installer for your platform:
- Linux: `.deb`, `.AppImage`
- Windows: `.exe` installer
- Mac: `.dmg` or `.app`

### Step 2: Initial Settings Panel
After installation, the Settings Panel wizard appears:

1. **Basic Configuration**: Agent name, Instance ID
2. **LLM Provider Selection**:
   - **API Mode** (default): Enter API key for OpenAI/Anthropic/Google
   - **Local Mode**: Will install Ollama on-demand
3. **Integrations**: Telegram, Discord, MCP Tools
4. **Security**: Encryption, read-only mode

### Step 3: On-Demand Modules
If you select Local LLM mode, a module installer will download and configure Ollama.

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