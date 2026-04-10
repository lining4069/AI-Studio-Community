import { zodResolver } from "@hookform/resolvers/zod";
import { useEffect } from "react";
import { useForm } from "react-hook-form";

import { useUpdateKnowledgeBase } from "@/api/endpoints/knowledge-base";
import type {
  EmbeddingModelResponse,
  KbDocumentResponse,
  RerankModelResponse,
} from "@/api/types";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { getErrorMessage } from "@/lib/data";
import {
  knowledgeBaseOverviewSchema,
  type KnowledgeBaseOverviewSchema,
} from "@/lib/validators/knowledge-base";
import { formatDate } from "@/lib/utils";

type OverviewFormProps = {
  kbId?: string;
  detail: KbDocumentResponse;
  embeddingModels: EmbeddingModelResponse[];
  rerankModels: RerankModelResponse[];
};

export function KnowledgeBaseOverviewForm({
  kbId,
  detail,
  embeddingModels,
  rerankModels,
}: OverviewFormProps) {
  const updateKnowledgeBase = useUpdateKnowledgeBase(kbId);
  const form = useForm<KnowledgeBaseOverviewSchema>({
    resolver: zodResolver(knowledgeBaseOverviewSchema),
    defaultValues: {
      name: detail.name,
      description: detail.description ?? "",
      embedding_model_id: detail.embedding_model_id ?? "",
      rerank_model_id: detail.rerank_model_id ?? "",
      chunk_size: detail.chunk_size,
      chunk_overlap: detail.chunk_overlap,
      top_k: detail.top_k,
      similarity_threshold: detail.similarity_threshold,
      vector_weight: detail.vector_weight,
      enable_rerank: detail.enable_rerank,
      rerank_top_k: detail.rerank_top_k,
    },
  });

  useEffect(() => {
    form.reset({
      name: detail.name,
      description: detail.description ?? "",
      embedding_model_id: detail.embedding_model_id ?? "",
      rerank_model_id: detail.rerank_model_id ?? "",
      chunk_size: detail.chunk_size,
      chunk_overlap: detail.chunk_overlap,
      top_k: detail.top_k,
      similarity_threshold: detail.similarity_threshold,
      vector_weight: detail.vector_weight,
      enable_rerank: detail.enable_rerank,
      rerank_top_k: detail.rerank_top_k,
    });
  }, [detail, form]);

  const onSubmit = form.handleSubmit(async (values) => {
    await updateKnowledgeBase.mutateAsync({
      name: values.name,
      description: values.description || undefined,
      embedding_model_id: values.embedding_model_id || undefined,
      rerank_model_id: values.rerank_model_id || undefined,
      chunk_size: values.chunk_size,
      chunk_overlap: values.chunk_overlap,
      top_k: values.top_k,
      similarity_threshold: values.similarity_threshold,
      vector_weight: values.vector_weight,
      enable_rerank: values.enable_rerank,
      rerank_top_k: values.rerank_top_k,
    });
  });

  const embeddingModelName =
    embeddingModels.find((model) => model.id === detail.embedding_model_id)?.name ??
    "系统默认";
  const rerankModelName =
    rerankModels.find((model) => model.id === detail.rerank_model_id)?.name ??
    "系统默认";
  const rerankSummary = detail.enable_rerank
    ? `已启用 · ${rerankModelName}`
    : "未启用";
  const chunkAndRetrieveSummary = `${detail.chunk_size} 字 / 重叠 ${detail.chunk_overlap} / Top ${detail.top_k}`;

  return (
    <div className="grid gap-6 xl:grid-cols-[1.15fr_0.85fr]">
      <Card className="border-slate-200/80 shadow-sm">
        <CardHeader>
          <CardTitle>知识库配置</CardTitle>
          <CardDescription>
            在同一个工作台里维护基础信息、切片参数和默认检索配置，保存后即可继续到
            Retrieve / Chat 验证效果。
          </CardDescription>
        </CardHeader>
        <CardContent>
          <form className="space-y-5" onSubmit={onSubmit}>
            <div className="grid gap-4 md:grid-cols-2">
              <div className="space-y-2 md:col-span-2">
                <Label htmlFor="kb-detail-name">知识库名称</Label>
                <Input id="kb-detail-name" {...form.register("name")} />
              </div>
              <div className="space-y-2 md:col-span-2">
                <Label htmlFor="kb-detail-description">知识库描述</Label>
                <Textarea
                  id="kb-detail-description"
                  rows={4}
                  {...form.register("description")}
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="kb-detail-embedding-model">Embedding Model</Label>
                <select
                  id="kb-detail-embedding-model"
                  className="flex h-10 w-full rounded-xl border border-slate-200 bg-white px-3 text-sm outline-none focus:ring-2 focus:ring-sky-500"
                  {...form.register("embedding_model_id")}
                >
                  <option value="">使用系统默认</option>
                  {embeddingModels.map((model) => (
                    <option key={model.id} value={model.id}>
                      {model.name}
                    </option>
                  ))}
                </select>
              </div>
              <div className="space-y-2">
                <Label htmlFor="kb-detail-rerank-model">Rerank Model</Label>
                <select
                  id="kb-detail-rerank-model"
                  className="flex h-10 w-full rounded-xl border border-slate-200 bg-white px-3 text-sm outline-none focus:ring-2 focus:ring-sky-500"
                  {...form.register("rerank_model_id")}
                >
                  <option value="">使用系统默认</option>
                  {rerankModels.map((model) => (
                    <option key={model.id} value={model.id}>
                      {model.name}
                    </option>
                  ))}
                </select>
              </div>
            </div>

            <div className="rounded-3xl border border-slate-200 bg-slate-50/70 p-4">
              <p className="text-sm font-medium text-slate-950">切片与召回参数</p>
              <div className="mt-4 grid gap-4 md:grid-cols-2">
                <div className="space-y-2">
                  <Label htmlFor="kb-detail-chunk-size">Chunk Size</Label>
                  <Input
                    id="kb-detail-chunk-size"
                    type="number"
                    min={100}
                    max={4000}
                    {...form.register("chunk_size")}
                  />
                </div>
                <div className="space-y-2">
                  <Label htmlFor="kb-detail-chunk-overlap">Chunk Overlap</Label>
                  <Input
                    id="kb-detail-chunk-overlap"
                    type="number"
                    min={0}
                    max={1000}
                    {...form.register("chunk_overlap")}
                  />
                </div>
                <div className="space-y-2">
                  <Label htmlFor="kb-detail-top-k">Top K</Label>
                  <Input
                    id="kb-detail-top-k"
                    type="number"
                    min={1}
                    max={20}
                    {...form.register("top_k")}
                  />
                </div>
                <div className="space-y-2">
                  <Label htmlFor="kb-detail-rerank-top-k">Rerank Top K</Label>
                  <Input
                    id="kb-detail-rerank-top-k"
                    type="number"
                    min={1}
                    max={20}
                    {...form.register("rerank_top_k")}
                  />
                </div>
                <div className="space-y-2">
                  <Label htmlFor="kb-detail-similarity-threshold">
                    Similarity Threshold
                  </Label>
                  <Input
                    id="kb-detail-similarity-threshold"
                    type="number"
                    min={0}
                    max={1}
                    step="0.01"
                    {...form.register("similarity_threshold")}
                  />
                </div>
                <div className="space-y-2">
                  <Label htmlFor="kb-detail-vector-weight">Vector Weight</Label>
                  <Input
                    id="kb-detail-vector-weight"
                    type="number"
                    min={0}
                    max={1}
                    step="0.05"
                    {...form.register("vector_weight")}
                  />
                </div>
              </div>
            </div>

            <label className="flex items-center gap-3 rounded-2xl border border-slate-200 px-4 py-3 text-sm text-slate-600">
              <input
                type="checkbox"
                className="size-4 rounded border-slate-300 text-sky-600 focus:ring-sky-500"
                {...form.register("enable_rerank")}
              />
              启用 Rerank，优先对召回结果进行二次排序
            </label>

            {updateKnowledgeBase.error ? (
              <p className="rounded-2xl bg-rose-50 px-3 py-2 text-sm text-rose-600">
                {getErrorMessage(updateKnowledgeBase.error)}
              </p>
            ) : null}

            <div className="flex justify-end">
              <Button type="submit" disabled={updateKnowledgeBase.isPending}>
                {updateKnowledgeBase.isPending ? "保存中..." : "保存配置"}
              </Button>
            </div>
          </form>
        </CardContent>
      </Card>

      <div className="space-y-6">
        <Card className="overflow-hidden border-slate-200/80 bg-[linear-gradient(145deg,#0f172a_0%,#115e59_48%,#f3fbff_100%)] text-white shadow-sm">
          <CardHeader>
            <CardTitle className="text-white">当前工作台摘要</CardTitle>
            <CardDescription className="text-white/75">
              让配置、检索和问答在同一上下文中闭环。
            </CardDescription>
          </CardHeader>
          <CardContent className="grid gap-3 sm:grid-cols-2">
            {[
              ["更新时间", formatDate(detail.updated_at)],
              ["Embedding 模型", embeddingModelName],
              ["Rerank 策略", rerankSummary],
              ["切片与召回", chunkAndRetrieveSummary],
            ].map(([label, value]) => (
              <div
                key={label}
                className="rounded-2xl border border-white/15 bg-white/10 p-4 backdrop-blur"
              >
                <p className="text-xs uppercase tracking-[0.22em] text-white/70">
                  {label}
                </p>
                <p className="mt-3 text-sm font-medium text-white">{value}</p>
              </div>
            ))}
          </CardContent>
        </Card>

        <Card className="border-slate-200/80 shadow-sm">
          <CardHeader>
            <CardTitle>使用建议</CardTitle>
            <CardDescription>
              配置完成后，建议继续进入 Retrieve 与 Chat 验证检索召回和回答效果。
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-3 text-sm leading-6 text-slate-500">
            <div className="rounded-2xl bg-slate-50 p-4">
              <p className="font-medium text-slate-950">1. 先看 Retrieve</p>
              <p className="mt-2">
                调整 chunk 和召回参数后，优先验证返回片段是否准确命中。
              </p>
            </div>
            <div className="rounded-2xl bg-slate-50 p-4">
              <p className="font-medium text-slate-950">2. 再看 Chat</p>
              <p className="mt-2">
                在问答页验证回答是否稳定、是否引用到了正确知识上下文。
              </p>
            </div>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
