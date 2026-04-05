'use client'

import Link from 'next/link'
import { BarChart2, FileText, Sparkles, ArrowRight } from 'lucide-react'
import Sidebar from '@/components/Sidebar'

function LaptopMock() {
  return (
    <div className="w-full max-w-[880px] px-3 sm:px-4">
      <div className="rounded-[1.125rem] bg-gradient-to-b from-slate-200/95 to-slate-300/90 p-[10px] shadow-[0_20px_50px_-15px_rgba(15,23,42,0.18)] ring-1 ring-white/60">
        <div className="flex items-center gap-2 px-2 pb-2 pt-0.5">
          <span className="h-2 w-2 rounded-full bg-[#ff5f57]" />
          <span className="h-2 w-2 rounded-full bg-[#febc2e]" />
          <span className="h-2 w-2 rounded-full bg-[#28c840]" />
          <span className="ml-1 flex-1 truncate text-center text-[10px] font-medium text-slate-500">
            inLaw — договор оказания услуг
          </span>
        </div>

        <div className="aspect-video w-full overflow-hidden rounded-md bg-white shadow-inner ring-1 ring-slate-200/80">
          <div className="flex h-full min-h-0">
            <div className="min-w-0 flex-1 overflow-y-auto border-r border-slate-100 p-3 sm:p-4">
              <p className="mb-1.5 text-[9px] font-semibold uppercase tracking-wider text-slate-400 sm:text-[10px]">
                Предмет договора
              </p>
              <h3 className="mb-2 text-sm font-bold leading-tight text-ink sm:text-[15px]">
                Договор № 14-б
              </h3>
              <p className="text-[10px] leading-relaxed text-slate-700 sm:text-[11px]">
                Исполнитель обязуется оказать услуги консультирования в соответствии с{' '}
                <span className="rounded bg-emerald-100/90 px-0.5 font-medium text-emerald-900">
                  статьёй 8 ТК РК
                </span>
                , а Заказчик оплатить услуги в порядке, установленном разделом 2.
              </p>
              <p className="mt-2 text-[10px] leading-relaxed text-slate-600 sm:text-[11px]">
                Выплата производится два раза в месяц согласно{' '}
                <span className="rounded bg-emerald-100/90 px-0.5 font-medium text-emerald-900">
                  ст. 105 ТК РК
                </span>
                .
              </p>
            </div>
            <div className="w-[36%] min-w-[100px] shrink-0 overflow-y-auto border-l border-slate-100 bg-slate-50/95 p-2 sm:w-[34%] sm:p-3">
              <div className="mb-2 flex flex-wrap gap-1 border-b border-slate-200/80 pb-2">
                <span className="inline-flex items-center gap-0.5 rounded-md bg-[#ADFF5E] px-1.5 py-0.5 text-[8px] font-semibold text-slate-900 sm:text-[9px]">
                  <BarChart2 className="h-2.5 w-2.5 shrink-0 sm:h-3 sm:w-3" />
                  Анализ
                </span>
                <span className="rounded-md px-1 py-0.5 text-[8px] text-slate-400 sm:text-[9px]">Хронология</span>
              </div>
              <p className="mb-1.5 text-[8px] font-semibold uppercase tracking-wide text-slate-500 sm:text-[9px]">
                Релевантные нормы
              </p>
              <div className="space-y-1.5">
                <div className="rounded-lg border border-emerald-200/80 bg-emerald-50/90 p-1.5 sm:p-2">
                  <div className="mb-0.5 flex items-center gap-1">
                    <span className="h-1.5 w-1.5 shrink-0 rounded-full bg-emerald-500" />
                    <span className="line-clamp-2 text-[8px] font-semibold text-slate-900 sm:text-[9px]">
                      Трудовой кодекс РК (ст. 8)
                    </span>
                  </div>
                  <p className="line-clamp-2 text-[7px] leading-tight text-slate-600 sm:text-[8px]">
                    Семантически близкий фрагмент…
                  </p>
                </div>
                <div className="rounded-lg border border-emerald-200/80 bg-emerald-50/90 p-1.5 sm:p-2">
                  <div className="mb-0.5 flex items-center gap-1">
                    <span className="h-1.5 w-1.5 shrink-0 rounded-full bg-emerald-500" />
                    <span className="line-clamp-2 text-[8px] font-semibold text-slate-900 sm:text-[9px]">
                      Трудовой кодекс РК (ст. 105)
                    </span>
                  </div>
                  <p className="text-[7px] text-slate-500 sm:text-[8px]">Релевантность 0.842</p>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
      <div
        aria-hidden
        className="mx-auto mt-1.5 h-1.5 w-[78%] rounded-full bg-gradient-to-b from-slate-300/90 to-slate-400/60"
      />
    </div>
  )
}

export default function Home() {
  return (
    <div className="flex min-h-screen">
      <Sidebar />

      <main className="relative flex min-h-0 flex-1 flex-col overflow-y-auto bg-gradient-to-b from-[#fcfdf9] via-[#f4f7ec] to-[#e8efe3]">
        <div
          className="pointer-events-none absolute inset-0 bg-gradient-to-br from-[#c0f11c]/[0.07] via-transparent to-[#9dc914]/[0.06]"
          aria-hidden
        />
        <div
          className="pointer-events-none absolute inset-0 bg-[radial-gradient(ellipse_100%_60%_at_50%_0%,rgba(255,255,255,0.85),transparent_55%)]"
          aria-hidden
        />

        <section className="relative px-6 pb-10 pt-12 sm:pb-14 sm:pt-16">
          <div className="mx-auto max-w-3xl text-center">
            <p className="mb-3 inline-flex items-center gap-2 rounded-full border border-white/70 bg-white/80 px-3 py-1 text-xs font-medium text-slate-600 shadow-sm backdrop-blur-sm">
              <Sparkles className="h-3.5 w-3.5 text-amber-500" />
              ИИ-анализ по базе adilet.zan.kz
            </p>
            <h1 className="text-balance text-4xl font-bold tracking-tight text-ink sm:text-5xl sm:leading-[1.1]">
              Юридические документы
              <br />
              <span className="text-slate-800">под контролем в один клик</span>
            </h1>
            <p className="mx-auto mt-5 max-w-xl text-pretty text-base leading-relaxed text-slate-600 sm:text-lg">
              Проверка формулировок, поиск релевантных норм и подсказки по актуальному законодательству
              Республики Казахстан — в привычном редакторе.
            </p>
            <div className="mt-8 flex flex-wrap items-center justify-center gap-3">
              <Link
                href="/documents"
                className="inline-flex items-center gap-2 rounded-full bg-[#ADFF5E] px-6 py-3 text-sm font-semibold text-ink shadow-md shadow-lime-900/10 transition hover:bg-[#9FEA3A]"
              >
                <FileText className="h-4 w-4" />
                Открыть документы
                <ArrowRight className="h-4 w-4 opacity-80" />
              </Link>
              <Link
                href="/templates"
                className="inline-flex items-center gap-2 rounded-full border border-slate-200/90 bg-white/90 px-5 py-3 text-sm font-semibold text-slate-800 shadow-sm backdrop-blur-sm transition hover:border-slate-300 hover:bg-white"
              >
                Шаблоны
              </Link>
            </div>
          </div>
        </section>

        <section className="relative flex flex-1 flex-col items-center px-4 pb-16 pt-2 sm:pb-20">
          <p className="mb-6 text-center text-[11px] font-semibold uppercase tracking-[0.18em] text-slate-500">
            Пример интерфейса
          </p>
          <LaptopMock />
          <p className="mt-8 max-w-md text-center text-sm text-slate-600">
            Редактор с подсветкой норм и панелью «Релевантные нормы» по семантике (коллекция{' '}
            <code className="rounded-md bg-white/50 px-1.5 py-0.5 text-xs text-slate-700 ring-1 ring-slate-200/80">
              zan_legal_docs
            </code>
            ).
          </p>
        </section>
      </main>
    </div>
  )
}
