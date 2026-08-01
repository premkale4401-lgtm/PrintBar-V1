/**
 * PrintBar — Pricing Service
 *
 * GET /api/v1/pricing/calculate → real-time price calculation (no auth required)
 * GET /api/v1/pricing/config    → active pricing configuration
 *
 * The frontend NEVER calculates prices. This service is the only source of truth.
 */

import { apiFetch } from '../lib/api';

export interface PriceCalculationParams {
  pages: number;
  colorMode: 'BW' | 'COLOR';
  paperSize: 'A4' | 'A3' | 'LETTER' | 'LEGAL';
  copies: number;
  duplex: boolean;
  pagesPerSheet: 1 | 2 | 4 | 6;
}

export interface PriceBreakdown {
  subtotalInr: number;
  gstInr: number;
  totalInr: number;
  sheets: number;
  pricePerSheetInr: number;
  gstPercent: number;
  pages: number;
  copies: number;
  colorMode: string;
  paperSize: string;
  duplex: boolean;
  pagesPerSheet: number;
}

export interface PricingConfig {
  bwPriceInr: string;
  colorPriceInr: string;
  a3Multiplier: string;
  legalMultiplier: string;
  duplexDiscount: string;
  gstPercent: string;
  currency: string;
  validFrom: string;
}

export const pricingService = {
  /**
   * Calls the backend to calculate an exact price for the current print config.
   * Parses string decimal amounts from backend into JavaScript numbers to prevent
   * TypeError runtime exceptions when calling .toFixed(2) in UI components.
   */
  async calculatePrice(params: PriceCalculationParams): Promise<PriceBreakdown> {
    const searchParams = new URLSearchParams({
      pages: String(params.pages),
      color_mode: params.colorMode,
      paper_size: params.paperSize,
      copies: String(params.copies),
      duplex: String(params.duplex),
      pages_per_sheet: String(params.pagesPerSheet),
    });

    const raw = await apiFetch<any>({
      method: 'GET',
      url: `/pricing/calculate?${searchParams.toString()}`,
    });

    return {
      subtotalInr: typeof raw.subtotalInr === 'number' ? raw.subtotalInr : parseFloat(raw.subtotalInr ?? '0'),
      gstInr: typeof raw.gstInr === 'number' ? raw.gstInr : parseFloat(raw.gstInr ?? '0'),
      totalInr: typeof raw.totalInr === 'number' ? raw.totalInr : parseFloat(raw.totalInr ?? '0'),
      sheets: Number(raw.sheets ?? 0),
      pricePerSheetInr: typeof raw.pricePerSheetInr === 'number' ? raw.pricePerSheetInr : parseFloat(raw.pricePerSheetInr ?? '0'),
      gstPercent: typeof raw.gstPercent === 'number' ? raw.gstPercent : parseFloat(raw.gstPercent ?? '18'),
      pages: Number(raw.pagesToPrint ?? raw.pages ?? params.pages),
      copies: Number(raw.copies ?? params.copies),
      colorMode: raw.colorMode ?? params.colorMode,
      paperSize: raw.paperSize ?? params.paperSize,
      duplex: Boolean(raw.duplex ?? params.duplex),
      pagesPerSheet: Number(raw.pagesPerSheet ?? params.pagesPerSheet),
    };
  },

  /**
   * Returns the active pricing configuration for display in the UI.
   */
  async getPricingConfig(): Promise<PricingConfig> {
    return apiFetch<PricingConfig>({
      method: 'GET',
      url: '/pricing/config',
    });
  },
};
