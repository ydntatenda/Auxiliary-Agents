const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000";

export type CaptureResponse = {
  workflow_id: string;
  status: string;
};

export type WorkflowStatus = {
  workflow_id: string;
  status: string;
  has_transcript: boolean;
  gaps_total: number;
  gaps_resolved: number;
};

export type ClarifyResponse = {
  question: string | null;
  done: boolean;
  message: string | null;
};

export type SopResponse = {
  workflow_id: string;
  sop: string;
};

export type SourceStatus = "pending" | "processing" | "ready" | "failed";

export type Source = {
  id: string;
  workflow_id: string;
  order: number;
  modality: string;
  label: string | null;
  contributor_role: string | null;
  status: SourceStatus;
  error: string | null;
  meta: Record<string, unknown> | null;
  assembled_text: string | null;
};

export type CreateWorkflowResponse = {
  workflow_id: string;
  status: string;
};

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`, init);
  if (!response.ok) {
    const text = await response.text();
    throw new Error(text || response.statusText);
  }
  // 204 No Content has no body to parse.
  if (response.status === 204) return undefined as T;
  return response.json() as Promise<T>;
}

// Workflow identity (sub-stage A).
export async function createWorkflow(
  name: string,
  unit: string,
  contributorRole: string,
) {
  return request<CreateWorkflowResponse>("/workflows", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ name, unit, contributor_role: contributorRole }),
  });
}

// Source management (sub-stage B).
export async function listSources(workflowId: string) {
  return request<Source[]>(`/workflows/${workflowId}/sources`);
}

export async function addTextSource(
  workflowId: string,
  text: string,
  contributorRole: string | null,
  label?: string,
) {
  return request<Source>(`/workflows/${workflowId}/sources`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      modality: "text",
      raw_text: text,
      label,
      contributor_role: contributorRole,
    }),
  });
}

export async function addFileSource(
  workflowId: string,
  modality: "voice" | "screen" | "document",
  file: Blob,
  filename: string,
  contributorRole: string | null,
  label?: string,
) {
  const body = new FormData();
  body.append("modality", modality);
  body.append("file", file, filename);
  if (label) body.append("label", label);
  if (contributorRole) body.append("contributor_role", contributorRole);
  return request<Source>(`/workflows/${workflowId}/sources`, {
    method: "POST",
    body,
  });
}

export async function addChatSource(
  workflowId: string,
  messages: Array<{ question: string; answer: string }>,
  contributorRole: string | null,
  label?: string,
) {
  return request<Source>(`/workflows/${workflowId}/sources`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      modality: "chat",
      chat_messages: messages,
      label,
      contributor_role: contributorRole,
    }),
  });
}

export async function deleteSource(workflowId: string, sourceId: string) {
  return request<void>(`/workflows/${workflowId}/sources/${sourceId}`, {
    method: "DELETE",
  });
}

export async function retrySource(workflowId: string, sourceId: string) {
  return request<Source>(
    `/workflows/${workflowId}/sources/${sourceId}/retry`,
    { method: "POST" },
  );
}

export async function updateSource(
  workflowId: string,
  sourceId: string,
  patch: { label?: string; move?: "up" | "down" },
) {
  return request<Source>(`/workflows/${workflowId}/sources/${sourceId}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(patch),
  });
}

// Deprecated single-shot endpoints, kept so the backend shims have a caller
// in any old build still in flight. The new capture flow does not use these.
export async function captureText(name: string, unit: string, text: string) {
  return request<CaptureResponse>("/capture/text", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ name, unit, text }),
  });
}

export async function captureVoice(name: string, unit: string, file: Blob) {
  const body = new FormData();
  body.append("name", name);
  body.append("unit", unit);
  body.append("file", file, "voice.webm");
  return request<CaptureResponse>("/capture/voice", { method: "POST", body });
}

export async function captureScreen(name: string, unit: string, file: Blob) {
  const body = new FormData();
  body.append("name", name);
  body.append("unit", unit);
  body.append("file", file, "screen.webm");
  return request<CaptureResponse>("/capture/screen", { method: "POST", body });
}

export async function getStatus(workflowId: string) {
  return request<WorkflowStatus>(`/workflows/${workflowId}/status`);
}

export async function extractWorkflow(workflowId: string) {
  return request(`/workflows/${workflowId}/extract`, { method: "POST" });
}

export async function startClarification(workflowId: string) {
  return request<ClarifyResponse>(`/workflows/${workflowId}/clarify`, {
    method: "POST",
  });
}

export async function answerClarification(workflowId: string, answer: string) {
  return request<ClarifyResponse>(`/workflows/${workflowId}/clarify/answer`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ answer }),
  });
}

export async function getSop(workflowId: string) {
  return request<SopResponse>(`/workflows/${workflowId}/sop`);
}

export function sopDownloadUrl(workflowId: string) {
  return `${API_BASE_URL}/workflows/${workflowId}/sop/download`;
}
