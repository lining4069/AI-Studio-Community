import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";

import { apiClient } from "@/api/client";
import type { UserResponse, UserUpdateRequest } from "@/api/types";

export function useUserProfile() {
  return useQuery({
    queryKey: ["user", "profile"],
    queryFn: async () => {
      const response = await apiClient.get<UserResponse>("/v1/user/info");
      return response.data;
    },
  });
}

export function useUpdateUserProfile() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (payload: UserUpdateRequest) => {
      const response = await apiClient.put<UserResponse, UserUpdateRequest>("/v1/user/update", payload);
      return response.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["user", "profile"] });
      queryClient.invalidateQueries({ queryKey: ["auth", "current-user"] });
      toast.success("账户信息已更新");
    },
  });
}
