import { ArrowLeft, RefreshCw } from 'lucide-react'
import { ThemeToggle } from '../components/Sidebar'

export default function AdminPage({ stats, onBack, onRefresh, theme, onToggleTheme }) {
  const docs = stats?.documents || {}

  return (
    <div style={{ minHeight: '100vh', padding: '1.5rem', maxWidth: 960, margin: '0 auto' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1.5rem' }}>
        <div style={{ display: 'flex', gap: 10, alignItems: 'center' }}>
          <button className="btn btn-ghost" onClick={onBack}>
            <ArrowLeft size={16} /> Back
          </button>
          <div className="brand">
            <div className="brand-name">Admin Dashboard</div>
            <div className="brand-sub">Document & usage statistics</div>
          </div>
        </div>
        <div style={{ display: 'flex', gap: 8 }}>
          <button className="btn btn-ghost" onClick={onRefresh}>
            <RefreshCw size={16} /> Refresh
          </button>
          <ThemeToggle theme={theme} onToggle={onToggleTheme} />
        </div>
      </div>

      <div className="stats-grid" style={{ gridTemplateColumns: 'repeat(auto-fit, minmax(160px, 1fr))', padding: 0 }}>
        {[
          ['Documents', docs.total_documents],
          ['Indexed', docs.indexed_documents],
          ['Pages', docs.total_pages],
          ['Chunks', docs.total_chunks],
          ['Storage (bytes)', docs.total_size_bytes],
          ['Sessions', stats?.total_sessions],
          ['Messages', stats?.total_messages],
          ['Tokens used', stats?.total_tokens_used],
          ['Cache hits', stats?.cache_hits],
          ['Cache misses', stats?.cache_misses],
        ].map(([label, value]) => (
          <div className="stat" key={label}>
            <div className="label">{label}</div>
            <div className="value">{value ?? '—'}</div>
          </div>
        ))}
      </div>
    </div>
  )
}
