/**
 * PrintBar — Upload Service
 *
 * POST   /api/v1/uploads        → upload a PDF file (multipart/form-data)
 * DELETE /api/v1/uploads/{id}   → delete a file
 *
 * Uses axios directly (not apiFetch) to support onUploadProgress callbacks.
 */

import { apiClient } from '../lib/api';
import { sessionService } from './session.service';

export interface UploadResult {
  fileId: string;
  pageCount: number;
  fileSizeBytes: number;
  sha256: string;
  expiresAt: string;
  originalFilename: string;
}

export interface UploadProgressCallback {
  (percentage: number): void;
}

export const uploadService = {
  /**
   * Uploads a PDF file to the backend.
   * Auto-initializes a guest session if none exists.
   *
   * @param file - The File object from the browser's file input.
   * @param onProgress - Called with 0–100 as the upload progresses.
   * @returns UploadResult with fileId and pageCount.
   */
  async uploadPdf(
    file: File,
    onProgress?: UploadProgressCallback,
  ): Promise<UploadResult> {
    // Ensure active guest session token exists before upload
    if (!sessionService.hasActiveSession()) {
      await sessionService.createSession();
    }

    const formData = new FormData();
    formData.append('file', file, file.name);

    const response = await apiClient.post<{ success: true; data: UploadResult }>(
      '/uploads',
      formData,
      {
        headers: {
          'Content-Type': 'multipart/form-data',
        },
        onUploadProgress: (progressEvent) => {
          if (progressEvent.total && onProgress) {
            const pct = Math.round(
              (progressEvent.loaded * 100) / progressEvent.total,
            );
            onProgress(pct);
          }
        },
      },
    );

    return response.data.data;
  },

  /**
   * Deletes a previously uploaded file from Supabase Storage.
   * Per privacy policy, the DB record is retained but storage is freed.
   */
  async deleteUpload(fileId: string): Promise<void> {
    await apiClient.delete(`/uploads/${fileId}`);
  },
};
