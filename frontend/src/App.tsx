import { Heart, Search } from "lucide-react";
import { useEffect, useState } from "react";
import { AuthDialog } from "@/components/AuthDialog";
import { SourceDialog } from "@/components/SourceDialog";
import { SummaryCard } from "@/components/SummaryCard";
import { ThemeToggle } from "@/components/ThemeToggle";
import { TopicFilter } from "@/components/TopicFilter";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import { useCurrentUser, useLogout } from "@/hooks/useAuth";
import { useDiscoverFeed } from "@/hooks/useDiscoverFeed";
import { useInfiniteScrollTrigger } from "@/hooks/useInfiniteScrollTrigger";
import { useLikedFeed } from "@/hooks/useLikedFeed";

type View = "feed" | "liked";

function App() {
  const [view, setView] = useState<View>("feed");
  const [topic, setTopic] = useState<string | null>(null);
  const [searchInput, setSearchInput] = useState("");
  const [search, setSearch] = useState("");
  const [openClusterId, setOpenClusterId] = useState<string | null>(null);
  const [authDialogOpen, setAuthDialogOpen] = useState(false);

  const { data: currentUser } = useCurrentUser();
  const logoutMutation = useLogout();

  // The Liked toggle only exists while logged in - fall back to the main feed on logout so a
  // stale "liked" view isn't left stranded with no way back to it.
  useEffect(() => {
    if (!currentUser) setView("feed");
  }, [currentUser]);

  // Debounce the search box so every keystroke doesn't fire its own /discover request.
  useEffect(() => {
    const id = setTimeout(() => setSearch(searchInput.trim()), 400);
    return () => clearTimeout(id);
  }, [searchInput]);

  const feed = useDiscoverFeed(topic ?? undefined, search || undefined);
  const liked = useLikedFeed(view === "liked" && !!currentUser);
  const active = view === "liked" ? liked : feed;
  const { fetchNextPage, hasNextPage, isFetchingNextPage, isLoading, isError } = active;

  const sentinelRef = useInfiniteScrollTrigger(() => {
    if (hasNextPage && !isFetchingNextPage) fetchNextPage();
  });

  const cards = active.data?.pages.flat() ?? [];

  return (
    <div className="min-h-screen bg-background text-foreground">
      <header className="sticky top-0 z-10 border-b border-border bg-background/95 backdrop-blur">
        <div className="mx-auto flex max-w-5xl items-center justify-between gap-4 px-4 py-3">
          <div className="flex items-center gap-3">
            <h1 className="text-lg font-semibold">News Intelligence</h1>
            {view === "feed" && <TopicFilter selected={topic} onSelect={setTopic} />}
            {currentUser && (
              <Button
                variant={view === "liked" ? "secondary" : "ghost"}
                size="sm"
                className="gap-1.5"
                onClick={() => setView(view === "liked" ? "feed" : "liked")}
              >
                <Heart className="size-3.5" fill={view === "liked" ? "currentColor" : "none"} />
                Liked
              </Button>
            )}
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
        {view === "feed" && (
          <div className="relative mb-4 max-w-sm">
            <Search className="pointer-events-none absolute top-1/2 left-2.5 size-3.5 -translate-y-1/2 text-muted-foreground" />
            <Input
              value={searchInput}
              onChange={(e) => setSearchInput(e.target.value)}
              placeholder="Search stories..."
              className="h-8 pl-8"
            />
          </div>
        )}

        {isError && (
          <p className="text-sm text-destructive">
            {view === "liked"
              ? "Couldn't load your liked stories. Is the API running?"
              : "Couldn't load the feed. Is the API running?"}
          </p>
        )}

        {view === "liked" && !isLoading && cards.length === 0 && (
          <p className="py-8 text-center text-sm text-muted-foreground">
            Nothing liked yet - tap the thumbs-up on a story to save it here.
          </p>
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
