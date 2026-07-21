'use client';

import React, { useEffect, useState, useMemo } from 'react';
import ReactECharts from 'echarts-for-react';
import { Card } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { useRouter } from 'next/navigation';
import { RefreshCcw, Layers } from 'lucide-react';

interface HeatmapTreemapProps {
  initialType?: 'sp500' | 'nasdaq100' | 'themes' | 'etfs';
}

export default function HeatmapTreemap({ initialType = 'sp500' }: HeatmapTreemapProps) {
  const router = useRouter();
  const [mapType, setMapType] = useState<'sp500' | 'nasdaq100' | 'themes' | 'etfs'>(initialType);
  const [treeData, setTreeData] = useState<any>(null);
  const [loading, setLoading] = useState<boolean>(true);

  useEffect(() => {
    async function loadHeatmap() {
      try {
        setLoading(true);
        const res = await fetch(`/api/heatmaps/${mapType}`);
        const data = await res.json();
        setTreeData(data);
      } catch (err) {
        console.error('Failed to load heatmap:', err);
      } finally {
        setLoading(false);
      }
    }
    loadHeatmap();
  }, [mapType]);

  const option = useMemo(() => {
    if (!treeData || !treeData.children) return {};

    // Helper for visual color mapping based on changePct (-3% to +3%)
    const getColorForPct = (pct: number) => {
      if (pct >= 3.0) return '#10b981'; // bright emerald
      if (pct >= 1.5) return '#059669';
      if (pct > 0) return '#047857';
      if (pct === 0) return '#3f3f46'; // zinc
      if (pct > -1.5) return '#b91c1c';
      if (pct > -3.0) return '#dc2626';
      return '#ef4444'; // bright ruby red
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

    const formattedData = treeData.children.map(processChildren);

    return {
      tooltip: {
        formatter: (info: any) => {
          const data = info.data;
          if (!data || !data.price) {
            return `<div class="font-mono text-xs font-bold text-zinc-200">${info.name}</div>`;
          }
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
              <div class="text-[10px] text-cyan-400 pt-1 border-t border-zinc-700">Click to view full analysis profile →</div>
            </div>
          `;
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
                borderColor: '#18181b',
                borderWidth: 3,
                gapWidth: 3
              },
              upperLabel: {
                show: true,
                height: 24,
                color: '#a1a1aa',
                fontFamily: 'monospace',
                fontSize: 11,
                fontWeight: 'bold'
              }
            },
            {
              itemStyle: {
                borderColor: '#27272a',
                borderWidth: 1,
                gapWidth: 1
              }
            }
          ],
          data: formattedData
        }
      ]
    };
  }, [treeData]);

  const onChartClick = (params: any) => {
    if (params.data && params.data.name && params.data.price !== undefined) {
      router.push(`/research/screener/${params.data.name}`);
    }
  };

  return (
    <Card className="bg-zinc-950 border-zinc-800 p-4 space-y-4 rounded-xl shadow-2xl">
      {/* Controls Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-b border-zinc-800 pb-4">
        <div className="flex items-center space-x-2">
          <Layers className="h-5 w-5 text-cyan-400" />
          <h2 className="text-lg font-bold font-mono text-white tracking-tight">Market Heatmaps</h2>
        </div>

        <div className="flex items-center space-x-2 overflow-x-auto">
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
    </Card>
  );
}
