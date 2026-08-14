import { useCallback, useRef, useState } from 'react'
import { streamChat } from '../api'

export function useChatStream() {
  const [streaming, setStreaming] = useState(false)
  const abortRef = useRef(null)

  const send = useCallback(async ({ message, sessionId, documentIds, onMeta, onToken, onDone, onError }) => {
    setStreaming(true)
    abortRef.current = new AbortController()
    let full = ''
    try {
      await streamChat(
        { message, session_id: sessionId, document_ids: documentIds },
        {
          signal: abortRef.current.signal,
          onEvent: (event) => {
            if (event.event === 'meta') onMeta?.(event)
            if (event.event === 'token') {
              full += event.content || ''
              onToken?.(event.content || '', full)
            }
            if (event.event === 'done') onDone?.({ ...event, answer: event.answer || full })
          },
        },
      )
    } catch (err) {
      if (err.name !== 'AbortError') onError?.(err)
    } finally {
      setStreaming(false)
    }
  }, [])

  const cancel = useCallback(() => {
    abortRef.current?.abort()
    setStreaming(false)
  }, [])

  return { send, cancel, streaming }
}
