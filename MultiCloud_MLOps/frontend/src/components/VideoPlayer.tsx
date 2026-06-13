import React, { useState, useEffect } from 'react';
import { Box, Paper, Typography, CircularProgress, Alert } from '@mui/material';

interface VideoPlayerProps {
  videoUrl: string;
  title?: string;
}

const VideoPlayer: React.FC<VideoPlayerProps> = ({ videoUrl, title }) => {
  const [actualVideoUrl, setActualVideoUrl] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const fetchVideoUrl = async () => {
      try {
        setLoading(true);
        setError(null);
        
        // The API gateway returns JSON with the presigned URL
        const response = await fetch(videoUrl);
        
        if (response.ok) {
          const data = await response.json();
          // API returns { "url": "..." }
          if (data.url) {
            setActualVideoUrl(data.url);
          } else {
            // Fallback: if response doesn't have url field, try using response.url
            setActualVideoUrl(response.url || videoUrl);
          }
        } else {
          // If response is not ok, try to parse as JSON anyway
          try {
            const data = await response.json();
            if (data.url) {
              setActualVideoUrl(data.url);
            } else {
              throw new Error('Invalid response format');
            }
          } catch {
            // If not JSON, check for redirect
            const location = response.headers.get('Location');
            if (location) {
              setActualVideoUrl(location);
            } else {
              throw new Error(`Failed to load video: ${response.status} ${response.statusText}`);
            }
          }
        }
      } catch (err) {
        console.error('Error fetching video URL:', err);
        setError(err instanceof Error ? err.message : 'Failed to load video');
        // Fallback: try using the original URL directly
        setActualVideoUrl(videoUrl);
      } finally {
        setLoading(false);
      }
    };

    if (videoUrl) {
      fetchVideoUrl();
    }
  }, [videoUrl]);

  if (loading) {
    return (
      <Paper elevation={3} sx={{ p: 2 }}>
        {title && (
          <Typography variant="h6" gutterBottom>
            {title}
          </Typography>
        )}
        <Box display="flex" justifyContent="center" alignItems="center" minHeight="300px">
          <CircularProgress />
        </Box>
      </Paper>
    );
  }

  if (error && !actualVideoUrl) {
    return (
      <Paper elevation={3} sx={{ p: 2 }}>
        {title && (
          <Typography variant="h6" gutterBottom>
            {title}
          </Typography>
        )}
        <Alert severity="error">{error}</Alert>
      </Paper>
    );
  }

  return (
    <Paper elevation={3} sx={{ p: 2 }}>
      {title && (
        <Typography variant="h6" gutterBottom>
          {title}
        </Typography>
      )}
      <Box
        component="video"
        controls
        sx={{
          width: '100%',
          maxHeight: '500px',
          backgroundColor: '#000',
          borderRadius: 1,
        }}
        key={actualVideoUrl} // Force re-render when URL changes
      >
        <source src={actualVideoUrl || videoUrl} type="video/mp4" />
        <source src={actualVideoUrl || videoUrl} type="video/quicktime" />
        <source src={actualVideoUrl || videoUrl} type="video/x-msvideo" />
        Your browser does not support the video tag.
      </Box>
    </Paper>
  );
};

export default VideoPlayer;
