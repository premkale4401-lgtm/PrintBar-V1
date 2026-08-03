/**
 * PrintBar — Admin Service
 *
 * POST /api/v1/admin/auth/login        → admin login (email + password → JWT pair)
 * POST /api/v1/admin/auth/logout       → revoke refresh token
 * POST /api/v1/admin/auth/refresh      → token rotation
 * GET  /api/v1/admin/dashboard         → platform stats
 * GET  /api/v1/admin/jobs              → paginated job list
 * GET  /api/v1/admin/kiosks            → all kiosks
 * POST /api/v1/admin/kiosks            → register kiosk
 * GET  /api/v1/admin/kiosks/{id}       → single kiosk detail
 * POST /api/v1/admin/kiosks/{id}/rotate-key → rotate API key
 * GET  /api/v1/admin/pricing           → pricing rules
 * POST /api/v1/admin/pricing           → create pricing rule
 * GET  /api/v1/admin/audit-logs        → audit log
 * GET  /api/v1/admin/users             → platform users (super admin)
 */

import {
  apiFetch,
  setAdminTokens,
  clearAdminTokens,
  ADMIN_REFRESH_KEY,
} from '../lib/api';

// ─── Auth ─────────────────────────────────────────────────────────────────────

export interface AdminLoginResult {
  accessToken: string;
  refreshToken: string;
  expiresIn: number;
  role: string;
  name: string;
}

// ─── Dashboard ────────────────────────────────────────────────────────────────

export interface DashboardStats {
  today: {
    jobsCompleted: number;
    revenueInr: number;
  };
  total: {
    jobsCompleted: number;
  };
  activeKiosks: number;
  connectedKiosks: number;
  queuedJobs: number;
  recentJobs: AdminRecentJob[];
}

export interface AdminRecentJob {
  jobId: string;
  status: string;
  colorMode: string;
  totalInr: string;
  createdAt: string | null;
}

// ─── Jobs ─────────────────────────────────────────────────────────────────────

export interface AdminJob {
  jobId: string;
  sessionId: string;
  status: string;
  colorMode: string;
  paperSize: string;
  copies: number;
  pagesSelected: number;
  totalInr: string;
  kioskId: string | null;
  createdAt: string | null;
  completedAt: string | null;
}

export interface AdminJobsResult {
  jobs: AdminJob[];
  page: number;
  pageSize: number;
  total: number;
}

// ─── Kiosks ───────────────────────────────────────────────────────────────────

export interface AdminKiosk {
  kioskId: string;
  name: string;
  location: string;
  city: string;
  status: string;
  wsConnected: boolean;
  appVersion: string | null;
  cpuPercent: number | null;
  ramPercent: number | null;
  diskPercent: number | null;
  temperatureC: number | null;
  lastHeartbeat: string | null;
}

export interface KioskHeartbeatEntry {
  receivedAt: string | null;
  cpuPercent: number | null;
  ramPercent: number | null;
  diskPercent: number | null;
  temperatureC: number | null;
  printerStatus: string | null;
}

export interface AdminKioskDetail extends AdminKiosk {
  isActive: boolean;
  jobsCompletedToday: number;
  jobsCompletedTotal: number;
  recentHeartbeats: KioskHeartbeatEntry[];
}

// ─── Pricing ──────────────────────────────────────────────────────────────────

export interface AdminPricingRule {
  id: string;
  name: string;
  bwPriceInr: string;
  colorPriceInr: string;
  a3Multiplier: string;
  legalMultiplier: string;
  duplexDiscount: string;
  gstPercent: string;
  isActive: boolean;
  validFrom: string;
  validUntil: string | null;
  notes: string | null;
}

export interface CreatePricingRuleParams {
  name: string;
  bwPriceInr: string;
  colorPriceInr: string;
  a3Multiplier?: string;
  legalMultiplier?: string;
  duplexDiscount?: string;
  gstPercent?: string;
  notes?: string;
}

// ─── Audit Logs ───────────────────────────────────────────────────────────────

export interface AuditLogEntry {
  id: string;
  actorType: string;
  action: string;
  entityType: string | null;
  entityId: string | null;
  result: string;
  ipAddress: string | null;
  createdAt: string | null;
}

export interface AuditLogsResult {
  data: AuditLogEntry[];
  page: number;
  pageSize: number;
  total: number;
}

// ─── Users ────────────────────────────────────────────────────────────────────

export interface AdminUser {
  id: string;
  name: string;
  email: string;
  role: string;
  isActive: boolean;
  lastLoginAt: string | null;
  createdAt: string | null;
}

export interface AdminUsersResult {
  users: AdminUser[];
  page: number;
  pageSize: number;
  total: number;
}

// ─── Service ──────────────────────────────────────────────────────────────────

export const adminService = {
  // ── Authentication ──────────────────────────────────────────────────────────

  /** Logs in an admin user and stores JWT tokens. */
  async login(email: string, password: string): Promise<AdminLoginResult> {
    const result = await apiFetch<AdminLoginResult>({
      method: 'POST',
      url: '/admin/auth/login',
      data: { email, password },
    });
    setAdminTokens(result.accessToken, result.refreshToken);
    return result;
  },

  /** Revokes refresh token and clears stored credentials. */
  async logout(): Promise<void> {
    const refreshToken = localStorage.getItem(ADMIN_REFRESH_KEY);
    try {
      await apiFetch<{ message: string }>({
        method: 'POST',
        url: '/admin/auth/logout',
        data: { refreshToken },
      });
    } finally {
      clearAdminTokens();
    }
  },

  /** Rotates the access token using the stored refresh token. */
  async refreshToken(): Promise<string> {
    const refreshToken = localStorage.getItem(ADMIN_REFRESH_KEY);
    const result = await apiFetch<{ accessToken: string; refreshToken: string; expiresIn: number }>({
      method: 'POST',
      url: '/admin/auth/refresh',
      data: { refreshToken },
    });
    setAdminTokens(result.accessToken, result.refreshToken);
    return result.accessToken;
  },

  // ── Dashboard ───────────────────────────────────────────────────────────────

  async getDashboardStats(): Promise<DashboardStats> {
    return apiFetch<DashboardStats>({ method: 'GET', url: '/admin/dashboard' });
  },

  // ── Jobs ────────────────────────────────────────────────────────────────────

  async getJobs(page = 1, pageSize = 50, status?: string): Promise<AdminJobsResult> {
    const params = new URLSearchParams({
      page: String(page),
      page_size: String(pageSize),
    });
    if (status) params.append('status', status);
    return apiFetch<AdminJobsResult>({
      method: 'GET',
      url: `/admin/jobs?${params.toString()}`,
    });
  },

  // ── Kiosks ──────────────────────────────────────────────────────────────────

  async getKiosks(): Promise<AdminKiosk[]> {
    return apiFetch<AdminKiosk[]>({ method: 'GET', url: '/admin/kiosks' });
  },

  async getKioskDetail(kioskId: string): Promise<AdminKioskDetail> {
    return apiFetch<AdminKioskDetail>({ method: 'GET', url: `/admin/kiosks/${kioskId}` });
  },

  async registerKiosk(payload: {
    name: string;
    location: string;
    city?: string;
    notes?: string;
    latitude?: number;
    longitude?: number;
  }): Promise<{ kioskId: string; name: string; apiKey: string; warning: string }> {
    return apiFetch<{ kioskId: string; name: string; apiKey: string; warning: string }>({
      method: 'POST',
      url: '/admin/kiosks',
      data: payload,
    });
  },

  async rotateKioskKey(kioskId: string): Promise<{ kioskId: string; apiKey: string }> {
    return apiFetch<{ kioskId: string; apiKey: string }>({
      method: 'POST',
      url: `/admin/kiosks/${kioskId}/rotate-key`,
    });
  },

  // ── Pricing ─────────────────────────────────────────────────────────────────

  async getPricingRules(): Promise<AdminPricingRule[]> {
    return apiFetch<AdminPricingRule[]>({ method: 'GET', url: '/admin/pricing' });
  },

  async createPricingRule(
    params: CreatePricingRuleParams,
  ): Promise<{ id: string; name: string; active: boolean }> {
    return apiFetch<{ id: string; name: string; active: boolean }>({
      method: 'POST',
      url: '/admin/pricing',
      data: params,
    });
  },

  // ── Audit Logs ──────────────────────────────────────────────────────────────

  async getAuditLogs(page = 1, pageSize = 50, action?: string): Promise<AuditLogsResult> {
    const params = new URLSearchParams({
      page: String(page),
      page_size: String(pageSize),
    });
    if (action) params.append('action', action);
    return apiFetch<AuditLogsResult>({
      method: 'GET',
      url: `/admin/audit-logs?${params.toString()}`,
    });
  },

  // ── Users ────────────────────────────────────────────────────────────────────

  async getUsers(page = 1, pageSize = 20): Promise<AdminUsersResult> {
    const params = new URLSearchParams({
      page: String(page),
      page_size: String(pageSize),
    });
    return apiFetch<AdminUsersResult>({
      method: 'GET',
      url: `/admin/users?${params.toString()}`,
    });
  },
};
