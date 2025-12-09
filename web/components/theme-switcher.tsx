'use client';

import * as React from "react";
import { Palette, Check } from "lucide-react";

import { Button } from "@/components/ui/button";
import {
    Popover,
    PopoverContent,
    PopoverTrigger,
} from "@/components/ui/popover";
import {
    Command,
    CommandEmpty,
    CommandGroup,
    CommandInput,
    CommandItem,
    CommandList,
} from "@/components/ui/command";
import { useTheme } from "@/context/theme-context";
import { cn } from "@/lib/utils";

export function ThemeSwitcher() {
    const { setTheme, theme, availableThemes } = useTheme();
    const [open, setOpen] = React.useState(false);

    return (
        <Popover open={open} onOpenChange={setOpen}>
            <PopoverTrigger asChild>
                <Button variant="ghost" size="icon" title="Switch Chart Theme">
                    <Palette className="h-[1.2rem] w-[1.2rem] rotate-0 scale-100 transition-all" />
                    <span className="sr-only">Switch Theme</span>
                </Button>
            </PopoverTrigger>
            <PopoverContent className="w-[200px] p-0" align="end">
                <Command>
                    <CommandInput placeholder="Select theme..." />
                    <CommandList>
                        <CommandEmpty>No theme found.</CommandEmpty>
                        <CommandGroup>
                            {availableThemes.map((t) => (
                                <CommandItem
                                    key={t}
                                    value={t}
                                    onSelect={(currentValue) => {
                                        setTheme(currentValue as any)
                                        setOpen(false)
                                    }}
                                    className="capitalize"
                                >
                                    <Check
                                        className={cn(
                                            "mr-2 h-4 w-4",
                                            theme === t ? "opacity-100" : "opacity-0"
                                        )}
                                    />
                                    {t.replace(/-/g, ' ')}
                                </CommandItem>
                            ))}
                        </CommandGroup>
                    </CommandList>
                </Command>
            </PopoverContent>
        </Popover>
    );
}
