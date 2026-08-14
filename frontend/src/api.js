const API_BASE = import.meta.env.VITE_API_BASE_URL || '/api/v1'

async function request(path, options = {}) {
  const res = await fetch(`${API_BASE}${path}`, options)
  if (!res.ok) {
    let detail = res.statusText
    try {
      const body = await res.json()
      detail = body.detail || JSON.stringify(body)
    } catch {
      /* ignore */
    }
    throw new Error(typeof detail === 'string' ? detail : JSON.stringify(detail))
  }
  if (res.status === 204) return null
  const ct = res.headers.get('content-type') || ''
  if (ct.includes('application/pdf')) return res.blob()
  return res.json()
}

export const api = {
  health: () => request('/health'),
  listDocuments: () => request('/documents'),
  uploadDocuments: (files) => {
    const form = new FormData()
    files.forEach((f) => form.append('files', f))
    return request('/upload', { method: 'POST', body: form })
  },
  deleteDocument: (id) => request(`/document/${id}`, { method: 'DELETE' }),
  reindex: () => request('/reindex', { method: 'POST' }),
  documentStats: () => request('/documents/stats'),
  adminStats: () => request('/admin/stats'),
  listSessions: () => request('/history'),
  getSession: (id) => request(`/history/${id}`),
  deleteSession: (id) => request(`/history/${id}`, { method: 'DELETE' }),
  rateMessage: (id, rating) =>
    request(`/messages/${id}/rate`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ rating }),
    }),
  exportSession: (id) => request(`/history/${id}/export`),
  chat: (payload) =>
    request('/chat', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ ...payload, stream: false }),
    }),
}

/**
 * Stream chat via SSE. Calls onEvent for each parsed event.
 */
export async function streamChat(payload, { onEvent, signal } = {}) {
  const res = await fetch(`${API_BASE}/chat/stream`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ ...payload, stream: true }),
    signal,
  })
  if (!res.ok) {
    const text = await res.text()
    throw new Error(text || res.statusText)
  }
  const reader = res.body.getReader()
  const decoder = new TextDecoder()
  let buffer = ''
  while (true) {
    const { done, value } = await reader.read()
    if (done) break
    buffer += decoder.decode(value, { stream: true })
    const parts = buffer.split('\n\n')
    buffer = parts.pop() || ''
    for (const part of parts) {
      const line = part.trim()
      if (!line.startsWith('data:')) continue
      const data = line.slice(5).trim()
      if (data === '[DONE]') return
      try {
        onEvent?.(JSON.parse(data))
      } catch {
        /* skip malformed */
      }
    }
  }
}
