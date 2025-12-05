"use client"

import * as React from "react"
import { Check, ChevronsUpDown, Search } from "lucide-react"
import { cn } from "@/lib/utils"
import { Button } from "@/components/ui/button"
import {
    Dialog,
    DialogContent,
    DialogHeader,
    DialogTitle,
    DialogDescription,
    DialogTrigger,
} from "@/components/ui/dialog"
import {
    Command,
    CommandEmpty,
    CommandGroup,
    CommandInput,
    CommandItem,
    CommandList,
} from "@/components/ui/command"

const indicators = [
    {
        value: "sma",
        label: "Moving Average (SMA)",
    },
    {
        value: "ema",
        label: "Exponential Moving Average (EMA)",
    },
    {
        value: "watermark",
        label: "Watermark (Anchored Text)",
    },
]

interface IndicatorsDialogProps {
    children: React.ReactNode
    onSelect: (value: string) => void
}

export function IndicatorsDialog({ children, onSelect }: IndicatorsDialogProps) {
    const [open, setOpen] = React.useState(false)

    return (
        <Dialog open={open} onOpenChange={setOpen}>
            <DialogTrigger asChild>
                {children}
            </DialogTrigger>
            <DialogContent className="sm:max-w-[425px] p-0 gap-0">
                <DialogHeader className="px-4 py-2 border-b">
                    <DialogTitle>Indicators</DialogTitle>
                    <DialogDescription className="sr-only">
                        Select an indicator to add to the chart
                    </DialogDescription>
                </DialogHeader>
                <Command className="rounded-lg border-none shadow-none">
                    <CommandInput placeholder="Search indicators..." />
                    <CommandList>
                        <CommandEmpty>No results found.</CommandEmpty>
                        <CommandGroup heading="Trend">
                            {indicators.map((indicator) => (
                                <CommandItem
                                    key={indicator.value}
                                    value={indicator.value}
                                    onSelect={(currentValue) => {
                                        onSelect(currentValue)
                                        setOpen(false)
                                    }}
                                >
                                    {indicator.label}
                                </CommandItem>
                            ))}
                        </CommandGroup>
                    </CommandList>
                </Command>
            </DialogContent>
        </Dialog>
    )
}
