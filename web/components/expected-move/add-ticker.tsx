"use client";

import { useState } from "react";
import { Plus } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { toast } from "sonner";
import { getExpectedMoveData } from "@/actions/get-expected-move";

interface AddTickerProps {
    onAdd: (ticker: string) => void;
}

export function AddTicker({ onAdd }: AddTickerProps) {
    const [ticker, setTicker] = useState("");
    const [loading, setLoading] = useState(false);

    const handleSubmit = async (e: React.FormEvent) => {
        e.preventDefault();
        const t = ticker.trim().toUpperCase();
        if (!t) return;

        setLoading(true);
        try {
            // We just trigger the fetch. The parent component will re-fetch data based on DB or we pass data back?
            // Actually, best pattern is: Call Server Action to fetch & store, then tell Parent to refresh DB.
            // But for now, let's just use the existing action and ignore the return, relying on parent refresh?
            // OR, cleaner: Parent handles the "Add" logic via the same action.
            // Let's just pass the ticker up to parent.
            onAdd(t);
            setTicker("");
        } catch (err) {
            toast.error("Failed to add ticker");
        } finally {
            setLoading(false);
        }
    };

    return (
        <form onSubmit={handleSubmit} className="flex gap-2 items-center">
            <Input
                value={ticker}
                onChange={(e) => setTicker(e.target.value)}
                placeholder="Add Ticker (e.g. SPX)"
                className="w-32 h-8"
            />
            <Button type="submit" size="sm" disabled={loading} className="h-8">
                {loading ? "..." : <Plus className="w-4 h-4" />}
            </Button>
        </form>
    );
}
