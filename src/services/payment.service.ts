/**
 * PrintBar — Payment Service
 *
 * POST /api/v1/payments/create-order → create Razorpay order (returns orderId + public keyId)
 * POST /api/v1/payments/verify       → verify Razorpay HMAC-SHA256 signature
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

export interface RazorpayOrderResult {
  jobId: string;
  paymentId: string;
  razorpayOrderId: string;
  amountPaise: number;
  currency: string;
  keyId: string;
  totalInr: string;
  breakdown?: Record<string, any>;
  idempotent?: boolean;
}

export interface RazorpayVerifyParams {
  razorpay_order_id: string;
  razorpay_payment_id: string;
  razorpay_signature: string;
  job_id: string;
}

export interface RazorpayVerifyResult {
  jobId: string;
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
   * Creates a Razorpay order and print job.
   * Returns orderId, amount in paise, currency, and the public KEY_ID.
   */
  async createRazorpayOrder(params: CheckoutParams): Promise<RazorpayOrderResult> {
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

    return apiFetch<RazorpayOrderResult>({
      method: 'POST',
      url: `/payments/create-order?${searchParams.toString()}`,
    });
  },

  /**
   * Verifies Razorpay payment signature server-side.
   */
  async verifyRazorpayPayment(data: RazorpayVerifyParams): Promise<RazorpayVerifyResult> {
    return apiFetch<RazorpayVerifyResult>({
      method: 'POST',
      url: '/payments/verify',
      data,
    });
  },

  /**
   * Backward-compatible helper method mapping to createRazorpayOrder.
   */
  async initiateCheckout(params: CheckoutParams): Promise<any> {
    return this.createRazorpayOrder(params);
  },

  /**
   * Polls payment and job status.
   */
  async getPaymentStatus(jobId: string): Promise<PaymentStatus> {
    return apiFetch<PaymentStatus>({
      method: 'GET',
      url: `/payments/${jobId}/status`,
    });
  },

  /**
   * Gets full print job details.
   */
  async getJob(jobId: string): Promise<JobDetails> {
    return apiFetch<JobDetails>({
      method: 'GET',
      url: `/jobs/${jobId}`,
    });
  },
};
