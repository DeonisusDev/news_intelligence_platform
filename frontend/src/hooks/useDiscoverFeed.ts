import { useInfiniteQuery } from "@tanstack/react-query";
import { fetchDiscoverPage, PAGE_SIZE } from "@/api/discover";

export function useDiscoverFeed(topic?: string) {
  return useInfiniteQuery({
    queryKey: ["discover", topic ?? "all"],
    queryFn: ({ pageParam }) => fetchDiscoverPage(pageParam, topic),
    initialPageParam: 0,
    getNextPageParam: (lastPage, allPages) =>
      lastPage.length < PAGE_SIZE ? undefined : allPages.length * PAGE_SIZE,
  });
}
