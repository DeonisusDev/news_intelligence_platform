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

interface SourceDialogProps {
  clusterId: string | null;
  onOpenChange: (open: boolean) => void;
}

export function SourceDialog({ clusterId, onOpenChange }: SourceDialogProps) {
  const { data, isLoading, isError } = useClusterDetail(clusterId);

  return (
    <Dialog open={clusterId !== null} onOpenChange={onOpenChange}>
      <DialogContent className="max-h-[85vh] overflow-y-auto sm:max-w-lg">
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

            <div className="mt-4 space-y-3">
              <h3 className="text-sm font-semibold text-foreground">Sources</h3>
              <ul className="space-y-2">
                {data.sources.map((source) => (
                  <li key={source.url}>
                    <a
                      href={source.url}
                      target="_blank"
                      rel="noreferrer"
                      className="flex items-center justify-between gap-3 rounded-lg border border-border p-3 text-sm transition-colors hover:bg-muted"
                    >
                      <span className="font-medium">
                        {source.source_name ?? "Unknown source"}
                      </span>
                      {source.published_at && (
                        <span className="shrink-0 text-xs text-muted-foreground">
                          {timeAgo(source.published_at)}
                        </span>
                      )}
                    </a>
                  </li>
                ))}
              </ul>
            </div>
          </>
        )}
      </DialogContent>
    </Dialog>
  );
}
