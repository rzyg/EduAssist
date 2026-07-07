/** 后端 API 基础地址（运行时自动获取，不在 Tauri 环境时使用默认值） */
let _base: string | null = null

async function resolveBase(): Promise<string> {
    if (_base) return _base
    try {
        const {invoke} = await import('@tauri-apps/api/core')
        _base = await invoke<string>('get_backend_url')
    } catch {
        _base = 'http://127.0.0.1:8000'
    }
    return _base
}

/** 获取完整的 API 路径 */
export async function api(path: string): Promise<string> {
    return (await resolveBase()) + path
}

/** 获取 API 基础地址 */
export async function getApiBase(): Promise<string> {
    return resolveBase()
}
