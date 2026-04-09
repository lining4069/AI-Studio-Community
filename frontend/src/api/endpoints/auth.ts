import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";

import { apiClient } from "@/api/client";
import type {
  RefreshTokenRequest,
  UserAuthedResponse,
  UserCreateRequest,
  UserResponse,
} from "@/api/types";
import { authStorage } from "@/lib/storage";

type LoginRequest = {
  username: string;
  password: string;
  device_id: string;
};

export function useCurrentUser() {
  return useQuery({
    queryKey: ["auth", "current-user"],
    queryFn: async () => {
      const response = await apiClient.get<UserResponse>("/v1/user/info");
      return response.data;
    },
    enabled: authStorage.hasAccessToken(),
  });
}

export function useLogin() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (payload: LoginRequest) => {
      const response = await apiClient.post<UserAuthedResponse, LoginRequest>(
        "/v1/auth/login",
        payload,
      );
      return response.data;
    },
    onSuccess: (data) => {
      authStorage.setTokens({
        accessToken: data.access_token,
        refreshToken: data.refresh_token,
      });
      queryClient.invalidateQueries({ queryKey: ["auth", "current-user"] });
      queryClient.invalidateQueries({ queryKey: ["user", "profile"] });
      toast.success(`欢迎回来，${data.userInfo.nickname ?? data.userInfo.username}`);
    },
  });
}

export function useRegister() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (payload: UserCreateRequest) => {
      const response = await apiClient.post<UserAuthedResponse, UserCreateRequest>(
        "/v1/auth/register",
        payload,
      );
      return response.data;
    },
    onSuccess: (data) => {
      authStorage.setTokens({
        accessToken: data.access_token,
        refreshToken: data.refresh_token,
      });
      queryClient.invalidateQueries({ queryKey: ["auth", "current-user"] });
      queryClient.invalidateQueries({ queryKey: ["user", "profile"] });
      toast.success(`注册成功，欢迎 ${data.userInfo.username}`);
    },
  });
}

export function useRefreshToken() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (payload: RefreshTokenRequest) => {
      const response = await apiClient.post<UserAuthedResponse, RefreshTokenRequest>(
        "/v1/auth/refresh",
        payload,
      );
      return response.data;
    },
    onSuccess: (data) => {
      authStorage.setTokens({
        accessToken: data.access_token,
        refreshToken: data.refresh_token,
      });
      queryClient.invalidateQueries({ queryKey: ["auth", "current-user"] });
    },
  });
}

export function useLogout() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async () => {
      const tokens = authStorage.getTokens();
      if (!tokens) {
        return null;
      }

      await apiClient.post<null, { refresh_token: string }>("/v1/auth/logout", {
        refresh_token: tokens.refreshToken,
      });

      return null;
    },
    onSettled: () => {
      authStorage.clear();
      queryClient.clear();
      toast.success("你已退出登录");
    },
  });
}
