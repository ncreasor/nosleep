'use client'

import { useState, useEffect, useRef, useCallback } from 'react'
import { useParams, useRouter } from 'next/navigation'
import Sidebar from '@/components/Sidebar'
import { useAuth } from '@/components/useAuth'
import {
  ArrowLeft, Check, Loader2, Bold, Italic, Underline,
  List, ListOrdered, Heading1, Heading2, Minus, Redo, Undo,
  ChevronRight, Trash2, X, BarChart2, GitBranch, Sparkles, AlertCircle,
} from 'lucide-react'

const BACKEND = process.env.NEXT_PUBLIC_BACKEND_URL || 'http://localhost:8000'

function highlightArticlesInDom(container, articles) {
  if (!container || !articles || articles.length === 0) return

  let html = container.innerHTML
  const originalHtml = html

  // Sort by norm_text length (longest first) to avoid partial replacements
  const sortedArticles = [...articles].sort((a, b) => b.norm_text.length - a.norm_text.length)

  for (const article of sortedArticles) {
    const normText = article.norm_text
    // Escape special regex chars in norm_text
    const escaped = normText.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
    const regex = new RegExp(`(${escaped})(?!<)`, 'g')

    const statusClass = `norm-${article.status}`
    html = html.replace(regex, `<span data-norm="${normText}" class="norm-highlight ${statusClass}">$1</span>`)
  }

  if (html !== originalHtml) {
    container.innerHTML = html
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
  const [articlesLoading, setArticlesLoading] = useState(false)
  const [selectedArticle, setSelectedArticle] = useState(null)
  const [errors, setErrors] = useState([])
  const [errorsSummary, setErrorsSummary] = useState('')
  const [errorsLoading, setErrorsLoading] = useState(false)
  const [dismissedErrors, setDismissedErrors] = useState(new Set())
  const [askModal, setAskModal] = useState(null)

  const editorRef = useRef(null)
  const titleSaveTimeout = useRef(null)
  const contentSaveTimeout = useRef(null)
  const savedTitleRef = useRef('')
  const analyzedRef = useRef(false)

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

  // Load document errors (lazy load when Formulation tab opened)
  useEffect(() => {
    if (activePanel !== 'formulation' || errors.length > 0 || errorsLoading) return
    setErrorsLoading(true)
    fetch(`${BACKEND}/documents/${id}/errors`, { headers: authHeaders })
      .then(res => res.ok ? res.json() : null)
      .then(data => {
        if (data) {
          setErrorsSummary(data.summary || '')
          setErrors(data.errors || [])
        }
      })
      .catch(err => console.error('Failed to load errors:', err))
      .finally(() => setErrorsLoading(false))
  }, [activePanel, id, authHeaders])

  // Load content: localStorage first, then backend text endpoint for PDFs
  useEffect(() => {
    if (loading || !editorRef.current || analyzedRef.current) return

    const saved = localStorage.getItem(`doc-content-${id}`)
    if (saved) {
      editorRef.current.innerHTML = saved
      updateWordCount()
      analyzedRef.current = true
      analyzeDocument(editorRef.current.innerText)
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
        analyzedRef.current = true
        analyzeDocument(raw)
      })
      .catch(() => {})
  }, [loading, id, authHeaders])

  const analyzeDocument = async (text) => {
    if (!text || text.trim().length === 0) {
      setArticles([])
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

      const { articles: foundArticles } = await res.json()
      setArticles(foundArticles || [])

      // Highlight found articles in DOM
      if (editorRef.current && foundArticles && foundArticles.length > 0) {
        highlightArticlesInDom(editorRef.current, foundArticles)
      }
    } catch (error) {
      console.error('Document analysis error:', error)
      setArticles([])
    } finally {
      setArticlesLoading(false)
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
    // Tabs array with icons
    const tabs = [
      { id: 'analysis', label: 'ИИ Анализ', Icon: BarChart2 },
      { id: 'chronology', label: 'Хронология', Icon: GitBranch },
      { id: 'formulation', label: 'Формулировка', Icon: Sparkles }
    ]

    const acceptFix = (error) => {
      if (!editorRef.current || !error.original_text) return
      const html = editorRef.current.innerHTML
      const updated = html.replace(
        error.original_text,
        `<mark class="norm-fixed">${error.suggestion}</mark>`
      )
      if (updated !== html) {
        editorRef.current.innerHTML = updated
        localStorage.setItem(`doc-content-${id}`, updated)
        setErrors(prev => prev.filter(e => e.id !== error.id))
        setSaveStatus('unsaved')
      }
    }

    const askAboutError = async (error) => {
      setAskModal({ error, loading: true, explanation: null })
      try {
        const context = editorRef.current?.textContent.substring(0, 2000) || ''
        const res = await fetch(`${BACKEND}/ai/explain-error`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json', ...authHeaders },
          body: JSON.stringify({
            error_title: error.title,
            original_text: error.original_text,
            suggestion: error.suggestion,
            reason: error.reason,
            document_context: context
          })
        })
        if (res.ok) {
          const data = await res.json()
          setAskModal({ error, loading: false, explanation: data.explanation })
        } else {
          setAskModal({ error, loading: false, explanation: 'Не удалось получить объяснение' })
        }
      } catch (err) {
        console.error('Error asking about error:', err)
        setAskModal({ error, loading: false, explanation: 'Ошибка запроса' })
      }
    }

    const dismissError = (id) => {
      setDismissedErrors(prev => new Set([...prev, id]))
    }

    const visibleErrors = errors.filter(e => !dismissedErrors.has(e.id))

    return (
      <div className="w-80 bg-white border-l border-gray-200 flex flex-col overflow-hidden">
        {/* Tab bar with grid layout */}
        <div className="grid grid-cols-3 gap-2 p-3 border-b border-gray-100 bg-white">
          {tabs.map(tab => (
            <button
              key={tab.id}
              onClick={() => setActivePanel(tab.id)}
              className={`flex flex-col items-center gap-1 py-3 px-2 rounded-xl border-2 transition-all ${
                activePanel === tab.id
                  ? 'bg-[#ADFF5E] border-[#ADFF5E]'
                  : 'bg-white border-gray-200 hover:border-gray-300'
              }`}
            >
              <tab.Icon size={16} className={activePanel === tab.id ? 'text-gray-900' : 'text-gray-600'} />
              <span className={`text-xs font-semibold ${activePanel === tab.id ? 'text-gray-900' : 'text-gray-600'}`}>
                {tab.label}
              </span>
            </button>
          ))}
        </div>

        {/* Content area */}
        <div className="flex-1 overflow-y-auto p-4">
          {/* Analysis Tab - List of articles */}
          {activePanel === 'analysis' && (
            <div className="space-y-4">
              <p className="text-xs font-semibold text-gray-700 uppercase">Статьи документа</p>

              {articlesLoading ? (
                <div className="flex items-center justify-center py-8">
                  <Loader2 size={16} className="animate-spin text-gray-300" />
                </div>
              ) : articles.length === 0 ? (
                <p className="text-xs text-gray-400 text-center py-8">Нормативные ссылки не найдены</p>
              ) : (
                <div className="space-y-3">
                  {articles.map((article, idx) => (
                    <div
                      key={idx}
                      onClick={() => {
                        setSelectedArticle(article)
                        setActivePanel('chronology')
                      }}
                      className={`flex items-start gap-3 p-4 rounded-xl border cursor-pointer hover:shadow-sm transition-all ${
                        article.status === 'valid'
                          ? 'bg-green-50 border-green-200'
                          : article.status === 'outdated'
                          ? 'bg-gray-50 border-gray-200'
                          : 'bg-red-50 border-red-200'
                      }`}
                    >
                      <div
                        className="w-3 h-3 rounded-full mt-1 flex-shrink-0"
                        style={{
                          backgroundColor:
                            article.status === 'valid'
                              ? '#10B981'
                              : article.status === 'outdated'
                              ? '#9CA3AF'
                              : '#EF4444'
                        }}
                      />
                      <div className="flex-1 min-w-0">
                        <p className="text-sm font-medium text-gray-900">{article.norm_text}</p>
                        <p className="text-xs text-gray-500 mt-1">
                          {article.status === 'valid'
                            ? 'Действует'
                            : article.status === 'outdated'
                            ? 'Устарела'
                            : 'Не существует'}
                        </p>
                        {article.applicability && (
                          <p className="text-xs text-gray-600 mt-1.5 leading-relaxed">{article.applicability}</p>
                        )}
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}

          {/* Chronology Tab */}
          {activePanel === 'chronology' && (
            <div className="space-y-4">
              {!selectedArticle ? (
                <div className="flex flex-col items-center justify-center py-12 text-center">
                  <div className="w-10 h-10 rounded-full bg-gray-100 flex items-center justify-center mb-3">
                    <GitBranch size={18} className="text-gray-400" />
                  </div>
                  <p className="text-xs text-gray-500 font-medium">Кликните на норму</p>
                  <p className="text-xs text-gray-400 mt-1">в списке или в документе</p>
                </div>
              ) : selectedArticle ? (
                <>
                  {/* Status badge */}
                  <div className="flex items-center gap-2">
                    {(() => {
                      const s = selectedArticle.status
                      const m = { valid: 'ДЕЙСТВУЕТ', outdated: 'УСТАРЕЛА', invalid: 'НЕ СУЩЕСТВУЕТ' }
                      const c = {
                        valid: 'bg-green-100 text-green-800',
                        outdated: 'bg-gray-100 text-gray-800',
                        invalid: 'bg-red-100 text-red-800'
                      }
                      return (
                        <span className={`text-xs font-semibold px-2.5 py-1 rounded-full ${c[s] || c.valid}`}>
                          {m[s] || s}
                        </span>
                      )
                    })()}
                  </div>

                  {/* Article title and reference */}
                  <div>
                    <p className="text-sm font-semibold text-gray-900">{selectedArticle.title || selectedArticle.norm_text}</p>
                    {selectedArticle.title && (
                      <p className="text-xs text-gray-400 mt-0.5">{selectedArticle.norm_text}</p>
                    )}
                  </div>

                  {/* Applicability */}
                  {selectedArticle.applicability && (
                    <div className="p-3 bg-blue-50 rounded-xl border border-blue-100">
                      <p className="text-xs font-medium text-blue-900 mb-1">Применимость:</p>
                      <p className="text-xs text-blue-800 leading-relaxed">{selectedArticle.applicability}</p>
                    </div>
                  )}

                  {/* Usage context */}
                  {selectedArticle.usage_context && (
                    <div className="p-3 bg-amber-50 rounded-xl border border-amber-100">
                      <p className="text-xs font-medium text-amber-900 mb-1">Контекст использования:</p>
                      <p className="text-xs text-amber-800 leading-relaxed">{selectedArticle.usage_context}</p>
                    </div>
                  )}

                  {/* Timeline */}
                  {(() => {
                    const entries = []
                    if (selectedArticle.introduced) {
                      entries.push({
                        date: selectedArticle.introduced,
                        label: 'Введена',
                        type: 'introduced'
                      })
                    }
                    if (selectedArticle.amendments && Array.isArray(selectedArticle.amendments)) {
                      selectedArticle.amendments.forEach(a => {
                        entries.push({ date: a.date, label: a.description, type: 'amendment' })
                      })
                    }
                    entries.sort((a, b) => a.date.localeCompare(b.date))

                    if (entries.length === 0 && !selectedArticle.replaced_by && !selectedArticle.deleted_at) return null

                    const isValid = selectedArticle.status === 'valid'
                    const isOutdated = selectedArticle.status === 'outdated'
                    const isInvalid = selectedArticle.status === 'invalid'

                    return (
                      <div className="border-t border-gray-100 pt-4">
                        <p className="text-xs font-medium text-gray-500 mb-3 uppercase">История изменений</p>

                        {selectedArticle.deleted_at && (
                          <div className="mb-4 p-3 rounded-xl bg-red-50 border border-red-200">
                            <p className="text-xs font-medium text-red-900">Удалена {selectedArticle.deleted_at}</p>
                          </div>
                        )}

                        {isOutdated && selectedArticle.replaced_by && (
                          <div className="mb-4 p-3 rounded-xl bg-gray-50 border border-gray-200">
                            <p className="text-xs font-medium text-gray-900">
                              Заменена {selectedArticle.status_since || ''}:
                            </p>
                            <p className="text-xs text-gray-600 mt-1">{selectedArticle.replaced_by}</p>
                          </div>
                        )}

                        {entries.length > 0 && (
                          <div className="relative pl-8">
                            <div
                              className="absolute left-3 top-0 bottom-0 w-0.5"
                              style={{
                                background:
                                  isValid ? '#ADFF5E' :
                                  isOutdated ? 'transparent' :
                                  'transparent',
                                borderLeft:
                                  isOutdated ? '2px dashed #9CA3AF' :
                                  isInvalid ? '2px dashed #EF4444' :
                                  'none'
                              }}
                            />

                            <div className="space-y-3">
                              {entries.map((entry, idx) => (
                                <div key={idx} className="relative">
                                  <div className="flex gap-3">
                                    <div className="text-xs text-gray-400 w-16 flex-shrink-0 pt-0.5">
                                      {new Date(entry.date).toLocaleDateString('ru-RU', {
                                        day: 'numeric',
                                        month: '2-digit',
                                        year: '2-digit'
                                      })}
                                    </div>
                                    <div className="flex-1 p-3 rounded-xl border border-gray-200 bg-white">
                                      <p className="text-xs font-medium text-gray-900">{entry.label}</p>
                                    </div>
                                  </div>
                                </div>
                              ))}
                            </div>
                          </div>
                        )}
                      </div>
                    )
                  })()}

                  {/* Current status explanation */}
                  {selectedArticle.current_status_explanation && (
                    <div className="p-3 bg-gray-50 rounded-xl border border-gray-200">
                      <p className="text-xs text-gray-700 leading-relaxed">
                        {selectedArticle.current_status_explanation}
                      </p>
                    </div>
                  )}
                </>
              ) : (
                <p className="text-xs text-gray-400 text-center py-4">Статья не найдена</p>
              )}
            </div>
          )}

          {/* Formulation Tab */}
          {activePanel === 'formulation' && (
            <div className="space-y-4">
              {selectedArticle && (
                <div>
                  <p className="text-xs font-semibold text-gray-700 mb-3">Статья: {selectedArticle.title || selectedArticle.norm_text}</p>

                  {selectedArticle.applicability && (
                    <div className="p-2 mb-3 rounded-lg bg-blue-50 border border-blue-100">
                      <p className="text-xs text-blue-800">{selectedArticle.applicability}</p>
                    </div>
                  )}

                  {selectedArticle.usage_context && (
                    <div className="p-2 mb-4 rounded-lg bg-amber-50 border border-amber-100">
                      <p className="text-xs text-amber-800">{selectedArticle.usage_context}</p>
                    </div>
                  )}

                  <div className="border-b border-gray-100 pb-4 mb-4" />
                </div>
              )}

              {/* Document-level errors */}
              {errorsLoading ? (
                <div className="flex items-center justify-center py-8">
                  <Loader2 size={16} className="animate-spin text-gray-300" />
                </div>
              ) : visibleErrors.length > 0 ? (
                <>
                  <p className="text-xs font-semibold text-gray-700 mb-3">Ошибки документа</p>
                  <p className="text-sm text-gray-600 mb-4">{errorsSummary || 'Найдены ошибки в документе:'}</p>
                  <div className="space-y-3">
                    {visibleErrors.map((error, idx) => (
                      <div key={error.id || idx} className="border border-gray-200 rounded-xl overflow-hidden">
                        <div className="flex items-start gap-3 p-4">
                          <AlertCircle size={16} className="text-red-500 mt-0.5 flex-shrink-0" />
                          <div className="flex-1 min-w-0">
                            <p className="text-xs font-semibold text-gray-900">{error.title}</p>
                            <p className="text-xs text-gray-600 mt-1 line-clamp-2">"{error.suggestion}"</p>
                            {error.reason && (
                              <p className="text-xs text-gray-500 mt-1.5 italic">{error.reason}</p>
                            )}
                          </div>
                        </div>

                        {/* Action buttons */}
                        <div className="flex gap-2 px-4 pb-3 border-t border-gray-100">
                          <button
                            onClick={() => acceptFix(error)}
                            className="flex-1 flex items-center justify-center gap-1 px-3 py-2 text-xs font-semibold text-gray-900 bg-[#ADFF5E] rounded-lg hover:bg-[#9AE84F] transition-colors"
                          >
                            <Check size={12} /> Принять
                          </button>
                          <button
                            onClick={() => askAboutError(error)}
                            className="flex-1 flex items-center justify-center gap-1 px-3 py-2 text-xs font-semibold text-gray-700 border border-gray-300 rounded-lg hover:bg-gray-50 transition-colors"
                          >
                            Спросить
                          </button>
                          <button
                            onClick={() => dismissError(error.id)}
                            className="px-3 py-2 text-gray-400 hover:text-red-600 hover:bg-red-50 rounded-lg transition-colors"
                          >
                            <X size={14} />
                          </button>
                        </div>

                        {/* AI Explanation */}
                        {askModal?.error?.id === error.id && askModal.explanation && (
                          <div className="p-4 bg-blue-50 border-t border-gray-100">
                            <p className="text-xs font-medium text-blue-900 mb-2">Объяснение:</p>
                            <p className="text-xs text-blue-800 leading-relaxed">{askModal.explanation}</p>
                          </div>
                        )}
                      </div>
                    ))}
                  </div>
                </>
              ) : (
                <p className="text-xs text-gray-400 text-center py-8">Ошибки не найдены</p>
              )}
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

          <RightPanel />
        </div>
      </main>
    </div>
  )
}
