import React from 'react';
import { BrowserRouter as Router, Routes, Route, Navigate } from 'react-router-dom';
import {
  AppBar,
  Toolbar,
  Typography,
  Container,
  Box,
  Button,
  CssBaseline,
  ThemeProvider,
  createTheme,
} from '@mui/material';
import {
  CloudUpload,
  Dashboard as DashboardIcon,
  RateReview,
  Shield,
} from '@mui/icons-material';
import { useNavigate, useLocation } from 'react-router-dom';

// Pages
import Upload from './pages/Upload';
import Dashboard from './pages/Dashboard';
import ReviewQueue from './pages/ReviewQueue';
import VideoDetails from './pages/VideoDetails';

// Create Material-UI theme
const theme = createTheme({
  palette: {
    primary: {
      main: '#1976d2',
    },
    secondary: {
      main: '#dc004e',
    },
    success: {
      main: '#4caf50',
    },
    warning: {
      main: '#ff9800',
    },
    error: {
      main: '#f44336',
    },
  },
  typography: {
    fontFamily: '"Roboto", "Helvetica", "Arial", sans-serif',
    h4: {
      fontWeight: 700,
    },
    h6: {
      fontWeight: 600,
    },
  },
  components: {
    MuiButton: {
      styleOverrides: {
        root: {
          textTransform: 'none',
          borderRadius: 8,
        },
      },
    },
    MuiCard: {
      styleOverrides: {
        root: {
          borderRadius: 12,
        },
      },
    },
    MuiPaper: {
      styleOverrides: {
        root: {
          borderRadius: 12,
        },
      },
    },
  },
});

const Navigation: React.FC = () => {
  const navigate = useNavigate();
  const location = useLocation();

  const navItems = [
    { label: 'Upload', path: '/upload', icon: <CloudUpload /> },
    { label: 'Dashboard', path: '/dashboard', icon: <DashboardIcon /> },
    { label: 'Review Queue', path: '/review', icon: <RateReview /> },
  ];

  return (
    <AppBar position="static" elevation={2}>
      <Toolbar>
        <Shield sx={{ mr: 2, fontSize: 32 }} />
        <Typography variant="h6" component="div" sx={{ flexGrow: 1, fontWeight: 700 }}>
          Guardian AI
        </Typography>
        <Box sx={{ display: 'flex', gap: 1 }}>
          {navItems.map((item) => (
            <Button
              key={item.path}
              color="inherit"
              startIcon={item.icon}
              onClick={() => navigate(item.path)}
              sx={{
                backgroundColor: location.pathname === item.path ? 'rgba(255,255,255,0.1)' : 'transparent',
                '&:hover': {
                  backgroundColor: 'rgba(255,255,255,0.2)',
                },
              }}
            >
              {item.label}
            </Button>
          ))}
        </Box>
      </Toolbar>
    </AppBar>
  );
};

const AppContent: React.FC = () => {
  return (
    <>
      <Navigation />
      <Box sx={{ minHeight: 'calc(100vh - 64px)', backgroundColor: '#f5f5f5' }}>
        <Routes>
          <Route path="/" element={<Navigate to="/upload" replace />} />
          <Route path="/upload" element={<Upload />} />
          <Route path="/dashboard" element={<Dashboard />} />
          <Route path="/review" element={<ReviewQueue />} />
          <Route path="/video/:videoId" element={<VideoDetails />} />
        </Routes>
      </Box>
    </>
  );
};

const App: React.FC = () => {
  return (
    <ThemeProvider theme={theme}>
      <CssBaseline />
      <Router>
        <AppContent />
      </Router>
    </ThemeProvider>
  );
};

export default App;
