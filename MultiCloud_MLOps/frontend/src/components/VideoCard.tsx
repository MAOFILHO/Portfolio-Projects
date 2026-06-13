import React from 'react';
import {
  Card,
  CardContent,
  CardActions,
  Typography,
  Button,
  Box,
  Chip,
  LinearProgress,
} from '@mui/material';
import {
  Videocam,
  Info,
  Schedule,
  Storage,
} from '@mui/icons-material';
import { Video } from '../types';
import StatusBadge from './StatusBadge';
import { useNavigate } from 'react-router-dom';

interface VideoCardProps {
  video: Video;
}

const VideoCard: React.FC<VideoCardProps> = ({ video }) => {
  const navigate = useNavigate();

  const formatFileSize = (bytes: number): string => {
    if (bytes === 0) return '0 Bytes';
    const k = 1024;
    const sizes = ['Bytes', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return Math.round(bytes / Math.pow(k, i) * 100) / 100 + ' ' + sizes[i];
  };

  const formatDate = (dateString: string): string => {
    const date = new Date(dateString);
    return date.toLocaleString();
  };

  const getRiskColor = (score: number): string => {
    if (score < 0.3) return 'success';
    if (score < 0.7) return 'warning';
    return 'error';
  };

  return (
    <Card
      elevation={2}
      sx={{
        height: '100%',
        display: 'flex',
        flexDirection: 'column',
        transition: 'transform 0.2s, box-shadow 0.2s',
        '&:hover': {
          transform: 'translateY(-4px)',
          boxShadow: 4,
        },
      }}
    >
      <CardContent sx={{ flexGrow: 1 }}>
        {/* Header */}
        <Box display="flex" alignItems="center" mb={2}>
          <Videocam sx={{ mr: 1, color: 'primary.main' }} />
          <Typography variant="h6" component="div" noWrap sx={{ flexGrow: 1 }}>
            {video.filename}
          </Typography>
        </Box>

        {/* Status Badge */}
        <Box mb={2}>
          <StatusBadge status={video.status} decision={video.decision} />
        </Box>

        {/* Metadata */}
        <Box mb={2}>
          <Box display="flex" alignItems="center" mb={1}>
            <Storage sx={{ fontSize: 16, mr: 1, color: 'text.secondary' }} />
            <Typography variant="body2" color="text.secondary">
              {formatFileSize(video.size)}
            </Typography>
          </Box>
          <Box display="flex" alignItems="center">
            <Schedule sx={{ fontSize: 16, mr: 1, color: 'text.secondary' }} />
            <Typography variant="body2" color="text.secondary">
              {formatDate(video.uploaded_at)}
            </Typography>
          </Box>
        </Box>

        {/* Scores */}
        {video.final_score > 0 && (
          <Box>
            <Typography variant="subtitle2" gutterBottom>
              Analysis Scores
            </Typography>
            
            <Box mb={1}>
              <Box display="flex" justifyContent="space-between" mb={0.5}>
                <Typography variant="caption">Risk Score</Typography>
                <Typography variant="caption" fontWeight="bold">
                  {(video.risk_score * 100).toFixed(1)}%
                </Typography>
              </Box>
              <LinearProgress
                variant="determinate"
                value={video.risk_score * 100}
                color={getRiskColor(video.risk_score) as any}
                sx={{ height: 6, borderRadius: 3 }}
              />
            </Box>

            {(video.nsfw_score !== null && video.nsfw_score !== undefined) && (
              <Box mb={1}>
                <Box display="flex" justifyContent="space-between" mb={0.5}>
                  <Typography variant="caption">NSFW Score</Typography>
                  <Typography variant="caption" fontWeight="bold">
                    {(video.nsfw_score * 100).toFixed(1)}%
                  </Typography>
                </Box>
                <LinearProgress
                  variant="determinate"
                  value={video.nsfw_score * 100}
                  color={getRiskColor(video.nsfw_score) as any}
                  sx={{ height: 6, borderRadius: 3 }}
                />
              </Box>
            )}

            {(video.violence_score !== null && video.violence_score !== undefined) && (
              <Box mb={1}>
                <Box display="flex" justifyContent="space-between" mb={0.5}>
                  <Typography variant="caption">Violence Score</Typography>
                  <Typography variant="caption" fontWeight="bold">
                    {(video.violence_score * 100).toFixed(1)}%
                  </Typography>
                </Box>
                <LinearProgress
                  variant="determinate"
                  value={video.violence_score * 100}
                  color={getRiskColor(video.violence_score) as any}
                  sx={{ height: 6, borderRadius: 3 }}
                />
              </Box>
            )}
          </Box>
        )}

        {/* Additional Info */}
        {video.human_reviewed && (
          <Box mt={2}>
            <Chip
              label="Human Reviewed"
              size="small"
              color="info"
              variant="outlined"
            />
          </Box>
        )}
      </CardContent>

      <CardActions>
        <Button
          size="small"
          startIcon={<Info />}
          onClick={() => navigate(`/video/${video.video_id}`)}
          fullWidth
        >
          View Details
        </Button>
      </CardActions>
    </Card>
  );
};

export default VideoCard;
