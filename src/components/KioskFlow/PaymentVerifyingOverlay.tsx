/**
 * PrintBar — PaymentVerifyingOverlay
 *
 * Full-screen overlay shown after payment modal closes.
 * Drives the "Verifying Payment..." → "✓ Payment Verified" transition.
 *
 * States:
 *   polling    → Animated spinner + "Verifying Payment... Please wait."
 *   verified   → Green checkmark + "✓ Payment Verified — Preparing Print Job..."
 *   failed     → Red X + error message + Retry button
 *   cancelled  → Yellow warning + "Payment cancelled" + Retry button
 *   expired    → Orange warning + "Session expired" + Retry button
 *   timeout    → Blue info + "Taking longer than expected..." + contact info
 *
 * Design:
 *   - Matches PrintBar's futuristic blue/white aesthetic
 *   - Glassmorphism backdrop blur
 *   - Smooth state transitions with CSS animations
 *   - No Razorpay branding anywhere
 */

import React from 'react';
import {
  Loader2,
  CheckCircle2,
  XCircle,
  AlertTriangle,
  Clock,
  RefreshCw,
  ShieldCheck,
} from 'lucide-react';
import { PollingStatus } from '../../hooks/usePaymentPolling';

interface PaymentVerifyingOverlayProps {
  /** Current polling status from usePaymentPolling. */
  status: PollingStatus;
  /** Total amount being verified (display only). */
  amountDisplay: string;
  /** Error message for failed/cancelled/timeout states. */
  errorMessage: string | null;
  /** Elapsed seconds since polling started. */
  elapsedSeconds: number;
  /** Called when user clicks "Retry Payment". */
  onRetry: () => void;
  /** Called when user clicks "Cancel". */
  onCancel?: () => void;
  /** Whether to show the overlay. */
  isVisible: boolean;
}

export const PaymentVerifyingOverlay: React.FC<PaymentVerifyingOverlayProps> = ({
  status,
  amountDisplay,
  errorMessage,
  elapsedSeconds,
  onRetry,
  onCancel,
  isVisible,
}) => {
  if (!isVisible) return null;

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center p-4"
      style={{
        background: 'rgba(15, 23, 42, 0.75)',
        backdropFilter: 'blur(12px)',
        WebkitBackdropFilter: 'blur(12px)',
        animation: 'fadeIn 0.2s ease-out',
      }}
    >
      <div
        className="bg-white rounded-3xl shadow-2xl border border-slate-100 w-full max-w-sm overflow-hidden"
        style={{ animation: 'slideUp 0.25s ease-out' }}
      >
        {/* State: POLLING — Verifying */}
        {(status === 'polling') && (
          <VerifyingState
            amountDisplay={amountDisplay}
            elapsedSeconds={elapsedSeconds}
          />
        )}

        {/* State: VERIFIED — Success */}
        {status === 'verified' && (
          <VerifiedState amountDisplay={amountDisplay} />
        )}

        {/* State: FAILED — Payment failed */}
        {status === 'failed' && (
          <FailedState
            errorMessage={errorMessage}
            onRetry={onRetry}
            onCancel={onCancel}
          />
        )}

        {/* State: CANCELLED — User cancelled */}
        {status === 'cancelled' && (
          <CancelledState onRetry={onRetry} onCancel={onCancel} />
        )}

        {/* State: EXPIRED — Session expired */}
        {status === 'expired' && (
          <ExpiredState onRetry={onRetry} />
        )}

        {/* State: TIMEOUT — Webhook delay */}
        {status === 'timeout' && (
          <TimeoutState elapsedSeconds={elapsedSeconds} onRetry={onRetry} />
        )}

        {/* State: ERROR — Network error */}
        {status === 'error' && (
          <FailedState
            errorMessage={errorMessage ?? 'An unexpected error occurred.'}
            onRetry={onRetry}
            onCancel={onCancel}
          />
        )}
      </div>

      <style>{overlayStyles}</style>
    </div>
  );
};

// ─── Sub-components ───────────────────────────────────────────────────────────

const VerifyingState: React.FC<{
  amountDisplay: string;
  elapsedSeconds: number;
}> = ({ amountDisplay, elapsedSeconds }) => (
  <div className="p-8 text-center space-y-5">
    {/* Animated spinner */}
    <div className="flex items-center justify-center">
      <div
        className="w-20 h-20 rounded-full flex items-center justify-center"
        style={{
          background: 'linear-gradient(135deg, #e8f0ff 0%, #dbeafe 100%)',
          boxShadow: '0 0 0 8px rgba(0, 103, 255, 0.08)',
        }}
      >
        <Loader2 className="w-9 h-9 text-[#0067ff] animate-spin" strokeWidth={2.5} />
      </div>
    </div>

    <div className="space-y-1.5">
      <h3 className="text-xl font-extrabold text-slate-900 font-['Outfit']">
        Verifying Payment...
      </h3>
      <p className="text-sm text-slate-500 font-medium">
        Please wait. Do not close this window.
      </p>
    </div>

    {/* Amount badge */}
    <div className="inline-flex items-center gap-2 bg-blue-50 border border-blue-100 rounded-full px-4 py-1.5">
      <span className="w-2 h-2 rounded-full bg-[#0067ff] animate-pulse" />
      <span className="text-sm font-bold text-[#0067ff]">{amountDisplay}</span>
    </div>

    {/* Security note */}
    <div className="flex items-center justify-center gap-1.5 text-xs text-slate-400 font-medium">
      <ShieldCheck className="w-3.5 h-3.5 text-emerald-500" />
      <span>Secured by PrintBar · Backend verification</span>
    </div>

    {/* Elapsed time */}
    {elapsedSeconds > 5 && (
      <p className="text-[11px] text-slate-400">
        {elapsedSeconds}s elapsed · This usually takes 2–5 seconds
      </p>
    )}
  </div>
);

const VerifiedState: React.FC<{ amountDisplay: string }> = ({ amountDisplay }) => (
  <div className="p-8 text-center space-y-5">
    {/* Green checkmark */}
    <div className="flex items-center justify-center">
      <div
        className="w-20 h-20 rounded-full flex items-center justify-center"
        style={{
          background: 'linear-gradient(135deg, #d1fae5 0%, #a7f3d0 100%)',
          boxShadow: '0 0 0 8px rgba(16, 185, 129, 0.08)',
          animation: 'scaleIn 0.3s cubic-bezier(0.175, 0.885, 0.32, 1.275)',
        }}
      >
        <CheckCircle2 className="w-10 h-10 text-emerald-600" strokeWidth={2} />
      </div>
    </div>

    <div className="space-y-1.5">
      <h3 className="text-xl font-extrabold text-slate-900 font-['Outfit']">
        ✓ Payment Verified
      </h3>
      <p className="text-sm text-slate-600 font-medium">
        Preparing your print job...
      </p>
    </div>

    {/* Amount confirmed */}
    <div className="inline-flex items-center gap-2 bg-emerald-50 border border-emerald-100 rounded-full px-4 py-1.5">
      <CheckCircle2 className="w-3.5 h-3.5 text-emerald-600" />
      <span className="text-sm font-bold text-emerald-700">{amountDisplay} paid</span>
    </div>

    <p className="text-xs text-slate-400 font-medium">
      Your document is being sent to the printer
    </p>
  </div>
);

const FailedState: React.FC<{
  errorMessage: string | null;
  onRetry: () => void;
  onCancel?: () => void;
}> = ({ errorMessage, onRetry, onCancel }) => (
  <div className="p-8 text-center space-y-5">
    <div className="flex items-center justify-center">
      <div
        className="w-20 h-20 rounded-full flex items-center justify-center"
        style={{
          background: 'linear-gradient(135deg, #fee2e2 0%, #fecaca 100%)',
          boxShadow: '0 0 0 8px rgba(239, 68, 68, 0.08)',
        }}
      >
        <XCircle className="w-10 h-10 text-red-500" strokeWidth={2} />
      </div>
    </div>

    <div className="space-y-1.5">
      <h3 className="text-xl font-extrabold text-slate-900 font-['Outfit']">
        Payment Failed
      </h3>
      <p className="text-sm text-slate-500 font-medium leading-relaxed">
        {errorMessage ?? 'An error occurred. Please try again.'}
      </p>
    </div>

    <div className="flex flex-col gap-2.5 pt-1">
      <button
        type="button"
        onClick={onRetry}
        className="w-full bg-[#0067ff] hover:bg-[#0052cc] text-white font-bold text-sm py-3 rounded-xl transition-all cursor-pointer flex items-center justify-center gap-2 active:scale-95"
      >
        <RefreshCw className="w-4 h-4" />
        Retry Payment
      </button>
      {onCancel && (
        <button
          type="button"
          onClick={onCancel}
          className="w-full text-slate-500 hover:text-slate-700 font-semibold text-sm py-2 transition-colors cursor-pointer"
        >
          Cancel
        </button>
      )}
    </div>
  </div>
);

const CancelledState: React.FC<{
  onRetry: () => void;
  onCancel?: () => void;
}> = ({ onRetry, onCancel }) => (
  <div className="p-8 text-center space-y-5">
    <div className="flex items-center justify-center">
      <div
        className="w-20 h-20 rounded-full flex items-center justify-center"
        style={{
          background: 'linear-gradient(135deg, #fef3c7 0%, #fde68a 100%)',
          boxShadow: '0 0 0 8px rgba(245, 158, 11, 0.08)',
        }}
      >
        <AlertTriangle className="w-10 h-10 text-amber-500" strokeWidth={2} />
      </div>
    </div>

    <div className="space-y-1.5">
      <h3 className="text-xl font-extrabold text-slate-900 font-['Outfit']">
        Payment Cancelled
      </h3>
      <p className="text-sm text-slate-500 font-medium">
        You cancelled the payment. Your document is safe — retry when ready.
      </p>
    </div>

    <div className="flex flex-col gap-2.5 pt-1">
      <button
        type="button"
        onClick={onRetry}
        className="w-full bg-[#0067ff] hover:bg-[#0052cc] text-white font-bold text-sm py-3 rounded-xl transition-all cursor-pointer flex items-center justify-center gap-2 active:scale-95"
      >
        <RefreshCw className="w-4 h-4" />
        Try Again
      </button>
      {onCancel && (
        <button
          type="button"
          onClick={onCancel}
          className="w-full text-slate-500 hover:text-slate-700 font-semibold text-sm py-2 transition-colors cursor-pointer"
        >
          Go Back
        </button>
      )}
    </div>
  </div>
);

const ExpiredState: React.FC<{ onRetry: () => void }> = ({ onRetry }) => (
  <div className="p-8 text-center space-y-5">
    <div className="flex items-center justify-center">
      <div
        className="w-20 h-20 rounded-full flex items-center justify-center"
        style={{
          background: 'linear-gradient(135deg, #ffedd5 0%, #fed7aa 100%)',
          boxShadow: '0 0 0 8px rgba(249, 115, 22, 0.08)',
        }}
      >
        <Clock className="w-10 h-10 text-orange-500" strokeWidth={2} />
      </div>
    </div>

    <div className="space-y-1.5">
      <h3 className="text-xl font-extrabold text-slate-900 font-['Outfit']">
        Session Expired
      </h3>
      <p className="text-sm text-slate-500 font-medium">
        Your payment session expired. Please start a new payment.
      </p>
    </div>

    <button
      type="button"
      onClick={onRetry}
      className="w-full bg-[#0067ff] hover:bg-[#0052cc] text-white font-bold text-sm py-3 rounded-xl transition-all cursor-pointer flex items-center justify-center gap-2 active:scale-95"
    >
      <RefreshCw className="w-4 h-4" />
      Start New Payment
    </button>
  </div>
);

const TimeoutState: React.FC<{
  elapsedSeconds: number;
  onRetry: () => void;
}> = ({ elapsedSeconds, onRetry }) => (
  <div className="p-8 text-center space-y-5">
    <div className="flex items-center justify-center">
      <div
        className="w-20 h-20 rounded-full flex items-center justify-center"
        style={{
          background: 'linear-gradient(135deg, #e0f2fe 0%, #bae6fd 100%)',
          boxShadow: '0 0 0 8px rgba(14, 165, 233, 0.08)',
        }}
      >
        <Clock className="w-10 h-10 text-sky-500" strokeWidth={2} />
      </div>
    </div>

    <div className="space-y-1.5">
      <h3 className="text-xl font-extrabold text-slate-900 font-['Outfit']">
        Taking Longer Than Expected
      </h3>
      <p className="text-sm text-slate-500 font-medium leading-relaxed">
        Verification is delayed ({elapsedSeconds}s). If money was deducted, it will be refunded automatically.
      </p>
    </div>

    <div className="bg-blue-50 border border-blue-100 rounded-xl p-3 text-xs text-blue-700 font-medium text-left space-y-1">
      <p>💬 Contact the counter if this persists.</p>
      <p>📧 support@printbar.in</p>
    </div>

    <button
      type="button"
      onClick={onRetry}
      className="w-full bg-slate-100 hover:bg-slate-200 text-slate-700 font-bold text-sm py-3 rounded-xl transition-all cursor-pointer"
    >
      Try a New Payment
    </button>
  </div>
);

// ─── CSS Animations ───────────────────────────────────────────────────────────

const overlayStyles = `
@keyframes fadeIn {
  from { opacity: 0; }
  to   { opacity: 1; }
}
@keyframes slideUp {
  from { opacity: 0; transform: translateY(16px) scale(0.97); }
  to   { opacity: 1; transform: translateY(0) scale(1); }
}
@keyframes scaleIn {
  from { transform: scale(0.5); opacity: 0; }
  to   { transform: scale(1);   opacity: 1; }
}
`;
