import { NextResponse } from 'next/server';
import { MissionControlService } from '@/lib/mission-control/service';
import * as fs from 'fs';
import * as path from 'path';
import { exec } from 'child_process';
import { promisify } from 'util';

const execAsync = promisify(exec);

export async function POST(request: Request) {
    try {
        const { ticker } = await request.json();
        if (!ticker) return NextResponse.json({ error: 'Ticker required' }, { status: 400 });

        const service = new MissionControlService(ticker);
        const summary = await service.getSummary();

        // 1. Save to disk
        const snapshotDir = path.join(process.cwd(), '..', 'data', 'snapshots');
        if (!fs.existsSync(snapshotDir)) fs.mkdirSync(snapshotDir, { recursive: true });

        const filename = `${ticker}_${new Date().toISOString().replace(/[:.]/g, '-')}.json`;
        const filePath = path.join(snapshotDir, filename);
        fs.writeFileSync(filePath, JSON.stringify(summary, null, 2));

        // 2. Build Discord Message
        // 2. Build Discord Message
        const biasInfo = typeof summary.bias === 'string'
            ? summary.bias
            : `${summary.bias.bias} (${summary.bias.score.toFixed(0)}% Conviction)`;

        // Get Active War Game Scenario
        let warGameInfo = 'N/A';
        if (summary.panels.warGame && summary.panels.warGame.currentScenario) {
            const sc = summary.panels.warGame.scenarios.find((s: any) =>
                s.id.startsWith(summary.panels.warGame.currentScenario) &&
                (summary.panels.warGame.currentScenario === 'long' ? s.id === 'longTrue' : s.id === 'shortTrue')
            );
            // More robust: find the one with highest probability or just use the current group
            // Ideally use the Narrative logic, but for now simple output:
            warGameInfo = `${summary.panels.warGame.currentScenario.toUpperCase()} Bias (Overnight)`;
        }

        // Get Top Narratives
        let narrativeText = '';
        if (summary.panels.narrative && summary.panels.narrative.length > 0) {
            narrativeText = '\n\n**Mission Brief:**\n' +
                summary.panels.narrative
                    .slice(0, 3)
                    .map((n: any) => `- ${n.icon || '•'} **${n.title}**: ${n.content}`) // Simple bullet if icon missing
                    .join('\n');
        }

        const message = `**Mission Control Snapshot: ${ticker}**
Bias: ${biasInfo}
HTF Trinity: ${summary.panels.htfTrinity?.trinity_bias || 'N/A'}
War Game: ${warGameInfo}
Fuel: ${summary.fuel ? summary.fuel.toFixed(1) + '%' : 'N/A'}${narrativeText}`;

        // 3. Notify Discord (using the python script in background)
        try {
            // Write message to temp file to avoid CLI issues
            const tempMsgPath = path.join(snapshotDir, `${filename}.txt`);
            fs.writeFileSync(tempMsgPath, message);

            const scriptPath = path.join(process.cwd(), '..', 'scripts', 'utils', 'discord_notify.py');
            // Use --message-file argument and data_gap_reports channel
            await execAsync(`python "${scriptPath}" --channel data_gap_reports --message-file "${tempMsgPath}"`);

            // Clean up temp file
            fs.unlinkSync(tempMsgPath);
        } catch (discordError) {
            console.error('Discord notification failed:', discordError);
            // Don't fail the whole request if discord fails
        }

        return NextResponse.json({
            success: true,
            filePath,
            filename
        });
    } catch (error) {
        console.error('Snapshot error:', error);
        return NextResponse.json({ success: false, error: 'Failed to create snapshot' }, { status: 500 });
    }
}
