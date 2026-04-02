'use client'

import { useState, useEffect } from 'react'
import { useRouter } from 'next/navigation'
import Sidebar from '@/components/Sidebar'
import { useAuth } from '@/components/useAuth'

const BACKEND = process.env.NEXT_PUBLIC_BACKEND_URL || 'http://localhost:8000'

export default function StatisticsPage() {
  const { loading: authLoading, authHeaders } = useAuth()
  const router = useRouter()

  const [activeTab, setActiveTab] = useState('overview')
  const [stats, setStats] = useState({
    documents: 0,
    templates: 0,
    corrections: 0,
    exports: 0
  })
  const [documents, setDocuments] = useState([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    if (authLoading) return
    fetchStats()
  }, [authLoading])

  const fetchStats = async () => {
    try {
      const docsRes = await fetch(`${BACKEND}/documents`, { headers: authHeaders })
      const templatesRes = await fetch(`${BACKEND}/templates`, { headers: authHeaders })

      const docs = docsRes.ok ? await docsRes.json() : []
      const templates = templatesRes.ok ? await templatesRes.json() : []

      setDocuments(docs)
      setStats({
        documents: docs.length,
        templates: templates.length,
        corrections: 0,
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
                    { label: 'Поправки', value: stats.corrections, change: '+12%' },
                    { label: 'Экспорты', value: stats.exports, change: '+12%' }
                  ].map((metric, i) => (
                    <div key={i} className="border border-gray-200 rounded-lg p-4">
                      <p className="text-xs font-medium text-gray-500 mb-1 uppercase tracking-wide">{metric.label}</p>
                      <p className="text-3xl font-bold text-ink mb-1">{metric.value}</p>
                      <p className="text-xs font-medium text-[#AAFF45]">{metric.change}</p>
                    </div>
                  ))}
                </div>

                {/* Charts */}
                <div className="grid grid-cols-2 gap-6">
                  {/* Mismatch Chart */}
                  <div className="border border-gray-200 rounded-lg p-6">
                    <h3 className="font-semibold text-ink mb-4">Несоответствия</h3>
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
                            strokeDasharray={`${(validCount / validDocuments.length || 0) * 283} 283`}
                          />
                          <circle cx="50" cy="50" r="45" fill="none" stroke="#E5E7EB" strokeWidth="8" opacity="0.3" />
                        </svg>
                        <div className="absolute inset-0 flex items-center justify-center">
                          <div className="text-center">
                            <p className="text-2xl font-bold text-ink">{Math.round((validCount / validDocuments.length || 0) * 100)}%</p>
                            <p className="text-xs text-gray-500">Исправленные</p>
                          </div>
                        </div>
                      </div>
                    </div>
                    <div className="mt-4 space-y-2 text-sm">
                      <div className="flex justify-between">
                        <span className="text-gray-600">Исправленные</span>
                        <span className="font-semibold text-ink">{validCount}</span>
                      </div>
                      <div className="flex justify-between">
                        <span className="text-gray-600">Неисправленные</span>
                        <span className="font-semibold text-ink">{invalidCount}</span>
                      </div>
                    </div>
                  </div>

                  {/* Account Types */}
                  <div className="border border-gray-200 rounded-lg p-6">
                    <h3 className="font-semibold text-ink mb-4">Типы аккаунтов</h3>
                    <div className="flex items-center justify-center h-40">
                      <div className="relative w-32 h-32">
                        <svg viewBox="0 0 100 100" className="w-full h-full">
                          {/* Pie segments */}
                          <circle cx="50" cy="50" r="40" fill="#AAFF45" />
                          <path d="M 50 50 L 50 10 A 40 40 0 0 1 82.28 17.72 Z" fill="#A8A9AD" opacity="0.5" />
                          <circle cx="50" cy="50" r="20" fill="white" />
                        </svg>
                      </div>
                    </div>
                    <div className="mt-4 space-y-2 text-sm">
                      <div className="flex items-center gap-2">
                        <div className="w-2 h-2 rounded-full bg-[#AAFF45]"></div>
                        <span className="text-gray-600">Very Active</span>
                      </div>
                      <div className="flex items-center gap-2">
                        <div className="w-2 h-2 rounded-full bg-gray-400"></div>
                        <span className="text-gray-600">Inactive</span>
                      </div>
                    </div>
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
