import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { ProcessDeltaScorecard } from './ProcessDeltaScorecard';
import { ReviewQueuePanel } from './ReviewQueuePanel';
import { PracticeTerminal } from './PracticeTerminal';
import { GovernancePanel } from './GovernancePanel';

export const metadata = {
  title: 'Trading Brain · Governance Dashboard',
};

export default function TradingBrainDashboardPage() {
  return (
    <div className="container mx-auto py-6 space-y-4">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">Trading Second Brain</h1>
        <p className="text-sm text-muted-foreground">
          Canonical evidence ledger: process reconciliation, review queues, deliberate practice, and model governance.
          All data flows through the python web bridge — compliance logic is never reimplemented client-side.
        </p>
      </div>
      <Tabs defaultValue="process-delta" className="space-y-4">
        <TabsList>
          <TabsTrigger value="process-delta">Process Delta</TabsTrigger>
          <TabsTrigger value="practice">Practice</TabsTrigger>
          <TabsTrigger value="governance">Governance</TabsTrigger>
          <TabsTrigger value="review">Review Queue</TabsTrigger>
        </TabsList>
        <TabsContent value="process-delta">
          <ProcessDeltaScorecard />
        </TabsContent>
        <TabsContent value="practice">
          <PracticeTerminal />
        </TabsContent>
        <TabsContent value="governance">
          <GovernancePanel />
        </TabsContent>
        <TabsContent value="review">
          <ReviewQueuePanel />
        </TabsContent>
      </Tabs>
    </div>
  );
}