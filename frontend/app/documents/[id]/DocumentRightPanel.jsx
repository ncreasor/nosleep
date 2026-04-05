'use client'

import {
  Loader2, Sparkles, AlertCircle, Wrench,
  ShieldCheck, Link2, AlertTriangle, Download, MessageSquare, Send,
  BarChart2, GitBranch, X,
} from 'lucide-react'

import {
  groundingVerdictLabel,
  isGrounded,
  ringColorsForArticle,
  ringPctForArticle,
} from './documentPanelHelpers'

export function DocumentRightPanel({
  activePanel,
  setActivePanel,
  exportSnapshotsJson,
  normsMeta,
  handleAnalyzeClick,
  articlesLoading,
  articles,
  refChecks,
  setSelectedArticle,
  selectedArticle,
  normRemedy,
  solveNormIssue,
  applyNormEdits,
  chronology,
  aiChat,
  aiChatInput,
  setAiChatInput,
  aiChatScrollRef,
  aiChatTextareaRef,
  sendAiChatMessage,
  approveAiChat,
  rejectAiChat,
}) {
    const tabs = [
      { id: 'analysis', label: 'ИИ Анализ', Icon: BarChart2 },
      { id: 'chronology', label: 'Хронология', Icon: GitBranch },
      { id: 'ai_chat', label: 'AI-Chat', Icon: MessageSquare },
    ]

    return (
      <div className="w-80 bg-white border-l border-gray-200 flex flex-col overflow-hidden">
        {/* Tab bar with grid layout */}
        <div className="grid grid-cols-3 gap-2 p-3 border-b border-gray-100 bg-white">
          {tabs.map(tab => (
            <button
              key={tab.id}
              type="button"
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

        <div className="flex items-center justify-end gap-2 px-3 pb-2 border-b border-gray-50">
          <button
            type="button"
            onClick={exportSnapshotsJson}
            className="inline-flex items-center gap-1.5 rounded-lg border border-gray-200 bg-white px-2.5 py-1.5 text-[11px] font-medium text-gray-700 hover:bg-gray-50"
            title="Сохранить анализ и изменения в файл JSON"
          >
            <Download size={14} className="text-gray-500" />
            Скачать JSON
          </button>
        </div>

        {/* Content area: flex column so AI-Chat keeps composer pinned */}
        <div className="flex-1 flex flex-col min-h-0 overflow-hidden p-4">
          {/* Analysis Tab - List of articles */}
          {activePanel === 'analysis' && (
            <div className="flex-1 min-h-0 overflow-y-auto space-y-4">
              <div>
                <h3 className="text-sm font-semibold tracking-tight text-gray-900">Релевантные нормы</h3>
                <p className="mt-1 text-[11px] leading-relaxed text-gray-500">
                  Поиск по <span className="font-medium text-gray-600">zan_legal_docs</span>
                  {normsMeta?.verify_facts !== false
                    ? ' · ИИ сверяет фрагмент документа с до 5 кандидатами из выдачи'
                    : ' · только семантическое сопоставление'}
                </p>
              </div>

              {/* Analysis trigger button */}
              <button
                type="button"
                onClick={handleAnalyzeClick}
                disabled={articlesLoading}
                className="w-full flex items-center justify-center gap-2 py-3 px-4 rounded-xl font-semibold text-sm transition-colors disabled:opacity-60 disabled:cursor-not-allowed bg-[#ADFF5E] text-gray-900 hover:bg-[#9AE84F]"
              >
                {articlesLoading ? (
                  <>
                    <Loader2 size={16} className="animate-spin" />
                    Анализируем...
                  </>
                ) : articles.length > 0 ? (
                  <>
                    <Sparkles size={16} />
                    Повторить анализ
                  </>
                ) : (
                  <>
                    <Sparkles size={16} />
                    Сделать анализ
                  </>
                )}
              </button>

              {/* Reference validation problems */}
              {!articlesLoading && refChecks.length > 0 && (() => {
                const invalid = refChecks.filter(r => !r.valid)
                const fantasy = refChecks.filter(r => r.fantasy)
                const valid = refChecks.filter(r => r.valid)
                if (invalid.length === 0 && fantasy.length === 0) {
                  return (
                    <div className="rounded-xl border border-emerald-200 bg-emerald-50/80 p-3">
                      <div className="flex items-center gap-2 mb-1">
                        <ShieldCheck size={14} className="text-emerald-600" />
                        <span className="text-xs font-semibold text-emerald-900">Все ссылки проверены</span>
                      </div>
                      <p className="text-[11px] text-emerald-800">
                        {valid.length} {valid.length === 1 ? 'ссылка на норму найдена' : 'ссылок на нормы найдено'} в базе данных — все корректны.
                      </p>
                    </div>
                  )
                }
                return (
                  <div className="rounded-xl border border-red-200 bg-red-50/80 p-3 space-y-2.5">
                    <div className="flex items-center gap-2">
                      <AlertCircle size={14} className="text-red-600 shrink-0" />
                      <span className="text-xs font-semibold text-red-900">
                        Проблемы документа: {invalid.length} из {refChecks.length} ссылок не найдены в базе
                      </span>
                    </div>
                    <div className="space-y-1.5 max-h-72 overflow-y-auto">
                      {invalid.map((ref, i) => (
                        <div key={i} className="rounded-lg border border-red-200/80 bg-white p-2.5">
                          <div className="flex items-start gap-2">
                            <X size={12} className="text-red-500 mt-0.5 shrink-0" />
                            <div className="min-w-0 flex-1">
                              <p className="text-[11px] font-semibold text-red-900">{ref.reference}</p>
                              {ref.fantasy && (
                                <span className="inline-block mt-0.5 px-1.5 py-0.5 rounded text-[9px] font-bold uppercase tracking-wide bg-red-100 text-red-700">
                                  Вымышленная норма
                                </span>
                              )}
                              {ref.suspicious && !ref.fantasy && (
                                <span className="inline-block mt-0.5 px-1.5 py-0.5 rounded text-[9px] font-bold uppercase tracking-wide bg-amber-100 text-amber-800">
                                  Подозрительный номер статьи
                                </span>
                              )}
                              <p className="mt-1 text-[10px] text-red-700">
                                {ref.reason || 'Статья не найдена в базе законодательства РК'}
                              </p>
                              {ref.context && (
                                <p className="mt-1 text-[10px] text-gray-500 italic line-clamp-2">
                                  «...{ref.context}...»
                                </p>
                              )}
                            </div>
                          </div>
                        </div>
                      ))}
                    </div>
                    {valid.length > 0 && (
                      <p className="text-[10px] text-gray-500 pt-1 border-t border-red-100">
                        {valid.length} {valid.length === 1 ? 'ссылка корректна' : 'ссылок корректны'} и найдены в базе.
                      </p>
                    )}
                  </div>
                )
              })()}

              {!articlesLoading && articles.length > 0 && (
                <div className="rounded-lg border border-blue-100 bg-blue-50/60 px-3 py-2 text-[10px] leading-relaxed text-blue-800">
                  <span className="font-semibold">Как читать результаты:</span> «Проверено по базе» — норма сверена с текстом из базы законодательства.
                  «Не проверено» — только совпадение по смыслу, может быть неточным. Процент показывает достоверность проверки, а не схожесть.
                </div>
              )}

              {articlesLoading ? (
                <div className="flex items-center justify-center py-10">
                  <Loader2 size={20} className="animate-spin text-gray-300" />
                </div>
              ) : articles.length === 0 ? (
                <p className="rounded-xl border border-dashed border-gray-200 bg-gray-50/80 px-4 py-8 text-center text-xs text-gray-500 leading-relaxed">
                  {normsMeta
                    ? (normsMeta.verify_facts !== false
                      ? 'Подтверждённых соответствий нет: проверка не связала текст с выбранными нормами. Добавьте контекст в документ или проверьте формулировки.'
                      : 'Совпадений не найдено — попробуйте расширить текст документа.')
                    : 'Нажмите «Сделать анализ», чтобы найти релевантные нормы законодательства в документе.'}
                </p>
              ) : (
                <div className="space-y-2.5">
                  {articles.map((article, idx) => {
                    const ringPct = ringPctForArticle(article)
                    const { confColor, ringColor } = ringColorsForArticle(article)
                    const av = article.article_verification
                    const gv = article.grounding?.verdict
                    const gvLabel = groundingVerdictLabel(gv)
                    const sem = typeof article.semantic_similarity_pct === 'number'
                      ? article.semantic_similarity_pct
                      : (typeof article.confidence === 'number' ? article.confidence : null)
                    const align = av?.alignment
                    return (
                      <button
                        type="button"
                        key={article.qdrant_point_id || article.norm_text || idx}
                        onClick={() => {
                          setSelectedArticle(article)
                          setActivePanel('chronology')
                        }}
                        className="group w-full rounded-2xl border border-gray-200/90 bg-white p-3.5 text-left shadow-sm ring-1 ring-black/[0.03] transition hover:border-gray-300 hover:shadow-md"
                      >
                        <div className="flex gap-3">
                          {ringPct != null && (
                            <div className="relative flex h-12 w-12 shrink-0 items-center justify-center">
                              <svg className="h-12 w-12 -rotate-90" viewBox="0 0 36 36">
                                <circle
                                  cx="18"
                                  cy="18"
                                  r="15.5"
                                  fill="none"
                                  className="stroke-gray-100"
                                  strokeWidth="3"
                                />
                                <circle
                                  cx="18"
                                  cy="18"
                                  r="15.5"
                                  fill="none"
                                  className={ringColor}
                                  strokeWidth="3"
                                  strokeDasharray={`${(ringPct / 100) * 97.4} 97.4`}
                                  strokeLinecap="round"
                                />
                              </svg>
                              <span className={`absolute text-[11px] font-bold tabular-nums ${confColor}`}>
                                {ringPct}%
                              </span>
                            </div>
                          )}
                          <div className="min-w-0 flex-1">
                            <div className="flex items-start justify-between gap-2">
                              <p className="text-[13px] font-semibold leading-snug text-gray-900 line-clamp-2">
                                {article.norm_text}
                              </p>
                              <span
                                className={`shrink-0 rounded-full px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide ${
                                  article.status === 'valid'
                                    ? 'bg-emerald-50 text-emerald-800'
                                    : article.status === 'outdated'
                                    ? 'bg-slate-100 text-slate-700'
                                    : 'bg-red-50 text-red-800'
                                }`}
                              >
                                {article.status === 'valid'
                                  ? 'Действует'
                                  : article.status === 'outdated'
                                  ? 'Не действ.'
                                  : 'Нет в базе'}
                              </span>
                            </div>
                            <p className="mt-0.5 text-[10px] font-medium uppercase tracking-wider text-gray-400">
                              {isGrounded(article) ? 'Проверено по базе' : article.grounding ? 'Не подтверждено' : 'Только поиск (не проверено)'}
                            </p>
                            {sem != null && article.grounding && (
                              <p className="mt-0.5 text-[10px] text-gray-500">
                                Схожесть: {sem}%
                              </p>
                            )}
                            {gvLabel && (
                              <div className="mt-1.5">
                                <span
                                  className={`inline-flex rounded-md px-2 py-0.5 text-[10px] font-semibold ring-1 ${
                                    gv === 'applicable'
                                      ? 'bg-emerald-50 text-emerald-900 ring-emerald-200/80'
                                      : gv === 'partially_applicable'
                                      ? 'bg-amber-50 text-amber-900 ring-amber-200/80'
                                      : 'bg-slate-50 text-slate-700 ring-slate-200/80'
                                  }`}
                                >
                                  {gvLabel}
                                </span>
                              </div>
                            )}
                            {av && (
                              <div className="mt-2 flex flex-wrap gap-1.5">
                                {align === 'match' && (
                                  <span className="inline-flex items-center gap-1 rounded-md bg-emerald-50 px-2 py-0.5 text-[10px] font-medium text-emerald-800 ring-1 ring-emerald-200/80">
                                    <Link2 size={10} />
                                    Статьи согласованы
                                  </span>
                                )}
                                {align === 'mismatch' && (
                                  <span className="inline-flex items-center gap-1 rounded-md bg-amber-50 px-2 py-0.5 text-[10px] font-medium text-amber-900 ring-1 ring-amber-200/80">
                                    <AlertTriangle size={10} />
                                    Номера различаются
                                  </span>
                                )}
                                {align === 'unknown' && (
                                  <span className="inline-flex items-center gap-1 rounded-md bg-slate-50 px-2 py-0.5 text-[10px] font-medium text-slate-600 ring-1 ring-slate-200/80">
                                    Статьи: н/д
                                  </span>
                                )}
                                {av.registry?.valid === true && (
                                  <span className="inline-flex items-center gap-1 rounded-md bg-sky-50 px-2 py-0.5 text-[10px] font-medium text-sky-900 ring-1 ring-sky-200/80">
                                    <ShieldCheck size={10} />
                                    Справочник ОК
                                  </span>
                                )}
                                {av.registry?.valid === false && (
                                  <span className="inline-flex items-center gap-1 rounded-md bg-red-50 px-2 py-0.5 text-[10px] font-medium text-red-800 ring-1 ring-red-200/80">
                                    Справочник: нет статьи
                                  </span>
                                )}
                              </div>
                            )}
                            {article.law_chunk_preview && (
                              <p className="mt-2 line-clamp-2 text-[11px] leading-relaxed text-gray-600">
                                {article.law_chunk_preview}
                              </p>
                            )}
                          </div>
                        </div>
                      </button>
                    )
                  })}
                </div>
              )}
            </div>
          )}

          {/* Chronology Tab */}
          {activePanel === 'chronology' && (
            <div className="flex-1 min-h-0 overflow-y-auto space-y-4">
              {!selectedArticle ? (
                <div className="flex flex-col items-center justify-center py-12 text-center">
                  <div className="w-10 h-10 rounded-full bg-gray-100 flex items-center justify-center mb-3">
                    <GitBranch size={18} className="text-gray-400" />
                  </div>
                  <p className="text-xs text-gray-500 font-medium">Кликните на норму</p>
                  <p className="text-xs text-gray-400 mt-1">в списке или в документе</p>
                </div>
              ) : (
                <>
                  {/* Selected article header */}
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
                    {(selectedArticle.status === 'outdated' || selectedArticle.status === 'invalid') && (
                      <button
                        type="button"
                        onClick={solveNormIssue}
                        disabled={normRemedy.loading}
                        className="ml-auto flex items-center gap-1.5 text-xs font-semibold px-3 py-1.5 rounded-lg bg-[#ADFF5E] text-gray-900 hover:bg-[#9AE84F] disabled:opacity-60 disabled:cursor-not-allowed transition-colors"
                      >
                        {normRemedy.loading ? (
                          <Loader2 size={14} className="animate-spin" />
                        ) : (
                          <Wrench size={14} />
                        )}
                        Решить проблему
                      </button>
                    )}
                  </div>

                  {/* Norm remedy UI */}
                  {(selectedArticle.status === 'outdated' || selectedArticle.status === 'invalid') &&
                    (normRemedy.summary || normRemedy.error || normRemedy.edits?.length > 0 || normRemedy.applied) && (
                    <div className="space-y-3">
                      {normRemedy.error && (
                        <div className="p-3 rounded-xl border border-red-200 bg-red-50 text-xs text-red-900">{normRemedy.error}</div>
                      )}
                      {normRemedy.summary && !normRemedy.error && (
                        <p className="text-xs text-gray-700 leading-relaxed">{normRemedy.summary}</p>
                      )}
                      {normRemedy.warnings?.length > 0 && (
                        <p className="text-[11px] text-amber-700">{normRemedy.warnings.join(' · ')}</p>
                      )}
                      {normRemedy.edits?.length > 0 && (
                        <>
                          <p className="text-[11px] font-semibold text-gray-600 uppercase">Правки в тексте</p>
                          <div className="space-y-2 max-h-64 overflow-y-auto">
                            {normRemedy.edits.map((ed, i) => (
                              <div key={i} className="p-2.5 rounded-lg border border-gray-200 bg-gray-50 text-[11px]">
                                {ed.reason && <p className="text-gray-600 mb-1.5">{ed.reason}</p>}
                                <div className="space-y-1">
                                  <div>
                                    <span className="text-gray-400">Было: </span>
                                    <span className="text-red-800 line-through break-words">{ed.find}</span>
                                  </div>
                                  <div>
                                    <span className="text-gray-400">Станет: </span>
                                    <span className="text-green-800 font-medium break-words">{ed.replace || '(удалить)'}</span>
                                  </div>
                                </div>
                              </div>
                            ))}
                          </div>
                          {normRemedy.applyError && (
                            <p className="text-xs text-red-600">{normRemedy.applyError}</p>
                          )}
                          <button
                            type="button"
                            onClick={applyNormEdits}
                            className="w-full flex items-center justify-center gap-2 text-xs font-semibold py-2.5 rounded-xl bg-gray-900 text-white hover:bg-gray-800 transition-colors"
                          >
                            <Wrench size={14} />
                            Применить в документе
                          </button>
                        </>
                      )}
                      {normRemedy.applied && (
                        <p className="text-xs font-medium text-green-700">Изменения внесены в текст редактора.</p>
                      )}
                      {!normRemedy.loading &&
                        !normRemedy.error &&
                        normRemedy.summary &&
                        (!normRemedy.edits || normRemedy.edits.length === 0) &&
                        !normRemedy.applied && (
                          <p className="text-xs text-gray-500">Автоматических замен не требуется — проверьте формулировки вручную.</p>
                        )}
                    </div>
                  )}

                  {/* Article title */}
                  <div>
                    <p className="text-sm font-semibold text-gray-900">{selectedArticle.title || selectedArticle.norm_text}</p>
                    {selectedArticle.title && (
                      <p className="text-xs text-gray-400 mt-0.5">{selectedArticle.norm_text}</p>
                    )}
                  </div>

                  {/* Current status explanation */}
                  {selectedArticle.current_status_explanation && (
                    <div className="p-3 bg-gray-50 rounded-xl border border-gray-200">
                      <p className="text-xs text-gray-700 leading-relaxed">
                        {selectedArticle.current_status_explanation}
                      </p>
                    </div>
                  )}

                  {/* Law URL */}
                  {selectedArticle.law_url && (
                    <a
                      href={selectedArticle.law_url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="flex items-center gap-1.5 text-[11px] font-medium text-blue-700 hover:text-blue-900 transition-colors"
                    >
                      <Link2 size={12} />
                      Открыть на adilet.zan.kz
                    </a>
                  )}

                  {/* Chronology timeline — from Qdrant */}
                  <div className="border-t border-gray-100 pt-4">
                    <p className="text-[10px] font-semibold text-gray-500 mb-3 uppercase tracking-wide">
                      Хронология по базе законодательства
                    </p>

                    {chronology.loading ? (
                      <div className="flex items-center justify-center py-8">
                        <Loader2 size={16} className="animate-spin text-gray-300" />
                      </div>
                    ) : chronology.error ? (
                      <p className="text-xs text-red-500 text-center py-4">{chronology.error}</p>
                    ) : chronology.timeline.length === 0 && chronology.related.length === 0 ? (
                      <p className="text-xs text-gray-400 text-center py-6">
                        Связанные нормы не найдены в базе
                      </p>
                    ) : (
                      <div className="space-y-5">
                        {/* Main timeline */}
                        {chronology.timeline.length > 0 && (
                          <div className="relative pl-7">
                            <div className="absolute left-2.5 top-1 bottom-1 w-0.5 bg-[#ADFF5E]" />
                            <div className="space-y-3">
                              {chronology.timeline.map((entry, idx) => (
                                <div key={entry.point_id || idx} className="relative">
                                  <div className="absolute -left-[18px] top-2.5 w-2.5 h-2.5 rounded-full border-2 border-[#ADFF5E] bg-white" />
                                  <div className="rounded-xl border border-gray-200 bg-white p-3 shadow-sm">
                                    <div className="flex items-start justify-between gap-2 mb-1">
                                      {entry.date && (
                                        <span className="text-[10px] font-bold tabular-nums text-gray-500 shrink-0">
                                          {entry.date}
                                        </span>
                                      )}
                                      <span className={`shrink-0 rounded-full px-1.5 py-0.5 text-[9px] font-semibold uppercase ${
                                        entry.is_active
                                          ? 'bg-emerald-50 text-emerald-700'
                                          : 'bg-slate-100 text-slate-600'
                                      }`}>
                                        {entry.is_active ? 'Действует' : 'Утратил силу'}
                                      </span>
                                    </div>
                                    <p className="text-[11px] font-semibold text-gray-900 leading-snug">
                                      {entry.title}
                                      {entry.number && <span className="font-normal text-gray-500"> ({entry.number})</span>}
                                    </p>
                                    {entry.text_preview && (
                                      <p className="mt-1.5 text-[10px] text-gray-500 leading-relaxed line-clamp-3">
                                        {entry.text_preview}
                                      </p>
                                    )}
                                    {entry.url && (
                                      <a
                                        href={entry.url}
                                        target="_blank"
                                        rel="noopener noreferrer"
                                        className="mt-1.5 inline-flex items-center gap-1 text-[10px] text-blue-600 hover:text-blue-800"
                                      >
                                        <Link2 size={9} /> adilet.zan.kz
                                      </a>
                                    )}
                                  </div>
                                </div>
                              ))}
                            </div>
                          </div>
                        )}

                        {/* Related laws */}
                        {chronology.related.length > 0 && (
                          <div>
                            <p className="text-[10px] font-semibold text-gray-500 mb-2 uppercase tracking-wide">
                              Связанные нормы
                            </p>
                            <div className="space-y-2">
                              {chronology.related.map((entry, idx) => (
                                <div key={entry.point_id || idx} className="rounded-xl border border-gray-200 bg-gray-50/50 p-2.5">
                                  <div className="flex items-start justify-between gap-2 mb-0.5">
                                    {entry.date && (
                                      <span className="text-[10px] font-bold tabular-nums text-gray-400 shrink-0">
                                        {entry.date}
                                      </span>
                                    )}
                                    <span className={`shrink-0 rounded-full px-1.5 py-0.5 text-[9px] font-semibold uppercase ${
                                      entry.is_active
                                        ? 'bg-emerald-50 text-emerald-700'
                                        : 'bg-slate-100 text-slate-600'
                                    }`}>
                                      {entry.is_active ? 'Действует' : 'Утратил силу'}
                                    </span>
                                  </div>
                                  <p className="text-[11px] font-medium text-gray-800 leading-snug">
                                    {entry.title}
                                    {entry.number && <span className="font-normal text-gray-500"> ({entry.number})</span>}
                                  </p>
                                  {entry.text_preview && (
                                    <p className="mt-1 text-[10px] text-gray-500 leading-relaxed line-clamp-2">
                                      {entry.text_preview}
                                    </p>
                                  )}
                                  {entry.url && (
                                    <a
                                      href={entry.url}
                                      target="_blank"
                                      rel="noopener noreferrer"
                                      className="mt-1 inline-flex items-center gap-1 text-[10px] text-blue-600 hover:text-blue-800"
                                    >
                                      <Link2 size={9} /> adilet.zan.kz
                                    </a>
                                  )}
                                </div>
                              ))}
                            </div>
                          </div>
                        )}
                      </div>
                    )}
                  </div>
                </>
              )}
            </div>
          )}

          {activePanel === 'ai_chat' && (
            <div className="flex flex-1 flex-col min-h-0 gap-3">
              <div className="shrink-0">
                <h3 className="text-sm font-semibold text-gray-900">AI-Chat</h3>
                <p className="mt-1 text-[11px] text-gray-500 leading-relaxed">
                  Claude Haiku: ответы и точечные замены. В документ — только после подтверждения.
                </p>
              </div>
              {aiChat.error && (
                <p className="text-xs text-red-600 shrink-0">{aiChat.error}</p>
              )}
              <div
                ref={aiChatScrollRef}
                className="min-h-0 flex-1 overflow-y-auto overscroll-contain space-y-3 pr-0.5"
              >
                {aiChat.loading && aiChat.messages.length === 0 ? (
                  <div className="flex justify-center py-12">
                    <Loader2 size={20} className="animate-spin text-gray-300" />
                  </div>
                ) : (
                  aiChat.messages.map((m) => (
                    <div
                      key={m.id}
                      className={`rounded-xl border px-3 py-2.5 text-xs ${
                        m.role === 'user'
                          ? 'ml-2 border-[#ADFF5E] bg-[#f4ffe8]'
                          : 'mr-0 border-gray-200 bg-gray-50'
                      }`}
                    >
                      {m.role === 'user' && (
                        <p className="text-gray-800 whitespace-pre-wrap text-[13px] leading-relaxed">{m.content}</p>
                      )}
                      {m.role === 'assistant' && m.assistant && (
                        <>
                          <p className="text-gray-800 whitespace-pre-wrap leading-relaxed text-[13px]">{m.assistant.reply}</p>
                          {Array.isArray(m.assistant.proposed_edits) && m.assistant.proposed_edits.length > 0 && (
                            <div className="mt-2 space-y-2 border-t border-gray-200 pt-2">
                              {m.assistant.proposed_edits.map((ed, i) => (
                                <div key={i} className="rounded-lg bg-white border border-gray-100 p-2">
                                  {ed.reason && <p className="text-[10px] text-gray-500 mb-1">{ed.reason}</p>}
                                  <p className="text-[10px] text-red-800 line-through break-words">{ed.find}</p>
                                  <p className="text-[10px] text-emerald-800 font-medium break-words mt-0.5">{ed.replace}</p>
                                </div>
                              ))}
                              {m.assistant.status === 'pending' && (
                                <div className="flex gap-2 mt-2">
                                  <button
                                    type="button"
                                    onClick={() => approveAiChat(m.id)}
                                    className="flex-1 py-2 rounded-lg bg-gray-900 text-white text-[11px] font-semibold hover:bg-gray-800"
                                  >
                                    Принять в документ
                                  </button>
                                  <button
                                    type="button"
                                    onClick={() => rejectAiChat(m.id)}
                                    className="flex-1 py-2 rounded-lg border border-gray-300 text-gray-700 text-[11px] font-semibold hover:bg-gray-50"
                                  >
                                    Отклонить
                                  </button>
                                </div>
                              )}
                              {m.assistant.status === 'applied' && (
                                <p className="text-[10px] font-medium text-emerald-700 mt-2">Внесено в документ</p>
                              )}
                              {m.assistant.status === 'rejected' && (
                                <p className="text-[10px] font-medium text-gray-500 mt-2">Отклонено</p>
                              )}
                            </div>
                          )}
                          {m.assistant.status === 'none' && !(m.assistant.proposed_edits?.length) && (
                            <p className="text-[10px] text-gray-400 mt-1">Без автоматических замен</p>
                          )}
                        </>
                      )}
                      {m.role === 'assistant' && !m.assistant && (
                        <p className="text-gray-600 whitespace-pre-wrap text-[13px]">{m.content}</p>
                      )}
                    </div>
                  ))
                )}
              </div>
              <div className="shrink-0 pt-1 border-t border-gray-100 bg-white">
                <div className="rounded-2xl border border-gray-200 bg-gray-50/90 shadow-sm p-2 focus-within:border-gray-300 focus-within:ring-2 focus-within:ring-[#ADFF5E]/60 focus-within:ring-offset-0">
                  <div className="flex gap-2 items-end">
                    <textarea
                      ref={aiChatTextareaRef}
                      value={aiChatInput}
                      onChange={(e) => setAiChatInput(e.target.value)}
                      onKeyDown={(e) => {
                        if (e.key === 'Enter' && !e.shiftKey) {
                          e.preventDefault()
                          sendAiChatMessage()
                        }
                      }}
                      placeholder="Сообщение для ИИ…"
                      rows={4}
                      className="flex-1 min-h-[5.5rem] max-h-48 resize-y rounded-xl border-0 bg-transparent px-2.5 py-2.5 text-sm text-gray-900 placeholder:text-gray-400 focus:outline-none leading-relaxed"
                    />
                    <button
                      type="button"
                      disabled={aiChat.sending || !aiChatInput.trim()}
                      onClick={sendAiChatMessage}
                      title="Отправить"
                      className="mb-0.5 flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-gray-900 text-white transition hover:bg-gray-800 disabled:cursor-not-allowed disabled:opacity-40"
                    >
                      {aiChat.sending ? <Loader2 size={18} className="animate-spin" /> : <Send size={18} strokeWidth={2} />}
                    </button>
                  </div>
                </div>
                <p className="mt-2 text-[10px] text-gray-400 px-0.5">
                  Enter — отправить · Shift+Enter — новая строка
                </p>
              </div>
            </div>
          )}
        </div>
      </div>
    )
}
