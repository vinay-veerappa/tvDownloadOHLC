'use client';

import React, { useEffect, useState, useMemo } from 'react';
import ReactECharts from 'echarts-for-react';
import { Card } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { useRouter } from 'next/navigation';
import { RefreshCcw, Layers, Search, ChevronDown, Filter, X } from 'lucide-react';

interface HeatmapTreemapProps {
  initialType?: 'sp500' | 'nasdaq100' | 'themes' | 'etfs';
}

export default function HeatmapTreemap({ initialType = 'sp500' }: HeatmapTreemapProps) {
  const router = useRouter();
  const [mapType, setMapType] = useState<'sp500' | 'nasdaq100' | 'themes' | 'etfs'>(initialType);
  const [treeData, setTreeData] = useState<any>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [selectedGroup, setSelectedGroup] = useState<string>('ALL'); // Selected Sector / Theme filter
  const [activeCategoryModal, setActiveCategoryModal] = useState<{ name: string; stocks: any[] } | null>(null);

  useEffect(() => {
    async function loadHeatmap() {
      try {
        setLoading(true);
        const res = await fetch(`/api/heatmaps/${mapType}`);
        const data = await res.json();
        setTreeData(data);
        setSelectedGroup('ALL'); // Reset group filter on map switch
      } catch (err) {
        console.error('Failed to load heatmap:', err);
      } finally {
        setLoading(false);
      }
    }
    loadHeatmap();
  }, [mapType]);

  // Extract all sector / theme names for the group dropdown filter
  const groupNames = useMemo(() => {
    if (!treeData || !treeData.children) return [];
    return treeData.children.map((c: any) => c.name).sort();
  }, [treeData]);

  // Filter tree data by selected Sector / Theme
  const filteredTreeData = useMemo(() => {
    if (!treeData || !treeData.children) return null;
    if (selectedGroup === 'ALL') return treeData;
    const matched = treeData.children.filter((c: any) => c.name === selectedGroup);
    return {
      name: treeData.name,
      children: matched
    };
  }, [treeData, selectedGroup]);

  const option = useMemo(() => {
    if (!filteredTreeData || !filteredTreeData.children) return {};

    const getColorForPct = (pct: number) => {
      if (pct >= 3.0) return '#10b981'; // bright emerald
      if (pct >= 1.5) return '#059669';
      if (pct > 0) return '#047857';
      if (pct === 0) return '#3f3f46'; // zinc
      if (pct > -1.5) return '#b91c1c';
      if (pct > -3.0) return '#dc2626';
      return '#ef4444'; // bright ruby red
    };

    // Helper to recursively collect all leaf stocks under a sector/theme node
    const collectLeafStocks = (node: any): any[] => {
      if (!node) return [];
      if (node.children) {
        return node.children.flatMap(collectLeafStocks);
      }
      if (node.name && node.price !== undefined) {
        return [node];
      }
      return [];
    };

    const processChildren = (node: any) => {
      if (node.children) {
        return {
          name: node.name,
          children: node.children.map(processChildren)
        };
      }
      return {
        name: node.name,
        value: node.value || 1000000000,
        price: node.price,
        changePct: node.changePct,
        company: node.company,
        itemStyle: {
          color: getColorForPct(node.changePct || 0)
        }
      };
    };

    const formattedData = filteredTreeData.children.map(processChildren);

    return {
      tooltip: {
        trigger: 'item',
        enterable: true,
        formatter: (info: any) => {
          const data = info.data;

          // Single Stock Leaf Node Tooltip
          if (data && data.price !== undefined) {
            const isPos = data.changePct >= 0;
            return `
              <div class="font-mono p-1 text-xs space-y-1">
                <div class="font-bold text-white text-sm">${data.name} <span class="text-zinc-400 text-xs font-normal">(${data.company || ''})</span></div>
                <div class="flex justify-between gap-4 text-zinc-300">
                  <span>Price:</span>
                  <span class="font-bold text-white">$${data.price.toFixed(2)}</span>
                </div>
                <div class="flex justify-between gap-4">
                  <span class="text-zinc-300">Change:</span>
                  <span class="font-bold ${isPos ? 'text-emerald-400' : 'text-rose-400'}">${isPos ? '+' : ''}${data.changePct.toFixed(2)}%</span>
                </div>
                <div class="text-[10px] text-cyan-400 pt-1 border-t border-zinc-700">Click to view profile →</div>
              </div>
            `;
          }

          // Sector / Theme Parent Node Tooltip (Finviz Dropdown Card showing ALL tickers in category)
          const leafStocks = collectLeafStocks(info.data);
          if (leafStocks.length > 0) {
            const stocksListHtml = leafStocks.slice(0, 15).map((s: any) => {
              const isPos = s.changePct >= 0;
              return `
                <div style="display:flex; justify-content:space-between; align-items:center; font-size:11px; padding:2px 0; border-bottom:1px solid #18181b;">
                  <span style="font-weight:bold; color:#ffffff; width:50px;">${s.name}</span>
                  <span style="color:#a1a1aa; padding:0 8px;">$${s.price.toFixed(2)}</span>
                  <span style="font-weight:bold; color:${isPos ? '#34d399' : '#f87171'};">${isPos ? '+' : ''}${s.changePct.toFixed(2)}%</span>
                </div>
              `;
            }).join('');

            return `
              <div style="font-family:monospace; padding:8px; background-color:#09090b; border:1px solid #27272a; border-radius:8px; min-width:240px;">
                <div style="font-weight:bold; color:#22d3ee; font-size:12px; border-bottom:1px solid #27272a; padding-bottom:4px; margin-bottom:6px; display:flex; justify-space-between;">
                  <span>${info.name}</span>
                  <span style="color:#71717a; font-size:10px; font-weight:normal;">(${leafStocks.length} Tickers)</span>
                </div>
                <div style="max-height:220px; overflow-y:auto;">
                  ${stocksListHtml}
                </div>
                ${leafStocks.length > 15 ? `<div style="font-size:9px; color:#a1a1aa; text-align:center; padding-top:4px;">+ ${leafStocks.length - 15} more tickers... (Click category to view all)</div>` : ''}
              </div>
            `;
          }

          return `<div class="font-mono text-xs font-bold text-zinc-200">${info.name}</div>`;
        },
        backgroundColor: '#09090b',
        borderColor: '#27272a',
        textStyle: { color: '#f4f4f5' }
      },
      series: [
        {
          type: 'treemap',
          width: '100%',
          height: '100%',
          roam: false,
          nodeClick: false,
          breadcrumb: { show: false },
          label: {
            show: true,
            formatter: (params: any) => {
              if (params.data && params.data.changePct !== undefined) {
                const isPos = params.data.changePct >= 0;
                return `{name|${params.name}}\n{change|${isPos ? '+' : ''}${params.data.changePct.toFixed(2)}%}`;
              }
              return params.name;
            },
            rich: {
              name: {
                fontSize: 13,
                fontWeight: 'bold',
                color: '#ffffff',
                fontFamily: 'monospace',
                lineHeight: 16
              },
              change: {
                fontSize: 11,
                fontWeight: '600',
                color: '#e4e4e7',
                fontFamily: 'monospace'
              }
            }
          },
          itemStyle: {
            borderColor: '#09090b',
            borderWidth: 2,
            gapWidth: 2
          },
          levels: [
            {
              itemStyle: {
                borderColor: '#09090b',
                borderWidth: 4,
                gapWidth: 4
              },
              upperLabel: {
                show: true,
                height: 26,
                color: '#ffffff',
                backgroundColor: '#18181b',
                fontFamily: 'monospace',
                fontSize: 12,
                fontWeight: 'bold',
                padding: [4, 8]
              }
            },
            {
              itemStyle: {
                borderColor: '#18181b',
                borderWidth: 2,
                gapWidth: 2
              },
              upperLabel: {
                show: true,
                height: 18,
                color: '#a1a1aa',
                fontFamily: 'monospace',
                fontSize: 10,
                fontWeight: '600',
                padding: [2, 4]
              }
            },
            {
              itemStyle: {
                borderColor: '#09090b',
                borderWidth: 1,
                gapWidth: 1
              }
            }
          ],
          data: formattedData
        }
      ]
    };
  }, [filteredTreeData]);

  // Handle click on Treemap nodes (single ticker vs sector group)
  const onChartClick = (params: any) => {
    if (params.data) {
      if (params.data.price !== undefined) {
        // Direct single ticker click
        router.push(`/research/screener/${params.data.name}`);
      } else {
        // Sector / Theme parent block click -> Open Category Stocks Modal Dropdown
        const collect = (node: any): any[] => {
          if (!node) return [];
          if (node.children) return node.children.flatMap(collect);
          if (node.name && node.price !== undefined) return [node];
          return [];
        };
        const stocks = collect(params.data);
        if (stocks.length > 0) {
          setActiveCategoryModal({
            name: params.data.name,
            stocks: stocks.sort((a, b) => b.value - a.value)
          });
        }
      }
    }
  };

  return (
    <Card className="bg-zinc-950 border-zinc-800 p-4 space-y-4 rounded-xl shadow-2xl relative">
      {/* Controls Header */}
      <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-4 border-b border-zinc-800 pb-4">
        <div className="flex items-center space-x-3">
          <Layers className="h-5 w-5 text-cyan-400" />
          <h2 className="text-lg font-bold font-mono text-white tracking-tight">Market Heatmaps</h2>
        </div>

        <div className="flex flex-wrap items-center gap-3">
          {/* Sector / Theme Filter Dropdown */}
          <div className="relative flex items-center">
            <Filter className="absolute left-2.5 h-3.5 w-3.5 text-cyan-400" />
            <select
              value={selectedGroup}
              onChange={(e) => setSelectedGroup(e.target.value)}
              className="pl-8 pr-7 py-1.5 bg-zinc-900 border border-zinc-800 rounded-lg text-xs font-mono text-cyan-300 font-bold focus:outline-none focus:border-cyan-500 appearance-none cursor-pointer"
            >
              <option value="ALL">All Sectors & Themes ({groupNames.length})</option>
              {groupNames.map((g: string) => (
                <option key={g} value={g}>
                  {g}
                </option>
              ))}
            </select>
            <ChevronDown className="absolute right-2 h-3.5 w-3.5 text-zinc-500 pointer-events-none" />
          </div>

          {/* Map Type Buttons */}
          <div className="flex items-center space-x-1.5 overflow-x-auto">
            {[
              { id: 'sp500', label: 'S&P 500' },
              { id: 'nasdaq100', label: 'Nasdaq 100' },
              { id: 'themes', label: 'Themes Map' },
              { id: 'etfs', label: 'Sector ETFs' }
            ].map((btn) => (
              <Button
                key={btn.id}
                onClick={() => setMapType(btn.id as any)}
                variant={mapType === btn.id ? 'default' : 'outline'}
                className={`h-8 text-xs font-mono font-bold ${
                  mapType === btn.id
                    ? 'bg-cyan-600 hover:bg-cyan-500 text-white'
                    : 'bg-zinc-900 border-zinc-800 text-zinc-400 hover:bg-zinc-800 hover:text-zinc-200'
                }`}
              >
                {btn.label}
              </Button>
            ))}
          </div>
        </div>
      </div>

      {/* Treemap Render Container */}
      <div className="w-full h-[650px] relative bg-zinc-900/40 rounded-lg overflow-hidden border border-zinc-800/80">
        {loading ? (
          <div className="absolute inset-0 flex flex-col items-center justify-center space-y-3 bg-zinc-950/80">
            <RefreshCcw className="h-8 w-8 text-cyan-400 animate-spin" />
            <span className="text-xs text-zinc-400 font-mono">Loading {mapType.toUpperCase()} Heatmap...</span>
          </div>
        ) : (
          <ReactECharts
            option={option}
            style={{ height: '100%', width: '100%' }}
            onEvents={{ click: onChartClick }}
          />
        )}
      </div>

      {/* Finviz Category Tickers Dropdown Modal / Side Drawer */}
      {activeCategoryModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 backdrop-blur-sm p-4">
          <div className="bg-zinc-950 border border-zinc-800 rounded-xl p-5 max-w-lg w-full space-y-4 shadow-2xl font-mono">
            <div className="flex items-center justify-between border-b border-zinc-800 pb-3">
              <div>
                <h3 className="text-sm font-bold text-cyan-400 uppercase tracking-wider">
                  {activeCategoryModal.name}
                </h3>
                <p className="text-[10px] text-zinc-500 mt-0.5">
                  All {activeCategoryModal.stocks.length} Tickers in this Category / Theme
                </p>
              </div>
              <Button
                size="icon"
                variant="ghost"
                onClick={() => setActiveCategoryModal(null)}
                className="h-7 w-7 text-zinc-400 hover:text-white hover:bg-zinc-900"
              >
                <X className="h-4 w-4" />
              </Button>
            </div>

            {/* List of Tickers */}
            <div className="max-h-[380px] overflow-y-auto space-y-2 pr-1">
              {activeCategoryModal.stocks.map((s: any) => {
                const isPos = s.changePct >= 0;
                return (
                  <div
                    key={s.name}
                    onClick={() => {
                      setActiveCategoryModal(null);
                      router.push(`/research/screener/${s.name}`);
                    }}
                    className="flex items-center justify-between p-2.5 rounded-lg bg-zinc-900/60 hover:bg-zinc-900 border border-zinc-800/80 cursor-pointer transition-colors"
                  >
                    <div>
                      <div className="font-bold text-white text-xs">{s.name}</div>
                      <div className="text-[10px] text-zinc-500">{s.company || s.name}</div>
                    </div>
                    <div className="text-right text-xs">
                      <div className="font-bold text-zinc-200">${s.price.toFixed(2)}</div>
                      <div className={`font-bold ${isPos ? 'text-emerald-400' : 'text-rose-400'}`}>
                        {isPos ? '+' : ''}{s.changePct.toFixed(2)}%
                      </div>
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        </div>
      )}
    </Card>
  );
}
