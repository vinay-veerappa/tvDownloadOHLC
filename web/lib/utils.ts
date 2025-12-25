import { clsx, type ClassValue } from "clsx"
import { twMerge } from "tailwind-merge"

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs))
}

export function formatTimeForTimezone(time: number, timezone: string = 'America/New_York'): string {
  const date = new Date(time * 1000);
  // Handle UTC explicitly if needed, though toLocaleString handles it well with 'UTC' or 'America/New_York'
  return date.toLocaleString('en-US', {
    timeZone: timezone === 'local' ? undefined : timezone,
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
    hour12: false
  });
}
