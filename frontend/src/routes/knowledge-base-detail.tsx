import { useState } from "react";
import { Upload, Wand2 } from "lucide-react";
import { useParams } from "react-router-dom";

import {
  useIndexKnowledgeBaseFile,
  useKnowledgeBaseDetail,
  useKnowledgeBaseFiles,
  useUploadKnowledgeBaseFile,
} from "@/api/endpoints/knowledge-base";
import {
  useChatModels,
  useEmbeddingModels,
  useRerankModels,
} from "@/api/endpoints/settings";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Button } from "@/components/ui/button";
import { SectionHeading } from "@/components/shared/section-heading";
import { EmptyState } from "@/components/shared/empty-state";
import { KnowledgeBaseChatPanel } from "@/features/knowledge-base/detail/chat-panel";
import { KnowledgeBaseOverviewForm } from "@/features/knowledge-base/detail/overview-form";
import { KnowledgeBaseRetrievePanel } from "@/features/knowledge-base/detail/retrieve-panel";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { formatDate } from "@/lib/utils";

export function KnowledgeBaseDetailRoute() {
  const { kbId } = useParams();
  const [selectedFile, setSelectedFile] = useState<File | null>(null);

  const detail = useKnowledgeBaseDetail(kbId);
  const files = useKnowledgeBaseFiles(kbId);
  const uploadFile = useUploadKnowledgeBaseFile(kbId);
  const indexFile = useIndexKnowledgeBaseFile(kbId);
  const chatModels = useChatModels();
  const embeddingModels = useEmbeddingModels();
  const rerankModels = useRerankModels();

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
          {detail.data ? (
            <KnowledgeBaseOverviewForm
              kbId={kbId}
              detail={detail.data}
              embeddingModels={embeddingModels.data ?? []}
              rerankModels={rerankModels.data ?? []}
            />
          ) : null}
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
          {detail.data ? (
            <KnowledgeBaseRetrievePanel kbId={kbId} topK={detail.data.top_k} />
          ) : null}
        </TabsContent>
        <TabsContent value="chat">
          {detail.data ? (
            <KnowledgeBaseChatPanel
              kbId={kbId}
              kbName={detail.data.name}
              chatModels={chatModels.data ?? []}
            />
          ) : null}
        </TabsContent>
      </Tabs>
    </div>
  );
}
