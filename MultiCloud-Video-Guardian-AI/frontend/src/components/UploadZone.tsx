import React, { useCallback, useState } from 'react';
import {
  Box,
  Typography,
  Paper,
  LinearProgress,
  Alert,
  Button,
} from '@mui/material';
import { CloudUpload } from '@mui/icons-material';

interface UploadZoneProps {
  onUpload: (file: File) => Promise<void>;
  acceptedFormats?: string[];
  maxSizeMB?: number;
}

const UploadZone: React.FC<UploadZoneProps> = ({
  onUpload,
  acceptedFormats = ['.mp4', '.mov', '.avi'],
  maxSizeMB = 500,
}) => {
  const [isDragging, setIsDragging] = useState(false);
  const [isUploading, setIsUploading] = useState(false);
  const [uploadProgress, setUploadProgress] = useState(0);
  const [error, setError] = useState<string | null>(null);

  const validateFile = (file: File): string | null => {
    // Check file type
    const fileExtension = '.' + file.name.split('.').pop()?.toLowerCase();
    if (!acceptedFormats.includes(fileExtension)) {
      return `Invalid file format. Accepted formats: ${acceptedFormats.join(', ')}`;
    }

    // Check file size
    const fileSizeMB = file.size / (1024 * 1024);
    if (fileSizeMB > maxSizeMB) {
      return `File too large. Maximum size: ${maxSizeMB}MB`;
    }

    return null;
  };

  const handleFile = useCallback(
    async (file: File) => {
      setError(null);

      // Validate file
      const validationError = validateFile(file);
      if (validationError) {
        setError(validationError);
        return;
      }

      try {
        setIsUploading(true);
        setUploadProgress(0);

        // Simulate progress (in real implementation, use axios onUploadProgress)
        const progressInterval = setInterval(() => {
          setUploadProgress((prev) => {
            if (prev >= 90) {
              clearInterval(progressInterval);
              return 90;
            }
            return prev + 10;
          });
        }, 200);

        await onUpload(file);

        clearInterval(progressInterval);
        setUploadProgress(100);

        // Reset after success
        setTimeout(() => {
          setIsUploading(false);
          setUploadProgress(0);
        }, 1500);
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Upload failed');
        setIsUploading(false);
        setUploadProgress(0);
      }
    },
    [onUpload]
  );

  const handleDrop = useCallback(
    (e: React.DragEvent<HTMLDivElement>) => {
      e.preventDefault();
      setIsDragging(false);

      const files = Array.from(e.dataTransfer.files);
      if (files.length > 0) {
        handleFile(files[0]);
      }
    },
    [handleFile]
  );

  const handleDragOver = useCallback((e: React.DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    setIsDragging(true);
  }, []);

  const handleDragLeave = useCallback((e: React.DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    setIsDragging(false);
  }, []);

  const handleFileInput = useCallback(
    (e: React.ChangeEvent<HTMLInputElement>) => {
      const files = e.target.files;
      if (files && files.length > 0) {
        handleFile(files[0]);
      }
    },
    [handleFile]
  );

  return (
    <Box>
      <Paper
        elevation={isDragging ? 8 : 2}
        onDrop={handleDrop}
        onDragOver={handleDragOver}
        onDragLeave={handleDragLeave}
        sx={{
          p: 4,
          textAlign: 'center',
          border: isDragging ? '2px dashed #1976d2' : '2px dashed #ccc',
          backgroundColor: isDragging ? '#e3f2fd' : '#fafafa',
          cursor: 'pointer',
          transition: 'all 0.3s ease',
          '&:hover': {
            backgroundColor: '#f5f5f5',
            borderColor: '#1976d2',
          },
        }}
      >
        <input
          type="file"
          id="file-upload"
          accept={acceptedFormats.join(',')}
          onChange={handleFileInput}
          style={{ display: 'none' }}
          disabled={isUploading}
        />

        <label htmlFor="file-upload" style={{ cursor: 'pointer' }}>
          <CloudUpload sx={{ fontSize: 64, color: '#1976d2', mb: 2 }} />
          <Typography variant="h6" gutterBottom>
            {isDragging ? 'Drop video here' : 'Drag & drop video here'}
          </Typography>
          <Typography variant="body2" color="text.secondary" gutterBottom>
            or
          </Typography>
          <Button
            variant="contained"
            component="span"
            disabled={isUploading}
            sx={{ mt: 1 }}
          >
            Browse Files
          </Button>
          <Typography variant="caption" display="block" sx={{ mt: 2 }} color="text.secondary">
            Accepted formats: {acceptedFormats.join(', ')} | Max size: {maxSizeMB}MB
          </Typography>
        </label>
      </Paper>

      {isUploading && (
        <Box sx={{ mt: 2 }}>
          <Typography variant="body2" gutterBottom>
            Uploading... {uploadProgress}%
          </Typography>
          <LinearProgress variant="determinate" value={uploadProgress} />
        </Box>
      )}

      {error && (
        <Alert severity="error" sx={{ mt: 2 }} onClose={() => setError(null)}>
          {error}
        </Alert>
      )}
    </Box>
  );
};

export default UploadZone;
