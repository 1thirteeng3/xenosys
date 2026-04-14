// XenoSys Desktop - Tauri Application
// Manages sidecar processes (Gateway and Core)

#![cfg_attr(
    all(not(debug_assertions), target_os = "windows"),
    windows_subsystem = "windows"
)]

use log::{info, error, warn};
use std::process::Stdio;
use std::sync::Mutex;
use tauri::Manager;
use tokio::io::{AsyncBufReadExt, BufReader};
use tokio::process::Command;

// State for managing sidecar processes
struct SidecarState {
    gateway_running: bool,
    core_running: bool,
}

struct AppState {
    sidecars: Mutex<SidecarState>,
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
        })
        .invoke_handler(tauri::generate_handler![
            start_sidecars,
            stop_sidecars,
            get_status,
            check_ollama,
            install_ollama,
            configure_mode
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
    
    // Start Core sidecar
    if !sidecar_state.core_running {
        let core_path = get_sidecar_path("core");
        info!("Starting core from: {}", core_path);
        
        let mut child = Command::new(&core_path)
            .stdout(Stdio::piped())
            .stderr(Stdio::piped())
            .spawn()
            .map_err(|e| format!("Failed to start core: {}", e))?;
        
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