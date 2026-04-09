import { authStorage } from "@/lib/storage";
import { env } from "@/lib/env";

type RequestOptions = RequestInit & {
  raw?: boolean;
};

type ApiEnvelope<T> = {
  code: number;
  message: string;
  data: T;
  total?: number;
};

async function request<T>(path: string, options: RequestOptions = {}) {
  const headers = new Headers(options.headers ?? {});
  const tokens = authStorage.getTokens();

  if (!headers.has("Content-Type") && options.body && !(options.body instanceof FormData)) {
    headers.set("Content-Type", "application/json");
  }

  if (tokens?.accessToken) {
    headers.set("Authorization", `Bearer ${tokens.accessToken}`);
  }

  const response = await fetch(`${env.apiBaseUrl}${path}`, {
    ...options,
    headers,
  });

  if (!response.ok) {
    const text = await response.text();
    throw new Error(text || `Request failed with ${response.status}`);
  }

  if (options.raw) {
    return response as T;
  }

  if (response.status === 204) {
    return null as T;
  }

  return (await response.json()) as T;
}

export const apiClient = {
  get: <T>(path: string) => request<ApiEnvelope<T>>(path),
  post: <T, B = unknown>(path: string, body?: B) =>
    request<ApiEnvelope<T>>(path, {
      method: "POST",
      body: body instanceof FormData ? body : body ? JSON.stringify(body) : undefined,
    }),
  patch: <T, B = unknown>(path: string, body?: B) =>
    request<ApiEnvelope<T>>(path, {
      method: "PATCH",
      body: body instanceof FormData ? body : body ? JSON.stringify(body) : undefined,
    }),
  put: <T, B = unknown>(path: string, body?: B) =>
    request<ApiEnvelope<T>>(path, {
      method: "PUT",
      body: body instanceof FormData ? body : body ? JSON.stringify(body) : undefined,
    }),
  delete: (path: string) =>
    request<null>(path, {
      method: "DELETE",
    }),
};

export type { ApiEnvelope };
