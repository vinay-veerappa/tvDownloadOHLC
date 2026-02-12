"use client"

import { useState } from "react"
import { Input } from "@/components/ui/input"
import { Button } from "@/components/ui/button"
import { Label } from "@/components/ui/label"
import { Eye, EyeOff, Link as LinkIcon, Image as ImageIcon } from "lucide-react"

interface ChartUrlInputProps {
    value: string
    onChange: (value: string) => void
}

export function ChartUrlInput({ value, onChange }: ChartUrlInputProps) {
    const [previewOpen, setPreviewOpen] = useState(false)

    // Simple check if string is a URL
    const isValidUrl = (str: string) => {
        try {
            new URL(str)
            return true
        } catch {
            return false
        }
    }

    return (
        <div className="space-y-2">
            <div className="flex items-center justify-between">
                <Label>Chart URL / Screenshot</Label>
                {value && isValidUrl(value) && (
                    <Button 
                        type="button" 
                        variant="ghost" 
                        size="sm" 
                        className="h-6 px-2 text-xs"
                        onClick={() => setPreviewOpen(!previewOpen)}
                    >
                        {previewOpen ? <EyeOff className="w-3 h-3 mr-1" /> : <Eye className="w-3 h-3 mr-1" />}
                        {previewOpen ? "Hide" : "Preview"}
                    </Button>
                )}
            </div>
            
            <div className="flex gap-2">
                <div className="relative flex-1">
                    <LinkIcon className="absolute left-2.5 top-2.5 h-4 w-4 text-muted-foreground" />
                    <Input
                        value={value}
                        onChange={(e) => onChange(e.target.value)}
                        placeholder="https://www.tradingview.com/x/..."
                        className="pl-9"
                    />
                </div>
            </div>

            {previewOpen && value && (
                <div className="mt-2 relative aspect-video w-full overflow-hidden rounded-lg border bg-muted/50 flex items-center justify-center">
                    {/* Only try to render as image if it looks like one, otherwise iframe or link */}
                    <img 
                        src={value} 
                        alt="Chart Preview" 
                        className="object-contain w-full h-full"
                        onError={(e) => {
                            // Fallback if not an image
                            e.currentTarget.style.display = 'none'
                        }}
                    />
                    <div className="absolute inset-0 flex items-center justify-center -z-10 text-muted-foreground text-sm">
                        <ImageIcon className="w-4 h-4 mr-2" />
                        Preview unavailable (Link might not be a direct image)
                    </div>
                </div>
            )}
        </div>
    )
}
