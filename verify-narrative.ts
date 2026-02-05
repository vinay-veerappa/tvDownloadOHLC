import { MissionControlService } from './web/lib/mission-control/service';

async function verify() {
    console.log("--- Verifying Narrative Synthesis ---");
    const ticker = "NQ1";
    const service = new MissionControlService(ticker);

    try {
        const summary = await service.getSummary();
        console.log("Ticker:", summary.ticker);
        console.log("Bias:", summary.bias.bias, "(Score:", summary.bias.score, ")");

        console.log("\n--- Narrative Feed Items ---");
        summary.panels.narrative.forEach((item, i) => {
            console.log(`[Item ${i + 1}] ${item.title} (${item.category}):`);
            console.log(`   ${item.content}`);
        });

        const story = summary.panels.narrative.find(n => n.title === 'Weekly Story');
        if (story) {
            console.log("\n✅ SUCCESS: Weekly Story found in Narrative Feed.");
            if (story.content.includes("NFP")) console.log("✅ SUCCESS: Story contains NFP context.");
            if (story.content.includes("EMA")) console.log("✅ SUCCESS: Story contains EMA context.");
        } else {
            console.warn("\n❌ FAILURE: Weekly Story missing from Narrative Feed.");
        }

    } catch (error) {
        console.error("Verification failed:", error);
    }
}

verify();
