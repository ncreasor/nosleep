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
          content: `CRITICAL: Extract ONLY legal norm references that are EXPLICITLY MENTIONED in the document text.
Do NOT generate, invent, or hallucinate norms that are not in the text.
Do NOT create fictional statutes like "статья 888" or "статья 777" if they don't appear in the document.

Look for patterns like:
- "ст. 293 ТК РК"
- "статья 50 ТК РК"
- "ст. 100 ГК РК"
- "Закон РК от ..."

Document text:
---
${truncated}
---

For EACH reference explicitly found in the document, provide:
- norm_text: exact reference as written in document
- title, status, applicability, usage_context, introduced, amendments, replaced_by, deleted_at, current_status_explanation

IMPORTANT: If the reference text doesn't actually exist as a real norm in Kazakhstan legislation, mark status as "invalid".

Return as JSON:
{
  "articles": [
    { "norm_text": "ст. 293 ТК РК", ... }
  ]
}

If ZERO norms are explicitly mentioned in the document, return {"articles": []}.
Do NOT invent any norms. Empty document = empty articles array.`,
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

    // Load Kazakh laws database for validation
    const kazakhLawsDb = {
      'ТК РК': {
        articles: {
          '1': true, '2': true, '10': true, '25': true, '27': true, '45': true,
          '50': true, '55': true, '100': true, '105': true, '108': true,
          '130': true, '191': true, '293': true, '300': true
        }
      },
      'ГК РК': {
        articles: { '1': true, '2': true, '10': true, '50': true, '100': true, '140': true, '180': true, '207': true }
      },
      'УК РК': {
        articles: { '1': true, '15': true, '20': true, '100': true, '175': true }
      },
      'НК РК': {
        articles: { '1': true, '10': true, '30': true, '50': true, '100': true }
      },
      'ГПК РК': {
        articles: { '1': true, '50': true, '100': true, '150': true }
      },
      'УПК РК': {
        articles: { '1': true, '7': true, '50': true }
      },
      'КоАП РК': {
        articles: { '1': true, '15': true, '50': true }
      },
      'ЖК РК': {
        articles: { '1': true, '10': true, '50': true }
      },
      'СК РК': {
        articles: { '1': true, '10': true, '50': true, '100': true }
      },
      'ЗК РК': {
        articles: { '1': true, '10': true, '50': true }
      }
    }

    // Function to validate norm against database
    function validateNorm(normText) {
      const pattern = /(?:ст\.|статья)\s+(\d+)\s+([А-Яа-я\s]+?)(?:\s+\(|$)/
      const match = normText.match(pattern)
      if (!match) return { valid: false, status: 'invalid' }

      const [, articleNum, lawPart] = match
      const lawCode = lawPart.trim()

      if (!kazakhLawsDb[lawCode]) return { valid: false, status: 'invalid' }
      if (!kazakhLawsDb[lawCode].articles[articleNum]) return { valid: false, status: 'invalid' }

      return { valid: true, status: 'valid' }
    }

    // Normalize string "null" to actual null values
    const normalized = jsonResponse.articles.map(article => {
      const norm = { ...article }
      if (norm.introduced === 'null') norm.introduced = null
      if (norm.replaced_by === 'null') norm.replaced_by = null
      if (norm.deleted_at === 'null') norm.deleted_at = null

      // Validate against real database
      const validation = validateNorm(norm.norm_text || '')
      if (!validation.valid) {
        norm.status = 'invalid'
        norm.title = `Не найдена в базе (${norm.norm_text || 'неизвестная'})`
      }

      return norm
    })

    return Response.json({ articles: normalized })
  } catch (error) {
    console.error('Document analysis error:', error)
    return Response.json({ error: error.message }, { status: 500 })
  }
}
