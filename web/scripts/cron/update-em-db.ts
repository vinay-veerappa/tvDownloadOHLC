
import { getExpectedMoveData } from '../../actions/get-expected-move';
import { DEFAULT_WATCHLIST } from '../../lib/watchlist-constants';

async function main() {
    console.log(`[${new Date().toISOString()}] Starting Scheduled Expected Move Update...`);

    // Ensure we have a list of tickers
    const tickers = DEFAULT_WATCHLIST;
    console.log(`Updating ${tickers.length} tickers: ${tickers.join(', ')}`);

    // Force Refresh (refresh=true)
    const result = await getExpectedMoveData(tickers, true);

    if (result.success) {
        console.log(`[SUCCESS] Updated ${result.data?.length} tickers.`);
    } else {
        console.error(`[ERROR] Update Failed: ${result.error}`);
        process.exit(1);
    }
}

main().catch(err => {
    console.error('Unhandled Error:', err);
    process.exit(1);
});
