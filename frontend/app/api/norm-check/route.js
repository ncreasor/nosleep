const BACKEND_URL = process.env.NEXT_PUBLIC_BACKEND_URL || 'http://localhost:8000'

export async function POST(request) {
  try {
    const { norms } = await request.json()

    if (!Array.isArray(norms) || norms.length === 0) {
      return Response.json({ results: {} })
    }

    // Delegate to backend for secure OpenAI processing
    const backendResponse = await fetch(`${BACKEND_URL}/ai/check-norms`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ norms }),
    })

    if (!backendResponse.ok) {
      const error = await backendResponse.text()
      console.error('Backend error:', error)
      return Response.json({ error: 'Backend check failed' }, { status: 500 })
    }

    const result = await backendResponse.json()
    return Response.json(result)

  } catch (error) {
    console.error('Norm check error:', error)
    return Response.json({ error: error.message }, { status: 500 })
  }
}
