'use client'

import { useState, useEffect, useRef, useCallback } from 'react'
import { useParams, useRouter } from 'next/navigation'
import Sidebar from '@/components/Sidebar'
import { useAuth } from '@/components/useAuth'
import {
  ArrowLeft, Check, Loader2, Bold, Italic, Underline,
  List, ListOrdered, Heading1, Heading2, Minus, Undo, Redo,
} from 'lucide-react'

const BACKEND = process.env.NEXT_PUBLIC_BACKEND_URL || 'http://localhost:8000'

function parseTemplateContent(content) {
  if (!content) return ''
  try {
    const o = JSON.parse(content)
    if (o && o.format === 'rich_html' && typeof o.html === 'string') return o.html
  } catch (_) {}
  const t = String(content).trim()
  if (t.startsWith('<')) return t
  return t
    .split(/\n{2,}/)
    .map((p) => `<p>${p.replace(/\n/g, '<br>')}</p>`)
    .join('')
}

function serializeTemplateContent(html) {
  return JSON.stringify({ format: 'rich_html', html })
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
      onMouseDown={(e) => { e.preventDefault(); onClick() }}
      title={title}
      className={`p-1.5 rounded transition-colors ${active ? 'bg-gray-200 text-ink' : 'text-gray-500 hover:bg-gray-100 hover:text-gray-800'}`}
    >
      {children}
    </button>
  )
}

export default function TemplateEditorPage() {
  const { id } = useParams()
  const router = useRouter()
  const { loading: authLoading, authHeaders } = useAuth()

  const [template, setTemplate] = useState(null)
  const [title, setTitle] = useState('')
  const [saveStatus, setSaveStatus] = useState('idle')
  const [loading, setLoading] = useState(true)
  const [wordCount, setWordCount] = useState(0)
  const [activeFormats, setActiveFormats] = useState({})

  const editorRef = useRef(null)
  const titleSaveTimeout = useRef(null)
  const contentSaveTimeout = useRef(null)
  const savedTitleRef = useRef('')

  useEffect(() => {
    if (authLoading) return
    fetch(`${BACKEND}/templates/${id}`, { headers: authHeaders })
      .then((res) => (res.ok ? res.json() : null))
      .then((data) => {
        if (!data) {
          router.push('/templates')
          return
        }
        setTemplate(data)
        setTitle(data.name)
        savedTitleRef.current = data.name
      })
      .finally(() => setLoading(false))
  }, [authLoading, id, authHeaders, router])

  useEffect(() => {
    if (!template || loading) return
    const el = editorRef.current
    if (!el) return
    const cached = localStorage.getItem(`template-content-${id}`)
    if (cached) {
      el.innerHTML = cached
    } else {
      el.innerHTML = parseTemplateContent(template.content) || '<p><br></p>'
    }
    const text = el.innerText || ''
    setWordCount(text.trim().split(/\s+/).filter(Boolean).length)
  }, [template, id, loading])

  const persistToServer = useCallback(async () => {
    if (!editorRef.current) return
    const body = serializeTemplateContent(editorRef.current.innerHTML)
    localStorage.setItem(`template-content-${id}`, editorRef.current.innerHTML)
    setSaveStatus('saving')
    try {
      const res = await fetch(`${BACKEND}/templates/${id}`, {
        method: 'PATCH',
        headers: { ...authHeaders, 'Content-Type': 'application/json' },
        body: JSON.stringify({ content: body }),
      })
      if (res.ok) {
        setTemplate(await res.json())
        setSaveStatus('saved')
        setTimeout(() => setSaveStatus('idle'), 2000)
      } else {
        setSaveStatus('unsaved')
      }
    } catch {
      setSaveStatus('unsaved')
    }
  }, [id, authHeaders])

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
    contentSaveTimeout.current = setTimeout(persistToServer, 1500)
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
        const res = await fetch(`${BACKEND}/templates/${id}`, {
          method: 'PATCH',
          headers: { ...authHeaders, 'Content-Type': 'application/json' },
          body: JSON.stringify({ name: val.trim() }),
        })
        if (res.ok) {
          setTemplate(await res.json())
          savedTitleRef.current = val.trim()
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

  useEffect(() => {
    const handler = (e) => {
      if ((e.metaKey || e.ctrlKey) && e.key === 's') {
        e.preventDefault()
        persistToServer()
      }
    }
    window.addEventListener('keydown', handler)
    return () => window.removeEventListener('keydown', handler)
  }, [persistToServer])

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
        <div className="rounded-2xl border border-gray-300 bg-white shadow-sm h-full flex flex-col overflow-hidden">
          <div className="flex items-center justify-between px-5 py-3 border-b border-gray-100">
            <button
              type="button"
              onClick={() => router.push('/templates')}
              className="flex items-center gap-1.5 text-sm text-gray-400 hover:text-gray-700 transition-colors"
            >
              <ArrowLeft size={15} />
              Шаблоны
            </button>
            <div className="flex items-center gap-4">
              <SaveStatus status={saveStatus} />
              <button
                type="button"
                onMouseDown={(e) => e.preventDefault()}
                onClick={persistToServer}
                className="bg-brand hover:bg-brand-hover transition-colors text-ink font-semibold text-xs px-3 py-1.5 rounded-full flex items-center gap-1.5"
              >
                <Check size={12} />
                Сохранить
              </button>
            </div>
          </div>

          <div className="flex items-center gap-0.5 px-5 py-2 border-b border-gray-100">
            <ToolbarBtn onClick={() => fmt('undo')} title="Отменить"><Undo size={15} /></ToolbarBtn>
            <ToolbarBtn onClick={() => fmt('redo')} title="Повторить"><Redo size={15} /></ToolbarBtn>
            <div className="w-px h-4 bg-gray-200 mx-1.5" />
            <ToolbarBtn onClick={() => fmt('bold')} active={activeFormats.bold} title="Жирный"><Bold size={15} /></ToolbarBtn>
            <ToolbarBtn onClick={() => fmt('italic')} active={activeFormats.italic} title="Курсив"><Italic size={15} /></ToolbarBtn>
            <ToolbarBtn onClick={() => fmt('underline')} active={activeFormats.underline} title="Подчёркнутый"><Underline size={15} /></ToolbarBtn>
            <div className="w-px h-4 bg-gray-200 mx-1.5" />
            <ToolbarBtn onClick={() => fmt('formatBlock', 'h1')} title="Заголовок 1"><Heading1 size={15} /></ToolbarBtn>
            <ToolbarBtn onClick={() => fmt('formatBlock', 'h2')} title="Заголовок 2"><Heading2 size={15} /></ToolbarBtn>
            <ToolbarBtn onClick={() => fmt('formatBlock', 'p')} title="Обычный текст">
              <span className="text-xs font-medium leading-none">¶</span>
            </ToolbarBtn>
            <div className="w-px h-4 bg-gray-200 mx-1.5" />
            <ToolbarBtn onClick={() => fmt('insertUnorderedList')} active={activeFormats.insertUnorderedList} title="Список"><List size={15} /></ToolbarBtn>
            <ToolbarBtn onClick={() => fmt('insertOrderedList')} active={activeFormats.insertOrderedList} title="Нумерация"><ListOrdered size={15} /></ToolbarBtn>
            <ToolbarBtn onClick={insertHr} title="Разделитель"><Minus size={15} /></ToolbarBtn>
            <div className="ml-auto text-xs text-gray-300">
              {wordCount} {wordCount === 1 ? 'слово' : wordCount < 5 ? 'слова' : 'слов'}
            </div>
          </div>

          <div className="flex-1 overflow-y-auto">
            <div className="max-w-3xl mx-auto px-16 py-10">
              <input
                type="text"
                value={title}
                onChange={handleTitleChange}
                placeholder="Название шаблона"
                className="w-full text-4xl font-bold text-ink outline-none border-none bg-transparent placeholder-gray-200 mb-8"
              />
              <div className="w-full h-px bg-gray-100 mb-8" />
              <div
                ref={editorRef}
                contentEditable
                suppressContentEditableWarning
                onInput={handleContentInput}
                onKeyUp={updateActiveFormats}
                onSelect={updateActiveFormats}
                data-placeholder="Текст шаблона..."
                className="editor-body outline-none min-h-[50vh] text-gray-800 text-base leading-7"
              />
            </div>
          </div>
        </div>
      </main>
    </div>
  )
}
