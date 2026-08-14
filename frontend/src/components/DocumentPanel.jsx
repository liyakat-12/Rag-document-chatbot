import { useCallback, useRef, useState } from 'react'
import { FileUp, Loader2, RefreshCw, Trash2 } from 'lucide-react'

export default function DocumentPanel({
  documents,
  uploading,
  onUpload,
  onDelete,
  onReindex,
  reindexing,
}) {
  const inputRef = useRef(null)
  const [dragOver, setDragOver] = useState(false)

  const handleFiles = useCallback(
    (fileList) => {
      const files = Array.from(fileList || []).filter((f) =>
        f.name.toLowerCase().endsWith('.pdf'),
      )
      if (files.length) onUpload(files)
    },
    [onUpload],
  )

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100%' }}>
      <div className="panel-header">
        <div className="brand">
          <div className="brand-name">Documents</div>
          <div className="brand-sub">{documents.length} uploaded</div>
        </div>
        <button
          className="btn-icon"
          onClick={onReindex}
          disabled={reindexing}
          title="Re-index all"
        >
          {reindexing ? <Loader2 className="spin" size={16} /> : <RefreshCw size={16} />}
        </button>
      </div>

      <div
        className={`dropzone ${dragOver ? 'active' : ''}`}
        onClick={() => inputRef.current?.click()}
        onDragOver={(e) => {
          e.preventDefault()
          setDragOver(true)
        }}
        onDragLeave={() => setDragOver(false)}
        onDrop={(e) => {
          e.preventDefault()
          setDragOver(false)
          handleFiles(e.dataTransfer.files)
        }}
      >
        <FileUp size={22} style={{ marginBottom: 6 }} />
        <div>{uploading ? 'Uploading…' : 'Drag & drop PDFs here'}</div>
        <div className="session-meta">or click to browse · max 20 MB</div>
        <input
          ref={inputRef}
          type="file"
          accept="application/pdf,.pdf"
          multiple
          hidden
          onChange={(e) => {
            handleFiles(e.target.files)
            e.target.value = ''
          }}
        />
      </div>

      <div className="doc-list">
        {documents.map((d) => (
          <div key={d.id} className="doc-item">
            <div className="info">
              <div className="name" title={d.original_filename}>
                {d.original_filename}
              </div>
              <div className="doc-meta">
                {d.page_count} pages · {d.chunk_count} chunks · {d.status}
              </div>
            </div>
            <button className="btn-icon" onClick={() => onDelete(d.id)} title="Delete">
              <Trash2 size={14} />
            </button>
          </div>
        ))}
      </div>
    </div>
  )
}
