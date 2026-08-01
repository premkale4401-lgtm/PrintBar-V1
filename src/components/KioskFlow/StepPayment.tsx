import React, { useState } from 'react';
import { PrintConfig } from '../../types';
import { usePricing } from '../../hooks/usePricing';
import { useCheckout } from '../../hooks/useCheckout';
import { useToast } from '../Toast';
import { 
  FileText, 
  ArrowLeft, 
  ShieldCheck, 
  Lock, 
  Trash2, 
  ArrowRight,
  HelpCircle,
  Smartphone,
  QrCode,
  Loader2,
  CheckCircle2,
  ExternalLink
} from 'lucide-react';

interface StepPaymentProps {
  config: PrintConfig;
  onBack: () => void;
  onPayAndStartPrint: () => void;
  /** Called with the jobId once the backend creates the print job. */
  onJobCreated?: (jobId: string) => void;
}

export const StepPayment: React.FC<StepPaymentProps> = ({
  config,
  onBack,
  onPayAndStartPrint,
  onJobCreated,
}) => {
  const [isRedirecting, setIsRedirecting] = useState(false);
  const [redirectingApp, setRedirectingApp] = useState<string | null>(null);
  const [upiId, setUpiId] = useState('');
  const [activeTab, setActiveTab] = useState<'apps' | 'qr'>('apps');
  const { showToast } = useToast();

  const file = config.file;
  const filesList = (config.files && config.files.length > 0) ? config.files : (file ? [file] : []);
  const pageCount = filesList.length > 0 ? filesList.reduce((acc, f) => acc + f.pageCount, 0) : 12;
  const fileName = filesList.length > 1 ? `${filesList.length} Files (${filesList[0].name} +${filesList.length - 1} more)` : (file ? file.name : 'proposal_v2.pdf');

  const getSelectedPagesCount = (): number => {
    if (config.pagesSelection === 'all' || !config.pageRange || !config.pageRange.trim()) {
      return pageCount;
    }
    const set = new Set<number>();
    const parts = config.pageRange.split(',');
    for (const part of parts) {
      const trimmed = part.trim();
      if (trimmed.includes('-')) {
        const [startStr, endStr] = trimmed.split('-');
        const start = parseInt(startStr, 10);
        const end = parseInt(endStr, 10);
        if (!isNaN(start) && !isNaN(end)) {
          for (let i = Math.min(start, end); i <= Math.max(start, end); i++) {
            if (i >= 1 && i <= pageCount) set.add(i);
          }
        }
      } else {
        const num = parseInt(trimmed, 10);
        if (!isNaN(num) && num >= 1 && num <= pageCount) {
          set.add(num);
        }
      }
    }
    return set.size;
  };

  const selectedPagesCount = getSelectedPagesCount();
  const pagesPerSheet = config.pagesPerSheet || '1 on 1';
  const perSheetCount = pagesPerSheet === '2 on 1' ? 2 : pagesPerSheet === '4 on 1' ? 4 : pagesPerSheet === '6 on 1' ? 6 : 1;
  const totalPhysicalSheets = Math.ceil(selectedPagesCount / perSheetCount) * config.copies;

  // Backend-driven pricing (never local).
  const { price: backendPrice, isLoading: isPriceLoading } = usePricing(config, selectedPagesCount);
  const displayPrice = backendPrice ? `₹${backendPrice.totalInr.toFixed(2)}` : isPriceLoading ? 'Calculating...' : '₹—';

  // Easebuzz checkout hook.
  const { initiateCheckout, isLoading: isCheckoutLoading } = useCheckout();

  /** Gets the fileId from the first uploaded file. */
  const getFileId = (): string | null => {
    if (filesList.length > 0 && filesList[0].fileId) {
      return filesList[0].fileId;
    }
    return null;
  };

  /** Initiates the real Easebuzz checkout flow. */
  const handlePay = async () => {
    const fileId = getFileId();
    if (!fileId) {
      showToast('Upload error: file not found. Please go back and re-upload.', 'error');
      return;
    }

    setRedirectingApp('Easebuzz');
    setIsRedirecting(true);

    const result = await initiateCheckout(config, selectedPagesCount, fileId);
    if (result) {
      onJobCreated?.(result.jobId);
      // window.location.href is set inside initiateCheckout — page will redirect.
    } else {
      setIsRedirecting(false);
      setRedirectingApp(null);
      showToast('Payment initiation failed. Please try again.', 'error');
    }
  };

  /** Legacy UPI submit — still calls handlePay for consistency. */
  const handleUpiSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!upiId.trim()) return;
    handlePay();
  };

  return (
    <div className="space-y-8 max-w-5xl mx-auto pb-12">
      
      {/* 2-COLUMN LAYOUT */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-8 items-start">
        
        {/* LEFT COLUMN: ORDER SUMMARY & SECURITY PROOF */}
        <div className="lg:col-span-5 space-y-6">
          
          {/* Back Button */}
          <button
            onClick={onBack}
            className="inline-flex items-center gap-2 text-xs sm:text-sm font-semibold text-slate-600 hover:text-slate-900 transition-colors cursor-pointer"
          >
            <ArrowLeft className="w-4 h-4" />
            <span>Back to Print Settings</span>
          </button>

          {/* Title */}
          <h1 className="text-2xl font-extrabold font-['Outfit'] text-slate-900 tracking-tight">
            Order Summary
          </h1>

          {/* Document & Price Card */}
          <div className="bg-white border border-slate-200/80 rounded-2xl p-5 shadow-xs space-y-4">
            
            {/* File item row */}
            <div className="flex items-center gap-3.5">
              <div className="w-12 h-14 rounded-xl bg-blue-50 flex items-center justify-center shrink-0">
                <FileText className="w-6 h-6 text-[#0067ff] stroke-[2]" />
              </div>
              <div>
                <h3 className="text-sm font-bold text-slate-900">
                  {fileName}
                </h3>
                <p className="text-xs text-slate-500 mt-0.5">
                  {selectedPagesCount} {selectedPagesCount === 1 ? 'page' : 'pages'} selected • {config.copies} {config.copies === 1 ? 'copy' : 'copies'} • {config.colorMode === 'color' ? 'Color' : 'Black & White'}
                </p>
              </div>
            </div>

            <div className="border-t border-slate-100 pt-4 space-y-2.5 text-xs text-slate-600 font-normal">
              <div className="flex justify-between">
                <span>Sheets required</span>
                <span className="text-slate-900 font-medium">{totalPhysicalSheets} {totalPhysicalSheets === 1 ? 'sheet' : 'sheets'}</span>
              </div>
              {backendPrice && (
                <div className="flex justify-between">
                  <span>Rate per sheet ({config.colorMode === 'color' ? 'Color' : 'B&W'})</span>
                  <span className="text-slate-900 font-medium">₹{Number(backendPrice.pricePerSheetInr).toFixed(2)}</span>
                </div>
              )}
            </div>

            <div className="border-t border-slate-100 pt-3 flex items-center justify-between">
              <span className="text-sm font-bold text-slate-900">
                Total Amount
              </span>
              {isPriceLoading ? (
                <span className="flex items-center gap-1.5 text-slate-400 font-bold text-xl">
                  <Loader2 className="w-4 h-4 animate-spin" />
                  Calculating...
                </span>
              ) : backendPrice ? (
                <span className="text-2xl font-black text-[#0067ff]">
                  ₹{Number(backendPrice.totalInr).toFixed(2)}
                </span>
              ) : (
                <span className="text-2xl font-black text-[#0067ff]">₹—</span>
              )}
            </div>

          </div>

          {/* Trust Points Box */}
          <div className="bg-slate-50/70 border border-slate-100 rounded-2xl p-5 space-y-4">
            
            <div className="flex items-center gap-3.5">
              <div className="w-8 h-8 rounded-full bg-emerald-100/80 text-emerald-600 flex items-center justify-center shrink-0">
                <ShieldCheck className="w-4 h-4 stroke-[2.2]" />
              </div>
              <div>
                <h4 className="text-xs font-bold text-slate-900">
                  Instant Direct Payment
                </h4>
                <p className="text-xs text-slate-500 font-normal mt-0.2">
                  Direct app opening with no extra charges.
                </p>
              </div>
            </div>

            <div className="flex items-center gap-3.5">
              <div className="w-8 h-8 rounded-full bg-emerald-100/80 text-emerald-600 flex items-center justify-center shrink-0">
                <Lock className="w-4 h-4 stroke-[2.2]" />
              </div>
              <div>
                <h4 className="text-xs font-bold text-slate-900">
                  Encrypted UPI Gateway
                </h4>
                <p className="text-xs text-slate-500 font-normal mt-0.2">
                  100% secure payment authorized by your UPI PIN.
                </p>
              </div>
            </div>

            <div className="flex items-center gap-3.5">
              <div className="w-8 h-8 rounded-full bg-emerald-100/80 text-emerald-600 flex items-center justify-center shrink-0">
                <Trash2 className="w-4 h-4 stroke-[2.2]" />
              </div>
              <div>
                <h4 className="text-xs font-bold text-slate-900">
                  Automatic File Cleanup
                </h4>
                <p className="text-xs text-slate-500 font-normal mt-0.2">
                  Files are permanently removed right after printing.
                </p>
              </div>
            </div>

          </div>

        </div>

        {/* RIGHT COLUMN: PAYMENT METHOD CARD */}
        <div className="lg:col-span-7">
          <div className="bg-white border border-slate-200/80 rounded-3xl p-6 sm:p-8 shadow-xs">
            
            {/* Header */}
            <div className="flex items-center justify-between mb-6">
              <div>
                <h2 className="text-xl font-bold font-['Outfit'] text-slate-900">
                  Select Payment Method
                </h2>
                <p className="text-xs text-slate-500 mt-1">
                  Click Pay to complete your order for {isPriceLoading ? 'calculating...' : displayPrice}
                </p>
              </div>
              <div className="bg-emerald-50 text-emerald-700 border border-emerald-200/60 text-[11px] font-bold uppercase tracking-wide px-3 py-1 rounded-full flex items-center gap-1.5 shrink-0">
                <Lock className="w-3 h-3 text-emerald-600" />
                <span>DIRECT UPI</span>
              </div>
            </div>

            {/* TAB SELECTOR: APPS OR QR */}
            <div className="flex rounded-xl bg-slate-100 p-1 mb-6">
              <button
                type="button"
                onClick={() => setActiveTab('apps')}
                className={`flex-1 py-2 text-xs font-bold rounded-lg transition-all cursor-pointer flex items-center justify-center gap-1.5 ${
                  activeTab === 'apps' ? 'bg-white text-slate-900 shadow-2xs' : 'text-slate-600 hover:text-slate-900'
                }`}
              >
                <Smartphone className="w-3.5 h-3.5" />
                <span>UPI Apps (Direct)</span>
              </button>
              <button
                type="button"
                onClick={() => setActiveTab('qr')}
                className={`flex-1 py-2 text-xs font-bold rounded-lg transition-all cursor-pointer flex items-center justify-center gap-1.5 ${
                  activeTab === 'qr' ? 'bg-white text-slate-900 shadow-2xs' : 'text-slate-600 hover:text-slate-900'
                }`}
              >
                <QrCode className="w-3.5 h-3.5" />
                <span>Scan QR Code</span>
              </button>
            </div>

            {/* TAB CONTENT 1: DIRECT APP BUTTONS */}
            {activeTab === 'apps' && (
              <div className="space-y-4">
                
                {/* PHONEPE BUTTON */}
                <button
                  type="button"
                  onClick={handlePay}
                  disabled={isCheckoutLoading || isPriceLoading}
                  className="w-full bg-[#5f259f] hover:bg-[#4d1e82] disabled:opacity-60 text-white p-4 sm:p-5 rounded-2xl flex items-center justify-between transition-all cursor-pointer shadow-sm active:scale-[0.99] group border border-purple-700/30"
                >
                  <div className="flex items-center gap-4">
                    {/* PhonePe Logo Badge */}
                    <div className="w-12 h-12 rounded-xl bg-white flex items-center justify-center shrink-0 shadow-xs">
                      <svg className="w-7 h-7" viewBox="0 0 100 100" fill="none">
                        <rect width="100" height="100" rx="20" fill="#5F259F"/>
                        <path d="M68 32H44V26C44 23.79 42.21 22 40 22C37.79 22 36 23.79 36 26V74C36 76.21 37.79 78 40 78C42.21 78 44 76.21 44 74V56H56C63.73 56 70 49.73 70 42C70 36.48 68 32 68 32ZM56 46H44V34H56C60.42 34 64 37.58 64 42C64 46.42 60.42 50 56 50Z" fill="white"/>
                        <path d="M52 62L68 76" stroke="white" strokeWidth="6" strokeLinecap="round"/>
                      </svg>
                    </div>
                    <div className="text-left">
                      <div className="flex items-center gap-2">
                        <h3 className="font-extrabold text-base text-white">PhonePe</h3>
                        <span className="bg-purple-300/20 text-purple-100 text-[10px] font-bold px-2 py-0.5 rounded-full uppercase tracking-wider">Direct App</span>
                      </div>
                      <p className="text-xs text-purple-100/90 mt-0.5">
                        Redirects directly to PhonePe app
                      </p>
                    </div>
                  </div>
                  <div className="w-9 h-9 rounded-full bg-white/10 group-hover:bg-white/20 flex items-center justify-center shrink-0 text-white transition-colors">
                    <ExternalLink className="w-4 h-4" />
                  </div>
                </button>

                {/* GOOGLE PAY (GPAY) BUTTON */}
                <button
                  type="button"
                  onClick={handlePay}
                  disabled={isCheckoutLoading || isPriceLoading}
                  className="w-full bg-white hover:bg-slate-50 disabled:opacity-60 text-slate-900 border-2 border-slate-200 hover:border-slate-300 p-4 sm:p-5 rounded-2xl flex items-center justify-between transition-all cursor-pointer shadow-2xs active:scale-[0.99] group"
                >
                  <div className="flex items-center gap-4">
                    {/* GPay Logo Badge */}
                    <div className="w-12 h-12 rounded-xl bg-slate-50 border border-slate-100 flex items-center justify-center shrink-0 shadow-2xs">
                      <svg className="w-7 h-7" viewBox="0 0 24 24">
                        <path fill="#4285F4" d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z"/>
                        <path fill="#34A853" d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z"/>
                        <path fill="#FBBC05" d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.06H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.94l2.85-2.22.81-.63z"/>
                        <path fill="#EA4335" d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.06l3.66 2.84c.87-2.6 3.3-4.52 6.16-4.52z"/>
                      </svg>
                    </div>
                    <div className="text-left">
                      <div className="flex items-center gap-2">
                        <h3 className="font-extrabold text-base text-slate-900">Google Pay (GPay)</h3>
                        <span className="bg-blue-50 text-blue-700 text-[10px] font-bold px-2 py-0.5 rounded-full uppercase tracking-wider">Direct App</span>
                      </div>
                      <p className="text-xs text-slate-500 mt-0.5">
                        Redirects directly to Google Pay app
                      </p>
                    </div>
                  </div>
                  <div className="w-9 h-9 rounded-full bg-slate-100 group-hover:bg-slate-200 flex items-center justify-center shrink-0 text-slate-700 transition-colors">
                    <ExternalLink className="w-4 h-4" />
                  </div>
                </button>

                {/* MANUAL UPI VPA FORM */}
                <div className="pt-4 border-t border-slate-100">
                  <label className="block text-xs font-bold text-slate-700 mb-2">
                    Or Enter Any UPI ID (VPA)
                  </label>
                  <form onSubmit={handleUpiSubmit} className="flex gap-2">
                    <input
                      type="text"
                      value={upiId}
                      onChange={(e) => setUpiId(e.target.value)}
                      placeholder="e.g. mobile@ybl or username@upi"
                      className="flex-1 bg-slate-50 border border-slate-200 rounded-xl px-4 py-2.5 text-sm font-medium text-slate-900 placeholder:text-slate-400 focus:outline-none focus:border-[#0067ff]"
                    />
                    <button
                      type="submit"
                      disabled={!upiId.trim()}
                      className="bg-[#0067ff] hover:bg-[#0052cc] disabled:opacity-50 text-white font-bold text-xs sm:text-sm px-5 py-2.5 rounded-xl transition-all cursor-pointer shrink-0"
                    >
                      Verify & Pay
                    </button>
                  </form>
                </div>

              </div>
            )}

            {/* TAB CONTENT 2: QR CODE */}
            {activeTab === 'qr' && (
              <div className="text-center py-4 space-y-4">
                <div className="bg-slate-50 border border-slate-200 p-6 rounded-2xl inline-block shadow-2xs relative">
                  {/* Generated QR Code display */}
                  <img 
                    src={`https://api.qrserver.com/v1/create-qr-code/?size=180x180&data=${encodeURIComponent(`upi://pay?pa=printkiosk@upi&pn=PrintKiosk&am=${backendPrice ? backendPrice.totalInr.toFixed(2) : '0'}&cu=INR`)}`}
                    alt="UPI QR Code" 
                    className="w-44 h-44 mx-auto rounded-lg"
                  />
                  <div className="mt-3 flex items-center justify-center gap-2">
                    <span className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse" />
                    <span className="text-xs font-bold text-slate-700">Scan with PhonePe, GPay, or Paytm</span>
                  </div>
                </div>

                <div>
                <button
                  type="button"
                  onClick={handlePay}
                  disabled={isCheckoutLoading || isPriceLoading}
                  className="w-full bg-[#0067ff] hover:bg-[#0052cc] disabled:opacity-60 text-white font-bold text-sm py-3.5 rounded-xl transition-all cursor-pointer flex items-center justify-center gap-2 active:scale-95"
                >
                  <span>Proceed to Pay {displayPrice}</span>
                  <ArrowRight className="w-4 h-4" />
                </button>
              </div>
              </div>
            )}

          </div>

          {/* Need help link */}
          <div className="mt-6 text-center">
            <button
              type="button"
              onClick={() => alert('Support available 24/7. Contact support@printbar.com')}
              className="inline-flex items-center gap-1.5 text-xs text-slate-500 hover:text-slate-800 font-medium transition-colors cursor-pointer"
            >
              <HelpCircle className="w-3.5 h-3.5" />
              <span>Need help with your payment?</span>
            </button>
          </div>

        </div>

      </div>

      {/* REDIRECT OVERLAY / MODAL */}
      {isRedirecting && (
        <div className="fixed inset-0 bg-slate-900/60 backdrop-blur-xs z-50 flex items-center justify-center p-4 animate-fadeIn">
          <div className="bg-white rounded-3xl p-8 max-w-sm w-full text-center space-y-4 shadow-2xl border border-slate-100">
            <div className="w-16 h-16 rounded-full bg-blue-50 text-[#0067ff] flex items-center justify-center mx-auto">
              <Loader2 className="w-8 h-8 animate-spin" />
            </div>
            <h3 className="text-lg font-extrabold text-slate-900">
              Opening {redirectingApp}...
            </h3>
            <p className="text-xs text-slate-500 leading-relaxed">
              Redirecting to Easebuzz payment gateway for {displayPrice}. Once authorized, printing will start automatically.
            </p>
            <div className="pt-2">
              <span className="inline-flex items-center gap-1.5 text-[11px] font-bold text-emerald-600 bg-emerald-50 px-3 py-1 rounded-full">
                <CheckCircle2 className="w-3.5 h-3.5" />
                Connecting securely
              </span>
            </div>
          </div>
        </div>
      )}

    </div>
  );
};

