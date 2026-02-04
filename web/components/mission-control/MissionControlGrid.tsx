/**
 * Mission Control Grid
 * 
 * Bento grid layout for dashboard panels.
 */

'use client';

import { getEnabledPanels, getPanelColSpan } from '@/config/panels';
import type { MissionControlSummary } from '@/lib/mission-control/service';
import { Skeleton } from '../ui/skeleton';
import { EMAZonePanel } from './panels/EMAZonePanel';
import { PremiumDiscountPanel } from './panels/PremiumDiscountPanel';
import { DistroPanel } from './panels/DistroPanel';
import { RegimeStreakPanel } from './panels/RegimeStreakPanel';
import { CandleSciencePanel } from './panels/CandleSciencePanel';
import { MODLODPanel } from './panels/MODLODPanel';
import { EconomicCalendarPanel } from './panels/EconomicCalendarPanel';
import { HTFTrinityPanel } from './panels/HTFTrinityPanel';
import { WarGamePanel } from './panels/WarGamePanel';
import { NarrativePanel } from './panels/NarrativePanel';

interface MissionControlGridProps {
    ticker: string;
    data: MissionControlSummary | undefined;
    isLoading: boolean;
    isSnapshotMode: boolean;
}

import { BasePanel } from './BasePanel';

export function MissionControlGrid({
    ticker,
    data,
    isLoading,
    isSnapshotMode,
}: MissionControlGridProps) {
    const panels = getEnabledPanels();

    if (isLoading) {
        return (
            <div className="grid grid-cols-1 gap-4 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
                {panels.map((panel) => (
                    <BasePanel
                        key={panel.id}
                        title={panel.displayName}
                        description={panel.description}
                        colSpan={getPanelColSpan(panel.size)}
                        isSnapshotMode={isSnapshotMode}
                    >
                        <div className="space-y-4">
                            <Skeleton className="h-8 w-1/3" />
                            <Skeleton className="h-32 w-full" />
                        </div>
                    </BasePanel>
                ))}
            </div>
        );
    }

    // Render panel content based on panel ID
    const renderPanelContent = (panelId: string) => {
        if (!data) return <div className="text-sm text-muted-foreground">No data</div>;

        switch (panelId) {
            case 'htfTrinity':
                return <HTFTrinityPanel data={data.panels.htfTrinity} isLoading={isLoading} />;

            case 'warGame':
                return <WarGamePanel data={data.panels.warGame} isLoading={isLoading} />;

            case 'emaZones':
                return <EMAZonePanel data={data.panels.emaZones} isLoading={isLoading} />;

            case 'premiumDiscount':
                return <PremiumDiscountPanel data={data.panels.premiumDiscount} isLoading={isLoading} />;

            case 'distro':
                return <DistroPanel data={data.panels.distro} isLoading={isLoading} />;

            case 'regimeStreak':
                return <RegimeStreakPanel data={data.panels.regimeStreak} isLoading={isLoading} />;

            case 'candleScience':
                return <CandleSciencePanel data={data.panels.candleScience} isLoading={isLoading} />;

            case 'modLod':
                return <MODLODPanel data={data.panels.modLod} isLoading={isLoading} />;

            case 'economicCalendar':
                return <EconomicCalendarPanel data={data.panels.economicCalendar} isLoading={isLoading} />;

            case 'narrative':
                return <NarrativePanel data={data.panels.narrative} isLoading={isLoading} />;

            default:
                return (
                    <div className="flex h-32 items-center justify-center text-sm text-muted-foreground">
                        {panelId} panel - Coming soon
                    </div>
                );
        }
    };

    return (
        <div className="grid grid-cols-1 gap-4 auto-rows-min md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
            {panels.map((panel) => (
                <BasePanel
                    key={panel.id}
                    title={panel.displayName}
                    description={panel.description}
                    colSpan={getPanelColSpan(panel.size)}
                    isSnapshotMode={isSnapshotMode}
                >
                    {renderPanelContent(panel.id)}
                </BasePanel>
            ))}
        </div>
    );
}
