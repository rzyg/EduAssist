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

let _token: string | null = null

/** 获取 Bearer Token（Tauri 环境） */
export async function getToken(): Promise<string> {
    if (_token !== null) return _token
    try {
        const {invoke} = await import('@tauri-apps/api/core')
        _token = await invoke<string>('get_token')
    } catch {
        _token = ''
    }
    return _token
}

/** 获取开发者模式状态（Tauri 环境） */
export async function getDevMode(): Promise<boolean> {
    try {
        const {invoke} = await import('@tauri-apps/api/core')
        return await invoke<boolean>('get_dev_mode')
    } catch {
        return false
    }
}

/** 带 Bearer Token 的 fetch 封装 */
export async function apiFetch(path: string, options: RequestInit = {}): Promise<Response> {
    const url = await api(path)
    const token = await getToken()
    if (token) {
        const headers = new Headers(options.headers)
        headers.set('Authorization', `Bearer ${token}`)
        return fetch(url, {...options, headers})
    }
    return fetch(url, options)
}
