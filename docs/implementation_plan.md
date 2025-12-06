# Phase 4: Journal Management & Trade History

## Goal Description
Implement full support for multiple Trading Accounts and Strategies, and provide a dedicated UI to manage them and view trade history. This moves the app from a simple "trade placer" to a "trading journal".

## User Review Required
> [!IMPORTANT]
> This requires a Database Schema update. We will add `Account` and `Strategy` models and link `Trade` to them. Existing simulated trades might need a default account.

## Proposed Changes

### Database Schema (`web/prisma/schema.prisma`)
- **[NEW] Model `Account`**: `id`, `name`, `currency`, `balance`, `isDefault`.
- **[NEW] Model `Strategy`**: `id`, `name`, `description`, `color`.
- **[MODIFY] Model `Trade`**: Add relations `account Account`, `strategy Strategy?`.

### Backend (`web/actions/`)
#### [NEW] [journal-actions.ts](file:///c:/Users/vinay/tvDownloadOHLC/web/actions/journal-actions.ts)
- `getAccounts()`, `createAccount()`, `updateAccount()`, `deleteAccount()`
- `getStrategies()`, `createStrategy()`, `updateStrategy()`

#### [MODIFY] [trade-actions.ts](file:///c:/Users/vinay/tvDownloadOHLC/web/actions/trade-actions.ts)
- Update `createTrade` to accept `accountId` and `strategyId`.

### Frontend Logic
#### [MODIFY] [trading-context.tsx](file:///c:/Users/vinay/tvDownloadOHLC/web/context/trading-context.tsx)
- Fetch accounts/strategies on mount.
- State for `activeAccount` and `activeStrategy`.
- Helper `createAccount`, `setCurrentAccount`.

### UI Components
#### [NEW] [account-manager-dialog.tsx](file:///c:/Users/vinay/tvDownloadOHLC/web/components/journal/account-manager-dialog.tsx)
- Modal to list, add, edit, and delete trading accounts.

#### [NEW] [journal-panel.tsx](file:///c:/Users/vinay/tvDownloadOHLC/web/components/journal/journal-panel.tsx)
- Bottom sheet/panel to display Trade History.
- Sortable table of trades (Date, Ticker, Type, P&L).

#### [MODIFY] [top-toolbar.tsx](file:///c:/Users/vinay/tvDownloadOHLC/web/components/top-toolbar.tsx)
- Connect dropdowns to real context data.
- Trigger `AccountManagerDialog`.

## Verification Plan
1. **Schema Migration**: Verify DB updates without data loss (or clean reset).
2. **Account Creation**: Create "Evaluation Account" and ensure it appears in dropdown.
3. **Trade Linking**: Place a trade, verify it saves with the correct `accountId`.
4. **History**: Open Journal Panel and verify the new trade appears there.
