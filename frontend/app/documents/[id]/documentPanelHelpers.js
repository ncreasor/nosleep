export function groundingVerdictLabel(verdict) {
  const m = {
    applicable: 'Подтверждено',
    partially_applicable: 'Частично',
    not_applicable: 'Не подтверждено',
    unclear: 'Неясно',
  }
  return m[verdict] || null
}

export function ringPctForArticle(article) {
  const g = article.grounding
  if (g && typeof g.grounding_confidence === 'number') return g.grounding_confidence
  if (typeof article.confidence === 'number') return article.confidence
  if (typeof article.semantic_similarity_pct === 'number') return article.semantic_similarity_pct
  return null
}

export function isGrounded(article) {
  return !!(article.grounding && article.grounding.verdict && article.grounding.verdict !== 'unclear')
}

export function ringColorsForArticle(article) {
  const g = article.grounding
  if (g?.verdict === 'applicable') return { confColor: 'text-emerald-600', ringColor: 'stroke-emerald-500' }
  if (g?.verdict === 'partially_applicable') return { confColor: 'text-amber-600', ringColor: 'stroke-amber-500' }
  if (g?.verdict === 'unclear') return { confColor: 'text-slate-500', ringColor: 'stroke-slate-400' }
  const level = article.confidence_level
  if (level === 'high') return { confColor: 'text-emerald-600', ringColor: 'stroke-emerald-500' }
  if (level === 'medium') return { confColor: 'text-amber-600', ringColor: 'stroke-amber-500' }
  return { confColor: 'text-slate-500', ringColor: 'stroke-slate-400' }
}
