/**
 * PrintBar — StepPayment
 *
 * Payment step in the kiosk flow. Preserves the existing 2-column layout.
 *
 * Enhanced payment flows:
 *   Mobile Android:
 *     - PhonePe, GPay, Paytm, BHIM, Amazon Pay → UPI intent app-switch
 *     - WhatsApp Pay, Other UPI → generic UPI intent / fallback to Razorpay modal
 *     - UPI ID → Razorpay modal with VPA pre-filled
 *
 *   Desktop:
 *     - All app buttons → Razorpay Standard Checkout modal (UPI intent not supported)
 *     - QR tab → backend-generated QR code, auto-polled every 3 seconds
 *     - UPI ID → Razorpay modal
 *
 *   After payment:
 *     - PaymentVerifyingOverlay shows "Verifying Payment..." (never instant success)
 *     - usePaymentPolling polls backend every 2.5s for VERIFIED status
 *     - Only after backend confirms VERIFIED → onPayAndStartPrint() is called
 *
 * Security:
 *   - Frontend NEVER marks payment successful.
 *   - Backend verification drives all transitions.
 *   - Modal dismiss → cancelPayment() called in DB.
 */

import React, { useState, useEffect, useRef } from 'react';
import { PrintConfig } from '../../types';
import { usePricing } from '../../hooks/usePricing';
import { useCheckout } from '../../hooks/useCheckout';
import { usePaymentPolling } from '../../hooks/usePaymentPolling';
import { useUpiAppSwitch } from '../../hooks/useUpiAppSwitch';
import { paymentService } from '../../services/payment.service';
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
  ExternalLink,
  RefreshCw,
} from 'lucide-react';
import { PaymentVerifyingOverlay } from './PaymentVerifyingOverlay';

interface StepPaymentProps {
  config: PrintConfig;
  onBack: () => void;
  onPayAndStartPrint: () => void;
  onJobCreated?: (jobId: string) => void;
}

/** Maps display name to UPI app identifier. */
const UPI_APPS = [
  {
    id: 'phonepe' as const,
    name: 'PhonePe',
    badge: 'DIRECT APP',
    badgeColor: 'bg-purple-300/20 text-purple-100',
    desc: 'Redirects directly to PhonePe app',
    bgClass: 'bg-[#5f259f] hover:bg-[#4d1e82] border border-purple-700/30',
    textClass: 'text-white',
    descClass: 'text-purple-100/90',
    badgeBg: 'bg-purple-300/20 text-purple-100',
    iconBg: 'bg-white',
    chevronBg: 'bg-white/10 group-hover:bg-white/20 text-white',
    logo: (
      <svg className="w-7 h-7" viewBox="0 0 100 100" fill="none">
        <rect width="100" height="100" rx="20" fill="#5F259F"/>
        <path d="M68 32H44V26C44 23.79 42.21 22 40 22C37.79 22 36 23.79 36 26V74C36 76.21 37.79 78 40 78C42.21 78 44 76.21 44 74V56H56C63.73 56 70 49.73 70 42C70 36.48 68 32 68 32ZM56 46H44V34H56C60.42 34 64 37.58 64 42C64 46.42 60.42 50 56 50Z" fill="white"/>
        <path d="M52 62L68 76" stroke="white" strokeWidth="6" strokeLinecap="round"/>
      </svg>
    ),
  },
  {
    id: 'gpay' as const,
    name: 'Google Pay',
    badge: 'DIRECT APP',
    badgeColor: 'bg-blue-50 text-blue-700',
    desc: 'Redirects directly to Google Pay app',
    bgClass: 'bg-white hover:bg-slate-50 border-2 border-slate-200 hover:border-slate-300',
    textClass: 'text-slate-900',
    descClass: 'text-slate-500',
    badgeBg: 'bg-blue-50 text-blue-700',
    iconBg: 'bg-slate-50 border border-slate-100',
    chevronBg: 'bg-slate-100 group-hover:bg-slate-200 text-slate-700',
    logo: (
      <svg className="w-7 h-7" viewBox="0 0 24 24">
        <path fill="#4285F4" d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z"/>
        <path fill="#34A853" d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z"/>
        <path fill="#FBBC05" d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.06H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.94l2.85-2.22.81-.63z"/>
        <path fill="#EA4335" d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.06l3.66 2.84c.87-2.6 3.3-4.52 6.16-4.52z"/>
      </svg>
    ),
  },
  {
    id: 'paytm' as const,
    name: 'Paytm',
    badge: 'UPI',
    badgeColor: 'bg-sky-50 text-sky-700',
    desc: 'Pay using Paytm UPI',
    bgClass: 'bg-white hover:bg-slate-50 border-2 border-slate-200 hover:border-slate-300',
    textClass: 'text-slate-900',
    descClass: 'text-slate-500',
    badgeBg: 'bg-sky-50 text-sky-700',
    iconBg: 'bg-sky-50 border border-sky-100',
    chevronBg: 'bg-slate-100 group-hover:bg-slate-200 text-slate-700',
    logo: (
      <svg className="w-7 h-7" viewBox="0 0 100 100" fill="none">
        <rect width="100" height="100" rx="16" fill="#00BAF2"/>
        <text x="50" y="65" textAnchor="middle" fontSize="36" fontWeight="bold" fill="white">P</text>
      </svg>
    ),
  },
  {
    id: 'bhim' as const,
    name: 'BHIM UPI',
    badge: 'UPI',
    badgeColor: 'bg-emerald-50 text-emerald-700',
    desc: 'Pay using BHIM UPI',
    bgClass: 'bg-white hover:bg-slate-50 border-2 border-slate-200 hover:border-slate-300',
    textClass: 'text-slate-900',
    descClass: 'text-slate-500',
    badgeBg: 'bg-emerald-50 text-emerald-700',
    iconBg: 'bg-emerald-50 border border-emerald-100',
    chevronBg: 'bg-slate-100 group-hover:bg-slate-200 text-slate-700',
    logo: (
      <svg className="w-7 h-7" viewBox="0 0 100 100" fill="none">
        <rect width="100" height="100" rx="16" fill="#1B5E20"/>
        <text x="50" y="65" textAnchor="middle" fontSize="28" fontWeight="bold" fill="white">BHIM</text>
      </svg>
    ),
  },
  {
    id: 'amazon' as const,
    name: 'Amazon Pay',
    badge: 'UPI',
    badgeColor: 'bg-orange-50 text-orange-700',
    desc: 'Pay using Amazon Pay UPI',
    bgClass: 'bg-white hover:bg-slate-50 border-2 border-slate-200 hover:border-slate-300',
    textClass: 'text-slate-900',
    descClass: 'text-slate-500',
    badgeBg: 'bg-orange-50 text-orange-700',
    iconBg: 'bg-orange-50 border border-orange-100',
    chevronBg: 'bg-slate-100 group-hover:bg-slate-200 text-slate-700',
    logo: (
      <svg className="w-7 h-7" viewBox="0 0 100 100" fill="none">
        <rect width="100" height="100" rx="16" fill="#FF9900"/>
        <text x="50" y="65" textAnchor="middle" fontSize="32" fontWeight="bold" fill="white">a</text>
      </svg>
    ),
  },
];

export const StepPayment: React.FC<StepPaymentProps> = ({
  config,
  onBack,
  onPayAndStartPrint,
  onJobCreated,
}) => {
  const [upiId, setUpiId] = useState('');
  const [activeTab, setActiveTab] = useState<'apps' | 'qr'>('apps');
  const [isPayingWith, setIsPayingWith] = useState<string | null>(null);
  const [showVerifyingOverlay, setShowVerifyingOverlay] = useState(false);
  const [currentJobId, setCurrentJobId] = useState<string | null>(null);
  const [qrOrderResult, setQrOrderResult] = useState<any>(null);
  const [isCreatingQrOrder, setIsCreatingQrOrder] = useState(false);
  const qrPollIntervalRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const { showToast } = useToast();

  // File resolution
  const file = config.file;
  const filesList = (config.files && config.files.length > 0)
    ? config.files
    : (file ? [file] : []);
  const pageCount = filesList.length > 0
    ? filesList.reduce((acc, f) => acc + f.pageCount, 0)
    : 12;
  const fileName = filesList.length > 1
    ? `${filesList.length} Files (${filesList[0].name} +${filesList.length - 1} more)`
    : (file ? file.name : 'document.pdf');

  // Page selection
  const getSelectedPagesCount = (): number => {
    if (config.pagesSelection === 'all' || !config.pageRange?.trim()) return pageCount;
    const set = new Set<number>();
    for (const part of config.pageRange!.split(',')) {
      const t = part.trim();
      if (t.includes('-')) {
        const [s, e] = t.split('-').map(Number);
        if (!isNaN(s) && !isNaN(e)) {
          for (let i = Math.min(s, e); i <= Math.max(s, e); i++) {
            if (i >= 1 && i <= pageCount) set.add(i);
          }
        }
      } else {
        const n = parseInt(t, 10);
        if (!isNaN(n) && n >= 1 && n <= pageCount) set.add(n);
      }
    }
    return set.size;
  };

  const selectedPagesCount = getSelectedPagesCount();
  const pagesPerSheet = config.pagesPerSheet || '1 on 1';
  const perSheetCount = pagesPerSheet === '2 on 1' ? 2 : pagesPerSheet === '4 on 1' ? 4 : pagesPerSheet === '6 on 1' ? 6 : 1;
  const totalPhysicalSheets = Math.ceil(selectedPagesCount / perSheetCount) * config.copies;

  // Backend pricing (never local)
  const { price: backendPrice, isLoading: isPriceLoading } = usePricing(config, selectedPagesCount);
  const displayPrice = backendPrice
    ? `₹${Number(backendPrice.totalInr).toFixed(2)}`
    : isPriceLoading ? 'Calculating...' : '₹—';

  // Hooks
  const { initiateCheckout, createOrder, isLoading: isCheckoutLoading } = useCheckout();
  const {
    startPolling,
    stopPolling,
    pollingStatus,
    errorMessage: pollingError,
    elapsedSeconds,
  } = usePaymentPolling();
  const { platform, canLaunchApps, launchApp } = useUpiAppSwitch();

  // When polling reaches VERIFIED, notify parent
  useEffect(() => {
    if (pollingStatus === 'verified') {
      setTimeout(() => {
        setShowVerifyingOverlay(false);
        onPayAndStartPrint();
      }, 1800); // Show verified state for 1.8s before proceeding
    }
  }, [pollingStatus, onPayAndStartPrint]);

  const getFileId = (): string | null => {
    if (filesList.length > 0 && filesList[0].fileId) return filesList[0].fileId;
    return null;
  };

  const handleJobCreated = (jobId: string) => {
    setCurrentJobId(jobId);
    onJobCreated?.(jobId);
  };

  /** Common post-payment handler: show overlay and start polling. */
  const startVerification = (jobId: string) => {
    setCurrentJobId(jobId);
    setShowVerifyingOverlay(true);
    startPolling(jobId);
  };

  /** Full checkout flow (modal). Used by UPI ID and desktop app buttons. */
  const handleModalPay = async (appName: string) => {
    const fileId = getFileId();
    if (!fileId) {
      showToast('Upload error: file not found. Please go back and re-upload.', 'error');
      return;
    }

    setIsPayingWith(appName);

    const result = await initiateCheckout(
      config,
      selectedPagesCount,
      fileId,
      (jobId) => {
        handleJobCreated(jobId);
        startVerification(jobId);
      },
    );

    setIsPayingWith(null);

    if (result) {
      // Checkout returned immediately after modal success + verify call
      // startVerification already called inside onSuccess callback above
      if (!showVerifyingOverlay && result.jobId) {
        startVerification(result.jobId);
      }
    }
  };

  /** Mobile UPI app-switch flow. Falls back to modal if app can't launch. */
  const handleUpiAppSwitch = async (appId: typeof UPI_APPS[number]['id'], appName: string) => {
    const fileId = getFileId();
    if (!fileId) {
      showToast('Upload error: file not found. Please go back and re-upload.', 'error');
      return;
    }

    if (!canLaunchApps) {
      // Desktop — fall back to Razorpay modal
      return handleModalPay(appName);
    }

    if (!backendPrice) {
      showToast('Price is still loading. Please wait.', 'error');
      return;
    }

    setIsPayingWith(appName);

    try {
      // Step 1: Create order on backend to get txnRef
      const orderResult = await createOrder(config, selectedPagesCount, fileId);
      if (!orderResult) {
        setIsPayingWith(null);
        showToast('Failed to create payment order. Please try again.', 'error');
        return;
      }

      handleJobCreated(orderResult.jobId);

      // Step 2: Launch UPI app with the Razorpay order ID as txnRef
      const switchResult = await launchApp(appId, {
        merchantVpa: 'printbar@razorpay',  // Razorpay merchant VPA
        merchantName: 'PrintBar',
        amountInr: Number(backendPrice.totalInr).toFixed(2),
        txnRef: orderResult.gatewayOrderId,
        txnNote: 'PrintBar Self-Service Printing',
      });

      if (!switchResult.launched) {
        // App not installed or launch failed — fall back to Razorpay modal
        showToast(`${appName} not available. Opening payment page...`, 'info');
        setIsPayingWith(null);
        return handleModalPay(appName);
      }

      // Step 3: Show verifying overlay and poll for payment
      startVerification(orderResult.jobId);
    } catch (err) {
      console.error('[StepPayment] UPI app switch error:', err);
      showToast('Payment initiation failed. Please try again.', 'error');
    } finally {
      setIsPayingWith(null);
    }
  };

  /** UPI ID form submit. */
  const handleUpiSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    const trimmed = upiId.trim();
    if (!trimmed) return;

    // Basic format validation: must contain @
    if (!trimmed.includes('@') || trimmed.length < 3) {
      showToast('Please enter a valid UPI ID (e.g. name@bank)', 'error');
      return;
    }

    await handleModalPay(`UPI ID: ${trimmed}`);
  };

  /** Create QR order and start QR poll. */
  const handleCreateQrOrder = async () => {
    const fileId = getFileId();
    if (!fileId || !backendPrice) return;

    setIsCreatingQrOrder(true);

    try {
      const orderResult = await createOrder(config, selectedPagesCount, fileId);
      if (!orderResult) {
        showToast('Failed to create payment order. Please try again.', 'error');
        return;
      }

      handleJobCreated(orderResult.jobId);
      setQrOrderResult(orderResult);

      // Poll gateway order status every 3 seconds for QR payment
      qrPollIntervalRef.current = setInterval(async () => {
        try {
          const poll = await paymentService.pollOrderStatus(orderResult.jobId);
          if (poll.isPaid) {
            clearInterval(qrPollIntervalRef.current!);
            startVerification(orderResult.jobId);
          }
        } catch (_) { /* non-critical */ }
      }, 3000);
    } catch (err) {
      showToast('Failed to generate QR. Please try again.', 'error');
    } finally {
      setIsCreatingQrOrder(false);
    }
  };

  // Clear QR polling on unmount
  useEffect(() => {
    return () => {
      if (qrPollIntervalRef.current) clearInterval(qrPollIntervalRef.current);
      stopPolling();
    };
  }, [stopPolling]);

  const handleRetry = () => {
    setShowVerifyingOverlay(false);
    stopPolling();
    setCurrentJobId(null);
    setQrOrderResult(null);
    if (qrPollIntervalRef.current) {
      clearInterval(qrPollIntervalRef.current);
      qrPollIntervalRef.current = null;
    }
  };

  /**
   * DEV MODE ONLY — Bypasses payment gateway completely.
   * Creates an order first (so the DB record exists), then calls the
   * dev/complete endpoint to mark it paid without any real gateway call.
   * Only available when backend ENVIRONMENT=development.
   */
  const [isDevPaying, setIsDevPaying] = useState(false);
  const handleDevPay = async () => {
    const fileId = getFileId();
    if (!fileId) {
      showToast('No file found. Please go back and re-upload.', 'error');
      return;
    }

    setIsDevPaying(true);
    try {
      // Step 1: Create the order so a job + payment record exist in DB.
      const orderResult = await createOrder(config, selectedPagesCount, fileId);
      if (!orderResult) {
        showToast('Failed to create order. Is the backend running?', 'error');
        return;
      }
      handleJobCreated(orderResult.jobId);

      // Step 2: Bypass payment gateway — mark SUCCESS immediately.
      await paymentService.devCompletePayment(orderResult.jobId);

      // Step 3: Show verifying overlay briefly then proceed.
      startVerification(orderResult.jobId);
    } catch (err: any) {
      const msg = err?.message || 'Dev pay failed. Check that the backend is running.';
      showToast(msg, 'error');
    } finally {
      setIsDevPaying(false);
    }
  };

  const isAnythingLoading = isCheckoutLoading || isPriceLoading || isCreatingQrOrder || isDevPaying;

  // Detect dev mode — check hostname or explicit env var.
  const isDevMode = typeof window !== 'undefined' &&
    (window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1');

  // Build QR URI from order result or fallback
  const qrPaymentUri = qrOrderResult && backendPrice
    ? `upi://pay?pa=printbar@razorpay&pn=PrintBar&am=${Number(backendPrice.totalInr).toFixed(2)}&tr=${qrOrderResult.gatewayOrderId}&tn=PrintBar+Payment&cu=INR`
    : backendPrice
    ? `upi://pay?pa=printbar@razorpay&pn=PrintBar&am=${Number(backendPrice.totalInr).toFixed(2)}&tn=PrintBar+Payment&cu=INR`
    : '';

  return (
    <div className="space-y-8 max-w-5xl mx-auto pb-12">

      {/* DEV MODE BANNER */}
      {isDevMode && (
        <div className="rounded-2xl border-2 border-dashed border-amber-400 bg-amber-50 p-4 flex flex-col sm:flex-row items-start sm:items-center gap-4">
          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-2 mb-1">
              <span className="text-base">⚠️</span>
              <span className="text-xs font-black text-amber-800 uppercase tracking-widest">Development Mode</span>
            </div>
            <p className="text-xs text-amber-700 font-medium leading-relaxed">
              No Razorpay credentials? Use the button to bypass payment and test the full print flow.
              <br />
              <span className="font-bold">This button will NOT appear in production.</span>
            </p>
          </div>
          <button
            type="button"
            onClick={handleDevPay}
            disabled={isAnythingLoading || isPriceLoading || !backendPrice}
            className="shrink-0 bg-amber-500 hover:bg-amber-600 disabled:opacity-50 text-white font-black text-sm px-5 py-3 rounded-xl transition-all cursor-pointer flex items-center gap-2 active:scale-95 whitespace-nowrap"
          >
            {isDevPaying ? (
              <>
                <svg className="w-4 h-4 animate-spin" fill="none" viewBox="0 0 24 24">
                  <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                  <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
                </svg>
                Processing...
              </>
            ) : (
              <>
                <span>🚀</span>
                Skip Payment ({displayPrice})
              </>
            )}
          </button>
        </div>
      )}

      {/* Payment Verifying Overlay */}
      <PaymentVerifyingOverlay
        isVisible={showVerifyingOverlay}
        status={pollingStatus}
        amountDisplay={displayPrice}
        errorMessage={pollingError}
        elapsedSeconds={elapsedSeconds}
        onRetry={handleRetry}
        onCancel={handleRetry}
      />

      {/* 2-COLUMN LAYOUT — PRESERVED */}
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
                <h3 className="text-sm font-bold text-slate-900">{fileName}</h3>
                <p className="text-xs text-slate-500 mt-0.5">
                  {selectedPagesCount} {selectedPagesCount === 1 ? 'page' : 'pages'} selected
                  {' '}• {config.copies} {config.copies === 1 ? 'copy' : 'copies'}
                  {' '}• {config.colorMode === 'color' ? 'Color' : 'Black & White'}
                </p>
              </div>
            </div>

            <div className="border-t border-slate-100 pt-4 space-y-2.5 text-xs text-slate-600 font-normal">
              <div className="flex justify-between">
                <span>Sheets required</span>
                <span className="text-slate-900 font-medium">
                  {totalPhysicalSheets} {totalPhysicalSheets === 1 ? 'sheet' : 'sheets'}
                </span>
              </div>
              {backendPrice && (
                <div className="flex justify-between">
                  <span>Rate per sheet ({config.colorMode === 'color' ? 'Color' : 'B&W'})</span>
                  <span className="text-slate-900 font-medium">
                    ₹{Number(backendPrice.pricePerSheetInr).toFixed(2)}
                  </span>
                </div>
              )}
            </div>

            <div className="border-t border-slate-100 pt-3 flex items-center justify-between">
              <span className="text-sm font-bold text-slate-900">Total Amount</span>
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
                <h4 className="text-xs font-bold text-slate-900">Instant Direct Payment</h4>
                <p className="text-xs text-slate-500 font-normal mt-0.2">
                  {canLaunchApps ? 'Direct app opening with no extra charges.' : 'Secure UPI payment — no extra charges.'}
                </p>
              </div>
            </div>

            <div className="flex items-center gap-3.5">
              <div className="w-8 h-8 rounded-full bg-emerald-100/80 text-emerald-600 flex items-center justify-center shrink-0">
                <Lock className="w-4 h-4 stroke-[2.2]" />
              </div>
              <div>
                <h4 className="text-xs font-bold text-slate-900">Encrypted UPI Gateway</h4>
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
                <h4 className="text-xs font-bold text-slate-900">Automatic File Cleanup</h4>
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
                  Click Pay to complete your order for{' '}
                  {isPriceLoading ? 'calculating...' : displayPrice}
                </p>
              </div>
              <div className="bg-emerald-50 text-emerald-700 border border-emerald-200/60 text-[11px] font-bold uppercase tracking-wide px-3 py-1 rounded-full flex items-center gap-1.5 shrink-0">
                <Lock className="w-3 h-3 text-emerald-600" />
                <span>DIRECT UPI</span>
              </div>
            </div>

            {/* TAB SELECTOR */}
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
                onClick={() => { setActiveTab('qr'); if (!qrOrderResult) handleCreateQrOrder(); }}
                className={`flex-1 py-2 text-xs font-bold rounded-lg transition-all cursor-pointer flex items-center justify-center gap-1.5 ${
                  activeTab === 'qr' ? 'bg-white text-slate-900 shadow-2xs' : 'text-slate-600 hover:text-slate-900'
                }`}
              >
                <QrCode className="w-3.5 h-3.5" />
                <span>Scan QR Code</span>
              </button>
            </div>

            {/* TAB 1: UPI APPS */}
            {activeTab === 'apps' && (
              <div className="space-y-3">

                {/* UPI App Buttons */}
                {UPI_APPS.map((app) => (
                  <button
                    key={app.id}
                    type="button"
                    onClick={() => handleUpiAppSwitch(app.id, app.name)}
                    disabled={isAnythingLoading || !!isPayingWith}
                    className={`w-full ${app.bgClass} disabled:opacity-60 p-4 sm:p-5 rounded-2xl flex items-center justify-between transition-all cursor-pointer shadow-sm active:scale-[0.99] group`}
                  >
                    <div className="flex items-center gap-4">
                      <div className={`w-12 h-12 rounded-xl ${app.iconBg} flex items-center justify-center shrink-0 shadow-xs`}>
                        {app.logo}
                      </div>
                      <div className="text-left">
                        <div className="flex items-center gap-2">
                          <h3 className={`font-extrabold text-base ${app.textClass}`}>{app.name}</h3>
                          <span className={`${app.badgeBg} text-[10px] font-bold px-2 py-0.5 rounded-full uppercase tracking-wider`}>
                            {canLaunchApps ? 'DIRECT APP' : app.badge}
                          </span>
                        </div>
                        <p className={`text-xs ${app.descClass} mt-0.5`}>
                          {canLaunchApps ? app.desc : `Pay using ${app.name}`}
                        </p>
                      </div>
                    </div>
                    <div className={`w-9 h-9 rounded-full ${app.chevronBg} flex items-center justify-center shrink-0 transition-colors`}>
                      {isPayingWith === app.name ? (
                        <Loader2 className="w-4 h-4 animate-spin" />
                      ) : (
                        <ExternalLink className="w-4 h-4" />
                      )}
                    </div>
                  </button>
                ))}

                {/* Other UPI Apps */}
                <button
                  type="button"
                  onClick={() => handleModalPay('Other UPI')}
                  disabled={isAnythingLoading || !!isPayingWith}
                  className="w-full bg-white hover:bg-slate-50 border-2 border-dashed border-slate-200 hover:border-slate-300 disabled:opacity-60 p-4 rounded-2xl flex items-center justify-between transition-all cursor-pointer group"
                >
                  <div className="flex items-center gap-4">
                    <div className="w-12 h-12 rounded-xl bg-slate-50 border border-slate-100 flex items-center justify-center shrink-0">
                      <span className="text-2xl">⊕</span>
                    </div>
                    <div className="text-left">
                      <h3 className="font-extrabold text-base text-slate-900">Other UPI Apps</h3>
                      <p className="text-xs text-slate-500 mt-0.5">WhatsApp Pay & any installed UPI app</p>
                    </div>
                  </div>
                  <div className="w-9 h-9 rounded-full bg-slate-100 group-hover:bg-slate-200 flex items-center justify-center shrink-0 text-slate-700 transition-colors">
                    {isPayingWith === 'Other UPI' ? (
                      <Loader2 className="w-4 h-4 animate-spin" />
                    ) : (
                      <ExternalLink className="w-4 h-4" />
                    )}
                  </div>
                </button>

                {/* UPI ID Entry */}
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
                      disabled={!upiId.trim() || isAnythingLoading}
                      className="bg-[#0067ff] hover:bg-[#0052cc] disabled:opacity-50 text-white font-bold text-xs sm:text-sm px-5 py-2.5 rounded-xl transition-all cursor-pointer shrink-0"
                    >
                      Verify & Pay
                    </button>
                  </form>
                </div>
              </div>
            )}

            {/* TAB 2: QR CODE */}
            {activeTab === 'qr' && (
              <div className="text-center py-4 space-y-4">

                {isCreatingQrOrder ? (
                  <div className="py-8 flex flex-col items-center gap-3">
                    <Loader2 className="w-10 h-10 text-[#0067ff] animate-spin" />
                    <p className="text-sm text-slate-500 font-medium">Generating QR Code...</p>
                  </div>
                ) : qrOrderResult && qrPaymentUri ? (
                  <>
                    <div className="bg-slate-50 border border-slate-200 p-6 rounded-2xl inline-block shadow-2xs relative">
                      <img
                        src={`https://api.qrserver.com/v1/create-qr-code/?size=200x200&data=${encodeURIComponent(qrPaymentUri)}&margin=1`}
                        alt="UPI Payment QR Code"
                        className="w-48 h-48 mx-auto rounded-lg"
                      />
                      <div className="mt-3 flex items-center justify-center gap-2">
                        <span className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse" />
                        <span className="text-xs font-bold text-slate-700">Waiting for payment...</span>
                      </div>
                    </div>

                    <p className="text-xs text-slate-500 font-medium">
                      Scan with PhonePe, Google Pay, Paytm, BHIM, or Amazon Pay
                    </p>

                    <div className="bg-blue-50 border border-blue-100 rounded-xl p-3 text-xs text-blue-700 font-medium">
                      Amount: <span className="font-black">{displayPrice}</span> · Auto-verifies after scan
                    </div>

                    <button
                      type="button"
                      onClick={handleCreateQrOrder}
                      disabled={isCreatingQrOrder}
                      className="inline-flex items-center gap-1.5 text-xs text-slate-500 hover:text-slate-700 font-semibold transition-colors cursor-pointer"
                    >
                      <RefreshCw className="w-3.5 h-3.5" />
                      Refresh QR
                    </button>
                  </>
                ) : (
                  <>
                    <div className="py-4">
                      <div className="bg-slate-50 border border-slate-200 p-6 rounded-2xl inline-block shadow-2xs">
                        {qrPaymentUri ? (
                          <img
                            src={`https://api.qrserver.com/v1/create-qr-code/?size=180x180&data=${encodeURIComponent(qrPaymentUri)}&margin=1`}
                            alt="UPI QR Code"
                            className="w-44 h-44 mx-auto rounded-lg"
                          />
                        ) : (
                          <div className="w-44 h-44 flex items-center justify-center bg-slate-100 rounded-lg">
                            <p className="text-xs text-slate-400 font-medium px-4 text-center">
                              Click below to generate QR
                            </p>
                          </div>
                        )}
                        <div className="mt-3 flex items-center justify-center gap-2">
                          <span className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse" />
                          <span className="text-xs font-bold text-slate-700">Scan with PhonePe, GPay, or Paytm</span>
                        </div>
                      </div>
                    </div>

                    <button
                      type="button"
                      onClick={handleCreateQrOrder}
                      disabled={isAnythingLoading || isPriceLoading}
                      className="w-full bg-[#0067ff] hover:bg-[#0052cc] disabled:opacity-60 text-white font-bold text-sm py-3.5 rounded-xl transition-all cursor-pointer flex items-center justify-center gap-2 active:scale-95"
                    >
                      {isCreatingQrOrder ? (
                        <Loader2 className="w-4 h-4 animate-spin" />
                      ) : (
                        <>
                          <span>Generate QR & Pay {displayPrice}</span>
                          <ArrowRight className="w-4 h-4" />
                        </>
                      )}
                    </button>
                  </>
                )}
              </div>
            )}
          </div>

          {/* Need help link */}
          <div className="mt-6 text-center">
            <button
              type="button"
              onClick={() => alert('Support available 24/7. Contact support@printbar.in')}
              className="inline-flex items-center gap-1.5 text-xs text-slate-500 hover:text-slate-800 font-medium transition-colors cursor-pointer"
            >
              <HelpCircle className="w-3.5 h-3.5" />
              <span>Need help with your payment?</span>
            </button>
          </div>
        </div>
      </div>
    </div>
  );
};
