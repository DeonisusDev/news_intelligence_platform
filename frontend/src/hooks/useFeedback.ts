import { useMutation, useQueryClient } from "@tanstack/react-query";
import { removeFeedback, submitFeedback } from "@/api/discover";

export function useFeedback() {
  const queryClient = useQueryClient();

  const vote = useMutation({
    mutationFn: ({ clusterId, vote }: { clusterId: string; vote: 1 | -1 }) =>
      submitFeedback(clusterId, vote),
    // The backend re-ranks the feed by affinity after a vote, so a full refetch (not just a
    // local cache patch) is the only way to reflect the new ordering.
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["discover"] }),
  });

  const unvote = useMutation({
    mutationFn: (clusterId: string) => removeFeedback(clusterId),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["discover"] }),
  });

  return { vote, unvote };
}
