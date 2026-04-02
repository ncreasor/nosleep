'use client'

import { useState, useEffect, useCallback } from 'react'
import Sidebar from '@/components/Sidebar'
import { useAuth } from '@/components/useAuth'
import { useRouter } from 'next/navigation'
import FolderColorPicker from '@/components/FolderColorPicker'
import { DOC_TYPE_COLORS, resolveFolderColor } from '@/lib/folderColors'
import { Search, Plus, Upload, Check, X, MoreHorizontal, Trash2, Pencil, FolderPlus } from 'lucide-react'

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
    <div onClick={onClick} className="border border-gray-200 rounded-xl p-4 flex flex-col justify-between hover:border-gray-300 hover:shadow-sm transition-all cursor-pointer min-h-[130px]">
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
        <h2 className="font-bold text-ink text-base mb-4">Новый документ</h2>
        <form onSubmit={handleSubmit} className="flex flex-col gap-4">
          <input
            autoFocus
            type="text"
            value={title}
            onChange={e => setTitle(e.target.value)}
            placeholder="Введите название документа"
            className="border border-gray-200 rounded-xl px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-brand focus:border-transparent"
          />
          <div className="flex gap-2">
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
              className="flex-1 bg-[#AAFF45] hover:bg-[#9FEA3A] text-ink font-semibold py-2 rounded-full text-sm disabled:opacity-60 transition-colors"
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
        <h2 className="font-bold text-ink text-base mb-4">Новая папка</h2>
        <form onSubmit={handleSubmit} className="flex flex-col gap-4">
          <input
            autoFocus
            type="text"
            value={name}
            onChange={e => setName(e.target.value)}
            placeholder="Название папки"
            className="border border-gray-200 rounded-xl px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-brand focus:border-transparent"
          />
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
          <FolderColorPicker
            selectedColor={color}
            previewName={name}
            previewDocType={docType}
            onSelect={hex => {
              setColor(hex)
              setColorManuallySet(true)
            }}
          />
          <div className="flex gap-2">
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
              className="flex-1 bg-[#AAFF45] hover:bg-[#9FEA3A] text-ink font-semibold py-2 rounded-full text-sm disabled:opacity-60 transition-colors"
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
  const [folders, setFolders] = useState([])
  const [loading, setLoading] = useState(true)
  const [search, setSearch] = useState('')
  const [showNewDoc, setShowNewDoc] = useState(false)
  const [showNewFolder, setShowNewFolder] = useState(false)
  const [editingId, setEditingId] = useState(null)
  const [editTitle, setEditTitle] = useState('')
  const [openMenu, setOpenMenu] = useState(null)
  const [colorPickerFolderId, setColorPickerFolderId] = useState(null)
  const [pendingColor, setPendingColor] = useState(null)

  const fetchDocuments = useCallback(async () => {
    try {
      const res = await fetch(`${BACKEND}/documents`, { headers: authHeaders })
      if (res.ok) setDocuments(await res.json())
    } catch (e) {
      console.error(e)
    }
  }, [authHeaders])

  const fetchFolders = useCallback(async () => {
    try {
      const res = await fetch(`${BACKEND}/folders`, { headers: authHeaders })
      if (res.ok) setFolders(await res.json())
    } catch (e) {
      console.error(e)
    } finally {
      setLoading(false)
    }
  }, [authHeaders])

  useEffect(() => {
    if (!authLoading) {
      fetchDocuments()
      fetchFolders()
    }
  }, [authLoading])

  const handleCreate = async (title) => {
    try {
      const res = await fetch(`${BACKEND}/documents`, {
        method: 'POST',
        headers: { ...authHeaders, 'Content-Type': 'application/json' },
        body: JSON.stringify({ title })
      })
      if (res.ok) {
        const doc = await res.json()
        setShowNewDoc(false)
        router.push(`/documents/${doc.id}`)
      }
    } catch (e) {
      console.error(e)
    }
  }

  const handleCreateFolder = async (name, docType, color) => {
    try {
      const res = await fetch(`${BACKEND}/folders`, {
        method: 'POST',
        headers: { ...authHeaders, 'Content-Type': 'application/json' },
        body: JSON.stringify({ name, document_type: docType, color })
      })
      if (res.ok) {
        setShowNewFolder(false)
        fetchFolders()
      }
    } catch (e) {
      console.error(e)
    }
  }

  const handleRename = async (docId) => {
    try {
      await fetch(`${BACKEND}/documents/${docId}`, {
        method: 'PATCH',
        headers: { ...authHeaders, 'Content-Type': 'application/json' },
        body: JSON.stringify({ title: editTitle })
      })
      setEditingId(null)
      fetchDocuments()
    } catch (e) {
      console.error(e)
    }
  }

  const handleDelete = async (docId) => {
    try {
      await fetch(`${BACKEND}/documents/${docId}`, { method: 'DELETE', headers: authHeaders })
      fetchDocuments()
    } catch (e) {
      console.error(e)
    }
  }

  const handleChangeColor = async (folderId, hex) => {
    try {
      await fetch(`${BACKEND}/folders/${folderId}`, {
        method: 'PATCH',
        headers: { ...authHeaders, 'Content-Type': 'application/json' },
        body: JSON.stringify({ color: hex })
      })
      setColorPickerFolderId(null)
      fetchFolders()
    } catch (e) {
      console.error(e)
    }
  }

  const handleDeleteFolder = async (folderId) => {
    try {
      await fetch(`${BACKEND}/folders/${folderId}`, { method: 'DELETE', headers: authHeaders })
      fetchFolders()
    } catch (e) {
      console.error(e)
    }
  }

  if (authLoading) return null

  const filteredDocs = documents.filter(d => d.title.toLowerCase().includes(search.toLowerCase()))
  const todayDocs = filteredDocs.filter(d => isToday(d.created_at))
  const olderDocs = filteredDocs.filter(d => !isToday(d.created_at))

  return (
    <div className="flex h-screen bg-gray-50">
      <Sidebar />

      <main className="flex-1 overflow-hidden min-w-0 py-4 pr-4">
        <div className="rounded-2xl border border-gray-300 bg-white shadow-sm overflow-hidden h-full flex flex-col">
          {/* Header */}
          <div className="border-b border-gray-200 p-6">
            <div className="flex items-center justify-between gap-4 mb-4">
              <h1 className="text-2xl font-bold text-ink">Документы</h1>
              <div className="flex items-center gap-3">
                <div className="relative flex-1 max-w-sm">
                  <Search className="absolute left-3 top-2.5 text-gray-400" size={18} />
                  <input
                    type="text"
                    placeholder="Поиск документов"
                    value={search}
                    onChange={e => setSearch(e.target.value)}
                    className="w-full border border-gray-200 rounded-lg pl-10 pr-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-brand focus:border-transparent"
                  />
                </div>
                <button
                  onClick={() => setShowNewDoc(true)}
                  className="flex items-center gap-2 px-4 py-2 bg-[#AAFF45] hover:bg-[#9FEA3A] text-ink font-semibold rounded-lg transition-colors whitespace-nowrap"
                >
                  <Plus size={18} />
                  Загрузить документ
                </button>
              </div>
            </div>

            {/* Folders */}
            {folders.length > 0 && (
              <div className="mb-4">
                <h3 className="text-xs font-semibold text-gray-400 uppercase tracking-wide mb-3">Типы документов</h3>
                <div className="flex gap-4 overflow-x-auto pb-2">
                  {folders.map(folder => (
                    <div
                      key={folder.id}
                      className="flex-shrink-0 border border-gray-200 rounded-lg p-4 min-w-[200px] hover:border-gray-300 transition-colors group relative"
                      style={{
                        borderBottom: `4px solid ${resolveFolderColor(folder)}`
                      }}
                    >
                      <h4 className="font-semibold text-sm text-ink mb-1">{folder.name}</h4>
                      <p className="text-xs text-gray-500">{documents.filter(d => d.folder_id === folder.id).length} документов</p>
                      <button
                        onClick={e => {
                          e.stopPropagation()
                          setColorPickerFolderId(folder.id)
                          setPendingColor(resolveFolderColor(folder))
                        }}
                        className="opacity-0 group-hover:opacity-100 absolute top-2 right-2 transition-opacity"
                      >
                        <MoreHorizontal size={16} className="text-gray-400" />
                      </button>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>

          {/* Documents */}
          <div className="flex-1 overflow-y-auto p-6">
            {loading ? (
              <div className="flex items-center justify-center h-40 text-gray-400">Загрузка...</div>
            ) : (
              <>
                {todayDocs.length > 0 && (
                  <div className="mb-8">
                    <h3 className="text-xs font-semibold text-gray-400 uppercase tracking-wide mb-3">Сегодня</h3>
                    <div className="grid grid-cols-4 gap-4">
                      {todayDocs.map(doc => (
                        <DocCard
                          key={doc.id}
                          doc={doc}
                          openMenu={openMenu}
                          setOpenMenu={setOpenMenu}
                          editingId={editingId}
                          setEditingId={setEditingId}
                          editTitle={editTitle}
                          setEditTitle={setEditTitle}
                          onDelete={handleDelete}
                          onRename={handleRename}
                          onClick={() => router.push(`/documents/${doc.id}`)}
                        />
                      ))}
                    </div>
                  </div>
                )}

                {olderDocs.length > 0 && (
                  <div>
                    <h3 className="text-xs font-semibold text-gray-400 uppercase tracking-wide mb-3">Ранее</h3>
                    <div className="grid grid-cols-4 gap-4">
                      {olderDocs.map(doc => (
                        <DocCard
                          key={doc.id}
                          doc={doc}
                          openMenu={openMenu}
                          setOpenMenu={setOpenMenu}
                          editingId={editingId}
                          setEditingId={setEditingId}
                          editTitle={editTitle}
                          setEditTitle={setEditTitle}
                          onDelete={handleDelete}
                          onRename={handleRename}
                          onClick={() => router.push(`/documents/${doc.id}`)}
                        />
                      ))}
                    </div>
                  </div>
                )}

                {filteredDocs.length === 0 && (
                  <div className="flex items-center justify-center h-40 text-gray-400">Документов не найдено</div>
                )}
              </>
            )}
          </div>
        </div>
      </main>

      {/* Color Picker for Folders */}
      {colorPickerFolderId && (
        <div className="fixed inset-0 bg-black bg-opacity-30 flex items-center justify-center z-50">
          <div className="bg-white rounded-2xl border border-gray-200 shadow-xl p-6">
            <FolderColorPicker
              selectedColor={pendingColor}
              previewName={folders.find(f => f.id === colorPickerFolderId)?.name}
              onSelect={hex => handleChangeColor(colorPickerFolderId, hex)}
            />
            <div className="flex gap-2 mt-4">
              <button
                onClick={() => {
                  handleDeleteFolder(colorPickerFolderId)
                  setColorPickerFolderId(null)
                }}
                className="flex-1 border border-red-200 text-red-600 font-medium py-2 rounded-full text-sm hover:bg-red-50 transition-colors"
              >
                Удалить папку
              </button>
              <button
                onClick={() => setColorPickerFolderId(null)}
                className="flex-1 border border-gray-200 text-gray-600 font-medium py-2 rounded-full text-sm hover:bg-gray-50 transition-colors"
              >
                Закрыть
              </button>
            </div>
          </div>
        </div>
      )}

      {showNewDoc && <NewDocModal onClose={() => setShowNewDoc(false)} onCreate={handleCreate} />}
      {showNewFolder && <NewFolderModal onClose={() => setShowNewFolder(false)} onCreate={handleCreateFolder} />}
    </div>
  )
}
