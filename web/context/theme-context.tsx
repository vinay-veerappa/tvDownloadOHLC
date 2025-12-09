'use client';

import React, { createContext, useContext, useEffect, useState } from 'react';
import { THEMES, ThemeName, ThemeParams } from '@/lib/themes';

interface ThemeContextType {
    theme: ThemeName;
    themeParams: ThemeParams;
    setTheme: (theme: ThemeName) => void;
    availableThemes: ThemeName[];
}

const ThemeContext = createContext<ThemeContextType | undefined>(undefined);

const STORAGE_KEY = 'chart_theme_preference';
const DEFAULT_THEME: ThemeName = 'institutional-dark';

export function ThemeProvider({ children }: { children: React.ReactNode }) {
    const [theme, setThemeState] = useState<ThemeName>(DEFAULT_THEME);
    const [mounted, setMounted] = useState(false);

    useEffect(() => {
        const saved = localStorage.getItem(STORAGE_KEY) as ThemeName;
        if (saved && THEMES[saved]) {
            setThemeState(saved);
        }
        setMounted(true);
    }, []);

    const setTheme = (newTheme: ThemeName) => {
        setThemeState(newTheme);
        localStorage.setItem(STORAGE_KEY, newTheme);

        // Dispatch custom event for non-React components (e.g. some chart internals if needed)
        window.dispatchEvent(new CustomEvent('theme-changed', { detail: newTheme }));
    };

    const value = {
        theme,
        themeParams: THEMES[theme],
        setTheme,
        availableThemes: Object.keys(THEMES) as ThemeName[]
    };

    // Always provide context to prevent 'useTheme' errors in children
    // Hydration mismatch is less critical than crash
    return (
        <ThemeContext.Provider value={value}>
            {mounted ? children : <div style={{ visibility: 'hidden' }}>{children}</div>}
        </ThemeContext.Provider>
    );
}

export function useTheme() {
    const context = useContext(ThemeContext);
    if (context === undefined) {
        throw new Error('useTheme must be used within a ThemeProvider');
    }
    return context;
}
