const BACKEND_URL = process.env.NEXT_PUBLIC_BACKEND_URL || 'http://localhost:8000'

export async function POST(request) {
  try {
    const { document_text } = await request.json()

    if (!document_text || typeof document_text !== 'string') {
      return Response.json({ error: 'document_text is required' }, { status: 400 })
    }

    // Delegate to backend for secure OpenAI processing
    const backendResponse = await fetch(`${BACKEND_URL}/ai/analyze-legal-norms`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ document_text }),
    })

    if (!backendResponse.ok) {
      const error = await backendResponse.text()
      console.error('Backend error:', error)
      return Response.json({ error: 'Backend analysis failed' }, { status: 500 })
    }

    const result = await backendResponse.json()
    return Response.json(result)

  } catch (error) {
    console.error('Document analysis error:', error)
    return Response.json({ error: error.message }, { status: 500 })
  }
}
