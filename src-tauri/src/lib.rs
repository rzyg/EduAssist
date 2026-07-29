use std::path::PathBuf;
use std::process::{Child, Command};
use std::sync::Mutex;
use tauri::Manager;
use tauri::tray::{MouseButton, MouseButtonState, TrayIconBuilder, TrayIconEvent};
use tauri::menu::{MenuBuilder, MenuItemBuilder};
use tauri::image::Image;
use tracing_subscriber::layer::SubscriberExt;
use tracing_subscriber::Layer;
use tracing_subscriber::util::SubscriberInitExt;

use std::time::{SystemTime, UNIX_EPOCH};

#[cfg(windows)]
use std::os::windows::process::CommandExt;

#[cfg(windows)]
const CREATE_NEW_CONSOLE: u32 = 0x00000010;

/// 不创建控制台窗口（用于生产环境的子进程）
#[cfg(windows)]
const CREATE_NO_WINDOW: u32 = 0x08000000;

fn generate_token() -> String {
    let start = SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .unwrap_or_default()
        .as_nanos();
    format!("{:x}", start)
}

// ── 后端进程状态 ─────────────────────────────────────────────────────────
struct BackendProcess {
    child: Mutex<Option<Child>>,
    base_dir: PathBuf,
    token: String,
}

// ── 开发模式下弹出一个独立的控制台窗口 ──────────────────────────────────
#[cfg(windows)]
fn with_dev_console(cmd: &mut Command) -> &mut Command {
    cmd.creation_flags(CREATE_NEW_CONSOLE);
    cmd
}
#[cfg(not(windows))]
fn with_dev_console(cmd: &mut Command) -> &mut Command {
    cmd
}

/// 抑制控制台窗口（用于生产环境子进程）
#[cfg(windows)]
fn with_no_window(cmd: &mut Command) -> &mut Command {
    cmd.creation_flags(CREATE_NO_WINDOW);
    cmd
}
#[cfg(not(windows))]
fn with_no_window(cmd: &mut Command) -> &mut Command {
    cmd
}

// ── Tauri 命令 ──────────────────────────────────────────────────────────

/// 强制杀死进程树（Windows 用 taskkill，其他平台用 kill）
fn kill_process_tree(child: &mut Child) {
    #[cfg(windows)]
    {
        let pid = child.id();
        let _ = Command::new("taskkill")
            .args(["/F", "/T", "/PID", &pid.to_string()])
            .creation_flags(CREATE_NO_WINDOW)
            .spawn()
            .and_then(|mut c| c.wait());
    }
    #[cfg(not(windows))]
    {
        let _ = child.kill();
        let _ = child.wait();
    }
}

#[tauri::command]
fn get_token(state: tauri::State<BackendProcess>) -> String {
    state.token.clone()
}

#[tauri::command]
fn get_dev_mode(state: tauri::State<BackendProcess>) -> bool {
    let config_path = state.base_dir.join("config.yaml");
    if let Ok(content) = std::fs::read_to_string(&config_path) {
        content.lines().any(|l| {
            let t = l.trim();
            t.starts_with("dev_mode:") && t.trim_start_matches("dev_mode:").trim() == "true"
        })
    } else {
        false
    }
}

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

    // 判断开发者模式 → 不传递 auth token
    let is_dev_mode = {
        let config_path = base_dir.join("config.yaml");
        if let Ok(content) = std::fs::read_to_string(&config_path) {
            content.lines().any(|l| {
                let t = l.trim();
                t.starts_with("dev_mode:") && t.trim_start_matches("dev_mode:").trim() == "true"
            })
        } else {
            false
        }
    };
    let token = if is_dev_mode { "" } else { &state.token };

    let mut guard = state.child.lock().map_err(|e| e.to_string())?;
    if let Some(ref mut child) = *guard {
        kill_process_tree(child);
        let _ = child.wait();
    }

    let child = if tauri::is_dev() {
        tracing::info!("开发环境，项目根目录: {:?}", base_dir);

        let conda_result = with_dev_console(
            Command::new("conda")
                .args(["run", "--no-capture-output", "-n", "eduassist", "python", "-m", "core.main"])
                .current_dir(base_dir)
                .env("EDUASSIST_BASE", base_dir.as_os_str())
                .env("EDUASSIST_TOKEN", token),
        )
        .spawn();

        conda_result.or_else(|_| {
            println!("⚠️ conda 启动失败，尝试直接使用 python");
            with_no_window(
                Command::new(base_dir.join(".venv/Scripts/python.exe"))
                    .args(["-m", "core.main"])
                    .current_dir(base_dir)
                    .env("EDUASSIST_BASE", base_dir.as_os_str())
                    .env("EDUASSIST_TOKEN", token),
            )
            .spawn()
        }).map_err(|e| format!("启动后端失败 (dev): {}", e))?
    } else {
        println!("📍 生产环境，安装目录: {:?}", base_dir);

        let exe_path = base_dir.join("core/main.exe");
        if !exe_path.exists() {
            return Err(format!("后端程序不存在: {:?}", exe_path));
        }

        with_no_window(
            Command::new(exe_path)
                .current_dir(base_dir)
                .env("EDUASSIST_BASE", base_dir.as_os_str())
                .env("EDUASSIST_TOKEN", token),
        )
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
        kill_process_tree(child);
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

#[tauri::command]
fn get_app_version(app: tauri::AppHandle) -> String {
    app.config().version.clone().unwrap_or_default()
}

#[tauri::command]
async fn download_and_install(
    url: String,
    state: tauri::State<'_, BackendProcess>,
    app: tauri::AppHandle,
) -> Result<String, String> {
    let tmp_dir = std::env::temp_dir().join("eduassist_update.exe");
    tracing::info!("下载更新包: {} → {:?}", url, tmp_dir);

    let resp = ureq::get(&url)
        .call()
        .map_err(|e| format!("下载失败: {}", e))?;

    let body = resp
        .into_body()
        .read_to_vec()
        .map_err(|e| format!("读取响应失败: {}", e))?;

    std::fs::write(&tmp_dir, &body).map_err(|e| format!("写入文件失败: {}", e))?;

    let _ = Command::new(&tmp_dir)
        .arg("/S")
        .spawn()
        .map_err(|e| format!("启动安装包失败: {}", e))?;

    let mut guard = state.child.lock().map_err(|e| e.to_string())?;
    if let Some(ref mut child) = *guard {
        kill_process_tree(child);
        let _ = child.wait();
    }

    app.exit(0);
    Ok("更新中…".to_string())
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
                            kill_process_tree(child);
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

// ── 从 config.yaml 读取后端地址 ──────────────────────────────────────────
#[tauri::command]
fn get_backend_url(state: tauri::State<BackendProcess>) -> Result<String, String> {
    let base_dir = &state.base_dir;
    let config_path = base_dir.join("config.yaml");

    if !config_path.exists() {
        return Ok("http://127.0.0.1:8000".to_string());
    }

    let content = std::fs::read_to_string(&config_path).map_err(|e| e.to_string())?;
    let mut host = "127.0.0.1";
    let mut port = "8000";
    let mut in_server = false;

    for line in content.lines() {
        let trimmed = line.trim();
        if trimmed == "server:" {
            in_server = true;
            continue;
        }
        if in_server {
            if trimmed.starts_with("host:") {
                host = trimmed.trim_start_matches("host:").trim().trim_matches('"');
                // 如果是 localhost，转成 127.0.0.1
                if host == "localhost" { host = "127.0.0.1"; }
            } else if trimmed.starts_with("port:") {
                port = trimmed.trim_start_matches("port:").trim().trim_matches('"');
            } else if trimmed.contains(':') && !trimmed.starts_with('#') {
                // 遇到下一个顶层 key，退出 server 段
                in_server = false;
            }
        }
    }

    Ok(format!("http://{}:{}", host, port))
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

// ── 日志初始化 ──────────────────────────────────────────────────────────

fn get_log_dir() -> PathBuf {
    if tauri::is_dev() {
        std::env::current_dir()
            .unwrap_or_default()
            .parent()
            .unwrap_or(&std::env::current_dir().unwrap_or_default())
            .join("logs/tauri")
    } else {
        std::env::current_exe()
            .unwrap_or_default()
            .parent()
            .unwrap_or(&PathBuf::from("."))
            .join("logs/tauri")
    }
}

fn cleanup_old_logs(log_dir: &PathBuf) {
    let Ok(entries) = std::fs::read_dir(log_dir) else { return };
    let cutoff = std::time::SystemTime::now()
        - std::time::Duration::from_secs(7 * 24 * 3600);

    for entry in entries.flatten() {
        let path = entry.path();
        if let Ok(metadata) = entry.metadata() {
            if let Ok(modified) = metadata.modified() {
                if modified < cutoff {
                    let _ = std::fs::remove_file(&path);
                }
            }
        }
    }
}

fn setup_logging() -> tracing_appender::non_blocking::WorkerGuard {
    let log_dir = get_log_dir();
    std::fs::create_dir_all(&log_dir).ok();

    cleanup_old_logs(&log_dir);

    let file_appender = tracing_appender::rolling::RollingFileAppender::builder()
        .rotation(tracing_appender::rolling::Rotation::DAILY)
        .filename_prefix("tauri")
        .filename_suffix("log")
        .build(&log_dir)
        .expect("failed to create file appender");
    let (non_blocking, guard) = tracing_appender::non_blocking(file_appender);

    let filter = tracing_subscriber::EnvFilter::try_from_default_env()
        .unwrap_or_else(|_| "eduassist_lib=info".into());

    tracing_subscriber::registry()
        .with(
            tracing_subscriber::fmt::layer()
                .with_target(true)
                .with_thread_ids(true)
                .with_line_number(true)
                .with_ansi(false)
                .with_writer(non_blocking)
                .with_filter(filter.clone()),
        )
        .with(
            tracing_subscriber::fmt::layer()
                .with_target(true)
                .with_line_number(true)
                .with_ansi(true)
                .with_filter(filter),
        )
        .init();

    guard
}

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    let _guard = setup_logging();
    tracing::info!("Tauri 应用启动，日志目录: {:?}", get_log_dir());
    let app = tauri::Builder::default()
        .plugin(tauri_plugin_opener::init())
        .invoke_handler(tauri::generate_handler![
            greet,
            get_mode,
            get_token,
            get_dev_mode,
            start_backend,
            kill_backend,
            restart_backend,
            get_backend_url,
            get_app_version,
            download_and_install
        ])
        .setup(|app| {
            let base_dir = detect_base_dir(app);
            let token = generate_token();
            app.manage(BackendProcess {
                child: Mutex::new(None),
                base_dir,
                token,
            });

            // 设置托盘
            if let Err(e) = setup_tray(app) {
                eprintln!("托盘初始化失败: {}", e);
            };
            Ok(())
        })
        .build(tauri::generate_context!())
        .expect("error while building tauri application");

    // 注册退出事件 → 杀死后端 + 清理日志
    app.run(|app_handle, event| {
        if let tauri::RunEvent::Exit = event {
            tracing::info!("应用退出，清理后端进程");
            if let Some(state) = app_handle.try_state::<BackendProcess>() {
                if let Ok(mut guard) = state.child.lock() {
                    if let Some(ref mut child) = *guard {
                        kill_process_tree(child);
                        let _ = child.wait();
                    }
                }
            }
            // 清理日志目录
            let log_dir = get_log_dir();
            let _ = std::fs::remove_dir_all(&log_dir);
        }
    });
}

// ── 原 greet 命令（保留）───────────────────────────────────────────────
#[tauri::command]
fn greet(name: &str) -> String {
    format!("Hello, {}! You've been greeted from Rust!", name)
}
