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
    },
    'ict-midnight': { // ICT - Pure Black with Neon Accents
        chart: {
            background: '#000000',
            grid: '#1a1a1a',
            crosshair: '#00ff88',
        },
        candle: {
            upBody: '#00ff88',      // Neon Green
            upWick: '#00ff88',
            upBorder: '#00ff88',
            downBody: '#ff0055',    // Neon Pink/Red
            downWick: '#ff0055',
            downBorder: '#ff0055',
        },
        ui: {
            text: '#ffffff',
            decoration: '#2a2a2a',
        },
        tools: {
            primary: '#00ddff',     // Cyan - High visibility for trendlines
            secondary: '#ffaa00',   // Orange - For FVGs and zones
            transparentFill: 'rgba(0, 221, 255, 0.12)',
        },
        indicators: {
            sessions: {
                asia: '#9d00ff',    // Purple
                london: '#ffdd00',  // Yellow
                ny: '#00ddff',      // Cyan
                midnight: '#666666',
                opacity: 0.18
            },
            profiler: {
                poc: '#ff0055',     // Neon Pink
                valueArea: '#00ddff',
                up: '#00ff88',
                down: '#ff0055'
            },
            levels: {
                pdh: '#00ddff',     // Cyan for previous levels
                pdl: '#00ddff',
                open: '#ffaa00',    // Orange for open
                close: '#ffdd00',   // Yellow for close
                settlement: '#9d00ff' // Purple for settlement
            }
        }
    },
    'ict-terminal': { // ICT - Classic Terminal Green
        chart: {
            background: '#0a0e0a',  // Very dark green-black
            grid: '#1a2e1a',
            crosshair: '#33ff33',
        },
        candle: {
            upBody: '#00ff00',      // Bright Green
            upWick: '#66ff66',
            upBorder: '#00ff00',
            downBody: '#ff3333',    // Bright Red
            downWick: '#ff6666',
            downBorder: '#ff3333',
        },
        ui: {
            text: '#33ff33',
            decoration: '#1a2e1a',
        },
        tools: {
            primary: '#00ffff',     // Cyan - Excellent contrast
            secondary: '#ffff00',   // Yellow - For zones
            transparentFill: 'rgba(0, 255, 255, 0.15)',
        },
        indicators: {
            sessions: {
                asia: '#ff00ff',    // Magenta
                london: '#ffff00',  // Yellow
                ny: '#00ffff',      // Cyan
                midnight: '#66ff66',
                opacity: 0.20
            },
            profiler: {
                poc: '#ffff00',     // Yellow POC
                valueArea: '#00ffff',
                up: '#00ff00',
                down: '#ff3333'
            },
            levels: {
                pdh: '#00ffff',
                pdl: '#00ffff',
                open: '#ffff00',
                close: '#ff00ff',
                settlement: '#ff9900'
            }
        }
    },
    'ict-ocean': { // ICT - Deep Blue Professional
        chart: {
            background: '#0a1628',  // Deep navy
            grid: '#1a2d4a',
            crosshair: '#64b5f6',
        },
        candle: {
            upBody: '#26c6da',      // Cyan
            upWick: '#4dd0e1',
            upBorder: '#26c6da',
            downBody: '#ff6b6b',    // Coral Red
            downWick: '#ff8787',
            downBorder: '#ff6b6b',
        },
        ui: {
            text: '#b0c4de',        // Light steel blue
            decoration: '#1a2d4a',
        },
        tools: {
            primary: '#ffd700',     // Gold - Stands out beautifully
            secondary: '#ff69b4',   // Hot Pink - For zones
            transparentFill: 'rgba(255, 215, 0, 0.12)',
        },
        indicators: {
            sessions: {
                asia: '#ba68c8',    // Purple
                london: '#ffa726',  // Orange
                ny: '#42a5f5',      // Blue
                midnight: '#78909c',
                opacity: 0.22
            },
            profiler: {
                poc: '#ffd700',     // Gold
                valueArea: '#42a5f5',
                up: '#26c6da',
                down: '#ff6b6b'
            },
            levels: {
                pdh: '#ffd700',
                pdl: '#ffd700',
                open: '#26c6da',
                close: '#ff69b4',
                settlement: '#ffa726'
            }
        }
    },
    'ict-paper': { // ICT - High Contrast Light Theme
        chart: {
            background: '#fafafa',  // Off-white (easier on eyes than pure white)
            grid: '#d0d0d0',
            crosshair: '#1976d2',
        },
        candle: {
            upBody: '#00897b',      // Teal
            upWick: '#00695c',
            upBorder: '#00695c',
            downBody: '#d32f2f',    // Deep Red
            downWick: '#b71c1c',
            downBorder: '#b71c1c',
        },
        ui: {
            text: '#212121',
            decoration: '#e0e0e0',
        },
        tools: {
            primary: '#1976d2',     // Blue - Clear on white
            secondary: '#f57c00',   // Deep Orange - For zones
            transparentFill: 'rgba(25, 118, 210, 0.08)',
        },
        indicators: {
            sessions: {
                asia: '#7b1fa2',    // Purple
                london: '#f57c00',  // Orange
                ny: '#1976d2',      // Blue
                midnight: '#616161',
                opacity: 0.12
            },
            profiler: {
                poc: '#d32f2f',     // Red
                valueArea: '#1976d2',
                up: '#00897b',
                down: '#d32f2f'
            },
            levels: {
                pdh: '#1976d2',
                pdl: '#1976d2',
                open: '#00897b',
                close: '#f57c00',
                settlement: '#7b1fa2'
            }
        }
    },
    'ict-charcoal': { // ICT - Dark Grey with Vibrant Highlights
        chart: {
            background: '#1c1c1e',  // Dark charcoal
            grid: '#2c2c2e',
            crosshair: '#ff9f0a',
        },
        candle: {
            upBody: '#30d158',      // iOS Green
            upWick: '#32d74b',
            upBorder: '#30d158',
            downBody: '#ff453a',    // iOS Red
            downWick: '#ff6961',
            downBorder: '#ff453a',
        },
        ui: {
            text: '#e5e5e7',
            decoration: '#38383a',
        },
        tools: {
            primary: '#0a84ff',     // iOS Blue - Perfect contrast
            secondary: '#ff9f0a',   // iOS Orange - For zones
            transparentFill: 'rgba(10, 132, 255, 0.15)',
        },
        indicators: {
            sessions: {
                asia: '#bf5af2',    // iOS Purple
                london: '#ff9f0a',  // iOS Orange
                ny: '#0a84ff',      // iOS Blue
                midnight: '#8e8e93',
                opacity: 0.20
            },
            profiler: {
                poc: '#ff453a',     // iOS Red
                valueArea: '#0a84ff',
                up: '#30d158',
                down: '#ff453a'
            },
            levels: {
                pdh: '#64d2ff',     // iOS Cyan
                pdl: '#64d2ff',
                open: '#30d158',
                close: '#ff9f0a',
                settlement: '#bf5af2'
            }
        }
    }
};

export type ThemeName = keyof typeof THEMES;
