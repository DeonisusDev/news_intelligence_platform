import { useInfiniteQuery } from "@tanstack/react-query";
import { fetchLikedPage, PAGE_SIZE } from "@/api/discover";

export function useLikedFeed(enabled: boolean) {
  return useInfiniteQuery({
    queryKey: ["liked"],
    queryFn: ({ pageParam }) => fetchLikedPage(pageParam),
    initialPageParam: 0,
    getNextPageParam: (lastPage, allPages) =>
      lastPage.length < PAGE_SIZE ? undefined : allPages.length * PAGE_SIZE,
    enabled,
  });
}
