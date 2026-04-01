'use client'

import { useState, useEffect, useRef, useCallback } from 'react'
import Sidebar from '@/components/Sidebar'
import { useAuth } from '@/components/useAuth'
import { useRouter } from 'next/navigation'
import FolderColorPicker from '@/components/FolderColorPicker'
import { DOC_TYPE_COLORS, resolveFolderColor } from '@/lib/folderColors'
import {
  Search, MoreHorizontal, Trash2, Pencil, X, Check, Plus,
  FileText, Upload, Folder, FolderPlus, ChevronRight, Grid3x3, List, Palette,
} from 'lucide-react'

const BACKEND = process.env.NEXT_PUBLIC_BACKEND_URL || 'http://localhost:8000'

const DOC_TYPES = ['Договор', 'Иск', 'Жалоба', 'Решение суда', 'Заявление', 'Другое']

function timeAgo(dateStr) {
  const diff = Date.now() - new Date(dateStr).getTime()
  const mins = Math.floor(diff / 60000)
  const hours = Math.floor(mins / 60)
  const days = Math.floor(hours / 24)
  if (days > 0) return `${days} ${days === 1 ? 'день' : days < 5 ? 'дня' : 'дней'} назад`
  if (hours > 0) return `${hours} ${hours === 1 ? 'час' : hours < 5 ? 'часа' : 'часов'} назад`
  if (mins > 0) return `${mins} ${mins === 1 ? 'минуту' : mins < 5 ? 'минуты' : 'минут'} назад`
  return 'только что'
}

function isToday(dateStr) {
  const d = new Date(dateStr)
  const now = new Date()
  return d.getDate() === now.getDate() && d.getMonth() === now.getMonth() && d.getFullYear() === now.getFullYear()
}

function DocCard({ doc, openMenu, setOpenMenu, editingId, setEditingId, editTitle, setEditTitle, onDelete, onRename, onClick }) {
  return (
    <div onClick={onClick} className="border border-gray-200 rounded-xl p-4 flex flex-col justify-between relative hover:border-gray-300 hover:shadow-sm transition-all cursor-pointer min-h-[130px]">
      <div className="flex items-start justify-between gap-2">
        {editingId === doc.id ? (
          <div className="flex items-center gap-1 flex-1">
            <input
              autoFocus
              value={editTitle}
              onChange={e => setEditTitle(e.target.value)}
              onKeyDown={e => {
                if (e.key === 'Enter') onRename(doc.id)
                if (e.key === 'Escape') setEditingId(null)
              }}
              className="text-sm font-semibold text-ink flex-1 border-b border-brand outline-none bg-transparent"
            />
            <button onClick={e => { e.stopPropagation(); onRename(doc.id) }} className="text-brand-hover hover:text-brand-active ml-1">
              <Check size={14} />
            </button>
            <button onClick={e => { e.stopPropagation(); setEditingId(null) }} className="text-gray-400 hover:text-gray-600">
              <X size={14} />
            </button>
          </div>
        ) : (
          <p className="text-sm font-semibold text-ink leading-snug line-clamp-3">{doc.title}</p>
        )}

        <div className="relative flex-shrink-0">
          <button
            onClick={e => { e.stopPropagation(); setOpenMenu(openMenu === doc.id ? null : doc.id) }}
            className="p-1 rounded hover:bg-gray-100 transition-colors text-gray-400"
          >
            <MoreHorizontal size={16} />
          </button>
          {openMenu === doc.id && (
            <div className="absolute right-0 top-7 bg-white border border-gray-200 rounded-lg shadow-lg z-10 py-1 w-40">
              <button
                onClick={e => { e.stopPropagation(); setEditingId(doc.id); setEditTitle(doc.title); setOpenMenu(null) }}
                className="flex items-center gap-2 px-3 py-2 text-sm text-gray-700 hover:bg-gray-50 w-full text-left"
              >
                <Pencil size={13} /> Переименовать
              </button>
              <button
                onClick={e => { e.stopPropagation(); onDelete(doc.id) }}
                className="flex items-center gap-2 px-3 py-2 text-sm text-red-600 hover:bg-red-50 w-full text-left"
              >
                <Trash2 size={13} /> Удалить
              </button>
            </div>
          )}
        </div>
      </div>

      <p className="text-xs text-gray-400">Редактировано {timeAgo(doc.updated_at)}</p>
    </div>
  )
}

function NewDocModal({ onClose, onCreate }) {
  const [title, setTitle] = useState('')
  const [loading, setLoading] = useState(false)

  const handleSubmit = async (e) => {
    e.preventDefault()
    if (!title.trim()) return
    setLoading(true)
    await onCreate(title.trim())
    setLoading(false)
  }

  return (
    <div className="fixed inset-0 bg-black bg-opacity-30 flex items-center justify-center z-50">
      <div className="bg-white rounded-2xl border border-gray-200 shadow-xl w-full max-w-sm p-6">
        <div className="flex items-center gap-3 mb-5">
          <span className="w-9 h-9 bg-gray-100 rounded-xl flex items-center justify-center text-gray-500">
            <FileText size={18} />
          </span>
          <h2 className="font-bold text-ink text-base">Новый документ</h2>
        </div>
        <form onSubmit={handleSubmit} className="flex flex-col gap-4">
          <div className="flex flex-col gap-1">
            <label className="text-xs font-medium text-gray-600">Название</label>
            <input
              autoFocus
              type="text"
              value={title}
              onChange={e => setTitle(e.target.value)}
              placeholder="Введите название документа"
              className="border border-gray-200 rounded-xl px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-brand focus:border-transparent"
            />
          </div>
          <div className="flex gap-2 mt-1">
            <button
              type="button"
              onClick={onClose}
              className="flex-1 border border-gray-200 text-gray-600 font-medium py-2 rounded-full text-sm hover:bg-gray-50 transition-colors"
            >
              Отмена
            </button>
            <button
              type="submit"
              disabled={!title.trim() || loading}
              className="flex-1 bg-brand hover:bg-brand-hover text-ink font-semibold py-2 rounded-full text-sm disabled:opacity-60 transition-colors"
            >
              {loading ? 'Создание...' : 'Создать'}
            </button>
          </div>
        </form>
      </div>
    </div>
  )
}

function NewFolderModal({ onClose, onCreate }) {
  const [name, setName] = useState('')
  const [docType, setDocType] = useState(DOC_TYPES[0])
  const [color, setColor] = useState(DOC_TYPE_COLORS[DOC_TYPES[0]])
  const [colorManuallySet, setColorManuallySet] = useState(false)
  const [loading, setLoading] = useState(false)

  const handleSubmit = async (e) => {
    e.preventDefault()
    if (!name.trim()) return
    setLoading(true)
    await onCreate(name.trim(), docType, color)
    setLoading(false)
  }

  return (
    <div className="fixed inset-0 bg-black bg-opacity-30 flex items-center justify-center z-50">
      <div className="bg-white rounded-2xl border border-gray-200 shadow-xl w-full max-w-md p-6">
        <div className="flex items-center gap-3 mb-5">
          <span className="w-9 h-9 bg-gray-100 rounded-xl flex items-center justify-center text-gray-500">
            <FolderPlus size={18} />
          </span>
          <h2 className="font-bold text-ink text-base">Новая папка</h2>
        </div>
        <form onSubmit={handleSubmit} className="flex flex-col gap-4">
          <div className="flex flex-col gap-1">
            <label className="text-xs font-medium text-gray-600">Название папки</label>
            <input
              autoFocus
              type="text"
              value={name}
              onChange={e => setName(e.target.value)}
              placeholder="Например: Договоры 2026"
              className="border border-gray-200 rounded-xl px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-brand focus:border-transparent"
            />
          </div>
          <div className="flex flex-col gap-1">
            <label className="text-xs font-medium text-gray-600">Тип документов</label>
            <select
              value={docType}
              onChange={e => {
                setDocType(e.target.value)
                if (!colorManuallySet) {
                  setColor(DOC_TYPE_COLORS[e.target.value] || '#6B7280')
                }
              }}
              className="border border-gray-200 rounded-xl px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-brand focus:border-transparent bg-white"
            >
              {DOC_TYPES.map(t => <option key={t} value={t}>{t}</option>)}
            </select>
          </div>
          <FolderColorPicker
            selectedColor={color}
            previewName={name}
            previewDocType={docType}
            onSelect={hex => {
              setColor(hex)
              setColorManuallySet(true)
            }}
          />
          <div className="flex gap-2 mt-1">
            <button
              type="button"
              onClick={onClose}
              className="flex-1 border border-gray-200 text-gray-600 font-medium py-2 rounded-full text-sm hover:bg-gray-50 transition-colors"
            >
              Отмена
            </button>
            <button
              type="submit"
              disabled={!name.trim() || loading}
              className="flex-1 bg-brand hover:bg-brand-hover text-ink font-semibold py-2 rounded-full text-sm disabled:opacity-60 transition-colors"
            >
              {loading ? 'Создание...' : 'Создать'}
            </button>
          </div>
        </form>
      </div>
    </div>
  )
}

export default function DocumentsPage() {
  const { loading: authLoading, authHeaders } = useAuth()
  const router = useRouter()

  const [documents, setDocuments] = useState([])
  const [loading, setLoading] = useState(true)
  const [search, setSearch] = useState('')
  const [searchResults, setSearchResults] = useState(null)
  const [showNewDoc, setShowNewDoc] = useState(false)
  const [openMenu, setOpenMenu] = useState(null)
  const [editingId, setEditingId] = useState(null)
  const [editTitle, setEditTitle] = useState('')
  const [toast, setToast] = useState(null)
  const [uploading, setUploading] = useState(false)

  // Folders
  const [folders, setFolders] = useState([])
  const [activeFolderId, setActiveFolderId] = useState(null) // null = all docs
  const [folderDocs, setFolderDocs] = useState(null) // null when all docs view
  const [folderLoading, setFolderLoading] = useState(false)
  const [showNewFolder, setShowNewFolder] = useState(false)
  const [folderMenuId, setFolderMenuId] = useState(null)
  const [editingFolderId, setEditingFolderId] = useState(null)
  const [editFolderName, setEditFolderName] = useState('')
  const [viewMode, setViewMode] = useState('home') // 'home', 'documents', or 'folders'
  const [colorPickerFolderId, setColorPickerFolderId] = useState(null)
  const [pendingColor, setPendingColor] = useState(null)

  const searchTimeout = useRef(null)
  const uploadInputRef = useRef(null)

  const showToast = useCallback((msg, type = 'success') => {
    setToast({ msg, type })
    setTimeout(() => setToast(null), 3000)
  }, [])

  const fetchDocuments = useCallback(async () => {
    try {
      const res = await fetch(`${BACKEND}/documents`, { headers: authHeaders })
      if (res.ok) setDocuments(await res.json())
    } catch (e) {
      console.error(e)
    } finally {
      setLoading(false)
    }
  }, [authHeaders])

  const fetchFolders = useCallback(async () => {
    try {
      const res = await fetch(`${BACKEND}/folders`, { headers: authHeaders })
      if (res.ok) setFolders(await res.json())
    } catch (e) {
      console.error(e)
    }
  }, [authHeaders])

  useEffect(() => {
    if (!authLoading) {
      fetchDocuments()
      fetchFolders()
    }
  }, [authLoading])

  // When active folder changes, fetch that folder's docs
  useEffect(() => {
    if (activeFolderId === null) {
      setFolderDocs(null)
      return
    }
    setFolderLoading(true)
    fetch(`${BACKEND}/folders/${activeFolderId}/documents`, { headers: authHeaders })
      .then(res => res.ok ? res.json() : [])
      .then(data => setFolderDocs(data))
      .catch(() => setFolderDocs([]))
      .finally(() => setFolderLoading(false))
  }, [activeFolderId])

  // Search
  useEffect(() => {
    clearTimeout(searchTimeout.current)
    if (!search.trim()) { setSearchResults(null); return }
    searchTimeout.current = setTimeout(async () => {
      try {
        const res = await fetch(`${BACKEND}/documents/search?q=${encodeURIComponent(search)}&limit=20`, { headers: authHeaders })
        if (res.ok) setSearchResults(await res.json())
      } catch (e) { console.error(e) }
    }, 400)
  }, [search])

  // Close menus on outside click
  useEffect(() => {
    const handler = () => { setOpenMenu(null); setFolderMenuId(null) }
    document.addEventListener('click', handler)
    return () => document.removeEventListener('click', handler)
  }, [])

  const handleCreate = async (title) => {
    try {
      const blob = new Blob([''], { type: 'text/plain' })
      const file = new File([blob], `${title}.txt`, { type: 'text/plain' })
      const formData = new FormData()
      formData.append('file', file)
      if (activeFolderId !== null) formData.append('folder_id', activeFolderId)
      const res = await fetch(`${BACKEND}/documents/upload`, {
        method: 'POST',
        headers: authHeaders,
        body: formData,
      })
      if (res.ok) {
        const doc = await res.json()
        await fetch(`${BACKEND}/documents/${doc.id}`, {
          method: 'PATCH',
          headers: { ...authHeaders, 'Content-Type': 'application/json' },
          body: JSON.stringify({ title }),
        })
        // Add to local state immediately so counts update
        const newDoc = { ...doc, title, folder_id: activeFolderId }
        setDocuments(prev => [newDoc, ...prev])
        if (activeFolderId !== null) setFolderDocs(prev => [newDoc, ...(prev || [])])
        setShowNewDoc(false)
        router.push(`/documents/${doc.id}`)
      } else {
        const err = await res.json().catch(() => ({}))
        showToast(err.detail || `Ошибка ${res.status}`, 'error')
        setShowNewDoc(false)
      }
    } catch (e) {
      showToast('Не удалось подключиться к серверу', 'error')
      setShowNewDoc(false)
    }
  }

  const handleCreateFolder = async (name, docType, color) => {
    try {
      const res = await fetch(`${BACKEND}/folders`, {
        method: 'POST',
        headers: { ...authHeaders, 'Content-Type': 'application/json' },
        body: JSON.stringify({ name, document_type: docType }),
      })
      if (res.ok) {
        const folder = await res.json()
        setFolders(f => [...f, folder])
        showToast('Папка создана')
      } else {
        const err = await res.json().catch(() => ({}))
        showToast(err.detail || 'Ошибка создания папки', 'error')
      }
    } catch (e) {
      showToast('Не удалось создать папку', 'error')
    }
    setShowNewFolder(false)
  }

  const handleRenameFolder = async (id) => {
    if (!editFolderName.trim()) { setEditingFolderId(null); return }
    try {
      const res = await fetch(`${BACKEND}/folders/${id}`, {
        method: 'PATCH',
        headers: { ...authHeaders, 'Content-Type': 'application/json' },
        body: JSON.stringify({ name: editFolderName }),
      })
      if (res.ok) {
        const updated = await res.json()
        setFolders(f => f.map(x => x.id === id ? updated : x))
      }
    } catch (e) { console.error(e) }
    setEditingFolderId(null)
  }

  const handleDeleteFolder = async (id) => {
    try {
      await fetch(`${BACKEND}/folders/${id}`, { method: 'DELETE', headers: authHeaders })
      setFolders(f => f.filter(x => x.id !== id))
      if (activeFolderId === id) setActiveFolderId(null)
      showToast('Папка удалена')
    } catch (e) { console.error(e) }
    setFolderMenuId(null)
  }

  const handleChangeColor = async (folderId, hex) => {
    try {
      const res = await fetch(`${BACKEND}/folders/${folderId}`, {
        method: 'PATCH',
        headers: { ...authHeaders, 'Content-Type': 'application/json' },
        body: JSON.stringify({ color: hex }),
      })
      if (res.ok) {
        const updated = await res.json()
        setFolders(f => f.map(x => x.id === folderId ? updated : x))
      }
    } catch (e) { console.error(e) }
    setColorPickerFolderId(null)
    setPendingColor(null)
  }

  const handleUploadFile = async (e) => {
    const file = e.target.files?.[0]
    if (!file) return
    setUploading(true)
    try {
      const formData = new FormData()
      formData.append('file', file)
      if (activeFolderId !== null) formData.append('folder_id', activeFolderId)
      const res = await fetch(`${BACKEND}/documents/upload`, {
        method: 'POST',
        headers: authHeaders,
        body: formData,
      })
      if (!res.ok) {
        const err = await res.json().catch(() => ({}))
        showToast(err.detail || `Ошибка ${res.status}`, 'error')
        return
      }
      const doc = await res.json()
      const newDoc = { ...doc, folder_id: activeFolderId }
      setDocuments(prev => [newDoc, ...prev])
      if (activeFolderId !== null) setFolderDocs(prev => [newDoc, ...(prev || [])])
      if (file.name.toLowerCase().endsWith('.docx')) {
        const mammoth = (await import('mammoth')).default
        const arrayBuffer = await file.arrayBuffer()
        const { value: html } = await mammoth.convertToHtml({ arrayBuffer })
        localStorage.setItem(`doc-content-${doc.id}`, html)
      }
      router.push(`/documents/${doc.id}`)
    } catch (err) {
      showToast('Не удалось загрузить документ', 'error')
    } finally {
      setUploading(false)
      e.target.value = ''
    }
  }

  const handleDelete = async (id) => {
    try {
      await fetch(`${BACKEND}/documents/${id}`, { method: 'DELETE', headers: authHeaders })
      setDocuments(docs => docs.filter(d => d.id !== id))
      if (folderDocs) setFolderDocs(fd => fd.filter(d => d.id !== id))
      showToast('Документ удалён')
    } catch (e) { console.error(e) }
    setOpenMenu(null)
  }

  const handleRename = async (id) => {
    try {
      const res = await fetch(`${BACKEND}/documents/${id}`, {
        method: 'PATCH',
        headers: { ...authHeaders, 'Content-Type': 'application/json' },
        body: JSON.stringify({ title: editTitle }),
      })
      if (res.ok) {
        const updated = await res.json()
        setDocuments(docs => docs.map(d => d.id === id ? updated : d))
        if (folderDocs) setFolderDocs(fd => fd.map(d => d.id === id ? updated : d))
      }
    } catch (e) { console.error(e) }
    setEditingId(null)
  }

  const baseDisplayed = activeFolderId !== null ? (folderDocs || []) : documents
  const displayed = searchResults
    ? searchResults.map(r => ({ ...r, updated_at: r.updated_at || new Date().toISOString() }))
    : baseDisplayed

  const todayDocs = displayed.filter(d => isToday(d.updated_at))
  const earlierDocs = displayed.filter(d => !isToday(d.updated_at))

  const cardProps = {
    openMenu, setOpenMenu, editingId, setEditingId, editTitle, setEditTitle,
    onDelete: handleDelete, onRename: handleRename,
  }

  const activeFolder = folders.find(f => f.id === activeFolderId)

  const handleFolderClick = (folderId) => {
    setActiveFolderId(folderId)
    setViewMode('documents')
  }

  // Get documents grouped by folder
  const getDocumentsByFolder = () => {
    const grouped = {}
    documents.forEach(doc => {
      const folderId = doc.folder_id || 'unassigned'
      if (!grouped[folderId]) grouped[folderId] = []
      grouped[folderId].push(doc)
    })
    return grouped
  }

  // Get folder name or "Unassigned"
  const getFolderName = (folderId) => {
    if (folderId === 'unassigned') return 'Без папки'
    const folder = folders.find(f => f.id === parseInt(folderId))
    return folder?.name || 'Unknown'
  }

  // Get folder or create a synthetic one for unassigned
  const getFolderObject = (folderId) => {
    if (folderId === 'unassigned') return { id: 'unassigned', name: 'Без папки', document_type: 'mixed' }
    return folders.find(f => f.id === parseInt(folderId))
  }

  if (authLoading) return null

  return (
    <>
      {showNewDoc && <NewDocModal onClose={() => setShowNewDoc(false)} onCreate={handleCreate} />}
      {showNewFolder && <NewFolderModal onClose={() => setShowNewFolder(false)} onCreate={handleCreateFolder} />}

      {toast && (
        <div className={`fixed bottom-8 left-1/2 -translate-x-1/2 px-5 py-3 rounded-xl shadow-lg text-sm font-medium text-white z-50 ${toast.type === 'error' ? 'bg-red-500' : 'bg-brand-hover'}`}>
          {toast.msg}
        </div>
      )}

      <div className="flex h-screen bg-gray-50">
        <Sidebar />

        <main className="flex-1 overflow-hidden min-w-0 py-4 pr-4">
          <div className="rounded-2xl border border-gray-300 bg-white shadow-sm h-full flex overflow-hidden">

            {/* Folder panel */}
            {(viewMode === 'documents' || viewMode === 'home') && (
            <div className="w-52 flex-shrink-0 border-r border-gray-100 flex flex-col py-4">
              <div className="px-4 mb-3 flex items-center justify-between">
                <span className="text-xs font-semibold text-gray-400 uppercase tracking-wide">Папки</span>
                <button
                  onClick={() => setShowNewFolder(true)}
                  className="p-1 rounded-lg text-gray-400 hover:bg-gray-100 hover:text-gray-600 transition-colors"
                  title="Новая папка"
                >
                  <FolderPlus size={15} />
                </button>
              </div>

              <div className="flex flex-col gap-0.5 px-2 flex-1 overflow-y-auto">
                {/* All documents */}
                <button
                  onClick={() => setActiveFolderId(null)}
                  className={`flex items-center gap-2.5 px-2 py-2 rounded-lg text-sm transition-colors w-full text-left ${
                    activeFolderId === null
                      ? 'bg-brand bg-opacity-20 text-ink font-semibold'
                      : 'text-gray-600 hover:bg-gray-50'
                  }`}
                >
                  <FileText size={15} className={activeFolderId === null ? 'text-brand-hover' : 'text-gray-400'} />
                  <span className="flex-1 truncate">Все документы</span>
                  {activeFolderId === null && <ChevronRight size={12} className="text-gray-400 flex-shrink-0" />}
                </button>

                {/* Folder list */}
                {folders.map(folder => (
                  <div key={folder.id} className="relative group">
                    {editingFolderId === folder.id ? (
                      <div className="flex items-center gap-1 px-2 py-2">
                        <input
                          autoFocus
                          value={editFolderName}
                          onChange={e => setEditFolderName(e.target.value)}
                          onKeyDown={e => {
                            if (e.key === 'Enter') handleRenameFolder(folder.id)
                            if (e.key === 'Escape') setEditingFolderId(null)
                          }}
                          className="flex-1 text-sm border-b border-brand outline-none bg-transparent min-w-0"
                        />
                        <button onClick={() => handleRenameFolder(folder.id)} className="text-brand-hover flex-shrink-0">
                          <Check size={13} />
                        </button>
                        <button onClick={() => setEditingFolderId(null)} className="text-gray-400 flex-shrink-0">
                          <X size={13} />
                        </button>
                      </div>
                    ) : (
                      <button
                        onClick={() => setActiveFolderId(folder.id)}
                        className={`flex items-center gap-2.5 px-2 py-2 rounded-lg text-sm transition-colors w-full text-left ${
                          activeFolderId === folder.id
                            ? 'bg-brand bg-opacity-20 text-ink font-semibold'
                            : 'text-gray-600 hover:bg-gray-50'
                        }`}
                      >
                        <Folder size={15} style={{ color: resolveFolderColor(folder), opacity: activeFolderId === folder.id ? 1 : 0.65 }} className="flex-shrink-0" />
                        <span className="flex-1 truncate">{folder.name}</span>
                        <button
                          onClick={e => { e.stopPropagation(); setFolderMenuId(folderMenuId === folder.id ? null : folder.id) }}
                          className="flex-shrink-0 opacity-0 group-hover:opacity-100 p-0.5 rounded hover:bg-gray-200 text-gray-400 transition-opacity"
                        >
                          <MoreHorizontal size={13} />
                        </button>
                      </button>
                    )}

                    {folderMenuId === folder.id && (
                      <div className="absolute left-full top-0 ml-1 bg-white border border-gray-200 rounded-lg shadow-lg z-20 py-1 w-40">
                        <button
                          onClick={e => { e.stopPropagation(); setColorPickerFolderId(folder.id); setPendingColor(resolveFolderColor(folder)); setFolderMenuId(null) }}
                          className="flex items-center gap-2 px-3 py-2 text-sm text-gray-700 hover:bg-gray-50 w-full text-left"
                        >
                          <Palette size={13} /> Изменить цвет
                        </button>
                        <button
                          onClick={e => { e.stopPropagation(); setEditingFolderId(folder.id); setEditFolderName(folder.name); setFolderMenuId(null) }}
                          className="flex items-center gap-2 px-3 py-2 text-sm text-gray-700 hover:bg-gray-50 w-full text-left"
                        >
                          <Pencil size={13} /> Переименовать
                        </button>
                        <button
                          onClick={e => { e.stopPropagation(); handleDeleteFolder(folder.id) }}
                          className="flex items-center gap-2 px-3 py-2 text-sm text-red-600 hover:bg-red-50 w-full text-left"
                        >
                          <Trash2 size={13} /> Удалить
                        </button>
                      </div>
                    )}

                    {colorPickerFolderId === folder.id && (
                      <div
                        className="absolute left-full top-0 ml-1 bg-white border border-gray-200 rounded-xl shadow-xl z-30 p-4 w-72"
                        onClick={e => e.stopPropagation()}
                      >
                        <FolderColorPicker
                          selectedColor={pendingColor}
                          previewName={folder.name}
                          previewDocType={folder.document_type}
                          onSelect={hex => setPendingColor(hex)}
                        />
                        <div className="flex gap-2 mt-3">
                          <button
                            onClick={() => setColorPickerFolderId(null)}
                            className="flex-1 border border-gray-200 text-gray-600 text-xs py-1.5 rounded-full hover:bg-gray-50"
                          >Отмена</button>
                          <button
                            onClick={() => handleChangeColor(folder.id, pendingColor)}
                            className="flex-1 bg-brand hover:bg-brand-hover text-ink text-xs font-semibold py-1.5 rounded-full"
                          >Сохранить</button>
                        </div>
                      </div>
                    )}
                  </div>
                ))}

                {folders.length === 0 && (
                  <p className="text-xs text-gray-300 px-2 py-4 text-center">Нет папок</p>
                )}
              </div>
            </div>
            )}

            {/* Main content */}
            <div className="flex-1 flex flex-col min-w-0 overflow-hidden">
              {/* Header */}
              <div className="flex items-center justify-between px-8 py-6 border-b border-gray-100">
                <div className="flex items-center gap-4">
                  {viewMode === 'home' && (
                    <h1 className="text-3xl font-bold text-ink">Документы</h1>
                  )}
                  {viewMode === 'documents' && (
                    <h1 className="text-3xl font-bold text-ink">
                      {activeFolder ? activeFolder.name : 'Документы'}
                    </h1>
                  )}
                  {viewMode === 'folders' && (
                    <div className="flex items-center gap-2 text-sm text-gray-600">
                      <button onClick={() => setViewMode('documents')} className="hover:text-gray-900">Папки</button>
                      {activeFolder && (
                        <>
                          <ChevronRight size={14} className="text-gray-400" />
                          <button onClick={() => setActiveFolderId(activeFolder.id)} className="hover:text-gray-900 font-medium">{activeFolder.name}</button>
                        </>
                      )}
                    </div>
                  )}
                  {(viewMode === 'documents' || viewMode === 'home') && activeFolder && (
                    <span className="text-xs text-gray-400 bg-gray-100 px-2.5 py-1 rounded-full">
                      {activeFolder.document_type}
                    </span>
                  )}
                  {(viewMode === 'documents' || viewMode === 'home') && (
                    <button
                      onClick={() => setShowNewDoc(true)}
                      className="bg-brand hover:bg-brand-hover active:bg-brand-active transition-colors text-ink font-semibold px-4 py-1.5 rounded-full text-sm flex items-center gap-2"
                    >
                      <Plus size={15} />
                      Создать
                    </button>
                  )}

                  {(viewMode === 'documents' || viewMode === 'home') && (
                    <>
                      <input
                        ref={uploadInputRef}
                        type="file"
                        accept=".docx,.pdf"
                        onChange={handleUploadFile}
                        className="hidden"
                      />
                      <button
                        onClick={() => uploadInputRef.current?.click()}
                        disabled={uploading}
                        className="border border-gray-200 hover:border-gray-300 hover:bg-gray-50 transition-colors text-gray-700 font-semibold px-4 py-1.5 rounded-full text-sm flex items-center gap-2 disabled:opacity-50"
                      >
                        <Upload size={15} />
                        {uploading ? 'Загрузка...' : 'Загрузить'}
                      </button>
                    </>
                  )}
                </div>

                <div className="flex items-center gap-4">
                  {(viewMode === 'documents' || viewMode === 'home') && (
                    <div className="relative">
                      <Search size={15} className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400" />
                      <input
                        type="text"
                        placeholder="Поиск документов"
                        value={search}
                        onChange={e => setSearch(e.target.value)}
                        className="pl-9 pr-4 py-2 border border-gray-200 rounded-full text-sm w-64 focus:outline-none focus:ring-2 focus:ring-brand focus:border-transparent"
                      />
                    </div>
                  )}
                </div>

                <div className="flex items-center gap-2 border border-gray-200 rounded-lg p-1">
                  <button
                    onClick={() => setViewMode('home')}
                    className={`p-1.5 rounded transition-colors ${viewMode === 'home' ? 'bg-gray-100 text-gray-700' : 'text-gray-400 hover:text-gray-600'}`}
                    title="Домашняя"
                  >
                    <FileText size={16} />
                  </button>
                  <button
                    onClick={() => { setViewMode('documents'); setActiveFolderId(null) }}
                    className={`p-1.5 rounded transition-colors ${viewMode === 'documents' ? 'bg-gray-100 text-gray-700' : 'text-gray-400 hover:text-gray-600'}`}
                    title="Все документы"
                  >
                    <List size={16} />
                  </button>
                  <button
                    onClick={() => setViewMode('folders')}
                    className={`p-1.5 rounded transition-colors ${viewMode === 'folders' ? 'bg-gray-100 text-gray-700' : 'text-gray-400 hover:text-gray-600'}`}
                    title="Вид папок"
                  >
                    <Grid3x3 size={16} />
                  </button>
                </div>
              </div>

              {/* Body */}
              <div className="flex-1 overflow-y-auto px-8 pb-8">
                {viewMode === 'home' ? (
                  // Home view — folder cards + recent docs
                  <div className="py-6 flex flex-col gap-8">
                    {loading ? (
                      <div className="flex items-center justify-center h-40 text-gray-400 text-sm">Загрузка...</div>
                    ) : (
                      <>
                        {/* Folder cards row */}
                        {folders.length > 0 && (
                          <div>
                            <h3 className="text-xs font-semibold text-gray-400 uppercase tracking-wide mb-4">Типы документов</h3>
                            <div className="flex gap-4 overflow-x-auto pb-2 -mx-1 px-1">
                              {folders.map(folder => {
                                const count = documents.filter(d => d.folder_id === folder.id).length
                                const color = resolveFolderColor(folder)
                                return (
                                  <div
                                    key={folder.id}
                                    onClick={() => { setActiveFolderId(folder.id); setViewMode('documents') }}
                                    className="relative flex-shrink-0 w-56 border border-gray-200 rounded-xl p-5 cursor-pointer hover:shadow-md hover:border-gray-300 transition-all group"
                                  >
                                    <div className="flex items-start justify-between mb-3">
                                      <h4 className="font-semibold text-ink text-sm leading-snug pr-4">{folder.name}</h4>
                                      <button
                                        onClick={e => { e.stopPropagation(); setFolderMenuId(folderMenuId === folder.id ? null : folder.id) }}
                                        className="p-1 rounded hover:bg-gray-100 text-gray-400 flex-shrink-0 opacity-0 group-hover:opacity-100 transition-opacity"
                                      >
                                        <MoreHorizontal size={15} />
                                      </button>
                                    </div>
                                    <p className="text-xs text-gray-400 mb-4">{count} {count === 1 ? 'документ' : count < 5 ? 'документа' : 'документов'}</p>
                                    {/* Colored bottom bar matching screenshot */}
                                    <div className="h-1 rounded-full" style={{ backgroundColor: color }} />

                                    {/* Context menu */}
                                    {folderMenuId === folder.id && (
                                      <div
                                        className="absolute right-2 top-10 bg-white border border-gray-200 rounded-lg shadow-lg z-20 py-1 w-40"
                                        onClick={e => e.stopPropagation()}
                                      >
                                        {editingFolderId === folder.id ? (
                                          <div className="flex items-center gap-1 px-3 py-2">
                                            <input
                                              autoFocus
                                              value={editFolderName}
                                              onChange={e => setEditFolderName(e.target.value)}
                                              onKeyDown={e => {
                                                if (e.key === 'Enter') handleRenameFolder(folder.id)
                                                if (e.key === 'Escape') { setEditingFolderId(null); setFolderMenuId(null) }
                                              }}
                                              className="flex-1 text-sm border-b border-brand outline-none bg-transparent min-w-0"
                                            />
                                            <button onClick={() => handleRenameFolder(folder.id)} className="text-brand-hover flex-shrink-0"><Check size={12} /></button>
                                            <button onClick={() => { setEditingFolderId(null); setFolderMenuId(null) }} className="text-gray-400 flex-shrink-0"><X size={12} /></button>
                                          </div>
                                        ) : (
                                          <button
                                            onClick={e => { e.stopPropagation(); setEditingFolderId(folder.id); setEditFolderName(folder.name) }}
                                            className="flex items-center gap-2 px-3 py-2 text-sm text-gray-700 hover:bg-gray-50 w-full text-left"
                                          >
                                            <Pencil size={13} /> Переименовать
                                          </button>
                                        )}
                                        <button
                                          onClick={e => { e.stopPropagation(); handleDeleteFolder(folder.id) }}
                                          className="flex items-center gap-2 px-3 py-2 text-sm text-red-600 hover:bg-red-50 w-full text-left"
                                        >
                                          <Trash2 size={13} /> Удалить
                                        </button>
                                      </div>
                                    )}
                                  </div>
                                )
                              })}
                            </div>
                          </div>
                        )}

                        {/* Recent documents (unassigned first, then by date) */}
                        {documents.filter(d => !d.folder_id).length > 0 && (
                          <section>
                            <h3 className="text-xs font-semibold text-gray-400 uppercase tracking-wide mb-4">Без папки</h3>
                            <div className="grid grid-cols-4 gap-4">
                              {documents.filter(d => !d.folder_id).map(doc => (
                                <DocCard key={doc.id} doc={doc} {...cardProps} onClick={() => router.push(`/documents/${doc.id}`)} />
                              ))}
                            </div>
                          </section>
                        )}

                        {todayDocs.length > 0 && (
                          <section>
                            <h3 className="text-xs font-semibold text-gray-400 uppercase tracking-wide mb-4">Сегодня</h3>
                            <div className="grid grid-cols-4 gap-4">
                              {todayDocs.map(doc => (
                                <DocCard key={doc.id} doc={doc} {...cardProps} onClick={() => router.push(`/documents/${doc.id}`)} />
                              ))}
                            </div>
                          </section>
                        )}

                        {earlierDocs.length > 0 && (
                          <section>
                            <h3 className="text-xs font-semibold text-gray-400 uppercase tracking-wide mb-4">Ранее</h3>
                            <div className="grid grid-cols-4 gap-4">
                              {earlierDocs.map(doc => (
                                <DocCard key={doc.id} doc={doc} {...cardProps} onClick={() => router.push(`/documents/${doc.id}`)} />
                              ))}
                            </div>
                          </section>
                        )}

                        {documents.length === 0 && folders.length === 0 && (
                          <div className="flex flex-col items-center justify-center h-40 gap-2">
                            <p className="text-gray-400 text-sm">Документов пока нет</p>
                          </div>
                        )}
                      </>
                    )}
                  </div>
                ) : viewMode === 'folders' ? (
                  // Folders view
                  <>
                    {loading ? (
                      <div className="flex items-center justify-center h-40 text-gray-400 text-sm">Загрузка...</div>
                    ) : folders.length === 0 ? (
                      <div className="flex flex-col items-center justify-center h-40 gap-2">
                        <p className="text-gray-400 text-sm">Папок пока нет</p>
                      </div>
                    ) : (
                      <div className="pt-6">
                        <div className="grid grid-cols-4 gap-4">
                          {folders.map(folder => (
                            <div key={folder.id} className="border border-gray-200 rounded-xl p-6 flex flex-col items-center justify-center text-center relative hover:border-gray-300 hover:shadow-sm transition-all cursor-pointer min-h-[160px] group" onClick={() => handleFolderClick(folder.id)}>
                              <div className="w-16 h-16 rounded-xl flex items-center justify-center mb-4 transition-colors" style={{ backgroundColor: `${resolveFolderColor(folder)}18` }}>
                                <Folder size={32} style={{ color: resolveFolderColor(folder) }} />
                              </div>
                              <p className="text-sm font-semibold text-ink line-clamp-2">{folder.name}</p>
                              <p className="text-xs text-gray-400 mt-2">{folder.document_type}</p>

                              <div className="absolute top-3 right-3 opacity-0 group-hover:opacity-100 transition-opacity">
                                <button
                                  onClick={e => { e.stopPropagation(); setFolderMenuId(folderMenuId === folder.id ? null : folder.id) }}
                                  className="p-1.5 rounded hover:bg-gray-200 text-gray-400 transition-colors"
                                >
                                  <MoreHorizontal size={16} />
                                </button>

                                {folderMenuId === folder.id && (
                                  <div className="absolute right-0 top-8 bg-white border border-gray-200 rounded-lg shadow-lg z-20 py-1 w-40">
                                    <button
                                      onClick={e => { e.stopPropagation(); setColorPickerFolderId(folder.id); setPendingColor(resolveFolderColor(folder)); setFolderMenuId(null) }}
                                      className="flex items-center gap-2 px-3 py-2 text-sm text-gray-700 hover:bg-gray-50 w-full text-left"
                                    >
                                      <Palette size={13} /> Изменить цвет
                                    </button>
                                    <button
                                      onClick={e => { e.stopPropagation(); setEditingFolderId(folder.id); setEditFolderName(folder.name); setFolderMenuId(null) }}
                                      className="flex items-center gap-2 px-3 py-2 text-sm text-gray-700 hover:bg-gray-50 w-full text-left"
                                    >
                                      <Pencil size={13} /> Переименовать
                                    </button>
                                    <button
                                      onClick={e => { e.stopPropagation(); handleDeleteFolder(folder.id) }}
                                      className="flex items-center gap-2 px-3 py-2 text-sm text-red-600 hover:bg-red-50 w-full text-left"
                                    >
                                      <Trash2 size={13} /> Удалить
                                    </button>
                                  </div>
                                )}
                              </div>

                              {colorPickerFolderId === folder.id && (
                                <div
                                  className="absolute right-0 top-0 bg-white border border-gray-200 rounded-xl shadow-xl z-30 p-4 w-72 mr-1"
                                  onClick={e => e.stopPropagation()}
                                >
                                  <FolderColorPicker
                                    selectedColor={pendingColor}
                                    previewName={folder.name}
                                    previewDocType={folder.document_type}
                                    onSelect={hex => setPendingColor(hex)}
                                  />
                                  <div className="flex gap-2 mt-3">
                                    <button
                                      onClick={() => setColorPickerFolderId(null)}
                                      className="flex-1 border border-gray-200 text-gray-600 text-xs py-1.5 rounded-full hover:bg-gray-50"
                                    >Отмена</button>
                                    <button
                                      onClick={() => handleChangeColor(folder.id, pendingColor)}
                                      className="flex-1 bg-brand hover:bg-brand-hover text-ink text-xs font-semibold py-1.5 rounded-full"
                                    >Сохранить</button>
                                  </div>
                                </div>
                              )}

                              {editingFolderId === folder.id && (
                                <div className="absolute inset-0 bg-white rounded-xl flex items-center justify-center">
                                  <input
                                    autoFocus
                                    value={editFolderName}
                                    onChange={e => setEditFolderName(e.target.value)}
                                    onKeyDown={e => {
                                      if (e.key === 'Enter') handleRenameFolder(folder.id)
                                      if (e.key === 'Escape') setEditingFolderId(null)
                                    }}
                                    className="text-sm border-b border-brand outline-none bg-transparent px-2 w-4/5"
                                  />
                                  <button onClick={() => handleRenameFolder(folder.id)} className="text-brand-hover flex-shrink-0 ml-1">
                                    <Check size={13} />
                                  </button>
                                  <button onClick={() => setEditingFolderId(null)} className="text-gray-400 flex-shrink-0">
                                    <X size={13} />
                                  </button>
                                </div>
                              )}
                            </div>
                          ))}
                        </div>
                      </div>
                    )}
                  </>
                ) : (
                  // Documents view
                  <>
                    {(loading || folderLoading) ? (
                      <div className="flex items-center justify-center h-40 text-gray-400 text-sm">Загрузка...</div>
                    ) : displayed.length === 0 ? (
                      <div className="flex flex-col items-center justify-center h-40 gap-2">
                        <p className="text-gray-400 text-sm">
                          {search ? 'Ничего не найдено' : activeFolderId ? 'Папка пуста' : 'Документов пока нет'}
                        </p>
                      </div>
                    ) : (
                      <>
                        {todayDocs.length > 0 && (
                          <section className="mb-8">
                            <h2 className="text-sm text-gray-500 mb-4">Сегодня</h2>
                            <div className="grid grid-cols-4 gap-4">
                              {todayDocs.map(doc => (
                                <DocCard key={doc.id} doc={doc} {...cardProps} onClick={() => router.push(`/documents/${doc.id}`)} />
                              ))}
                            </div>
                          </section>
                        )}
                        {earlierDocs.length > 0 && (
                          <section>
                            <h2 className="text-sm text-gray-500 mb-4">Ранее</h2>
                            <div className="grid grid-cols-4 gap-4">
                              {earlierDocs.map(doc => (
                                <DocCard key={doc.id} doc={doc} {...cardProps} onClick={() => router.push(`/documents/${doc.id}`)} />
                              ))}
                            </div>
                          </section>
                        )}
                      </>
                    )}
                  </>
                )}
              </div>
            </div>

          </div>
        </main>
      </div>
    </>
  )
}
