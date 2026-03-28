'use client'

import { useState, useEffect } from 'react'
import { useRouter } from 'next/navigation'
import { X } from 'lucide-react'

const BACKEND = process.env.NEXT_PUBLIC_BACKEND_URL || 'http://localhost:8000'

function TosModal({ onClose }) {
  return (
    <div className="fixed inset-0 bg-black bg-opacity-40 flex items-center justify-center z-50 p-4">
      <div className="bg-white rounded-2xl border border-gray-200 shadow-xl w-full max-w-lg max-h-[80vh] flex flex-col">
        <div className="flex items-center justify-between px-6 py-4 border-b border-gray-100">
          <h2 className="font-bold text-ink text-base">Условия использования</h2>
          <button onClick={onClose} className="text-gray-400 hover:text-gray-600 transition-colors">
            <X size={18} />
          </button>
        </div>
        <div className="overflow-y-auto px-6 py-5 text-sm text-gray-600 flex flex-col gap-4">
          <p className="text-xs text-gray-400">Последнее обновление: 28 марта 2026 г.</p>

          <section>
            <h3 className="font-semibold text-gray-800 mb-1">1. Общие положения</h3>
            <p>Используя платформу Company («Платформа»), вы соглашаетесь соблюдать настоящие Условия использования. Платформа предназначена для ИИ-анализа юридических документов и предоставляется исключительно в информационных целях.</p>
          </section>

          <section>
            <h3 className="font-semibold text-gray-800 mb-1">2. Учётная запись</h3>
            <p>Вы обязаны предоставить достоверную контактную информацию при регистрации. Вы несёте ответственность за сохранность своих учётных данных и все действия, совершённые под вашей учётной записью.</p>
          </section>

          <section>
            <h3 className="font-semibold text-gray-800 mb-1">3. Загружаемые документы</h3>
            <p>Загружая документы на Платформу, вы подтверждаете, что имеете право на их обработку. Мы не передаём ваши документы третьим лицам и используем их исключительно для предоставления услуг анализа.</p>
          </section>

          <section>
            <h3 className="font-semibold text-gray-800 mb-1">4. Ограничения</h3>
            <p>Запрещается использовать Платформу для загрузки материалов, нарушающих законодательство, права третьих лиц или содержащих вредоносный код. Мы оставляем за собой право приостановить доступ в случае нарушений.</p>
          </section>

          <section>
            <h3 className="font-semibold text-gray-800 mb-1">5. Отказ от гарантий</h3>
            <p>Результаты ИИ-анализа носят информационный характер и не являются юридической консультацией. Платформа предоставляется «как есть» без каких-либо гарантий точности или полноты анализа.</p>
          </section>

          <section>
            <h3 className="font-semibold text-gray-800 mb-1">6. Изменения условий</h3>
            <p>Мы можем изменять настоящие Условия. Продолжая использовать Платформу после уведомления об изменениях, вы соглашаетесь с новой редакцией.</p>
          </section>

          <section>
            <h3 className="font-semibold text-gray-800 mb-1">7. Связь</h3>
            <p>По всем вопросам обращайтесь: <span className="text-brand-active">support@company.kz</span></p>
          </section>
        </div>
        <div className="px-6 py-4 border-t border-gray-100">
          <button
            onClick={onClose}
            className="w-full bg-brand hover:bg-brand-hover transition-colors text-ink font-semibold py-2.5 rounded-full text-sm"
          >
            Понятно
          </button>
        </div>
      </div>
    </div>
  )
}

export default function LoginPage() {
  const router = useRouter()
  const [mode, setMode] = useState('login')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [termsAgreed, setTermsAgreed] = useState(false)
  const [showTos, setShowTos] = useState(false)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)

  useEffect(() => {
    if (localStorage.getItem('token')) router.replace('/documents')
  }, [])

  const doLogin = async (email, password) => {
    const res = await fetch(`${BACKEND}/auth/token`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
      body: new URLSearchParams({ username: email, password }),
    })
    if (res.ok) {
      const { access_token } = await res.json()
      localStorage.setItem('token', access_token)
      router.push('/documents')
      return true
    }
    const err = await res.json().catch(() => ({}))
    throw new Error(err.detail || `Ошибка ${res.status}`)
  }

  const handleSubmit = async (e) => {
    e.preventDefault()
    setError(null)
    setLoading(true)
    try {
      if (mode === 'login') {
        await doLogin(email, password)
      } else {
        const res = await fetch(`${BACKEND}/auth/register`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ email, password, terms_agreed: termsAgreed }),
        })
        if (res.ok) {
          await doLogin(email, password)
        } else {
          const err = await res.json().catch(() => ({}))
          throw new Error(err.detail || `Ошибка ${res.status}`)
        }
      }
    } catch (e) {
      setError(e.message)
    } finally {
      setLoading(false)
    }
  }

  const switchMode = (m) => {
    setMode(m)
    setError(null)
    setTermsAgreed(false)
  }

  return (
    <>
      {showTos && <TosModal onClose={() => setShowTos(false)} />}

      <div className="flex h-screen bg-gray-50 items-center justify-center">
        <div className="bg-white rounded-2xl border border-gray-200 shadow-sm w-full max-w-sm p-8">
          {/* Logo */}
          <div className="flex items-center gap-3 mb-8">
            <img src="/inlawlogo.svg" alt="inLaw" className="w-10 h-10 rounded-xl" />
            <span className="font-semibold text-gray-800">inLaw</span>
          </div>

          <h1 className="text-xl font-bold text-ink mb-1">
            {mode === 'login' ? 'Вход в аккаунт' : 'Регистрация'}
          </h1>
          <p className="text-sm text-gray-500 mb-6">
            {mode === 'login' ? 'Введите email и пароль для входа' : 'Создайте новый аккаунт'}
          </p>

          <form onSubmit={handleSubmit} className="flex flex-col gap-4">
            <div className="flex flex-col gap-1">
              <label className="text-xs font-medium text-gray-600">Email</label>
              <input
                type="email"
                required
                value={email}
                onChange={e => setEmail(e.target.value)}
                placeholder="you@example.com"
                className="border border-gray-200 rounded-xl px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-brand focus:border-transparent"
              />
            </div>

            <div className="flex flex-col gap-1">
              <label className="text-xs font-medium text-gray-600">Пароль</label>
              <input
                type="password"
                required
                value={password}
                onChange={e => setPassword(e.target.value)}
                placeholder="••••••••"
                className="border border-gray-200 rounded-xl px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-brand focus:border-transparent"
              />
            </div>

            {mode === 'register' && (
              <label className="flex items-start gap-2.5 cursor-pointer">
                <input
                  type="checkbox"
                  required
                  checked={termsAgreed}
                  onChange={e => setTermsAgreed(e.target.checked)}
                  className="mt-0.5 accent-brand-hover flex-shrink-0"
                />
                <span className="text-xs text-gray-500 leading-relaxed">
                  Я прочитал(а) и соглашаюсь с{' '}
                  <button
                    type="button"
                    onClick={() => setShowTos(true)}
                    className="text-brand-active font-medium hover:underline"
                  >
                    Условиями использования
                  </button>
                </span>
              </label>
            )}

            {error && (
              <p className="text-xs text-red-600 bg-red-50 px-3 py-2 rounded-lg">{error}</p>
            )}

            <button
              type="submit"
              disabled={loading || (mode === 'register' && !termsAgreed)}
              className="bg-brand hover:bg-brand-hover active:bg-brand-active transition-colors text-ink font-semibold py-2.5 rounded-full text-sm disabled:opacity-60 mt-1"
            >
              {loading ? '...' : mode === 'login' ? 'Войти' : 'Зарегистрироваться'}
            </button>
          </form>

          <p className="text-xs text-gray-500 text-center mt-5">
            {mode === 'login' ? 'Нет аккаунта?' : 'Уже есть аккаунт?'}{' '}
            <button
              onClick={() => switchMode(mode === 'login' ? 'register' : 'login')}
              className="text-brand-active font-medium hover:underline"
            >
              {mode === 'login' ? 'Зарегистрироваться' : 'Войти'}
            </button>
          </p>
        </div>
      </div>
    </>
  )
}
