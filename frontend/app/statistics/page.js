'use client'

import { useState, useEffect } from 'react'
import Sidebar from '@/components/Sidebar'
import { useAuth } from '@/components/useAuth'

const BACKEND = process.env.NEXT_PUBLIC_BACKEND_URL || 'http://localhost:8000'

const CORRECTION_TYPE_LABELS = {
  law_ref: 'Ссылки на нормы',
  outdated: 'Устаревшие нормы',
  formulation: 'Формулировка',
  norm_remedy: 'Правки норм',
}

export default function StatisticsPage() {
  const { loading: authLoading, authHeaders } = useAuth()

  const [activeTab, setActiveTab] = useState('overview')
  const [stats, setStats] = useState({
    documents: 0,
    templates: 0,
    corrections: 0,
    exports: 0
  })
  const [documents, setDocuments] = useState([])
  const [correctionsByType, setCorrectionsByType] = useState({})
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    if (authLoading) return
    fetchStats()
  }, [authLoading])

  const fetchStats = async () => {
    try {
      const [docsRes, templatesRes, statsRes] = await Promise.all([
        fetch(`${BACKEND}/documents`, { headers: authHeaders }),
        fetch(`${BACKEND}/templates`, { headers: authHeaders }),
        fetch(`${BACKEND}/documents/stats`, { headers: authHeaders }),
      ])

      const docs = docsRes.ok ? await docsRes.json() : []
      const templates = templatesRes.ok ? await templatesRes.json() : []
      const summary = statsRes.ok ? await statsRes.json() : { corrections_total: 0, corrections_by_type: {} }

      setDocuments(docs)
      setCorrectionsByType(summary.corrections_by_type || {})
      setStats({
        documents: docs.length,
        templates: templates.length,
        corrections: summary.corrections_total ?? 0,
        exports: 0
      })
    } catch (e) {
      console.error('Error fetching stats:', e)
    } finally {
      setLoading(false)
    }
  }

  if (authLoading) return null

  const validDocuments = documents.filter(d => d.classification)
  const validCount = validDocuments.filter(d => d.classification === 'valid').length
  const invalidCount = validDocuments.length - validCount
  const classificationPct = validDocuments.length
    ? Math.round((validCount / validDocuments.length) * 100)
    : 0
  const correctionRows = Object.entries(correctionsByType)
    .map(([key, n]) => ({
      key,
      n,
      label: CORRECTION_TYPE_LABELS[key] || key,
    }))
    .sort((a, b) => b.n - a.n)

  return (
    <div className="flex h-screen bg-gray-50">
      <Sidebar />

      <main className="flex-1 overflow-hidden min-w-0 py-4 pr-4">
        <div className="rounded-2xl border border-gray-300 bg-white shadow-sm overflow-hidden h-full flex flex-col">
          {/* Header */}
          <div className="border-b border-gray-200 p-6">
            <h1 className="text-2xl font-bold text-ink mb-4">Статистика</h1>
            <div className="flex gap-2">
              {['overview', 'documents', 'templates'].map(tab => (
                <button
                  key={tab}
                  onClick={() => setActiveTab(tab)}
                  className={`px-4 py-2 rounded-lg font-medium text-sm transition-colors ${
                    activeTab === tab
                      ? 'bg-[#AAFF45] text-ink'
                      : 'border border-gray-200 text-gray-600 hover:bg-gray-50'
                  }`}
                >
                  {tab === 'overview' && 'Овервью'}
                  {tab === 'documents' && 'Документы'}
                  {tab === 'templates' && 'Шаблоны'}
                </button>
              ))}
            </div>
          </div>

          {/* Content */}
          <div className="flex-1 overflow-y-auto p-6">
            {loading ? (
              <div className="flex items-center justify-center h-40 text-gray-400">Загрузка...</div>
            ) : activeTab === 'overview' ? (
              <div className="space-y-6">
                {/* Metrics */}
                <div className="grid grid-cols-4 gap-6">
                  {[
                    { label: 'Документы', value: stats.documents, change: '+12%' },
                    { label: 'Шаблоны', value: stats.templates, change: '+12%' },
                    { label: 'Поправки', value: stats.corrections, change: null },
                    { label: 'Экспорты', value: stats.exports, change: '+12%' }
                  ].map((metric, i) => (
                    <div key={i} className="border border-gray-200 rounded-lg p-4">
                      <p className="text-xs font-medium text-gray-500 mb-1 uppercase tracking-wide">{metric.label}</p>
                      <p className="text-3xl font-bold text-ink mb-1">{metric.value}</p>
                      {metric.change != null ? (
                        <p className="text-xs font-medium text-[#AAFF45]">{metric.change}</p>
                      ) : (
                        <p className="text-xs text-gray-400">Применено в редакторе</p>
                      )}
                    </div>
                  ))}
                </div>

                {/* Charts */}
                <div className="grid grid-cols-2 gap-6">
                  {/* Corrections by type */}
                  <div className="border border-gray-200 rounded-lg p-6">
                    <h3 className="font-semibold text-ink mb-1">Исправления</h3>
                    <p className="text-xs text-gray-500 mb-4">Сохранённые применения из редактора документов</p>
                    {stats.corrections === 0 ? (
                      <div className="flex items-center justify-center h-40 text-sm text-gray-400">
                        Пока нет применённых исправлений
                      </div>
                    ) : (
                      <div className="space-y-3">
                        {correctionRows.map(({ key, n, label }) => (
                          <div key={key}>
                            <div className="flex justify-between text-sm mb-1">
                              <span className="text-gray-700">{label}</span>
                              <span className="font-semibold text-ink">{n}</span>
                            </div>
                            <div className="h-2 rounded-full bg-gray-100 overflow-hidden">
                              <div
                                className="h-full rounded-full bg-[#AAFF45] transition-all"
                                style={{ width: `${Math.min(100, (n / stats.corrections) * 100)}%` }}
                              />
                            </div>
                          </div>
                        ))}
                      </div>
                    )}
                  </div>

                  {/* Document classification */}
                  <div className="border border-gray-200 rounded-lg p-6">
                    <h3 className="font-semibold text-ink mb-1">Классификация документов</h3>
                    <p className="text-xs text-gray-500 mb-4">По полю «классификация» в базе</p>
                    {validDocuments.length === 0 ? (
                      <div className="flex items-center justify-center h-40 text-sm text-gray-400">
                        Нет документов с классификацией
                      </div>
                    ) : (
                      <>
                        <div className="flex items-center justify-center h-40">
                          <div className="relative w-32 h-32">
                            <svg viewBox="0 0 100 100" className="w-full h-full">
                              <circle
                                cx="50"
                                cy="50"
                                r="45"
                                fill="none"
                                stroke="#AAFF45"
                                strokeWidth="8"
                                strokeDasharray={`${(classificationPct / 100) * 283} 283`}
                                transform="rotate(-90 50 50)"
                              />
                              <circle cx="50" cy="50" r="45" fill="none" stroke="#E5E7EB" strokeWidth="8" opacity="0.3" />
                            </svg>
                            <div className="absolute inset-0 flex items-center justify-center">
                              <div className="text-center">
                                <p className="text-2xl font-bold text-ink">{classificationPct}%</p>
                                <p className="text-xs text-gray-500">Действующие</p>
                              </div>
                            </div>
                          </div>
                        </div>
                        <div className="mt-4 space-y-2 text-sm">
                          <div className="flex justify-between">
                            <span className="text-gray-600">Действующие (valid)</span>
                            <span className="font-semibold text-ink">{validCount}</span>
                          </div>
                          <div className="flex justify-between">
                            <span className="text-gray-600">Прочие</span>
                            <span className="font-semibold text-ink">{invalidCount}</span>
                          </div>
                        </div>
                      </>
                    )}
                  </div>
                </div>
              </div>
            ) : activeTab === 'documents' ? (
              <div className="text-gray-400">Статистика документов — в разработке</div>
            ) : (
              <div className="text-gray-400">Статистика шаблонов — в разработке</div>
            )}
          </div>
        </div>
      </main>
    </div>
  )
}
