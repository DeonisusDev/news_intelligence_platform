import { useQuery } from "@tanstack/react-query";
import { fetchClusterDetail } from "@/api/discover";

export function useClusterDetail(clusterId: string | null) {
  return useQuery({
    queryKey: ["cluster", clusterId],
    queryFn: () => fetchClusterDetail(clusterId as string),
    enabled: clusterId !== null,
  });
}
