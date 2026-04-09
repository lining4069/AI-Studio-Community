import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";

import { apiClient } from "@/api/client";
import type {
  KbDocumentCreate,
  KbDocumentResponse,
  KbFileResponse,
  RAGRequest,
  RAGResponse,
  RetrievalRequest,
  RetrievalResponse,
} from "@/api/types";
import { extractListData } from "@/lib/data";

type PageData<T> = {
  items: T[];
  total: number;
  page: number;
  page_size: number;
};

export function useKnowledgeBases() {
  return useQuery({
    queryKey: ["knowledge-bases"],
    queryFn: async () => {
      const response = await apiClient.get<PageData<KbDocumentResponse>>(
        "/v1/knowledge-bases",
      );
      return response.data;
    },
  });
}

export function useKnowledgeBaseDetail(kbId?: string) {
  return useQuery({
    queryKey: ["knowledge-bases", kbId],
    queryFn: async () => {
      const response = await apiClient.get<KbDocumentResponse>(
        `/v1/knowledge-bases/${kbId}`,
      );
      return response.data;
    },
    enabled: Boolean(kbId),
  });
}

export function useCreateKnowledgeBase() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (payload: KbDocumentCreate) => {
      const response = await apiClient.post<KbDocumentResponse, KbDocumentCreate>(
        "/v1/knowledge-bases",
        payload,
      );
      return response.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["knowledge-bases"] });
      toast.success("知识库已创建");
    },
  });
}

export function useKnowledgeBaseFiles(kbId?: string) {
  return useQuery({
    queryKey: ["knowledge-bases", kbId, "files"],
    queryFn: async () => {
      const response = await apiClient.get<PageData<KbFileResponse>>(
        `/v1/knowledge-bases/${kbId}/files`,
      );
      return extractListData(response.data);
    },
    enabled: Boolean(kbId),
  });
}

export function useUploadKnowledgeBaseFile(kbId?: string) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (file: File) => {
      const formData = new FormData();
      formData.append("file", file);

      const response = await apiClient.post<KbFileResponse, FormData>(
        `/v1/knowledge-bases/${kbId}/files`,
        formData,
      );
      return response.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["knowledge-bases", kbId, "files"] });
      toast.success("文件已上传");
    },
  });
}

export function useIndexKnowledgeBaseFile(kbId?: string) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (fileId: string) => {
      const response = await apiClient.post<KbFileResponse, undefined>(
        `/v1/knowledge-bases/${kbId}/files/${fileId}/index`,
      );
      return response.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["knowledge-bases", kbId, "files"] });
      toast.success("索引任务已提交");
    },
  });
}

export function useRetrieveKnowledgeBase() {
  return useMutation({
    mutationFn: async (payload: RetrievalRequest) => {
      const response = await apiClient.post<RetrievalResponse, RetrievalRequest>(
        "/v1/knowledge-bases/retrieve",
        payload,
      );
      return response.data;
    },
  });
}

export function useKnowledgeBaseChat() {
  return useMutation({
    mutationFn: async (payload: RAGRequest) => {
      const response = await apiClient.post<RAGResponse, RAGRequest>(
        "/v1/knowledge-bases/rag",
        payload,
      );
      return response.data;
    },
  });
}
