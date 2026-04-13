import { zodResolver } from "@hookform/resolvers/zod";
import { useForm } from "react-hook-form";
import { z } from "zod";

import {
  type AgentMCPServerResponse,
  type EmbeddingModelResponse,
  type LlmModelResponse,
  type RerankModelResponse,
  useCreateChatModel,
  useCreateEmbeddingModel,
  useCreateMcpServer,
  useCreateRerankModel,
  useUpdateChatModel,
  useUpdateEmbeddingModel,
  useUpdateMcpServer,
  useUpdateRerankModel,
} from "@/api/endpoints/settings";
import { useUpdateUserProfile } from "@/api/endpoints/user";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import {
  getErrorMessage,
  parseKeyValueText,
  parseLines,
  stringifyKeyValueText,
  stringifyLines,
} from "@/lib/data";
import {
  chatModelSchema,
  embeddingModelSchema,
  mcpServerSchema,
  profileSchema,
  rerankModelSchema,
  type ChatModelSchema,
  type McpServerSchema,
  type ProfileSchema,
  type RerankModelSchema,
} from "@/lib/validators/settings";

type BaseFormProps = {
  onSuccess?: () => void;
};

type FormMode = "create" | "edit";

export function ProfileForm({
  initialValues,
}: {
  initialValues?: Partial<ProfileSchema>;
}) {
  const updateProfile = useUpdateUserProfile();
  const form = useForm<ProfileSchema>({
    resolver: zodResolver(profileSchema),
    values: {
      nickname: initialValues?.nickname ?? "",
      email: initialValues?.email ?? "",
      bio: initialValues?.bio ?? "",
    },
  });

  const onSubmit = form.handleSubmit(async (values) => {
    await updateProfile.mutateAsync({
      nickname: values.nickname || undefined,
      email: values.email || undefined,
      bio: values.bio || undefined,
    });
  });

  return (
    <form className="space-y-4" onSubmit={onSubmit}>
      <div className="grid gap-4 md:grid-cols-2">
        <div className="space-y-2">
          <Label htmlFor="profile-nickname">昵称</Label>
          <Input id="profile-nickname" {...form.register("nickname")} />
        </div>
        <div className="space-y-2">
          <Label htmlFor="profile-email">邮箱</Label>
          <Input id="profile-email" type="email" {...form.register("email")} />
        </div>
      </div>
      <div className="space-y-2">
        <Label htmlFor="profile-bio">简介</Label>
        <Textarea id="profile-bio" rows={4} {...form.register("bio")} />
      </div>
      {updateProfile.error ? (
        <p className="rounded-2xl bg-rose-50 px-3 py-2 text-sm text-rose-600">
          {getErrorMessage(updateProfile.error)}
        </p>
      ) : null}
      <Button type="submit" disabled={updateProfile.isPending}>
        {updateProfile.isPending ? "保存中..." : "保存账户信息"}
      </Button>
    </form>
  );
}

export function McpServerForm({
  onSuccess,
  mode = "create",
  server,
}: BaseFormProps & {
  mode?: FormMode;
  server?: Partial<AgentMCPServerResponse> | null;
}) {
  const createMcp = useCreateMcpServer();
  const updateMcp = useUpdateMcpServer(server?.id);
  const form = useForm<McpServerSchema>({
    resolver: zodResolver(mcpServerSchema),
    values: {
      name: server?.name ?? "",
      transport: server?.transport ?? "streamable_http",
      url: server?.url ?? "",
      command: server?.command ?? "",
      argsText: stringifyLines(server?.args),
      headersText: stringifyKeyValueText(server?.headers as Record<string, unknown> | null | undefined),
      envText: stringifyKeyValueText(server?.env),
      cwd: server?.cwd ?? "",
    },
  });
  const transport = form.watch("transport");
  const usesUrlFields = transport === "streamable_http" || transport === "sse";
  const usesCommandFields = transport === "stdio";

  const onSubmit = form.handleSubmit(async (values) => {
    const payload = {
      name: values.name,
      transport: values.transport,
      url: values.url || undefined,
      command: values.command || undefined,
      args: parseLines(values.argsText ?? ""),
      headers: parseKeyValueText(values.headersText ?? ""),
      env: parseKeyValueText(values.envText ?? ""),
      cwd: values.cwd || undefined,
      enabled: server?.enabled ?? true,
    };

    if (mode === "edit" && server?.id) {
      await updateMcp.mutateAsync(payload);
    } else {
      await createMcp.mutateAsync(payload);
      form.reset();
    }
    onSuccess?.();
  });

  const mutation = mode === "edit" ? updateMcp : createMcp;

  return (
    <form className="space-y-4" onSubmit={onSubmit}>
      <div className="grid gap-4 md:grid-cols-2">
        <div className="space-y-2">
          <Label htmlFor="mcp-name">名称</Label>
          <Input id="mcp-name" {...form.register("name")} />
        </div>
        <div className="space-y-2">
          <Label htmlFor="mcp-transport">Transport</Label>
          <select
            id="mcp-transport"
            className="flex h-10 w-full rounded-xl border border-slate-200 bg-white px-3 text-sm outline-none focus:ring-2 focus:ring-sky-500"
            {...form.register("transport")}
          >
            <option value="streamable_http">streamable_http</option>
            <option value="stdio">stdio</option>
            <option value="sse">sse</option>
          </select>
        </div>
      </div>
      {usesUrlFields ? (
        <div className="space-y-2">
          <Label htmlFor="mcp-url">URL</Label>
          <Input id="mcp-url" placeholder="https://..." {...form.register("url")} />
        </div>
      ) : null}
      {usesCommandFields ? (
        <>
          <div className="grid gap-4 md:grid-cols-2">
            <div className="space-y-2">
              <Label htmlFor="mcp-command">Command</Label>
              <Input
                id="mcp-command"
                placeholder="uvx / npx / python"
                {...form.register("command")}
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="mcp-cwd">CWD</Label>
              <Input id="mcp-cwd" placeholder="/abs/path" {...form.register("cwd")} />
            </div>
          </div>
          <div className="space-y-2">
            <Label htmlFor="mcp-args">Args（每行一个）</Label>
            <Textarea id="mcp-args" rows={3} {...form.register("argsText")} />
          </div>
        </>
      ) : null}
      <div className={usesUrlFields && usesCommandFields ? "grid gap-4 md:grid-cols-2" : "space-y-4"}>
        {usesUrlFields ? (
          <div className="space-y-2">
            <Label htmlFor="mcp-headers">Headers（KEY=VALUE）</Label>
            <Textarea id="mcp-headers" rows={4} {...form.register("headersText")} />
          </div>
        ) : null}
        {usesCommandFields ? (
          <div className="space-y-2">
            <Label htmlFor="mcp-env">Env（KEY=VALUE）</Label>
            <Textarea id="mcp-env" rows={4} {...form.register("envText")} />
          </div>
        ) : null}
      </div>
      {mutation.error ? (
        <p className="rounded-2xl bg-rose-50 px-3 py-2 text-sm text-rose-600">
          {getErrorMessage(mutation.error)}
        </p>
      ) : null}
      <Button type="submit" disabled={mutation.isPending}>
        {mutation.isPending
          ? mode === "edit"
            ? "保存中..."
            : "创建中..."
          : mode === "edit"
            ? "保存 MCP Server"
            : "创建 MCP Server"}
      </Button>
    </form>
  );
}

export function ChatModelForm({
  onSuccess,
  mode = "create",
  model,
}: BaseFormProps & {
  mode?: FormMode;
  model?: Partial<LlmModelResponse> | null;
}) {
  const createModel = useCreateChatModel();
  const updateModel = useUpdateChatModel(model?.id);
  const form = useForm<ChatModelSchema>({
    resolver: zodResolver(chatModelSchema),
    values: {
      name: model?.name ?? "",
      provider: model?.provider ?? "openai_compatible",
      model_name: model?.model_name ?? "",
      base_url: model?.base_url ?? "",
      api_key: "",
      description: model?.description ?? "",
    },
  });

  const onSubmit = form.handleSubmit(async (values) => {
    const payload = {
      name: values.name,
      provider: values.provider,
      model_name: values.model_name,
      base_url: values.base_url || undefined,
      api_key: values.api_key || undefined,
      temperature: model?.temperature ?? 0.1,
      context_window: model?.context_window ?? 8000,
      support_vision: model?.support_vision ?? false,
      support_function_calling: model?.support_function_calling ?? true,
      is_enabled: model?.is_enabled ?? true,
      is_default: model?.is_default ?? false,
      description: values.description || undefined,
    };

    if (mode === "edit" && model?.id) {
      await updateModel.mutateAsync(payload);
    } else {
      await createModel.mutateAsync(payload);
      form.reset();
    }
    onSuccess?.();
  });

  const mutation = mode === "edit" ? updateModel : createModel;

  return (
    <form className="space-y-4" onSubmit={onSubmit}>
      <div className="grid gap-4 md:grid-cols-2">
        <div className="space-y-2">
          <Label htmlFor="chat-model-name">名称</Label>
          <Input id="chat-model-name" {...form.register("name")} />
        </div>
        <div className="space-y-2">
          <Label htmlFor="chat-model-provider">Provider</Label>
          <Input id="chat-model-provider" {...form.register("provider")} />
        </div>
      </div>
      <div className="space-y-2">
        <Label htmlFor="chat-model-model-name">Model Name</Label>
        <Input id="chat-model-model-name" {...form.register("model_name")} />
      </div>
      <div className="grid gap-4 md:grid-cols-2">
        <div className="space-y-2">
          <Label htmlFor="chat-model-base-url">Base URL</Label>
          <Input id="chat-model-base-url" {...form.register("base_url")} />
        </div>
        <div className="space-y-2">
          <Label htmlFor="chat-model-api-key">API Key</Label>
          <Input id="chat-model-api-key" type="password" {...form.register("api_key")} />
        </div>
      </div>
      <div className="space-y-2">
        <Label htmlFor="chat-model-description">描述</Label>
        <Textarea id="chat-model-description" rows={3} {...form.register("description")} />
      </div>
      {mutation.error ? (
        <p className="rounded-2xl bg-rose-50 px-3 py-2 text-sm text-rose-600">
          {getErrorMessage(mutation.error)}
        </p>
      ) : null}
      <Button type="submit" disabled={mutation.isPending}>
        {mutation.isPending
          ? mode === "edit"
            ? "保存中..."
            : "创建中..."
          : mode === "edit"
            ? "保存 Chat Model"
            : "创建 Chat Model"}
      </Button>
    </form>
  );
}

export function EmbeddingModelForm({
  onSuccess,
  mode = "create",
  model,
}: BaseFormProps & {
  mode?: FormMode;
  model?: Partial<EmbeddingModelResponse> | null;
}) {
  const createModel = useCreateEmbeddingModel();
  const updateModel = useUpdateEmbeddingModel(model?.id);
  const form = useForm<
    z.input<typeof embeddingModelSchema>,
    unknown,
    z.output<typeof embeddingModelSchema>
  >({
    resolver: zodResolver(embeddingModelSchema),
    values: {
      name: model?.name ?? "",
      type: model?.type ?? "openai_compatible",
      model_name: model?.model_name ?? "",
      endpoint: model?.endpoint ?? "",
      api_key: "",
      local_model_path: model?.local_model_path ?? "",
      description: model?.description ?? "",
    },
  });

  const onSubmit = form.handleSubmit(async (values) => {
    const payload = {
      name: values.name,
      type: values.type,
      model_name: values.model_name || undefined,
      endpoint: values.endpoint || undefined,
      api_key: values.api_key || undefined,
      local_model_path: values.local_model_path || undefined,
      batch_size: model?.batch_size ?? 10,
      is_enabled: model?.is_enabled ?? true,
      is_default: model?.is_default ?? false,
      description: values.description || undefined,
    };

    if (mode === "edit" && model?.id) {
      await updateModel.mutateAsync(payload);
    } else {
      await createModel.mutateAsync(payload);
      form.reset();
    }
    onSuccess?.();
  });

  const mutation = mode === "edit" ? updateModel : createModel;

  return (
    <form className="space-y-4" onSubmit={onSubmit}>
      <div className="grid gap-4 md:grid-cols-2">
        <div className="space-y-2">
          <Label htmlFor="embedding-name">名称</Label>
          <Input id="embedding-name" {...form.register("name")} />
        </div>
        <div className="space-y-2">
          <Label htmlFor="embedding-type">类型</Label>
          <select
            id="embedding-type"
            className="flex h-10 w-full rounded-xl border border-slate-200 bg-white px-3 text-sm outline-none focus:ring-2 focus:ring-sky-500"
            {...form.register("type")}
          >
            <option value="openai_compatible">openai_compatible</option>
            <option value="local">local</option>
          </select>
        </div>
      </div>
      <div className="grid gap-4 md:grid-cols-2">
        <div className="space-y-2">
          <Label htmlFor="embedding-model-name">Model Name</Label>
          <Input id="embedding-model-name" {...form.register("model_name")} />
        </div>
        <div className="space-y-2">
          <Label htmlFor="embedding-endpoint">Endpoint</Label>
          <Input id="embedding-endpoint" {...form.register("endpoint")} />
        </div>
      </div>
      <div className="grid gap-4 md:grid-cols-2">
        <div className="space-y-2">
          <Label htmlFor="embedding-api-key">API Key</Label>
          <Input id="embedding-api-key" type="password" {...form.register("api_key")} />
        </div>
        <div className="space-y-2">
          <Label htmlFor="embedding-local-model-path">本地模型路径</Label>
          <Input id="embedding-local-model-path" {...form.register("local_model_path")} />
        </div>
      </div>
      <div className="space-y-2">
        <Label htmlFor="embedding-description">描述</Label>
        <Textarea id="embedding-description" rows={3} {...form.register("description")} />
      </div>
      {mutation.error ? (
        <p className="rounded-2xl bg-rose-50 px-3 py-2 text-sm text-rose-600">
          {getErrorMessage(mutation.error)}
        </p>
      ) : null}
      <Button type="submit" disabled={mutation.isPending}>
        {mutation.isPending
          ? mode === "edit"
            ? "保存中..."
            : "创建中..."
          : mode === "edit"
            ? "保存 Embedding Model"
            : "创建 Embedding Model"}
      </Button>
    </form>
  );
}

export function RerankModelForm({
  onSuccess,
  mode = "create",
  model,
}: BaseFormProps & {
  mode?: FormMode;
  model?: Partial<RerankModelResponse> | null;
}) {
  const createModel = useCreateRerankModel();
  const updateModel = useUpdateRerankModel(model?.id);
  const form = useForm<RerankModelSchema>({
    resolver: zodResolver(rerankModelSchema),
    values: {
      name: model?.name ?? "",
      provider: model?.provider ?? "dashscope",
      model_name: model?.model_name ?? "",
      base_url: model?.base_url ?? "",
      api_key: "",
      description: model?.description ?? "",
    },
  });

  const onSubmit = form.handleSubmit(async (values) => {
    const payload = {
      name: values.name,
      provider: values.provider,
      model_name: values.model_name || undefined,
      base_url: values.base_url || undefined,
      api_key: values.api_key || undefined,
      is_enabled: model?.is_enabled ?? true,
      is_default: model?.is_default ?? false,
      description: values.description || undefined,
    };

    if (mode === "edit" && model?.id) {
      await updateModel.mutateAsync(payload);
    } else {
      await createModel.mutateAsync(payload);
      form.reset();
    }
    onSuccess?.();
  });

  const mutation = mode === "edit" ? updateModel : createModel;

  return (
    <form className="space-y-4" onSubmit={onSubmit}>
      <div className="grid gap-4 md:grid-cols-2">
        <div className="space-y-2">
          <Label htmlFor="rerank-name">名称</Label>
          <Input id="rerank-name" {...form.register("name")} />
        </div>
        <div className="space-y-2">
          <Label htmlFor="rerank-provider">Provider</Label>
          <Input id="rerank-provider" {...form.register("provider")} />
        </div>
      </div>
      <div className="grid gap-4 md:grid-cols-2">
        <div className="space-y-2">
          <Label htmlFor="rerank-model-name">Model Name</Label>
          <Input id="rerank-model-name" {...form.register("model_name")} />
        </div>
        <div className="space-y-2">
          <Label htmlFor="rerank-base-url">Base URL</Label>
          <Input id="rerank-base-url" {...form.register("base_url")} />
        </div>
      </div>
      <div className="space-y-2">
        <Label htmlFor="rerank-api-key">API Key</Label>
        <Input id="rerank-api-key" type="password" {...form.register("api_key")} />
      </div>
      <div className="space-y-2">
        <Label htmlFor="rerank-description">描述</Label>
        <Textarea id="rerank-description" rows={3} {...form.register("description")} />
      </div>
      {mutation.error ? (
        <p className="rounded-2xl bg-rose-50 px-3 py-2 text-sm text-rose-600">
          {getErrorMessage(mutation.error)}
        </p>
      ) : null}
      <Button type="submit" disabled={mutation.isPending}>
        {mutation.isPending
          ? mode === "edit"
            ? "保存中..."
            : "创建中..."
          : mode === "edit"
            ? "保存 Rerank Model"
            : "创建 Rerank Model"}
      </Button>
    </form>
  );
}
