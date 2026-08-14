import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import { Bot, Copy, ThumbsDown, ThumbsUp, User } from 'lucide-react'

function TypingIndicator() {
  return (
    <div className="typing" aria-label="Assistant is typing">
      <span />
      <span />
      <span />
    </div>
  )
}

export default function MessageList({ messages, streaming, onCopy, onRate }) {
  if (!messages.length && !streaming) {
    return (
      <div className="empty-state">
        <h2>Ask your documents</h2>
        <p>
          Upload PDFs on the right, then ask questions. Answers include source citations and a
          confidence score.
        </p>
      </div>
    )
  }

  return (
    <div className="chat-area">
      {messages.map((m) => (
        <div key={m.id} className={`message-row ${m.role}`}>
          {m.role !== 'user' && <div className="avatar">AI</div>}
          <div className="bubble">
            {m.role === 'assistant' ? (
              <div className="markdown">
                <ReactMarkdown remarkPlugins={[remarkGfm]}>{m.content}</ReactMarkdown>
              </div>
            ) : (
              <div>{m.content}</div>
            )}
            {m.role === 'assistant' && (
              <div className="message-actions">
                {typeof m.confidence === 'number' && (
                  <span className="confidence">
                    Confidence: {(m.confidence * 100).toFixed(0)}%
                  </span>
                )}
                {m.cached && <span className="chip">cached</span>}
                <button className="btn-icon" title="Copy" onClick={() => onCopy(m.content)}>
                  <Copy size={14} />
                </button>
                <button
                  className="btn-icon"
                  title="Thumbs up"
                  onClick={() => onRate(m.id, 'up')}
                  style={{ color: m.rating === 'up' ? 'var(--accent)' : undefined }}
                >
                  <ThumbsUp size={14} />
                </button>
                <button
                  className="btn-icon"
                  title="Thumbs down"
                  onClick={() => onRate(m.id, 'down')}
                  style={{ color: m.rating === 'down' ? 'var(--danger)' : undefined }}
                >
                  <ThumbsDown size={14} />
                </button>
              </div>
            )}
          </div>
          {m.role === 'user' && (
            <div className="avatar" style={{ background: 'var(--user-bubble)', color: '#fff' }}>
              <User size={16} />
            </div>
          )}
        </div>
      ))}
      {streaming && (
        <div className="message-row assistant">
          <div className="avatar">
            <Bot size={16} />
          </div>
          <div className="bubble">
            <TypingIndicator />
          </div>
        </div>
      )}
    </div>
  )
}
