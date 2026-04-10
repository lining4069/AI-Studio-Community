import { SearchCheck } from "lucide-react";
import { useState } from "react";

import { useRetrieveKnowledgeBase } from "@/api/endpoints/knowledge-base";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Textarea } from "@/components/ui/textarea";
import { getErrorMessage } from "@/lib/data";

type RetrievePanelProps = {
  kbId?: string;
  topK: number;
};

export function KnowledgeBaseRetrievePanel({
  kbId,
  topK,
}: RetrievePanelProps) {
  const [retrieveQuery, setRetrieveQuery] = useState("");
  const [results, setResults] = useState<
    {
      chunk_id: string;
      score: number;
      content: string;
    }[]
  >([]);
  const retrieve = useRetrieveKnowledgeBase();

  const handleRetrieve = async () => {
    if (!kbId || !retrieveQuery.trim()) {
      return;
    }

    const response = await retrieve.mutateAsync({
      query: retrieveQuery,
      kb_ids: [kbId],
    });
    setResults(response.results);
  };

  return (
    <div className="grid gap-6 xl:grid-cols-[0.92fr_1.08fr]">
      <Card className="border-slate-200/80 shadow-sm">
        <CardHeader>
          <CardTitle>检索调试</CardTitle>
          <CardDescription>
            先验证召回片段是否准确，再进入 Chat 检查最终回答质量。
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="rounded-2xl bg-slate-50 p-4 text-sm leading-6 text-slate-500">
            当前知识库默认会使用 <span className="font-medium text-slate-950">Top K {topK}</span>{" "}
            作为召回数量。建议使用接近用户真实问题的表达来验证结果质量。
          </div>
          <Textarea
            rows={6}
            value={retrieveQuery}
            onChange={(event) => setRetrieveQuery(event.target.value)}
            placeholder="例如：总结这套系统里的 AgentConfig 与 Session 的关系"
          />
          {retrieve.error ? (
            <p className="rounded-2xl bg-rose-50 px-3 py-2 text-sm text-rose-600">
              {getErrorMessage(retrieve.error)}
            </p>
          ) : null}
          <div className="flex justify-end">
            <Button onClick={handleRetrieve} disabled={retrieve.isPending}>
              <SearchCheck className="mr-2 size-4" />
              {retrieve.isPending ? "检索中..." : "执行检索"}
            </Button>
          </div>
        </CardContent>
      </Card>

      <Card className="border-slate-200/80 shadow-sm">
        <CardHeader>
          <CardTitle>命中结果</CardTitle>
          <CardDescription>
            关注片段是否贴题、得分是否合理、内容是否足以支撑后续问答。
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          {results.length ? (
            results.map((result, index) => (
              <div
                key={result.chunk_id}
                className="rounded-3xl border border-slate-200 bg-[linear-gradient(180deg,#ffffff_0%,#f8fbff_100%)] p-5 shadow-sm"
              >
                <div className="flex flex-wrap items-center justify-between gap-3">
                  <div>
                    <p className="text-xs font-semibold uppercase tracking-[0.22em] text-sky-600">
                      命中片段 {index + 1}
                    </p>
                    <p className="mt-2 text-sm font-medium text-slate-950">
                      {result.chunk_id}
                    </p>
                  </div>
                  <div className="rounded-full bg-sky-50 px-3 py-1 text-sm font-medium text-sky-700">
                    相关度 {result.score.toFixed(4)}
                  </div>
                </div>
                <p className="mt-4 whitespace-pre-wrap text-sm leading-7 text-slate-600">
                  {result.content}
                </p>
              </div>
            ))
          ) : (
            <div className="rounded-3xl border border-dashed border-slate-300 bg-slate-50/80 p-6 text-sm leading-6 text-slate-500">
              还没有检索结果。先输入一个问题并执行检索，看看当前切片和召回参数是否能命中正确内容。
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
