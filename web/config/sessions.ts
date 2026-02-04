/**
 * Mission Control - Session Configuration
 * 
 * Defines trading session time windows in America/New_York timezone.
 * Used for session-based analysis (Distro, Regime, etc.)
 */

export interface SessionConfig {
    start: string; // HH:MM format
    end: string;   // HH:MM format
    timezone: string;
    displayName: string;
}

export const SESSION_CONFIGS: Record<string, SessionConfig> = {
    ASIA: {
        start: '18:00',
        end: '02:00',
        timezone: 'America/New_York',
        displayName: 'Asian Session',
    },
    LONDON: {
        start: '02:00',
        end: '08:00',
        timezone: 'America/New_York',
        displayName: 'London Session',
    },
    NY1: {
        start: '09:30',
        end: '12:00',
        timezone: 'America/New_York',
        displayName: 'NY Morning',
    },
    NY2: {
        start: '12:00',
        end: '16:00',
        timezone: 'America/New_York',
        displayName: 'NY Afternoon',
    },
    FIRST_30M: {
        start: '09:30',
        end: '10:00',
        timezone: 'America/New_York',
        displayName: 'First 30 Minutes',
    },
};

/**
 * Get session configuration
 */
export function getSessionConfig(session: string): SessionConfig {
    const config = SESSION_CONFIGS[session];
    if (!config) {
        throw new Error(`No configuration found for session: ${session}`);
    }
    return config;
}

/**
 * Get all session names
 */
export function getAvailableSessions(): string[] {
    return Object.keys(SESSION_CONFIGS);
}

/**
 * Check if a time falls within a session
 * @param time - Time in HH:MM format
 * @param session - Session name
 */
export function isTimeInSession(time: string, session: string): boolean {
    const config = getSessionConfig(session);
    const [hours, minutes] = time.split(':').map(Number);
    const [startHours, startMinutes] = config.start.split(':').map(Number);
    const [endHours, endMinutes] = config.end.split(':').map(Number);

    const timeMinutes = hours * 60 + minutes;
    const startTime = startHours * 60 + startMinutes;
    const endTime = endHours * 60 + endMinutes;

    // Handle overnight sessions (e.g., ASIA 18:00-02:00)
    if (endTime < startTime) {
        return timeMinutes >= startTime || timeMinutes < endTime;
    }

    return timeMinutes >= startTime && timeMinutes < endTime;
}
