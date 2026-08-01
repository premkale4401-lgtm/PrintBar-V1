/**
 * PrintBar — useKiosks hook
 *
 * Wraps kioskService with TanStack Query to fetch and cache
 * active kiosk station locations for the Kiosk Flow and Locations View.
 */

import { useQuery } from '@tanstack/react-query';
import { kioskService, DEFAULT_KIOSK_HUBS } from '../services/kiosk.service';
import { PrinterHub } from '../types';

export function useKiosks() {
  const { data: hubs = DEFAULT_KIOSK_HUBS, isLoading, isError, refetch } = useQuery<PrinterHub[]>({
    queryKey: ['kiosks-public'],
    queryFn: () => kioskService.getKiosks(),
    staleTime: 30_000,
  });

  return { hubs, isLoading, isError, refetch };
}
