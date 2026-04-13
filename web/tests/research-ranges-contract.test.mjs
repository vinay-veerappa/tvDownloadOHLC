import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';

const pagePath = path.resolve(process.cwd(), 'app/research/ranges/page.tsx');
const source = fs.readFileSync(pagePath, 'utf8');

function mustInclude(snippet, message) {
  assert.equal(
    source.includes(snippet),
    true,
    message ?? `Expected snippet not found: ${snippet}`,
  );
}

test('ranges page includes both-sides sweep probability analytics', () => {
  mustInclude('type BothSidesConditionRow', 'Missing both-sides condition type.');
  mustInclude('function getBothSidesConditionSql', 'Missing both-sides condition SQL helper.');
  mustInclude('Sweep Probability', 'Missing both-sides sweep probability card.');
  mustInclude('Top Lift Condition', 'Missing both-sides lift card.');
});

test('ranges page includes GEX overlap panel', () => {
  mustInclude('GEX Overlap', 'Missing GEX overlap panel.');
  mustInclude('describeLevelOverlap', 'Missing overlap distance helper.');
  mustInclude('Macro Call Wall', 'Missing call-wall row.');
  mustInclude('Macro Put Wall', 'Missing put-wall row.');
});

test('ranges page includes execution-quality missing statistics', () => {
  mustInclude('type ExecutionQualitySummary', 'Missing execution quality summary type.');
  mustInclude('function getExecutionQualitySummarySql', 'Missing execution quality summary SQL helper.');
  mustInclude('Median Minutes to Loss', 'Missing median minutes-to-loss card.');
  mustInclude('MAE Before MFE (Winners)', 'Missing MAE-before-MFE card.');
});

test('ranges page includes session-segment expectancy decomposition', () => {
  mustInclude('type SessionExpectancyRow', 'Missing session expectancy type.');
  mustInclude('function getSessionExpectancySql', 'Missing session expectancy SQL helper.');
  mustInclude('Entry Session Segment', 'Missing session expectancy table header.');
  mustInclude('POWER_HOUR', 'Missing power-hour session bucket.');
});

test('ranges page includes sweep-reclaim efficiency decomposition', () => {
  mustInclude('type SweepReclaimSummary', 'Missing sweep-reclaim summary type.');
  mustInclude('function getSweepReclaimSummarySql', 'Missing sweep-reclaim summary SQL helper.');
  mustInclude('Sweep → Reclaim Efficiency', 'Missing sweep-reclaim panel.');
  mustInclude('Median Follow-Through', 'Missing sweep-reclaim median follow-through metric.');
});

test('ranges page includes breakout acceptance quality diagnostics', () => {
  mustInclude('type BreakoutAcceptanceSummary', 'Missing breakout acceptance summary type.');
  mustInclude('function getBreakoutAcceptanceSummarySql', 'Missing breakout acceptance SQL helper.');
  mustInclude('Breakout Acceptance', 'Missing breakout acceptance panel.');
  mustInclude('2-Bar Hold Rate', 'Missing 2-bar hold metric.');
  mustInclude('Median Pullback Depth', 'Missing breakout pullback-depth metric.');
});

test('ranges page includes volatility-normalized excursion diagnostics', () => {
  mustInclude('type VolatilityExcursionSummary', 'Missing volatility excursion summary type.');
  mustInclude('function getVolatilityExcursionSql', 'Missing volatility excursion SQL helper.');
  mustInclude('Volatility-Normalized Excursion', 'Missing volatility-normalized excursion panel.');
  mustInclude('Directional/Adverse Ratio', 'Missing directional/adverse ratio metric.');
  mustInclude('Directional Sigma Units', 'Missing directional sigma-normalized metric.');
  mustInclude('Adverse Sigma Units', 'Missing adverse sigma-normalized metric.');
});

test('ranges page includes edge stability diagnostics', () => {
  mustInclude('type EdgeStabilitySummary', 'Missing edge stability summary type.');
  mustInclude('function getEdgeStabilitySummarySql', 'Missing edge stability summary SQL helper.');
  mustInclude('Edge Stability', 'Missing edge stability panel.');
  mustInclude('Win-Rate Z-Score', 'Missing edge stability z-score metric.');
  mustInclude('Ruin Proxy (10R/20d)', 'Missing edge stability ruin-proxy metric.');
  mustInclude('Max Drawdown', 'Missing max drawdown metric.');
});

test('ranges page includes first-boundary by-performance diagnostics', () => {
  mustInclude('type BoundaryPerformanceSummary', 'Missing boundary performance summary type.');
  mustInclude('function getBoundaryPerformanceSummarySql', 'Missing boundary performance summary SQL helper.');
  mustInclude('function getBoundaryPerformanceByBoundarySql', 'Missing boundary performance by-boundary SQL helper.');
  mustInclude('By Performance', 'Missing by-performance panel title.');
  mustInclude('First Boundary Broken', 'Missing first-boundary-broken context table.');
});
