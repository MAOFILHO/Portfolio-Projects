import React, { useState } from 'react';
import {
  Container,
  Typography,
  Box,
  Paper,
  Alert,
  Button,
  Divider,
} from '@mui/material';
import { CheckCircle, ContentCopy } from '@mui/icons-material';
import UploadZone from '../components/UploadZone';
import { ingestionApi } from '../services/api';
import { useNavigate } from 'react-router-dom';

const Upload: React.FC = () => {
  const navigate = useNavigate();
  const [uploadSuccess, setUploadSuccess] = useState(false);
  const [jobId, setJobId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const handleUpload = async (file: File) => {
    try {
      setError(null);
      setUploadSuccess(false);

      const response = await ingestionApi.uploadVideo(file);
      
      setJobId(response.job_id);
      setUploadSuccess(true);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Upload failed');
      setUploadSuccess(false);
    }
  };

  const copyToClipboard = () => {
    if (jobId) {
      navigator.clipboard.writeText(jobId);
    }
  };

  const handleViewDashboard = () => {
    navigate('/dashboard');
  };

  return (
    <Container maxWidth="md" sx={{ py: 4 }}>
      <Box mb={4}>
        <Typography variant="h4" component="h1" gutterBottom fontWeight="bold">
          Upload Video for Moderation
        </Typography>
        <Typography variant="body1" color="text.secondary">
          Upload a video file to analyze for inappropriate content. Our AI-powered system will
          screen the video and provide moderation results.
        </Typography>
      </Box>

      <UploadZone onUpload={handleUpload} />

      {uploadSuccess && jobId && (
        <Box mt={3}>
          <Alert
            severity="success"
            icon={<CheckCircle />}
            action={
              <Button color="inherit" size="small" onClick={handleViewDashboard}>
                View Dashboard
              </Button>
            }
          >
            <Typography variant="subtitle2" gutterBottom>
              Video uploaded successfully!
            </Typography>
            <Typography variant="body2">
              Your video is now being processed. You can track its status in the dashboard.
            </Typography>
          </Alert>

          <Paper elevation={2} sx={{ p: 3, mt: 2 }}>
            <Typography variant="subtitle2" gutterBottom>
              Video ID
            </Typography>
            <Box display="flex" alignItems="center" gap={1}>
              <Typography
                variant="body2"
                sx={{
                  fontFamily: 'monospace',
                  backgroundColor: '#f5f5f5',
                  p: 1,
                  borderRadius: 1,
                  flexGrow: 1,
                  wordBreak: 'break-all',
                }}
              >
                {jobId}
              </Typography>
              <Button
                variant="outlined"
                size="small"
                startIcon={<ContentCopy />}
                onClick={copyToClipboard}
              >
                Copy
              </Button>
            </Box>
            <Typography variant="caption" color="text.secondary" display="block" mt={1}>
              Track processing status on the dashboard
            </Typography>
          </Paper>
        </Box>
      )}

      {error && (
        <Alert severity="error" sx={{ mt: 3 }} onClose={() => setError(null)}>
          {error}
        </Alert>
      )}

      <Divider sx={{ my: 4 }} />

      <Box>
        <Typography variant="h6" gutterBottom>
          How it works
        </Typography>
        <Box component="ol" sx={{ pl: 2 }}>
          <Typography component="li" variant="body2" paragraph>
            <strong>Upload:</strong> Select or drag & drop your video file (MP4, MOV, or AVI, max 500MB)
          </Typography>
          <Typography component="li" variant="body2" paragraph>
            <strong>Fast Screening:</strong> CPU-based analysis detects motion, scenes, and initial risk assessment
          </Typography>
          <Typography component="li" variant="body2" paragraph>
            <strong>Deep Analysis:</strong> High-risk videos undergo deep learning analysis (CPU in this setup) for NSFW content and violence
          </Typography>
          <Typography component="li" variant="body2" paragraph>
            <strong>Decision:</strong> Automated policy engine approves, rejects, or flags for human review
          </Typography>
          <Typography component="li" variant="body2" paragraph>
            <strong>Review:</strong> Videos with moderate risk scores are reviewed by human moderators
          </Typography>
        </Box>
      </Box>
    </Container>
  );
};

export default Upload;
