import { useState } from "react";
import { AuthDialog } from "@/components/AuthDialog";
import { SourceDialog } from "@/components/SourceDialog";
import { SummaryCard } from "@/components/SummaryCard";
import { ThemeToggle } from "@/components/ThemeToggle";
import { TopicFilter } from "@/components/TopicFilter";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { useCurrentUser, useLogout } from "@/hooks/useAuth";
import { useDiscoverFeed } from "@/hooks/useDiscoverFeed";
import { useInfiniteScrollTrigger } from "@/hooks/useInfiniteScrollTrigger";

function App() {
  const [topic, setTopic] = useState<string | null>(null);
  const [openClusterId, setOpenClusterId] = useState<string | null>(null);
  const [authDialogOpen, setAuthDialogOpen] = useState(false);

  const { data: currentUser } = useCurrentUser();
  const logoutMutation = useLogout();

  const { data, fetchNextPage, hasNextPage, isFetchingNextPage, isLoading, isError } =
    useDiscoverFeed(topic ?? undefined);

  const sentinelRef = useInfiniteScrollTrigger(() => {
    if (hasNextPage && !isFetchingNextPage) fetchNextPage();
  });

  const cards = data?.pages.flat() ?? [];

  return (
    <div className="min-h-screen bg-background text-foreground">
      <header className="sticky top-0 z-10 border-b border-border bg-background/95 backdrop-blur">
        <div className="mx-auto flex max-w-5xl items-center justify-between gap-4 px-4 py-3">
          <div className="flex items-center gap-3">
            <h1 className="text-lg font-semibold">News Intelligence</h1>
            <TopicFilter selected={topic} onSelect={setTopic} />
          </div>
          <div className="flex items-center gap-2">
            {currentUser ? (
              <>
                <span className="hidden text-sm text-muted-foreground sm:inline">
                  {currentUser.email}
                </span>
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => logoutMutation.mutate()}
                  disabled={logoutMutation.isPending}
                >
                  Log out
                </Button>
              </>
            ) : (
              <Button variant="outline" size="sm" onClick={() => setAuthDialogOpen(true)}>
                Log in
              </Button>
            )}
            <ThemeToggle />
          </div>
        </div>
      </header>

      <main className="mx-auto max-w-5xl px-4 py-6">
        {isError && (
          <p className="text-sm text-destructive">Couldn't load the feed. Is the API running?</p>
        )}

        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {isLoading &&
            Array.from({ length: 6 }).map((_, i) => (
              <Skeleton key={i} className="h-72 w-full rounded-xl" />
            ))}
          {cards.map((card) => (
            <SummaryCard key={card.cluster_id} card={card} onOpen={setOpenClusterId} />
          ))}
        </div>

        <div ref={sentinelRef} className="h-10" />
        {isFetchingNextPage && (
          <p className="py-4 text-center text-sm text-muted-foreground">Loading more...</p>
        )}
        {!hasNextPage && cards.length > 0 && (
          <p className="py-4 text-center text-sm text-muted-foreground">
            You've reached the end.
          </p>
        )}
      </main>

      <SourceDialog
        clusterId={openClusterId}
        onOpenChange={(open) => !open && setOpenClusterId(null)}
      />
      <AuthDialog open={authDialogOpen} onOpenChange={setAuthDialogOpen} />
    </div>
  );
}

export default App;
