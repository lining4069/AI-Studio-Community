import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";

import { apiClient } from "@/api/client";
import type {
  AgentConfigCreate,
  AgentConfigDetailResponse,
  AgentConfigKBCreate,
  AgentConfigMCPCreate,
  AgentConfigResponse,
  AgentConfigToolCreate,
  AgentConfigUpdate,
  AgentRunRequest,
  AgentRunDetailResponse,
  AgentSessionCreate,
  AgentSessionResponse,
  BuiltinToolsResponse,
} from "@/api/types";
import { extractListData } from "@/lib/data";

export function useAgentConfigs() {
  return useQuery({
    queryKey: ["agent", "configs"],
    queryFn: async () => {
      const response = await apiClient.get<AgentConfigResponse[]>("/v1/agent/configs");
      return response.data ?? [];
    },
  });
}

export function useAgentConfigDetail(configId?: string) {
  return useQuery({
    queryKey: ["agent", "configs", configId],
    queryFn: async () => {
      const response = await apiClient.get<AgentConfigDetailResponse>(
        `/v1/agent/configs/${configId}`,
      );
      return response.data;
    },
    enabled: Boolean(configId),
  });
}

export function useCreateAgentConfig() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (payload: AgentConfigCreate) => {
      const response = await apiClient.post<AgentConfigResponse, AgentConfigCreate>(
        "/v1/agent/configs",
        payload,
      );
      return response.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["agent", "configs"] });
      toast.success("助手已创建");
    },
  });
}

export function useBuiltinTools() {
  return useQuery({
    queryKey: ["agent", "builtin-tools"],
    queryFn: async () => {
      const response = await apiClient.get<BuiltinToolsResponse>(
        "/v1/agent/builtin-tools",
      );
      return response.data?.tools ?? [];
    },
  });
}

export function useCreateSession() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (payload: AgentSessionCreate) => {
      const response = await apiClient.post<AgentSessionResponse, AgentSessionCreate>(
        "/v1/agent/sessions",
        payload,
      );
      return response.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["agent", "sessions"] });
      toast.success("会话已创建");
    },
  });
}

export function useSessions(configId?: string, page = 1, pageSize = 20) {
  return useQuery({
    queryKey: ["agent", "sessions", configId ?? "all", page, pageSize],
    queryFn: async () => {
      const params = new URLSearchParams({
        page: String(page),
        page_size: String(pageSize),
      });

      if (configId) {
        params.set("config_id", configId);
      }

      const response = await apiClient.get<{
        items?: AgentSessionResponse[] | null;
      }>(`/v1/agent/sessions?${params.toString()}`);
      return extractListData(response.data);
    },
  });
}

export function useRunAgent(sessionId?: string) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (payload: AgentRunRequest) => {
      const response = await apiClient.post<AgentRunDetailResponse | Record<string, unknown>, AgentRunRequest>(
        `/v1/agent/sessions/${sessionId}/runs`,
        payload,
      );
      return response.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["agent", "sessions"] });
      queryClient.invalidateQueries({ queryKey: ["agent", "sessions", sessionId] });
      queryClient.invalidateQueries({
        queryKey: ["agent", "sessions", sessionId, "messages"],
      });
      queryClient.invalidateQueries({
        queryKey: ["agent", "sessions", sessionId, "steps"],
      });
    },
  });
}

export function useSessionDetail(sessionId?: string) {
  return useQuery({
    queryKey: ["agent", "sessions", sessionId],
    queryFn: async () => {
      const response = await apiClient.get<AgentSessionResponse>(
        `/v1/agent/sessions/${sessionId}`,
      );
      return response.data;
    },
    enabled: Boolean(sessionId),
  });
}

export function useSessionMessages(sessionId?: string) {
  return useQuery({
    queryKey: ["agent", "sessions", sessionId, "messages"],
    queryFn: async () => {
      const response = await apiClient.get<unknown[]>(
        `/v1/agent/sessions/${sessionId}/messages`,
      );
      return extractListData(response.data as unknown[]);
    },
    enabled: Boolean(sessionId),
  });
}

export function useSessionSteps(sessionId?: string) {
  return useQuery({
    queryKey: ["agent", "sessions", sessionId, "steps"],
    queryFn: async () => {
      const response = await apiClient.get<unknown[]>(
        `/v1/agent/sessions/${sessionId}/steps`,
      );
      return extractListData(response.data as unknown[]);
    },
    enabled: Boolean(sessionId),
  });
}

export function useUpdateAgentConfig(configId?: string) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (payload: AgentConfigUpdate) => {
      const response = await apiClient.put<AgentConfigResponse, AgentConfigUpdate>(
        `/v1/agent/configs/${configId}`,
        payload,
      );
      return response.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["agent", "configs"] });
      queryClient.invalidateQueries({ queryKey: ["agent", "configs", configId] });
      toast.success("助手配置已保存");
    },
  });
}

export function useAddAgentTool(configId?: string) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (payload: AgentConfigToolCreate) => {
      const response = await apiClient.post<unknown, AgentConfigToolCreate>(
        `/v1/agent/configs/${configId}/tools`,
        payload,
      );
      return response.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["agent", "configs", configId] });
      toast.success("内置工具已加入助手");
    },
  });
}

export function useRemoveAgentTool(configId?: string) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (toolId: number) => {
      await apiClient.delete(`/v1/agent/configs/${configId}/tools/${toolId}`);
      return toolId;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["agent", "configs", configId] });
      toast.success("工具已移除");
    },
  });
}

export function useLinkAgentMcp(configId?: string) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (payload: AgentConfigMCPCreate) => {
      const response = await apiClient.post<unknown, AgentConfigMCPCreate>(
        `/v1/agent/configs/${configId}/mcp-servers`,
        payload,
      );
      return response.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["agent", "configs", configId] });
      toast.success("MCP 已关联到助手");
    },
  });
}

export function useUnlinkAgentMcp(configId?: string) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (linkId: number) => {
      await apiClient.delete(`/v1/agent/configs/${configId}/mcp-servers/${linkId}`);
      return linkId;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["agent", "configs", configId] });
      toast.success("MCP 关联已移除");
    },
  });
}

export function useLinkAgentKb(configId?: string) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (payload: AgentConfigKBCreate) => {
      const response = await apiClient.post<unknown, AgentConfigKBCreate>(
        `/v1/agent/configs/${configId}/kbs`,
        payload,
      );
      return response.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["agent", "configs", configId] });
      toast.success("知识库已关联到助手");
    },
  });
}

export function useUnlinkAgentKb(configId?: string) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (linkId: number) => {
      await apiClient.delete(`/v1/agent/configs/${configId}/kbs/${linkId}`);
      return linkId;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["agent", "configs", configId] });
      toast.success("知识库关联已移除");
    },
  });
}
