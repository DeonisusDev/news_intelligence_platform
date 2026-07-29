import { Check, X } from "lucide-react";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { useClusterDetail } from "@/hooks/useClusterDetail";
import { timeAgo } from "@/lib/time";
import type { SummaryDetail } from "@/api/discover";

interface SourceDialogProps {
  clusterId: string | null;
  onOpenChange: (open: boolean) => void;
}

export function SourceDialog({ clusterId, onOpenChange }: SourceDialogProps) {
  const { data, isLoading, isError } = useClusterDetail(clusterId);

  return (
    <Dialog open={clusterId !== null} onOpenChange={onOpenChange}>
      <DialogContent className="max-h-[85vh] overflow-y-auto sm:max-w-2xl">
        {isLoading && (
          <div className="space-y-3">
            <Skeleton className="h-6 w-3/4" />
            <Skeleton className="h-20 w-full" />
            <Skeleton className="h-4 w-1/2" />
          </div>
        )}

        {isError && <p className="text-sm text-destructive">Couldn't load this story.</p>}

        {data && (
          <>
            <DialogHeader>
              <div className="flex flex-wrap items-center gap-2">
                <Badge variant="secondary">{data.topic}</Badge>
                <Badge variant="outline">{data.article_count} sources</Badge>
              </div>
              <DialogTitle className="text-left">{data.summary}</DialogTitle>
              <DialogDescription className="text-left">
                First reported {timeAgo(data.first_published_at)}
              </DialogDescription>
            </DialogHeader>

            <AnalysisSection data={data} />
            <KeyFactsSection data={data} />
            <ConsensusSection data={data} />
            <SourcesSection data={data} />
          </>
        )}
      </DialogContent>
    </Dialog>
  );
}

function AnalysisSection({ data }: { data: SummaryDetail }) {
  if (!data.why_it_matters) return null;

  return (
    <div className="mt-4 space-y-3">
      <h3 className="text-sm font-semibold text-foreground">Why it matters</h3>
      <p className="text-sm leading-relaxed text-muted-foreground">{data.why_it_matters}</p>
      {data.before_state && data.after_state && (
        <div className="grid grid-cols-2 gap-3">
          <div className="rounded-lg border border-border p-3">
            <p className="text-xs font-medium text-muted-foreground uppercase">Before</p>
            <p className="mt-1 text-sm">{data.before_state}</p>
          </div>
          <div className="rounded-lg border border-border p-3">
            <p className="text-xs font-medium text-muted-foreground uppercase">After</p>
            <p className="mt-1 text-sm">{data.after_state}</p>
          </div>
        </div>
      )}
    </div>
  );
}

function KeyFactsSection({ data }: { data: SummaryDetail }) {
  const { organizations, locations, people } = data.key_facts;
  if (organizations.length === 0 && locations.length === 0 && people.length === 0) return null;

  const groups: { label: string; values: string[] }[] = [
    { label: "Organizations", values: organizations },
    { label: "Locations", values: locations },
    { label: "People", values: people },
  ];

  return (
    <div className="mt-4 space-y-2">
      <h3 className="text-sm font-semibold text-foreground">Key facts</h3>
      <div className="space-y-2">
        {groups
          .filter((g) => g.values.length > 0)
          .map((g) => (
            <div key={g.label} className="flex flex-wrap items-center gap-1.5 text-sm">
              <span className="text-muted-foreground">{g.label}:</span>
              {g.values.map((v) => (
                <Badge key={v} variant="outline">
                  {v}
                </Badge>
              ))}
            </div>
          ))}
      </div>
    </div>
  );
}

function ConsensusSection({ data }: { data: SummaryDetail }) {
  const { consensus_points, disagreement_points } = data;
  if (consensus_points.length === 0 && disagreement_points.length === 0) return null;

  return (
    <div className="mt-4 grid grid-cols-1 gap-3 sm:grid-cols-2">
      {consensus_points.length > 0 && (
        <div>
          <h3 className="mb-1.5 text-sm font-semibold text-foreground">Agreement</h3>
          <ul className="space-y-1.5">
            {consensus_points.map((point) => (
              <li key={point} className="flex items-start gap-1.5 text-sm">
                <Check className="mt-0.5 size-3.5 shrink-0 text-emerald-600 dark:text-emerald-400" />
                <span>{point}</span>
              </li>
            ))}
          </ul>
        </div>
      )}
      {disagreement_points.length > 0 && (
        <div>
          <h3 className="mb-1.5 text-sm font-semibold text-foreground">Disagreement</h3>
          <ul className="space-y-1.5">
            {disagreement_points.map((point) => (
              <li key={point} className="flex items-start gap-1.5 text-sm">
                <X className="mt-0.5 size-3.5 shrink-0 text-red-600 dark:text-red-400" />
                <span>{point}</span>
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}

function SourcesSection({ data }: { data: SummaryDetail }) {
  return (
    <div className="mt-4 space-y-3">
      <h3 className="text-sm font-semibold text-foreground">Sources</h3>
      <ul className="space-y-2">
        {data.sources.map((source) => (
          <li key={source.url}>
            <a
              href={source.url}
              target="_blank"
              rel="noreferrer"
              className="block rounded-lg border border-border p-3 text-sm transition-colors hover:bg-muted"
            >
              <div className="flex items-center justify-between gap-3">
                <span className="font-medium">{source.source_name ?? "Unknown source"}</span>
                {source.published_at && (
                  <span className="shrink-0 text-xs text-muted-foreground">
                    {timeAgo(source.published_at)}
                  </span>
                )}
              </div>
              {source.source_summary && (
                <p className="mt-1 text-xs text-muted-foreground">{source.source_summary}</p>
              )}
            </a>
          </li>
        ))}
      </ul>
    </div>
  );
}
