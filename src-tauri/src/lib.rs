use std::net::TcpStream;
use std::sync::{Arc, Mutex};
use std::time::Duration;
use tauri::Manager;

const SERVER_HOST: &str = "127.0.0.1";
const SERVER_PORT: u16 = 8501;
const POLL_INTERVAL_MS: u64 = 500;
const MAX_ATTEMPTS: u32 = 60; // 30 seconds

fn wait_for_server() -> bool {
    for _ in 0..MAX_ATTEMPTS {
        if TcpStream::connect((SERVER_HOST, SERVER_PORT)).is_ok() {
            return true;
        }
        std::thread::sleep(Duration::from_millis(POLL_INTERVAL_MS));
    }
    false
}

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    tauri::Builder::default()
        .plugin(tauri_plugin_shell::init())
        .setup(|app| {
            let handle = app.handle().clone();

            #[cfg(not(debug_assertions))]
            {
                use tauri_plugin_shell::ShellExt;

                // Spawn the bundled Python sidecar and hold onto the child so we can kill it on exit
                let sidecar = app
                    .shell()
                    .sidecar("cachecow-server")
                    .expect("cachecow-server sidecar not found");
                let (_, child) = sidecar.spawn().expect("failed to spawn cachecow-server");

                // Store the child in app state so the on_window_event handler can reach it
                app.manage(Arc::new(Mutex::new(Some(child))));
            }

            // Wait for the server in a background thread, then navigate
            std::thread::spawn(move || {
                if wait_for_server() {
                    if let Some(window) = handle.get_webview_window("main") {
                        let url = format!("http://{}:{}", SERVER_HOST, SERVER_PORT);
                        let _ = window.eval(&format!(
                            "window.location.replace('{}')",
                            url
                        ));
                    }
                }
            });

            Ok(())
        })
        .on_window_event(|window, event| {
            if let tauri::WindowEvent::Destroyed = event {
                #[cfg(not(debug_assertions))]
                {
                    use tauri_plugin_shell::process::CommandChild;
                    if let Some(child_state) = window.app_handle().try_state::<Arc<Mutex<Option<CommandChild>>>>() {
                        if let Ok(mut guard) = child_state.lock() {
                            if let Some(child) = guard.take() {
                                let _ = child.kill();
                            }
                        }
                    }
                }
            }
        })
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}
