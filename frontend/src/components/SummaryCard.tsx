import type { SummaryCard as SummaryCardData } from "@/api/discover";
import { Badge } from "@/components/ui/badge";
import { consensusLabel } from "@/lib/consensus";
import { timeAgo } from "@/lib/time";

interface SummaryCardProps {
  card: SummaryCardData;
  onOpen: (clusterId: string) => void;
}

export function SummaryCard({ card, onOpen }: SummaryCardProps) {
  return (
    <button
      type="button"
      onClick={() => onOpen(card.cluster_id)}
      className="flex flex-col overflow-hidden rounded-xl border border-border bg-card text-left shadow-sm transition-shadow hover:shadow-md focus-visible:outline focus-visible:outline-2 focus-visible:outline-ring"
    >
      {card.image_url && (
        <img src={card.image_url} alt="" className="h-44 w-full object-cover" loading="lazy" />
      )}
      <div className="flex flex-1 flex-col gap-2 p-4">
        <div className="flex flex-wrap items-center gap-2">
          <Badge variant="secondary">{card.topic}</Badge>
          <Badge variant="outline">{consensusLabel(card.article_count)}</Badge>
        </div>
        <p className="line-clamp-4 text-sm leading-relaxed text-foreground">{card.summary}</p>
        <div className="mt-auto flex items-center justify-between pt-2 text-xs text-muted-foreground">
          <span>{timeAgo(card.first_published_at)}</span>
          <span>
            Covered by {card.article_count} source{card.article_count === 1 ? "" : "s"}
          </span>
        </div>
      </div>
    </button>
  );
}
