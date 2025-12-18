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
    indicators: {
        sessions: {
            asia: string;
            london: string;
            ny: string;
            midnight: string;
            opacity: number;
        };
        profiler: {
            poc: string;
            valueArea: string;
            up: string;
            down: string;
        };
        levels: {
            pdh: string;
            pdl: string;
            open: string;
            close: string;
            settlement: string;
        };
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
        },
        indicators: {
            sessions: {
                asia: '#00E5FF',  // Electric Cyan
                london: '#FF6D00', // Vivid Orange
                ny: '#2962FF',    // Royal Blue
                midnight: '#ECEFF1', // White/Silver
                opacity: 0.25      // Increased from 0.15
            },
            profiler: {
                poc: '#FF1744',   // Bright Red
                valueArea: '#2979FF', // Bright Blue
                up: '#00E676',    // Bright Green
                down: '#FF1744'   // Bright Red
            },
            levels: {
                pdh: '#B0BEC5',
                pdl: '#B0BEC5',
                open: '#1DE9B6',  // Teal Accent
                close: '#FFEA00', // Yellow Accent
                settlement: '#FF9100' // Orange Accent
            }
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
        },
        indicators: {
            sessions: {
                asia: '#006064', // Deep Teal (High Contrast on White)
                london: '#E65100', // Deep Orange
                ny: '#1565C0', // Deep Blue
                midnight: '#455A64', // Dark Grey
                opacity: 0.20 // Increased from 0.12
            },
            profiler: {
                poc: '#D50000',
                valueArea: '#0D47A1',
                up: '#00695C',
                down: '#C62828'
            },
            levels: {
                pdh: '#546E7A',
                pdl: '#546E7A',
                open: '#004D40',
                close: '#F9A825',
                settlement: '#FF6F00'
            }
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
        },
        indicators: {
            sessions: {
                asia: '#90A4AE', // Slate Blue
                london: '#E0E0E0', // Light Grey/Silver
                ny: '#FFFFFF',    // White
                midnight: '#CFD8DC',
                opacity: 0.25     // Increased
            },
            profiler: {
                poc: '#FFFFFF',
                valueArea: '#90A4AE',
                up: '#cfd8dc',
                down: '#546e7a'
            },
            levels: {
                pdh: '#ECEFF1',
                pdl: '#ECEFF1',
                open: '#B0BEC5',
                close: '#90A4AE',
                settlement: '#78909C'
            }
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
        },
        indicators: {
            sessions: {
                asia: '#651FFF',  // Deep Purple/Electric
                london: '#FFD600', // Bright Yellow
                ny: '#00B0FF',    // Electric Light Blue
                midnight: '#B0BEC5',
                opacity: 0.25
            },
            profiler: {
                poc: '#FFAB00',
                valueArea: '#2962FF',
                up: '#2962FF',
                down: '#B0BEC5'
            },
            levels: {
                pdh: '#82B1FF',
                pdl: '#82B1FF',
                open: '#00E676',
                close: '#FFFF00',
                settlement: '#FF9100'
            }
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
        },
        indicators: {
            sessions: {
                asia: '#00E676',  // Bright Green
                london: '#FFEA00', // Bright Yellow
                ny: '#2979FF',    // Bright Blue
                midnight: '#CFD8DC',
                opacity: 0.25
            },
            profiler: {
                poc: '#FF6E40',   // Deep Orange
                valueArea: '#69F0AE',
                up: '#69F0AE',
                down: '#FF5252'
            },
            levels: {
                pdh: '#F4FF81',
                pdl: '#F4FF81',
                open: '#64FFDA',
                close: '#FFFF00',
                settlement: '#FFAB40'
            }
        }
    }
};

export type ThemeName = keyof typeof THEMES;
