/**
 * PrintBar — Kiosk Service
 *
 * Fetches active printing kiosk stations from the backend API.
 */

import { apiClient } from '../lib/api';
import { PrinterHub } from '../types';

export const DEFAULT_KIOSK_HUBS: PrinterHub[] = [
  {
    id: 'hub-01',
    name: 'Main Digital Print Kiosk',
    address: '142 Main St, Suite 100',
    city: 'Metropolis',
    distanceKm: 0.0,
    status: 'online',
    paperLevel: 98,
    tonerLevel: 95,
    colorAvailable: true,
    a3Available: true,
    is24Hours: true,
    currentQueue: 0,
    completedToday: 142,
    lastMaintenance: '2026-07-25',
    latitude: 37.7749,
    longitude: -122.4194,
  },
];

export const kioskService = {
  /**
   * Fetches active kiosk stations from the backend API.
   */
  async getKiosks(): Promise<PrinterHub[]> {
    try {
      const response = await apiClient.get<{ success: true; data: any[] }>('/admin/kiosks');
      if (response.data?.data && Array.isArray(response.data.data) && response.data.data.length > 0) {
        return response.data.data.map((k: any) => ({
          id: k.kioskId || k.id,
          name: k.name || 'PrintBar Kiosk',
          address: k.location || k.address || 'Central Location',
          city: k.city || 'Metropolis',
          distanceKm: 0,
          status: k.status === 'ONLINE' ? 'online' : k.status === 'OFFLINE' ? 'offline' : 'warning',
          paperLevel: 100,
          tonerLevel: 100,
          colorAvailable: true,
          a3Available: true,
          is24Hours: true,
          currentQueue: 0,
          completedToday: 0,
          lastMaintenance: new Date().toISOString().split('T')[0],
          latitude: 37.7749,
          longitude: -122.4194,
        }));
      }
    } catch (err) {
      console.warn('Could not fetch kiosks from API, using default network hub:', err);
    }

    return DEFAULT_KIOSK_HUBS;
  },
};
