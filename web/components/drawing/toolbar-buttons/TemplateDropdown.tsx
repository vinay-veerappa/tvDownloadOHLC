"use client";

import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import { ChevronDown, Plus, Check } from "lucide-react";
import { templateStorage } from "@/lib/template-storage";
import { cn } from "@/lib/utils";
import { Input } from "@/components/ui/input";
import {
    Dialog,
    DialogContent,
    DialogHeader,
    DialogTitle,
    DialogFooter,
} from "@/components/ui/dialog";

interface TemplateDropdownProps {
    toolType: string;
    currentOptions: Record<string, any>;
    onApplyTemplate: (options: Record<string, any>) => void;
    onSaveTemplate?: () => void;
}

export function TemplateDropdown({
    toolType,
    currentOptions,
    onApplyTemplate,
}: TemplateDropdownProps) {
    const [open, setOpen] = useState(false);
    const [showSaveDialog, setShowSaveDialog] = useState(false);
    const [newTemplateName, setNewTemplateName] = useState("");

    const templates = templateStorage.getByToolType(toolType);
    const defaultTemplate = templateStorage.getDefault(toolType);

    const handleSaveTemplate = () => {
        if (newTemplateName.trim()) {
            templateStorage.save({
                name: newTemplateName.trim(),
                toolType,
                options: currentOptions,
            });
            setNewTemplateName("");
            setShowSaveDialog(false);
        }
    };

    const handleApplyDefault = () => {
        if (defaultTemplate) {
            onApplyTemplate(defaultTemplate.options);
        }
        setOpen(false);
    };

    return (
        <>
            <Popover open={open} onOpenChange={setOpen}>
                <PopoverTrigger asChild>
                    <Button variant="ghost" size="sm" className="h-8 px-2 gap-1">
                        <span className="text-xs">Template</span>
                        <ChevronDown className="h-3 w-3" />
                    </Button>
                </PopoverTrigger>
                <PopoverContent className="w-56 p-1" align="start">
                    <div className="flex flex-col">
                        {/* Save Template */}
                        <button
                            className="flex items-center gap-2 px-2 py-1.5 text-sm rounded hover:bg-muted text-left"
                            onClick={() => {
                                setOpen(false);
                                setShowSaveDialog(true);
                            }}
                        >
                            <Plus className="h-4 w-4" />
                            Save Drawing Template As...
                        </button>

                        {/* Apply Default */}
                        {defaultTemplate && (
                            <button
                                className="flex items-center gap-2 px-2 py-1.5 text-sm rounded hover:bg-muted text-left"
                                onClick={handleApplyDefault}
                            >
                                <Check className="h-4 w-4 opacity-0" />
                                Apply Default Drawing Template
                            </button>
                        )}

                        {templates.length > 0 && (
                            <>
                                <div className="my-1 border-t border-border" />
                                {templates.map((template) => (
                                    <button
                                        key={template.id}
                                        className={cn(
                                            "flex items-center gap-2 px-2 py-1.5 text-sm rounded hover:bg-muted text-left",
                                            template.isDefault && "font-medium"
                                        )}
                                        onClick={() => {
                                            onApplyTemplate(template.options);
                                            setOpen(false);
                                        }}
                                    >
                                        <span className="w-4">
                                            {template.isDefault && <Check className="h-4 w-4" />}
                                        </span>
                                        {template.isDefault ? `[${template.name}]` : template.name}
                                    </button>
                                ))}
                            </>
                        )}
                    </div>
                </PopoverContent>
            </Popover>

            {/* Save Template Dialog */}
            <Dialog open={showSaveDialog} onOpenChange={setShowSaveDialog}>
                <DialogContent className="max-w-sm">
                    <DialogHeader>
                        <DialogTitle>Save Drawing Template</DialogTitle>
                    </DialogHeader>
                    <div className="py-4">
                        <Input
                            placeholder="Template name"
                            value={newTemplateName}
                            onChange={(e) => setNewTemplateName(e.target.value)}
                            onKeyDown={(e) => {
                                if (e.key === "Enter") handleSaveTemplate();
                            }}
                        />
                    </div>
                    <DialogFooter>
                        <Button variant="outline" onClick={() => setShowSaveDialog(false)}>
                            Cancel
                        </Button>
                        <Button onClick={handleSaveTemplate} disabled={!newTemplateName.trim()}>
                            Save
                        </Button>
                    </DialogFooter>
                </DialogContent>
            </Dialog>
        </>
    );
}
