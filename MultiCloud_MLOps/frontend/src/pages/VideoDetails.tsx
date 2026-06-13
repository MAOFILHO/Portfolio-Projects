import React, { useState, useEffect } from 'react';
import {
  Container,
  Typography,
  Box,
  Paper,
  CircularProgress,
  Alert,
  Button,
  Grid,
  Divider,
  Chip,
  LinearProgress,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogContentText,
  DialogActions,
} from '@mui/material';
import {
  ArrowBack,
  CheckCircle,
  Cancel,
  RateReview,
  CloudDownload,
  Delete,
  Info,
  Schedule,
  Storage,
  Psychology,
} from '@mui/icons-material';
import { useParams, useNavigate } from 'react-router-dom';
import { videoApi } from '../services/api';
import { Video } from '../types';
import StatusBadge from '../components/StatusBadge';
import VideoPlayer from '../components/VideoPlayer';

const VideoDetails: React.FC = () => {
  const { videoId } = useParams<{ videoId: string }>();
  const navigate = useNavigate();
  const [video, setVideo] = useState<Video | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [deleteDialogOpen, setDeleteDialogOpen] = useState(false);
  const [deleting, setDeleting] = useState(false);

  useEffect(() => {
    const fetchVideo = async () => {
      if (!videoId) return;

      try {
        setLoading(true);
        setError(null);

        const videoData = await videoApi.getVideoById(videoId);
        setVideo(videoData);
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Failed to load video details');
      } finally {
        setLoading(false);
      }
    };

    fetchVideo();
  }, [videoId]);

  const formatFileSize = (bytes: number): string => {
    if (bytes === 0) return '0 Bytes';
    const k = 1024;
    const sizes = ['Bytes', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return Math.round((bytes / Math.pow(k, i)) * 100) / 100 + ' ' + sizes[i];
  };

  const formatDate = (dateString?: string): string => {
    if (!dateString) return 'N/A';
    const date = new Date(dateString);
    return date.toLocaleString();
  };

  const getRiskColor = (score: number): 'success' | 'warning' | 'error' => {
    if (score < 0.3) return 'success';
    if (score < 0.7) return 'warning';
    return 'error';
  };

  const handleDeleteClick = () => {
    setDeleteDialogOpen(true);
  };

  const handleDeleteConfirm = async () => {
    if (!videoId) return;

    try {
      setDeleting(true);
      await videoApi.deleteVideo(videoId);
      // Navigate back to dashboard after successful deletion
      navigate('/dashboard');
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to delete video');
      setDeleteDialogOpen(false);
    } finally {
      setDeleting(false);
    }
  };

  const handleDeleteCancel = () => {
    setDeleteDialogOpen(false);
  };

  if (loading) {
    return (
      <Container maxWidth="lg" sx={{ py: 4 }}>
        <Box display="flex" justifyContent="center" alignItems="center" minHeight="400px">
          <CircularProgress />
        </Box>
      </Container>
    );
  }

  if (error || !video) {
    return (
      <Container maxWidth="lg" sx={{ py: 4 }}>
        <Alert severity="error">
          {error || 'Video not found'}
        </Alert>
        <Button
          startIcon={<ArrowBack />}
          onClick={() => navigate('/dashboard')}
          sx={{ mt: 2 }}
        >
          Back to Dashboard
        </Button>
      </Container>
    );
  }

  return (
    <Container maxWidth="lg" sx={{ py: 4 }}>
      {/* Header */}
      <Box mb={4}>
        <Button
          startIcon={<ArrowBack />}
          onClick={() => navigate('/dashboard')}
          sx={{ mb: 2 }}
        >
          Back to Dashboard
        </Button>
        <Typography variant="h4" component="h1" gutterBottom fontWeight="bold">
          Video Details
        </Typography>
      </Box>

      <Grid container spacing={3}>
        {/* Left Column - Video Player */}
        <Grid item xs={12} md={8}>
          <VideoPlayer
            videoUrl={`/api/videos/${video.video_id}/stream`}
            title={video.filename}
          />

          {/* Processing Timeline */}
          <Paper elevation={2} sx={{ p: 3, mt: 3 }}>
            <Typography variant="h6" gutterBottom>
              Processing Timeline
            </Typography>
            <Box>
              <Box display="flex" alignItems="center" mb={2}>
                <Schedule sx={{ mr: 1, color: 'text.secondary' }} />
                <Box flexGrow={1}>
                  <Typography variant="body2" fontWeight="bold">
                    Uploaded
                  </Typography>
                  <Typography variant="caption" color="text.secondary">
                    {formatDate(video.uploaded_at)}
                  </Typography>
                </Box>
              </Box>

              {video.screened_at && (
                <Box display="flex" alignItems="center" mb={2}>
                  <Psychology sx={{ mr: 1, color: 'info.main' }} />
                  <Box flexGrow={1}>
                    <Typography variant="body2" fontWeight="bold">
                      CPU Screening Completed
                    </Typography>
                    <Typography variant="caption" color="text.secondary">
                      {formatDate(video.screened_at)}
                    </Typography>
                  </Box>
                </Box>
              )}

              {video.analyzed_at && (
                <Box display="flex" alignItems="center" mb={2}>
                  <Psychology sx={{ mr: 1, color: 'warning.main' }} />
                  <Box flexGrow={1}>
                    <Typography variant="body2" fontWeight="bold">
                      Deep Analysis Completed
                    </Typography>
                    <Typography variant="caption" color="text.secondary">
                      {formatDate(video.analyzed_at)}
                    </Typography>
                  </Box>
                </Box>
              )}

              {video.decided_at && (
                <Box display="flex" alignItems="center" mb={2}>
                  <Info sx={{ mr: 1, color: 'primary.main' }} />
                  <Box flexGrow={1}>
                    <Typography variant="body2" fontWeight="bold">
                      Decision Made
                    </Typography>
                    <Typography variant="caption" color="text.secondary">
                      {formatDate(video.decided_at)}
                    </Typography>
                  </Box>
                </Box>
              )}

              {video.reviewed_at && (
                <Box display="flex" alignItems="center">
                  <RateReview sx={{ mr: 1, color: 'success.main' }} />
                  <Box flexGrow={1}>
                    <Typography variant="body2" fontWeight="bold">
                      Human Review Completed
                    </Typography>
                    <Typography variant="caption" color="text.secondary">
                      {formatDate(video.reviewed_at)}
                    </Typography>
                  </Box>
                </Box>
              )}
            </Box>
          </Paper>
        </Grid>

        {/* Right Column - Metadata and Scores */}
        <Grid item xs={12} md={4}>
          {/* Status */}
          <Paper elevation={2} sx={{ p: 3, mb: 3 }}>
            <Typography variant="h6" gutterBottom>
              Status
            </Typography>
            <StatusBadge status={video.status} decision={video.decision} />
            <Box mt={2}>
              <Typography variant="body2" color="text.secondary">
                Decision: <strong>{video.decision}</strong>
              </Typography>
            </Box>
          </Paper>

          {/* Metadata */}
          <Paper elevation={2} sx={{ p: 3, mb: 3 }}>
            <Typography variant="h6" gutterBottom>
              Metadata
            </Typography>
            <Box>
              <Box display="flex" alignItems="center" mb={1}>
                <Storage sx={{ fontSize: 16, mr: 1, color: 'text.secondary' }} />
                <Typography variant="body2">
                  Size: {formatFileSize(video.size)}
                </Typography>
              </Box>
              <Box display="flex" alignItems="center" mb={1}>
                <Info sx={{ fontSize: 16, mr: 1, color: 'text.secondary' }} />
                <Typography variant="body2">
                  Video ID: {video.video_id.substring(0, 8)}...
                </Typography>
              </Box>
              {video.frames_analyzed && (
                <Box display="flex" alignItems="center" mb={1}>
                  <Psychology sx={{ fontSize: 16, mr: 1, color: 'text.secondary' }} />
                  <Typography variant="body2">
                    Frames Analyzed: {video.frames_analyzed}
                  </Typography>
                </Box>
              )}
              {video.screening_type && (
                <Box display="flex" alignItems="center">
                  <Info sx={{ fontSize: 16, mr: 1, color: 'text.secondary' }} />
                  <Typography variant="body2">
                    Screening Type: {video.screening_type.toUpperCase()}
                  </Typography>
                </Box>
              )}
            </Box>
          </Paper>

          {/* Analysis Scores */}
          <Paper elevation={2} sx={{ p: 3, mb: 3 }}>
            <Typography variant="h6" gutterBottom>
              Analysis Scores
            </Typography>

            {/* Risk Score */}
            <Box mb={2}>
              <Box display="flex" justifyContent="space-between" mb={0.5}>
                <Typography variant="body2">Risk Score</Typography>
                <Typography variant="body2" fontWeight="bold">
                  {(video.risk_score * 100).toFixed(1)}%
                </Typography>
              </Box>
              <LinearProgress
                variant="determinate"
                value={video.risk_score * 100}
                color={getRiskColor(video.risk_score)}
                sx={{ height: 8, borderRadius: 4 }}
              />
            </Box>

            {/* NSFW Score - Always show if it exists (not null/undefined) */}
            {(video.nsfw_score !== null && video.nsfw_score !== undefined) && (
              <Box mb={2}>
                <Box display="flex" justifyContent="space-between" mb={0.5}>
                  <Typography variant="body2">NSFW Score</Typography>
                  <Typography variant="body2" fontWeight="bold">
                    {(video.nsfw_score * 100).toFixed(1)}%
                  </Typography>
                </Box>
                <LinearProgress
                  variant="determinate"
                  value={video.nsfw_score * 100}
                  color={getRiskColor(video.nsfw_score)}
                  sx={{ height: 8, borderRadius: 4 }}
                />
              </Box>
            )}

            {/* Violence Score - Always show if it exists (not null/undefined) */}
            {(video.violence_score !== null && video.violence_score !== undefined) && (
              <Box mb={2}>
                <Box display="flex" justifyContent="space-between" mb={0.5}>
                  <Typography variant="body2">Violence Score</Typography>
                  <Typography variant="body2" fontWeight="bold">
                    {(video.violence_score * 100).toFixed(1)}%
                  </Typography>
                </Box>
                <LinearProgress
                  variant="determinate"
                  value={video.violence_score * 100}
                  color={getRiskColor(video.violence_score)}
                  sx={{ height: 8, borderRadius: 4 }}
                />
              </Box>
            )}

            {/* Final Score */}
            <Divider sx={{ my: 2 }} />
            <Box>
              <Box display="flex" justifyContent="space-between" mb={0.5}>
                <Typography variant="body2" fontWeight="bold">
                  Final Score
                </Typography>
                <Typography variant="body2" fontWeight="bold">
                  {(video.final_score * 100).toFixed(1)}%
                </Typography>
              </Box>
              <LinearProgress
                variant="determinate"
                value={video.final_score * 100}
                color={getRiskColor(video.final_score)}
                sx={{ height: 10, borderRadius: 5 }}
              />
            </Box>
          </Paper>

          {/* Human Review Notes */}
          {video.human_reviewed && video.reviewer_notes && (
            <Paper elevation={2} sx={{ p: 3, mb: 3 }}>
              <Typography variant="h6" gutterBottom>
                Review Notes
              </Typography>
              <Typography variant="body2" color="text.secondary">
                {video.reviewer_notes}
              </Typography>
              <Box mt={2}>
                <Chip
                  label="Human Reviewed"
                  size="small"
                  color="info"
                  icon={<RateReview />}
                />
              </Box>
            </Paper>
          )}

          {/* Actions */}
          <Paper elevation={2} sx={{ p: 3 }}>
            <Typography variant="h6" gutterBottom>
              Actions
            </Typography>
            <Button
              variant="outlined"
              color="error"
              startIcon={<Delete />}
              fullWidth
              onClick={handleDeleteClick}
              disabled={deleting}
            >
              {deleting ? 'Deleting...' : 'Delete Video'}
            </Button>
            <Typography variant="caption" color="text.secondary" display="block" textAlign="center" sx={{ mt: 1 }}>
              This will permanently delete the video from storage
            </Typography>
          </Paper>
        </Grid>
      </Grid>

      {/* Delete Confirmation Dialog */}
      <Dialog
        open={deleteDialogOpen}
        onClose={handleDeleteCancel}
        aria-labelledby="delete-dialog-title"
        aria-describedby="delete-dialog-description"
      >
        <DialogTitle id="delete-dialog-title">
          Delete Video?
        </DialogTitle>
        <DialogContent>
          <DialogContentText id="delete-dialog-description">
            Are you sure you want to delete "{video?.filename}"? This action cannot be undone.
            The video will be permanently removed from storage and all associated data will be deleted.
          </DialogContentText>
        </DialogContent>
        <DialogActions>
          <Button onClick={handleDeleteCancel} color="primary" disabled={deleting}>
            Cancel
          </Button>
          <Button onClick={handleDeleteConfirm} color="error" variant="contained" disabled={deleting}>
            {deleting ? 'Deleting...' : 'Delete'}
          </Button>
        </DialogActions>
      </Dialog>
    </Container>
  );
};

export default VideoDetails;
