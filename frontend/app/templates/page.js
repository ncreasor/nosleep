'use client'

import { useState, useEffect, useRef } from 'react'
import { useRouter } from 'next/navigation'
import Sidebar from '@/components/Sidebar'
import { useAuth } from '@/components/useAuth'
import { Search, Plus, ChevronDown, ChevronRight, MoreHorizontal, FileUp, Loader2, Upload } from 'lucide-react'

const BACKEND = process.env.NEXT_PUBLIC_BACKEND_URL || 'http://localhost:8000'

function defaultNameFromFilename(name) {
  if (!name) return 'Новый шаблон'
  const base = name.replace(/\.(docx|doc)$/i, '')
  return base || 'Новый шаблон'
}

function isWordTemplateFile(name) {
  if (!name) return false
  const n = name.toLowerCase()
  return n.endsWith('.docx') || n.endsWith('.doc')
}

function textToRichHtml(text) {
  const t = (text || '').trim()
  if (!t) return '<p><br></p>'
  return t
    .split(/\n{2,}/)
    .map((p) => `<p>${p.replace(/\n/g, '<br>')}</p>`)
    .join('')
}

function serializeTemplateContent(html) {
  return JSON.stringify({ format: 'rich_html', html })
}

export default function TemplatesPage() {
  const { loading: authLoading, authHeaders } = useAuth()
  const router = useRouter()
  const docxInputRef = useRef(null)

  const [folders, setFolders] = useState([])
  const [expandedFolders, setExpandedFolders] = useState({})
  const [search, setSearch] = useState('')
  const [loading, setLoading] = useState(true)
  const [showNewTemplate, setShowNewTemplate] = useState(null)
  const [templateName, setTemplateName] = useState('')
  const [templateFolders, setTemplateFolders] = useState({})
  const [newTemplateFolderId, setNewTemplateFolderId] = useState(null)

  const [docxModal, setDocxModal] = useState(null)
  const [docxLoading, setDocxLoading] = useState(false)
  const [docxDropActive, setDocxDropActive] = useState(false)

  useEffect(() => {
    if (authLoading) return
    fetchFolders()
  }, [authLoading])

  const fetchFolders = async () => {
    try {
      const res = await fetch(`${BACKEND}/templates/folders`, { headers: authHeaders })
      if (res.ok) {
        const data = await res.json()
        setFolders(data)
        if (data.length > 0) {
          setExpandedFolders((prev) => ({ ...prev, [data[0].id]: true }))
        }
        const templates = {}
        for (const folder of data) {
          const tRes = await fetch(`${BACKEND}/templates?folder_id=${folder.id}`, { headers: authHeaders })
          if (tRes.ok) {
            templates[folder.id] = await tRes.json()
          }
        }
        const rootRes = await fetch(`${BACKEND}/templates`, { headers: authHeaders })
        if (rootRes.ok) {
          const all = await rootRes.json()
          templates.__root = all.filter((t) => t.folder_id == null)
        } else {
          templates.__root = []
        }
        setTemplateFolders(templates)
      }
    } catch (e) {
      console.error('Error fetching folders:', e)
    } finally {
      setLoading(false)
    }
  }

  const toggleFolder = (folderId) => {
    setExpandedFolders((prev) => ({
      ...prev,
      [folderId]: !prev[folderId],
    }))
  }

  const handleCreateTemplate = async () => {
    if (!templateName.trim() || !showNewTemplate) return
    const folderId = newTemplateFolderId
    try {
      const res = await fetch(`${BACKEND}/templates`, {
        method: 'POST',
        headers: { ...authHeaders, 'Content-Type': 'application/json' },
        body: JSON.stringify({
          name: templateName.trim(),
          content: serializeTemplateContent('<p><br></p>'),
          folder_id: folderId,
          description: '',
        }),
      })

      if (res.ok) {
        const created = await res.json()
        setTemplateName('')
        setShowNewTemplate(null)
        setNewTemplateFolderId(null)
        fetchFolders()
        router.push(`/templates/${created.id}`)
      }
    } catch (e) {
      console.error('Error creating template:', e)
    }
  }

  const openDocxPicker = () => {
    docxInputRef.current?.click()
  }

  const processWordFile = async (file) => {
    if (!file || !isWordTemplateFile(file.name)) {
      alert('Нужен файл Word: .doc или .docx')
      return
    }
    setDocxLoading(true)
    try {
      const fd = new FormData()
      fd.append('file', file)
      const res = await fetch(`${BACKEND}/templates/from-word`, {
        method: 'POST',
        headers: { ...authHeaders },
        body: fd,
      })
      if (!res.ok) {
        const raw = await res.text()
        let msg = raw || 'Не удалось прочитать файл'
        try {
          const j = JSON.parse(raw)
          if (j.detail != null) msg = typeof j.detail === 'string' ? j.detail : JSON.stringify(j.detail)
        } catch {
          /* plain text error body */
        }
        console.error(msg)
        alert(msg)
        return
      }
      const data = await res.json()
      const suggested = defaultNameFromFilename(data.filename || file.name)
      setDocxModal({
        text: data.text || '',
        suggestedName: suggested,
        name: suggested,
      })
      setNewTemplateFolderId(folders[0]?.id ?? null)
    } catch (err) {
      console.error(err)
      alert('Ошибка загрузки')
    } finally {
      setDocxLoading(false)
    }
  }

  const onDocxSelected = async (e) => {
    const file = e.target.files?.[0]
    e.target.value = ''
    await processWordFile(file)
  }

  const onDocxDragEnter = (e) => {
    e.preventDefault()
    e.stopPropagation()
    if (e.dataTransfer.types?.includes('Files')) setDocxDropActive(true)
  }

  const onDocxDragLeave = (e) => {
    e.preventDefault()
    e.stopPropagation()
    const next = e.relatedTarget
    if (!next || !e.currentTarget.contains(next)) setDocxDropActive(false)
  }

  const onDocxDragOver = (e) => {
    e.preventDefault()
    e.stopPropagation()
    e.dataTransfer.dropEffect = 'copy'
  }

  const onDocxDrop = async (e) => {
    e.preventDefault()
    e.stopPropagation()
    setDocxDropActive(false)
    const file = e.dataTransfer.files?.[0]
    await processWordFile(file)
  }

  const confirmDocxTemplate = async () => {
    if (!docxModal) return
    const name = (docxModal.name || docxModal.suggestedName || 'Шаблон').trim()
    if (!name) return
    const html = textToRichHtml(docxModal.text)
    const content = serializeTemplateContent(html)
    try {
      const res = await fetch(`${BACKEND}/templates`, {
        method: 'POST',
        headers: { ...authHeaders, 'Content-Type': 'application/json' },
        body: JSON.stringify({
          name,
          content,
          folder_id: newTemplateFolderId,
          description: 'Импорт из Word',
        }),
      })
      if (res.ok) {
        const created = await res.json()
        localStorage.setItem(`template-content-${created.id}`, html)
        setDocxModal(null)
        setNewTemplateFolderId(null)
        fetchFolders()
        router.push(`/templates/${created.id}`)
      }
    } catch (e) {
      console.error(e)
    }
  }

  if (authLoading) return null

  const q = search.toLowerCase().trim()
  const filteredFolders = folders.filter((f) => {
    if (!q) return true
    if (f.name.toLowerCase().includes(q)) return true
    const list = templateFolders[f.id] || []
    return list.some((t) => t.name.toLowerCase().includes(q))
  })

  const filterTemplates = (list) => {
    if (!list) return []
    if (!q) return list
    return list.filter((t) => t.name.toLowerCase().includes(q))
  }

  return (
    <div className="flex h-screen bg-gray-50">
      <Sidebar />

      <main className="flex-1 overflow-hidden min-w-0 py-4 pr-4">
        <div className="rounded-2xl border border-gray-300 bg-white shadow-sm overflow-hidden h-full flex flex-col">
          <div className="border-b border-gray-200 p-6 flex items-center justify-between gap-4 flex-wrap">
            <h1 className="text-2xl font-bold text-ink">Шаблоны</h1>
            <div className="flex items-center gap-3 flex-1 max-w-xl min-w-[200px]">
              <div className="relative flex-1">
                <Search className="absolute left-3 top-2.5 text-gray-400" size={18} />
                <input
                  type="text"
                  placeholder="Поиск по названию"
                  value={search}
                  onChange={(e) => setSearch(e.target.value)}
                  className="w-full border border-gray-200 rounded-lg pl-10 pr-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-brand focus:border-transparent"
                />
              </div>
            </div>
            <div className="flex items-center gap-2">
              <input
                ref={docxInputRef}
                type="file"
                accept=".doc,.docx,application/msword,application/vnd.openxmlformats-officedocument.wordprocessingml.document"
                className="hidden"
                onChange={onDocxSelected}
              />
              <button
                type="button"
                onClick={openDocxPicker}
                disabled={docxLoading}
                className="flex items-center gap-2 px-4 py-2 border border-gray-300 text-ink font-semibold rounded-lg hover:bg-gray-50 transition-colors disabled:opacity-60"
              >
                {docxLoading ? <Loader2 size={18} className="animate-spin" /> : <FileUp size={18} />}
                Из Word
              </button>
              <button
                type="button"
                onClick={() => {
                  setShowNewTemplate(true)
                  setTemplateName('')
                  setNewTemplateFolderId(folders[0]?.id ?? null)
                }}
                className="flex items-center gap-2 px-4 py-2 bg-[#AAFF45] hover:bg-[#9FEA3A] text-ink font-semibold rounded-lg transition-colors"
              >
                <Plus size={18} />
                Пустой шаблон
              </button>
            </div>
          </div>

          <div className="flex-1 overflow-y-auto p-6">
            <button
              type="button"
              onClick={openDocxPicker}
              disabled={docxLoading}
              onDragEnter={onDocxDragEnter}
              onDragLeave={onDocxDragLeave}
              onDragOver={onDocxDragOver}
              onDrop={onDocxDrop}
              className={`w-full mb-6 rounded-xl border-2 border-dashed px-6 py-10 text-center transition-colors disabled:opacity-60 disabled:pointer-events-none ${
                docxDropActive
                  ? 'border-[#AAFF45] bg-[#f4ffe8]'
                  : 'border-gray-200 bg-gray-50/80 hover:border-gray-300 hover:bg-gray-50'
              }`}
            >
              {docxLoading ? (
                <div className="flex flex-col items-center gap-3 text-gray-600">
                  <Loader2 size={36} className="animate-spin text-brand" />
                  <span className="text-sm font-medium">Читаем файл…</span>
                </div>
              ) : (
                <div className="flex flex-col items-center gap-2 pointer-events-none">
                  <div
                    className={`rounded-full p-3 ${docxDropActive ? 'bg-[#AAFF45]/30' : 'bg-white border border-gray-200'}`}
                  >
                    <Upload size={28} className="text-gray-700" />
                  </div>
                  <p className="text-sm font-semibold text-ink">Перетащите .doc или .docx сюда</p>
                  <p className="text-xs text-gray-500">или нажмите, чтобы выбрать файл на диске</p>
                </div>
              )}
            </button>

            {loading ? (
              <div className="flex items-center justify-center h-40 text-gray-400">Загрузка...</div>
            ) : folders.length === 0 ? (
              <div className="space-y-4">
                <p className="text-center text-gray-500 text-sm">
                  Папок пока нет — шаблоны без папки:
                </p>
                <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
                  {filterTemplates(templateFolders.__root)?.map((template) => (
                    <button
                      type="button"
                      key={template.id}
                      onClick={() => router.push(`/templates/${template.id}`)}
                      className="text-left border border-gray-200 rounded-lg p-4 bg-white hover:border-gray-400 cursor-pointer transition-colors"
                    >
                      <h3 className="font-semibold text-sm text-ink line-clamp-2">{template.name}</h3>
                      <p className="text-xs text-gray-500 mt-1">
                        {template.updated_at
                          ? new Date(template.updated_at).toLocaleDateString('ru-RU')
                          : ''}
                      </p>
                    </button>
                  ))}
                </div>
                {(!templateFolders.__root || templateFolders.__root.length === 0) && (
                  <p className="text-center text-gray-400 text-sm py-8">Шаблонов пока нет — загрузите Word (.doc / .docx) или создайте пустой.</p>
                )}
              </div>
            ) : (
              <div className="space-y-4">
                {filteredFolders.map((folder) => (
                  <div key={folder.id} className="border border-gray-200 rounded-lg overflow-hidden">
                    <button
                      type="button"
                      onClick={() => toggleFolder(folder.id)}
                      className="w-full flex items-center justify-between p-4 hover:bg-gray-50 transition-colors"
                    >
                      <div className="flex items-center gap-3">
                        {expandedFolders[folder.id] ? <ChevronDown size={18} /> : <ChevronRight size={18} />}
                        <span className="font-semibold text-ink">{folder.name}</span>
                      </div>
                      <span className="text-sm text-gray-500">
                        {filterTemplates(templateFolders[folder.id]).length} шаблонов
                      </span>
                    </button>

                    {expandedFolders[folder.id] && (
                      <div className="border-t border-gray-200 p-4 bg-gray-50 grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
                        {filterTemplates(templateFolders[folder.id])?.length > 0 ? (
                          filterTemplates(templateFolders[folder.id]).map((template) => (
                            <button
                              type="button"
                              key={template.id}
                              onClick={() => router.push(`/templates/${template.id}`)}
                              className="text-left border border-gray-200 rounded-lg p-4 bg-white hover:border-gray-400 hover:shadow-sm cursor-pointer transition-colors group"
                            >
                              <div className="flex items-start justify-between mb-2">
                                <h3 className="font-semibold text-sm text-ink line-clamp-2">{template.name}</h3>
                                <MoreHorizontal size={16} className="text-gray-300 opacity-0 group-hover:opacity-100" />
                              </div>
                              <p className="text-xs text-gray-500">
                                {template.updated_at
                                  ? new Date(template.updated_at).toLocaleDateString('ru-RU')
                                  : 'Дата не указана'}
                              </p>
                            </button>
                          ))
                        ) : (
                          <p className="text-sm text-gray-400 col-span-4">Нет шаблонов</p>
                        )}
                      </div>
                    )}
                  </div>
                ))}

                {templateFolders.__root?.length > 0 && (
                  <div className="border border-dashed border-gray-300 rounded-lg p-4">
                    <p className="text-xs font-semibold text-gray-500 mb-3 uppercase">Без папки</p>
                    <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
                      {filterTemplates(templateFolders.__root).map((template) => (
                        <button
                          type="button"
                          key={template.id}
                          onClick={() => router.push(`/templates/${template.id}`)}
                          className="text-left border border-gray-200 rounded-lg p-4 bg-white hover:border-gray-400 cursor-pointer transition-colors"
                        >
                          <h3 className="font-semibold text-sm text-ink line-clamp-2">{template.name}</h3>
                          <p className="text-xs text-gray-500 mt-1">
                            {template.updated_at
                              ? new Date(template.updated_at).toLocaleDateString('ru-RU')
                              : ''}
                          </p>
                        </button>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            )}
          </div>
        </div>
      </main>

      {showNewTemplate && (
        <div className="fixed inset-0 bg-black bg-opacity-30 flex items-center justify-center z-50">
          <div className="bg-white rounded-2xl border border-gray-200 shadow-xl w-full max-w-md p-6">
            <h2 className="font-bold text-ink text-base mb-4">Новый шаблон</h2>
            <input
              autoFocus
              type="text"
              value={templateName}
              onChange={(e) => setTemplateName(e.target.value)}
              placeholder="Название шаблона"
              className="w-full border border-gray-200 rounded-xl px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-brand focus:border-transparent mb-3"
              onKeyDown={(e) => e.key === 'Enter' && handleCreateTemplate()}
            />
            {folders.length > 0 && (
              <label className="block text-xs text-gray-500 mb-1">Папка</label>
            )}
            {folders.length > 0 && (
              <select
                value={newTemplateFolderId ?? ''}
                onChange={(e) => setNewTemplateFolderId(e.target.value ? Number(e.target.value) : null)}
                className="w-full border border-gray-200 rounded-xl px-3 py-2 text-sm mb-4"
              >
                <option value="">Без папки</option>
                {folders.map((f) => (
                  <option key={f.id} value={f.id}>
                    {f.name}
                  </option>
                ))}
              </select>
            )}
            <div className="flex gap-2">
              <button
                type="button"
                onClick={() => {
                  setShowNewTemplate(null)
                  setNewTemplateFolderId(null)
                }}
                className="flex-1 border border-gray-200 text-gray-600 font-medium py-2 rounded-full text-sm hover:bg-gray-50 transition-colors"
              >
                Отмена
              </button>
              <button
                type="button"
                onClick={handleCreateTemplate}
                disabled={!templateName.trim()}
                className="flex-1 bg-[#AAFF45] hover:bg-[#9FEA3A] text-ink font-semibold py-2 rounded-full text-sm disabled:opacity-60 transition-colors"
              >
                Создать
              </button>
            </div>
          </div>
        </div>
      )}

      {docxModal && (
        <div className="fixed inset-0 bg-black bg-opacity-30 flex items-center justify-center z-50">
          <div className="bg-white rounded-2xl border border-gray-200 shadow-xl w-full max-w-md p-6">
            <h2 className="font-bold text-ink text-base mb-2">Шаблон из Word</h2>
            <p className="text-xs text-gray-500 mb-4">Текст извлечён — отредактируйте в редакторе после создания.</p>
            <input
              type="text"
              value={docxModal.name ?? ''}
              onChange={(e) => setDocxModal((m) => ({ ...m, name: e.target.value }))}
              placeholder="Название шаблона"
              className="w-full border border-gray-200 rounded-xl px-3 py-2 text-sm mb-3"
            />
            {folders.length > 0 && (
              <select
                value={newTemplateFolderId ?? ''}
                onChange={(e) => setNewTemplateFolderId(e.target.value ? Number(e.target.value) : null)}
                className="w-full border border-gray-200 rounded-xl px-3 py-2 text-sm mb-4"
              >
                <option value="">Без папки</option>
                {folders.map((f) => (
                  <option key={f.id} value={f.id}>
                    {f.name}
                  </option>
                ))}
              </select>
            )}
            <div className="flex gap-2">
              <button
                type="button"
                onClick={() => setDocxModal(null)}
                className="flex-1 border border-gray-200 text-gray-600 font-medium py-2 rounded-full text-sm hover:bg-gray-50"
              >
                Отмена
              </button>
              <button
                type="button"
                onClick={confirmDocxTemplate}
                disabled={!(docxModal.name || docxModal.suggestedName || '').trim()}
                className="flex-1 bg-[#AAFF45] hover:bg-[#9FEA3A] text-ink font-semibold py-2 rounded-full text-sm disabled:opacity-60"
              >
                Создать и открыть
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
