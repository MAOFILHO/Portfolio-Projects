import React from 'react';
import { Chip } from '@mui/material';
import {
  CheckCircle,
  Cancel,
  HourglassEmpty,
  RateReview,
  CloudUpload,
  Psychology,
} from '@mui/icons-material';
import { VideoStatus } from '../types';

interface StatusBadgeProps {
  status: VideoStatus;
  decision?: 'approve' | 'reject' | 'review' | 'pending';
  size?: 'small' | 'medium';
}

const StatusBadge: React.FC<StatusBadgeProps> = ({ status, decision, size = 'medium' }) => {
  const getStatusConfig = (status: VideoStatus, decision?: string) => {
    // If decision is pending, show Processing regardless of status
    if (decision === 'pending') {
      return {
        label: 'Processing',
        color: 'default' as const,
        icon: <HourglassEmpty />,
      };
    }

    switch (status) {
      case 'approved':
      case 'approve':
        return {
          label: 'Approved',
          color: 'success' as const,
          icon: <CheckCircle />,
        };
      case 'rejected':
      case 'reject':
        return {
          label: 'Rejected',
          color: 'error' as const,
          icon: <Cancel />,
        };
      case 'review':
        return {
          label: 'Pending Review',
          color: 'warning' as const,
          icon: <RateReview />,
        };
      case 'uploaded':
        return {
          label: 'Uploaded',
          color: 'info' as const,
          icon: <CloudUpload />,
        };
      case 'screened':
        // If screened but decision is pending, show Processing
        if (decision === 'pending') {
          return {
            label: 'Processing',
            color: 'default' as const,
            icon: <HourglassEmpty />,
          };
        }
        return {
          label: 'Screened',
          color: 'info' as const,
          icon: <Psychology />,
        };
      case 'analyzed':
        // If analyzed but decision is pending, show Processing
        if (decision === 'pending') {
          return {
            label: 'Processing',
            color: 'default' as const,
            icon: <HourglassEmpty />,
          };
        }
        return {
          label: 'Analyzed',
          color: 'info' as const,
          icon: <Psychology />,
        };
      case 'processing':
      case 'gpu_queued':
        return {
          label: 'Processing',
          color: 'default' as const,
          icon: <HourglassEmpty />,
        };
      default:
        return {
          label: status,
          color: 'default' as const,
          icon: <HourglassEmpty />,
        };
    }
  };

  const config = getStatusConfig(status, decision);

  return (
    <Chip
      label={config.label}
      color={config.color}
      size={size}
      icon={config.icon}
      sx={{ fontWeight: 500 }}
    />
  );
};

export default StatusBadge;
