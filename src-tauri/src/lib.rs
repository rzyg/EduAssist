use std::process::{Child, Command};
use std::sync::Mutex;
use tauri::Manager;

// ── 后端进程状态 ─────────────────────────────────────────────────────────
struct BackendProcess(Mutex<Option<Child>>);

// ── Tauri 命令 ──────────────────────────────────────────────────────────

#[tauri::command]
fn get_mode() -> String {
    if tauri::is_dev() {
        "tauri-dev".to_string()
    } else {
        "normal".to_string()
    }
}

#[tauri::command]
fn start_backend(state: tauri::State<BackendProcess>) -> Result<String, String> {
    // 杀死残留进程
    let mut guard = state.0.lock().map_err(|e| e.to_string())?;
    if let Some(ref mut child) = *guard {
        let _ = child.kill();
        let _ = child.wait();
    }

    let child = if tauri::is_dev() {
        // ── tauri dev 模式：走 conda 虚拟环境 ──
        let cmd = "conda";
        let args = ["run", "-n", "eduassist", "python", "core/main.py"];
        // 如果 conda 不可用，回退到直接用 python
        Command::new(cmd)
            .args(&args)
            .spawn()
            .or_else(|_| {
                Command::new("python")
                    .arg("core/main.py")
                    .spawn()
            })
            .map_err(|e| format!("启动后端失败 (dev): {}", e))?
    } else {
        // ── 正常模式：直接跑打包的 exe ──
        Command::new("core/main.exe")
            .spawn()
            .map_err(|e| format!("启动后端失败: {}", e))?
    };

    *guard = Some(child);
    Ok("后端已启动".to_string())
}

#[tauri::command]
fn kill_backend(state: tauri::State<BackendProcess>) -> Result<String, String> {
    let mut guard = state.0.lock().map_err(|e| e.to_string())?;
    if let Some(ref mut child) = *guard {
        let _ = child.kill();
        let _ = child.wait();
        *guard = None;
    }
    Ok("后端已停止".to_string())
}

#[tauri::command]
fn restart_backend(state: tauri::State<BackendProcess>) -> Result<String, String> {
    kill_backend(state)?;
    // 等一秒让端口释放
    std::thread::sleep(std::time::Duration::from_secs(1));
    start_backend(state)
}

// ── 入口 ────────────────────────────────────────────────────────────────

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    tauri::Builder::default()
        .plugin(tauri_plugin_opener::init())
        .manage(BackendProcess(Mutex::new(None)))
        .invoke_handler(tauri::generate_handler![
            greet,
            get_mode,
            start_backend,
            kill_backend,
            restart_backend
        ])
        .setup(|app| {
            // 应用启动后延迟 2 秒自动拉起后端
            let handle = app.handle().clone();
            std::thread::spawn(move || {
                std::thread::sleep(std::time::Duration::from_secs(2));
                let state = handle.state::<BackendProcess>();
                let _ = start_backend(state);
            });
            Ok(())
        })
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}

// ── 原 greet 命令（保留）───────────────────────────────────────────────
#[tauri::command]
fn greet(name: &str) -> String {
    format!("Hello, {}! You've been greeted from Rust!", name)
}
