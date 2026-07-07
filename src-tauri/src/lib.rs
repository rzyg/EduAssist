use std::path::PathBuf;
use std::process::{Child, Command};
use std::sync::Mutex;
use tauri::Manager;
use tauri::tray::{MouseButton, MouseButtonState, TrayIconBuilder, TrayIconEvent};
use tauri::menu::{MenuBuilder, MenuItemBuilder};
use tauri::image::Image;

#[cfg(windows)]
use std::os::windows::process::CommandExt;

#[cfg(windows)]
const CREATE_NEW_CONSOLE: u32 = 0x00000010;

// ── 后端进程状态 ─────────────────────────────────────────────────────────
struct BackendProcess {
    child: Mutex<Option<Child>>,
    base_dir: PathBuf,
}

// ── 开发模式下弹出一个独立的控制台窗口 ──────────────────────────────────
#[cfg(windows)]
fn with_dev_console(mut cmd: Command) -> Command {
    cmd.creation_flags(CREATE_NEW_CONSOLE);
    cmd
}
#[cfg(not(windows))]
fn with_dev_console(cmd: Command) -> Command {
    cmd
}

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
    let base_dir = &state.base_dir;

    let mut guard = state.child.lock().map_err(|e| e.to_string())?;
    if let Some(ref mut child) = *guard {
        let _ = child.kill();
        let _ = child.wait();
    }

    let child = if tauri::is_dev() {
        let conda_cmd = || -> Result<Child, std::io::Error> {
            let mut c = Command::new("conda");
            c.args(["run", "--no-capture-output", "-n", "eduassist", "python", "-m", "core.main"])
             .current_dir(base_dir);
            with_dev_console(c).spawn()
        };
        conda_cmd().or_else(|_| {
            let mut c = Command::new("python");
            c.args(["-m", "core.main"])
             .current_dir(base_dir);
            with_dev_console(c).spawn()
        }).map_err(|e| format!("启动后端失败 (dev): {}", e))?
    } else {
        Command::new("core/main.exe")
            .current_dir(base_dir)
            .spawn()
            .map_err(|e| format!("启动后端失败: {}", e))?
    };

    *guard = Some(child);
    Ok("后端已启动".to_string())
}

#[tauri::command]
fn kill_backend(state: tauri::State<BackendProcess>) -> Result<String, String> {
    let mut guard = state.child.lock().map_err(|e| e.to_string())?;
    if let Some(ref mut child) = *guard {
        let _ = child.kill();
        let _ = child.wait();
        *guard = None;
    }
    Ok("后端已停止".to_string())
}

#[tauri::command]
fn restart_backend(state: tauri::State<BackendProcess>) -> Result<String, String> {
    kill_backend(state.clone())?;
    std::thread::sleep(std::time::Duration::from_secs(1));
    start_backend(state)
}

// ── 托盘图标 & 窗口关闭 → 隐藏 ──────────────────────────────────────────

fn setup_tray(app: &tauri::App) -> Result<(), Box<dyn std::error::Error>> {
    // 关闭窗口 → 隐藏到托盘
    if let Some(window) = app.get_webview_window("main") {
        let win = window.clone();
        window.on_window_event(move |event| {
            if let tauri::WindowEvent::CloseRequested { api, .. } = event {
                api.prevent_close();
                let _ = win.hide();
            }
        });
    }

    // 托盘菜单
    let quit = MenuItemBuilder::with_id("quit", "退出").build(app)?;
    let menu = MenuBuilder::new(app).item(&quit).build()?;

    // 托盘图标（复用 tauri.conf.json 中配置的图标）
    let icon = app.default_window_icon()
        .cloned()
        .unwrap_or_else(|| Image::new_owned(vec![0u8; 32 * 32 * 4], 32, 32));

    TrayIconBuilder::new()
        .icon(icon)
        .menu(&menu)
        .on_menu_event(|app, event| {
            if event.id.as_ref() == "quit" {
                // 退出前杀死后端
                if let Some(state) = app.try_state::<BackendProcess>() {
                    if let Ok(mut guard) = state.child.lock() {
                        if let Some(ref mut child) = *guard {
                            let _ = child.kill().ok();
                            let _ = child.wait().ok();
                        }
                    }
                }
                app.exit(0);
            }
        })
        .on_tray_icon_event(|tray, event| {
            if let TrayIconEvent::Click {
                button: MouseButton::Left,
                button_state: MouseButtonState::Up,
                ..
            } = event
            {
                if let Some(window) = tray.app_handle().get_webview_window("main") {
                    let _ = window.show();
                    let _ = window.set_focus();
                }
            }
        })
        .build(app)?;

    Ok(())
}

// ── 入口 ────────────────────────────────────────────────────────────────

fn detect_base_dir(app: &tauri::App) -> PathBuf {
    if tauri::is_dev() {
        std::env::current_dir()
            .ok()
            .as_ref()
            .and_then(|d| d.parent().map(|p| p.to_path_buf()))
            .unwrap_or_else(|| PathBuf::from(".."))
    } else {
        app.path().resource_dir().unwrap_or_else(|_| PathBuf::from("."))
    }
}

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    tauri::Builder::default()
        .plugin(tauri_plugin_opener::init())
        .invoke_handler(tauri::generate_handler![
            greet,
            get_mode,
            start_backend,
            kill_backend,
            restart_backend
        ])
        .setup(|app| {
            let base_dir = detect_base_dir(app);
            app.manage(BackendProcess {
                child: Mutex::new(None),
                base_dir,
            });

            // 设置托盘
            if let Err(e) = setup_tray(app) {
                eprintln!("托盘初始化失败: {}", e);
            }

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
