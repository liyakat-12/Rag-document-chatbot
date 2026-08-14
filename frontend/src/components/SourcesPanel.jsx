import { X } from 'lucide-react'

export default function SourcesPanel({ sources, chunks, stats, open, onClose }) {
  const items = chunks?.length ? chunks : sources || []

  return (
    <aside className={`right-panel ${open ? 'open' : ''}`}>
      <div className="panel-header">
        <div className="brand">
          <div className="brand-name">Sources & Stats</div>
          <div className="brand-sub">Retrieved context</div>
        </div>
        {onClose && (
          <button className="btn-icon" onClick={onClose}>
            <X size={18} />
          </button>
        )}
      </div>

      {stats && (
        <div className="stats-grid">
          <div className="stat">
            <div className="label">Documents</div>
            <div className="value">{stats.documents?.total_documents ?? 0}</div>
          </div>
          <div className="stat">
            <div className="label">Chunks</div>
            <div className="value">{stats.documents?.total_chunks ?? 0}</div>
          </div>
          <div className="stat">
            <div className="label">Sessions</div>
            <div className="value">{stats.total_sessions ?? 0}</div>
          </div>
          <div className="stat">
            <div className="label">Tokens</div>
            <div className="value">{stats.total_tokens_used ?? 0}</div>
          </div>
          <div className="stat">
            <div className="label">Cache hits</div>
            <div className="value">{stats.cache_hits ?? 0}</div>
          </div>
          <div className="stat">
            <div className="label">Cache miss</div>
            <div className="value">{stats.cache_misses ?? 0}</div>
          </div>
        </div>
      )}

      <div className="sources-panel">
        {items.length === 0 && (
          <div className="session-meta">Sources from the latest answer appear here.</div>
        )}
        {items.map((s, i) => (
          <div key={s.chunk_id || i} className="source-card">
            <h4>
              {s.filename} · p.{s.page_number}
              {typeof s.score === 'number' && (
                <span className="chip" style={{ marginLeft: 8 }}>
                  {(s.score * 100).toFixed(0)}%
                </span>
              )}
            </h4>
            <p>{s.content}</p>
          </div>
        ))}
      </div>
    </aside>
  )
}
