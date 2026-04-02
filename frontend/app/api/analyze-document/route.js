import { OpenAI } from 'openai'

const client = new OpenAI({
  apiKey: process.env.OPENAI_API_KEY,
})

export async function POST(request) {
  try {
    const { document_text } = await request.json()

    if (!document_text || typeof document_text !== 'string') {
      return Response.json({ error: 'document_text is required' }, { status: 400 })
    }

    // Truncate to ~4000 chars to stay within token budget
    const truncated = document_text.substring(0, 4000)

    const response = await client.chat.completions.create({
      model: 'gpt-4o-mini',
      messages: [
        {
          role: 'system',
          content: `You are a legal document analyzer specializing in Kazakhstan legislation.
You understand Kazakh legal codes: ГК РК (Civil Code), ТК РК (Labor Code), УК РК (Criminal Code),
УПК РК, ГПК РК (Civil Procedure Code), КоАП РК, НК РК (Tax Code), ЗК РК (Land Code), ЖК РК (Housing Code), СК РК (Family Code).

Your task: Read the provided document text and find ALL references to Kazakhstan legal norms/articles.
For each reference found, provide comprehensive analysis including:
- When the norm was introduced
- All significant amendments with dates
- Whether it was replaced (and by what)
- Whether it was deleted
- Current legal status (valid/outdated/invalid)
- How this norm applies to the given document (applicability)
- Where and in what context it is mentioned in the document (usage_context)

Return ONLY valid JSON, no markdown or explanation.`,
        },
        {
          role: 'user',
          content: `Analyze the following document text and extract all references to Kazakhstan legal norms/articles.
For each norm found, return an object with: norm_text, title, status, applicability, usage_context, introduced, amendments (array), replaced_by, deleted_at, current_status_explanation.

Document text:
---
${truncated}
---

Return as JSON array:
{
  "articles": [
    {
      "norm_text": "ст. 293 ТК РК",
      "title": "Official article name in Russian",
      "status": "valid|outdated|invalid",
      "applicability": "How this norm applies to the document (1-2 sentences in Russian)",
      "usage_context": "Where and how it's mentioned in the document (1-2 sentences in Russian)",
      "introduced": "YYYY-MM-DD or null",
      "amendments": [
        { "date": "YYYY-MM-DD", "description": "What changed" }
      ],
      "replaced_by": "What replaced it or null",
      "deleted_at": "YYYY-MM-DD or null",
      "current_status_explanation": "1-2 sentences explaining current status in Russian"
    }
  ]
}

If no legal norms are found, return {"articles": []}.`,
        },
      ],
      temperature: 0.3,
      max_tokens: 3000,
    })

    const content = response.choices[0].message.content.trim()

    let jsonResponse
    try {
      jsonResponse = JSON.parse(content)
    } catch (e) {
      console.error('Failed to parse OpenAI response:', content)
      return Response.json({ error: 'Invalid JSON response from OpenAI' }, { status: 500 })
    }

    // Validate response structure
    if (!jsonResponse.articles || !Array.isArray(jsonResponse.articles)) {
      return Response.json({ articles: [] })
    }

    return Response.json({ articles: jsonResponse.articles })
  } catch (error) {
    console.error('Document analysis error:', error)
    return Response.json({ error: error.message }, { status: 500 })
  }
}
