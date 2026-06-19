import React, { useState, useEffect } from 'react';
import {
  Container,
  Typography,
  Box,
  Grid,
  Paper,
  Card,
  CardContent,
  CircularProgress,
  Alert,
  Tabs,
  Tab,
  Button,
  TextField,
  InputAdornment,
} from '@mui/material';
import {
  VideoLibrary,
  CheckCircle,
  Cancel,
  RateReview,
  HourglassEmpty,
  Refresh,
  Search,
} from '@mui/icons-material';
import { videoApi, dashboardApi } from '../services/api';
import { Video } from '../types';
import VideoCard from '../components/VideoCard';

interface TabPanelProps {
  children?: React.ReactNode;
  index: number;
  value: number;
}

const TabPanel: React.FC<TabPanelProps> = ({ children, value, index }) => {
  return (
    <div role="tabpanel" hidden={value !== index}>
      {value === index && <Box sx={{ py: 3 }}>{children}</Box>}
    </div>
  );
};

const Dashboard: React.FC = () => {
  const [videos, setVideos] = useState<Video[]>([]);
  const [filteredVideos, setFilteredVideos] = useState<Video[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [tabValue, setTabValue] = useState(0);
  const [searchQuery, setSearchQuery] = useState('');
  const [stats, setStats] = useState({
    total: 0,
    approved: 0,
    rejected: 0,
    pending_review: 0,
    processing: 0,
  });

  const fetchData = async () => {
    try {
      setLoading(true);
      setError(null);

      const [videosData, statsData] = await Promise.all([
        videoApi.getAllVideos(),
        dashboardApi.getStats(),
      ]);

      setVideos(videosData);
      setFilteredVideos(videosData);
      setStats(statsData);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load data');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchData();
  }, []);

  useEffect(() => {
    // Filter videos based on tab and search query
    let filtered = videos;

    // Filter by tab
    switch (tabValue) {
      case 1: // Approved
        filtered = filtered.filter((v) => v.status === 'approved');
        break;
      case 2: // Rejected
        filtered = filtered.filter((v) => v.status === 'rejected');
        break;
      case 3: // Pending Review
        filtered = filtered.filter((v) => v.status === 'review');
        break;
      case 4: // Processing
        filtered = filtered.filter((v) => {
          // Include videos that are actively processing OR have pending decisions
          const isProcessingStatus = ['uploaded', 'screened', 'analyzed', 'processing', 'gpu_queued'].includes(v.status);
          const hasPendingDecision = v.decision === 'pending';
          // Show in Processing if status indicates processing OR decision is pending
          return isProcessingStatus || hasPendingDecision;
        });
        break;
      default: // All
        break;
    }

    // Filter by search query
    if (searchQuery) {
      filtered = filtered.filter((v) =>
        v.filename.toLowerCase().includes(searchQuery.toLowerCase()) ||
        v.video_id.toLowerCase().includes(searchQuery.toLowerCase())
      );
    }

    setFilteredVideos(filtered);
  }, [tabValue, searchQuery, videos]);

  const handleTabChange = (_event: React.SyntheticEvent, newValue: number) => {
    setTabValue(newValue);
  };

  const StatCard = ({ title, value, icon, color }: any) => (
    <Card elevation={2}>
      <CardContent>
        <Box display="flex" alignItems="center" justifyContent="space-between">
          <Box>
            <Typography variant="h4" fontWeight="bold" color={color}>
              {value}
            </Typography>
            <Typography variant="body2" color="text.secondary">
              {title}
            </Typography>
          </Box>
          <Box
            sx={{
              backgroundColor: `${color}.lighter`,
              borderRadius: 2,
              p: 1.5,
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
            }}
          >
            {icon}
          </Box>
        </Box>
      </CardContent>
    </Card>
  );

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
            Dashboard
          </Typography>
          <Typography variant="body1" color="text.secondary">
            Monitor and manage your video moderation queue
          </Typography>
        </Box>
        <Button
          variant="outlined"
          startIcon={<Refresh />}
          onClick={fetchData}
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

      {/* Statistics Cards */}
      <Grid container spacing={3} mb={4}>
        <Grid item xs={12} sm={6} md={2.4}>
          <StatCard
            title="Total Videos"
            value={stats.total}
            icon={<VideoLibrary sx={{ fontSize: 32, color: 'primary.main' }} />}
            color="primary"
          />
        </Grid>
        <Grid item xs={12} sm={6} md={2.4}>
          <StatCard
            title="Approved"
            value={stats.approved}
            icon={<CheckCircle sx={{ fontSize: 32, color: 'success.main' }} />}
            color="success"
          />
        </Grid>
        <Grid item xs={12} sm={6} md={2.4}>
          <StatCard
            title="Rejected"
            value={stats.rejected}
            icon={<Cancel sx={{ fontSize: 32, color: 'error.main' }} />}
            color="error"
          />
        </Grid>
        <Grid item xs={12} sm={6} md={2.4}>
          <StatCard
            title="Pending Review"
            value={stats.pending_review}
            icon={<RateReview sx={{ fontSize: 32, color: 'warning.main' }} />}
            color="warning"
          />
        </Grid>
        <Grid item xs={12} sm={6} md={2.4}>
          <StatCard
            title="Processing"
            value={stats.processing}
            icon={<HourglassEmpty sx={{ fontSize: 32, color: 'info.main' }} />}
            color="info"
          />
        </Grid>
      </Grid>

      {/* Search and Filters */}
      <Paper elevation={2} sx={{ mb: 3 }}>
        <Box p={2}>
          <TextField
            fullWidth
            placeholder="Search by filename or video ID..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            InputProps={{
              startAdornment: (
                <InputAdornment position="start">
                  <Search />
                </InputAdornment>
              ),
            }}
          />
        </Box>

        <Tabs value={tabValue} onChange={handleTabChange} sx={{ borderTop: 1, borderColor: 'divider' }}>
          <Tab label={`All (${videos.length})`} />
          <Tab label={`Approved (${stats.approved})`} />
          <Tab label={`Rejected (${stats.rejected})`} />
          <Tab label={`Pending Review (${stats.pending_review})`} />
          <Tab label={`Processing (${stats.processing})`} />
        </Tabs>
      </Paper>

      {/* Video Grid */}
      <TabPanel value={tabValue} index={tabValue}>
        {filteredVideos.length === 0 ? (
          <Paper elevation={1} sx={{ p: 4, textAlign: 'center' }}>
            <Typography variant="h6" color="text.secondary">
              No videos found
            </Typography>
            <Typography variant="body2" color="text.secondary" mt={1}>
              {searchQuery
                ? 'Try adjusting your search query'
                : 'Upload a video to get started'}
            </Typography>
          </Paper>
        ) : (
          <Grid container spacing={3}>
            {filteredVideos.map((video) => (
              <Grid item xs={12} sm={6} md={4} key={video.video_id}>
                <VideoCard video={video} />
              </Grid>
            ))}
          </Grid>
        )}
      </TabPanel>
    </Container>
  );
};

export default Dashboard;
