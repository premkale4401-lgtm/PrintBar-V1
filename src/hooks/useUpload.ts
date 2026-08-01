/**
 * PrintBar — useUpload hook
 *
 * Wraps the upload service to provide:
 * - Real upload progress (0–100)
 * - Loading and error states
 * - The returned fileId and pageCount from the backend
 *
 * Used by StepUpload to replace local pdfjs-only file handling.
 */

import { useState, useCallback } from 'react';
import { uploadService, UploadResult } from '../services/upload.service';
import { PrintBarApiError } from '../lib/api';

interface UseUploadResult {
  upload: (file: File) => Promise<UploadResult | null>;
  deleteUpload: (fileId: string) => Promise<void>;
  isUploading: boolean;
  progress: number;
  error: string | null;
  errorCode: string | null;
  reset: () => void;
}

export function useUpload(): UseUploadResult {
  const [isUploading, setIsUploading] = useState(false);
  const [progress, setProgress] = useState(0);
  const [error, setError] = useState<string | null>(null);
  const [errorCode, setErrorCode] = useState<string | null>(null);

  const reset = useCallback(() => {
    setIsUploading(false);
    setProgress(0);
    setError(null);
    setErrorCode(null);
  }, []);

  const upload = useCallback(async (file: File): Promise<UploadResult | null> => {
    setIsUploading(true);
    setProgress(0);
    setError(null);
    setErrorCode(null);

    try {
      const result = await uploadService.uploadPdf(file, (pct) => {
        setProgress(pct);
      });
      return result;
    } catch (err) {
      if (err instanceof PrintBarApiError) {
        setError(err.message);
        setErrorCode(err.code);
      } else {
        setError('Upload failed. Please try again.');
        setErrorCode('SYS_UNKNOWN');
      }
      return null;
    } finally {
      setIsUploading(false);
    }
  }, []);

  const deleteUpload = useCallback(async (fileId: string): Promise<void> => {
    try {
      await uploadService.deleteUpload(fileId);
    } catch {
      // Deletion failure is non-fatal; backend will clean up via retention worker.
    }
  }, []);

  return { upload, deleteUpload, isUploading, progress, error, errorCode, reset };
}
