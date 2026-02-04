/**
 * Mission Control - Panel Registry
 * 
 * Central registry for all dashboard panels.
 * Controls panel order, size, and metadata.
 */

export type PanelSize = 'sm' | 'md' | 'lg' | 'xl';

export interface PanelConfig {
    id: string;
    displayName: string;
    order: number;
    size: PanelSize;
    enabled: boolean;
    description?: string;
}

/**
 * Panel Registry
 * Order determines display sequence in the grid
 */
export const PANEL_REGISTRY: Record<string, PanelConfig> = {
    htfTrinity: {
        id: 'htfTrinity',
        displayName: 'HTF Trinity',
        order: 1,
        size: 'md',
        enabled: true,
        description: 'Weekly/Monthly/Daily context',
    },
    warGame: {
        id: 'warGame',
        displayName: 'War Game Matrix',
        order: 2,
        size: 'lg',
        enabled: true,
        description: 'Scenario-based planning',
    },
    candleScience: {
        id: 'candleScience',
        displayName: 'Candle Science',
        order: 3,
        size: 'md',
        enabled: true,
        description: 'Daily C3 projection',
    },
    premiumDiscount: {
        id: 'premiumDiscount',
        displayName: 'Premium/Discount',
        order: 4,
        size: 'md',
        enabled: true,
        description: 'Multi-timeframe P/D zones',
    },
    distro: {
        id: 'distro',
        displayName: 'Fuel (Distribution)',
        order: 5,
        size: 'lg',
        enabled: true,
        description: 'Session range analysis',
    },
    regimeStreak: {
        id: 'regimeStreak',
        displayName: 'Regime & Streaks',
        order: 6,
        size: 'md',
        enabled: true,
        description: 'Session TRUE/FALSE analysis',
    },
    modLod: {
        id: 'modLod',
        displayName: 'HOD/LOD Radar',
        order: 7,
        size: 'sm',
        enabled: true,
        description: 'Daily high/low timing',
    },
    economicCalendar: {
        id: 'economicCalendar',
        displayName: 'Economic Calendar',
        order: 8,
        size: 'md',
        enabled: true,
        description: 'Upcoming high-impact events',
    },
    narrative: {
        id: 'narrative',
        displayName: 'Narrative Feed',
        order: 9,
        size: 'md',
        enabled: true,
        description: 'Contextual market stories',
    },
    emaZones: {
        id: 'emaZones',
        displayName: 'EMA Zones',
        order: 10,
        size: 'md',
        enabled: true,
        description: 'Daily 5 EMA probability zones',
    },
};

/**
 * Get enabled panels sorted by order
 */
export function getEnabledPanels(): PanelConfig[] {
    return Object.values(PANEL_REGISTRY)
        .filter((panel) => panel.enabled)
        .sort((a, b) => a.order - b.order);
}

/**
 * Get panel configuration by ID
 */
export function getPanelConfig(id: string): PanelConfig {
    const config = PANEL_REGISTRY[id];
    if (!config) {
        throw new Error(`No configuration found for panel: ${id}`);
    }
    return config;
}

/**
 * Get grid column span for panel size
 */
export function getPanelColSpan(size: PanelSize): string {
    const spanMap: Record<PanelSize, string> = {
        sm: 'col-span-1',
        md: 'col-span-2',
        lg: 'col-span-3',
        xl: 'col-span-4',
    };
    return spanMap[size];
}
