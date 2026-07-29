import type {
  ClipInfo,
  FrameUploadResponse,
  OnDemandAnalysisResult,
  OnDemandFeature,
  SurveillanceEvent,
} from "../types";

const API_BASE_URL: string = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000";
const API_KEY: string = import.meta.env.VITE_API_KEY ?? "";

export async function uploadFrame(cameraId: string, blob: Blob): Promise<FrameUploadResponse> {
  const formData = new FormData();
  formData.append("camera_id", cameraId);
  formData.append("file", blob, "frame.jpg");

  const response = await fetch(`${API_BASE_URL}/api/v1/frames`, {
    method: "POST",
    headers: API_KEY ? { "X-Api-Key": API_KEY } : undefined,
    body: formData,
  });

  if (!response.ok) {
    throw new Error(`Frame upload failed: ${response.status} ${await response.text()}`);
  }

  return response.json() as Promise<FrameUploadResponse>;
}

export async function uploadClip(cameraId: string, blob: Blob, contentType: string): Promise<void> {
  const extension = contentType === "video/mp4" ? "mp4" : "webm";
  const formData = new FormData();
  formData.append("camera_id", cameraId);
  formData.append("file", blob, `clip.${extension}`);

  const response = await fetch(`${API_BASE_URL}/api/v1/clips`, {
    method: "POST",
    headers: API_KEY ? { "X-Api-Key": API_KEY } : undefined,
    body: formData,
  });

  if (!response.ok) {
    throw new Error(`Clip upload failed: ${response.status} ${await response.text()}`);
  }
}

export async function fetchClips(limit = 50): Promise<ClipInfo[]> {
  const response = await fetch(`${API_BASE_URL}/api/v1/clips?limit=${limit}`, { cache: "no-store" });
  if (!response.ok) {
    throw new Error(`Failed to fetch clips: ${response.status}`);
  }
  const payload = (await response.json()) as { clips: ClipInfo[] };
  return payload.clips;
}

export function clipVideoUrl(blobName: string): string {
  return `${API_BASE_URL}/api/v1/clips/${blobName}`;
}

export async function fetchEvents(limit = 50): Promise<SurveillanceEvent[]> {
  const response = await fetch(`${API_BASE_URL}/api/v1/events?limit=${limit}`, { cache: "no-store" });
  if (!response.ok) {
    throw new Error(`Failed to fetch events: ${response.status}`);
  }
  const payload = (await response.json()) as { events: SurveillanceEvent[] };
  return payload.events;
}

export function frameImageUrl(blobName: string): string {
  return `${API_BASE_URL}/api/v1/frames/${blobName}`;
}

export async function analyzeFrame(
  blobName: string,
  features: OnDemandFeature[]
): Promise<OnDemandAnalysisResult> {
  const response = await fetch(
    `${API_BASE_URL}/api/v1/frames/${blobName}/analyze?features=${features.join(",")}`,
    { method: "POST", headers: API_KEY ? { "X-Api-Key": API_KEY } : undefined }
  );
  if (!response.ok) {
    throw new Error(`Analysis failed: ${response.status} ${await response.text()}`);
  }
  return response.json() as Promise<OnDemandAnalysisResult>;
}

export async function fetchHealth(): Promise<{ status: string }> {
  const response = await fetch(`${API_BASE_URL}/api/v1/health`, { cache: "no-store" });
  return response.json() as Promise<{ status: string }>;
}

export interface AppSettings {
  alert_watch_tags: string[];
  alert_min_confidence: number;
  alert_min_count: number;
  capture_interval_seconds: number;
  analyzer_backend: string;
  alert_crowd_threshold: number;
  alert_restricted_zone: string;
  alert_severity_map: Record<string, string>;
}

export async function fetchSettings(): Promise<AppSettings> {
  const response = await fetch(`${API_BASE_URL}/api/v1/settings`, { cache: "no-store" });
  if (!response.ok) {
    throw new Error(`Failed to fetch settings: ${response.status}`);
  }
  return response.json() as Promise<AppSettings>;
}

export interface AuditEvent {
  PartitionKey: string;
  RowKey: string;
  Actor: string;
  Action: string;
  Details: string;
  // Not "Timestamp" -- that name collides with Table Storage's own
  // system-reserved property and never comes back as a regular field.
  LoggedAt: string;
}

export async function fetchAuditEvents(limit = 50): Promise<AuditEvent[]> {
  const response = await fetch(`${API_BASE_URL}/api/v1/audit?limit=${limit}`, { cache: "no-store" });
  if (!response.ok) {
    throw new Error(`Failed to fetch audit events: ${response.status}`);
  }
  const payload = (await response.json()) as { events: AuditEvent[] };
  return payload.events;
}

export async function logAuditEvent(actor: string, action: string, details = ""): Promise<void> {
  await fetch(`${API_BASE_URL}/api/v1/audit`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      ...(API_KEY ? { "X-Api-Key": API_KEY } : {}),
    },
    body: JSON.stringify({ actor, action, details }),
  }).catch(() => {
    // Audit logging is best-effort -- never block the UI action it's describing.
  });
}

export interface RequestBucket {
  timestamp: string;
  total: number;
  failed: number;
}

export async function fetchRequestsSummary(hours = 24): Promise<RequestBucket[]> {
  const response = await fetch(`${API_BASE_URL}/api/v1/observability/requests-summary?hours=${hours}`, {
    cache: "no-store",
  });
  if (!response.ok) {
    throw new Error(`Failed to fetch requests summary: ${response.status}`);
  }
  const payload = (await response.json()) as { buckets: RequestBucket[] };
  return payload.buckets;
}

export interface ExceptionEvent {
  timestamp: string;
  severity: number;
  message: string;
  problem_id: string;
}

export async function fetchRecentExceptions(limit = 20): Promise<ExceptionEvent[]> {
  const response = await fetch(`${API_BASE_URL}/api/v1/observability/exceptions?limit=${limit}`, {
    cache: "no-store",
  });
  if (!response.ok) {
    throw new Error(`Failed to fetch exceptions: ${response.status}`);
  }
  const payload = (await response.json()) as { exceptions: ExceptionEvent[] };
  return payload.exceptions;
}

export interface AgentActivityEntry {
  timestamp: string;
  message: string;
}

export async function fetchAgentActivity(hours = 24, limit = 100): Promise<AgentActivityEntry[]> {
  const response = await fetch(`${API_BASE_URL}/api/v1/agents/activity?hours=${hours}&limit=${limit}`, {
    cache: "no-store",
  });
  if (!response.ok) {
    throw new Error(`Failed to fetch agent activity: ${response.status}`);
  }
  const payload = (await response.json()) as { entries: AgentActivityEntry[] };
  return payload.entries;
}

export { API_BASE_URL };
