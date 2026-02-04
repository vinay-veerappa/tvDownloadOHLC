import { MissionControlService } from './service';

async function test() {
    const ticker = 'NQ1';
    console.log(`Testing Mission Control Summary for ${ticker}...`);

    const service = new MissionControlService(ticker);
    try {
        const summary = await service.getSummary();
        console.log('--- Summary Header ---');
        console.log(`Ticker: ${summary.ticker}`);
        console.log(`Market State: ${summary.marketState}`);
        console.log(`Bias: ${summary.bias}`);
        console.log(`Daily EM: ${summary.dailyEM}`);
        console.log(`Fuel: ${summary.fuel}`);
        console.log('--- Panels Status ---');
        Object.keys(summary.panels).forEach(p => {
            console.log(`${p}: ${summary.panels[p as keyof typeof summary.panels] ? 'OK' : 'MISSING'}`);
        });

        if (summary.panels.economicCalendar) {
            console.log('--- Economic Calendar ---');
            summary.panels.economicCalendar.forEach((e: any) => {
                console.log(`[${e.impact}] ${e.datetime} - ${e.name}`);
            });
        }
    } catch (error) {
        console.error('Error testing summary:', error);
    }
}

test();
