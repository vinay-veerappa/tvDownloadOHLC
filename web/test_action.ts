import { getLiveChartData } from "./actions/get-live-chart";

async function main() {
    const res = await getLiveChartData("/NQ", "1", undefined, 180000);
    console.log("Success:", res.success, "Candles count:", res.data?.candles?.length);
}
main();
