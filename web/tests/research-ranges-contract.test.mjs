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
