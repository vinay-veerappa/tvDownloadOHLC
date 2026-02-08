# NQ Playbook — Mermaid Flowcharts

Use these diagrams in any markdown-compatible documentation, Notion, Obsidian, GitHub, etc.

---

## 1. Session Flow Overview

```mermaid
flowchart LR
    subgraph OVERNIGHT["🌙 OVERNIGHT"]
        A[/"ASIA<br/>19:30-02:30<br/>OBSERVE"/]
    end
    
    subgraph PREMARKET["🌅 PRE-MARKET"]
        L[/"LONDON<br/>02:30-08:00<br/>OBSERVE"/]
    end
    
    subgraph RTH["📈 REGULAR TRADING HOURS"]
        NY[/"NY AM<br/>09:30-12:00<br/>TRADE"/]
        LUNCH[/"LUNCH<br/>12:00-13:30<br/>MANAGE"/]
        PM[/"NY PM<br/>13:30-16:00<br/>MANAGE"/]
    end
    
    A -->|"Establish Range"| L
    L -->|"Manipulation Pattern"| NY
    NY -->|"Execute Reversal"| LUNCH
    LUNCH -->|"Track H/L"| PM
    PM -->|"Close 15:45"| END((EOD))
```

---

## 2. London Pattern Classification

```mermaid
flowchart TD
    START{{"London Session Ends<br/>What did London do?"}}
    
    START --> HIGH{"Swept Asia HIGH?"}
    
    HIGH -->|YES| BOTH1{"Also swept Asia LOW?"}
    HIGH -->|NO| LOW{"Swept Asia LOW?"}
    
    BOTH1 -->|YES| ENGULF["🟡 LONDON ENGULFS<br/>Both sides swept<br/>Volatile day ahead"]
    BOTH1 -->|NO| PUP["🔴 PARTIAL UP<br/>Bearish manipulation<br/>64% NY reverses down"]
    
    LOW -->|YES| PDOWN["🟢 PARTIAL DOWN<br/>Bullish manipulation<br/>64% NY reverses up"]
    LOW -->|NO| INSIDE["⚪ ASIA INSIDE<br/>No manipulation<br/>Skip day - no edge"]
    
    style PDOWN fill:#1a472a,stroke:#3fb950,color:#fff
    style PUP fill:#4a1c1c,stroke:#f85149,color:#fff
    style ENGULF fill:#3d2e00,stroke:#d29922,color:#fff
    style INSIDE fill:#21262d,stroke:#8b949e,color:#fff
```

---

## 3. NY AM Entry Decision Tree

```mermaid
flowchart TD
    OPEN{{"09:30 NY Opens<br/>Where vs London Mid?"}}
    
    OPEN -->|"ABOVE London Mid"| ABOVE["🟢 LONG BIAS<br/>Position signal: 78%"]
    OPEN -->|"BELOW London Mid"| BELOW["🔴 SHORT BIAS<br/>Position signal: 73%"]
    
    ABOVE --> CHECK_L{"London Pattern?"}
    BELOW --> CHECK_S{"London Pattern?"}
    
    CHECK_L -->|"Partial Down<br/>(Aligned)"| LONG_GO["✅ TAKE LONG<br/>84-88% reversal"]
    CHECK_L -->|"Partial Up<br/>(Conflict)"| LONG_SKIP["❌ SKIP<br/>49-56% only"]
    
    CHECK_S -->|"Partial Up<br/>(Aligned)"| SHORT_GO["✅ TAKE SHORT<br/>84-87% reversal"]
    CHECK_S -->|"Partial Down<br/>(Conflict)"| SHORT_SKIP["❌ SKIP<br/>49-56% only"]
    
    style LONG_GO fill:#1a472a,stroke:#3fb950,color:#fff
    style SHORT_GO fill:#1a472a,stroke:#3fb950,color:#fff
    style LONG_SKIP fill:#4a1c1c,stroke:#f85149,color:#fff
    style SHORT_SKIP fill:#4a1c1c,stroke:#f85149,color:#fff
```

---

## 4. 72-Scenario Matrix (Simplified)

```mermaid
flowchart TD
    subgraph BEST["🟢 BEST SETUPS (75%+)"]
        B1["Small Asia + Partial Down + Above Mid<br/>LONG: 88.6%"]
        B2["Small Asia + Partial Up + Below Mid<br/>SHORT: 87.5%"]
        B3["Any Asia + Aligned Pattern + Position<br/>84-86%"]
    end
    
    subgraph MEDIUM["🟡 MEDIUM SETUPS (60-75%)"]
        M1["Medium Asia + Aligned<br/>73.2%"]
        M2["Large Asia + Any Pattern<br/>61-68%"]
    end
    
    subgraph SKIP["🔴 SKIP SETUPS (<60%)"]
        S1["Misaligned: Bearish Manip + Above Mid<br/>49-56%"]
        S2["Misaligned: Bullish Manip + Below Mid<br/>49-56%"]
    end
    
    style BEST fill:#1a472a,stroke:#3fb950
    style MEDIUM fill:#3d2e00,stroke:#d29922
    style SKIP fill:#4a1c1c,stroke:#f85149
```

---

## 5. Gap Confluence Analysis

```mermaid
flowchart LR
    subgraph CHASING["🟢 GAP CHASING (+18% Edge)"]
        C1["London swept LOW<br/>+ Gap UP"] --> C1R["78.5% reversal up"]
        C2["London swept HIGH<br/>+ Gap DOWN"] --> C2R["76.2% reversal down"]
    end
    
    subgraph FADING["🟡 GAP FADING (Baseline)"]
        F1["London swept LOW<br/>+ Gap DOWN"] --> F1R["60.3% reversal"]
        F2["London swept HIGH<br/>+ Gap UP"] --> F2R["58.1% reversal"]
    end
    
    style CHASING fill:#1a472a,stroke:#3fb950
    style FADING fill:#3d2e00,stroke:#d29922
```

---

## 6. Reversal Timing Distribution

```mermaid
pie showData
    title "When Reversals Occur in NY AM"
    "09:30-10:00 (60.6%)" : 60.6
    "10:00-10:30 (20.2%)" : 20.2
    "10:30-11:00 (10.1%)" : 10.1
    "11:00-12:00 (9.1%)" : 9.1
```

---

## 7. PM Session Management

```mermaid
flowchart TD
    PM_START{{"13:30 PM Session<br/>Do you have a position?"}}
    
    PM_START -->|"YES - In profit"| HOLD["🟢 HOLD WITH BE STOP<br/>• Move stop to breakeven<br/>• Target: Lunch H/L<br/>• PM continues 52%"]
    
    PM_START -->|"NO - Flat"| FLAT["🟡 DO NOT INITIATE<br/>• PM is for managing<br/>• Edge significantly lower<br/>• Wait for tomorrow"]
    
    HOLD --> CONT{"PM Direction?"}
    CONT -->|"Continues AM (52%)"| WIN["Let runner run"]
    CONT -->|"Reverses AM (20-23%)"| BE["Stopped at breakeven"]
    CONT -->|"Chops (25-28%)"| CHOP["Exit at 15:45"]
    
    style HOLD fill:#1a472a,stroke:#3fb950,color:#fff
    style FLAT fill:#3d2e00,stroke:#d29922,color:#fff
```

---

## 8. CBDR Sigma Targets

```mermaid
flowchart LR
    subgraph BULL["🟢 BULLISH MANIPULATION<br/>(London swept Asia Low)"]
        direction TB
        B_NEG2["-2σ: 58.3%<br/>(Manipulation leg)"]
        B_NEG1["-1σ: 73.1%"]
        B_POS1["+1σ: 41.2%"]
        B_POS2["+2σ: 25.6%<br/>(Target)"]
    end
    
    subgraph BEAR["🔴 BEARISH MANIPULATION<br/>(London swept Asia High)"]
        direction TB
        S_POS2["+2σ: 56.8%<br/>(Manipulation leg)"]
        S_POS1["+1σ: 71.4%"]
        S_NEG1["-1σ: 43.7%"]
        S_NEG2["-2σ: 27.2%<br/>(Target)"]
    end
    
    style BULL fill:#1a472a,stroke:#3fb950
    style BEAR fill:#4a1c1c,stroke:#f85149
```

---

## 9. Complete Pre-Market Checklist

```mermaid
flowchart TD
    subgraph CHECKLIST["📋 MORNING CHECKLIST"]
        direction TB
        C1["1️⃣ Asia Range Size"]
        C2["2️⃣ London Pattern"]
        C3["3️⃣ Gap Direction"]
        C4["4️⃣ NY Open Position"]
        C5["5️⃣ Alignment Check"]
    end
    
    C1 --> C1A{"Size?"}
    C1A -->|"Small"| C1S["🟢 66.8% reversal"]
    C1A -->|"Medium"| C1M["🟡 60.6% reversal"]
    C1A -->|"Large"| C1L["🔴 54.0% reversal"]
    
    C2 --> C2A{"Pattern?"}
    C2A -->|"Partial Down"| C2D["Bullish bias"]
    C2A -->|"Partial Up"| C2U["Bearish bias"]
    C2A -->|"Engulfs"| C2E["Volatile"]
    
    C3 --> C3A{"Gap vs Sweep?"}
    C3A -->|"Chasing"| C3C["🟢 +18% edge"]
    C3A -->|"Fading"| C3F["🟡 Baseline"]
    
    C4 --> C4A{"vs London Mid?"}
    C4A -->|"Above"| C4U["Long bias 78%"]
    C4A -->|"Below"| C4D["Short bias 73%"]
    
    C5 --> C5A{"Pattern + Position?"}
    C5A -->|"ALIGNED"| TRADE["✅ TRADE 84-88%"]
    C5A -->|"CONFLICT"| SKIP["❌ SKIP 49-56%"]
    
    style TRADE fill:#1a472a,stroke:#3fb950,color:#fff
    style SKIP fill:#4a1c1c,stroke:#f85149,color:#fff
```

---

## 10. Asia Range Effect on Reversal

```mermaid
xychart-beta
    title "Reversal Rate by Asia Range Size (NQ)"
    x-axis ["Small (P0-25)", "Medium (P25-50)", "Med-Large (P50-75)", "Large (P75+)"]
    y-axis "Reversal %" 50 --> 70
    bar [66.8, 60.6, 58.2, 54.0]
```

---

## Usage Notes

### Rendering in Different Platforms

**GitHub/GitLab**: Native support - just paste the code blocks

**Notion**: Use `/mermaid` block and paste content

**Obsidian**: Native support with Mermaid plugin

**VS Code**: Install "Markdown Preview Mermaid Support" extension

**Confluence**: Use Mermaid macro

**Static Site Generators**: Most support Mermaid (Hugo, Jekyll, Docusaurus)

### Live Editor

Test and modify diagrams at: https://mermaid.live/

### Customization

Change colors by modifying the `style` lines:
```
style NODENAME fill:#hexcolor,stroke:#hexcolor,color:#textcolor
```

Color reference:
- Green (trade): `#1a472a` fill, `#3fb950` stroke
- Yellow (caution): `#3d2e00` fill, `#d29922` stroke  
- Red (skip): `#4a1c1c` fill, `#f85149` stroke
