import { useState } from "react";
import { Upload, Wand2 } from "lucide-react";
import { useParams } from "react-router-dom";

import {
  useIndexKnowledgeBaseFile,
  useKnowledgeBaseChat,
  useKnowledgeBaseDetail,
  useKnowledgeBaseFiles,
  useRetrieveKnowledgeBase,
  useUploadKnowledgeBaseFile,
} from "@/api/endpoints/knowledge-base";
import { useChatModels } from "@/api/endpoints/settings";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Button } from "@/components/ui/button";
import { SectionHeading } from "@/components/shared/section-heading";
import { EmptyState } from "@/components/shared/empty-state";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { formatDate } from "@/lib/utils";

export function KnowledgeBaseDetailRoute() {
  const { kbId } = useParams();
  const [retrieveQuery, setRetrieveQuery] = useState("");
  const [chatQuery, setChatQuery] = useState("");
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [selectedModelId, setSelectedModelId] = useState("");

  const detail = useKnowledgeBaseDetail(kbId);
  const files = useKnowledgeBaseFiles(kbId);
  const retrieve = useRetrieveKnowledgeBase();
  const chat = useKnowledgeBaseChat();
  const uploadFile = useUploadKnowledgeBaseFile(kbId);
  const indexFile = useIndexKnowledgeBaseFile(kbId);
  const chatModels = useChatModels();

  const handleRetrieve = async () => {
    if (!kbId || !retrieveQuery.trim()) {
      return;
    }

    await retrieve.mutateAsync({
      query: retrieveQuery,
      kb_ids: [kbId],
    });
  };

  const handleChat = async () => {
    if (!kbId || !chatQuery.trim()) {
      return;
    }

    await chat.mutateAsync({
      query: chatQuery,
      kb_ids: [kbId],
      llm_model_id: selectedModelId || undefined,
    });
  };

  const handleUpload = async () => {
    if (!selectedFile) {
      return;
    }

    await uploadFile.mutateAsync(selectedFile);
    setSelectedFile(null);
  };

  return (
    <div className="space-y-8">
      <SectionHeading
        eyebrow="Knowledge Base Detail"
        title={detail.data?.name ?? "知识库详情"}
        description={
          detail.data?.description ??
          "知识库详情页内聚 Overview、Files、Retrieve 和 Chat 四个页签，便于在一个工作区里完成管理与验证。"
        }
      />

      <Tabs defaultValue="overview">
        <TabsList>
          <TabsTrigger value="overview">Overview</TabsTrigger>
          <TabsTrigger value="files">Files</TabsTrigger>
          <TabsTrigger value="retrieve">Retrieve</TabsTrigger>
          <TabsTrigger value="chat">Chat</TabsTrigger>
        </TabsList>
        <TabsContent value="overview">
          <Card>
            <CardHeader>
              <CardTitle>知识库概览</CardTitle>
              <CardDescription>展示 chunk 参数、关联模型、文件数量和最近更新时间。</CardDescription>
            </CardHeader>
            <CardContent className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
              {detail.data
                ? [
                    ["Chunk Size", detail.data.chunk_size],
                    ["Chunk Overlap", detail.data.chunk_overlap],
                    ["Top K", detail.data.top_k],
                    ["更新时间", formatDate(detail.data.updated_at)],
                  ].map(([label, value]) => (
                    <div key={label} className="rounded-2xl border border-slate-200 p-4">
                      <p className="text-xs font-semibold uppercase tracking-[0.2em] text-sky-600">
                        {label}
                      </p>
                      <p className="mt-3 text-lg font-semibold text-slate-950">{value}</p>
                    </div>
                  ))
                : null}
            </CardContent>
          </Card>
        </TabsContent>
        <TabsContent value="files">
          <Card>
            <CardHeader>
              <CardTitle>文件与索引</CardTitle>
              <CardDescription>处理上传、文件列表和单文件索引。</CardDescription>
            </CardHeader>
            <CardContent className="space-y-5">
              <div className="rounded-3xl border border-dashed border-slate-300 bg-slate-50 p-5">
                <div className="grid gap-4 md:grid-cols-[1fr_auto] md:items-end">
                  <div className="space-y-2">
                    <p className="text-sm font-medium text-slate-950">上传文件</p>
                    <Input
                      type="file"
                      onChange={(event) =>
                        setSelectedFile(event.target.files?.[0] ?? null)
                      }
                    />
                  </div>
                  <Button onClick={handleUpload} disabled={!selectedFile || uploadFile.isPending}>
                    <Upload className="mr-2 size-4" />
                    {uploadFile.isPending ? "上传中..." : "上传文件"}
                  </Button>
                </div>
              </div>

              {files.data?.length ? (
                <div className="space-y-3">
                  {files.data.map((file) => (
                    <div
                      key={file.id}
                      className="rounded-2xl border border-slate-200 p-4"
                    >
                      <div className="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
                        <div>
                          <p className="font-medium text-slate-950">{file.file_name}</p>
                          <p className="mt-1 text-sm text-slate-500">
                            {file.status} · {Math.round(file.file_size / 1024)} KB ·
                            更新于 {formatDate(file.updated_at)}
                          </p>
                        </div>
                        <Button
                          variant="outline"
                          onClick={() => indexFile.mutate(file.id)}
                          disabled={indexFile.isPending}
                        >
                          <Wand2 className="mr-2 size-4" />
                          重新索引
                        </Button>
                      </div>
                    </div>
                  ))}
                </div>
              ) : (
                <EmptyState
                  title="还没有文件"
                  description="上传文件后，这里会展示文件列表、状态以及单文件索引入口。"
                />
              )}
            </CardContent>
          </Card>
        </TabsContent>
        <TabsContent value="retrieve">
          <Card>
            <CardHeader>
              <CardTitle>检索调试</CardTitle>
              <CardDescription>直接调用 `POST /v1/knowledge-bases/retrieve` 查看检索结果。</CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <Textarea
                rows={4}
                value={retrieveQuery}
                onChange={(event) => setRetrieveQuery(event.target.value)}
                placeholder="例如：总结这套系统里的 AgentConfig 与 Session 的关系"
              />
              <div className="flex justify-end">
                <Button onClick={handleRetrieve} disabled={retrieve.isPending}>
                  {retrieve.isPending ? "检索中..." : "执行检索"}
                </Button>
              </div>
              {retrieve.data ? (
                <div className="space-y-3">
                  {retrieve.data.results.map((result) => (
                    <div key={result.chunk_id} className="rounded-2xl border border-slate-200 p-4">
                      <div className="flex items-center justify-between gap-3">
                        <p className="text-sm font-medium text-slate-950">{result.chunk_id}</p>
                        <p className="text-sm text-sky-600">score {result.score.toFixed(4)}</p>
                      </div>
                      <p className="mt-3 text-sm leading-6 text-slate-500">{result.content}</p>
                    </div>
                  ))}
                </div>
              ) : (
                <p className="text-sm text-slate-500">
                  这一页用于验证稠密/稀疏/Rerank 组合后的检索体验。
                </p>
              )}
            </CardContent>
          </Card>
        </TabsContent>
        <TabsContent value="chat">
          <Card>
            <CardHeader>
              <CardTitle>RAG Chat</CardTitle>
              <CardDescription>使用 `POST /v1/knowledge-bases/rag` 进行知识库问答。</CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="space-y-2">
                <p className="text-sm font-medium text-slate-950">选择 Chat Model（可选）</p>
                <select
                  className="flex h-10 w-full rounded-xl border border-slate-200 bg-white px-3 text-sm outline-none focus:ring-2 focus:ring-sky-500"
                  value={selectedModelId}
                  onChange={(event) => setSelectedModelId(event.target.value)}
                >
                  <option value="">使用后端默认模型</option>
                  {chatModels.data?.map((model) => (
                    <option key={model.id} value={model.id}>
                      {model.name}
                    </option>
                  ))}
                </select>
              </div>
              <Textarea
                rows={5}
                value={chatQuery}
                onChange={(event) => setChatQuery(event.target.value)}
                placeholder="基于当前知识库回答：这个系统中的 Agent 模块是如何组织的？"
              />
              <div className="flex justify-end">
                <Button onClick={handleChat} disabled={chat.isPending}>
                  {chat.isPending ? "生成中..." : "开始问答"}
                </Button>
              </div>
              {chat.data ? (
                <div className="space-y-4 rounded-3xl bg-slate-50 p-5">
                  <div>
                    <p className="text-xs font-semibold uppercase tracking-[0.22em] text-sky-600">
                      回答
                    </p>
                    <p className="mt-3 whitespace-pre-wrap text-sm leading-7 text-slate-700">
                      {chat.data.answer}
                    </p>
                  </div>
                  <div className="space-y-3">
                    <p className="text-sm font-medium text-slate-950">引用片段</p>
                    {chat.data.results.map((result) => (
                      <div key={result.chunk_id} className="rounded-2xl border border-slate-200 bg-white p-4">
                        <p className="text-xs text-slate-400">{result.chunk_id}</p>
                        <p className="mt-2 text-sm leading-6 text-slate-600">{result.content}</p>
                      </div>
                    ))}
                  </div>
                </div>
              ) : (
                <p className="text-sm text-slate-500">
                  第一版默认以当前详情页知识库为主，同时支持扩展到多 KB 问答。
                </p>
              )}
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>
    </div>
  );
}
