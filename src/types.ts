export type SystemErrorType = 
  | 'hardware_disconnected'
  | 'transaction_declined'
  | 'out_of_paper'
  | 'connection_lost'
  | 'transmission_interrupted'
  | 'file_size_exceeded';

export type PrintStep = 'upload' | 'configure' | 'payment' | 'printing' | 'success';

export type AppView = 'landing' | 'kiosk' | 'locations' | 'status' | 'admin';

export type PaperSize = 'A4' | 'Letter' | 'A3' | 'Legal';
export type PrintColorMode = 'bw' | 'color';

export interface UploadedFile {
  id: string;
  name: string;
  size: number; // in bytes
  pageCount: number;
  type: string;
  previewUrl?: string;
  /** Backend file ID returned by POST /api/v1/uploads */
  fileId?: string;
}

/** Backend guest session returned by POST /api/v1/sessions */
export interface GuestSession {
  sessionId: string;
  token: string;
  expiresAt: string;
  tokenType: string;
}

/** Backend-calculated price breakdown (never computed locally) */
export interface PriceBreakdown {
  subtotalInr: number;
  gstInr: number;
  totalInr: number;
  sheets: number;
  pricePerSheetInr: number;
  gstPercent: number;
}

/** WebSocket job status event payload */
export interface JobStatusEvent {
  type: string;
  jobId?: string;
  status?: string;
  progress?: number;
  currentPage?: number;
  totalPages?: number;
  message?: string;
}

export interface PrintConfig {
  file: UploadedFile | null;
  files?: UploadedFile[];
  copies: number;
  paperSize: PaperSize;
  colorMode: PrintColorMode;
  duplex: boolean; // double-sided
  orientation: 'portrait' | 'landscape';
  selectedHubId: string;
  pagesPerSheet?: '1 on 1' | '2 on 1' | '4 on 1' | '6 on 1';
  pagesSelection?: 'all' | 'range';
  pageRange?: string;
}

export interface PrinterHub {
  id: string;
  name: string;
  address: string;
  city: string;
  distanceKm: number;
  status: 'online' | 'warning' | 'offline';
  paperLevel: number; // 0 - 100
  tonerLevel: number; // 0 - 100
  colorAvailable: boolean;
  a3Available: boolean;
  is24Hours: boolean;
  currentQueue: number;
  completedToday: number;
  lastMaintenance: string;
  latitude: number;
  longitude: number;
}

export interface SystemAlert {
  id: string;
  code: string;
  title: string;
  severity: 'critical' | 'warning' | 'info';
  hubId: string;
  hubName: string;
  timestamp: string;
  message: string;
  suggestedAction: string;
  resolved: boolean;
}

export interface PrintJobRecord {
  id: string;
  fileName: string;
  pages: number;
  copies: number;
  hubName: string;
  totalCost: number;
  status: 'completed' | 'printing' | 'queued' | 'failed';
  timestamp: string;
  pickupPin: string;
  colorMode: PrintColorMode;
}
