import { zodResolver } from "@hookform/resolvers/zod";
import { useForm } from "react-hook-form";
import { z } from "zod";

import { useCreateAgentConfig } from "@/api/endpoints/agent";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { getErrorMessage } from "@/lib/data";
import { createAgentSchema } from "@/lib/validators/agent";

type CreateAgentFormProps = {
  onSuccess?: () => void;
};

export function CreateAgentForm({ onSuccess }: CreateAgentFormProps) {
  const createAgent = useCreateAgentConfig();
  const form = useForm<
    z.input<typeof createAgentSchema>,
    unknown,
    z.output<typeof createAgentSchema>
  >({
    resolver: zodResolver(createAgentSchema),
    defaultValues: {
      name: "",
      description: "",
      llm_model_id: "",
      agent_type: "simple",
      max_loop: 5,
      system_prompt: "",
      enabled: true,
    },
  });

  const onSubmit = form.handleSubmit(async (values) => {
    await createAgent.mutateAsync({
      name: values.name,
      description: values.description || undefined,
      llm_model_id: values.llm_model_id || undefined,
      agent_type: values.agent_type,
      max_loop: values.max_loop,
      system_prompt: values.system_prompt || undefined,
      enabled: values.enabled,
    });

    form.reset();
    onSuccess?.();
  });

  return (
    <form className="space-y-4" onSubmit={onSubmit}>
      <div className="space-y-2">
        <Label htmlFor="agent-name">助手名称</Label>
        <Input id="agent-name" {...form.register("name")} />
      </div>
      <div className="space-y-2">
        <Label htmlFor="agent-description">描述</Label>
        <Textarea id="agent-description" rows={3} {...form.register("description")} />
      </div>
      <div className="grid gap-4 md:grid-cols-2">
        <div className="space-y-2">
          <Label htmlFor="agent-type">Agent 类型</Label>
          <select
            id="agent-type"
            className="flex h-10 w-full rounded-xl border border-slate-200 bg-white px-3 text-sm outline-none focus:ring-2 focus:ring-sky-500"
            {...form.register("agent_type")}
          >
            <option value="simple">simple</option>
            <option value="react">react</option>
          </select>
        </div>
        <div className="space-y-2">
          <Label htmlFor="agent-max-loop">Max Loop</Label>
          <Input
            id="agent-max-loop"
            type="number"
            min={1}
            max={20}
            {...form.register("max_loop", { valueAsNumber: true })}
          />
        </div>
      </div>
      <div className="space-y-2">
        <Label htmlFor="agent-prompt">System Prompt</Label>
        <Textarea id="agent-prompt" rows={5} {...form.register("system_prompt")} />
      </div>
      {createAgent.error ? (
        <p className="rounded-2xl bg-rose-50 px-3 py-2 text-sm text-rose-600">
          {getErrorMessage(createAgent.error)}
        </p>
      ) : null}
      <Button type="submit" disabled={createAgent.isPending}>
        {createAgent.isPending ? "创建中..." : "创建助手"}
      </Button>
    </form>
  );
}
