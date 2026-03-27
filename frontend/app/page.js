'use client'

import { useEffect, useState } from 'react'

export default function Home() {
  const [health, setHealth] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  useEffect(() => {
    const checkHealth = async () => {
      try {
        const response = await fetch('http://localhost:8000/health')
        const data = await response.json()
        setHealth(data)
      } catch (err) {
        setError(err.message)
      } finally {
        setLoading(false)
      }
    }

    checkHealth()
  }, [])

  return (
    <main style={{ padding: '2rem', fontFamily: 'system-ui, sans-serif' }}>
      <h1>Welcome to Frontend</h1>
      <section style={{ marginTop: '2rem' }}>
        <h2>Backend Health Status</h2>
        {loading && <p>Loading...</p>}
        {error && <p style={{ color: 'red' }}>Error: {error}</p>}
        {health && (
          <div style={{ padding: '1rem', backgroundColor: '#f0f0f0', borderRadius: '4px' }}>
            <p>Status: <strong>{health.status}</strong></p>
          </div>
        )}
      </section>
    </main>
  )
}
