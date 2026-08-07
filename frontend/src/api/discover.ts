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
  // Phase 7 - the logged-in requester's own vote on this cluster, if any.
  my_vote: 1 | -1 | null;
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

  // credentials: "include" - GET /discover branches on the session cookie (Phase 7: a logged-in
  // request gets an affinity-re-ranked feed with my_vote populated per card; without this, the
  // browser silently drops the cookie and every request looks anonymous to the backend.
  const response = await fetch(`${API_BASE_URL}/discover?${params}`, { credentials: "include" });
  if (!response.ok) throw new Error(`Failed to load feed (${response.status})`);
  return response.json();
}

// The "Liked" page: previously-upvoted clusters, most recently liked first. Requires a session
// cookie - 401s if logged out (the caller should only invoke this when currentUser is set).
export async function fetchLikedPage(offset: number): Promise<SummaryCard[]> {
  const params = new URLSearchParams({ limit: String(PAGE_SIZE), offset: String(offset) });
  const response = await fetch(`${API_BASE_URL}/discover/liked?${params}`, {
    credentials: "include",
  });
  if (!response.ok) throw new Error(`Failed to load liked stories (${response.status})`);
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

// Phase 7: thumbs up/down. Requires a logged-in session (httpOnly cookie) - 401s otherwise.
export async function submitFeedback(clusterId: string, vote: 1 | -1): Promise<void> {
  const response = await fetch(`${API_BASE_URL}/discover/${clusterId}/feedback`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    credentials: "include",
    body: JSON.stringify({ vote }),
  });
  if (!response.ok) throw new Error(`Failed to submit feedback (${response.status})`);
}

export async function removeFeedback(clusterId: string): Promise<void> {
  const response = await fetch(`${API_BASE_URL}/discover/${clusterId}/feedback`, {
    method: "DELETE",
    credentials: "include",
  });
  if (!response.ok) throw new Error(`Failed to remove feedback (${response.status})`);
}
