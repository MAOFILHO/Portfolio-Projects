// Video status types (includes both display and API values)
export type VideoStatus = 'uploaded' | 'screened' | 'analyzed' | 'approved' | 'rejected' | 'review' | 'processing' | 'gpu_queued' | 'approve' | 'reject';

// Video interface
export interface Video {
  video_id: string;
  filename: string;
  s3_key: string;
  size: number;
  status: VideoStatus;
  risk_score: number;
  nsfw_score: number;
  violence_score: number;
  final_score: number;
  decision: 'approve' | 'reject' | 'review' | 'pending';
  screening_type?: 'cpu' | 'gpu';
  frames_analyzed?: number;
  human_reviewed: boolean;
  reviewer_notes?: string;
  uploaded_at: string;
  screened_at?: string;
  analyzed_at?: string;
  decided_at?: string;
  reviewed_at?: string;
  flagged_frames?: string[];
}

// Upload response
export interface UploadResponse {
  job_id: string;
  status: string;
}

// Review queue item
export interface ReviewQueueItem {
  video_id: string;
  risk_score: number;
  final_score: number;
  flagged_frames: string[];
  submitted_at: string;
  filename: string;
  ai_summary_available?: boolean;
}

// Dashboard stats
export interface DashboardStats {
  total: number;
  approved: number;
  rejected: number;
  pending_review: number;
  processing: number;
}

// API error response
export interface ApiError {
  detail: string;
  status?: number;
}
