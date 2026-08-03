/**
 * PrintBar — useCheckout Hook (Provider-Agnostic)
 *
 * Orchestrates the complete payment flow without exposing the gateway to the UI.
 *
 * Flow:
 *   1. createOrder() → backend creates print job + gateway order
 *   2. openGatewayModal() → opens Razorpay checkout (hidden from UI)
 *   3. On modal success → verifyPayment() → backend verifies HMAC-SHA256
 *   4. startPolling() → polls backend until VERIFIED
 *   5. On modal dismiss → cancelPayment() → marks CANCELLED in DB
 *
 * The UI only calls:
 *   initiateCheckout()     — for UPI ID and app fallback flows
 *   initiateQrPayment()    — already handled by usePaymentPolling directly
 *
 * Security:
 *   - Frontend NEVER marks payment successful.
 *   - Backend verifies every payment before QUEUED state.
 *   - cancelPayment() ensures DB state stays consistent on dismiss.
 */

import { useState, useCallback, useRef } from 'react';
import {
  paymentService,
  CheckoutParams,
  OrderResult,
} from '../services/payment.service';
import { PrintBarApiError } from '../lib/api';
import { RAZORPAY_KEY_ID } from '../lib/env';
import { safeRandomUUID } from '../lib/uuid';
import { PrintConfig } from '../types';

export const JOB_ID_STORAGE_KEY = 'pb_current_job_id';

// ─── Return type ─────────────────────────────────────────────────────────────

export interface CheckoutResult {
  jobId: string;
  paymentId: string;
  paymentUrl: string;
  amount: string;
  currency: string;
  status: string;
}

export interface UseCheckoutResult {
  /** Initiates a complete checkout flow (order + modal + verify). */
  initiateCheckout: (
    config: PrintConfig,
    pageCount: number,
    fileId: string,
    onSuccess?: (jobId: string) => void,
  ) => Promise<CheckoutResult | null>;
  /** Just creates the order — returns order details for QR or custom UI. */
  createOrder: (
    config: PrintConfig,
    pageCount: number,
    fileId: string,
  ) => Promise<OrderResult | null>;
  isLoading: boolean;
  jobId: string | null;
  error: string | null;
  errorCode: string | null;
}

// ─── Helpers ─────────────────────────────────────────────────────────────────

function mapColorMode(mode: string): 'BW' | 'COLOR' {
  return mode === 'color' ? 'COLOR' : 'BW';
}

function mapPaperSize(size: string): 'A4' | 'A3' | 'LETTER' | 'LEGAL' {
  return size as 'A4' | 'A3' | 'LETTER' | 'LEGAL';
}

function mapPagesPerSheet(pps?: string): number {
  if (pps === '2 on 1') return 2;
  if (pps === '4 on 1') return 4;
  if (pps === '6 on 1') return 6;
  return 1;
}

function buildCheckoutParams(
  config: PrintConfig,
  pageCount: number,
  fileId: string,
): CheckoutParams {
  return {
    fileId,
    colorMode: mapColorMode(config.colorMode),
    paperSize: mapPaperSize(config.paperSize),
    copies: config.copies,
    duplex: config.duplex,
    pagesSelected: pageCount,
    pagesPerSheet: mapPagesPerSheet(config.pagesPerSheet),
    orientation: config.orientation,
    pageRange:
      config.pagesSelection === 'range' ? (config.pageRange ?? undefined) : undefined,
    idempotencyKey: safeRandomUUID(),
  };
}

/** Dynamically loads the Razorpay checkout script if not already present. */
function loadRazorpayScript(): Promise<boolean> {
  return new Promise((resolve) => {
    if ((window as any).Razorpay) {
      resolve(true);
      return;
    }
    const script = document.createElement('script');
    script.src = 'https://checkout.razorpay.com/v1/checkout.js';
    script.async = true;
    script.onload = () => resolve(true);
    script.onerror = () => resolve(false);
    document.body.appendChild(script);
  });
}

// ─── Hook ────────────────────────────────────────────────────────────────────

export function useCheckout(): UseCheckoutResult {
  const [isLoading, setIsLoading] = useState(false);
  const [jobId, setJobId] = useState<string | null>(
    sessionStorage.getItem(JOB_ID_STORAGE_KEY),
  );
  const [error, setError] = useState<string | null>(null);
  const [errorCode, setErrorCode] = useState<string | null>(null);
  const currentJobIdRef = useRef<string | null>(null);

  /**
   * Creates a payment order without opening the modal.
   * Returns order details for QR code generation or custom UI.
   */
  const createOrder = useCallback(async (
    config: PrintConfig,
    pageCount: number,
    fileId: string,
  ): Promise<OrderResult | null> => {
    setIsLoading(true);
    setError(null);
    setErrorCode(null);

    try {
      const params = buildCheckoutParams(config, pageCount, fileId);
      const orderResult = await paymentService.createOrder(params);

      sessionStorage.setItem(JOB_ID_STORAGE_KEY, orderResult.jobId);
      setJobId(orderResult.jobId);
      currentJobIdRef.current = orderResult.jobId;

      return orderResult;
    } catch (err) {
      handleError(err);
      return null;
    } finally {
      setIsLoading(false);
    }
  }, []);

  /**
   * Full checkout flow:
   *   1. Create order
   *   2a. MOCK MODE: Call devCompletePayment → same downstream flow as real payment
   *   2b. REAL MODE: Load Razorpay script → Open modal → verify server-side
   *   3. On success: call onSuccess
   *   4. On dismiss (real mode only): cancel payment in DB
   */
  const initiateCheckout = useCallback(async (
    config: PrintConfig,
    pageCount: number,
    fileId: string,
    onSuccess?: (jobId: string) => void,
  ): Promise<CheckoutResult | null> => {
    setIsLoading(true);
    setError(null);
    setErrorCode(null);

    try {
      // Step 1: Create order on backend.
      const params = buildCheckoutParams(config, pageCount, fileId);
      const orderResult = await paymentService.createOrder(params);

      sessionStorage.setItem(JOB_ID_STORAGE_KEY, orderResult.jobId);
      setJobId(orderResult.jobId);
      currentJobIdRef.current = orderResult.jobId;

      // Step 2a: Mock mode — bypass gateway entirely.
      // Executes the identical downstream flow: PAYMENT_SUCCESS → QUEUED → print.
      if (orderResult.isMockMode) {
        // In mock mode, we simulate the Razorpay callback to exercise the exact
        // same backend verification pipeline (which uses MockPaymentProvider).
        await paymentService.verifyPayment({
          razorpay_order_id: orderResult.razorpayOrderId || orderResult.gatewayOrderId,
          razorpay_payment_id: "pay_mock_" + Date.now().toString(),
          razorpay_signature: "mock_signature_bypass",
          job_id: orderResult.jobId,
        });

        if (onSuccess) {
          onSuccess(orderResult.jobId);
        }

        return {
          jobId: orderResult.jobId,
          paymentId: orderResult.paymentId,
          paymentUrl: '',
          amount: orderResult.totalInr,
          currency: orderResult.currency || 'INR',
          status: 'VERIFYING',
        };
      }

      // Step 2b: Real payment mode — load gateway SDK and open modal.
      const scriptLoaded = await loadRazorpayScript();
      if (!scriptLoaded) {
        throw new Error('Failed to load payment SDK. Please check your network connection.');
      }

      // Step 3: Open Razorpay modal (the UI never knows it's Razorpay).
      return await new Promise<CheckoutResult | null>((resolve) => {
        const options = {
          key: orderResult.keyId || RAZORPAY_KEY_ID,
          amount: orderResult.amountPaise,
          currency: orderResult.currency || 'INR',
          name: 'PrintBar',
          description: `Self-Service Printing`,
          order_id: orderResult.razorpayOrderId || orderResult.gatewayOrderId,
          prefill: {},
          config: {
            display: {
              blocks: {
                utib: { name: 'Pay using UPI', instruments: [{ method: 'upi' }] },
              },
              sequence: ['block.utib'],
              preferences: { show_default_blocks: true },
            },
          },
          handler: async (response: any) => {
            try {
              // Step 4: Verify payment signature on backend (never on frontend).
              await paymentService.verifyPayment({
                razorpay_order_id: response.razorpay_order_id,
                razorpay_payment_id: response.razorpay_payment_id,
                razorpay_signature: response.razorpay_signature,
                job_id: orderResult.jobId,
              });

              if (onSuccess) {
                onSuccess(orderResult.jobId);
              }

              resolve({
                jobId: orderResult.jobId,
                paymentId: orderResult.paymentId,
                paymentUrl: '',
                amount: orderResult.totalInr,
                currency: orderResult.currency,
                status: 'VERIFYING', // Not "SUCCESS" — polling drives the final state.
              });
            } catch (verifyErr) {
              console.error('[useCheckout] Verification error:', verifyErr);
              setError('Payment verification failed. Please contact support if money was deducted.');
              setErrorCode('PAY_001');
              resolve(null);
            }
          },
          modal: {
            ondismiss: async () => {
              // Step 5: Mark payment as CANCELLED in DB when user dismisses.
              try {
                await paymentService.cancelPayment(orderResult.jobId);
              } catch (_) {
                // Non-critical — best effort.
              }
              setError('Payment was cancelled. You can retry.');
              setErrorCode('PAY_DISMISSED');
              resolve(null);
            },
            escape: true,
            animation: true,
            backdropclose: false,
          },
          theme: {
            color: '#0067ff',
            hide_topbar: false,
          },
        };

        const rzp = new (window as any).Razorpay(options);

        rzp.on('payment.failed', async (failRes: any) => {
          console.error('[useCheckout] Payment failed:', failRes);
          try {
            await paymentService.cancelPayment(orderResult.jobId);
          } catch (_) {
            // Non-critical.
          }
          const description = failRes?.error?.description || 'Payment failed. Please try again.';
          setError(description);
          setErrorCode('PAY_FAILED');
          resolve(null);
        });

        rzp.open();
      });
    } catch (err) {
      handleError(err);
      return null;
    } finally {
      setIsLoading(false);
    }
  }, []);


  function handleError(err: unknown): void {
    if (err instanceof PrintBarApiError) {
      setError(err.message);
      setErrorCode(err.code);
    } else if (err instanceof Error) {
      setError(err.message);
      setErrorCode('PAY_UNKNOWN');
    } else {
      setError('Payment initiation failed. Please try again.');
      setErrorCode('PAY_UNKNOWN');
    }
  }

  return { initiateCheckout, createOrder, isLoading, jobId, error, errorCode };
}
