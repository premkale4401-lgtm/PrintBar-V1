/**
 * PrintBar — usePricing hook
 *
 * Uses TanStack Query to fetch the real-time price from the backend.
 * Re-fetches automatically whenever any print option changes.
 *
 * The frontend NEVER computes prices locally.
 * This hook is the only source of pricing truth in the UI.
 */

import { useQuery } from '@tanstack/react-query';
import { pricingService, PriceBreakdown, PriceCalculationParams } from '../services/pricing.service';
import { PrintConfig } from '../types';

// ─── Config mapper ────────────────────────────────────────────────────────────

function mapConfigToParams(config: PrintConfig, pageCount: number): PriceCalculationParams {
  // Map frontend color mode to backend format.
  const colorMode = config.colorMode === 'color' ? 'COLOR' : 'BW';

  // Map pagesPerSheet string to number.
  const ppsStr = config.pagesPerSheet ?? '1 on 1';
  const ppsNum = ppsStr === '2 on 1' ? 2 : ppsStr === '4 on 1' ? 4 : ppsStr === '6 on 1' ? 6 : 1;

  // Map paper size to backend format (already uppercase-compatible).
  const paperSize = config.paperSize as 'A4' | 'A3' | 'LETTER' | 'LEGAL';

  return {
    pages: pageCount,
    colorMode,
    paperSize,
    copies: config.copies,
    duplex: config.duplex,
    pagesPerSheet: ppsNum as 1 | 2 | 4 | 6,
  };
}

// ─── Hook ─────────────────────────────────────────────────────────────────────

interface UsePricingResult {
  price: PriceBreakdown | null;
  isLoading: boolean;
  isError: boolean;
  error: string | null;
}

export function usePricing(config: PrintConfig, pageCount: number): UsePricingResult {
  const params = mapConfigToParams(config, pageCount);

  // Query key includes all pricing-relevant fields so it auto-refetches on change.
  const queryKey = [
    'pricing',
    params.pages,
    params.colorMode,
    params.paperSize,
    params.copies,
    params.duplex,
    params.pagesPerSheet,
  ];

  const { data, isLoading, isError, error } = useQuery<PriceBreakdown, Error>({
    queryKey,
    queryFn: () => pricingService.calculatePrice(params),
    // Only fetch when we have at least 1 page.
    enabled: pageCount > 0,
    // Keep previous data while re-fetching (no blank/jump UI).
    placeholderData: (prev) => prev,
    staleTime: 5_000,
    retry: 2,
  });

  return {
    price: data ?? null,
    isLoading,
    isError,
    error: isError ? (error?.message ?? 'Failed to calculate price.') : null,
  };
}
