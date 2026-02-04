'use client';

import { useState } from 'react';
import { X, Copy, Download, Check, FileJson, FileCode } from 'lucide-react';
import { CandleScienceStats } from '@/lib/candle-science/types';

interface ExportModalProps {
    stats: CandleScienceStats;
    onClose: () => void;
}

export function ExportModal({ stats, onClose }: ExportModalProps) {
    const [copied, setCopied] = useState<'json' | 'pine' | null>(null);

    // Pine Script Generation Logic
    const generatePineScript = () => {
        const { ticker, timeframe, sample_count, high_wicks, low_wicks, body, gaps } = stats;
        return `// === CANDLE SCIENCE DATA - ${ticker} ${timeframe} ===
// Generated Samples: ${sample_count.toLocaleString()}

// Probabilities (%)
var float PROB_C3H_C2H = ${high_wicks.c3_vs_c2.high_vs_high.above}
var float PROB_C3L_C2L = ${low_wicks.c3_vs_c2.low_vs_low.below}
var float PROB_C3C_C2H = ${body.c3_vs_c2.close_vs_high.above}
var float PROB_C3C_C2L = ${body.c3_vs_c2.close_vs_low.below}

// Median Distances (%)
var float MED_C3H_C2H = ${high_wicks.c3_vs_c2.high_vs_high.median_dist}
var float MED_C3L_C2L = ${low_wicks.c3_vs_c2.low_vs_low.median_dist}
`;
    };

    const pineScript = generatePineScript();
    const jsonData = JSON.stringify(stats, null, 2);

    const copyToClipboard = async (text: string, type: 'json' | 'pine') => {
        await navigator.clipboard.writeText(text);
        setCopied(type);
        setTimeout(() => setCopied(null), 2000);
    };

    const downloadFile = (content: string, filename: string) => {
        const blob = new Blob([content], { type: 'text/plain' });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = filename;
        a.click();
        URL.revokeObjectURL(url);
    };

    return (
        <div className="fixed inset-0 bg-black/80 backdrop-blur-sm flex items-center justify-center z-[100] p-4">
            <div className="bg-[#1a1a1a] rounded-2xl border border-[#3d3d3d] w-full max-w-2xl overflow-hidden shadow-2xl">
                <div className="flex items-center justify-between p-6 border-b border-[#3d3d3d]">
                    <h2 className="text-xl font-bold text-white flex items-center gap-3">
                        <Share2 className="w-5 h-5 text-emerald-500" />
                        Export Analytics
                    </h2>
                    <button onClick={onClose} title="Close" className="p-2 hover:bg-[#2d2d2d] rounded-xl transition-all">
                        <X className="w-5 h-5 text-[#606060]" />
                    </button>
                </div>

                <div className="p-6 space-y-6 max-h-[70vh] overflow-y-auto scrollbar-thin scrollbar-thumb-[#3d3d3d]">
                    {/* Pine Script Export */}
                    <div className="space-y-4">
                        <div className="flex items-center justify-between">
                            <div className="flex items-center gap-2">
                                <FileCode className="w-4 h-4 text-emerald-500" />
                                <span className="text-sm font-bold text-[#a0a0a0] uppercase tracking-wider">TradingView Snippet</span>
                            </div>
                            <div className="flex gap-2">
                                <button
                                    onClick={() => copyToClipboard(pineScript, 'pine')}
                                    className="p-1 px-3 bg-[#2d2d2d] text-xs font-bold text-white rounded-md hover:bg-[#3d3d3d] flex items-center gap-2 transition-all uppercase tracking-widest border border-[#3d3d3d]"
                                >
                                    {copied === 'pine' ? <Check className="w-3.5 h-3.5" /> : <Copy className="w-3.5 h-3.5" />}
                                    {copied === 'pine' ? 'Copied' : 'Copy'}
                                </button>
                            </div>
                        </div>
                        <pre className="bg-[#0a0a0a] p-4 rounded-xl text-[11px] font-mono text-emerald-500/80 overflow-x-auto border border-[#2d2d2d]">
                            {pineScript}
                        </pre>
                    </div>

                    {/* JSON Export */}
                    <div className="space-y-4">
                        <div className="flex items-center justify-between">
                            <div className="flex items-center gap-2">
                                <FileJson className="w-4 h-4 text-blue-500" />
                                <span className="text-sm font-bold text-[#a0a0a0] uppercase tracking-wider">Raw JSON Data</span>
                            </div>
                            <button
                                onClick={() => downloadFile(jsonData, `candle_science_${stats.ticker.toLowerCase()}.json`)}
                                className="p-1 px-3 bg-[#2d2d2d] text-xs font-bold text-white rounded-md hover:bg-[#3d3d3d] flex items-center gap-2 transition-all uppercase tracking-widest border border-[#3d3d3d]"
                            >
                                <Download className="w-3.5 h-3.5" />
                                Download
                            </button>
                        </div>
                        <pre className="bg-[#0a0a0a] p-4 rounded-xl text-[11px] font-mono text-blue-500/60 overflow-y-auto max-h-48 border border-[#2d2d2d] scrollbar-thin scrollbar-thumb-[#3d3d3d]">
                            {jsonData}
                        </pre>
                    </div>
                </div>

                <div className="p-6 bg-[#242424] border-t border-[#3d3d3d] flex justify-end">
                    <button
                        onClick={onClose}
                        className="px-6 py-2 bg-[#2d2d2d] text-white text-sm font-bold rounded-xl hover:bg-[#3d3d3d] transition-all uppercase tracking-widest"
                    >
                        Close
                    </button>
                </div>
            </div>
        </div>
    );
}

import { Share2 } from 'lucide-react';
