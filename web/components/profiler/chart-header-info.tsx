"use client"

interface HeaderItem {
    label: string;
    value: string | number;
    color?: string;
    subValue?: string; // e.g. (+0.5%)
    subColor?: string;
}

interface ChartHeaderInfoProps {
    title: string;
    subtitle?: string; // Usually the timestamp
    items: HeaderItem[];
}

export function ChartHeaderInfo({ title, subtitle, items }: ChartHeaderInfoProps) {
    return (
        <div className="flex items-center justify-between text-xs border-b pb-1 mb-2 h-7 overflow-hidden">
            <div className="flex items-center gap-4">
                <div className="font-semibold text-muted-foreground whitespace-nowrap">
                    {title}
                </div>
                {subtitle && (
                    <div className="text-muted-foreground font-mono">
                        {subtitle}
                    </div>
                )}
            </div>

            <div className="flex items-center gap-4 flex-1 justify-end">
                {items.map((item, idx) => (
                    <div key={idx} className="flex items-center gap-1.5 whitespace-nowrap">
                        <span className="text-muted-foreground hover:text-foreground transition-colors">
                            {item.label}:
                        </span>
                        <span
                            className="font-mono font-medium"
                            style={{ color: item.color }}
                        >
                            {item.value}
                        </span>
                        {item.subValue && (
                            <span
                                className="font-mono text-[10px]"
                                style={{ color: item.subColor || item.color }}
                            >
                                {item.subValue}
                            </span>
                        )}
                    </div>
                ))}
            </div>
        </div>
    );
}
