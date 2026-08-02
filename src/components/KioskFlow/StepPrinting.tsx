/**
 * PrintBar — StepPrinting Component
 *
 * Real-time print job status driven by useJobStatus hook.
 * WebSocket events drive the checklist progress; polling is the fallback.
 * The existing UI layout, animations, and styling are preserved exactly.
 */

import React, { useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { PrintConfig } from '../../types';
import { Check, QrCode, Loader2 } from 'lucide-react';
import { useJobStatus, JobProgressStatus } from '../../hooks/useJobStatus';
import { sessionService } from '../../services/session.service';

interface StepPrintingProps {
  config: PrintConfig;
  /** Backend job ID from StepPayment — required for real-time status. */
  jobId?: string | null;
  onPrintingComplete: () => void;
}

// Maps backend job status to which checklist steps are "done".
const STATUS_STEP_MAP: Record<string, number> = {
  QUEUED: 1,
  ASSIGNED: 2,
  DOWNLOADING: 3,
  READY_TO_PRINT: 3,
  PRINTING: 4,
  COMPLETED: 5,
  FAILED: 5,
  CANCELLED: 5,
};

export const StepPrinting: React.FC<StepPrintingProps> = ({
  config,
  jobId,
  onPrintingComplete,
}) => {
  const navigate = useNavigate();
  const file = config.file;
  const filesList = (config.files && config.files.length > 0) ? config.files : (file ? [file] : []);
  const pageCount = filesList.length > 0 ? filesList.reduce((acc, f) => acc + f.pageCount, 0) : 12;

  const sessionId = sessionService.getToken() ? 'session' : null;

  const { jobStatus, pageProgress, message, wsConnected, isPolling } = useJobStatus({
    jobId: jobId ?? null,
    sessionId,
    enabled: !!jobId,
  });

  // Auto-advance when job is completed.
  useEffect(() => {
    if (jobStatus === 'COMPLETED') {
      const timer = setTimeout(() => {
        onPrintingComplete();
      }, 1500);
      return () => clearTimeout(timer);
    }
  }, [jobStatus, onPrintingComplete]);

  const currentStep = jobStatus ? (STATUS_STEP_MAP[jobStatus] ?? 0) : 0;
  const isFailed = jobStatus === 'FAILED' || jobStatus === 'CANCELLED';

  const handleDone = () => {
    onPrintingComplete();
    navigate('/');
  };

  // Checklist steps driven by backend status.
  const steps = [
    {
      label: 'Preparing Document',
      desc: 'PDF conversion complete',
      doneAt: 1,
    },
    {
      label: 'Payment Verified',
      desc: 'Transaction confirmed by gateway',
      doneAt: 2,
    },
    {
      label: 'Sending to Printer',
      desc: pageProgress > 0 ? `Downloading to kiosk... ${pageProgress}%` : 'Transferring file to kiosk',
      doneAt: 3,
    },
    {
      label: 'Printing',
      desc: pageProgress > 0 ? `Printing page ${Math.round(pageProgress / 100 * pageCount)} of ${pageCount}` : 'Finalizing hardware release...',
      doneAt: 4,
    },
    {
      label: 'Completed',
      desc: 'Ready for pickup',
      doneAt: 5,
    },
  ];

  return (
    <div className="space-y-8 max-w-5xl mx-auto pb-12 pt-2">
      
      {/* 2-COLUMN GRID */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-12 items-center min-h-[420px]">
        
        {/* LEFT COLUMN: STATUS & CHECKLIST */}
        <div className="lg:col-span-6 space-y-6 text-left">
          
          {/* Header */}
          <div className="space-y-2">
            <h1 className="text-3xl font-extrabold font-['Outfit'] text-slate-900 tracking-tight">
              {isFailed ? 'Print Job Failed' : jobStatus === 'COMPLETED' ? 'Print Job Ready' : 'Processing Print Job'}
            </h1>
            <p className="text-sm text-slate-600 font-normal leading-relaxed">
              {isFailed
                ? (message ?? 'Your print job encountered an error. Please contact support.')
                : jobStatus === 'COMPLETED'
                ? `Successfully printed ${pageCount} pages. You can collect your items from Tray A.`
                : jobId
                ? `Tracking job status in real time${wsConnected ? ' via WebSocket' : isPolling ? ' via polling' : ''}...`
                : `Print job submitted. Waiting for kiosk to pick up...`
              }
            </p>
          </div>

          {/* Connection status indicator */}
          {jobId && (
            <div className="flex items-center gap-2">
              <span className={`w-2 h-2 rounded-full ${wsConnected ? 'bg-emerald-500 animate-pulse' : isPolling ? 'bg-amber-500 animate-pulse' : 'bg-slate-300'}`} />
              <span className="text-xs text-slate-500 font-medium">
                {wsConnected ? 'Live updates connected' : isPolling ? 'Polling for updates' : 'Connecting...'}
              </span>
            </div>
          )}

          {/* Timeline Status Checklist */}
          <div className="relative pl-6 space-y-6 before:absolute before:left-2.5 before:top-2 before:bottom-2 before:w-0.5 before:bg-slate-200">
            
            {steps.map((step, idx) => {
              const stepNum = idx + 1;
              const isDone = currentStep >= step.doneAt;
              const isActive = currentStep === idx && !isFailed;
              const isCurrent = stepNum === currentStep + 1 && !isFailed;

              return (
                <div key={step.label} className="relative flex items-start gap-4">
                  <div
                    className={`absolute -left-6 w-5 h-5 rounded-full flex items-center justify-center shrink-0 z-10 transition-all ${
                      isFailed && isDone
                        ? 'bg-red-100 border-2 border-red-400'
                        : isDone
                        ? 'bg-blue-600 text-white'
                        : isCurrent
                        ? 'bg-blue-100 border-2 border-blue-400'
                        : 'bg-slate-100 border-2 border-slate-300'
                    }`}
                  >
                    {isDone && !isFailed && <Check className="w-3 h-3 stroke-[3]" />}
                    {isCurrent && !isDone && <Loader2 className="w-3 h-3 text-blue-600 animate-spin" />}
                  </div>
                  <div>
                    <h4 className={`text-xs font-bold transition-colors ${
                      isDone && !isFailed ? 'text-blue-600' : isCurrent ? 'text-slate-800' : 'text-slate-800'
                    }`}>
                      {step.label}
                    </h4>
                    <p className="text-xs text-slate-500 font-normal mt-0.5">
                      {step.desc}
                    </p>
                    {/* Page progress bar for printing step */}
                    {stepNum === 4 && currentStep >= 3 && pageProgress > 0 && (
                      <div className="mt-1.5 h-1.5 w-32 bg-slate-200 rounded-full overflow-hidden">
                        <div
                          className="h-full bg-blue-500 rounded-full transition-all duration-500"
                          style={{ width: `${pageProgress}%` }}
                        />
                      </div>
                    )}
                  </div>
                </div>
              );
            })}

          </div>

        </div>

        {/* RIGHT COLUMN: JOB SUCCESSFUL CARD */}
        <div className="lg:col-span-6 flex flex-col items-center justify-center text-center py-8">
          
          {/* Status Circle */}
          <div className={`w-28 h-28 rounded-full flex items-center justify-center shadow-xs mb-6 transition-all ${
            isFailed
              ? 'bg-red-100'
              : jobStatus === 'COMPLETED'
              ? 'bg-[#46f29e]'
              : 'bg-blue-50'
          }`}>
            {isFailed ? (
              <span className="text-4xl">⚠️</span>
            ) : jobStatus === 'COMPLETED' ? (
              <Check className="w-14 h-14 text-slate-900 stroke-[3.5]" />
            ) : (
              <Loader2 className="w-14 h-14 text-blue-500 animate-spin" />
            )}
          </div>

          <h2 className="text-2xl font-bold font-['Outfit'] text-slate-900 mb-1.5">
            {isFailed ? 'Job Failed' : jobStatus === 'COMPLETED' ? 'Job Successful' : 'Processing...'}
          </h2>

          <p className="text-sm text-slate-500 font-normal max-w-xs mb-8">
            {isFailed
              ? 'Please contact kiosk support for assistance.'
              : jobStatus === 'COMPLETED'
              ? 'Your document has been printed and is ready.'
              : 'Please wait while your document is being processed.'
            }
          </p>

          {(jobStatus === 'COMPLETED' || isFailed) && (
            <button
              onClick={handleDone}
              className="bg-blue-600 hover:bg-blue-700 text-white font-semibold text-sm px-12 py-3 rounded-xl cursor-pointer transition-all shadow-xs active:scale-95"
            >
              Done
            </button>
          )}

        </div>

      </div>



    </div>
  );
};
