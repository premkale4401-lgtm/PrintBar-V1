import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { UploadedFile } from '../../types';
import { useUpload } from '../../hooks/useUpload';
import { useGuestSession } from '../../hooks/useGuestSession';
import { useToast } from '../Toast';
import { 
  Upload, 
  FileText, 
  CheckCircle2, 
  Trash2, 
  ArrowRight, 
  AlertCircle,
  X,
  Info,
  CloudUpload,
  Loader2,
  Plus,
  Files,
  ShieldCheck,
  Sparkles,
  Lock,
  Zap,
  Check
} from 'lucide-react';

import * as pdfjsLib from 'pdfjs-dist';

pdfjsLib.GlobalWorkerOptions.workerSrc = `https://unpkg.com/pdfjs-dist@${pdfjsLib.version}/build/pdf.worker.min.mjs`;

interface StepUploadProps {
  uploadedFile?: UploadedFile | null;
  uploadedFiles?: UploadedFile[];
  onSelectFile: (file: UploadedFile) => void;
  onSelectFiles?: (files: UploadedFile[]) => void;
  onRemoveFileItem?: (id: string) => void;
  onRemoveFile: () => void;
  onNext: () => void;
}

export const StepUpload: React.FC<StepUploadProps> = ({
  uploadedFile,
  uploadedFiles = [],
  onSelectFile,
  onSelectFiles,
  onRemoveFileItem,
  onRemoveFile,
  onNext,
}) => {
  const navigate = useNavigate();
  const [isDragging, setIsDragging] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [uploadingFilesCount, setUploadingFilesCount] = useState(0);
  useGuestSession(); // Pre-warm guest session token on kiosk upload page
  const { upload: uploadToBackend, isUploading, progress: uploadProgress, error: uploadError } = useUpload();
  const { showToast } = useToast();

  // Active files array combines prop uploadedFiles and fallback uploadedFile
  const activeFilesList: UploadedFile[] = uploadedFiles.length > 0 
    ? uploadedFiles 
    : (uploadedFile ? [uploadedFile] : []);

  const ALLOWED_EXTENSIONS = ['pdf', 'doc', 'docx', 'jpg', 'jpeg', 'png'];
  const MAX_FILE_SIZE = 25 * 1024 * 1024; // 25MB

  const processFiles = async (files: FileList | File[]) => {
    const fileArray = Array.from(files);
    if (fileArray.length === 0) return;

    // Check sizes & extensions
    const invalidTypeFiles = fileArray.filter(f => {
      const ext = f.name.split('.').pop()?.toLowerCase() || '';
      return !ALLOWED_EXTENSIONS.includes(ext);
    });

    if (invalidTypeFiles.length > 0) {
      setErrorMessage(`Unsupported file format detected (${invalidTypeFiles.map(f => f.name).join(', ')}). Please upload PDF, DOC, DOCX, JPG, or PNG files.`);
      return;
    }

    const emptyFiles = fileArray.filter(f => f.size === 0);
    if (emptyFiles.length > 0) {
      setErrorMessage(`Cannot upload empty files. The following file(s) are empty: ${emptyFiles.map(f => f.name).join(', ')}.`);
      return;
    }

    const oversizedFiles = fileArray.filter(f => f.size > MAX_FILE_SIZE);
    if (oversizedFiles.length > 0) {
      setErrorMessage(
        `File size limit exceeded! The following file(s) exceed the 25MB limit: ${oversizedFiles.map(f => `${f.name} (${(f.size / (1024 * 1024)).toFixed(1)}MB)`).join(', ')}. Maximum allowed size is 25MB per file.`
      );
      return;
    }

    setErrorMessage(null);
    setUploadingFilesCount(fileArray.length);

    const newUploadedFiles: UploadedFile[] = [];

    for (const file of fileArray) {
      const ext = file.name.split('.').pop()?.toLowerCase() || '';
      const previewUrl = URL.createObjectURL(file);
      const isImage = ['jpg', 'jpeg', 'png', 'webp', 'gif'].includes(ext);
      const isPdf = ext === 'pdf';
      const isDoc = ['doc', 'docx'].includes(ext);

      // Verify PDF header locally
      if (isPdf) {
        try {
          const slice = file.slice(0, 5);
          const headerBuffer = await slice.arrayBuffer();
          const headerString = new TextDecoder().decode(headerBuffer);
          if (headerString !== '%PDF-') {
            setErrorMessage(`The file "${file.name}" is corrupted or not a valid PDF document.`);
            setUploadingFilesCount(0);
            return;
          }
        } catch (err) {
          setErrorMessage(`Failed to read "${file.name}". The file might be corrupted.`);
          setUploadingFilesCount(0);
          return;
        }
      }

      // For PDFs: get page count from pdfjs for the preview, then upload to backend.
      let localPageCount = isImage ? 1 : 1;

      if (isPdf) {
        try {
          const arrayBuffer = await file.arrayBuffer();
          const pdf = await pdfjsLib.getDocument({ data: arrayBuffer }).promise;
          if (pdf && pdf.numPages > 0) {
            localPageCount = pdf.numPages;
          }
        } catch (err) {
          console.warn('Could not extract PDF page count locally for', file.name, err);
        }
      }

      // DOC/DOCX files: skip backend upload (can't render natively), handle as local files.
      if (isDoc) {
        const localFile: UploadedFile = {
          id: `local-${Date.now()}-${Math.random().toString(36).slice(2)}`,
          name: file.name,
          size: file.size,
          pageCount: 1,  // Cannot detect page count for DOC without conversion
          type: file.type || 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
          previewUrl,
          // No fileId — this is a local-only file
        };
        newUploadedFiles.push(localFile);
        continue;
      }

      // Upload to backend (PDF and images) — receives authoritative fileId and pageCount.
      const backendResult = await uploadToBackend(file);

      if (!backendResult) {
        // uploadToBackend sets error state internally; show specific error toast.
        showToast(
          uploadError || `Failed to upload ${file.name}. Please ensure the file is a valid PDF, JPG, or PNG document.`,
          'error',
        );
        setUploadingFilesCount(0);
        return;
      }

      const customUploaded: UploadedFile = {
        id: backendResult.fileId,   // Use backend fileId as the local ID.
        name: file.name,
        size: backendResult.fileSizeBytes,
        pageCount: backendResult.pageCount,  // Use backend authoritative page count.
        type: file.type || (isImage ? 'image/' + ext : 'application/pdf'),
        previewUrl,
        fileId: backendResult.fileId,        // Explicit backend reference.
      };

      newUploadedFiles.push(customUploaded);
    }

    setUploadingFilesCount(0);

    const combinedList = [...activeFilesList, ...newUploadedFiles];
    if (onSelectFiles) {
      onSelectFiles(combinedList);
    } else if (newUploadedFiles.length > 0) {
      onSelectFile(newUploadedFiles[0]);
    }
    if (newUploadedFiles.length > 0) {
      showToast(
        newUploadedFiles.length === 1
          ? `${newUploadedFiles[0].name} uploaded successfully.`
          : `${newUploadedFiles.length} files uploaded successfully.`,
        'success',
      );
    }
  };


  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(false);
    
    if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
      processFiles(e.dataTransfer.files);
    }
  };

  const handleNativeFileInput = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files.length > 0) {
      processFiles(e.target.files);
    }
  };

  const handleRemoveSingleItem = (id: string) => {
    if (onRemoveFileItem) {
      onRemoveFileItem(id);
    } else {
      const remaining = activeFilesList.filter(f => f.id !== id);
      if (remaining.length === 0) {
        onRemoveFile();
      } else if (onSelectFiles) {
        onSelectFiles(remaining);
      }
    }
  };

  const totalPagesSum = activeFilesList.reduce((acc, f) => acc + f.pageCount, 0);
  const totalSizeBytesSum = activeFilesList.reduce((acc, f) => acc + f.size, 0);
  const totalSizeMBStr = (totalSizeBytesSum / (1024 * 1024)).toFixed(1);

  return (
    <div className="space-y-6 max-w-3xl mx-auto pb-8">
      
      {/* 1. MAIN DROPZONE CARD */}
      <div className="bg-white border border-slate-200/80 rounded-3xl p-6 sm:p-8 shadow-xs">
        <div
          onDragOver={(e) => { e.preventDefault(); setIsDragging(true); }}
          onDragLeave={() => setIsDragging(false)}
          onDrop={handleDrop}
          className={`relative border-2 border-dashed rounded-2xl p-6 sm:p-10 text-center transition-all ${
            isDragging 
              ? 'border-blue-500 bg-blue-50/50 scale-[1.005]' 
              : 'border-slate-200 hover:border-slate-300 bg-slate-50/30'
          }`}
        >
          <input
            type="file"
            multiple
            accept=".pdf,.doc,.docx,.jpg,.jpeg,.png,application/pdf,application/msword,application/vnd.openxmlformats-officedocument.wordprocessingml.document,image/jpeg,image/png"
            onChange={handleNativeFileInput}
            disabled={isUploading}
            className="absolute inset-0 w-full h-full opacity-0 cursor-pointer disabled:cursor-not-allowed z-10"
          />

          <div className="max-w-md mx-auto flex flex-col items-center">
            
            {/* Upload Icon Circle */}
            <div className="w-12 h-12 rounded-full bg-blue-100/90 text-blue-600 flex items-center justify-center mb-3 shadow-xs">
              <Upload className="w-6 h-6 stroke-[2.2]" />
            </div>

            {/* Title & Subtitle */}
            <h2 className="text-xl sm:text-2xl font-bold font-['Outfit'] text-slate-900 mb-1">
              Drag & Drop multiple files
            </h2>
            <p className="text-xs sm:text-sm text-slate-500 mb-5 font-normal">
              Supports PDF, DOC, DOCX, JPG, PNG up to <span className="font-bold text-slate-700">25MB per file</span>.
            </p>

            {/* Buttons Row */}
            <div className="relative z-20 flex flex-wrap items-center justify-center gap-3">
              <label className={`bg-blue-600 hover:bg-blue-700 text-white font-semibold text-xs sm:text-sm px-5 py-2.5 rounded-xl flex items-center gap-2 transition-colors shadow-xs ${isUploading ? 'opacity-50 cursor-not-allowed' : 'cursor-pointer'}`}>
                <Upload className="w-4 h-4" />
                <span>Browse Multiple Files</span>
                <input
                  type="file"
                  multiple
                  disabled={isUploading}
                  accept=".pdf,.doc,.docx,.jpg,.jpeg,.png,application/pdf,application/msword,application/vnd.openxmlformats-officedocument.wordprocessingml.document,image/jpeg,image/png"
                  onChange={handleNativeFileInput}
                  className="hidden"
                />
              </label>
            </div>

          </div>
        </div>
      </div>

      {/* 2. UPLOADED FILES BATCH LIST & SUMMARY */}
      <div className="space-y-4">
        
        {/* Clean & Minimal Progress Bar when files are uploading */}
        {uploadingFilesCount > 0 && (
          <div className="bg-blue-50/70 border border-blue-100 rounded-2xl p-4 space-y-2.5">
            <div className="flex items-center justify-between text-xs font-bold text-slate-800">
              <div className="flex items-center gap-2">
                <Loader2 className="w-4 h-4 text-blue-600 animate-spin shrink-0" />
                <span>Uploading & processing {uploadingFilesCount} {uploadingFilesCount === 1 ? 'file' : 'files'}...</span>
              </div>
              <span className="text-blue-600 font-extrabold">{uploadProgress}%</span>
            </div>
            <div className="h-1.5 w-full bg-blue-100 rounded-full overflow-hidden">
              <div 
                className="h-full bg-blue-600 rounded-full transition-all duration-300"
                style={{ width: `${Math.max(10, uploadProgress)}%` }}
              />
            </div>
          </div>
        )}

        {/* Batch Summary Header */}
        {activeFilesList.length > 0 && (
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 px-1">
            <div className="flex items-center gap-2 text-xs font-bold text-slate-800">
              <Files className="w-4 h-4 text-blue-600" />
              <span>{activeFilesList.length} {activeFilesList.length === 1 ? 'File' : 'Files'} Selected</span>
              <span className="text-slate-300">•</span>
              <span className="text-slate-600">{totalPagesSum} Total Pages</span>
              <span className="text-slate-300">•</span>
              <span className="text-slate-600">{totalSizeMBStr} MB Total</span>
            </div>

            <div className="flex items-center gap-3">
              {/* + Add More Files Button */}
              <label className={`text-xs font-bold transition-colors inline-flex items-center gap-1 ${isUploading ? 'text-slate-400 cursor-not-allowed' : 'text-blue-600 hover:text-blue-700 cursor-pointer'}`}>
                <Plus className="w-3.5 h-3.5" />
                <span>Add More Files</span>
                <input
                  type="file"
                  multiple
                  disabled={isUploading}
                  accept=".pdf,.doc,.docx,.jpg,.jpeg,.png,application/pdf,application/msword,application/vnd.openxmlformats-officedocument.wordprocessingml.document,image/jpeg,image/png"
                  onChange={handleNativeFileInput}
                  className="hidden"
                />
              </label>

              <span className="text-slate-300">|</span>

              {/* Clear All Button */}
              <button
                onClick={onRemoveFile}
                disabled={isUploading}
                className="text-xs font-bold text-slate-400 hover:text-red-600 cursor-pointer disabled:opacity-50 disabled:cursor-not-allowed"
              >
                Clear All
              </button>
            </div>
          </div>
        )}

        {/* File Cards List */}
        {activeFilesList.length > 0 && (
          <div className="space-y-2.5">
            {activeFilesList.map((file, idx) => (
              <div key={file.id || idx} className="bg-white border border-slate-200/80 rounded-2xl p-4 flex flex-col sm:flex-row sm:items-center justify-between gap-3 shadow-xs hover:border-slate-300 transition-colors">
                <div className="flex items-center gap-3.5 overflow-hidden">
                  <div className="w-10 h-10 rounded-xl bg-blue-50 text-blue-600 flex items-center justify-center shrink-0 border border-blue-100">
                    <FileText className="w-5 h-5 stroke-[2.2]" />
                  </div>
                  <div className="overflow-hidden">
                    <h3 className="text-sm font-bold text-slate-900 truncate">
                      {file.name}
                    </h3>
                    <p className="text-xs text-slate-500 mt-0.5 font-medium">
                      {file.pageCount} {file.pageCount === 1 ? 'Page' : 'Pages'} • {(file.size / (1024 * 1024)).toFixed(1)} MB
                    </p>
                  </div>
                </div>

                <div className="flex items-center gap-2 shrink-0 self-end sm:self-auto">
                  <span className="bg-emerald-50 text-emerald-700 border border-emerald-200/60 text-[11px] font-semibold px-2.5 py-1 rounded-full flex items-center gap-1.5">
                    <CheckCircle2 className="w-3.5 h-3.5 text-emerald-600" />
                    <span>Ready</span>
                  </span>

                  <button
                    onClick={() => handleRemoveSingleItem(file.id)}
                    disabled={isUploading}
                    className="text-slate-400 hover:text-red-500 p-1.5 transition-colors cursor-pointer rounded-lg hover:bg-slate-100 disabled:opacity-50 disabled:cursor-not-allowed"
                    title="Remove file from list"
                  >
                    <Trash2 className="w-4 h-4" />
                  </button>
                </div>
              </div>
            ))}
          </div>
        )}

        {/* Error Notification Banner if invalid file uploaded */}
        {errorMessage && (
          <div className="bg-red-50/80 border border-red-200/80 rounded-2xl p-4 flex items-start justify-between shadow-xs mt-3" aria-live="polite">
            <div className="flex items-start gap-3.5">
              <div className="w-8 h-8 rounded-full bg-red-100 text-red-500 flex items-center justify-center shrink-0 mt-0.5">
                <AlertCircle className="w-4 h-4 stroke-[2.2]" />
              </div>
              <div>
                <h3 className="text-xs font-bold text-red-900">
                  Upload Error (25MB Size Limit)
                </h3>
                <p className="text-xs text-red-600 font-medium mt-0.5 leading-relaxed">
                  {errorMessage}
                </p>
              </div>
            </div>

            <button
              onClick={() => setErrorMessage(null)}
              className="text-slate-400 hover:text-slate-600 p-1 transition-colors cursor-pointer shrink-0"
              title="Dismiss error"
            >
              <X className="w-4 h-4" />
            </button>
          </div>
        )}

      </div>

      {/* 3. CLEAN PRIVACY & SECURITY NOTE */}
      <div className="bg-blue-50/50 border border-blue-100 rounded-2xl p-4 flex items-center gap-3 text-xs text-slate-600">
        <ShieldCheck className="w-4.5 h-4.5 text-blue-600 shrink-0" />
        <p className="leading-relaxed">
          <strong className="font-bold text-slate-900">Your Privacy is Protected: </strong>
          Files are SSL/TLS encrypted and automatically deleted from our servers permanently after printing.
        </p>
      </div>

      {/* 4. BOTTOM FOOTER BAR */}
      <div className="pt-4 flex items-center justify-between gap-4 border-t border-slate-200/60">
        <button
          onClick={() => navigate('/')}
          className="text-slate-600 hover:text-slate-900 text-sm font-semibold px-4 py-2 cursor-pointer transition-colors"
        >
          Cancel
        </button>

        <button
          disabled={activeFilesList.length === 0 || isUploading}
          onClick={() => {
            if (activeFilesList.length > 0 && !isUploading) {
              onNext();
            }
          }}
          className="bg-blue-600 hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed text-white font-semibold text-sm px-7 py-3 rounded-xl flex items-center gap-2 transition-colors cursor-pointer shadow-xs active:scale-95"
        >
          <span>Continue to Settings ({activeFilesList.length} {activeFilesList.length === 1 ? 'File' : 'Files'})</span>
          <ArrowRight className="w-4 h-4" />
        </button>
      </div>

    </div>
  );
};
