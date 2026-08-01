/**
 * PrintBar — useCheckout hook
 *
 * Wraps the checkout flow:
 * 1. Calls POST /api/v1/checkout with the print config.
 * 2. Receives { jobId, paymentUrl }.
 * 3. Redirects user to Easebuzz paymentUrl (same-tab redirect per doc 09).
 *
 * jobId is stored in sessionStorage so StepPrinting can pick it up
 * after the user returns from the Easebuzz payment page.
 */

import { useState, useCallback } from 'react';
import { paymentService, CheckoutResult } from '../services/payment.service';
import { PrintBarApiError } from '../lib/api';
import { PrintConfig } from '../types';

export const JOB_ID_STORAGE_KEY = 'pb_current_job_id';

interface UseCheckoutResult {
  initiateCheckout: (config: PrintConfig, pageCount: number, fileId: string) => Promise<CheckoutResult | null>;
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
    ): Promise<CheckoutResult | null> => {
      setIsLoading(true);
      setError(null);
      setErrorCode(null);

      try {
        const result = await paymentService.initiateCheckout({
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

        // Store jobId so StepPrinting can find it after Easebuzz redirect.
        sessionStorage.setItem(JOB_ID_STORAGE_KEY, result.jobId);
        setJobId(result.jobId);

        // Same-tab redirect to Easebuzz payment page.
        window.location.href = result.paymentUrl;

        return result;
      } catch (err) {
        if (err instanceof PrintBarApiError) {
          setError(err.message);
          setErrorCode(err.code);
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
