import { PrinterHub, SystemAlert, UploadedFile, PrintJobRecord } from '../types';

export const PRINTER_HUBS: PrinterHub[] = [
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

export const SAMPLE_FILES: UploadedFile[] = [];

export const INITIAL_ALERTS: SystemAlert[] = [];

export const RECENT_JOBS: PrintJobRecord[] = [];

export const PRICING_RATES = {
  bwPerPage: 0.10,
  colorPerPage: 0.35,
  paperMultiplier: {
    A4: 1.0,
    Letter: 1.0,
    Legal: 1.25,
    A3: 1.75,
  },
  duplexDiscountPercent: 0.15, // 15% discount for 2-sided
  taxRatePercent: 0.08, // 8% sales tax
};
