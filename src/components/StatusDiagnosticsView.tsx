import React, { useState } from 'react';
import { SystemErrorType } from '../types';
import { SystemErrorCard, ERROR_DETAILS } from './SystemErrorCard';
import { AlertTriangle, CheckCircle2, ShieldCheck, RefreshCw } from 'lucide-react';

export const StatusDiagnosticsView: React.FC = () => {
  // 'gallery' shows all 6 cards; or a specific error type shows ONLY that real issue card.
  const [selectedIssue, setSelectedIssue] = useState<SystemErrorType | 'gallery'>('gallery');
  const [activeMessage, setActiveMessage] = useState<string | null>(null);

  const handlePrimaryAction = (type: SystemErrorType) => {
    const details = ERROR_DETAILS[type];
    setActiveMessage(`Action executed for ${details.title}: "${details.primaryButtonText}". System running diagnostic test...`);
    setTimeout(() => {
      setActiveMessage(`Diagnostic complete: ${details.title} resolved successfully.`);
    }, 1500);
  };

  const handleSecondaryAction = (type: SystemErrorType) => {
    const details = ERROR_DETAILS[type];
    setActiveMessage(`Secondary action triggered: "${details.secondaryButtonText}".`);
  };

  const errorTypes: SystemErrorType[] = [
    'hardware_disconnected',
    'transaction_declined',
    'out_of_paper',
    'connection_lost',
    'transmission_interrupted',
    'file_size_exceeded',
  ];

  return (
    <div className="space-y-10 max-w-6xl mx-auto px-4 sm:px-6 lg:px-8 pb-16 pt-4 text-center">
      
      {/* 1. MAIN HEADER */}
      <div className="space-y-3 max-w-2xl mx-auto">
        <h1 className="text-3xl sm:text-4xl font-extrabold font-['Outfit'] text-slate-900 tracking-tight">
          System Status & Resolution
        </h1>
        <p className="text-xs sm:text-sm text-slate-500 font-normal leading-relaxed">
          A central gallery of professional error states and guided resolution pathways for the PrintBar infrastructure.
        </p>
      </div>

      {/* 2. ISSUE SELECTOR / FILTER CONTROLS */}
      <div className="flex flex-wrap items-center justify-center gap-2 max-w-4xl mx-auto bg-slate-100/80 p-1.5 rounded-2xl border border-slate-200/70">
        <button
          type="button"
          onClick={() => setSelectedIssue('gallery')}
          className={`px-3.5 py-1.5 rounded-xl text-xs font-semibold transition-all cursor-pointer ${
            selectedIssue === 'gallery'
              ? 'bg-blue-600 text-white shadow-xs'
              : 'text-slate-600 hover:text-slate-900 hover:bg-slate-200/60'
          }`}
        >
          All Error States Gallery
        </button>

        {errorTypes.map((type) => {
          const title = ERROR_DETAILS[type].title;
          const isActive = selectedIssue === type;
          return (
            <button
              key={type}
              type="button"
              onClick={() => {
                setSelectedIssue(type);
                setActiveMessage(null);
              }}
              className={`px-3 py-1.5 rounded-xl text-xs font-semibold transition-all cursor-pointer ${
                isActive
                  ? 'bg-blue-600 text-white shadow-xs'
                  : 'text-slate-600 hover:text-slate-900 hover:bg-slate-200/60'
              }`}
            >
              {title}
            </button>
          );
        })}
      </div>

      {/* Notification Banner when an action is clicked */}
      {activeMessage && (
        <div className="max-w-md mx-auto bg-blue-50 border border-blue-200 text-blue-800 text-xs font-medium p-3 rounded-xl flex items-center justify-between shadow-xs">
          <div className="flex items-center gap-2">
            <CheckCircle2 className="w-4 h-4 text-blue-600 shrink-0" />
            <span>{activeMessage}</span>
          </div>
          <button 
            onClick={() => setActiveMessage(null)}
            className="text-blue-500 hover:text-blue-800 font-bold ml-2 cursor-pointer"
          >
            ×
          </button>
        </div>
      )}

      {/* 3. CONTENT AREA */}
      {selectedIssue === 'gallery' ? (
        /* 3x2 Grid displaying all 6 cards matching reference image */
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6 pt-2">
          {errorTypes.map((type) => (
            <SystemErrorCard
              key={type}
              type={type}
              onPrimaryAction={() => handlePrimaryAction(type)}
              onSecondaryAction={() => handleSecondaryAction(type)}
            />
          ))}
        </div>
      ) : (
        /* Single Issue Mode: Displays ONLY the specific issue that came */
        <div className="pt-4 max-w-sm mx-auto">
          <div className="mb-4 text-xs font-semibold text-slate-400 uppercase tracking-wider flex items-center justify-center gap-1.5">
            <AlertTriangle className="w-3.5 h-3.5 text-amber-500" />
            <span>Active Issue Displayed</span>
          </div>
          <SystemErrorCard
            type={selectedIssue}
            onPrimaryAction={() => handlePrimaryAction(selectedIssue)}
            onSecondaryAction={() => handleSecondaryAction(selectedIssue)}
          />
        </div>
      )}

    </div>
  );
};
