# Trading & Journaling System Requirements

## 1. Overview
The goal is to integrate a simulated trading environment directly into the chart interface that doubles as a trade journaling system. This allows users to "execute" trades on historical or replay data, capture the context, and tag them for analysis. Data is persisted to a local SQLite database via Server Actions.

## 2. Core Components

### A. Chart Trading Interface (The "Frontend")
Inspired by TradingView, this interface sits directly on the chart.

**1. Floating Buy/Sell Panel**
- **Location**: Top-left (configurable).
- **Elements**:
    - **Symbol/Status**: Current Ticker, Market Open/Closed status.
    - **Quantity Input**: Number of contracts/shares.
    - **Big Red "SELL" Button**: Displays current Bid price.
    - **Big Blue "BUY" Button**: Displays current Ask price.
    - **Spread Display**: Small text showing the spread.
- **Micro-interactions**: Hover effects, click animation, "Order Filled" toast notification.

**2. On-Chart Interactions**
- **Instant Orders**: One-click Buy/Sell at market.
- **Drag-and-Drop Orders**:
    - Right-click at price level -> "Buy Limit" / "Sell Stop".
    - Drag active order lines to modify price.
    - Click "X" on order line to cancel.
- **Position Visualization**:
    - Horizontal line showing Average Entry Price.
    - P&L Label (Floating next to price line).
    - P&L Label (Floating next to price line).
    - "Reverse" and "Close" buttons on the label.

**3. Advanced Order Controls (Phase 3)**
- **Order Types**: Market (default), Limit, Stop.
- **Bracket Orders (SL/TP)**:
    - Ability to set Stop Loss and Take Profit targets before entry.
    - **OCO (One-Cancels-Other)**: Auto-cancel the remaining leg when one side is filled.
- **Interactive Placement**:
    - Click on Price Panel (Buy/Sell Widget) to set Limit prices.
    - Click on Chart Price Scale to place pending orders.
    - Drag SL/TP lines on chart to modify.

### B. Journaling Information (The "Context")
Before or during trading, the user sets the context for the session.

**1. Trade Context Bar (or Sidebar Panel)**
- **Account Selector**: Choose simulated account (e.g., "$100k Challenge", "Testing Strat A").
- **Strategy Selector**: Dropdown to associate trades with a strategy (e.g., "Gap Fill", "Breakout").
- **Session Tags**: Global tags for the day (e.g., "High Volatility", "News Day").

**2. Trade Entry Modal (Optional/Configurable)**
- pop-up when taking a trade (if "One-Click" is off) to add specific notes or setup tags (e.g., "A+ Setup", "FOMO").

### C. Post-Trade & Analysis (The "Backend")
Features to record and review the activity.

**1. Account Management (Journal Tab)**
- **Create Account**: "Simulated $50k", "Live Account", etc.
- **Manage**: Edit name, Reset balance, Delete account.
- **Switching**: Select active account for the session.

**2. Trade Management**
- **List View**: Sortable table of all trades (Date, Ticker, P&L, Status).
- **Detail View**: Full page per trade including screenshots and notes.
- **Editing**: Update notes, add tags, fix execution errors.

**3. Automated Screenshots**
- **Trigger**: On Trade Open and Trade Close.
- **Scope**: Captures visible chart area, indicators, and current drawings.
- **Storage**: Linked to the Trade ID.

**2. P&L Dashboard**
- Real-time Session P&L in the sidebar.
- History list of executed trades.

## 3. Data Model

### Account
```typescript
interface JournalAccount {
    id: string;
    name: string;
    currency: string;
    initialBalance: number;
    currentBalance: number;
    metrics: { winRate: number, profitFactor: number };
}
```

### Strategy
```typescript
interface Strategy {
    id: string;
    name: string;
    description: string;
    tags: string[]; // Default tags
}
```

### Trade / Journal Entry
```typescript
interface TradeEntry {
    id: string;
    accountId: string;
    strategyId: string;
    symbol: string;
    direction: 'LONG' | 'SHORT';
    
    // Execution
    entryPrice: number;
    exitPrice: number;
    quantity: number;
    entryTime: number;
    exitTime: number;
    
    // Outcomes
    pnl: number;
    fees: number;
    
    // Metadata
    tags: string[];        // e.g., "Mistake", "Impulsive", "Good Mgmt"
    notes: string;
    screenshotUrls: {
        entry: string;
        exit: string;
    };
    
    status: 'OPEN' | 'CLOSED';
}
```

## 4. UI Requirements & Mockups

### Screen 1: The Chart with Trading Panel
### Screen 1: The Chart with Trading Panel
![Trading Interface Mockup](C:/Users/vinay/.gemini/antigravity/brain/e19d63fd-4820-451b-a83a-779ec1adca48/buy_sell_mockup_1764996375977.png)
*(Based on Implemented Redesign)*
- **Trading Panel**: Compact, dark-mode panel.
- **Top**: "MARKET" label and Quantity input.
- **Middle**: Large Red "SELL MKT" and Blue "BUY MKT" buttons showing Bid/Ask.
- **Bottom**: Active Position info (Direction, Qty) and Real-time P&L (Green/Red).
- **Chart Area**: Position line (Dashed) showing Entry Price and floating P&L label.

### Screen 2: Settings > Trading
*(Based on User Image 2)*
- **General**:
    - [x] Show Buy/Sell Buttons
    - [x] Instant Order Placement (One-click)
- **Appearance**:
    - [x] Show Executions (Arrows on chart)

### Screen 3: Journal Controls (Top Bar)
- **Location**: Top Navigation Bar (replacing unused placeholders).
- **Controls**:
    - **Account Selector**: Dropdown (e.g., "$100k Eval", "Personal").
    - **Strategy Selector**: Dropdown (e.g., "Gap Fill", "Momentum").
    - **Session P&L**: Green/Red text display (e.g., "+$450.00").
- **Note**: This keeps the trading context always visible and frees up the sidebar.


## 5. Implementation Roadmap
1.  **Architecture**: Use Server Actions (`createTrade`, `closeTrade`) + Prisma (SQLite) for persistence. Use React State for UI.
2.  **UI Components**: Build `BuySellPanel` with P&L display.
3.  **Chart Integration**: Use Lightweight Charts `PriceLine` for positions and markers for executions.
4.  **Advanced Logic (Phase 3)**: Implement Limit Orders, Brackets (SL/TP), and OCO logic.
5.  **Settings Module**: Add "Trading" tab to existing settings modal.
