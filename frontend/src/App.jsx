import { useCallback, useEffect, useState } from 'react'
import {
  Download,
  FileText,
  LayoutDashboard,
  Menu,
  PanelRight,
} from 'lucide-react'
import { api } from './api'
import Sidebar, { ThemeToggle } from './components/Sidebar'
import DocumentPanel from './components/DocumentPanel'
import MessageList from './components/MessageList'
import Composer from './components/Composer'
import SourcesPanel from './components/SourcesPanel'
import { useTheme } from './hooks/useTheme'
import { useChatStream } from './hooks/useChatStream'
import AdminPage from './pages/AdminPage'

export default function App() {
  const { theme, toggle } = useTheme()
  const { send, cancel, streaming } = useChatStream()

  const [view, setView] = useState('chat')
  const [sessions, setSessions] = useState([])
  const [sessionId, setSessionId] = useState(null)
  const [messages, setMessages] = useState([])
  const [documents, setDocuments] = useState([])
  const [input, setInput] = useState('')
  const [sources, setSources] = useState([])
  const [chunks, setChunks] = useState([])
  const [stats, setStats] = useState(null)
  const [uploading, setUploading] = useState(false)
  const [reindexing, setReindexing] = useState(false)
  const [toast, setToast] = useState(null)
  const [sidebarOpen, setSidebarOpen] = useState(false)
  const [rightOpen, setRightOpen] = useState(false)
  const [showTypingRow, setShowTypingRow] = useState(false)

  const notify = (msg) => {
    setToast(msg)
    setTimeout(() => setToast(null), 2800)
  }

  const refreshSessions = useCallback(async () => {
    try {
      const data = await api.listSessions()
      setSessions(data.sessions || [])
    } catch (e) {
      console.error(e)
    }
  }, [])

  const refreshDocuments = useCallback(async () => {
    try {
      setDocuments(await api.listDocuments())
    } catch (e) {
      console.error(e)
    }
  }, [])

  const refreshStats = useCallback(async () => {
    try {
      setStats(await api.adminStats())
    } catch {
      /* optional */
    }
  }, [])

  useEffect(() => {
    refreshSessions()
    refreshDocuments()
    refreshStats()
  }, [refreshSessions, refreshDocuments, refreshStats])

  const loadSession = async (id) => {
    setSessionId(id)
    setSidebarOpen(false)
    try {
      const detail = await api.getSession(id)
      setMessages(
        (detail.messages || []).map((m) => ({
          id: m.id,
          role: m.role,
          content: m.content,
          confidence: m.confidence,
          rating: m.rating,
          sources: m.sources,
        })),
      )
      const lastAssistant = [...(detail.messages || [])].reverse().find((m) => m.role === 'assistant')
      setSources(lastAssistant?.sources || [])
      setChunks(lastAssistant?.sources || [])
    } catch (e) {
      notify(e.message)
    }
  }

  const newChat = () => {
    setSessionId(null)
    setMessages([])
    setSources([])
    setChunks([])
    setSidebarOpen(false)
  }

  const handleUpload = async (files) => {
    setUploading(true)
    try {
      await api.uploadDocuments(files)
      await refreshDocuments()
      await refreshStats()
      notify(`Uploaded ${files.length} PDF(s)`)
    } catch (e) {
      notify(e.message)
    } finally {
      setUploading(false)
    }
  }

  const handleDeleteDoc = async (id) => {
    try {
      await api.deleteDocument(id)
      await refreshDocuments()
      await refreshStats()
      notify('Document deleted')
    } catch (e) {
      notify(e.message)
    }
  }

  const handleReindex = async () => {
    setReindexing(true)
    try {
      const res = await api.reindex()
      await refreshDocuments()
      notify(`Reindexed ${res.documents_reindexed} docs / ${res.chunks_indexed} chunks`)
    } catch (e) {
      notify(e.message)
    } finally {
      setReindexing(false)
    }
  }

  const handleSend = async () => {
    const text = input.trim()
    if (!text || streaming) return
    setInput('')
    const tempUserId = `user-${Date.now()}`
    setMessages((prev) => [...prev, { id: tempUserId, role: 'user', content: text }])
    setShowTypingRow(true)

    const assistantId = `assistant-${Date.now()}`
    let createdAssistant = false

    await send({
      message: text,
      sessionId,
      onMeta: (meta) => {
        if (meta.session_id) setSessionId(meta.session_id)
        setSources(meta.sources || [])
        setChunks(meta.retrieved_chunks || meta.sources || [])
      },
      onToken: (_token, full) => {
        setShowTypingRow(false)
        if (!createdAssistant) {
          createdAssistant = true
          setMessages((prev) => [
            ...prev,
            { id: assistantId, role: 'assistant', content: full, confidence: null },
          ])
        } else {
          setMessages((prev) =>
            prev.map((m) => (m.id === assistantId ? { ...m, content: full } : m)),
          )
        }
      },
      onDone: (done) => {
        setShowTypingRow(false)
        setMessages((prev) =>
          prev.map((m) =>
            m.id === assistantId || (m.role === 'assistant' && m.id === assistantId)
              ? {
                  ...m,
                  id: done.message_id || m.id,
                  content: done.answer,
                  confidence: done.confidence,
                  cached: done.cached,
                  sources: done.sources,
                  rating: 'none',
                }
              : m,
          ),
        )
        setSources(done.sources || [])
        setChunks(done.retrieved_chunks || done.sources || [])
        refreshSessions()
        refreshStats()
      },
      onError: (err) => {
        setShowTypingRow(false)
        notify(err.message)
      },
    })
  }

  const handleCopy = async (text) => {
    try {
      await navigator.clipboard.writeText(text)
      notify('Copied to clipboard')
    } catch {
      notify('Copy failed')
    }
  }

  const handleRate = async (messageId, rating) => {
    try {
      await api.rateMessage(messageId, rating)
      setMessages((prev) =>
        prev.map((m) => (m.id === messageId ? { ...m, rating } : m)),
      )
    } catch (e) {
      notify(e.message)
    }
  }

  const handleExport = async () => {
    if (!sessionId) {
      notify('Start a chat first')
      return
    }
    try {
      const blob = await api.exportSession(sessionId)
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = `chat-${sessionId.slice(0, 8)}.pdf`
      a.click()
      URL.revokeObjectURL(url)
    } catch (e) {
      notify(e.message)
    }
  }

  const handleDeleteSession = async (id) => {
    try {
      await api.deleteSession(id)
      if (sessionId === id) newChat()
      await refreshSessions()
    } catch (e) {
      notify(e.message)
    }
  }

  if (view === 'admin') {
    return (
      <AdminPage
        stats={stats}
        onBack={() => setView('chat')}
        onRefresh={refreshStats}
        theme={theme}
        onToggleTheme={toggle}
      />
    )
  }

  return (
    <div className="app-shell">
      <Sidebar
        sessions={sessions}
        activeId={sessionId}
        onSelect={loadSession}
        onNew={newChat}
        onDelete={handleDeleteSession}
        open={sidebarOpen}
        onClose={() => setSidebarOpen(false)}
      />

      <main className="main">
        <div className="topbar">
          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <div className="mobile-toggles">
              <button className="btn-icon" onClick={() => setSidebarOpen(true)}>
                <Menu size={18} />
              </button>
            </div>
            <div className="brand">
              <div className="brand-name">DocuMind</div>
              <div className="brand-sub">RAG Document Chatbot</div>
            </div>
          </div>
          <div style={{ display: 'flex', gap: 6, alignItems: 'center' }}>
            <button className="btn btn-ghost" onClick={() => setView('admin')}>
              <LayoutDashboard size={16} /> Admin
            </button>
            <button className="btn btn-ghost" onClick={handleExport} disabled={!sessionId}>
              <Download size={16} /> PDF
            </button>
            <ThemeToggle theme={theme} onToggle={toggle} />
            <div className="mobile-toggles">
              <button className="btn-icon" onClick={() => setRightOpen(true)}>
                <PanelRight size={18} />
              </button>
            </div>
          </div>
        </div>

        <MessageList
          messages={messages}
          streaming={showTypingRow && streaming}
          onCopy={handleCopy}
          onRate={handleRate}
        />

        <Composer
          value={input}
          onChange={setInput}
          onSend={handleSend}
          streaming={streaming}
          onCancel={cancel}
          disabled={documents.length === 0}
        />
        {documents.length === 0 && (
          <div style={{ textAlign: 'center', paddingBottom: 12, color: 'var(--text-muted)', fontSize: 13 }}>
            <FileText size={14} style={{ verticalAlign: 'middle', marginRight: 6 }} />
            Upload at least one PDF to start chatting
          </div>
        )}
      </main>

      <div style={{ display: 'flex', flexDirection: 'column', borderLeft: '1px solid var(--border)' }}>
        <div style={{ flex: '0 0 45%', minHeight: 220, overflow: 'hidden', borderBottom: '1px solid var(--border)' }}>
          <DocumentPanel
            documents={documents}
            uploading={uploading}
            onUpload={handleUpload}
            onDelete={handleDeleteDoc}
            onReindex={handleReindex}
            reindexing={reindexing}
          />
        </div>
        <div style={{ flex: 1, minHeight: 0, overflow: 'hidden' }} className={rightOpen ? 'right-panel open' : ''}>
          <SourcesPanel
            sources={sources}
            chunks={chunks}
            stats={stats}
            open={rightOpen}
            onClose={() => setRightOpen(false)}
          />
        </div>
      </div>

      {toast && <div className="toast">{toast}</div>}
    </div>
  )
}
