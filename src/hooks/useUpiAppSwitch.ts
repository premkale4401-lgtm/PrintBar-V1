/**
 * PrintBar — useUpiAppSwitch Hook
 *
 * Detects platform and builds UPI intent URLs for mobile app-switch.
 *
 * Architecture:
 *   - On Android mobile: opens UPI deep link (phonepe://, tez://, etc.)
 *   - On desktop: UPI apps cannot be launched — QR or Razorpay modal used instead
 *   - Falls back gracefully if the specific app is not installed
 *   - Razorpay modal fallback is invoked as last resort
 *
 * UPI Intent URL format (NPCI standard):
 *   upi://pay?pa={vpa}&pn={name}&am={amount}&tr={txnRef}&tn={note}&cu=INR
 *
 * App-specific schemes (Android):
 *   PhonePe:    phonepe://pay?...
 *   GPay:       tez://upi/pay?...
 *   Paytm:      paytmmp://pay?...
 *   BHIM:       upi://pay?... (BHIM uses the generic scheme)
 *   Amazon Pay: amazonpay://...
 *   WhatsApp:   whatsapp://pay (limited support)
 */

import { useCallback } from 'react';

export type UpiApp =
  | 'phonepe'
  | 'gpay'
  | 'paytm'
  | 'bhim'
  | 'amazon'
  | 'whatsapp'
  | 'generic';

export type Platform = 'android' | 'ios' | 'desktop';

export interface UpiPaymentParams {
  /** UPI VPA of the merchant (recipient). */
  merchantVpa: string;
  /** Merchant display name. */
  merchantName: string;
  /** Amount in INR (string with 2 decimals, e.g. "6.00"). */
  amountInr: string;
  /** Transaction reference (Razorpay order ID — NPCI txnRef field). */
  txnRef: string;
  /** Transaction note shown to customer. */
  txnNote?: string;
}

export interface UpiAppSwitchResult {
  /** True if the app was launched (intent fired). */
  launched: boolean;
  /** Platform detected. */
  platform: Platform;
  /** Whether this device can launch UPI apps. */
  canLaunchApps: boolean;
  /** Error if launch failed. */
  error?: string;
}

/**
 * Detects the current platform from the user agent.
 * NOTE: User agent detection is best-effort. Always have a fallback.
 */
export function detectPlatform(): Platform {
  const ua = navigator.userAgent.toLowerCase();
  if (/android/.test(ua)) return 'android';
  if (/iphone|ipad|ipod/.test(ua)) return 'ios';
  return 'desktop';
}

/**
 * Returns true if this device/browser can launch UPI intent URLs.
 * Currently only Android Chrome/WebView supports UPI intents reliably.
 */
export function canLaunchUpiApps(): boolean {
  return detectPlatform() === 'android';
}

/**
 * Builds the UPI intent URL for the given app and payment params.
 * Returns a universal `upi://pay?...` URL if app-specific scheme is not needed.
 */
function buildUpiIntentUrl(app: UpiApp, params: UpiPaymentParams): string {
  const base = new URLSearchParams({
    pa: params.merchantVpa,
    pn: params.merchantName,
    am: params.amountInr,
    tr: params.txnRef,
    tn: params.txnNote ?? `PrintBar Payment`,
    cu: 'INR',
  }).toString();

  switch (app) {
    case 'phonepe':
      // PhonePe uses its own scheme on Android.
      return `phonepe://pay?${base}`;
    case 'gpay':
      // Google Pay uses the tez:// scheme.
      return `tez://upi/pay?${base}`;
    case 'paytm':
      // Paytm uses paytmmp:// scheme.
      return `paytmmp://pay?${base}`;
    case 'bhim':
      // BHIM uses the standard upi:// scheme.
      return `upi://pay?${base}`;
    case 'amazon':
      // Amazon Pay UPI.
      return `amazonpay://pay?${base}`;
    case 'whatsapp':
      // WhatsApp Pay has limited UPI support.
      return `whatsapp://pay?${base}`;
    case 'generic':
    default:
      // Generic UPI — opens the UPI app picker on Android.
      return `upi://pay?${base}`;
  }
}

export interface UseUpiAppSwitchResult {
  /** Current platform. */
  platform: Platform;
  /** Whether UPI app launch is supported. */
  canLaunchApps: boolean;
  /** Launch a specific UPI app for payment. */
  launchApp: (app: UpiApp, params: UpiPaymentParams) => Promise<UpiAppSwitchResult>;
  /** Launch the generic UPI app picker. */
  launchGenericUpi: (params: UpiPaymentParams) => Promise<UpiAppSwitchResult>;
}

export function useUpiAppSwitch(): UseUpiAppSwitchResult {
  const platform = detectPlatform();
  const canLaunchApps = platform === 'android';

  const launchApp = useCallback(async (
    app: UpiApp,
    params: UpiPaymentParams,
  ): Promise<UpiAppSwitchResult> => {
    if (!canLaunchApps) {
      return {
        launched: false,
        platform,
        canLaunchApps: false,
        error: 'UPI app launch is only supported on Android devices.',
      };
    }

    const intentUrl = buildUpiIntentUrl(app, params);

    try {
      // Attempt to open the UPI app via intent URL.
      // This works in Android Chrome and most Android browsers.
      window.location.href = intentUrl;

      // Give the system a moment to process the intent.
      // If the app is not installed, the browser will stay on the page.
      await new Promise<void>((resolve) => setTimeout(resolve, 500));

      return { launched: true, platform, canLaunchApps: true };
    } catch (err) {
      const error = err instanceof Error ? err.message : 'Failed to launch UPI app.';
      console.warn(`[useUpiAppSwitch] Failed to launch ${app}:`, err);
      return { launched: false, platform, canLaunchApps, error };
    }
  }, [platform, canLaunchApps]);

  const launchGenericUpi = useCallback(async (
    params: UpiPaymentParams,
  ): Promise<UpiAppSwitchResult> => {
    return launchApp('generic', params);
  }, [launchApp]);

  return {
    platform,
    canLaunchApps,
    launchApp,
    launchGenericUpi,
  };
}
