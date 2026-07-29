const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000";

export const PAGE_SIZE = 20;

export interface SummaryCard {
  cluster_id: string;
  summary: string;
  topic: string;
  sentiment: string;
  sentiment_score: number | null;
  keywords: string[];
  article_count: number;
  enriched_at: string;
  first_published_at: string;
  image_url: string | null;
}

export interface SourceArticle {
  source_name: string | null;
  source_provider: string | null;
  title: string | null;
  url: string;
  url_to_image: string | null;
  published_at: string | null;
  category: string | null;
  // Phase 6.1: "what this outlet focused on" - not present for every source.
  source_summary: string | null;
}

export interface KeyFacts {
  organizations: string[];
  locations: string[];
  people: string[];
}

export interface SummaryDetail extends SummaryCard {
  sources: SourceArticle[];
  // Phase 6.1 - detail-view-only.
  key_facts: KeyFacts;
  why_it_matters: string;
  before_state: string | null;
  after_state: string | null;
  consensus_points: string[];
  disagreement_points: string[];
}

export interface TopicStat {
  topic: string;
  cluster_count: number;
}

export async function fetchDiscoverPage(offset: number, topic?: string): Promise<SummaryCard[]> {
  const params = new URLSearchParams({ limit: String(PAGE_SIZE), offset: String(offset) });
  if (topic) params.set("topic", topic);

  const response = await fetch(`${API_BASE_URL}/discover?${params}`);
  if (!response.ok) throw new Error(`Failed to load feed (${response.status})`);
  return response.json();
}

export async function fetchClusterDetail(clusterId: string): Promise<SummaryDetail> {
  const response = await fetch(`${API_BASE_URL}/discover/${clusterId}`);
  if (!response.ok) throw new Error(`Failed to load story (${response.status})`);
  return response.json();
}

export async function fetchTopics(): Promise<TopicStat[]> {
  const response = await fetch(`${API_BASE_URL}/stats/topics`);
  if (!response.ok) throw new Error(`Failed to load topics (${response.status})`);
  return response.json();
}
