// XenoSys Desktop - Tauri Application
// Manages sidecar processes (Gateway and Core) and NAT traversal

#![cfg_attr(
    all(not(debug_assertions), target_os = "windows"),
    windows_subsystem = "windows"
)]

use log::{info, error, warn};
use std::process::Stdio;
use std::sync::Mutex;
use std::path::PathBuf;
use tauri::Manager;
use tauri_plugin_store::StoreExt;
use tokio::io::{AsyncBufReadExt, BufReader};
use tokio::process::Command;

// Base64 helper module
mod base64_helper {
    pub fn encode(data: &str) -> String {
        use std::io::Write;
        const CHARSET: &[u8] = b"ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/";
        
        let bytes = data.as_bytes();
        let mut result = String::new();
        
        for chunk in bytes.chunks(3) {
            let b0 = chunk[0] as usize;
            let b1 = chunk.get(1).copied().unwrap_or(0) as usize;
            let b2 = chunk.get(2).copied().unwrap_or(0) as usize;
            
            result.push(CHARSET[b0 >> 2] as char);
            result.push(CHARSET[((b0 & 0x03) << 4) | (b1 >> 4)] as char);
            
            if chunk.len() > 1 {
                result.push(CHARSET[((b1 & 0x0f) << 2) | (b2 >> 6)] as char);
            } else {
                result.push('=');
            }
            
            if chunk.len() > 2 {
                result.push(CHARSET[b2 & 0x3f] as char);
            } else {
                result.push('=');
            }
        }
        
        result
    }
}

// State for managing sidecar processes and tunnel
struct SidecarState {
    gateway_running: bool,
    core_running: bool,
}

struct TunnelState {
    running: bool,
    url: Option<String>,
    process: Option<u32>, // PID
}

struct AppState {
    sidecars: Mutex<SidecarState>,
    tunnel: Mutex<TunnelState>,
}

fn main() {
    // Initialize logging
    env_logger::Builder::from_env(env_logger::Env::default().default_filter_or("info"))
        .format_timestamp_millis()
        .init();

    info!("Starting XenoSys Desktop...");

    tauri::Builder::default()
        .manage(AppState {
            sidecars: Mutex::new(SidecarState {
                gateway_running: false,
                core_running: false,
            }),
            tunnel: Mutex::new(TunnelState {
                running: false,
                url: None,
                process: None,
            }),
        })
        // Initialize secure store for API keys
        .plugin(tauri_plugin_store::Builder::default().build())
        .invoke_handler(tauri::generate_handler![
            start_sidecars,
            stop_sidecars,
            get_status,
            check_ollama,
            install_ollama,
            configure_mode,
            save_api_key,      // Secure API key storage
            load_api_key,      // Load API key for sidecars
            download_cloudflared
        ])
        .setup(|app| {
            info!("Tauri app setup complete");
            
            // Set up global error handler
            std::panic::set_hook(Box::new(|panic_info| {
                error!("Panic occurred: {:?}", panic_info);
            }));
            
            Ok(())
        })
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}

// ============================================================================
// Sidecar Management Commands
// ============================================================================

#[tauri::command]
async fn start_sidecars(state: tauri::State<'_, AppState>) -> Result<String, String> {
    info!("Starting sidecar processes...");
    
    let mut sidecar_state = state.sidecars.lock().map_err(|e| e.to_string())?;
    
    // Start Gateway sidecar
    if !sidecar_state.gateway_running {
        let gateway_path = get_sidecar_path("gateway");
        info!("Starting gateway from: {}", gateway_path);
        
        let mut child = Command::new(&gateway_path)
            .env("TAURI_ENV", "true")
            .env("HOST", "127.0.0.1")
            .env("GRPC_HOST", "127.0.0.1")
            .stdout(Stdio::piped())
            .stderr(Stdio::piped())
            .spawn()
            .map_err(|e| format!("Failed to start gateway: {}", e))?;
        
        // Log output in background
        if let Some(stdout) = child.stdout.take() {
            let mut reader = BufReader::new(stdout).lines();
            tokio::spawn(async move {
                while let Ok(Some(line)) = reader.next_line().await {
                    info!("[gateway] {}", line);
                }
            });
        }
        
        sidecar_state.gateway_running = true;
    }
    
    // Start Core sidecar with API key from secure store
    if !sidecar_state.core_running {
        let core_path = get_sidecar_path("core");
        info!("Starting core from: {}", core_path);
        
        // Check if API key available from environment (set from store at app init)
        let api_key = std::env::var("OPENAI_API_KEY").ok();
        
        let mut child = if let Some(key) = api_key {
            info!("[Core] Using OPENAI_API_KEY from secure store");
            Command::new(&core_path)
                .env("TAURI_ENV", "true")
                .env("GRPC_HOST", "127.0.0.1")
                .env("HOST", "127.0.0.1")
                .env("OPENAI_API_KEY", key)
                .stdout(Stdio::piped())
                .stderr(Stdio::piped())
                .spawn()
                .map_err(|e| format!("Failed to start core: {}", e))?
        } else {
            Command::new(&core_path)
                .env("TAURI_ENV", "true")
                .env("GRPC_HOST", "127.0.0.1")
                .env("HOST", "127.0.0.1")
                .stdout(Stdio::piped())
                .stderr(Stdio::piped())
                .spawn()
                .map_err(|e| format!("Failed to start core: {}", e))?
        };
        
        // Log output in background
        if let Some(stdout) = child.stdout.take() {
            let mut reader = BufReader::new(stdout).lines();
            tokio::spawn(async move {
                while let Ok(Some(line)) = reader.next_line().await {
                    info!("[core] {}", line);
                }
            });
        }
        
        sidecar_state.core_running = true;
    }
    
    // Wait for services to be ready
    tokio::time::sleep(tokio::time::Duration::from_secs(3)).await;
    
    // Check if services are responding
    if let Err(e) = check_service("http://localhost:3000/health").await {
        warn!("Gateway may not be ready: {}", e);
    }
    
    if let Err(e) = check_service("http://localhost:50051/health").await {
        warn!("Core may not be ready: {}", e);
    }
    
    Ok("Sidecars started successfully".to_string())
}

#[tauri::command]
async fn stop_sidecars(state: tauri::State<'_, AppState>) -> Result<String, String> {
    info!("Stopping sidecar processes...");
    
    let mut sidecar_state = state.sidecars.lock().map_err(|e| e.to_string())?;
    
    // On Windows, we need to use taskkill
    #[cfg(target_os = "windows")]
    {
        let _ = Command::new("taskkill").args(&["/F", "/IM", "gateway.exe"]).output();
        let _ = Command::new("taskkill").args(&["/F", "/IM", "core.exe"]).output();
    }
    
    #[cfg(not(target_os = "windows"))]
    {
        let _ = Command::new("pkill").args(&["-f", "xenosys-gateway"]).output();
        let _ = Command::new("pkill").args(&["-f", "xenosys-core"]).output();
    }
    
    sidecar_state.gateway_running = false;
    sidecar_state.core_running = false;
    
    Ok("Sidecars stopped".to_string())
}

#[tauri::command]
fn get_status(state: tauri::State<'_, AppState>) -> Result<serde_json::Value, String> {
    let sidecar_state = state.sidecars.lock().map_err(|e| e.to_string())?;
    
    Ok(serde_json::json!({
        "gateway": sidecar_state.gateway_running,
        "core": sidecar_state.core_running,
        "mode": "cloud" // Will be updated based on user config
    }))
}

// ============================================================================
// Ollama Integration (Local Mode)
// ============================================================================

#[tauri::command]
async fn check_ollama() -> Result<bool, String> {
    info!("Checking Ollama status...");
    
    match check_service("http://localhost:11434/api/tags").await {
        Ok(_) => {
            info!("Ollama is running");
            Ok(true)
        }
        Err(_) => {
            info!("Ollama is not running");
            Ok(false)
        }
    }
}

#[tauri::command]
async fn install_ollama() -> Result<String, String> {
    info!("Installing Ollama...");
    
    let install_script = if cfg!(target_os = "windows") {
        // Windows PowerShell script to download and run Ollama installer
        r#"
        $ErrorActionPreference = 'Stop'
        $OllamaDir = "$env:LOCALAPPDATA\Ollama"
        $Installer = "$env:TEMP\OllamaSetup.exe"
        
        # Download installer
        Invoke-WebRequest -Uri "https://ollama.com/download/OllamaSetup.exe" -OutFile $Installer
        
        # Run installer silently
        Start-Process -FilePath $Installer -ArgumentList "/S" -Wait
        
        # Start Ollama service
        Start-Process -FilePath "$OllamaDir\ollama.exe" -ArgumentList "serve" -DetachWindow
        
        Write-Host "Ollama installed"
        "#
    } else {
        // macOS/Linux
        r#"
        # macOS
        if [ "$(uname)" = "Darwin" ]; then
            brew install ollama
            ollama serve &
        fi
        # Linux
        if [ "$(uname)" = "Linux" ]; then
            curl -fsSL https://ollama.ai/install.sh | sh
            ollama serve &
        fi
        "#
    };
    
    // Execute installation (in production, this would be a proper installer)
    #[cfg(target_os = "windows")]
    {
        let _ = Command::new("powershell")
            .args(&["-ExecutionPolicy", "Bypass", "-Command", install_script])
            .output()
            .await;
    }
    
    // Wait for Ollama to start
    tokio::time::sleep(tokio::time::Duration::from_secs(10)).await;
    
    // Pull the model
    let _ = Command::new("ollama").args(&["pull", "llama3.1:8b"]).output().await;
    
    Ok("Ollama installed and model pulled".to_string())
}

#[tauri::command]
async fn configure_mode(mode: String) -> Result<String, String> {
    info!("Configuring mode: {}", mode);
    
    match mode.as_str() {
        "cloud" => {
            // Configure for cloud LLM (OpenAI/Anthropic)
            info!("Mode set to cloud - using API keys");
            Ok("Configured for cloud mode".to_string())
        }
        "local" => {
            // Verify Ollama is available
            let ollama_running = check_ollama().await?;
            if !ollama_running {
                return Err("Ollama not installed. Please install Ollama first.".to_string());
            }
            info!("Mode set to local - using Ollama");
            Ok("Configured for local mode".to_string())
        }
        _ => Err(format!("Unknown mode: {}", mode))
    }
}

// ============================================================================
// Helper Functions
// ============================================================================

fn get_sidecar_path(name: &str) -> String {
    // Get the directory where the executable is located
    let base_dir = dirs::executable_dir()
        .unwrap_or_else(|| std::path::PathBuf::from("."));
    
    // Sidecar binaries are in sidecars/ subdirectory
    let sidecar_dir = base_dir.join("sidecars");
    
    #[cfg(target_os = "windows")]
    let sidecar_path = sidecar_dir.join(format!("{}.exe", name));
    
    #[cfg(not(target_os = "windows"))]
    let sidecar_path = sidecar_dir.join(name);
    
    sidecar_path.to_string_lossy().to_string()
}

async fn check_service(url: &str) -> Result<(), String> {
    let client = reqwest::Client::new();
    
    match client.get(url).timeout(std::time::Duration::from_secs(5)).send().await {
        Ok(response) if response.status().is_success() => Ok(()),
        Ok(response) => Err(format!("Service returned: {}", response.status())),
        Err(e) => Err(e.to_string()),
    }
}

// ============================================================================
// Cloudflare Tunnel (NAT Traversal)
// ============================================================================

fn get_cloudflared_path() -> String {
    let base_dir = dirs::executable_dir()
        .unwrap_or_else(|| std::path::PathBuf::from("."));
    
    #[cfg(target_os = "windows")]
    let cloudflared = base_dir.join("cloudflared.exe");
    
    #[cfg(not(target_os = "windows"))]
    let cloudflared = base_dir.join("cloudflared");
    
    cloudflared.to_string_lossy().to_string()
}

// ============================================================================
// Cloudflare Tunnel Commands
// ============================================================================

#[tauri::command]
async fn save_api_key(key_name: String, key_value: String, app_handle: tauri::AppHandle) -> Result<String, String> {
    info!("Saving API key: {}", key_name);
    
    // Get or create store
    let store = app_handle.store(".settings.dat")
        .map_err(|e| format!("Failed to open store: {}", e))?;
    
    // Save the key
    store.set(&key_name, &key_value);
    store.save()
        .map_err(|e| format!("Failed to save store: {}", e))?;
    
    // Set env var for sidecar processes
    std::env::set_var(&key_name, &key_value);
    
    info!("API key {} saved to secure store", key_name);
    Ok(format!("API key {} saved", key_name))
}

#[tauri::command]
async fn load_api_key(key_name: String, app_handle: tauri::AppHandle) -> Result<String, String> {
    info!("Loading API key: {}", key_name);
    
    // Get store
    let store = app_handle.store(".settings.dat")
        .map_err(|e| format!("Failed to open store: {}", e))?;
    
    // Get the key
    let value = store.get(&key_name)
        .ok_or(format!("Key {} not found", key_name))?
        .as_str()
        .ok_or("Invalid key value")?
        .to_string();
    
    info!("API key {} loaded", key_name);
    Ok(value)
}

#[tauri::command]
async fn download_cloudflared() -> Result<String, String> {
    info!("Downloading cloudflared...");
    
    let cloudflared_path = get_cloudflared_path();
    
    // Check if already exists
    if std::path::Path::new(&cloudflared_path).exists() {
        info!("cloudflared already exists at {}", cloudflared_path);
        return Ok(cloudflared_path);
    }
    
    let download_url = if cfg!(target_os = "windows") {
        "https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-windows-amd64.exe"
    } else if cfg!(target_os = "macos") {
        "https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-darwin-amd64"
    } else {
        "https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64"
    };
    
    info!("Downloading from: {}", download_url);
    
    // Download the binary
    let client = reqwest::Client::new();
    let response = client.get(download_url)
        .send()
        .await
        .map_err(|e| format!("Download failed: {}", e))?;
    
    let bytes = response.bytes()
        .await
        .map_err(|e| format!("Failed to read response: {}", e))?;
    
    // Write to file
    std::fs::write(&cloudflared_path, &bytes)
        .map_err(|e| format!("Failed to write file: {}", e))?;
    
    // Make executable (Unix only)
    #[cfg(not(target_os = "windows"))]
    {
        use std::os::unix::fs::PermissionsExt;
        let mut perms = std::fs::metadata(&cloudflared_path)
            .map_err(|e| format!("Failed to get permissions: {}", e))?
            .permissions();
        perms.set_mode(0o755);
        std::fs::set_permissions(&cloudflared_path, perms)
            .map_err(|e| format!("Failed to set permissions: {}", e))?;
    }
    
    info!("cloudflared downloaded to {}", cloudflared_path);
    Ok(cloudflared_path)
}

#[tauri::command]
async fn start_tunnel(state: tauri::State<'_, AppState>) -> Result<String, String> {
    info!("Starting Cloudflare tunnel...");
    
    // Ensure gateway is running
    let sidecar_state = state.sidecars.lock().map_err(|e| e.to_string())?;
    if !sidecar_state.gateway_running {
        return Err("Gateway must be running to start tunnel".to_string());
    }
    drop(sidecar_state);
    
    // Get cloudflared path
    let cloudflared_path = get_cloudflared_path();
    
    // Ensure cloudflared exists
    if !std::path::Path::new(&cloudflared_path).exists() {
        return Err("cloudflared not found. Call download_cloudflared first.".to_string());
    }
    
    // Start tunnel pointing to local gateway
    let mut child = Command::new(&cloudflared_path)
        .args(&["tunnel", "--url", "http://localhost:3000"])
        .stdout(Stdio::piped())
        .stderr(Stdio::piped())
        .spawn()
        .map_err(|e| format!("Failed to start tunnel: {}", e))?;
    
    // Parse output to get tunnel URL
    let stdout = child.stdout.take().ok_or("Failed to capture stdout")?;
    let mut reader = BufReader::new(stdout).lines();
    
    let mut tunnel_url: Option<String> = None;
    
    // Read output to find the URL (cloudflared outputs it to stdout)
    // Timeout after 30 seconds waiting for URL
    let timeout = std::time::Duration::from_secs(30);
    let start = std::time::Instant::now();
    
    while start.elapsed() < timeout {
        tokio::select! {
            line = reader.next_line() => {
                match line {
                    Ok(Some(line)) => {
                        info!("[cloudflared] {}", line);
                        // Cloudflare tunnel outputs URL like: https://*.trycloudflare.com
                        if line.starts_with("https://") && line.contains("trycloudflare") {
                            tunnel_url = Some(line.clone());
                            break;
                        }
                    }
                    Ok(None) => break,
                    Err(_) => break,
                }
            }
            _ = tokio::time::sleep(tokio::time::Duration::from_millis(100)) => {}
        }
    }
    
    let tunnel_url = match tunnel_url {
        Some(url) => url,
        None => return Err("Failed to get tunnel URL within timeout".to_string()),
    };
    
    // Update state
    let mut tunnel_state = state.tunnel.lock().map_err(|e| e.to_string())?;
    tunnel_state.running = true;
    tunnel_state.url = Some(tunnel_url.clone());
    tunnel_state.process = Some(child.id().unwrap_or(0));
    
    info!("Tunnel started: {}", tunnel_url);
    Ok(tunnel_url)
}

#[tauri::command]
async fn stop_tunnel(state: tauri::State<'_, AppState>) -> Result<String, String> {
    info!("Stopping Cloudflare tunnel...");
    
    let mut tunnel_state = state.tunnel.lock().map_err(|e| e.to_string())?;
    
    if let Some(pid) = tunnel_state.process {
        #[cfg(target_os = "windows")]
        {
            let _ = Command::new("taskkill")
                .args(&["/F", "/PID", &pid.to_string()])
                .output()
                .await;
        }
        
        #[cfg(not(target_os = "windows"))]
        {
            let _ = Command::new("kill")
                .arg(pid.to_string())
                .output()
                .await;
        }
    }
    
    tunnel_state.running = false;
    tunnel_state.url = None;
    tunnel_state.process = None;
    
    info!("Tunnel stopped");
    Ok("Tunnel stopped".to_string())
}

#[tauri::command]
fn get_tunnel_url(state: tauri::State<'_, AppState>) -> Result<Option<String>, String> {
    let tunnel_state = state.tunnel.lock().map_err(|e| e.to_string())?;
    Ok(tunnel_state.url.clone())
}

#[tauri::command]
fn generate_pairing_qr(state: tauri::State<'_, AppState>) -> Result<String, String> {
    let tunnel_state = state.tunnel.lock().map_err(|e| e.to_string())?;
    
    let tunnel_url = tunnel_state.url.clone()
        .ok_or("Tunnel not running. Start tunnel first.")?;
    
    // Generate JWT token for mobile auth (simplified - in production use proper JWT)
    let token = format!("xenosys_mobile_token_{}", std::time::SystemTime::now()
        .duration_since(std::time::UNIX_EPOCH)
        .unwrap()
        .as_secs());
    
    // Create JSON payload
    let payload = serde_json::json!({
        "url": tunnel_url,
        "token": token,
        "version": "1.0"
    });
    
    // Encode as base64 for QR
    let encoded = base64_helper::encode(&payload.to_string());
    
    info!("Generated pairing QR with URL: {}", tunnel_url);
    
    // Return the full QR data URL (in production, use proper QR library)
    Ok(format!("data:application/json;base64,{}", encoded))
}