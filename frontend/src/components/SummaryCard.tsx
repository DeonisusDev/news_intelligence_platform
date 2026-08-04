import { ThumbsDown, ThumbsUp } from "lucide-react";
import type { SummaryCard as SummaryCardData } from "@/api/discover";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { useCurrentUser } from "@/hooks/useAuth";
import { useFeedback } from "@/hooks/useFeedback";
import { consensusLabel } from "@/lib/consensus";
import { timeAgo } from "@/lib/time";

interface SummaryCardProps {
  card: SummaryCardData;
  onOpen: (clusterId: string) => void;
}

function FeedbackButtons({ clusterId, myVote }: { clusterId: string; myVote: 1 | -1 | null }) {
  const { vote, unvote } = useFeedback();
  const pending = vote.isPending || unvote.isPending;

  function handleVote(e: React.MouseEvent, value: 1 | -1) {
    e.stopPropagation();
    if (myVote === value) {
      unvote.mutate(clusterId);
    } else {
      vote.mutate({ clusterId, vote: value });
    }
  }

  return (
    <div className="flex items-center gap-0.5">
      <Button
        type="button"
        variant="ghost"
        size="icon-xs"
        aria-label="Upvote"
        aria-pressed={myVote === 1}
        disabled={pending}
        onClick={(e) => handleVote(e, 1)}
        className={myVote === 1 ? "text-emerald-600 dark:text-emerald-400" : ""}
      >
        <ThumbsUp className="size-3.5" />
      </Button>
      <Button
        type="button"
        variant="ghost"
        size="icon-xs"
        aria-label="Downvote"
        aria-pressed={myVote === -1}
        disabled={pending}
        onClick={(e) => handleVote(e, -1)}
        className={myVote === -1 ? "text-red-600 dark:text-red-400" : ""}
      >
        <ThumbsDown className="size-3.5" />
      </Button>
    </div>
  );
}

export function SummaryCard({ card, onOpen }: SummaryCardProps) {
  const { data: currentUser } = useCurrentUser();

  return (
    <div
      role="button"
      tabIndex={0}
      onClick={() => onOpen(card.cluster_id)}
      onKeyDown={(e) => {
        if (e.key === "Enter" || e.key === " ") {
          e.preventDefault();
          onOpen(card.cluster_id);
        }
      }}
      className="flex cursor-pointer flex-col overflow-hidden rounded-xl border border-border bg-card text-left shadow-sm transition-shadow hover:shadow-md focus-visible:outline focus-visible:outline-2 focus-visible:outline-ring"
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
          <div className="flex items-center gap-3">
            <span>
              Covered by {card.article_count} source{card.article_count === 1 ? "" : "s"}
            </span>
            {currentUser && <FeedbackButtons clusterId={card.cluster_id} myVote={card.my_vote} />}
          </div>
        </div>
      </div>
    </div>
  );
}
