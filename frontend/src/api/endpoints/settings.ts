import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";

import { apiClient } from "@/api/client";
import type {
  AgentMCPServerCreate,
  AgentMCPServerResponse,
  EmbeddingModelCreate,
  EmbeddingModelResponse,
  LlmModelCreate,
  LlmModelResponse,
  RerankModelCreate,
  RerankModelResponse,
} from "@/api/types";

type PageData<T> = {
  items: T[];
};

export function useMcpServers() {
  return useQuery({
    queryKey: ["settings", "mcp-servers"],
    queryFn: async () => {
      const response = await apiClient.get<AgentMCPServerResponse[]>(
        "/v1/agent/mcp-servers",
      );
      return response.data ?? [];
    },
  });
}

export function useCreateMcpServer() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (payload: AgentMCPServerCreate) => {
      const response = await apiClient.post<
        AgentMCPServerResponse,
        AgentMCPServerCreate
      >("/v1/agent/mcp-servers", payload);
      return response.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["settings", "mcp-servers"] });
      toast.success("MCP Server 已创建");
    },
  });
}

export function useChatModels() {
  return useQuery({
    queryKey: ["settings", "chat-models"],
    queryFn: async () => {
      const response = await apiClient.get<PageData<LlmModelResponse>>("/v1/llm-models");
      return response.data?.items ?? [];
    },
  });
}

export function useCreateChatModel() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (payload: LlmModelCreate) => {
      const response = await apiClient.post<LlmModelResponse, LlmModelCreate>(
        "/v1/llm-models",
        payload,
      );
      return response.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["settings", "chat-models"] });
      toast.success("Chat Model 已创建");
    },
  });
}

export function useEmbeddingModels() {
  return useQuery({
    queryKey: ["settings", "embedding-models"],
    queryFn: async () => {
      const response = await apiClient.get<PageData<EmbeddingModelResponse>>(
        "/v1/embedding-models",
      );
      return response.data?.items ?? [];
    },
  });
}

export function useCreateEmbeddingModel() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (payload: EmbeddingModelCreate) => {
      const response = await apiClient.post<
        EmbeddingModelResponse,
        EmbeddingModelCreate
      >("/v1/embedding-models", payload);
      return response.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["settings", "embedding-models"] });
      toast.success("Embedding Model 已创建");
    },
  });
}

export function useRerankModels() {
  return useQuery({
    queryKey: ["settings", "rerank-models"],
    queryFn: async () => {
      const response = await apiClient.get<PageData<RerankModelResponse>>(
        "/v1/rerank-models",
      );
      return response.data?.items ?? [];
    },
  });
}

export function useCreateRerankModel() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (payload: RerankModelCreate) => {
      const response = await apiClient.post<RerankModelResponse, RerankModelCreate>(
        "/v1/rerank-models",
        payload,
      );
      return response.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["settings", "rerank-models"] });
      toast.success("Rerank Model 已创建");
    },
  });
}
