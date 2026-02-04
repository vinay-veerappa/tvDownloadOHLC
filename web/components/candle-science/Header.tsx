import { Share2, RefreshCw } from 'lucide-react';

interface HeaderProps {
    ticker: string;
    timeframe: string;
    sampleCount: number;
    onExport: () => void;
    onReset: () => void;
}

export function Header({ ticker, timeframe, sampleCount, onExport, onReset }: HeaderProps) {
    return (
        <header className="h-16 bg-[#242424] border-b border-[#3d3d3d] flex items-center justify-between px-6 shrink-0 z-10">
            <div className="flex items-center gap-6">
                <h1 className="text-lg font-bold text-white flex items-center gap-2">
                    <span className="w-2 h-2 bg-emerald-500 rounded-full animate-pulse" />
                    Candle Science
                </h1>

                <div className="h-6 w-[1px] bg-[#3d3d3d]" />

                <div className="flex items-center gap-4">
                    <div className="flex items-center gap-2 bg-[#1a1a1a] px-3 py-1 rounded-md border border-[#3d3d3d]">
                        <span className="text-[10px] font-bold text-[#606060] uppercase tracking-wider">Asset</span>
                        <span className="text-sm font-bold text-white">{ticker}</span>
                    </div>
                    <div className="flex items-center gap-2 bg-[#1a1a1a] px-3 py-1 rounded-md border border-[#3d3d3d]">
                        <span className="text-[10px] font-bold text-[#606060] uppercase tracking-wider">Period</span>
                        <span className="text-sm font-bold text-white">{timeframe}</span>
                    </div>
                </div>
            </div>

            <div className="flex items-center gap-4">
                <div className="text-right">
                    <div className="text-[10px] font-bold text-[#606060] uppercase tracking-widest leading-none mb-1">Total Samples</div>
                    <div className="text-lg font-mono font-bold text-emerald-400 leading-none">{sampleCount.toLocaleString()}</div>
                </div>

                <div className="h-6 w-[1px] bg-[#3d3d3d] mx-2" />

                <div className="flex items-center gap-2">
                    <button
                        onClick={onReset}
                        className="p-2 text-[#a0a0a0] hover:text-white hover:bg-[#2d2d2d] rounded-lg transition-all"
                        title="Reset Filters"
                    >
                        <RefreshCw className="w-5 h-5" />
                    </button>
                    <button
                        onClick={onExport}
                        className="flex items-center gap-2 bg-emerald-600 hover:bg-emerald-500 text-white px-4 py-2 rounded-lg text-sm font-medium transition-all shadow-lg shadow-emerald-900/20"
                    >
                        <Share2 className="w-4 h-4" />
                        <span>Export</span>
                    </button>
                </div>
            </div>
        </header>
    );
}
