import { MessageSquarePlus, Moon, Sun, Trash2, X } from 'lucide-react'

export default function Sidebar({
  sessions,
  activeId,
  onSelect,
  onNew,
  onDelete,
  onClose,
  open,
}) {
  return (
    <aside className={`sidebar ${open ? 'open' : ''}`}>
      <div className="panel-header">
        <div className="brand">
          <div className="brand-name">DocuMind RAG</div>
          <div className="brand-sub">Chat history</div>
        </div>
        <div style={{ display: 'flex', gap: 4 }}>
          <button className="btn-icon" onClick={onNew} title="New chat">
            <MessageSquarePlus size={18} />
          </button>
          {onClose && (
            <button className="btn-icon mobile-only" onClick={onClose}>
              <X size={18} />
            </button>
          )}
        </div>
      </div>
      <div className="session-list">
        {sessions.length === 0 && (
          <div className="session-meta" style={{ padding: '0.5rem' }}>
            No conversations yet.
          </div>
        )}
        {sessions.map((s) => (
          <div
            key={s.id}
            className={`session-item ${s.id === activeId ? 'active' : ''}`}
            style={{ display: 'flex', alignItems: 'center', gap: 6 }}
          >
            <button
              style={{ flex: 1, textAlign: 'left', minWidth: 0 }}
              onClick={() => onSelect(s.id)}
            >
              <div className="session-title">{s.title}</div>
              <div className="session-meta">
                {s.message_count} messages · {new Date(s.updated_at).toLocaleDateString()}
              </div>
            </button>
            <button
              className="btn-icon"
              title="Delete session"
              onClick={() => onDelete(s.id)}
            >
              <Trash2 size={14} />
            </button>
          </div>
        ))}
      </div>
    </aside>
  )
}

export function ThemeToggle({ theme, onToggle }) {
  return (
    <button className="btn-icon" onClick={onToggle} title="Toggle theme">
      {theme === 'dark' ? <Sun size={18} /> : <Moon size={18} />}
    </button>
  )
}
