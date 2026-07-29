// Cheap article-count heuristic, not an LLM-derived confidence score - see the plan's Phase 6
// notes for why: a real confidence signal is deferred to Phase 6.1, once there's enrichment
// data worth basing it on.
export function consensusLabel(articleCount: number): string {
  if (articleCount >= 5) return "High consensus";
  if (articleCount >= 3) return "Medium consensus";
  return "Low consensus";
}
