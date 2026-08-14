import type { AppConfig, DashboardStats, Message, StreamEvent, Task } from "./types";
import { uiError, uiLog } from "./debug";

export interface RagUploadResult {
  ok: boolean;
  file_name: string;
  s3_key: string;
  url?: string | null;
  message: string;
  sync?: {
    ingestion_job_id?: string;
    status?: string;
  };
}

export interface FileUploadResult {
  ok: boolean;
  file_name: string;
  s3_key: string;
  url: string;
  content_type?: string;
}

export interface LlmGatewayConfig {
  url: string;
  configured: boolean;
  key_configured?: boolean;
}

export interface LlmGatewayVerifyResult {
  ok: boolean;
  message: string;
  models: string[];
  ui_models?: string[];
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const method = init?.method ?? "GET";
  uiLog(`api:${method} ${path}`);
  const res = await fetch(path, {
    credentials: "include",
    headers: {
      "Content-Type": "application/json",
      ...(init?.headers ?? {}),
    },
    ...init,
  });
  if (!res.ok) {
    const text = await res.text();
    uiError(`api:${method} ${path} failed`, { status: res.status, body: text });
    let message = text || res.statusText;
    try {
      const parsed = JSON.parse(text) as { detail?: string | { msg?: string }[] };
      if (typeof parsed.detail === "string" && parsed.detail) {
        message = parsed.detail;
      }
    } catch {
      // keep raw text
    }
    throw new Error(message);
  }
  if (res.status === 204) {
    uiLog(`api:${method} ${path} -> 204`);
    return undefined as T;
  }
  const text = await res.text();
  if (!text) {
    uiLog(`api:${method} ${path} -> empty`);
    return undefined as T;
  }
  const data = JSON.parse(text) as T;
  uiLog(`api:${method} ${path} -> ok`);
  return data;
}

export interface GraphStatus {
  user_id: string;
  exists: boolean;
  path: string | null;
  status: "idle" | "queued" | "running" | "ready" | "error" | "skipped_cooldown" | "disabled" | string;
  enabled?: boolean;
  error?: string | null;
  message?: string | null;
  last_success_at?: string | null;
  cooldown_seconds?: number;
  next_eligible_at?: string | null;
}

export interface WikiStatus {
  wiki_dir: string;
  sources?: string[];
  max_sources?: number;
  exists: boolean;
  path: string | null;
  storage?: string;
  status: "idle" | "queued" | "running" | "ready" | "error" | "unchanged" | string;
  pattern?: GraphPattern | string;
  error?: string | null;
  message?: string | null;
  last_success_at?: string | null;
  pid?: number | null;
}

export interface WikiSourcesConfig {
  wiki_dir: string;
  folders: string[];
  urls: string[];
  max_sources: number;
}

export interface WikiUrlIngestResult {
  wiki_dir: string;
  url: string;
  path: string;
  urls: string[];
  folders: string[];
  max_sources: number;
}

export interface WikiRawUploadResult {
  wiki_dir: string;
  raw_dir: string;
  count: number;
  saved: Array<{ name: string; path: string; bytes: number }>;
}

export interface WikiBrowseResult {
  path: string;
  parent: string | null;
  dirs: { name: string; path: string }[];
  shortcuts: { name: string; path: string }[];
}

export type GraphPattern = "pattern1" | "pattern2" | "pattern3";

export interface SessionInfo {
  user_id: string;
  name?: string | null;
  picture?: string | null;
  llm_gateway_ready?: boolean;
  knowledge_graph_enabled?: boolean;
  graph_pattern?: GraphPattern | string;
}

export const api = {
  getSession: () => request<SessionInfo | null>("/api/session"),
  setSession: (credential: string) =>
    request<SessionInfo>("/api/session", {
      method: "POST",
      body: JSON.stringify({ credential }),
    }),
  setSessionWithAccessToken: (access_token: string) =>
    request<SessionInfo>("/api/session", {
      method: "POST",
      body: JSON.stringify({ access_token }),
    }),
  setLocalSession: (user_id: string) =>
    request<SessionInfo>("/api/session", {
      method: "POST",
      body: JSON.stringify({ user_id }),
    }),
  clearSession: () => request<void>("/api/session", { method: "DELETE" }),
  patchSessionSettings: (body: {
    knowledge_graph_enabled?: boolean;
    graph_pattern?: GraphPattern | string;
  }) =>
    request<SessionInfo>("/api/session/settings", {
      method: "PATCH",
      body: JSON.stringify(body),
    }),
  getGraphStatus: () => request<GraphStatus>("/api/graph/status"),
  rebuildGraph: (force = false) =>
    request<GraphStatus>(`/api/graph/rebuild${force ? "?force=1" : ""}`, {
      method: "POST",
    }),
  getWikiStatus: () => request<WikiStatus>("/api/wiki/status"),
  syncWiki: (full = false) =>
    request<WikiStatus>(`/api/wiki/sync${full ? "?full=1" : ""}`, {
      method: "POST",
    }),
  setWikiGraphPattern: (pattern: GraphPattern | string) =>
    request<WikiStatus>("/api/wiki/pattern", {
      method: "PATCH",
      body: JSON.stringify({ pattern }),
    }),
  getWikiSources: () => request<WikiSourcesConfig>("/api/wiki/sources"),
  putWikiSources: (body: { folders: string[] }) =>
    request<WikiSourcesConfig>("/api/wiki/sources", {
      method: "PUT",
      body: JSON.stringify(body),
    }),
  ingestWikiUrl: (url: string) =>
    request<WikiUrlIngestResult>("/api/wiki/urls", {
      method: "POST",
      body: JSON.stringify({ url }),
    }),
  uploadWikiRawFiles: async (files: File[]): Promise<WikiRawUploadResult> => {
    if (!files.length) {
      throw new Error("업로드할 파일이 없습니다.");
    }
    uiLog("wiki:raw upload start", { count: files.length });
    const form = new FormData();
    for (const file of files) {
      form.append("files", file, file.name);
    }
    const res = await fetch("/api/wiki/raw", {
      method: "POST",
      credentials: "include",
      body: form,
    });
    if (!res.ok) {
      const text = await res.text();
      uiError("wiki:raw upload failed", { status: res.status, body: text });
      let message = text || res.statusText;
      try {
        const parsed = JSON.parse(text) as { detail?: string };
        if (typeof parsed.detail === "string" && parsed.detail) {
          message = parsed.detail;
        }
      } catch {
        // keep raw text
      }
      throw new Error(message);
    }
    const data = (await res.json()) as WikiRawUploadResult;
    uiLog("wiki:raw upload complete", data);
    return data;
  },
  browseWikiSources: (path?: string) => {
    const q = path ? `?path=${encodeURIComponent(path)}` : "";
    return request<WikiBrowseResult>(`/api/wiki/browse${q}`);
  },
  getConfig: () => request<AppConfig>("/api/config"),
  getAdminDashboard: () => request<DashboardStats>("/api/admin/dashboard"),
  getLlmGateway: () =>
    request<LlmGatewayConfig>("/api/config/llm-gateway"),
  verifyLlmGateway: (body: { url: string; key?: string }) =>
    request<LlmGatewayVerifyResult>("/api/config/llm-gateway/verify", {
      method: "POST",
      body: JSON.stringify({ url: body.url, key: body.key ?? "" }),
    }),
  listTasks: () => request<{ tasks: Task[] }>("/api/tasks"),
  createTask: (body: Partial<Task>) =>
    request<Task>("/api/tasks", {
      method: "POST",
      body: JSON.stringify(body),
    }),
  getTask: (id: string) => request<Task>(`/api/tasks/${id}`),
  patchTask: (id: string, body: Partial<Task>) =>
    request<Task>(`/api/tasks/${id}`, {
      method: "PATCH",
      body: JSON.stringify(body),
    }),
  deleteTask: (id: string) =>
    request<{ ok: boolean }>(`/api/tasks/${id}`, { method: "DELETE" }),
  getMessages: (id: string) =>
    request<{ messages: Message[] }>(`/api/tasks/${id}/messages`),
  uploadToRag: async (file: File): Promise<RagUploadResult> => {
    uiLog("rag:upload start", { name: file.name, size: file.size });
    const form = new FormData();
    form.append("file", file);
    const res = await fetch("/api/rag/upload", {
      method: "POST",
      credentials: "include",
      body: form,
    });
    if (!res.ok) {
      const text = await res.text();
      uiError("rag:upload failed", { status: res.status, body: text });
      let message = text || res.statusText;
      try {
        const parsed = JSON.parse(text) as { detail?: string };
        if (typeof parsed.detail === "string" && parsed.detail) {
          message = parsed.detail;
        }
      } catch {
        // keep raw text
      }
      throw new Error(message);
    }
    const data = (await res.json()) as RagUploadResult;
    uiLog("rag:upload complete", data);
    return data;
  },
  uploadFile: async (file: File): Promise<FileUploadResult> => {
    uiLog("file:upload start", { name: file.name, size: file.size, type: file.type });
    const form = new FormData();
    form.append("file", file);
    const res = await fetch("/api/files/upload", {
      method: "POST",
      credentials: "include",
      body: form,
    });
    if (!res.ok) {
      const text = await res.text();
      uiError("file:upload failed", { status: res.status, body: text });
      throw new Error(text || res.statusText);
    }
    const data = (await res.json()) as FileUploadResult;
    if (!data.url) {
      throw new Error("Upload succeeded but no URL was returned");
    }
    uiLog("file:upload complete", data);
    return data;
  },
  streamChat: async function* (
    taskId: string,
    prompt: string,
    files: string[] = [],
    signal?: AbortSignal,
  ): AsyncGenerator<StreamEvent> {
    uiLog("chat:stream start", { taskId, prompt, files });
    const res = await fetch(`/api/tasks/${taskId}/chat`, {
      method: "POST",
      credentials: "include",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ prompt, files }),
      signal,
    });
    if (!res.ok || !res.body) {
      const body = await res.text();
      uiError("chat:stream request failed", { status: res.status, body });
      throw new Error("Chat request failed. Please try again.");
    }

    const reader = res.body.getReader();
    const decoder = new TextDecoder();
    let buffer = "";
    let eventCount = 0;

    try {
      while (true) {
        if (signal?.aborted) {
          throw new DOMException("Aborted", "AbortError");
        }
        const { done, value } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });
        const parts = buffer.split("\n\n");
        buffer = parts.pop() ?? "";
        for (const part of parts) {
          const line = part
            .split("\n")
            .find((l) => l.startsWith("data:"));
          if (!line) continue;
          const payload = line.slice(5).trim();
          if (!payload) continue;
          const event = JSON.parse(payload) as StreamEvent;
          eventCount += 1;
          if (event.type === "token") {
            const text = event.data ?? "";
            uiLog("chat:sse token", { chars: text.length, preview: text.slice(0, 80) });
          } else if (event.type === "error") {
            uiError("chat:sse error", event);
          } else {
            uiLog(`chat:sse ${event.type}`, event);
          }
          yield event;
        }
      }
    } catch (err) {
      try {
        await reader.cancel();
      } catch {
        /* ignore cancel errors */
      }
      throw err;
    }

    uiLog("chat:stream end", { taskId, eventCount });
  },
};
