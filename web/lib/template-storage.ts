/**
 * Template Storage
 * 
 * Provides persistent storage for drawing templates:
 * - Save tool presets (colors, widths, styles)
 * - Load templates by tool type
 * - Set default template per tool
 */

export interface DrawingTemplate {
    id: string;
    name: string;
    toolType: string;
    options: Record<string, any>;
    isDefault?: boolean;
    createdAt: number;
}

const STORAGE_KEY = 'drawing-templates';
const DEFAULTS_KEY = 'drawing-template-defaults';

class TemplateStorage {
    private templates: Map<string, DrawingTemplate> = new Map();
    private defaults: Map<string, string> = new Map(); // toolType -> templateId

    constructor() {
        this.load();
    }

    // ===== CRUD Operations =====

    public save(template: Omit<DrawingTemplate, 'id' | 'createdAt'>): DrawingTemplate {
        const newTemplate: DrawingTemplate = {
            ...template,
            id: this.generateId(),
            createdAt: Date.now(),
        };

        this.templates.set(newTemplate.id, newTemplate);
        this.persist();
        return newTemplate;
    }

    public get(id: string): DrawingTemplate | undefined {
        return this.templates.get(id);
    }

    public getByToolType(toolType: string): DrawingTemplate[] {
        return Array.from(this.templates.values())
            .filter(t => t.toolType === toolType)
            .sort((a, b) => b.createdAt - a.createdAt);
    }

    public getAll(): DrawingTemplate[] {
        return Array.from(this.templates.values())
            .sort((a, b) => b.createdAt - a.createdAt);
    }

    public update(id: string, updates: Partial<DrawingTemplate>): boolean {
        const template = this.templates.get(id);
        if (!template) return false;

        this.templates.set(id, { ...template, ...updates, id });
        this.persist();
        return true;
    }

    public delete(id: string): boolean {
        const deleted = this.templates.delete(id);
        if (deleted) {
            // Also remove from defaults if it was set
            for (const [toolType, templateId] of this.defaults.entries()) {
                if (templateId === id) {
                    this.defaults.delete(toolType);
                }
            }
            this.persist();
        }
        return deleted;
    }

    // ===== Default Templates =====

    public setDefault(toolType: string, templateId: string): void {
        this.defaults.set(toolType, templateId);
        this.persistDefaults();
    }

    public getDefault(toolType: string): DrawingTemplate | undefined {
        const defaultId = this.defaults.get(toolType);
        if (!defaultId) return undefined;
        return this.templates.get(defaultId);
    }

    public clearDefault(toolType: string): void {
        this.defaults.delete(toolType);
        this.persistDefaults();
    }

    // ===== Persistence =====

    private load(): void {
        try {
            // Load templates
            const stored = localStorage.getItem(STORAGE_KEY);
            if (stored) {
                const templates: DrawingTemplate[] = JSON.parse(stored);
                templates.forEach(t => this.templates.set(t.id, t));
            }

            // Load defaults
            const defaultsStored = localStorage.getItem(DEFAULTS_KEY);
            if (defaultsStored) {
                const defaults: Record<string, string> = JSON.parse(defaultsStored);
                Object.entries(defaults).forEach(([k, v]) => this.defaults.set(k, v));
            }
        } catch (error) {
            console.error('Failed to load templates:', error);
        }
    }

    private persist(): void {
        try {
            const templates = Array.from(this.templates.values());
            localStorage.setItem(STORAGE_KEY, JSON.stringify(templates));
        } catch (error) {
            console.error('Failed to save templates:', error);
        }
    }

    private persistDefaults(): void {
        try {
            const defaults = Object.fromEntries(this.defaults.entries());
            localStorage.setItem(DEFAULTS_KEY, JSON.stringify(defaults));
        } catch (error) {
            console.error('Failed to save template defaults:', error);
        }
    }

    private generateId(): string {
        return `template_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
    }
}

// ===== Singleton Instance =====

export const templateStorage = new TemplateStorage();
