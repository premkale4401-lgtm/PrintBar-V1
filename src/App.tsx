import React, { useState } from 'react';
import { BrowserRouter, Routes, Route, useNavigate, Navigate } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { PrintStep, PrintConfig, UploadedFile } from './types';
import { useKiosks } from './hooks/useKiosks';
import { DEFAULT_KIOSK_HUBS } from './services/kiosk.service';
import { Navbar } from './components/Navbar';
import { LandingView } from './components/LandingView';
import { StepUpload } from './components/KioskFlow/StepUpload';
import { StepConfigure } from './components/KioskFlow/StepConfigure';
import { StepPayment } from './components/KioskFlow/StepPayment';
import { StepPrinting } from './components/KioskFlow/StepPrinting';
import { StepSuccess } from './components/KioskFlow/StepSuccess';
import { StatusDiagnosticsView } from './components/StatusDiagnosticsView';
import { AdminDashboard } from './components/AdminDashboard';
import { ToastProvider } from './components/Toast';
import { adminService } from './services/admin.service';
import { JOB_ID_STORAGE_KEY } from './hooks/useCheckout';
import { 
  Check
} from 'lucide-react';

// ─── TanStack Query Client ────────────────────────────────────────────────────

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 10_000,
      retry: 2,
    },
  },
});

// ─── App Content ─────────────────────────────────────────────────────────────

function AppContent() {
  const navigate = useNavigate();
  const [kioskStep, setKioskStep] = useState<PrintStep>('upload');

  // Track current job ID through kiosk flow (persists across Easebuzz redirect).
  const [currentJobId, setCurrentJobId] = useState<string | null>(
    sessionStorage.getItem(JOB_ID_STORAGE_KEY),
  );

  // Admin Authentication State — checks backend JWT presence.
  const [isAdminLoggedIn, setIsAdminLoggedIn] = useState<boolean>(() => {
    return !!localStorage.getItem('pb_admin_token');
  });

  /**
   * Admin login — calls POST /api/v1/admin/auth/login.
   * Supports both full email/pass and quick username/pass inputs.
   */
  const handleAdminLogin = async (emailOrUser: string, pass: string): Promise<boolean> => {
    try {
      let email = emailOrUser.trim().toLowerCase();
      let password = pass.trim();

      // Map quick / legacy login inputs to seed admin
      if (email === 'juned' || email === 'admin') {
        if (password === '9642912613' || password === 'PrintBar@2026!Admin' || password === 'admin') {
          email = 'admin@printbar.local';
          password = 'PrintBar@2026!Admin';
        }
      } else if (!email.includes('@')) {
        email = `${email}@printbar.local`;
      }

      await adminService.login(email, password);
      setIsAdminLoggedIn(true);
      return true;
    } catch (err) {
      console.warn('Admin login failed:', err);
      return false;
    }
  };

  const handleAdminLogout = async () => {
    try {
      await adminService.logout();
    } catch {
      // Even if logout API fails, clear local state.
    }
    setIsAdminLoggedIn(false);
    navigate('/');
  };

  const { hubs } = useKiosks();

  // Print Job Configuration State
  const [printConfig, setPrintConfig] = useState<PrintConfig>({
    file: null,
    files: [],
    copies: 1,
    paperSize: 'A4',
    colorMode: 'bw',
    duplex: false,
    orientation: 'portrait',
    selectedHubId: hubs[0]?.id || DEFAULT_KIOSK_HUBS[0].id,
  });

  const onlineHubs = hubs.filter(h => h.status === 'online');

  // Handlers for switching to Kiosk Flow directly
  const handleStartKioskFlow = (hubId?: string) => {
    if (hubId) {
      setPrintConfig(prev => ({ ...prev, selectedHubId: hubId }));
    }
    setKioskStep('upload');
    navigate('/kiosk');
  };

  const handleSelectFile = (file: UploadedFile) => {
    setPrintConfig(prev => {
      const existing = prev.files || [];
      const updated = [...existing, file];
      return { ...prev, files: updated, file: updated[0] || null };
    });
  };

  const handleSelectFiles = (files: UploadedFile[]) => {
    setPrintConfig(prev => ({ ...prev, files, file: files[0] || null }));
  };

  const handleRemoveFileItem = (id: string) => {
    setPrintConfig(prev => {
      const updated = (prev.files || []).filter(f => f.id !== id);
      return { ...prev, files: updated, file: updated[0] || null };
    });
  };

  const handleRemoveFile = () => {
    setPrintConfig(prev => ({ ...prev, file: null, files: [] }));
  };

  /** Called by StepPayment after checkout — records the job ID for StepPrinting. */
  const handleJobCreated = (jobId: string) => {
    setCurrentJobId(jobId);
    sessionStorage.setItem(JOB_ID_STORAGE_KEY, jobId);
  };

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100 flex flex-col font-['Plus_Jakarta_Sans',sans-serif]">
      
      {/* Top Header Navigation */}
      <Navbar
        onlineHubsCount={onlineHubs.length}
        totalHubsCount={hubs.length}
        onStartKioskFlow={() => handleStartKioskFlow()}
        isAdminLoggedIn={isAdminLoggedIn}
        onAdminLogin={handleAdminLogin}
        onAdminLogout={handleAdminLogout}
      />

      {/* Main Content Area */}
      <main className="flex-1 pt-6 bg-white">
        <Routes>
          {/* ROUTE 1: LANDING OVERVIEW */}
          <Route 
            path="/" 
            element={
              <LandingView
                onStartKioskFlow={handleStartKioskFlow}
                onSelectHubs={() => handleStartKioskFlow()}
                onOpenDiagnostics={() => navigate('/status')}
              />
            } 
          />

          {/* ROUTE 2: MULTI-STEP KIOSK PRINT FLOW */}
          <Route 
            path="/kiosk" 
            element={
              <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 pb-20 space-y-8">
                {/* Kiosk Step Progress Indicator Bar */}
                <div className="max-w-2xl mx-auto py-4 px-4">
                  <div className="relative flex items-center justify-between">
                    {/* Background Connecting Line */}
                    <div className="absolute top-4 left-6 right-6 h-0.5 bg-slate-200 -z-0" />
                    
                    {/* Active/Completed Connecting Line Overlay */}
                    {(() => {
                      const stepKeys: PrintStep[] = ['upload', 'configure', 'payment', 'printing', 'success'];
                      const currentIdx = stepKeys.indexOf(kioskStep);
                      if (currentIdx > 0) {
                        const widthPct = Math.min(100, (currentIdx / 3) * 100);
                        return (
                          <div 
                            className="absolute top-4 left-6 h-0.5 bg-blue-600 transition-all duration-300 -z-0" 
                            style={{ width: `calc(${widthPct}% - 24px)` }}
                          />
                        );
                      }
                      return null;
                    })()}

                    {[
                      { num: 1, key: 'upload', label: 'Upload' },
                      { num: 2, key: 'configure', label: 'Configure' },
                      { num: 3, key: 'payment', label: 'Payment' },
                      { num: 4, key: 'printing', label: 'Confirm' },
                    ].map((step, idx) => {
                      const stepKeys: PrintStep[] = ['upload', 'configure', 'payment', 'printing', 'success'];
                      const currentIdx = stepKeys.indexOf(kioskStep);
                      const isCompleted = currentIdx > idx;
                      const isActive = (kioskStep === step.key) || (step.key === 'printing' && kioskStep === 'success');

                      return (
                        <div key={step.key} className="relative z-10 flex flex-col items-center">
                          <div 
                            className={`w-8 h-8 rounded-full flex items-center justify-center font-bold text-xs transition-all ${
                              isCompleted || isActive
                                ? 'bg-blue-600 text-white shadow-xs'
                                : 'bg-slate-200/90 text-slate-500'
                            }`}
                          >
                            {isCompleted ? (
                              <Check className="w-4 h-4 stroke-[3]" />
                            ) : (
                              step.num
                            )}
                          </div>
                          <span 
                            className={`text-xs mt-2 font-medium transition-colors ${
                              isCompleted || isActive
                                ? 'text-blue-600 font-semibold' 
                                : 'text-slate-500'
                            }`}
                          >
                            {step.label}
                          </span>
                        </div>
                      );
                    })}
                  </div>
                </div>

                {/* Step Components */}
                {kioskStep === 'upload' && (
                  <StepUpload
                    uploadedFile={printConfig.file}
                    uploadedFiles={printConfig.files}
                    onSelectFile={handleSelectFile}
                    onSelectFiles={handleSelectFiles}
                    onRemoveFileItem={handleRemoveFileItem}
                    onRemoveFile={handleRemoveFile}
                    onNext={() => setKioskStep('configure')}
                  />
                )}

                {kioskStep === 'configure' && (
                  <StepConfigure
                    config={printConfig}
                    onChangeConfig={setPrintConfig}
                    onBack={() => setKioskStep('upload')}
                    onNext={() => setKioskStep('payment')}
                    onRemoveFile={handleRemoveFile}
                  />
                )}

                {kioskStep === 'payment' && (
                  <StepPayment
                    config={printConfig}
                    onBack={() => setKioskStep('configure')}
                    onPayAndStartPrint={() => setKioskStep('printing')}
                    onJobCreated={handleJobCreated}
                  />
                )}

                {kioskStep === 'printing' && (
                  <StepPrinting
                    config={printConfig}
                    jobId={currentJobId}
                    onPrintingComplete={() => setKioskStep('success')}
                  />
                )}

                {kioskStep === 'success' && (
                  <StepSuccess
                    config={printConfig}
                    onPrintAnother={() => {
                      setPrintConfig(prev => ({ ...prev, file: null }));
                      setKioskStep('upload');
                    }}
                    onGoHome={() => navigate('/')}
                  />
                )}
              </div>
            } 
          />

          {/* ROUTE 3: LOCATIONS / PRINTER HUBS */}
          <Route 
            path="/locations" 
            element={<Navigate to="/" replace />} 
          />

          {/* ROUTE 4: DIAGNOSTICS & SYSTEM ERRORS */}
          <Route 
            path="/status" 
            element={<StatusDiagnosticsView />} 
          />

          {/* ROUTE 5: ADMIN DASHBOARD COMMAND CENTER */}
          <Route 
            path="/admin" 
            element={isAdminLoggedIn ? <AdminDashboard /> : <Navigate to="/" replace />} 
          />

          {/* FALLBACK */}
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </main>



    </div>
  );
}

export default function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <ToastProvider>
        <BrowserRouter>
          <AppContent />
        </BrowserRouter>
      </ToastProvider>
    </QueryClientProvider>
  );
}
