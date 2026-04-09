import { Database, FilePlus2 } from "lucide-react";
import { useState } from "react";
import { Link } from "react-router-dom";

import { useKnowledgeBases } from "@/api/endpoints/knowledge-base";
import { EmptyState } from "@/components/shared/empty-state";
import { SectionHeading } from "@/components/shared/section-heading";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import { CreateKnowledgeBaseForm } from "@/features/knowledge-base/create-knowledge-base-form";
import { formatDate } from "@/lib/utils";

export function KnowledgeBasesRoute() {
  const [open, setOpen] = useState(false);
  const knowledgeBases = useKnowledgeBases();

  return (
    <div className="space-y-8">
      <SectionHeading
        eyebrow="Knowledge Base"
        title="知识库"
        description="知识库模块会围绕列表管理、文件索引、检索调试与 RAG Chat 构建完整闭环。"
        actions={
          <Dialog open={open} onOpenChange={setOpen}>
            <DialogTrigger asChild>
              <Button>
                <FilePlus2 className="mr-2 size-4" />
                新建知识库
              </Button>
            </DialogTrigger>
            <DialogContent>
              <DialogHeader>
                <DialogTitle>创建知识库</DialogTitle>
                <DialogDescription>
                  第一版先用推荐默认参数创建知识库，后续再进入详情页做检索与聊天验证。
                </DialogDescription>
              </DialogHeader>
              <CreateKnowledgeBaseForm onSuccess={() => setOpen(false)} />
            </DialogContent>
          </Dialog>
        }
      />

      {knowledgeBases.data?.items.length ? (
        <div className="grid gap-5 xl:grid-cols-3">
          {knowledgeBases.data.items.map((item) => (
            <Link key={item.id} to={`/knowledge-bases/${item.id}`}>
              <Card className="h-full transition hover:-translate-y-0.5 hover:border-emerald-200 hover:shadow-md">
                <CardHeader>
                  <div className="flex items-start justify-between gap-3">
                    <div className="flex size-12 items-center justify-center rounded-2xl bg-emerald-50 text-emerald-600">
                      <Database className="size-6" />
                    </div>
                    <Badge>{item.is_active ? "已启用" : "未启用"}</Badge>
                  </div>
                  <CardTitle className="mt-4">{item.name}</CardTitle>
                  <CardDescription>
                    {item.description || "这个知识库还没有填写描述。"}
                  </CardDescription>
                </CardHeader>
                <CardContent className="space-y-2 text-sm text-slate-500">
                  <p>Top K：{item.top_k}</p>
                  <p>Rerank：{item.enable_rerank ? "开启" : "关闭"}</p>
                  <p>更新时间：{formatDate(item.updated_at)}</p>
                </CardContent>
              </Card>
            </Link>
          ))}
        </div>
      ) : (
        <EmptyState
          title="还没有知识库"
          description="先创建知识库，再进入详情页完成文件上传、检索调试与 RAG Chat。"
          action={
            <Button onClick={() => setOpen(true)}>
              <FilePlus2 className="mr-2 size-4" />
              现在创建
            </Button>
          }
        />
      )}
    </div>
  );
}
