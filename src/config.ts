/** 后端 API 基础地址 */
export const API_BASE = 'http://127.0.0.1:8000'

/** 完整 API 路径辅助函数 */
export function api(path: string): string {
  return `${API_BASE}${path}`
}
