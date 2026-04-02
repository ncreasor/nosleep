'use client'

import { useState, useEffect, useRef, useCallback } from 'react'
import { useParams, useRouter } from 'next/navigation'
import Sidebar from '@/components/Sidebar'
import { useAuth } from '@/components/useAuth'
import {
  ArrowLeft, Check, Loader2, Bold, Italic, Underline,
  List, ListOrdered, Heading1, Heading2, Minus, Redo, Undo,
  ChevronRight, Trash2, MessageCircle, CheckCircle2, Scale,
} from 'lucide-react'

const BACKEND = process.env.NEXT_PUBLIC_BACKEND_URL || 'http://localhost:8000'

// Regex patterns for legal norms (Kazakh legislation)
const NORM_REGEX = /(?:(?:ч\.\s*\d+\s+)?(?:п\.\s*\d+(?:-\d+)?\s+)?ст\.\s*\d+(?:\.\d+)?\s+(?:ГК|ТК|УК|УПК|ГПК|КоАП|НК|ЖК|СК|КоИС|ЗК)\s+РК|[Сс]тать(?:я|и|ью?|ей)\s+\d+(?:\.\d+)?|Закон(?:\s+Республики\s+Казахстан|\s+РК)\s+от\s+[\d.]+\s+(?:года\s+)?№\s*[\d\-]+(?:-[IVX]+[ЗРК]*)?|ЗРК-\d+(?:-[IVX]+)?)/g

function highlightNormsInDom(container) {
  if (!container || container.querySelector('[data-norm]')) return

  const walker = document.createTreeWalker(
    container,
    NodeFilter.SHOW_TEXT,
    null,
    false
  )

  const nodesToReplace = []
  let node

  while (node = walker.nextNode()) {
    if (/\S/.test(node.nodeValue)) {
      const matches = Array.from(node.nodeValue.matchAll(NORM_REGEX))
      if (matches.length > 0) {
        nodesToReplace.push({ node, matches })
      }
    }
  }

  nodesToReplace.forEach(({ node, matches }) => {
    const fragment = document.createDocumentFragment()
    let lastIndex = 0

    matches.forEach(match => {
      if (match.index > lastIndex) {
        fragment.appendChild(
          document.createTextNode(node.nodeValue.slice(lastIndex, match.index))
        )
      }

      const span = document.createElement('span')
      span.setAttribute('data-norm', match[0])
      span.setAttribute('data-norm-status', 'pending')
      span.className = 'norm-highlight norm-pending'
      span.textContent = match[0]
      fragment.appendChild(span)

      lastIndex = match.index + match[0].length
    })

    if (lastIndex < node.nodeValue.length) {
      fragment.appendChild(
        document.createTextNode(node.nodeValue.slice(lastIndex))
      )
    }

    node.parentNode.replaceChild(fragment, node)
  })
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
  const [selectedNorm, setSelectedNorm] = useState(null)
  const [normLoading, setNormLoading] = useState(false)

  const editorRef = useRef(null)
  const titleSaveTimeout = useRef(null)
  const contentSaveTimeout = useRef(null)
  const savedTitleRef = useRef('')
  const normCache = useRef({})

  // Load document metadata and analysis
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

    // Fetch analysis data
    setAnalysisLoading(true)
    fetch(`${BACKEND}/documents/${id}/analysis`, { headers: authHeaders })
      .then(res => res.ok ? res.json() : null)
      .then(data => setAnalysis(data))
      .catch(() => {})
      .finally(() => setAnalysisLoading(false))
  }, [authLoading, id])

  // Load content: localStorage first, then backend text endpoint for PDFs
  useEffect(() => {
    if (loading || !editorRef.current) return

    const saved = localStorage.getItem(`doc-content-${id}`)
    if (saved) {
      editorRef.current.innerHTML = saved
      updateWordCount()
      return
    }

    // No local content — fetch from backend (PDF text extraction)
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
      })
      .catch(() => {})
  }, [loading, id])

  // Highlight norms and fetch their statuses
  useEffect(() => {
    if (!editorRef.current || loading) return

    highlightNormsInDom(editorRef.current)

    const normSpans = editorRef.current.querySelectorAll('[data-norm]')
    const uniqueNorms = Array.from(new Set(Array.from(normSpans).map(span => span.getAttribute('data-norm'))))

    if (uniqueNorms.length > 0) {
      fetchNormStatuses(uniqueNorms)
    }
  }, [loading, id])

  const fetchNormStatuses = async (uniqueNorms) => {
    const uncached = uniqueNorms.filter(n => !normCache.current[n])
    if (uncached.length === 0) return

    setNormLoading(true)
    try {
      const res = await fetch('/api/norm-check', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ norms: uncached })
      })

      if (!res.ok) throw new Error('Failed to fetch norm statuses')

      const { results } = await res.json()

      // Update cache
      Object.assign(normCache.current, results)

      // Update DOM classes
      document.querySelectorAll('[data-norm]').forEach(span => {
        const normText = span.getAttribute('data-norm')
        const data = normCache.current[normText]
        if (data) {
          span.removeAttribute('data-norm-status')
          span.classList.remove('norm-pending')
          span.classList.add(`norm-${data.status}`)
        }
      })
    } catch (error) {
      console.error('Norm status fetch error:', error)
    } finally {
      setNormLoading(false)
    }
  }

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

  function RightPanel() {
    return (
      <div className="w-80 bg-white border-l border-gray-200 flex flex-col overflow-hidden">
        {/* Tabs */}
        <div className="flex border-b border-gray-200 sticky top-0 bg-white">
          {['analysis', 'chronology', 'formulation'].map(tab => (
            <button
              key={tab}
              onClick={() => setActivePanel(tab)}
              className={`flex-1 py-3 text-xs font-medium transition-colors border-b-2 ${
                activePanel === tab
                  ? 'text-ink border-b-brand'
                  : 'text-gray-500 border-b-transparent hover:text-gray-700'
              }`}
            >
              {tab === 'analysis' && 'ИИ Анализ'}
              {tab === 'chronology' && 'Хронология'}
              {tab === 'formulation' && 'Формулировка'}
            </button>
          ))}
        </div>

        {/* Content */}
        <div className="flex-1 overflow-y-auto p-4">
          {activePanel === 'analysis' && (
            <div className="space-y-4">
              {analysisLoading ? (
                <div className="flex items-center justify-center py-8">
                  <Loader2 size={16} className="animate-spin text-gray-300" />
                </div>
              ) : !analysis ? (
                <p className="text-xs text-gray-400">Анализ недоступен</p>
              ) : (
                <>
                  {/* Summary */}
                  {analysis.summary && (
                    <div className="p-3 bg-blue-50 rounded-lg border border-blue-100">
                      <p className="text-xs text-blue-900">{analysis.summary}</p>
                    </div>
                  )}

                  {/* Articles/Relations */}
                  <div className="space-y-2">
                    {doc?.classification && (
                      <div className={`p-3 rounded-lg border border-gray-200 ${getClassificationColor(doc.classification)}`}>
                        <div className="flex items-start gap-2">
                          <div
                            className="w-2 h-2 rounded-full mt-1 flex-shrink-0"
                            style={{ backgroundColor: getClassificationDotColor(doc.classification) }}
                          />
                          <div className="min-w-0 flex-1">
                            <p className="text-xs font-medium text-gray-900">Классификация</p>
                            <p className="text-xs text-gray-600 mt-0.5">{doc.classification}</p>
                          </div>
                        </div>
                      </div>
                    )}

                    {analysis?.relations && Array.isArray(analysis.relations) && analysis.relations.length > 0 && (
                      <>
                        <p className="text-xs font-medium text-gray-600 mt-4">Связанные статьи</p>
                        {analysis.relations.slice(0, 5).map((relation, idx) => (
                          <div key={idx} className="p-3 rounded-lg border border-gray-200 hover:border-gray-300 transition-colors">
                            <div className="flex items-start gap-2">
                              <div
                                className="w-2 h-2 rounded-full mt-1 flex-shrink-0"
                                style={{ backgroundColor: getClassificationDotColor(relation.status || relation.classification) }}
                              />
                              <div className="min-w-0 flex-1">
                                <p className="text-xs font-medium text-gray-900 line-clamp-2">{relation.name || relation.title}</p>
                                {relation.description && <p className="text-xs text-gray-500 mt-1 line-clamp-2">{relation.description}</p>}
                              </div>
                            </div>
                          </div>
                        ))}
                      </>
                    )}

                    {!analysis?.relations || analysis.relations.length === 0 ? (
                      <p className="text-xs text-gray-400 text-center py-4">Данные не доступны</p>
                    ) : null}
                  </div>
                </>
              )}
            </div>
          )}

          {activePanel === 'chronology' && (
            <div className="space-y-4">
              {!selectedNorm ? (
                <div className="flex flex-col items-center justify-center py-12 text-center">
                  <div className="w-10 h-10 rounded-full bg-gray-100 flex items-center justify-center mb-3">
                    <Scale size={18} className="text-gray-400" />
                  </div>
                  <p className="text-xs text-gray-500 font-medium">Кликните на выделенную норму</p>
                  <p className="text-xs text-gray-400 mt-1">чтобы увидеть её историю</p>
                </div>
              ) : normLoading ? (
                <div className="space-y-3 animate-pulse">
                  <div className="h-6 bg-gray-100 rounded w-24" />
                  <div className="h-4 bg-gray-100 rounded w-48" />
                  <div className="h-3 bg-gray-100 rounded w-full mt-4" />
                  <div className="h-3 bg-gray-100 rounded w-3/4" />
                </div>
              ) : selectedNorm.data ? (
                <>
                  {/* Status badge */}
                  <div className="flex items-center gap-2">
                    {(() => {
                      const status = selectedNorm.data.status
                      const labelMap = { valid: 'ДЕЙСТВУЕТ', outdated: 'УСТАРЕЛА', invalid: 'НЕ СУЩЕСТВУЕТ' }
                      const classMap = {
                        valid: 'bg-green-100 text-green-800',
                        outdated: 'bg-gray-100 text-gray-800',
                        invalid: 'bg-red-100 text-red-800'
                      }
                      return (
                        <span className={`text-xs font-semibold px-2.5 py-1 rounded-full ${classMap[status] || classMap.valid}`}>
                          {labelMap[status] || status}
                        </span>
                      )
                    })()}
                  </div>

                  {/* Norm title */}
                  <div>
                    <p className="text-sm font-semibold text-gray-900 leading-snug">
                      {selectedNorm.data.title || selectedNorm.text}
                    </p>
                    {selectedNorm.data.title && (
                      <p className="text-xs text-gray-400 mt-0.5">{selectedNorm.text}</p>
                    )}
                  </div>

                  {/* Timeline */}
                  {(() => {
                    const entries = []
                    if (selectedNorm.data.introduced) {
                      entries.push({ date: selectedNorm.data.introduced, label: 'Введена', type: 'introduced' })
                    }
                    if (selectedNorm.data.amendments && Array.isArray(selectedNorm.data.amendments)) {
                      selectedNorm.data.amendments.forEach(a => {
                        entries.push({ date: a.date, label: a.description, type: 'amendment' })
                      })
                    }
                    entries.sort((a, b) => a.date.localeCompare(b.date))

                    return entries.length > 0 ? (
                      <div className="border-t border-gray-100 pt-4">
                        <p className="text-xs font-medium text-gray-500 mb-3 uppercase tracking-wide">Хронология</p>
                        <div className="space-y-0">
                          {entries.map((entry, idx) => (
                            <div key={idx} className="flex gap-3">
                              <div className="flex flex-col items-center">
                                <div className={`w-2 h-2 rounded-full ${
                                  entry.type === 'introduced' ? 'bg-blue-400' :
                                  entry.type === 'amendment' ? 'bg-gray-400' :
                                  'bg-green-500'
                                } mt-1.5 flex-shrink-0`} />
                                {idx < entries.length - 1 && <div className="w-px h-3 bg-gray-200" />}
                              </div>
                              <div className="pb-3 min-w-0">
                                <p className="text-xs font-medium text-gray-800 leading-snug">{entry.label}</p>
                                <p className="text-xs text-gray-400 mt-0.5">
                                  {new Date(entry.date).toLocaleDateString('ru-RU', {
                                    day: 'numeric', month: 'long', year: 'numeric'
                                  })}
                                </p>
                              </div>
                            </div>
                          ))}
                        </div>
                      </div>
                    ) : null
                  })()}

                  {/* Explanation */}
                  {selectedNorm.data.current_status_explanation && (
                    <div className="p-3 bg-gray-50 rounded-lg border border-gray-200">
                      <p className="text-xs text-gray-700 leading-relaxed">
                        {selectedNorm.data.current_status_explanation}
                      </p>
                    </div>
                  )}
                </>
              ) : (
                <p className="text-xs text-gray-400 text-center py-4">Норма не найдена</p>
              )}
            </div>
          )}

          {activePanel === 'formulation' && (
            <div className="space-y-3">
              <div className="space-y-2">
                {analysis?.errors && Array.isArray(analysis.errors) && analysis.errors.length > 0 ? (
                  analysis.errors.slice(0, 5).map((error, idx) => (
                    <div key={idx} className="p-3 rounded-lg border border-gray-200 hover:border-gray-300 transition-colors">
                      <p className="text-xs text-gray-900 mb-2">{error.text || error.description || error.message}</p>
                      <div className="flex gap-2">
                        <button className="flex-1 flex items-center justify-center gap-1 px-2 py-1.5 text-xs font-medium text-green-700 bg-green-50 rounded hover:bg-green-100 transition-colors">
                          <CheckCircle2 size={12} />
                          Принять
                        </button>
                        <button className="flex-1 flex items-center justify-center gap-1 px-2 py-1.5 text-xs font-medium text-blue-700 bg-blue-50 rounded hover:bg-blue-100 transition-colors">
                          <MessageCircle size={12} />
                          Спросить
                        </button>
                        <button className="flex items-center justify-center px-2 py-1.5 text-xs font-medium text-gray-600 hover:text-red-600 hover:bg-red-50 rounded transition-colors">
                          <Trash2 size={12} />
                        </button>
                      </div>
                    </div>
                  ))
                ) : (
                  <p className="text-xs text-gray-400 text-center py-8">Ошибки не найдены</p>
                )}
              </div>
            </div>
          )}
        </div>
      </div>
    )
  }

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
                    const data = normCache.current[normText]
                    setSelectedNorm({ text: normText, data })
                    setActivePanel('chronology')
                  }
                }}
                onSelect={updateActiveFormats}
                data-placeholder="Начните вводить текст..."
                className="editor-body outline-none min-h-[50vh] text-gray-800 text-base leading-7"
              />
            </div>
          </div>

          </div>

          <RightPanel />
        </div>
      </main>
    </div>
  )
}
