export interface WhaleAnomaly {
  strike: number;
  type: 'CALL' | 'PUT';
  dte_str: string;
  confluence: number;
  avg_vol_oi_ratio: number;
  notional: number;
  tier: number;
  volume: number;
  is_golden_sweep?: boolean;
}

export interface MacroSnapshotData {
  ticker: string;
  timestamp: string;
  tradingDate: string;
  spotPrice: number;
  macroCallWall: number | null;
  macroPutWall: number | null;
  zeroGamma: number | null;
  anomalies: {
    structural: WhaleAnomaly[];
    tactical: WhaleAnomaly[];
  };
  dominantNodes?: DominantNode[];
}

export interface DominantNode {
  strike: number;
  type: 'CALL' | 'PUT';
  oi: number;
  dominance_pct: number;
  label: string;
}
