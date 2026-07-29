import { useQuery } from "@tanstack/react-query";
import { fetchTopics } from "@/api/discover";

export function useTopics() {
  return useQuery({
    queryKey: ["topics"],
    queryFn: fetchTopics,
    staleTime: 5 * 60 * 1000,
  });
}
