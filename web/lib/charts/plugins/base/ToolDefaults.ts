export class ToolDefaults {
    private static STORAGE_KEY = 'tradingview_tool_defaults';
    private static _defaults: Record<string, any> = {};

    static load() {
        if (typeof window === 'undefined') return;
        try {
            const stored = localStorage.getItem(this.STORAGE_KEY);
            if (stored) {
                this._defaults = JSON.parse(stored);
            }
        } catch (e) {
            console.warn('Failed to load tool defaults', e);
        }
    }

    static save() {
        if (typeof window === 'undefined') return;
        try {
            localStorage.setItem(this.STORAGE_KEY, JSON.stringify(this._defaults));
        } catch (e) {
            console.warn('Failed to save tool defaults', e);
        }
    }

    static get(toolType: string): any {
        if (Object.keys(this._defaults).length === 0) this.load();
        return this._defaults[toolType] || {};
    }

    static set(toolType: string, options: any) {
        this._defaults[toolType] = { ...this._defaults[toolType], ...options };
        this.save();
    }
}
