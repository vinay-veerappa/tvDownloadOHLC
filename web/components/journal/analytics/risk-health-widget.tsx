"use client"

import { useEffect, useState } from "react"
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card"
import { getRiskMetrics, RiskMetrics } from "@/actions/analytics-actions"
import { Badge } from "@/components/ui/badge"
import { Info, AlertTriangle, TrendingUp, TrendingDown, Target, Shield, Activity } from "lucide-react"
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from "@/components/ui/tooltip"

interface RiskHealthWidgetProps {
  accountId?: string;
  strategyId?: string;
  startDate?: Date;
  endDate?: Date;
}

export function RiskHealthWidget({ accountId, strategyId, startDate, endDate }: RiskHealthWidgetProps) {
  const [metrics, setMetrics] = useState<RiskMetrics | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    async function load() {
      setLoading(true)
      try {
        const data = await getRiskMetrics({ accountId, strategyId, startDate, endDate })
        setMetrics(data)
      } catch (err) {
        console.error("Failed to load risk metrics", err)
      } finally {
        setLoading(false)
      }
    }
    load()
  }, [accountId, strategyId, startDate, endDate])

  if (loading) {
    return <div className="h-64 flex items-center justify-center text-muted-foreground animate-pulse">Calculating System Health...</div>
  }

  if (!metrics) return null

  // Helper to determine traffic light color
  const getScoreColor = (value: number, type: "SQN" | "ROR" | "CombinedEdge" | "DRR") => {
    switch (type) {
      case "SQN":
        if (value >= 3.0) return "text-green-500";
        if (value >= 2.0) return "text-emerald-400"; // B
        if (value >= 1.5) return "text-yellow-500"; // C
        return "text-red-500"; // D/F
      case "ROR":
        if (value < 1.0) return "text-green-500"; // Excellent
        if (value < 5.0) return "text-emerald-400"; // OK
        if (value < 10.0) return "text-yellow-500"; // Dangerous
        return "text-red-600"; // Lethal
      case "CombinedEdge":
        if (value > 150) return "text-green-500";
        if (value > 100) return "text-emerald-400";
        if (value > 50) return "text-yellow-500";
        return "text-red-500";
      case "DRR":
        if (value < 4) return "text-green-500";
        if (value < 6) return "text-emerald-400";
        if (value < 8) return "text-yellow-500";
        return "text-red-500";
      default: return "text-foreground";
    }
  }

  return (
    <div className="space-y-4">
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        
        {/* Combined Edge */}
        <Card className="border-l-4 border-l-blue-500">
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Combined Edge</CardTitle>
            <Activity className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className={`text-2xl font-bold ${getScoreColor(metrics.combinedEdge, "CombinedEdge")}`}>
              {metrics.combinedEdge.toFixed(1)}
            </div>
            <p className="text-xs text-muted-foreground mt-1">
              (EV / AvgLoss) × PF
            </p>
            <div className="mt-2 text-xs">
              Targets: {metrics.combinedEdge > 100 ? "Excellent (>100)" : "Needs Work (<50)"}
            </div>
          </CardContent>
        </Card>

        {/* SQN */}
        <Card className="border-l-4 border-l-purple-500">
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <div className="flex items-center gap-2">
               <CardTitle className="text-sm font-medium">SQN Score</CardTitle>
               <TooltipProvider>
                 <Tooltip>
                   <TooltipTrigger><Info className="h-3 w-3 text-muted-foreground cursor-pointer" /></TooltipTrigger>
                   <TooltipContent><p>System Quality Number: (AvgR * √N) / StdDev(R)</p></TooltipContent>
                 </Tooltip>
               </TooltipProvider>
            </div>
            <Target className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className={`text-2xl font-bold ${getScoreColor(metrics.sqn, "SQN")}`}>
              {metrics.sqn.toFixed(2)}
            </div>
            <p className="text-xs text-muted-foreground mt-1">
              Quality Rating
            </p>
            <div className="mt-2">
              <Badge variant={metrics.sqn > 2.0 ? "default" : "secondary"} className={metrics.sqn > 3.0 ? "bg-green-600" : ""}>
                 {metrics.sqn > 3.0 ? "Holy Grail" : metrics.sqn > 2.0 ? "Excellent" : metrics.sqn > 1.5 ? "Average" : "Weak"}
              </Badge>
            </div>
          </CardContent>
        </Card>

        {/* Risk of Ruin */}
        <Card className="border-l-4 border-l-red-500">
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
             <div className="flex items-center gap-2">
               <CardTitle className="text-sm font-medium">Risk of Ruin</CardTitle>
               <TooltipProvider>
                 <Tooltip>
                   <TooltipTrigger><AlertTriangle className="h-3 w-3 text-red-400 cursor-pointer" /></TooltipTrigger>
                   <TooltipContent><p>Probability of blowing account (based on 20 units)</p></TooltipContent>
                 </Tooltip>
               </TooltipProvider>
            </div>
            <Shield className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className={`text-2xl font-bold ${getScoreColor(metrics.ror, "ROR")}`}>
              {metrics.ror.toFixed(1)}%
            </div>
            <p className="text-xs text-muted-foreground mt-1">
              Chance of Ruin
            </p>
            <div className="mt-2 text-xs text-muted-foreground">
               Max Streak Predicted: <span className="font-semibold text-foreground">{metrics.predictedMaxStreak.toFixed(1)}</span>
            </div>
          </CardContent>
        </Card>

        {/* DRR */}
        <Card className="border-l-4 border-l-yellow-500">
           <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
             <div className="flex items-center gap-2">
               <CardTitle className="text-sm font-medium">Drawdown Rating</CardTitle>
               <TooltipProvider>
                 <Tooltip>
                   <TooltipTrigger><Info className="h-3 w-3 text-muted-foreground cursor-pointer" /></TooltipTrigger>
                   <TooltipContent><p>DRR = MaxDD / AvgLoss. Lower is better.</p></TooltipContent>
                 </Tooltip>
               </TooltipProvider>
            </div>
            <TrendingDown className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
             <div className={`text-2xl font-bold ${getScoreColor(metrics.drr, "DRR")}`}>
              {metrics.drr.toFixed(1)}
            </div>
             <p className="text-xs text-muted-foreground mt-1">
              Based on Max DD ${metrics.maxDrawdown.toFixed(0)}
            </p>
             <div className="mt-2 text-xs">
              {metrics.drr < 6 ? "Good Stability" : "High Volatility"}
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Advanced Stats Grid */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4 p-4 border rounded-lg bg-card/50">
         <div>
            <div className="text-xs text-muted-foreground uppercase font-bold tracking-wider">EV per Trade</div>
            <div className={`text-lg font-mono font-semibold ${metrics.ev > 0 ? "text-green-500" : "text-red-500"}`}>
               ${metrics.ev.toFixed(2)}
            </div>
         </div>
         <div>
            <div className="text-xs text-muted-foreground uppercase font-bold tracking-wider">Profit Factor</div>
            <div className="text-lg font-mono font-semibold">
               {metrics.pf.toFixed(2)}
            </div>
         </div>
         <div>
            <div className="text-xs text-muted-foreground uppercase font-bold tracking-wider">Actual Streak</div>
            <div className="text-lg font-mono font-semibold text-red-400">
               {metrics.maxConsecutiveLosses} Loss
            </div>
         </div>
         <div>
            <div className="text-xs text-muted-foreground uppercase font-bold tracking-wider">Win Rate</div>
            <div className="text-lg font-mono font-semibold">
               {metrics.winRate.toFixed(1)}%
            </div>
         </div>
      </div>
    </div>
  )
}
