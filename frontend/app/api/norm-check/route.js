import { OpenAI } from 'openai'

const client = new OpenAI({
  apiKey: process.env.OPENAI_API_KEY,
})

export async function POST(request) {
  try {
    const { norms } = await request.json()

    if (!Array.isArray(norms) || norms.length === 0) {
      return Response.json({ results: {} })
    }

    const normsText = norms.map((n, i) => `${i + 1}. "${n}"`).join('\n')

    const response = await client.chat.completions.create({
      model: 'gpt-4o-mini',
      messages: [
        {
          role: 'system',
          content: `You are a legal reference system specializing in the legislation of the Republic of Kazakhstan (RK/РК).
You have knowledge of Kazakh legal codes: ГК РК (Civil Code), ТК РК (Labor Code), УК РК (Criminal Code),
УПК РК, ГПК РК (Civil Procedure Code), КоАП РК, НК РК (Tax Code), ЗК РК (Land Code), ЖК РК (Housing Code), СК РК (Family Code).

For each legal norm reference provided, return a JSON object with:
- "status": one of "valid" (norm exists and is in force), "outdated" (norm exists but has been superseded or amended, or is from an old version), "invalid" (norm does not exist)
- "title": the official name/title of the article or law, null if unknown
- "introduced": ISO date string (YYYY-MM-DD) when the norm was first introduced, null if unknown
- "amendments": array of { "date": "YYYY-MM-DD", "description": "brief description in Russian" }, max 5, empty if none
- "current_status_explanation": 1-2 sentences in Russian explaining the current status
- "status_since": ISO date string (YYYY-MM-DD) when norm acquired its current status, null if unknown
- "replaced_by": string describing what replaced this norm (if status is "outdated"), null otherwise
- "is_latest_amendment": boolean true if using latest version, false if using older version
- "analysis": 2-3 sentence description in Russian of what this norm regulates, its scope, and who it applies to
- "related_laws": array of max 3 objects { "title": "official name", "number": "code abbreviation", "relevance": "brief explanation" } of related laws in the same domain
- "formulation_issues": array of max 3 objects { "type": "category", "description": "common mistake in Russian", "suggestion": "how to fix it" } - common errors when citing this norm in contracts/documents

Respond ONLY with valid JSON. No markdown, no explanation outside JSON.`,
        },
        {
          role: 'user',
          content: `Check the following legal norm references from Kazakh legislation. For each, return a comprehensive analysis including status, title, chronology, detailed explanation, related laws, and common formulation issues.

Norms to check:
${normsText}

Return as JSON object where each key is the norm reference text (exactly as provided):
{ "norm1": { status, title, introduced, amendments, current_status_explanation, status_since, replaced_by, is_latest_amendment, analysis, related_laws, formulation_issues }, "norm2": {...} }`,
        },
      ],
      temperature: 0.3,
      max_tokens: 2000,
    })

    const content = response.choices[0].message.content.trim()

    let jsonResponse
    try {
      jsonResponse = JSON.parse(content)
    } catch (e) {
      console.error('Failed to parse OpenAI response:', content)
      return Response.json({ error: 'Invalid JSON response from OpenAI' }, { status: 500 })
    }

    return Response.json({ results: jsonResponse })
  } catch (error) {
    console.error('Norm check error:', error)
    return Response.json({ error: error.message }, { status: 500 })
  }
}
