const BACKEND_URL = process.env.NEXT_PUBLIC_BACKEND_URL || 'http://localhost:8000'

export async function POST(request) {
  try {
    const { document_text, verify_facts } = await request.json()

    if (!document_text || typeof document_text !== 'string') {
      return Response.json({ error: 'document_text is required' }, { status: 400 })
    }

    const body = { document_text }
    if (typeof verify_facts === 'boolean') body.verify_facts = verify_facts

    const backendResponse = await fetch(`${BACKEND_URL}/ai/analyze-legal-norms`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
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
