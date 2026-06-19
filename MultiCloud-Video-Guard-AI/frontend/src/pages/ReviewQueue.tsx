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
  Card,
  CardContent,
  CardActions,
  Chip,
  TextField,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  LinearProgress,
} from '@mui/material';
import {
  CheckCircle,
  Cancel,
  Refresh,
  Psychology,
  Schedule,
} from '@mui/icons-material';
import { reviewApi } from '../services/api';
import { ReviewQueueItem } from '../types';

const ReviewQueue: React.FC = () => {
  const [queue, setQueue] = useState<ReviewQueueItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selectedVideo, setSelectedVideo] = useState<ReviewQueueItem | null>(null);
  const [reviewNotes, setReviewNotes] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [success, setSuccess] = useState<string | null>(null);

  const fetchQueue = async () => {
    try {
      setLoading(true);
      setError(null);

      const response = await reviewApi.getReviewQueue();
      setQueue(response.items);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load review queue');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchQueue();
  }, []);

  const handleReview = (video: ReviewQueueItem) => {
    setSelectedVideo(video);
    setReviewNotes('');
  };

  const handleSubmitReview = async (approved: boolean) => {
    if (!selectedVideo) return;

    try {
      setSubmitting(true);
      setError(null);

      await reviewApi.submitReview(selectedVideo.video_id, approved, reviewNotes);

      setSuccess(`Video ${approved ? 'approved' : 'rejected'} successfully`);
      setSelectedVideo(null);
      setReviewNotes('');

      // Refresh queue
      await fetchQueue();

      // Clear success message after 3 seconds
      setTimeout(() => setSuccess(null), 3000);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to submit review');
    } finally {
      setSubmitting(false);
    }
  };

  const formatDate = (dateString: string): string => {
    const date = new Date(dateString);
    return date.toLocaleString();
  };

  const getRiskColor = (score: number): 'success' | 'warning' | 'error' => {
    if (score < 0.3) return 'success';
    if (score < 0.7) return 'warning';
    return 'error';
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

  return (
    <Container maxWidth="lg" sx={{ py: 4 }}>
      {/* Header */}
      <Box display="flex" justifyContent="space-between" alignItems="center" mb={4}>
        <Box>
          <Typography variant="h4" component="h1" gutterBottom fontWeight="bold">
            Review Queue
          </Typography>
          <Typography variant="body1" color="text.secondary">
            Videos flagged for human review ({queue.length} pending)
          </Typography>
        </Box>
        <Button
          variant="outlined"
          startIcon={<Refresh />}
          onClick={fetchQueue}
          disabled={loading}
        >
          Refresh
        </Button>
      </Box>

      {error && (
        <Alert severity="error" sx={{ mb: 3 }} onClose={() => setError(null)}>
          {error}
        </Alert>
      )}

      {success && (
        <Alert severity="success" sx={{ mb: 3 }} onClose={() => setSuccess(null)}>
          {success}
        </Alert>
      )}

      {/* Queue List */}
      {queue.length === 0 ? (
        <Paper elevation={1} sx={{ p: 4, textAlign: 'center' }}>
          <CheckCircle sx={{ fontSize: 64, color: 'success.main', mb: 2 }} />
          <Typography variant="h6" gutterBottom>
            Review Queue is Empty
          </Typography>
          <Typography variant="body2" color="text.secondary">
            All videos have been reviewed. Great job!
          </Typography>
        </Paper>
      ) : (
        <Grid container spacing={3}>
          {queue.map((item) => (
            <Grid item xs={12} md={6} key={item.video_id}>
              <Card elevation={2}>
                <CardContent>
                  <Box display="flex" alignItems="center" justifyContent="space-between" mb={2}>
                    <Typography variant="h6" noWrap sx={{ flexGrow: 1, mr: 2 }}>
                      {item.filename}
                    </Typography>
                    <Chip
                      label="Pending"
                      color="warning"
                      size="small"
                      icon={<Psychology />}
                    />
                  </Box>

                  <Box mb={2}>
                    <Box display="flex" alignItems="center" mb={1}>
                      <Schedule sx={{ fontSize: 16, mr: 1, color: 'text.secondary' }} />
                      <Typography variant="body2" color="text.secondary">
                        Submitted: {formatDate(item.submitted_at)}
                      </Typography>
                    </Box>
                  </Box>

                  {/* Risk Score */}
                  <Box mb={2}>
                    <Box display="flex" justifyContent="space-between" mb={0.5}>
                      <Typography variant="subtitle2">Risk Score</Typography>
                      <Typography variant="subtitle2" fontWeight="bold">
                        {(item.risk_score * 100).toFixed(1)}%
                      </Typography>
                    </Box>
                    <LinearProgress
                      variant="determinate"
                      value={item.risk_score * 100}
                      color={getRiskColor(item.risk_score)}
                      sx={{ height: 8, borderRadius: 4 }}
                    />
                  </Box>

                  {/* Final Score */}
                  <Box mb={2}>
                    <Box display="flex" justifyContent="space-between" mb={0.5}>
                      <Typography variant="subtitle2">Final Score</Typography>
                      <Typography variant="subtitle2" fontWeight="bold">
                        {(item.final_score * 100).toFixed(1)}%
                      </Typography>
                    </Box>
                    <LinearProgress
                      variant="determinate"
                      value={item.final_score * 100}
                      color={getRiskColor(item.final_score)}
                      sx={{ height: 8, borderRadius: 4 }}
                    />
                  </Box>

                  {/* Flagged Frames */}
                  {item.flagged_frames && item.flagged_frames.length > 0 && (
                    <Box>
                      <Typography variant="caption" color="text.secondary">
                        {item.flagged_frames.length} frame(s) flagged
                      </Typography>
                    </Box>
                  )}

                  {/* AI Summary Available */}
                  {item.ai_summary_available && (
                    <Box mt={1}>
                      <Chip
                        label="AI Summary Available"
                        size="small"
                        color="info"
                        variant="outlined"
                      />
                    </Box>
                  )}
                </CardContent>

                <CardActions sx={{ justifyContent: 'space-between', px: 2, pb: 2 }}>
                  <Button
                    variant="contained"
                    color="success"
                    startIcon={<CheckCircle />}
                    onClick={() => handleReview(item)}
                    fullWidth
                    sx={{ mr: 1 }}
                  >
                    Review
                  </Button>
                </CardActions>
              </Card>
            </Grid>
          ))}
        </Grid>
      )}

      {/* Review Dialog */}
      <Dialog
        open={selectedVideo !== null}
        onClose={() => !submitting && setSelectedVideo(null)}
        maxWidth="sm"
        fullWidth
      >
        {selectedVideo && (
          <>
            <DialogTitle>
              Review Video: {selectedVideo.filename}
            </DialogTitle>
            <DialogContent>
              <Box mb={3}>
                <Typography variant="subtitle2" gutterBottom>
                  Risk Score: {(selectedVideo.risk_score * 100).toFixed(1)}%
                </Typography>
                <LinearProgress
                  variant="determinate"
                  value={selectedVideo.risk_score * 100}
                  color={getRiskColor(selectedVideo.risk_score)}
                  sx={{ height: 8, borderRadius: 4, mb: 2 }}
                />

                <Typography variant="subtitle2" gutterBottom>
                  Final Score: {(selectedVideo.final_score * 100).toFixed(1)}%
                </Typography>
                <LinearProgress
                  variant="determinate"
                  value={selectedVideo.final_score * 100}
                  color={getRiskColor(selectedVideo.final_score)}
                  sx={{ height: 8, borderRadius: 4 }}
                />
              </Box>

              <TextField
                fullWidth
                multiline
                rows={4}
                label="Review Notes (Optional)"
                placeholder="Add notes about your review decision..."
                value={reviewNotes}
                onChange={(e) => setReviewNotes(e.target.value)}
                disabled={submitting}
              />

              <Typography variant="caption" color="text.secondary" display="block" mt={1}>
                Your decision will be recorded and the video will be moved out of the review queue.
              </Typography>
            </DialogContent>
            <DialogActions sx={{ px: 3, pb: 2 }}>
              <Button
                onClick={() => setSelectedVideo(null)}
                disabled={submitting}
              >
                Cancel
              </Button>
              <Button
                variant="contained"
                color="error"
                startIcon={<Cancel />}
                onClick={() => handleSubmitReview(false)}
                disabled={submitting}
              >
                Reject
              </Button>
              <Button
                variant="contained"
                color="success"
                startIcon={<CheckCircle />}
                onClick={() => handleSubmitReview(true)}
                disabled={submitting}
              >
                Approve
              </Button>
            </DialogActions>
          </>
        )}
      </Dialog>
    </Container>
  );
};

export default ReviewQueue;
