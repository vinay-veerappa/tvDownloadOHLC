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
        const message = `**Mission Control Snapshot: ${ticker}**
Bias: ${summary.bias}
HTF Trinity: ${summary.panels.htfTrinity?.trinity_bias || 'N/A'}
MOD/LOD Mode: ${summary.panels.modLod?.hod_mode || 'N/A'} / ${summary.panels.modLod?.lod_mode || 'N/A'}`;

        // 3. Notify Discord (using the python script in background)
        try {
            // Use absolute path for safety if possible, or relative to root
            const scriptPath = path.join(process.cwd(), '..', 'scripts', 'utils', 'discord_notify.py');
            await execAsync(`python "${scriptPath}" --channel alerts --message "${message}"`);
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
