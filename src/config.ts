/**
 * 后端 API 通信统一入口
 *
 * - 地址解析：Tauri 环境通过 `invoke('get_backend_url')` 从 Rust 端获取
 *   （Rust 端按 dev / 生产自动切换，见 src-tauri/src/lib.rs）；
 *   非 Tauri 环境（纯 vite 调试）回退默认值 http://127.0.0.1:8000。
 * - 请求封装：apiFetch / apiGet / apiPost / apiUpload 统一注入 Bearer Token、
 *   拼接基础地址，并默认带超时。
 */
let _base: string | null = null

/** 默认后端地址（开发者调试模式 / 非 Tauri 环境回退值） */
const DEFAULT_BASE = 'http://127.0.0.1:8000'

/** 请求默认超时（毫秒），0 表示不设超时 */
const DEFAULT_TIMEOUT = 15000

async function resolveBase(): Promise<string> {
    if (_base) return _base
    try {
        const {invoke} = await import('@tauri-apps/api/core')
        _base = await invoke<string>('get_backend_url')
    } catch {
        _base = DEFAULT_BASE
    }
    return _base
}

/** 清除缓存的后端地址（修改监听地址/端口后调用，强制下次重新获取） */
export function resetApiBase(): void {
    _base = null
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

/** 获取开发者模式状态（Tauri 环境，读取 config.yaml 的 dev_mode） */
export async function getDevMode(): Promise<boolean> {
    try {
        const {invoke} = await import('@tauri-apps/api/core')
        return await invoke<boolean>('get_dev_mode')
    } catch {
        return false
    }
}

/** 当前运行模式：'tauri-dev'（tauri dev）| 'normal'（Tauri 生产）| 'browser'（纯浏览器调试） */
export async function getMode(): Promise<string> {
    try {
        const {invoke} = await import('@tauri-apps/api/core')
        return await invoke<string>('get_mode')
    } catch {
        return 'browser'
    }
}

/** 当前是否为开发者调试模式（tauri dev 或纯 vite dev） */
export async function isDevMode(): Promise<boolean> {
    return (await getMode()) !== 'normal'
}

export interface ApiFetchOptions extends RequestInit {
    /** 超时毫秒数，默认 15000；传 0 表示不设超时 */
    timeout?: number
}

/** 带 Bearer Token 的 fetch 封装（自动拼接基础地址 + 注入 token + 超时） */
export async function apiFetch(path: string, options: ApiFetchOptions = {}): Promise<Response> {
    const {timeout = DEFAULT_TIMEOUT, signal, ...rest} = options
    const url = await api(path)
    const headers = new Headers(rest.headers)
    const token = await getToken()
    if (token) headers.set('Authorization', `Bearer ${token}`)
    // 调用方显式传入 signal 时优先使用，否则按 timeout 生成
    const finalSignal = signal ?? (timeout > 0 ? AbortSignal.timeout(timeout) : undefined)
    return fetch(url, {...rest, headers, signal: finalSignal})
}

/** 解析响应：非 2xx 抛出包含后端 detail 的错误 */
async function parseJson<T>(res: Response): Promise<T> {
    if (res.ok) return res.json() as Promise<T>
    let detail = `请求失败 (${res.status})`
    try {
        const data = await res.json()
        if (data?.detail) {
            detail = typeof data.detail === 'string' ? data.detail : JSON.stringify(data.detail)
        }
    } catch { /* 响应体不是 JSON，保留默认信息 */
    }
    throw new Error(detail)
}

/** GET 请求，返回 JSON */
export async function apiGet<T = unknown>(path: string, options: ApiFetchOptions = {}): Promise<T> {
    return parseJson<T>(await apiFetch(path, {...options, method: 'GET'}))
}

/** POST JSON 请求，返回 JSON */
export async function apiPost<T = unknown>(path: string, body?: unknown, options: ApiFetchOptions = {}): Promise<T> {
    const headers = new Headers(options.headers)
    headers.set('Content-Type', 'application/json')
    return parseJson<T>(await apiFetch(path, {
        ...options,
        method: 'POST',
        headers,
        body: body === undefined ? undefined : JSON.stringify(body),
    }))
}

/** PUT JSON 请求，返回 JSON */
export async function apiPut<T = unknown>(path: string, body?: unknown, options: ApiFetchOptions = {}): Promise<T> {
    const headers = new Headers(options.headers)
    headers.set('Content-Type', 'application/json')
    return parseJson<T>(await apiFetch(path, {
        ...options,
        method: 'PUT',
        headers,
        body: body === undefined ? undefined : JSON.stringify(body),
    }))
}

/** 上传 FormData（自动注入 token；默认不设超时，避免大文件被截断），返回 JSON */
export async function apiUpload<T = unknown>(path: string, formData: FormData, options: ApiFetchOptions = {}): Promise<T> {
    return parseJson<T>(await apiFetch(path, {
        ...options,
        method: 'POST',
        body: formData,
        timeout: options.timeout ?? 0,
    }))
}

/** 后端健康检查（探测 /health 是否在线） */
export async function checkHealth(base?: string): Promise<boolean> {
    const url = (base ?? await resolveBase()) + '/health'
    try {
        const res = await fetch(url, {signal: AbortSignal.timeout(1500)})
        return res.ok && (await res.json()).status === 'ok'
    } catch {
        return false
    }
}
