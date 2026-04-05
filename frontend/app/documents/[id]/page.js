'use client'

import { useState, useEffect, useRef, useCallback } from 'react'
import { useParams, useRouter } from 'next/navigation'
import Sidebar from '@/components/Sidebar'
import { useAuth } from '@/components/useAuth'
import {
  ArrowLeft, Check, Loader2, Bold, Italic, Underline,
  List, ListOrdered, Heading1, Heading2, Minus, Redo, Undo,
} from 'lucide-react'
import { DocumentRightPanel } from './DocumentRightPanel'

const BACKEND = process.env.NEXT_PUBLIC_BACKEND_URL || 'http://localhost:8000'


function highlightArticlesInDom(container, articles) {
  if (!container || !articles || articles.length === 0) return

  // Sort by norm_text length (longest first) to avoid partial replacements
  const sortedArticles = [...articles].sort((a, b) => b.norm_text.length - a.norm_text.length)

  for (const article of sortedArticles) {
    // Use TreeWalker to walk through text nodes only (not HTML tags)
    const walker = document.createTreeWalker(
      container,
      NodeFilter.SHOW_TEXT,
      null,
      false
    )

    let textNode
    while ((textNode = walker.nextNode())) {
      const idx = textNode.nodeValue.indexOf(article.norm_text)
      if (idx === -1) continue

      // Split the text node:
      // Before match | match | after match
      const matchNode = textNode.splitText(idx)
      matchNode.splitText(article.norm_text.length)

      // Create span for the matched text
      const span = document.createElement('span')
      span.setAttribute('data-norm', article.norm_text)
      span.className = `norm-highlight norm-${article.status}`

      // Insert span before matchNode and move matchNode inside it
      matchNode.parentNode.insertBefore(span, matchNode)
      span.appendChild(matchNode)

      // Continue with next article (don't highlight same text twice)
      break
    }
  }
}

function SaveStatus({ status }) {
  if (status === 'saving') return (
    <span className="flex items-center gap-1.5 text-xs text-gray-400">
      <Loader2 size={12} className="animate-spin" /> Сохранение...
    </span>
  )
  if (status === 'saved') return (
    <span className="flex items-center gap-1.5 text-xs text-brand-hover">
      <Check size={12} /> Сохранено
    </span>
  )
  if (status === 'unsaved') return (
    <span className="flex items-center gap-1.5 text-xs text-amber-500">
      <span className="w-1.5 h-1.5 rounded-full bg-amber-400 inline-block" /> Не сохранено
    </span>
  )
  return null
}

function ToolbarBtn({ onClick, active, title, children }) {
  return (
    <button
      type="button"
      onMouseDown={e => { e.preventDefault(); onClick() }}
      title={title}
      className={`p-1.5 rounded transition-colors ${active ? 'bg-gray-200 text-ink' : 'text-gray-500 hover:bg-gray-100 hover:text-gray-800'}`}
    >
      {children}
    </button>
  )
}

export default function DocumentEditorPage() {
  const { id } = useParams()
  const router = useRouter()
  const { loading: authLoading, authHeaders } = useAuth()

  const [doc, setDoc] = useState(null)
  const [title, setTitle] = useState('')
  const [saveStatus, setSaveStatus] = useState('idle')
  const [loading, setLoading] = useState(true)
  const [wordCount, setWordCount] = useState(0)
  const [activeFormats, setActiveFormats] = useState({})
  const [activePanel, setActivePanel] = useState('analysis')
  const [analysis, setAnalysis] = useState(null)
  const [analysisLoading, setAnalysisLoading] = useState(false)
  const [articles, setArticles] = useState([])
  const [normsMeta, setNormsMeta] = useState(null)
  const [snapshotsFetchDone, setSnapshotsFetchDone] = useState(false)
  const [initialSnapshot, setInitialSnapshot] = useState(null)
  const [articlesLoading, setArticlesLoading] = useState(false)
  const [refChecks, setRefChecks] = useState([])
  const [selectedArticle, setSelectedArticle] = useState(null)
  const [chronology, setChronology] = useState({ timeline: [], related: [], loading: false, error: null })
  const [normRemedy, setNormRemedy] = useState({
    loading: false,
    summary: null,
    edits: [],
    skipped: [],
    warnings: [],
    error: null,
    applyError: null,
    applied: false,
  })
  const [aiChat, setAiChat] = useState({
    chat_id: null,
    messages: [],
    loading: false,
    sending: false,
    error: null,
  })
  const [aiChatInput, setAiChatInput] = useState('')
  const aiChatScrollRef = useRef(null)
  const aiChatTextareaRef = useRef(null)

  const editorRef = useRef(null)
  const titleSaveTimeout = useRef(null)
  const contentSaveTimeout = useRef(null)
  const savedTitleRef = useRef('')
  const analyzedRef = useRef(false)
  const persistSnapshotsTimerRef = useRef(null)

  useEffect(() => {
    if (authLoading) return
    fetch(`${BACKEND}/documents/${id}`, { headers: authHeaders })
      .then(res => res.ok ? res.json() : null)
      .then(data => {
        if (data) {
          setDoc(data)
          setTitle(data.title)
          savedTitleRef.current = data.title
        }
      })
      .finally(() => setLoading(false))

    setAnalysisLoading(true)
    Promise.all([
      fetch(`${BACKEND}/documents/${id}/snapshots`, { headers: authHeaders }).then(r =>
        r.ok ? r.json() : {}
      ),
      fetch(`${BACKEND}/documents/${id}/analysis`, { headers: authHeaders }).then(r =>
        r.ok ? r.json() : null
      ),
    ])
      .then(([snap, freshAnalysis]) => {
        if (snap?.analysis?.entity_analysis) {
          setAnalysis(snap.analysis.entity_analysis)
        } else if (freshAnalysis) {
          setAnalysis(freshAnalysis)
        }
        setInitialSnapshot(snap && typeof snap === 'object' ? snap : {})
      })
      .catch(() => setInitialSnapshot({}))
      .finally(() => {
        setSnapshotsFetchDone(true)
        setAnalysisLoading(false)
      })
  }, [authLoading, id, authHeaders])

  useEffect(() => {
    if (loading || !snapshotsFetchDone || !editorRef.current || analyzedRef.current) return

    const applyNormsFromSnapshot = () => {
      const na = initialSnapshot?.analysis?.norms_analysis
      if (na?.articles?.length) {
        setArticles(na.articles)
        setNormsMeta(na.meta ?? null)
        if (Array.isArray(na.reference_checks)) setRefChecks(na.reference_checks)
        highlightArticlesInDom(editorRef.current, na.articles)
        analyzedRef.current = true
        return true
      }
      return false
    }

    const saved = localStorage.getItem(`doc-content-${id}`)
    if (saved) {
      editorRef.current.innerHTML = saved
      updateWordCount()
      applyNormsFromSnapshot()
      return
    }

    fetch(`${BACKEND}/documents/${id}/text`, { headers: authHeaders })
      .then(res => res.ok ? res.json() : null)
      .then(data => {
        const raw = data?.text || data?.content || (typeof data === 'string' ? data : null)
        if (!raw || !editorRef.current) return
        const html = raw
          .split(/\n{2,}/)
          .map(p => `<p>${p.replace(/\n/g, '<br>')}</p>`)
          .join('')
        editorRef.current.innerHTML = html
        localStorage.setItem(`doc-content-${id}`, html)
        updateWordCount()
        applyNormsFromSnapshot()
      })
      .catch(() => {})
  }, [loading, id, authHeaders, snapshotsFetchDone, initialSnapshot])

  useEffect(() => {
    setNormRemedy({
      loading: false,
      summary: null,
      edits: [],
      skipped: [],
      warnings: [],
      error: null,
      applyError: null,
      applied: false,
    })
    // Fetch chronology when an article is selected
    if (!selectedArticle) {
      setChronology({ timeline: [], related: [], loading: false, error: null })
      return
    }
    const query = selectedArticle.title || selectedArticle.norm_text || ''
    if (!query) return
    setChronology(prev => ({ ...prev, loading: true, error: null }))
    fetch(`${BACKEND}/ai/law-chronology`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', ...authHeaders },
      body: JSON.stringify({
        query,
        title: selectedArticle.title || '',
        language: 'rus',
        top_k: 15,
      }),
    })
      .then(r => r.ok ? r.json() : Promise.reject('Failed'))
      .then(data => setChronology({
        timeline: Array.isArray(data.timeline) ? data.timeline : [],
        related: Array.isArray(data.related) ? data.related : [],
        loading: false,
        error: null,
      }))
      .catch(err => {
        console.error('Chronology fetch failed:', err)
        setChronology({ timeline: [], related: [], loading: false, error: 'Не удалось загрузить хронологию' })
      })
  }, [selectedArticle, authHeaders])

  const solveNormIssue = useCallback(async () => {
    if (!selectedArticle) return
    setNormRemedy((prev) => ({
      ...prev,
      loading: true,
      summary: null,
      edits: [],
      skipped: [],
      warnings: [],
      error: null,
      applyError: null,
      applied: false,
    }))
    try {
      const context = editorRef.current?.innerText?.substring(0, 12000) || ''
      const res = await fetch(`${BACKEND}/ai/remediate-norm`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', ...authHeaders },
        body: JSON.stringify({
          status: selectedArticle.status,
          norm_text: selectedArticle.norm_text,
          title: selectedArticle.title,
          law_url: selectedArticle.law_url,
          law_chunk_preview: selectedArticle.law_chunk_preview,
          usage_context: selectedArticle.usage_context,
          applicability: selectedArticle.applicability,
          current_status_explanation: selectedArticle.current_status_explanation,
          document_context: context,
        }),
      })
      if (res.ok) {
        const data = await res.json()
        setNormRemedy({
          loading: false,
          summary: data.summary || '',
          edits: Array.isArray(data.edits) ? data.edits : [],
          skipped: Array.isArray(data.skipped) ? data.skipped : [],
          warnings: Array.isArray(data.warnings) ? data.warnings : [],
          error: null,
          applyError: null,
          applied: false,
        })
      } else {
        const errText = await res.text().catch(() => '')
        setNormRemedy({
          loading: false,
          summary: null,
          edits: [],
          skipped: [],
          warnings: [],
          error: errText || 'Не удалось подготовить правки',
          applyError: null,
          applied: false,
        })
      }
    } catch (e) {
      console.error(e)
      setNormRemedy({
        loading: false,
        summary: null,
        edits: [],
        skipped: [],
        warnings: [],
        error: 'Ошибка запроса',
        applyError: null,
        applied: false,
      })
    }
  }, [selectedArticle, authHeaders])

  const analyzeDocument = async (text) => {
    if (!text || text.trim().length === 0) {
      setArticles([])
      setNormsMeta(null)
      return
    }

    setArticlesLoading(true)
    try {
      const res = await fetch('/api/analyze-document', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ document_text: text })
      })

      if (!res.ok) throw new Error('Failed to analyze document')

      const data = await res.json()
      const meta = data.meta ?? null
      const foundArticles = Array.isArray(data.articles) ? data.articles : []
      const checks = Array.isArray(data.reference_checks) ? data.reference_checks : []
      setNormsMeta(meta)
      setArticles(foundArticles)
      setRefChecks(checks)
      analyzedRef.current = true

      // Highlight found articles in DOM
      if (editorRef.current && foundArticles.length > 0) {
        highlightArticlesInDom(editorRef.current, foundArticles)
      }

      // Persist analysis results to database immediately
      try {
        const analysisPayload = {
          entity_analysis: analysis,
          norms_analysis: { meta, articles: foundArticles, reference_checks: checks },
          saved_at: new Date().toISOString(),
        }
        await fetch(`${BACKEND}/documents/${id}/snapshots`, {
          method: 'PUT',
          headers: { 'Content-Type': 'application/json', ...authHeaders },
          body: JSON.stringify({ analysis: analysisPayload }),
        })
      } catch (saveErr) {
        console.error('Failed to save analysis to DB:', saveErr)
      }
    } catch (error) {
      console.error('Document analysis error:', error)
      setArticles([])
      setNormsMeta(null)
    } finally {
      setArticlesLoading(false)
    }
  }

  const handleAnalyzeClick = useCallback(() => {
    if (!editorRef.current) return
    const text = editorRef.current.innerText
    analyzeDocument(text)
  }, [analysis, id, authHeaders])

  const exportSnapshotsJson = useCallback(async () => {
    let ai_chat = null
    try {
      const r = await fetch(`${BACKEND}/documents/${id}/ai-chat`, { headers: authHeaders })
      if (r.ok) ai_chat = await r.json()
    } catch {
      /* ignore */
    }
    const payload = {
      document_id: Number(id),
      title: doc?.title ?? null,
      exported_at: new Date().toISOString(),
      analysis: {
        entity_analysis: analysis,
        norms_analysis: { meta: normsMeta, articles, reference_checks: refChecks },
      },
      changes: {
        ai_chat,
      },
    }
    const blob = new Blob([JSON.stringify(payload, null, 2)], { type: 'application/json;charset=utf-8' })
    const a = document.createElement('a')
    a.href = URL.createObjectURL(blob)
    a.download = `document-${id}-analysis-changes.json`
    a.click()
    URL.revokeObjectURL(a.href)
  }, [id, doc, analysis, normsMeta, articles, authHeaders])

  useEffect(() => {
    if (authLoading || !snapshotsFetchDone || !doc) return
    if (persistSnapshotsTimerRef.current) clearTimeout(persistSnapshotsTimerRef.current)
    persistSnapshotsTimerRef.current = setTimeout(async () => {
      try {
        let ai_chat = null
        const ar = await fetch(`${BACKEND}/documents/${id}/ai-chat`, { headers: authHeaders })
        if (ar.ok) ai_chat = await ar.json()
        const analysisPayload = {
          entity_analysis: analysis,
          norms_analysis: { meta: normsMeta, articles, reference_checks: refChecks },
          saved_at: new Date().toISOString(),
        }
        const changesPayload = {
          ai_chat,
          saved_at: new Date().toISOString(),
        }
        await fetch(`${BACKEND}/documents/${id}/snapshots`, {
          method: 'PUT',
          headers: { 'Content-Type': 'application/json', ...authHeaders },
          body: JSON.stringify({ analysis: analysisPayload, changes: changesPayload }),
        })
        try {
          localStorage.setItem(
            `doc-snapshots-${id}`,
            JSON.stringify({ analysis: analysisPayload, changes: changesPayload })
          )
        } catch {
          /* ignore quota */
        }
      } catch (e) {
        console.error('Snapshot save failed', e)
      }
    }, 2000)
    return () => {
      if (persistSnapshotsTimerRef.current) clearTimeout(persistSnapshotsTimerRef.current)
    }
  }, [
    analysis,
    articles,
    refChecks,
    normsMeta,
    id,
    authHeaders,
    snapshotsFetchDone,
    authLoading,
    doc,
  ])

  // Cmd/Ctrl+S
  useEffect(() => {
    const handler = (e) => {
      if ((e.metaKey || e.ctrlKey) && e.key === 's') {
        e.preventDefault()
        saveContent()
      }
    }
    window.addEventListener('keydown', handler)
    return () => window.removeEventListener('keydown', handler)
  }, [id])

  const saveContent = useCallback(() => {
    if (!editorRef.current) return
    localStorage.setItem(`doc-content-${id}`, editorRef.current.innerHTML)
    setSaveStatus('saved')
    setTimeout(() => setSaveStatus('idle'), 2000)
  }, [id])

  const updateWordCount = () => {
    if (!editorRef.current) return
    const text = editorRef.current.innerText || ''
    setWordCount(text.trim().split(/\s+/).filter(Boolean).length)
  }

  const applyNormEdits = useCallback(() => {
    const edits = normRemedy.edits
    if (!editorRef.current || !edits?.length) return
    const sorted = [...edits].sort((a, b) => b.find.length - a.find.length)
    const appliedEdits = [...sorted]
    let text = editorRef.current.innerText
    for (const e of sorted) {
      const idx = text.indexOf(e.find)
      if (idx === -1) {
        setNormRemedy((prev) => ({
          ...prev,
          applyError: `Фрагмент не найден в тексте: «${e.find.slice(0, 96)}${e.find.length > 96 ? '…' : ''}»`,
        }))
        return
      }
      text = text.slice(0, idx) + e.replace + text.slice(idx + e.find.length)
    }
    const html = text.split(/\n{2,}/).map((p) => `<p>${p.replace(/\n/g, '<br>')}</p>`).join('')
    editorRef.current.innerHTML = html
    localStorage.setItem(`doc-content-${id}`, html)
    setSaveStatus('unsaved')
    setNormRemedy((prev) => ({
      ...prev,
      edits: [],
      applied: true,
      applyError: null,
    }))
    updateWordCount()
    clearTimeout(contentSaveTimeout.current)
    contentSaveTimeout.current = setTimeout(saveContent, 1500)

    const normLabel = selectedArticle?.norm_text || ''
    for (const e of appliedEdits) {
      fetch(`${BACKEND}/documents/${id}/corrections`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', ...authHeaders },
        body: JSON.stringify({
          error_id: null,
          error_type: 'norm_remedy',
          title: normLabel ? `Правка: ${normLabel.slice(0, 80)}` : 'Правка нормы',
          original_text: e.find,
          suggestion: e.replace,
          reason: null,
        }),
      }).catch(() => {})
    }
  }, [normRemedy.edits, id, saveContent, authHeaders, selectedArticle])

  const updateActiveFormats = () => {
    setActiveFormats({
      bold: document.queryCommandState('bold'),
      italic: document.queryCommandState('italic'),
      underline: document.queryCommandState('underline'),
      insertUnorderedList: document.queryCommandState('insertUnorderedList'),
      insertOrderedList: document.queryCommandState('insertOrderedList'),
    })
  }

  const handleContentInput = () => {
    updateWordCount()
    updateActiveFormats()
    setSaveStatus('unsaved')
    clearTimeout(contentSaveTimeout.current)
    contentSaveTimeout.current = setTimeout(saveContent, 1500)
  }

  const handleTitleChange = (e) => {
    const val = e.target.value
    setTitle(val)
    setSaveStatus('unsaved')
    clearTimeout(titleSaveTimeout.current)
    titleSaveTimeout.current = setTimeout(async () => {
      if (!val.trim() || val === savedTitleRef.current) return
      setSaveStatus('saving')
      try {
        const res = await fetch(`${BACKEND}/documents/${id}`, {
          method: 'PATCH',
          headers: { ...authHeaders, 'Content-Type': 'application/json' },
          body: JSON.stringify({ title: val }),
        })
        if (res.ok) {
          setDoc(await res.json())
          savedTitleRef.current = val
          setSaveStatus('saved')
          setTimeout(() => setSaveStatus('idle'), 2000)
        }
      } catch {
        setSaveStatus('unsaved')
      }
    }, 800)
  }

  const fmt = (cmd, value = null) => {
    document.execCommand(cmd, false, value)
    editorRef.current?.focus()
    handleContentInput()
    updateActiveFormats()
  }

  const insertHr = () => {
    document.execCommand('insertHTML', false, '<hr style="border:none;border-top:1px solid #e5e7eb;margin:1.5rem 0"/><p><br></p>')
    editorRef.current?.focus()
    handleContentInput()
  }

  function getClassificationColor(classification) {
    if (!classification) return 'bg-gray-50'
    if (classification.toLowerCase().includes('действи') || classification.toLowerCase().includes('valid')) return 'bg-green-50'
    if (classification.toLowerCase().includes('устар') || classification.toLowerCase().includes('old')) return 'bg-gray-100'
    if (classification.toLowerCase().includes('недейст') || classification.toLowerCase().includes('invalid')) return 'bg-red-50'
    return 'bg-gray-50'
  }

  function getClassificationDotColor(classification) {
    if (!classification) return '#D1D5DB'
    if (classification.toLowerCase().includes('действи') || classification.toLowerCase().includes('valid')) return '#10B981'
    if (classification.toLowerCase().includes('устар') || classification.toLowerCase().includes('old')) return '#9CA3AF'
    if (classification.toLowerCase().includes('недейст') || classification.toLowerCase().includes('invalid')) return '#EF4444'
    return '#D1D5DB'
  }

  const loadAiChat = useCallback(async () => {
    setAiChat(prev => ({ ...prev, loading: true, error: null }))
    try {
      const r = await fetch(`${BACKEND}/documents/${id}/ai-chat`, { headers: authHeaders })
      if (!r.ok) throw new Error('fail')
      const data = await r.json()
      setAiChat(prev => ({
        ...prev,
        chat_id: data.chat_id,
        messages: data.messages || [],
        loading: false,
      }))
    } catch {
      setAiChat(prev => ({ ...prev, loading: false, error: 'Не удалось загрузить чат' }))
    }
  }, [id, authHeaders])

  useEffect(() => {
    if (authLoading || activePanel !== 'ai_chat') return
    loadAiChat()
  }, [activePanel, authLoading, loadAiChat])

  useEffect(() => {
    if (activePanel !== 'ai_chat') return
    const el = aiChatScrollRef.current
    if (!el) return
    requestAnimationFrame(() => {
      el.scrollTop = el.scrollHeight
    })
  }, [aiChat.messages, activePanel])

  const sendAiChatMessage = useCallback(async () => {
    const text = aiChatInput.trim()
    if (!text || aiChat.sending) return
    const docPlain = editorRef.current?.innerText || ''
    setAiChat(prev => ({ ...prev, sending: true, error: null }))
    try {
      const r = await fetch(`${BACKEND}/documents/${id}/ai-chat/message`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', ...authHeaders },
        body: JSON.stringify({ message: text, document_plain_text: docPlain }),
      })
      if (!r.ok) {
        let detail = 'Ошибка запроса'
        try {
          const err = await r.json()
          if (err.detail) detail = typeof err.detail === 'string' ? err.detail : JSON.stringify(err.detail)
        } catch { /* ignore */ }
        throw new Error(detail)
      }
      const data = await r.json()
      setAiChatInput('')
      setAiChat(prev => ({
        ...prev,
        chat_id: data.chat_id,
        messages: data.messages || [],
        sending: false,
      }))
      requestAnimationFrame(() => {
        aiChatTextareaRef.current?.focus({ preventScroll: true })
      })
    } catch (e) {
      setAiChat(prev => ({
        ...prev,
        sending: false,
        error: e.message || 'Ошибка',
      }))
    }
  }, [aiChatInput, aiChat.sending, id, authHeaders])

  const approveAiChat = useCallback(async (messageId) => {
    const docPlain = editorRef.current?.innerText || ''
    setAiChat(prev => ({ ...prev, error: null }))
    try {
      const r = await fetch(`${BACKEND}/documents/${id}/ai-chat/approve`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', ...authHeaders },
        body: JSON.stringify({ message_id: messageId, document_plain_text: docPlain }),
      })
      const data = await r.json()
      if (!data.ok) {
        setAiChat(prev => ({ ...prev, error: data.detail || 'Не удалось применить' }))
        return
      }
      if (data.merged_plain && editorRef.current) {
        const html = data.merged_plain
          .split(/\n{2,}/)
          .map((p) => `<p>${p.replace(/\n/g, '<br>')}</p>`)
          .join('')
        const ed = editorRef.current
        const scrollEl = ed.closest('.overflow-y-auto')
        const editorScrollTop = scrollEl?.scrollTop ?? 0
        const winY = window.scrollY
        ed.innerHTML = html
        localStorage.setItem(`doc-content-${id}`, html)
        updateWordCount()
        setSaveStatus('unsaved')
        requestAnimationFrame(() => {
          window.scrollTo(window.scrollX, winY)
          if (scrollEl) scrollEl.scrollTop = editorScrollTop
          aiChatTextareaRef.current?.focus({ preventScroll: true })
        })
      }
      await loadAiChat()
    } catch (e) {
      setAiChat(prev => ({ ...prev, error: e.message || 'Ошибка' }))
    }
  }, [id, authHeaders, loadAiChat])

  const rejectAiChat = useCallback(async (messageId) => {
    try {
      const r = await fetch(`${BACKEND}/documents/${id}/ai-chat/reject`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', ...authHeaders },
        body: JSON.stringify({ message_id: messageId }),
      })
      if (!r.ok) return
      await loadAiChat()
    } catch { /* ignore */ }
  }, [id, authHeaders, loadAiChat])


  if (authLoading || loading) {
    return (
      <div className="flex h-screen bg-gray-50">
        <Sidebar />
        <main className="flex-1 flex items-center justify-center">
          <Loader2 size={24} className="animate-spin text-gray-300" />
        </main>
      </div>
    )
  }

  return (
    <div className="flex h-screen bg-gray-50">
      <Sidebar />

      <main className="flex-1 overflow-hidden min-w-0 py-4 pr-4 flex flex-col">
        <div className="rounded-2xl border border-gray-300 bg-white shadow-sm h-full flex flex-row overflow-hidden">
          <div className="flex-1 flex flex-col overflow-hidden">

          {/* Top bar */}
          <div className="flex items-center justify-between px-5 py-3 border-b border-gray-100">
            <button
              type="button"
              onClick={() => router.push('/documents')}
              className="flex items-center gap-1.5 text-sm text-gray-400 hover:text-gray-700 transition-colors"
            >
              <ArrowLeft size={15} />
              Документы
            </button>

            <div className="flex items-center gap-4">
              <SaveStatus status={saveStatus} />
              {doc?.status && (
                <span className="bg-gray-100 text-gray-500 text-xs px-2.5 py-0.5 rounded-full">{doc.status}</span>
              )}
              <button
                type="button"
                onMouseDown={e => e.preventDefault()}
                onClick={saveContent}
                className="bg-brand hover:bg-brand-hover transition-colors text-ink font-semibold text-xs px-3 py-1.5 rounded-full flex items-center gap-1.5"
              >
                <Check size={12} />
                Сохранить
              </button>
            </div>
          </div>

          {/* Formatting toolbar */}
          <div className="flex items-center gap-0.5 px-5 py-2 border-b border-gray-100">
            <ToolbarBtn onClick={() => fmt('undo')} title="Отменить (⌘Z)"><Undo size={15} /></ToolbarBtn>
            <ToolbarBtn onClick={() => fmt('redo')} title="Повторить (⌘⇧Z)"><Redo size={15} /></ToolbarBtn>

            <div className="w-px h-4 bg-gray-200 mx-1.5" />

            <ToolbarBtn onClick={() => fmt('bold')} active={activeFormats.bold} title="Жирный (⌘B)"><Bold size={15} /></ToolbarBtn>
            <ToolbarBtn onClick={() => fmt('italic')} active={activeFormats.italic} title="Курсив (⌘I)"><Italic size={15} /></ToolbarBtn>
            <ToolbarBtn onClick={() => fmt('underline')} active={activeFormats.underline} title="Подчёркнутый (⌘U)"><Underline size={15} /></ToolbarBtn>

            <div className="w-px h-4 bg-gray-200 mx-1.5" />

            <ToolbarBtn onClick={() => fmt('formatBlock', 'h1')} title="Заголовок 1"><Heading1 size={15} /></ToolbarBtn>
            <ToolbarBtn onClick={() => fmt('formatBlock', 'h2')} title="Заголовок 2"><Heading2 size={15} /></ToolbarBtn>
            <ToolbarBtn onClick={() => fmt('formatBlock', 'p')} title="Обычный текст">
              <span className="text-xs font-medium leading-none">¶</span>
            </ToolbarBtn>

            <div className="w-px h-4 bg-gray-200 mx-1.5" />

            <ToolbarBtn onClick={() => fmt('insertUnorderedList')} active={activeFormats.insertUnorderedList} title="Маркированный список"><List size={15} /></ToolbarBtn>
            <ToolbarBtn onClick={() => fmt('insertOrderedList')} active={activeFormats.insertOrderedList} title="Нумерованный список"><ListOrdered size={15} /></ToolbarBtn>
            <ToolbarBtn onClick={insertHr} title="Разделитель"><Minus size={15} /></ToolbarBtn>

            <div className="ml-auto text-xs text-gray-300">
              {wordCount} {wordCount === 1 ? 'слово' : wordCount < 5 ? 'слова' : 'слов'}
            </div>
          </div>

          {/* Editor area */}
          <div className="flex-1 overflow-y-auto">
            <div className="max-w-3xl mx-auto px-16 py-10">

              {/* Title */}
              <input
                type="text"
                value={title}
                onChange={handleTitleChange}
                placeholder="Название документа"
                className="w-full text-4xl font-bold text-ink outline-none border-none bg-transparent placeholder-gray-200 mb-2"
              />

              {/* Meta */}
              {doc && (doc.classification || doc.category || doc.jurisdiction || doc.law_number) && (
                <div className="flex flex-wrap gap-2 mb-8">
                  {doc.classification && <span className="bg-blue-50 text-blue-700 text-xs px-2.5 py-1 rounded-full font-medium">{doc.classification}</span>}
                  {doc.category && <span className="bg-gray-100 text-gray-600 text-xs px-2.5 py-1 rounded-full">{doc.category}</span>}
                  {doc.jurisdiction && <span className="bg-gray-100 text-gray-600 text-xs px-2.5 py-1 rounded-full">{doc.jurisdiction}</span>}
                  {doc.law_number && <span className="bg-amber-50 text-amber-700 text-xs px-2.5 py-1 rounded-full">№ {doc.law_number}</span>}
                </div>
              )}

              <div className="w-full h-px bg-gray-100 mb-8" />

              {/* ContentEditable body */}
              <div
                ref={editorRef}
                contentEditable
                suppressContentEditableWarning
                onInput={handleContentInput}
                onKeyUp={updateActiveFormats}
                onMouseUp={(e) => {
                  updateActiveFormats()
                  const span = e.target.closest('[data-norm]')
                  if (span) {
                    const normText = span.getAttribute('data-norm')
                    const foundArticle = articles.find(a => a.norm_text === normText)
                    if (foundArticle) {
                      setSelectedArticle(foundArticle)
                      setActivePanel('chronology')
                    }
                  }
                }}
                onSelect={updateActiveFormats}
                data-placeholder="Начните вводить текст..."
                className="editor-body outline-none min-h-[50vh] text-gray-800 text-base leading-7"
              />
            </div>
          </div>

          </div>

          <DocumentRightPanel
            activePanel={activePanel}
            setActivePanel={setActivePanel}
            exportSnapshotsJson={exportSnapshotsJson}
            normsMeta={normsMeta}
            handleAnalyzeClick={handleAnalyzeClick}
            articlesLoading={articlesLoading}
            articles={articles}
            refChecks={refChecks}
            setSelectedArticle={setSelectedArticle}
            selectedArticle={selectedArticle}
            normRemedy={normRemedy}
            solveNormIssue={solveNormIssue}
            applyNormEdits={applyNormEdits}
            chronology={chronology}
            aiChat={aiChat}
            aiChatInput={aiChatInput}
            setAiChatInput={setAiChatInput}
            aiChatScrollRef={aiChatScrollRef}
            aiChatTextareaRef={aiChatTextareaRef}
            sendAiChatMessage={sendAiChatMessage}
            approveAiChat={approveAiChat}
            rejectAiChat={rejectAiChat}
          />
        </div>
      </main>
    </div>
  )
}
