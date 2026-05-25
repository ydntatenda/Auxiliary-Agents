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

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`, init);
  if (!response.ok) {
    const text = await response.text();
    throw new Error(text || response.statusText);
  }
  return response.json() as Promise<T>;
}

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
  return request<ClarifyResponse>(`/workflows/${workflowId}/clarify`, { method: "POST" });
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

