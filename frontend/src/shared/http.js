export class ApiError extends Error {
  constructor(message, { status = 0, code = 'network_error', uncertain = false } = {}) {
    super(message)
    this.name = 'ApiError'
    this.status = status
    this.code = code
    this.uncertain = uncertain
  }
}

export function createHttp(fetcher = (...args) => fetch(...args)) {
  async function request(path, { method = 'GET', body, formData, timeout = 20000 } = {}) {
    const writing = !['GET', 'HEAD'].includes(method)
    const controller = new AbortController()
    const timer = setTimeout(() => controller.abort(), timeout)
    try {
      const response = await fetcher(path, {
        method, signal: controller.signal,
        headers: body === undefined || formData ? {} : { 'Content-Type': 'application/json' },
        ...(formData ? { body: formData } : body === undefined ? {} : { body: JSON.stringify(body) }),
      })
      if (response.ok && response.status === 204) return undefined
      let data
      try { data = await response.json() } catch {
        throw new ApiError('服务返回了无法读取的结果，请检查后端是否正常运行。', {
          status: response.status, code: 'invalid_response', uncertain: writing,
        })
      }
      if (!response.ok) {
        throw new ApiError(data?.error?.message || '请求未完成，请稍后重试。', {
          status: response.status, code: data?.error?.code || 'http_error', uncertain: response.status >= 500,
        })
      }
      return data
    } catch (error) {
      if (error instanceof ApiError) throw error
      throw new ApiError(controller.signal.aborted
        ? '等待服务响应超时，请先刷新学习记录。'
        : '暂时连接不到服务，请检查后端是否运行后再重试。', { uncertain: writing })
    } finally { clearTimeout(timer) }
  }
  return request
}
