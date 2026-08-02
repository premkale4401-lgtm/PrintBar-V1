/**
 * PrintBar — Payment Service (Provider-Agnostic)
 *
 * All API calls for payments go through this service.
 * The frontend does NOT know which payment gateway is being used.
 * Fields like razorpay_order_id are treated as opaque gateway tokens.
 *
 * Endpoints:
 *   POST /api/v1/payments/create-order    → create order (returns gateway details)
 *   POST /api/v1/payments/verify          → verify callback signature
 *   POST /api/v1/payments/{id}/cancel     → cancel payment
 *   GET  /api/v1/payments/{id}/status     → poll status + verification stage
 *   GET  /api/v1/payments/{id}/poll-order → poll gateway order (QR flow)
 */

import { apiFetch } from '../lib/api';

// ─── Request Params ──────────────────────────────────────────────────────────

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

export interface PaymentVerifyParams {
  razorpay_order_id: string;
  razorpay_payment_id: string;
  razorpay_signature: string;
  job_id: string;
}

// ─── Response Types ───────────────────────────────────────────────────────────

export interface CheckoutResult {
  jobId: string;
  paymentId: string;
  paymentUrl: string;
  amount: string;
  currency: string;
  status: string;
}

export interface OrderResult {
  /** Our internal print job UUID. */
  jobId: string;
  paymentId: string;
  /** Gateway order ID — treated as an opaque token by the frontend. */
  gatewayOrderId: string;
  /** Backward compat alias. Same as gatewayOrderId. */
  razorpayOrderId: string;
  /** Amount in smallest currency unit (paise for INR). */
  amountPaise: number;
  currency: string;
  /** Public gateway key — safe for frontend modal initialization. */
  keyId: string;
  totalInr: string;
  breakdown?: Record<string, unknown>;
  idempotent?: boolean;
}

export interface PaymentVerifyResult {
  jobId: string;
  status: string;
}

/** Verification stage returned by the polling endpoint. */
export type VerificationStage =
  | 'PENDING'
  | 'VERIFYING'
  | 'VERIFIED'
  | 'FAILED'
  | 'CANCELLED'
  | 'EXPIRED';

export interface PaymentStatusResult {
  jobId: string;
  jobStatus: string;
  paymentStatus: string;
  verificationStage: VerificationStage;
  totalInr: string;
  paidAt: string | null;
}

export interface OrderPollResult {
  isPaid: boolean;
  verificationStage: VerificationStage;
  jobId?: string;
  jobStatus?: string;
  gatewayError?: boolean;
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

// ─── Service ─────────────────────────────────────────────────────────────────

export const paymentService = {
  /**
   * Creates a payment order with the backend.
   * Returns gateway order details for the payment UI.
   * The frontend does not know which gateway is being used.
   */
  async createOrder(params: CheckoutParams): Promise<OrderResult> {
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

    return apiFetch<OrderResult>({
      method: 'POST',
      url: `/payments/create-order?${searchParams.toString()}`,
    });
  },

  /**
   * Backward-compat alias — maps to createOrder.
   */
  async createRazorpayOrder(params: CheckoutParams): Promise<OrderResult> {
    return this.createOrder(params);
  },

  /**
   * Backward-compat alias — maps to createOrder.
   */
  async initiateCheckout(params: CheckoutParams): Promise<OrderResult> {
    return this.createOrder(params);
  },

  /**
   * Verifies the payment gateway callback signature server-side.
   * Called after the payment modal handler fires.
   */
  async verifyPayment(data: PaymentVerifyParams): Promise<PaymentVerifyResult> {
    return apiFetch<PaymentVerifyResult>({
      method: 'POST',
      url: '/payments/verify',
      data,
    });
  },

  /**
   * Backward-compat alias — maps to verifyPayment.
   */
  async verifyRazorpayPayment(data: PaymentVerifyParams): Promise<PaymentVerifyResult> {
    return this.verifyPayment(data);
  },

  /**
   * Cancels a payment when the user dismisses the payment modal.
   * Marks payment as CANCELLED in the backend — job remains retryable.
   */
  async cancelPayment(jobId: string): Promise<void> {
    await apiFetch<{ message: string }>({
      method: 'POST',
      url: `/payments/${jobId}/cancel`,
    });
  },

  /**
   * Polls payment + job status + verification stage.
   * Call every 2.5 seconds after payment modal closes.
   * Stop polling when verificationStage reaches VERIFIED, FAILED, or CANCELLED.
   */
  async getPaymentStatus(jobId: string): Promise<PaymentStatusResult> {
    return apiFetch<PaymentStatusResult>({
      method: 'GET',
      url: `/payments/${jobId}/status`,
    });
  },

  /**
   * Polls the gateway for the current order payment status.
   * Used by the QR payment flow — call every 3 seconds while showing QR.
   * Returns isPaid=true when the customer has completed payment.
   */
  async pollOrderStatus(jobId: string): Promise<OrderPollResult> {
    return apiFetch<OrderPollResult>({
      method: 'GET',
      url: `/payments/${jobId}/poll-order`,
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

  /**
   * DEV ONLY — Bypasses payment gateway and marks payment SUCCESS immediately.
   * Only works when backend ENVIRONMENT=development.
   * Returns 403 in staging/production — safe to call without env checks on frontend.
   */
  async devCompletePayment(jobId: string): Promise<{ jobId: string; status: string }> {
    return apiFetch<{ jobId: string; status: string }>({
      method: 'POST',
      url: `/payments/dev/complete?job_id=${jobId}`,
    });
  },
};

// ─── Backward-Compat Type Aliases ─────────────────────────────────────────────
/** @deprecated Use PaymentStatusResult instead. */
export type PaymentStatus = PaymentStatusResult;
/** @deprecated Use OrderResult instead. */
export type RazorpayOrderResult = OrderResult;
/** @deprecated Use PaymentVerifyParams instead. */
export type RazorpayVerifyParams = PaymentVerifyParams;
