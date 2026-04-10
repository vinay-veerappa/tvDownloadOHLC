import { GET } from '@/app/api/economic-events/coverage/route';

async function main() {
  const thresholdDays = Number(process.env.ECON_GAP_THRESHOLD_DAYS ?? '14');
  const strict = (process.env.ECON_COVERAGE_STRICT ?? '0') === '1';
  const req = new Request(`http://localhost/api/economic-events/coverage?thresholdDays=${thresholdDays}`);
  const res = await GET(req);
  const payload = await res.json() as any;

  if (!payload?.success) {
    console.error('Coverage check failed:', payload);
    process.exit(1);
  }

  const summary = payload.summary ?? {};
  const topGap = Array.isArray(payload.gaps) && payload.gaps.length > 0 ? payload.gaps[0] : null;

  console.log('Economic Events Coverage Summary');
  console.log(JSON.stringify(summary, null, 2));

  if (topGap) {
    console.log('Top Gap:', JSON.stringify(topGap));
  }

  const threshold = Number(summary.thresholdDays ?? thresholdDays);
  const gapDays = Number(topGap?.days ?? 0);
  if (gapDays >= threshold) {
    const message = `Gap threshold breached: ${gapDays} days >= ${threshold} days`;
    if (strict) {
      console.error(message);
      process.exit(2);
    }
    console.warn(message);
  }
}

main().catch((err) => {
  console.error('Coverage check error:', err);
  process.exit(1);
});
