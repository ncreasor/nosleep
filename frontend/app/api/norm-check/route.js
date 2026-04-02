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
- "status": one of "valid" (norm exists and is in force), "outdated" (norm exists but has been superseded or
  amended in a way that changes its meaning substantially, or is from a version of the code that is no longer current),
  "invalid" (norm does not exist — wrong article number, non-existent code, or repealed without replacement)
- "title": the official name/title of the article or law, null if unknown
- "introduced": ISO date string (YYYY-MM-DD) when the norm was first introduced, null if unknown
- "amendments": array of { "date": "YYYY-MM-DD", "description": "brief description in Russian" },
  maximum 5 most significant amendments, empty array if none or unknown
- "current_status_explanation": 1-2 sentences in Russian explaining the current status

Respond ONLY with a valid JSON object where keys are norm reference texts exactly as provided. No markdown, no explanation outside JSON.`,
        },
        {
          role: 'user',
          content: `Check the following legal norm references from Kazakh legislation. For each, return an object with status, title, introduced date, amendments, and explanation.

Norms to check:
${normsText}

Return as JSON object where each key is the norm reference text (exactly as provided):
{ "norm1": { status, title, introduced, amendments, current_status_explanation }, "norm2": {...} }`,
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
