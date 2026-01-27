'use client';

import { useState } from 'react';
import { ChevronDown, Filter, Calendar, BarChart3, Clock } from 'lucide-react';
import { ReferenceFilters } from '@/lib/candle-science/types';

const TICKERS = ['NQ1', 'ES1', 'RTY1', 'YM1', 'GC1', 'CL1', 'AAPL', 'NVDA', 'TSLA', 'SPY', 'QQQ'];
const TIMEFRAMES = ['1m', '5m', '15m', '1h', '4h', '1d', '1W'];
const YEARS = ['2020', '2021', '2022', '2023', '2024', '2025', '2026'];
const MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
const DAYS = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'];
const HOURS = Array.from({ length: 24 }, (_, i) => `${i.toString().padStart(2, '0')}:00`);

interface SidebarProps {
    ticker: string;
    setTicker: (v: string) => void;
    timeframe: string;
    setTimeframe: (v: string) => void;
    years: string[];
    setYears: (v: string[]) => void;
    months: number[];
    setMonths: (v: number[]) => void;
    daysOfWeek: number[];
    setDaysOfWeek: (v: number[]) => void;
    c1OpenHours: number[];
    setC1OpenHours: (v: number[]) => void;
    referenceFilters: ReferenceFilters;
    setReferenceFilters: (v: ReferenceFilters) => void;
    resetFilters: () => void;
    isCollapsed: boolean;
    onToggle: () => void;
}

export function Sidebar({
    ticker, setTicker,
    timeframe, setTimeframe,
    years, setYears,
    months, setMonths,
    daysOfWeek, setDaysOfWeek,
    c1OpenHours, setC1OpenHours,
    referenceFilters, setReferenceFilters,
    resetFilters,
    isCollapsed,
    onToggle
}: SidebarProps) {

    const updateRefFilter = (key: keyof ReferenceFilters, value: any) => {
        setReferenceFilters({ ...referenceFilters, [key]: value });
    };

    return (
        <aside className={`${isCollapsed ? 'w-20' : 'w-80'} shrink-0 sticky top-0 h-screen bg-[#1e1e1e]/80 backdrop-blur-xl border-r border-white/5 flex flex-col transition-all duration-300 ease-in-out relative z-30`}>
            {/* Header / Toggle */}
            <div className="p-6 border-b border-white/5 h-20 flex items-center justify-between shrink-0">
                {/* Title (Hidden when collapsed) */}
                <div className={`flex items-center gap-4 ${isCollapsed ? 'hidden' : 'flex'}`}>
                    <div className="w-8 h-8 rounded-lg bg-emerald-500/10 flex items-center justify-center border border-emerald-500/20">
                        <Filter className="w-4 h-4 text-emerald-500" />
                    </div>
                    <span className="text-sm font-black text-white uppercase tracking-[0.2em] whitespace-nowrap">Sequence Logic</span>
                </div>

                {/* Collapse Button (Always visible) */}
                <button
                    onClick={onToggle}
                    className={`p-2 rounded-lg hover:bg-white/5 text-[#606060] hover:text-white transition-colors ${isCollapsed ? 'mx-auto' : ''}`}
                    title={isCollapsed ? "Expand Filters" : "Collapse Filters"}
                >
                    <ChevronDown className={`w-5 h-5 transition-transform duration-300 ${isCollapsed ? '-rotate-90' : 'rotate-90'}`} />
                </button>
            </div>

            {/* Scrollable Content */}
            <div className={`flex-1 overflow-y-auto overflow-x-hidden p-6 space-y-10 scrollbar-thin scrollbar-thumb-white/5 ${isCollapsed ? 'hidden' : 'block'}`}>
                {/* Data Selection */}
                <div className="space-y-6">
                    <SectionHeader icon={<BarChart3 className="w-4 h-4" />} title="Dataset" />

                    <div className="space-y-3">
                        <FilterDropDown
                            label="Instrument"
                            value={ticker}
                            options={TICKERS}
                            onChange={setTicker}
                        />
                        <FilterDropDown
                            label="Timeframe"
                            value={timeframe}
                            options={TIMEFRAMES}
                            onChange={setTimeframe}
                        />
                    </div>
                </div>

                {/* Reference Filters */}
                <div className="space-y-4">
                    <SectionHeader icon={<Clock className="w-3.5 h-3.5" />} title="Context" />

                    <div className="space-y-3">
                        <FilterDropDown
                            label="C1 Direction"
                            value={referenceFilters.c1Direction}
                            options={['all', 'bull', 'bear']}
                            onChange={(v) => updateRefFilter('c1Direction', v)}
                        />
                        <FilterDropDown
                            label="C2 Direction"
                            value={referenceFilters.c2Direction}
                            options={['all', 'bull', 'bear']}
                            onChange={(v) => updateRefFilter('c2Direction', v)}
                        />
                        <FilterDropDown
                            label="C2 vs C1 High"
                            value={referenceFilters.c2HighVsC1High}
                            options={['all', 'above', 'below']}
                            onChange={(v) => updateRefFilter('c2HighVsC1High', v)}
                        />
                        <FilterDropDown
                            label="C2 vs C1 Low"
                            value={referenceFilters.c2LowVsC1Low}
                            options={['all', 'above', 'below']}
                            onChange={(v) => updateRefFilter('c2LowVsC1Low', v)}
                        />
                        <FilterDropDown
                            label="C2 Cls vs C1 High"
                            value={referenceFilters.c2CloseVsC1High}
                            options={['all', 'above', 'below']}
                            onChange={(v) => updateRefFilter('c2CloseVsC1High', v)}
                        />
                        <FilterDropDown
                            label="C3 Opn vs C2 Cls"
                            value={referenceFilters.c3OpenVsC2Close}
                            options={['all', 'above', 'below']}
                            onChange={(v) => updateRefFilter('c3OpenVsC2Close', v)}
                        />
                        <FilterDropDown
                            label="C3 Opn vs C2 Opn"
                            value={referenceFilters.c3OpenVsC2Open}
                            options={['all', 'above', 'below']}
                            onChange={(v) => updateRefFilter('c3OpenVsC2Open', v)}
                        />
                    </div>
                </div>

                {/* Time Filters */}
                <div className="space-y-4">
                    <SectionHeader icon={<Calendar className="w-3.5 h-3.5" />} title="Temporal" />

                    <div className="space-y-3">
                        <MultiSelect
                            label="Years"
                            options={YEARS}
                            selected={years}
                            onChange={setYears}
                            placeholder="All Years"
                        />
                        <MultiSelect
                            label="Months"
                            options={MONTHS}
                            selected={months.map(m => MONTHS[m - 1])}
                            onChange={(v: string[]) => setMonths(v.map((m: string) => MONTHS.indexOf(m) + 1))}
                            placeholder="All Months"
                        />
                        <MultiSelect
                            label="Days"
                            options={DAYS}
                            selected={daysOfWeek.map(d => DAYS[d])}
                            onChange={(v: string[]) => setDaysOfWeek(v.map((d: string) => DAYS.indexOf(d)))}
                            placeholder="All Days"
                        />
                        <MultiSelect
                            label="C1 Hour"
                            options={HOURS}
                            selected={c1OpenHours.map(h => HOURS[h])}
                            onChange={(v: string[]) => setC1OpenHours(v.map((h: string) => HOURS.indexOf(h)))}
                            placeholder="All Hours"
                        />
                    </div>
                </div>
            </div>

            <div className={`p-6 border-t border-white/5 bg-black/40 backdrop-blur-md ${isCollapsed ? 'opacity-0' : 'opacity-100'} transition-opacity`}>
                <button
                    onClick={resetFilters}
                    className="w-full px-4 py-3 text-[10px] font-black text-rose-500 border border-rose-500/20 rounded-xl hover:bg-rose-500 hover:text-white transition-all duration-300 uppercase tracking-[0.2em] shadow-lg shadow-rose-900/10"
                >
                    Reset Analysis
                </button>
            </div>
        </aside>
    );
}

function SectionHeader({ icon, title }: { icon: React.ReactNode; title: string }) {
    return (
        <div className="flex items-center gap-2 px-1">
            <span className="text-emerald-500">{icon}</span>
            <span className="text-[10px] font-bold text-[#606060] uppercase tracking-widest">{title}</span>
        </div>
    );
}

function FilterDropDown({ label, value, options, onChange }: { label: string; value: string; options: string[]; onChange: (v: string) => void }) {
    const isFiltered = value !== 'all';
    return (
        <div>
            <label className="text-[10px] font-bold text-[#606060] block mb-1.5 ml-1 uppercase">{label}</label>
            <select
                value={value}
                onChange={(e) => onChange(e.target.value)}
                title={label}
                className={`w-full bg-[#1a1a1a] border rounded-lg px-3 py-2 text-sm focus:outline-none transition-all duration-200 ${isFiltered ? 'border-emerald-500/50 text-emerald-400 font-bold' : 'border-[#3d3d3d] text-[#a0a0a0]'
                    }`}
            >
                {options.map(t => <option key={t} value={t} className="bg-[#1a1a1a] text-white uppercase">{t}</option>)}
            </select>
        </div>
    );
}

function MultiSelect({ label, options, selected, onChange, placeholder }: any) {
    const [open, setOpen] = useState(false);
    const isFiltered = selected.length > 0;

    const toggle = (opt: string) => {
        if (selected.includes(opt)) {
            onChange(selected.filter((s: any) => s !== opt));
        } else {
            onChange([...selected, opt]);
        }
    };

    return (
        <div className="relative">
            <label className="text-[10px] font-bold text-[#606060] block mb-1.5 ml-1 uppercase">{label}</label>
            <button
                onClick={() => setOpen(!open)}
                className={`w-full bg-[#1a1a1a] border rounded-lg px-3 py-2 text-sm text-left flex items-center justify-between focus:outline-none transition-all duration-200 ${isFiltered ? 'border-emerald-500/50 text-emerald-400 font-bold' : 'border-[#3d3d3d] text-[#606060]'
                    }`}
            >
                <span className="truncate">
                    {selected.length ? `${selected.length} items` : placeholder}
                </span>
                <ChevronDown className={`w-3.5 h-3.5 transition-transform ${open ? 'rotate-180' : ''}`} />
            </button>

            {open && (
                <>
                    <div className="fixed inset-0 z-40" onClick={() => setOpen(false)} />
                    <div className="absolute left-0 right-0 z-50 mt-1 max-h-64 bg-[#1a1a1a] border border-[#3d3d3d] shadow-2xl rounded-lg overflow-y-auto scrollbar-thin scrollbar-thumb-[#3d3d3d]">
                        {options.map((opt: string) => (
                            <label key={opt} className="flex items-center px-3 py-2 hover:bg-[#2d2d2d] cursor-pointer group">
                                <div className={`w-4 h-4 rounded border flex items-center justify-center mr-3 transition-all ${selected.includes(opt) ? 'bg-emerald-500 border-emerald-500' : 'border-[#3d3d3d] group-hover:border-[#606060]'
                                    }`}>
                                    {selected.includes(opt) && <div className="w-1.5 h-1.5 bg-white rounded-full" />}
                                </div>
                                <input
                                    type="checkbox"
                                    className="hidden"
                                    checked={selected.includes(opt)}
                                    onChange={() => toggle(opt)}
                                />
                                <span className={`text-xs uppercase ${selected.includes(opt) ? 'text-white font-bold' : 'text-[#a0a0a0]'}`}>{opt}</span>
                            </label>
                        ))}
                    </div>
                </>
            )}
        </div>
    );
}
