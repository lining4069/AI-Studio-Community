import { zodResolver } from "@hookform/resolvers/zod";
import { useForm } from "react-hook-form";

import { useCreateKnowledgeBase } from "@/api/endpoints/knowledge-base";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { getErrorMessage } from "@/lib/data";
import {
  createKnowledgeBaseSchema,
  type CreateKnowledgeBaseSchema,
} from "@/lib/validators/knowledge-base";

type CreateKnowledgeBaseFormProps = {
  onSuccess?: () => void;
};

export function CreateKnowledgeBaseForm({ onSuccess }: CreateKnowledgeBaseFormProps) {
  const createKnowledgeBase = useCreateKnowledgeBase();
  const form = useForm<CreateKnowledgeBaseSchema>({
    resolver: zodResolver(createKnowledgeBaseSchema),
    defaultValues: {
      name: "",
      description: "",
      embedding_model_id: "",
      rerank_model_id: "",
    },
  });

  const onSubmit = form.handleSubmit(async (values) => {
    await createKnowledgeBase.mutateAsync({
      name: values.name,
      description: values.description || undefined,
      embedding_model_id: values.embedding_model_id || undefined,
      rerank_model_id: values.rerank_model_id || undefined,
      chunk_size: 512,
      chunk_overlap: 50,
      top_k: 5,
      similarity_threshold: 0,
      vector_weight: 0.7,
      enable_rerank: true,
      rerank_top_k: 3,
    });

    form.reset();
    onSuccess?.();
  });

  return (
    <form className="space-y-4" onSubmit={onSubmit}>
      <div className="space-y-2">
        <Label htmlFor="kb-name">知识库名称</Label>
        <Input id="kb-name" {...form.register("name")} />
      </div>
      <div className="space-y-2">
        <Label htmlFor="kb-description">描述</Label>
        <Textarea id="kb-description" rows={4} {...form.register("description")} />
      </div>
      {createKnowledgeBase.error ? (
        <p className="rounded-2xl bg-rose-50 px-3 py-2 text-sm text-rose-600">
          {getErrorMessage(createKnowledgeBase.error)}
        </p>
      ) : null}
      <Button type="submit" disabled={createKnowledgeBase.isPending}>
        {createKnowledgeBase.isPending ? "创建中..." : "创建知识库"}
      </Button>
    </form>
  );
}
