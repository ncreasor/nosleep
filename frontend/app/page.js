'use client'

import { useState } from 'react'
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, ResponsiveContainer, Cell } from 'recharts'
import { Button } from '@/components/ui/button'
import Sidebar from '@/components/Sidebar'

export default function Home() {
  const [uploadedFile, setUploadedFile] = useState(null)
  const [uploading, setUploading] = useState(false)

  const handleFileUpload = async (e) => {
    const file = e.target.files?.[0]
    if (!file) return

    setUploading(true)
    try {
      const formData = new FormData()
      formData.append('file', file)

      const backendUrl = process.env.NEXT_PUBLIC_BACKEND_URL || 'http://localhost:8000'
      const response = await fetch(`${backendUrl}/documents/upload`, {
        method: 'POST',
        body: formData
      })

      if (response.ok) {
        setUploadedFile(file.name)
      }
    } catch (error) {
      console.error('Upload error:', error)
    } finally {
      setUploading(false)
    }
  }

  return (
    <div className="flex h-screen bg-gray-50">
      <Sidebar />

      {/* Main Content */}
      <main className="flex-1 overflow-hidden min-w-0 py-4 pr-4">
        {/* Rounded Content Container */}
        <div className="rounded-2xl border border-gray-300 bg-white shadow-sm overflow-hidden h-full flex flex-col">
          {/* Hero Section */}
          <section className="flex flex-col items-center justify-center py-12 px-6">
            <h1 className="text-4xl font-bold text-center mb-3 text-ink leading-tight">
              Проверка правовых актов<br />в один клик
            </h1>

            <p className="text-base text-gray-600 text-center max-w-xl mb-6 leading-relaxed">
              ИИ-анализ для выявления противоречий, дублирования и устаревших положений в ваших юридических документах.
            </p>

            <label className="cursor-pointer">
              <input
                type="file"
                onChange={handleFileUpload}
                disabled={uploading}
                className="hidden"
                accept=".pdf,.doc,.docx,.txt"
              />
              <Button
                className="bg-brand hover:bg-brand-hover text-ink font-semibold px-5 py-2 text-sm"
                disabled={uploading}
              >
                {uploading ? 'Загрузка...' : 'Загрузить документ'}
              </Button>
            </label>
          </section>

          {/* Dashboard Section */}
          <section className="flex-1 overflow-y-auto border-t border-gray-200">
            <div className="p-8 w-full">
              {/* Header */}
              <div className="mb-6">
                <h2 className="text-xl font-bold mb-1 text-ink">
                  Добро пожаловать, Юридический отдел
                </h2>
                <p className="text-gray-500 text-sm">
                  Сводка анализа документов на эту неделю.
                </p>
              </div>

              {/* Metrics Grid */}
              <div className="grid grid-cols-2 gap-6 mb-6">
                {/* Documents Analyzed */}
                <div>
                  <p className="text-gray-500 text-xs font-medium mb-1 uppercase tracking-wide">
                    Документов проанализировано
                  </p>
                  <p className="text-3xl font-bold text-ink">24</p>
                  <p className="text-brand-active text-xs font-medium mt-1">↑ 12% от прошлой недели</p>
                </div>

                {/* Issues Found */}
                <div>
                  <p className="text-gray-500 text-xs font-medium mb-1 uppercase tracking-wide">
                    Найдено проблем
                  </p>
                  <p className="text-3xl font-bold text-ink">142</p>
                  <p className="text-red-600 text-xs font-medium mt-1">↑ 8% от прошлой недели</p>
                </div>

                {/* Compliance Rate */}
                <div>
                  <p className="text-gray-500 text-xs font-medium mb-2 uppercase tracking-wide">
                    Уровень соответствия
                  </p>
                  <div className="w-20 h-16 bg-gray-100 rounded-lg flex items-center justify-center text-2xl font-bold text-ink">
                    87%
                  </div>
                </div>

                {/* Status */}
                <div>
                  <p className="text-gray-500 text-xs font-medium mb-2 uppercase tracking-wide">
                    Текущий статус
                  </p>
                  <div className="flex gap-2 items-start">
                    <div className="w-2 h-2 bg-brand-hover rounded-full mt-1.5 flex-shrink-0" />
                    <div>
                      <span className="bg-brand/20 text-brand-active px-2 py-0.5 text-xs font-semibold rounded inline-block mb-1">
                        Готово
                      </span>
                      <p className="text-gray-600 text-xs">Все системы работают</p>
                    </div>
                  </div>
                </div>
              </div>

              {/* Bar Chart */}
              <div className="border-t border-gray-200 pt-6 mt-6">
                <p className="text-gray-700 text-sm font-semibold mb-4">
                  Документы обработаны (последние 6 недель)
                </p>
                <ResponsiveContainer width="100%" height={240}>
                  <BarChart
                    data={[
                      { week: 'Неделя 1', value: 18 },
                      { week: 'Неделя 2', value: 22 },
                      { week: 'Неделя 3', value: 28 },
                      { week: 'Неделя 4', value: 32 },
                      { week: 'Неделя 5', value: 38 },
                      { week: 'Неделя 6', value: 44 }
                    ]}
                    margin={{ top: 20, right: 30, left: 0, bottom: 20 }}
                  >
                    <CartesianGrid strokeDasharray="0" stroke="transparent" vertical={false} />
                    <XAxis
                      dataKey="week"
                      stroke="#999"
                      style={{ fontSize: '0.85rem', fontWeight: '500' }}
                      axisLine={{ stroke: '#e5e7eb' }}
                    />
                    <YAxis hide={true} domain={[0, 50]} />
                    <Bar dataKey="value" fill="#1f2937" radius={[6, 6, 0, 0]}>
                      {[
                        { week: 'Неделя 1', value: 18 },
                        { week: 'Неделя 2', value: 22 },
                        { week: 'Неделя 3', value: 28 },
                        { week: 'Неделя 4', value: 32 },
                        { week: 'Неделя 5', value: 38 },
                        { week: 'Неделя 6', value: 44 }
                      ].map((entry, index) => (
                        <Cell key={`cell-${index}`} fill={index === 5 ? '#facc15' : '#1f2937'} />
                      ))}
                    </Bar>
                  </BarChart>
                </ResponsiveContainer>
              </div>
            </div>
          </section>
        </div>
      </main>

      {uploadedFile && (
        <div className="fixed bottom-8 left-1/2 transform -translate-x-1/2 bg-brand-hover text-white px-6 py-3 rounded-lg shadow-lg">
          {`✓ Документ "${uploadedFile}" успешно загружен!`}
        </div>
      )}
    </div>
  )
}
