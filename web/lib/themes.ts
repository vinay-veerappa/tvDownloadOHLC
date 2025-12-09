export type ThemeParams = {
    chart: {
        background: string; // Solid or gradient top
        backgroundBottom?: string; // Gradient bottom (optional)
        grid: string;
        crosshair: string;
    };
    candle: {
        upBody: string;
        upWick: string;
        upBorder: string;
        downBody: string;
        downWick: string;
        downBorder: string;
    };
    ui: {
        text: string;
        decoration: string; // Panel borders, generic dividers
    };
    tools: {
        primary: string; // Trendlines, foreground tools
        secondary: string; // Accents, selection, levels
        transparentFill: string; // Standard opacity fill (e.g. 10-20%)
    };
};

export const THEMES: Record<string, ThemeParams> = {
    'institutional-dark': {
        chart: {
            background: '#131722',
            grid: '#2a2e39',
            crosshair: '#B2B5BE',
        },
        candle: {
            upBody: '#089981',
            upWick: '#089981',
            upBorder: '#089981',
            downBody: '#F23645',
            downWick: '#F23645',
            downBorder: '#F23645',
        },
        ui: {
            text: '#B2B5BE',
            decoration: '#2A2E39',
        },
        tools: {
            primary: '#FFFFFF',
            secondary: '#2962FF',
            transparentFill: 'rgba(41, 98, 255, 0.15)',
        }
    },
    'clean-slate': {
        chart: {
            background: '#FFFFFF',
            grid: '#E6E6E6',
            crosshair: '#505050',
        },
        candle: {
            upBody: '#00897B',
            upWick: '#004D40',
            upBorder: '#004D40',
            downBody: '#E53935',
            downWick: '#B71C1C',
            downBorder: '#B71C1C',
        },
        ui: {
            text: '#131722',
            decoration: '#E0E3EB',
        },
        tools: {
            primary: '#000000',
            secondary: '#FF9800',
            transparentFill: 'rgba(255, 152, 0, 0.15)',
        }
    },
    'monochrome-slate': { // Dark
        chart: {
            background: '#18191c',
            grid: '#2a2e39',
            crosshair: '#90a4ae',
        },
        candle: {
            upBody: '#cfd8dc',
            upWick: '#78909c',
            upBorder: '#cfd8dc',
            downBody: '#546e7a',
            downWick: '#78909c',
            downBorder: '#546e7a',
        },
        ui: {
            text: '#90a4ae',
            decoration: '#2a2e39',
        },
        tools: {
            primary: '#cfd8dc',
            secondary: '#78909c',
            transparentFill: 'rgba(120, 144, 156, 0.1)',
        }
    },
    'institutional-blue': { // Bloomberg Dark
        chart: {
            background: '#0a1021',
            grid: '#172138',
            crosshair: '#6c8ea4',
        },
        candle: {
            upBody: '#2962ff',
            upWick: '#6c8ea4',
            upBorder: '#2962ff',
            downBody: '#b0bec5',
            downWick: '#6c8ea4',
            downBorder: '#b0bec5',
        },
        ui: {
            text: '#6c8ea4',
            decoration: '#172138',
        },
        tools: {
            primary: '#b0bec5',
            secondary: '#2962ff',
            transparentFill: 'rgba(41, 98, 255, 0.15)',
        }
    },
    'muted-earth': { // Dark
        chart: {
            background: '#1e201f',
            grid: '#333534',
            crosshair: '#dcedc8',
        },
        candle: {
            upBody: '#69f0ae',
            upWick: '#dcedc8',
            upBorder: '#69f0ae',
            downBody: '#ff8a80',
            downWick: '#ff8a80',
            downBorder: '#ff8a80',
        },
        ui: {
            text: '#dcedc8',
            decoration: '#333534',
        },
        tools: {
            primary: '#dcedc8',
            secondary: '#ffccbc',
            transparentFill: 'rgba(220, 237, 200, 0.1)',
        }
    }
};

export type ThemeName = keyof typeof THEMES;
