'use client'

import { useState, useEffect } from 'react'
import { useRouter } from 'next/navigation'
import Sidebar from '@/components/Sidebar'
import { useAuth } from '@/components/useAuth'
import { Search, Plus, ChevronDown, ChevronRight, MoreHorizontal, Trash2, Pencil } from 'lucide-react'

const BACKEND = process.env.NEXT_PUBLIC_BACKEND_URL || 'http://localhost:8000'

export default function TemplatesPage() {
  const { loading: authLoading, authHeaders } = useAuth()
  const router = useRouter()

  const [folders, setFolders] = useState([])
  const [expandedFolders, setExpandedFolders] = useState({})
  const [search, setSearch] = useState('')
  const [loading, setLoading] = useState(true)
  const [showNewTemplate, setShowNewTemplate] = useState(null)
  const [templateName, setTemplateName] = useState('')
  const [templateFolders, setTemplateFolders] = useState({})

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

        // Fetch templates for each folder
        const templates = {}
        for (const folder of data) {
          const tRes = await fetch(`${BACKEND}/templates?folder_id=${folder.id}`, { headers: authHeaders })
          if (tRes.ok) {
            templates[folder.id] = await tRes.json()
          }
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
    setExpandedFolders(prev => ({
      ...prev,
      [folderId]: !prev[folderId]
    }))
  }

  const handleCreateTemplate = async () => {
    if (!templateName.trim() || !showNewTemplate) return

    try {
      const res = await fetch(`${BACKEND}/templates`, {
        method: 'POST',
        headers: { ...authHeaders, 'Content-Type': 'application/json' },
        body: JSON.stringify({
          name: templateName.trim(),
          content: '',
          folder_id: showNewTemplate,
          description: ''
        })
      })

      if (res.ok) {
        setTemplateName('')
        setShowNewTemplate(null)
        fetchFolders()
      }
    } catch (e) {
      console.error('Error creating template:', e)
    }
  }

  if (authLoading) return null

  const filteredFolders = folders.filter(f =>
    f.name.toLowerCase().includes(search.toLowerCase())
  )

  return (
    <div className="flex h-screen bg-gray-50">
      <Sidebar />

      <main className="flex-1 overflow-hidden min-w-0 py-4 pr-4">
        <div className="rounded-2xl border border-gray-300 bg-white shadow-sm overflow-hidden h-full flex flex-col">
          {/* Header */}
          <div className="border-b border-gray-200 p-6 flex items-center justify-between gap-4">
            <h1 className="text-2xl font-bold text-ink">Шаблоны</h1>
            <div className="flex items-center gap-3 flex-1 max-w-xl">
              <div className="relative flex-1">
                <Search className="absolute left-3 top-2.5 text-gray-400" size={18} />
                <input
                  type="text"
                  placeholder="Поиск шаблонов"
                  value={search}
                  onChange={e => setSearch(e.target.value)}
                  className="w-full border border-gray-200 rounded-lg pl-10 pr-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-brand focus:border-transparent"
                />
              </div>
            </div>
            <button
              onClick={() => setShowNewTemplate(-1)}
              className="flex items-center gap-2 px-4 py-2 bg-[#AAFF45] hover:bg-[#9FEA3A] text-ink font-semibold rounded-lg transition-colors"
            >
              <Plus size={18} />
              Создать шаблон
            </button>
          </div>

          {/* Content */}
          <div className="flex-1 overflow-y-auto p-6">
            {loading ? (
              <div className="flex items-center justify-center h-40 text-gray-400">Загрузка...</div>
            ) : filteredFolders.length === 0 ? (
              <div className="flex items-center justify-center h-40 text-gray-400">Шаблонов не найдено</div>
            ) : (
              <div className="space-y-4">
                {filteredFolders.map(folder => (
                  <div key={folder.id} className="border border-gray-200 rounded-lg overflow-hidden">
                    {/* Folder Header */}
                    <button
                      onClick={() => toggleFolder(folder.id)}
                      className="w-full flex items-center justify-between p-4 hover:bg-gray-50 transition-colors"
                    >
                      <div className="flex items-center gap-3">
                        {expandedFolders[folder.id] ? <ChevronDown size={18} /> : <ChevronRight size={18} />}
                        <span className="font-semibold text-ink">{folder.name}</span>
                      </div>
                      <span className="text-sm text-gray-500">{templateFolders[folder.id]?.length || 0} шаблонов</span>
                    </button>

                    {/* Folder Content */}
                    {expandedFolders[folder.id] && (
                      <div className="border-t border-gray-200 p-4 bg-gray-50 grid grid-cols-4 gap-4">
                        {templateFolders[folder.id]?.length > 0 ? (
                          templateFolders[folder.id].map(template => (
                            <div
                              key={template.id}
                              className="border border-gray-200 rounded-lg p-4 bg-white hover:border-gray-300 cursor-pointer transition-colors group"
                            >
                              <div className="flex items-start justify-between mb-2">
                                <h3 className="font-semibold text-sm text-ink line-clamp-2">{template.name}</h3>
                                <button className="opacity-0 group-hover:opacity-100 transition-opacity">
                                  <MoreHorizontal size={16} className="text-gray-400" />
                                </button>
                              </div>
                              <p className="text-xs text-gray-500">
                                {template.updated_at ? new Date(template.updated_at).toLocaleDateString('ru-RU') : 'Дата не указана'}
                              </p>
                            </div>
                          ))
                        ) : (
                          <p className="text-sm text-gray-400 col-span-4">Нет шаблонов</p>
                        )}
                      </div>
                    )}
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      </main>

      {/* New Template Modal */}
      {showNewTemplate !== null && (
        <div className="fixed inset-0 bg-black bg-opacity-30 flex items-center justify-center z-50">
          <div className="bg-white rounded-2xl border border-gray-200 shadow-xl w-full max-w-md p-6">
            <h2 className="font-bold text-ink text-base mb-4">Новый шаблон</h2>
            <input
              autoFocus
              type="text"
              value={templateName}
              onChange={e => setTemplateName(e.target.value)}
              placeholder="Название шаблона"
              className="w-full border border-gray-200 rounded-xl px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-brand focus:border-transparent mb-4"
              onKeyDown={e => e.key === 'Enter' && handleCreateTemplate()}
            />
            <div className="flex gap-2">
              <button
                onClick={() => setShowNewTemplate(null)}
                className="flex-1 border border-gray-200 text-gray-600 font-medium py-2 rounded-full text-sm hover:bg-gray-50 transition-colors"
              >
                Отмена
              </button>
              <button
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
    </div>
  )
}
