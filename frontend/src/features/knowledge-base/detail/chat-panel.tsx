import { Bot, MessagesSquare, Sparkles } from "lucide-react";
import { useState } from "react";

import { useKnowledgeBaseChat } from "@/api/endpoints/knowledge-base";
import type { LlmModelResponse } from "@/api/types";
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

type ChatTurn = {
  question: string;
  answer: string;
  results: {
    chunk_id: string;
    score: number;
    content: string;
  }[];
};

type ChatPanelProps = {
  kbId?: string;
  kbName: string;
  chatModels: LlmModelResponse[];
};

export function KnowledgeBaseChatPanel({
  kbId,
  kbName,
  chatModels,
}: ChatPanelProps) {
  const [chatQuery, setChatQuery] = useState("");
  const [selectedModelId, setSelectedModelId] = useState("");
  const [turns, setTurns] = useState<ChatTurn[]>([]);
  const chat = useKnowledgeBaseChat();

  const handleChat = async () => {
    if (!kbId || !chatQuery.trim()) {
      return;
    }

    const question = chatQuery.trim();
    const response = await chat.mutateAsync({
      query: question,
      kb_ids: [kbId],
      llm_model_id: selectedModelId || undefined,
    });

    setTurns((current) => [
      ...current,
      {
        question,
        answer: response.answer,
        results: response.results,
      },
    ]);
    setChatQuery("");
  };

  return (
    <div className="grid gap-6 xl:grid-cols-[1.12fr_0.88fr]">
      <Card className="border-slate-200/80 shadow-sm">
        <CardHeader>
          <CardTitle>知识库问答</CardTitle>
          <CardDescription>
            让当前知识库直接回答问题，验证最终用户看到的真实效果。
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="rounded-3xl bg-[linear-gradient(145deg,#0f172a_0%,#155e75_52%,#f3fbff_100%)] p-5 text-white shadow-sm">
            <p className="text-xs font-semibold uppercase tracking-[0.24em] text-white/70">
              当前工作区
            </p>
            <p className="mt-3 text-xl font-semibold">{kbName}</p>
            <p className="mt-2 text-sm leading-6 text-white/80">
              先通过问答验证知识库回答是否稳定，再回到 Retrieve 调整召回效果。
            </p>
          </div>

          <div className="space-y-2">
            <p className="text-sm font-medium text-slate-950">选择 Chat Model（可选）</p>
            <select
              className="flex h-10 w-full rounded-xl border border-slate-200 bg-white px-3 text-sm outline-none focus:ring-2 focus:ring-sky-500"
              value={selectedModelId}
              onChange={(event) => setSelectedModelId(event.target.value)}
            >
              <option value="">使用后端默认模型</option>
              {chatModels.map((model) => (
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
          {chat.error ? (
            <p className="rounded-2xl bg-rose-50 px-3 py-2 text-sm text-rose-600">
              {getErrorMessage(chat.error)}
            </p>
          ) : null}
          <div className="flex justify-end">
            <Button onClick={handleChat} disabled={chat.isPending}>
              <Sparkles className="mr-2 size-4" />
              {chat.isPending ? "生成中..." : "开始问答"}
            </Button>
          </div>
        </CardContent>
      </Card>

      <div className="space-y-6">
        <Card className="border-slate-200/80 shadow-sm">
          <CardHeader>
            <CardTitle>问答记录</CardTitle>
            <CardDescription>
              当前以单知识库问答为主，后续可扩展到多知识库对话。
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            {turns.length ? (
              turns.map((turn, index) => (
                <div key={`${turn.question}-${index}`} className="space-y-4">
                  <div className="rounded-3xl border border-slate-200 bg-white p-5 shadow-sm">
                    <div className="flex items-center gap-3">
                      <div className="flex size-10 items-center justify-center rounded-2xl bg-slate-100 text-slate-700">
                        <MessagesSquare className="size-5" />
                      </div>
                      <div>
                        <p className="text-xs font-semibold uppercase tracking-[0.22em] text-sky-600">
                          用户问题
                        </p>
                        <p className="mt-1 text-sm font-medium text-slate-950">
                          {turn.question}
                        </p>
                      </div>
                    </div>
                  </div>

                  <div className="rounded-3xl border border-sky-100 bg-sky-50/50 p-5 shadow-sm">
                    <div className="flex items-center gap-3">
                      <div className="flex size-10 items-center justify-center rounded-2xl bg-sky-100 text-sky-700">
                        <Bot className="size-5" />
                      </div>
                      <div>
                        <p className="text-xs font-semibold uppercase tracking-[0.22em] text-sky-600">
                          助手回答
                        </p>
                      </div>
                    </div>
                    <p className="mt-4 whitespace-pre-wrap text-sm leading-7 text-slate-700">
                      {turn.answer}
                    </p>
                    {turn.results.length ? (
                      <div className="mt-5 space-y-3">
                        {turn.results.map((result, resultIndex) => (
                          <div
                            key={result.chunk_id}
                            className="rounded-2xl border border-white/80 bg-white/90 p-4"
                          >
                            <div className="flex flex-wrap items-center justify-between gap-3">
                              <p className="text-xs font-semibold uppercase tracking-[0.2em] text-slate-500">
                                引用片段 {resultIndex + 1}
                              </p>
                              <p className="text-sm font-medium text-sky-700">
                                相关度 {result.score.toFixed(4)}
                              </p>
                            </div>
                            <p className="mt-3 text-sm leading-6 text-slate-600">
                              {result.content}
                            </p>
                          </div>
                        ))}
                      </div>
                    ) : null}
                  </div>
                </div>
              ))
            ) : (
              <div className="rounded-3xl border border-dashed border-slate-300 bg-slate-50/80 p-6 text-sm leading-6 text-slate-500">
                还没有问答记录。先提出一个与当前知识库内容强相关的问题，查看回答和引用片段是否可靠。
              </div>
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
