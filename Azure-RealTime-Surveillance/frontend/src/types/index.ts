export interface Detection {
  tag: string;
  confidence: number;
  bounding_box?: [number, number, number, number] | null;
}

export interface SurveillanceEvent {
  PartitionKey: string; // camera_id
  RowKey: string; // event_id
  FrameBlobName: string;
  CapturedAt: string;
  AnalyzedAt: string;
  Caption: string;
  Detections: string; // JSON-encoded { detections: Detection[] }
  IsAlert: boolean;
  MatchedTags: string; // JSON-encoded string[]
  Severity: string; // "critical" | "high" | "medium" | "low" | ""
}

export interface AlertMessage {
  event_id: string;
  camera_id: string;
  frame_blob_name: string;
  frame_url: string | null;
  caption: string | null;
  matched_tags: string[];
  severity: string | null;
  detections: Detection[];
  triggered_at: string;
}

export interface FrameUploadResponse {
  blob_name: string;
  url: string;
  camera_id: string;
}

export type CaptureSource = "webcam" | "sample-video";

export type OnDemandFeature = "tags" | "read" | "smartcrops";

export interface OnDemandAnalysisResult {
  tags?: { name: string; confidence: number }[];
  read_lines?: string[];
  smart_crops?: { aspect_ratio: number; bounding_box: [number, number, number, number] }[];
}

export interface ClipInfo {
  camera_id: string;
  blob_name: string;
  last_modified: string;
}
