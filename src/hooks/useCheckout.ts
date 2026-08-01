/**
 * PrintBar — useCheckout hook
 *
 * Integrated with Razorpay Standard Checkout:
 * 1. Calls POST /api/v1/payments/create-order with print configuration.
 * 2. Receives { jobId, razorpayOrderId, amountPaise, currency, keyId }.
 * 3. Dynamically loads Razorpay checkout script if needed.
 * 4. Opens Razorpay Modal (same tab, no redirect).
 * 5. On payment.success: calls POST /api/v1/payments/verify with signature.
 * 6. On verify success: stores jobId in sessionStorage and returns result.
 * 7. On modal.dismiss or payment.failed: handles cancellation / failure cleanly.
 */

import { useState, useCallback } from 'react';
import { paymentService, CheckoutResult, RazorpayOrderResult } from '../services/payment.service';
import { PrintBarApiError } from '../lib/api';
import { RAZORPAY_KEY_ID } from '../lib/env';
import { PrintConfig } from '../types';

export const JOB_ID_STORAGE_KEY = 'pb_current_job_id';

interface UseCheckoutResult {
  initiateCheckout: (
    config: PrintConfig,
    pageCount: number,
    fileId: string,
    onSuccess?: (jobId: string) => void,
  ) => Promise<CheckoutResult | null>;
  isLoading: boolean;
  jobId: string | null;
  error: string | null;
  errorCode: string | null;
}

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

/** Loads the Razorpay checkout script if not present on window. */
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

export function useCheckout(): UseCheckoutResult {
  const [isLoading, setIsLoading] = useState(false);
  const [jobId, setJobId] = useState<string | null>(
    sessionStorage.getItem(JOB_ID_STORAGE_KEY),
  );
  const [error, setError] = useState<string | null>(null);
  const [errorCode, setErrorCode] = useState<string | null>(null);

  const initiateCheckout = useCallback(
    async (
      config: PrintConfig,
      pageCount: number,
      fileId: string,
      onSuccess?: (jobId: string) => void,
    ): Promise<CheckoutResult | null> => {
      setIsLoading(true);
      setError(null);
      setErrorCode(null);

      try {
        // Step 1: Ensure Razorpay JS SDK is loaded
        const scriptLoaded = await loadRazorpayScript();
        if (!scriptLoaded) {
          throw new Error('Failed to load Razorpay payment SDK. Please check your network.');
        }

        // Step 2: Create Razorpay Order on backend
        const orderRes: RazorpayOrderResult = await paymentService.createRazorpayOrder({
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
          idempotencyKey: crypto.randomUUID(),
        });

        sessionStorage.setItem(JOB_ID_STORAGE_KEY, orderRes.jobId);
        setJobId(orderRes.jobId);

        // Step 3: Open Razorpay Standard Checkout Modal
        return await new Promise<CheckoutResult | null>((resolve) => {
          const options = {
            key: orderRes.keyId || RAZORPAY_KEY_ID,
            amount: orderRes.amountPaise,
            currency: orderRes.currency || 'INR',
            name: 'PrintBar',
            description: `Self-Service Printing (${orderRes.totalInr} INR)`,
            order_id: orderRes.razorpayOrderId,
            handler: async (response: any) => {
              try {
                // Step 4: Verify payment signature on backend
                await paymentService.verifyRazorpayPayment({
                  razorpay_order_id: response.razorpay_order_id,
                  razorpay_payment_id: response.razorpay_payment_id,
                  razorpay_signature: response.razorpay_signature,
                  job_id: orderRes.jobId,
                });

                if (onSuccess) {
                  onSuccess(orderRes.jobId);
                }

                resolve({
                  jobId: orderRes.jobId,
                  paymentId: orderRes.paymentId,
                  paymentUrl: '',
                  amount: orderRes.totalInr,
                  currency: orderRes.currency,
                  status: 'QUEUED',
                });
              } catch (verifyErr) {
                console.error('Razorpay verification error:', verifyErr);
                setError('Payment verification failed.');
                setErrorCode('PAY_001');
                resolve(null);
              }
            },
            modal: {
              ondismiss: () => {
                setError('Payment checkout cancelled.');
                setErrorCode('PAY_DISMISSED');
                resolve(null);
              },
            },
            theme: {
              color: '#0067ff',
            },
          };

          const rzp = new (window as any).Razorpay(options);

          rzp.on('payment.failed', (failRes: any) => {
            console.error('Razorpay payment failed:', failRes);
            setError(failRes.error?.description || 'Payment failed. Please try again.');
            setErrorCode('PAY_FAILED');
            resolve(null);
          });

          rzp.open();
        });
      } catch (err) {
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
        return null;
      } finally {
        setIsLoading(false);
      }
    },
    [],
  );

  return { initiateCheckout, isLoading, jobId, error, errorCode };
}
