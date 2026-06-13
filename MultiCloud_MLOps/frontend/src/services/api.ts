import axios, { AxiosError } from 'axios';
import { Video, UploadResponse, ReviewQueueItem } from '../types';

// API base URL - will be configured via environment variable or ingress
const API_BASE_URL = process.env.REACT_APP_API_URL || '/api';

const api = axios.create({
  baseURL: API_BASE_URL,
  timeout: 30000,
  headers: {
    'Content-Type': 'application/json',
  },
});

// Extract a user-friendly message from API error response
const getResponseMessage = (data: unknown): string => {
  if (typeof data === 'string') return data;
  if (data && typeof data === 'object') {
    const obj = data as Record<string, unknown>;
    if (typeof obj.detail === 'string') return obj.detail;
    if (typeof obj.message === 'string') return obj.message;
    if (Array.isArray(obj.detail)) {
      const first = obj.detail[0];
      if (first && typeof first === 'object' && typeof (first as { msg?: string }).msg === 'string') return (first as { msg: string }).msg;
    }
  }
  return 'Request failed. Please try again.';
};

// Error handler - always throws Error with readable message
const handleError = (error: AxiosError) => {
  if (error.response) {
    const message = getResponseMessage(error.response.data);
    console.error('API Error:', error.response.data);
    throw new Error(message);
  }
  if (error.request) {
    const isTimeout = error.code === 'ECONNABORTED';
    console.error(isTimeout ? 'Request timeout' : 'Network Error:', error.message);
    throw new Error(
      isTimeout
        ? 'Upload took too long. Try a smaller file or check your connection.'
        : 'Network error. Please check your connection.'
    );
  }
  console.error('Error:', error.message);
  throw new Error(error.message || 'An unexpected error occurred.');
};

// Ingestion Service APIs
export const ingestionApi = {
  // Upload video
  uploadVideo: async (file: File): Promise<UploadResponse> => {
    try {
      const formData = new FormData();
      formData.append('file', file);

      const response = await api.post<UploadResponse>('/ingestion/upload', formData, {
        headers: {
          'Content-Type': 'multipart/form-data',
        },
        timeout: 300000, // 5 minutes for large video uploads (up to 500MB)
      });

      return response.data;
    } catch (error) {
      return handleError(error as AxiosError);
    }
  },

  // Health check
  healthCheck: async (): Promise<{ status: string }> => {
    try {
      const response = await api.get('/ingestion/health');
      return response.data;
    } catch (error) {
      return handleError(error as AxiosError);
    }
  },
};

// Video Management APIs (via custom endpoint or direct DynamoDB query)
export const videoApi = {
  // Get all videos
  getAllVideos: async (): Promise<Video[]> => {
    try {
      // This would need a backend endpoint to query DynamoDB
      // For now, we'll create a mock endpoint
      const response = await api.get<Video[]>('/videos');
      return response.data;
    } catch (error) {
      return handleError(error as AxiosError);
    }
  },

  // Get video by ID
  getVideoById: async (videoId: string): Promise<Video> => {
    try {
      const response = await api.get<Video>(`/videos/${videoId}`);
      return response.data;
    } catch (error) {
      return handleError(error as AxiosError);
    }
  },

  // Get videos by status
  getVideosByStatus: async (status: string): Promise<Video[]> => {
    try {
      const response = await api.get<Video[]>(`/videos?status=${status}`);
      return response.data;
    } catch (error) {
      return handleError(error as AxiosError);
    }
  },

  // Delete video
  deleteVideo: async (videoId: string): Promise<{ message: string; video_id: string }> => {
    try {
      const response = await api.delete<{ message: string; video_id: string }>(`/videos/${videoId}`);
      return response.data;
    } catch (error) {
      return handleError(error as AxiosError);
    }
  },
};

// Human Review APIs
export const reviewApi = {
  // Get review queue
  getReviewQueue: async (): Promise<{ items: ReviewQueueItem[]; count: number }> => {
    try {
      const response = await api.get('/review/queue');
      return response.data;
    } catch (error) {
      return handleError(error as AxiosError);
    }
  },

  // Submit review decision
  submitReview: async (
    videoId: string,
    approved: boolean,
    notes: string = ''
  ): Promise<{ video_id: string; decision: string; reviewed_at: string; notes: string }> => {
    try {
      const response = await api.post(`/review/review/${videoId}`, null, {
        params: { approved, notes },
      });
      return response.data;
    } catch (error) {
      return handleError(error as AxiosError);
    }
  },

  // Get AI summary (if Azure OpenAI is enabled)
  getAISummary: async (videoId: string): Promise<{ summary: string; cached: boolean }> => {
    try {
      const response = await api.get(`/review/review/${videoId}/summary`);
      return response.data;
    } catch (error) {
      return handleError(error as AxiosError);
    }
  },

  // Health check
  healthCheck: async (): Promise<{ status: string; queue_size: number; ai_copilot_enabled: boolean }> => {
    try {
      const response = await api.get('/review/health');
      return response.data;
    } catch (error) {
      return handleError(error as AxiosError);
    }
  },
};

// Policy Engine APIs
export const policyApi = {
  // Health check
  healthCheck: async (): Promise<{ status: string }> => {
    try {
      const response = await api.get('/policy/health');
      return response.data;
    } catch (error) {
      return handleError(error as AxiosError);
    }
  },
};

// Dashboard stats (aggregated from videos)
export const dashboardApi = {
  // Get dashboard statistics
  getStats: async (): Promise<{
    total: number;
    approved: number;
    rejected: number;
    pending_review: number;
    processing: number;
  }> => {
    try {
      const response = await api.get('/dashboard/stats');
      return response.data;
    } catch (error) {
      // If endpoint doesn't exist, calculate from videos
      console.warn('Dashboard stats endpoint not available, calculating from videos');
      const videos = await videoApi.getAllVideos();
      
      return {
        total: videos.length,
        approved: videos.filter(v => v.status === 'approved').length,
        rejected: videos.filter(v => v.status === 'rejected').length,
        pending_review: videos.filter(v => v.status === 'review').length,
        processing: videos.filter(v => ['uploaded', 'screened', 'analyzed', 'processing'].includes(v.status)).length,
      };
    }
  },
};

export default api;
