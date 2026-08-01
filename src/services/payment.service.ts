/**
 * PrintBar — Payment Service
 *
 * POST /api/v1/checkout              → initiate payment (creates job + Easebuzz payment)
 * GET  /api/v1/payments/{id}/status  → poll payment + job status
 * GET  /api/v1/jobs/{id}             → get full job details
 */

import { apiFetch } from '../lib/api';

export interface CheckoutParams {
  fileId: string;
  colorMode: 'BW' | 'COLOR';
  paperSize: 'A4' | 'A3' | 'LETTER' | 'LEGAL';
  copies: number;
  duplex: boolean;
  pagesSelected: number;
  pagesPerSheet: number;
  orientation: 'portrait' | 'landscape';
  pageRange?: string;
  idempotencyKey?: string;
}

export interface CheckoutResult {
  jobId: string;
  paymentId: string;
  paymentUrl: string;
  amount: string;
  currency: string;
  status: string;
}

export interface PaymentStatus {
  jobId: string;
  jobStatus: string;
  paymentStatus: string;
  totalInr: string;
  paidAt: string | null;
}

export interface JobDetails {
  jobId: string;
  status: string;
  colorMode: string;
  paperSize: string;
  copies: number;
  duplex: boolean;
  pagesSelected: number;
  subtotalInr: string;
  gstInr: string;
  totalInr: string;
  kioskId: string | null;
  startedAt: string | null;
  completedAt: string | null;
  failureReason: string | null;
  createdAt: string | null;
}

export const paymentService = {
  /**
   * Initiates checkout by creating a print job and an Easebuzz payment session.
   * Returns the paymentUrl that the frontend should redirect the user to.
   *
   * The backend recalculates price — never trust frontend amounts.
   */
  async initiateCheckout(params: CheckoutParams): Promise<CheckoutResult> {
    // Build query string params (backend uses Query params, not JSON body for checkout).
    const searchParams = new URLSearchParams({
      file_id: params.fileId,
      color_mode: params.colorMode,
      paper_size: params.paperSize,
      copies: String(params.copies),
      duplex: String(params.duplex),
      pages_selected: String(params.pagesSelected),
      pages_per_sheet: String(params.pagesPerSheet),
      orientation: params.orientation,
    });

    if (params.pageRange) {
      searchParams.append('page_range', params.pageRange);
    }
    if (params.idempotencyKey) {
      searchParams.append('idempotency_key', params.idempotencyKey);
    }

    return apiFetch<CheckoutResult>({
      method: 'POST',
      url: `/checkout?${searchParams.toString()}`,
    });
  },

  /**
   * Polls payment and job status.
   * Call every 3 seconds after redirect back from Easebuzz,
   * or as a fallback when WebSocket is unavailable.
   */
  async getPaymentStatus(jobId: string): Promise<PaymentStatus> {
    return apiFetch<PaymentStatus>({
      method: 'GET',
      url: `/payments/${jobId}/status`,
    });
  },

  /**
   * Gets full print job details.
   * Used on the success screen to display accurate job summary.
   */
  async getJob(jobId: string): Promise<JobDetails> {
    return apiFetch<JobDetails>({
      method: 'GET',
      url: `/jobs/${jobId}`,
    });
  },
};
