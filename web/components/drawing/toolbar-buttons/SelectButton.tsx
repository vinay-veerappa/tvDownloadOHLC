"use client";

import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import { Check } from "lucide-react";
import { cn } from "@/lib/utils";

interface SelectOption {
    value: any;
    label: string;
}

interface SelectButtonProps {
    value: any;
    options: SelectOption[];
    onChange: (value: any) => void;
    tooltip?: string;
    icon?: React.ReactNode;
    displayValue?: string;  // Override display text
    disabled?: boolean;
}

export function SelectButton({
    value,
    options,
    onChange,
    tooltip = "Select",
    icon,
    displayValue,
    disabled = false
}: SelectButtonProps) {
    const [open, setOpen] = useState(false);

    const currentOption = options.find(o => o.value === value);
    // Anti-pattern fix: Only fall back to tooltip if there is NO icon and NO value.
    // If there is an icon, we prefer showing just the icon (or icon + value) rather than "Width" text.
    const uniqueDisplay = displayValue ?? currentOption?.label ?? (value !== undefined && value !== null ? String(value) : null);

    // If we have an icon, we only show text if we have a valid value.
    // If no icon, we fallback to tooltip to avoid empty button.
    const showText = uniqueDisplay || (!icon ? tooltip : null);

    return (
        <Popover open={open} onOpenChange={setOpen}>
            <PopoverTrigger asChild>
                <Button
                    variant="ghost"
                    size="sm"
                    className="h-8 px-2 gap-1 min-w-[32px]"
                    title={tooltip}
                    disabled={disabled}
                >
                    {icon}
                    {showText && <span className="text-xs font-medium">{showText}</span>}
                </Button>
            </PopoverTrigger>
            <PopoverContent className="w-auto min-w-[80px] p-1" align="start">
                <div className="flex flex-col">
                    {options.map((option) => (
                        <button
                            key={String(option.value)}
                            className={cn(
                                "flex items-center gap-2 px-2 py-1.5 text-sm rounded hover:bg-muted transition-colors text-left",
                                value === option.value && "bg-muted"
                            )}
                            onClick={() => {
                                onChange(option.value);
                                setOpen(false);
                            }}
                        >
                            <span className="w-4">
                                {value === option.value && <Check className="h-4 w-4" />}
                            </span>
                            <span>{option.label}</span>
                        </button>
                    ))}
                </div>
            </PopoverContent>
        </Popover>
    );
}
