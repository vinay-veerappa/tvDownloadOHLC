/**
 * Centralized label formatting utility for consistent display across dashboard.
 * Ensures classifications, macros, and other enum values are consistently formatted.
 */

const HYDRA_LABELS: Record<string, string> = {
  Hydra_1: 'Hydra 1 (08:20-08:40 ET)',
  Hydra_2: 'Hydra 2 (09:20-09:40 ET)',
  Hydra_3: 'Hydra 3 (10:20-10:40 ET)',
};

const ICT_SESSION_LABELS: Record<string, string> = {
  Asia_1: 'Asia 1 (20:00-22:00 ET)',
  Asia_2: 'Asia 2 (22:00-00:00 ET)',
  Asia_3: 'Asia 3 (00:00-03:00 ET)',
  London_1: 'London 1 (03:00-08:00 ET)',
  London_2: 'London 2 (08:00-12:00 ET)',
  NY_AM_1: 'NY AM 1 (09:30-10:30 ET)',
  NY_AM_2: 'NY AM 2 (10:30-12:00 ET)',
  NY_Lunch: 'NY Lunch (12:00-13:00 ET)',
  NY_PM: 'NY PM (13:00-16:00 ET)',
  NY_Close: 'NY Close (15:30-16:00 ET)',
};

const JUDAS_CLASSIFICATION_LABELS: Record<string, string> = {
  bullish_judas: 'Bullish Judas',
  bearish_judas: 'Bearish Judas',
  trend_up: 'Trend Up',
  trend_down: 'Trend Down',
};

const INSTRUMENTS = ['ES1', 'NQ1', 'YM1', 'RTY1', 'CL1', 'GC1'];
const UPPERCASE_LABELS = ['VIX', 'RTH', 'AM', 'PM'];

/**
 * Format any label/enum value for display in UI.
 * Handles:
 * - Judas classifications (bullish_judas → Bullish Judas)
 * - ICT sessions (London_1 → London 1 (03:00-08:00 ET))
 * - Hydra macros (Hydra_1 → Hydra 1 (08:20-08:40 ET))
 * - Instruments (ES1, NQ1, etc. → uppercase)
 * - Abbreviations (VIX, RTH, AM, PM → uppercase)
 * - Snake case → Title Case (trend_up → Trend Up)
 */
export function formatLabel(str: string): string {
  if (!str) return '--';

  // Check Judas Classification mapping first
  if (JUDAS_CLASSIFICATION_LABELS[str]) {
    return JUDAS_CLASSIFICATION_LABELS[str];
  }

  // Check ICT session mapping
  if (ICT_SESSION_LABELS[str]) {
    return ICT_SESSION_LABELS[str];
  }

  // Check Hydra macro mapping
  if (HYDRA_LABELS[str]) {
    return HYDRA_LABELS[str];
  }

  // Check if it's an instrument (ES1, NQ1, etc.)
  const upper = str.toUpperCase();
  if (INSTRUMENTS.includes(upper)) return upper;

  // Handle other uppercase abbreviations
  if (UPPERCASE_LABELS.includes(upper)) return upper;

  // Default: convert snake_case to Title Case
  return str
    .split('_')
    .map(word => {
      const lower = word.toLowerCase();
      if (UPPERCASE_LABELS.map(l => l.toLowerCase()).includes(lower)) return lower.toUpperCase();
      return word.charAt(0).toUpperCase() + word.slice(1).toLowerCase();
    })
    .join(' ');
}

/**
 * Get the classification label with consistent formatting for Judas types.
 */
export function formatJudasClassification(value: string): string {
  return JUDAS_CLASSIFICATION_LABELS[value] || formatLabel(value);
}

/**
 * Get all Judas classification options with their formatted labels.
 */
export function getFormattedJudasOptions(): { value: string; label: string }[] {
  return Object.entries(JUDAS_CLASSIFICATION_LABELS).map(([value, label]) => ({
    value,
    label,
  }));
}

/**
 * Get all Hydra macro options with their formatted labels.
 */
export function getFormattedHydraOptions(): { value: string; label: string }[] {
  return Object.entries(HYDRA_LABELS).map(([value, label]) => ({
    value,
    label,
  }));
}

/**
 * Get all ICT session options with their formatted labels.
 */
export function getFormattedICTOptions(): { value: string; label: string }[] {
  return Object.entries(ICT_SESSION_LABELS).map(([value, label]) => ({
    value,
    label,
  }));
}

/**
 * Get all ICT session values (unformatted keys).
 */
export function getICTSessionValues(): string[] {
  return Object.keys(ICT_SESSION_LABELS);
}
