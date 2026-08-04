import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { fetchCurrentUser, login, logout, register } from "@/api/auth";

const CURRENT_USER_KEY = ["auth", "me"];

export function useCurrentUser() {
  return useQuery({
    queryKey: CURRENT_USER_KEY,
    queryFn: fetchCurrentUser,
    staleTime: 5 * 60 * 1000,
    retry: false,
  });
}

export function useLogin() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ email, password }: { email: string; password: string }) =>
      login(email, password),
    onSuccess: (user) => queryClient.setQueryData(CURRENT_USER_KEY, user),
  });
}

export function useRegister() {
  return useMutation({
    mutationFn: ({ email, password }: { email: string; password: string }) =>
      register(email, password),
  });
}

export function useLogout() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: logout,
    onSuccess: () => queryClient.setQueryData(CURRENT_USER_KEY, null),
  });
}
