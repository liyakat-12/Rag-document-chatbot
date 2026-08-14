import { useEffect, useRef } from 'react'
import { Send, Square } from 'lucide-react'

export default function Composer({ value, onChange, onSend, streaming, onCancel, disabled }) {
  const ref = useRef(null)

  useEffect(() => {
    const el = ref.current
    if (!el) return
    el.style.height = 'auto'
    el.style.height = Math.min(el.scrollHeight, 160) + 'px'
  }, [value])

  return (
    <div className="composer">
      <div className="composer-box">
        <textarea
          ref={ref}
          value={value}
          placeholder="Ask a question about your documents…"
          rows={1}
          disabled={disabled}
          onChange={(e) => onChange(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === 'Enter' && !e.shiftKey) {
              e.preventDefault()
              if (!streaming && value.trim()) onSend()
            }
          }}
        />
        {streaming ? (
          <button className="btn btn-danger" onClick={onCancel} title="Stop">
            <Square size={16} />
          </button>
        ) : (
          <button className="btn" onClick={onSend} disabled={!value.trim() || disabled}>
            <Send size={16} />
            Send
          </button>
        )}
      </div>
    </div>
  )
}
