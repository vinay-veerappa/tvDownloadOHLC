"use client"

import React from 'react'
import { 
  Zap, 
  LayoutGrid, 
  Timer, 
  Activity,
  Maximize2
} from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { 
  DropdownMenu, 
  DropdownMenuContent, 
  DropdownMenuItem, 
  DropdownMenuTrigger 
} from '@/components/ui/dropdown-menu'
import { Slider } from '@/components/ui/slider'
import { Input } from '@/components/ui/input'

interface DashboardTopBarProps {
  activeTicker: string
  setActiveTicker: (t: string) => void
  lastSync: Date | null
  refreshInterval: number
  setRefreshInterval: (ms: number) => void
  strikeZoomRange: number
  setStrikeZoomRange: (val: number) => void
  onToggleSidebar: () => void
  onToggleRightSidebar: () => void
  sidebarOpen: boolean
  rightSidebarOpen: boolean
}

export function DashboardTopBar({ 
  activeTicker, 
  setActiveTicker, 
  lastSync, 
  refreshInterval, 
  setRefreshInterval,
  strikeZoomRange,
  setStrikeZoomRange,
  onToggleSidebar,
  onToggleRightSidebar,
  sidebarOpen,
  rightSidebarOpen
}: DashboardTopBarProps) {
  return (
    <header className="h-20 border-b border-white/5 bg-zinc-950/80 backdrop-blur-2xl px-10 flex items-center justify-between shrink-0 z-50">
      <div className="flex items-center gap-10">
        <div className="flex items-center gap-4">
          <div className="h-12 w-12 bg-emerald-500 rounded-2xl flex items-center justify-center shadow-[0_0_30px_rgba(16,185,129,0.3)]">
            <Zap className="text-black fill-black" size={24} />
          </div>
          <div>
            <h1 className="text-lg font-black tracking-tighter text-white uppercase italic">Mission Control</h1>
            <div className="flex items-center gap-2">
              <span className="text-[9px] font-black text-zinc-500 uppercase tracking-[0.3em]">Institutional GEX Analytics</span>
              <Badge variant="outline" className="text-[8px] bg-emerald-500/10 text-emerald-400 border-white/5 font-black py-0">v6.5.0-LIVE</Badge>
            </div>
          </div>
        </div>

        <div className="h-10 w-[1px] bg-white/5 mx-2" />

        <div className="flex items-center gap-2">
          <Button 
            variant="ghost" 
            size="icon" 
            onClick={onToggleSidebar}
            className={`h-11 w-11 rounded-xl border transition-all ${sidebarOpen ? 'bg-emerald-500/10 border-emerald-500/20 text-emerald-400' : 'bg-zinc-900/50 border-white/5 text-zinc-500 hover:text-white'}`}
            title="Toggle Watchlist (L)"
          >
            <LayoutGrid size={18} />
          </Button>
          <Button 
            variant="ghost" 
            size="icon" 
            onClick={onToggleRightSidebar}
            className={`h-11 w-11 rounded-xl border transition-all ${rightSidebarOpen ? 'bg-emerald-500/10 border-emerald-500/20 text-emerald-400' : 'bg-zinc-900/50 border-white/5 text-zinc-500 hover:text-white'}`}
            title="Toggle Briefing (R)"
          >
            <Activity size={18} />
          </Button>
        </div>

        <div className="h-10 w-[1px] bg-white/5 mx-2" />

        <div className="flex items-center gap-6 bg-zinc-900/30 px-8 py-3 rounded-2xl border border-white/5 group hover:border-emerald-500/20 transition-all duration-500 shadow-sm">
            <div className="flex flex-col">
              <span className="text-[8px] font-black text-zinc-600 uppercase tracking-[0.3em] mb-1.5 group-hover:text-emerald-500/50 transition-colors">Surface Precision</span>
              <div className="flex items-center gap-6">
                <span className="text-[10px] font-black text-zinc-400 uppercase tracking-widest min-w-[70px]">Strike Depth</span>
                <Slider 
                  value={[strikeZoomRange]} 
                  onValueChange={(v) => setStrikeZoomRange(v[0])} 
                  max={20} 
                  min={1} 
                  step={1} 
                  className="w-40" 
                />
                <div className="flex items-center gap-2">
                  <Input 
                    type="number"
                    value={strikeZoomRange}
                    onChange={(e) => {
                      const val = parseInt(e.target.value);
                      if (!isNaN(val)) setStrikeZoomRange(Math.max(1, Math.min(50, val)));
                    }}
                    className="h-7 w-12 bg-black/50 border-white/10 text-[11px] font-black text-emerald-400 text-center rounded-lg p-0 [appearance:textfield] [&::-webkit-outer-spin-button]:appearance-none [&::-webkit-inner-spin-button]:appearance-none"
                  />
                  <span className="text-[11px] font-mono font-black text-emerald-400/50">%</span>
                </div>
              </div>
            </div>
        </div>
      </div>

      <div className="flex items-center gap-8">
        <div className="flex flex-col items-end gap-1">
          <div className="flex items-center gap-2">
            <Timer size={12} className="text-emerald-500/50" />
            <span className="text-[10px] font-black text-zinc-400 uppercase tracking-widest">
              Last Pulse: {lastSync ? lastSync.toLocaleTimeString() : '—'}
            </span>
          </div>
          <div className="flex items-center gap-4">
            <DropdownMenu>
              <DropdownMenuTrigger asChild>
                <button className="text-[9px] font-black text-zinc-600 hover:text-emerald-400 uppercase tracking-widest transition-colors">
                  Frequency: {refreshInterval / 1000}s
                </button>
              </DropdownMenuTrigger>
              <DropdownMenuContent align="end" className="bg-zinc-900 border-white/10 rounded-xl">
                {[5000, 15000, 30000, 60000].map(ms => (
                  <DropdownMenuItem 
                    key={ms} 
                    onClick={() => setRefreshInterval(ms)}
                    className="text-[10px] font-black uppercase tracking-widest text-zinc-400 focus:bg-emerald-500/10 focus:text-emerald-400 cursor-pointer"
                  >
                    {ms / 1000} Seconds
                  </DropdownMenuItem>
                ))}
              </DropdownMenuContent>
            </DropdownMenu>
          </div>
        </div>

        <div className="h-10 w-[1px] bg-white/5 mx-2" />
        
        <div className="flex items-center gap-3">
          <div className="px-4 py-2 bg-zinc-900/50 rounded-xl border border-white/5">
            <span className="text-[10px] font-black text-zinc-500 uppercase tracking-widest">Active: </span>
            <span className="text-[10px] font-black text-emerald-400 uppercase tracking-widest">{activeTicker}</span>
          </div>
        </div>
      </div>
    </header>
  )
}
