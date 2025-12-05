/**
 * Template Manager for Drawing Tools
 * Handles saving, loading, and managing drawing templates in localStorage
 */

export interface DrawingTemplate {
    name: string;
    drawingType: string;
    options: Record<string, any>;
    createdAt: number;
}

const STORAGE_KEY = 'drawing_templates';
const DEFAULT_KEY = 'drawing_defaults';

export class TemplateManager {
    /**
     * Get all templates for a specific drawing type
     */
    static getTemplates(drawingType: string): DrawingTemplate[] {
        try {
            const allTemplates = this.getAllTemplates();
            return allTemplates.filter(t => t.drawingType === drawingType);
        } catch (error) {
            console.error('Failed to get templates:', error);
            return [];
        }
    }

    /**
     * Get all templates (all drawing types)
     */
    static getAllTemplates(): DrawingTemplate[] {
        try {
            const data = localStorage.getItem(STORAGE_KEY);
            return data ? JSON.parse(data) : [];
        } catch (error) {
            console.error('Failed to parse templates:', error);
            return [];
        }
    }

    /**
     * Save a new template
     */
    static saveTemplate(name: string, drawingType: string, options: Record<string, any>): boolean {
        try {
            const templates = this.getAllTemplates();

            // Check if template with same name exists for this drawing type
            const existingIndex = templates.findIndex(
                t => t.drawingType === drawingType && t.name === name
            );

            const template: DrawingTemplate = {
                name,
                drawingType,
                options,
                createdAt: Date.now()
            };

            if (existingIndex >= 0) {
                // Update existing
                templates[existingIndex] = template;
            } else {
                // Add new
                templates.push(template);
            }

            localStorage.setItem(STORAGE_KEY, JSON.stringify(templates));
            return true;
        } catch (error) {
            console.error('Failed to save template:', error);
            return false;
        }
    }

    /**
     * Delete a template
     */
    static deleteTemplate(drawingType: string, name: string): boolean {
        try {
            const templates = this.getAllTemplates();
            const filtered = templates.filter(
                t => !(t.drawingType === drawingType && t.name === name)
            );
            localStorage.setItem(STORAGE_KEY, JSON.stringify(filtered));
            return true;
        } catch (error) {
            console.error('Failed to delete template:', error);
            return false;
        }
    }

    /**
     * Get template by name
     */
    static getTemplate(drawingType: string, name: string): DrawingTemplate | null {
        const templates = this.getTemplates(drawingType);
        return templates.find(t => t.name === name) || null;
    }

    /**
     * Save default options for a drawing type
     */
    static saveDefault(drawingType: string, options: Record<string, any>): boolean {
        try {
            const defaults = this.getAllDefaults();
            defaults[drawingType] = options;
            localStorage.setItem(DEFAULT_KEY, JSON.stringify(defaults));
            return true;
        } catch (error) {
            console.error('Failed to save default:', error);
            return false;
        }
    }

    /**
     * Get default options for a drawing type
     */
    static getDefault(drawingType: string): Record<string, any> | null {
        try {
            const defaults = this.getAllDefaults();
            return defaults[drawingType] || null;
        } catch (error) {
            console.error('Failed to get default:', error);
            return null;
        }
    }

    /**
     * Get all defaults
     */
    static getAllDefaults(): Record<string, Record<string, any>> {
        try {
            const data = localStorage.getItem(DEFAULT_KEY);
            return data ? JSON.parse(data) : {};
        } catch (error) {
            console.error('Failed to parse defaults:', error);
            return {};
        }
    }

    /**
     * Clear all templates (for testing/reset)
     */
    static clearAll(): void {
        localStorage.removeItem(STORAGE_KEY);
        localStorage.removeItem(DEFAULT_KEY);
    }
}
