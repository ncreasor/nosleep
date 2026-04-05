'use client'

import { useEffect, useState, useMemo } from 'react'
import { useRouter } from 'next/navigation'

const BACKEND = process.env.NEXT_PUBLIC_BACKEND_URL || 'http://localhost:8000'

export function useAuth({ redirect = true } = {}) {
  const router = useRouter()
  const [user, setUser] = useState(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    const token = localStorage.getItem('token')
    if (!token) {
      setLoading(false)
      if (redirect) router.replace('/login')
      return
    }
    fetch(`${BACKEND}/auth/me`, {
      headers: { Authorization: `Bearer ${token}` },
    })
      .then(res => {
        if (res.ok) return res.json()
        localStorage.removeItem('token')
        if (redirect) router.replace('/login')
        return null
      })
      .then(data => { if (data) setUser(data) })
      .finally(() => setLoading(false))
  }, [])

  const logout = () => {
    localStorage.removeItem('token')
    router.push('/login')
  }

  const token = typeof window !== 'undefined' ? localStorage.getItem('token') : null
  const authHeaders = useMemo(
    () => (token ? { Authorization: `Bearer ${token}` } : {}),
    [token]
  )

  return { user, loading, logout, authHeaders }
}
