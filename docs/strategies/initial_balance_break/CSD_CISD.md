In Inner Circle Trader (ICT) methodology, the **Change in State of Delivery (CSD / CISD)** is the defining algorithmic mechanism behind an **Order Block**.  
Unlike retail supply/demand zones or standard candlestick engulfing patterns, an ICT Order Block is **not** a volume cluster or a zone. It is anchored strictly to a single price point: the **Opening Price** of the candidate candle. The CSD marks the exact moment the Interbank Price Delivery Algorithm (IPDA) shifts its delivery mode from buy-side to sell-side (or vice versa).

## **1\. Bullish Order Block CSD Rules**

A Bullish Order Block forms when price delivery shifts from sell-side (bearish) to buy-side (bullish).

### **A. Identification (Candidate Candle)**

* **The Candidate**: The last down-close candle (or consecutive series of down-close candles) formed prior to an upward price run toward an established liquidity pool or higher timeframe (HTF) objective.  
* **Anchor Point**: The exact **Opening Price** of that candidate down-close candle.

### **B. Validation Rule (The CSD Trigger)**

* **Price Delivery Breach**: A Bullish CSD is triggered the moment price **trades up through the Opening Price** of the candidate down-close candle.  
* **Wick vs. Body Close**: Price **does not need to close above** the opening price to validate the Order Block. Merely trading through the opening price validates the CSD. However, a full candle body close above the opening price provides higher confirmation of a protected intraday swing low.

### **C. Order Flow & Range Sensitivity**

* **Discount Sensitivity**: Once validated, standard institutional order flow expects price to respect the **upper half** (discount sensitivity / upper quadrant) of the down-close candle's range.  
* **Forbidden Zone**: Candle bodies should **not** close in the lower half of the Order Block range. If candle bodies settle in the lower half, it signals underlying order flow weakness.

### **D. Inversion Rule**

* If price fails to hold the CSD Order Block and candle bodies close beneath the lower half, the setup inverts. The failed bullish OB becomes a **Bearish Inversion Order Block (or Breaker)**, shifting market directional probability to **\~85% bearish**.

## **2\. Bearish Order Block CSD Rules**

A Bearish Order Block forms when price delivery shifts from buy-side (bullish) to sell-side (bearish).

### **A. Identification (Candidate Candle)**

* **The Candidate**: The last up-close candle (or consecutive series of up-close candles) formed prior to a downward price run toward an established sellside liquidity pool.  
* **Anchor Point**: The exact **Opening Price** of that candidate up-close candle.

### **B. Validation Rule (The CSD Trigger)**

* **Price Delivery Breach**: A Bearish CSD is triggered the moment price **trades down through the Opening Price** of the candidate up-close candle.  
* **Wick vs. Body Close**: Price **does not need to close below** the opening price to validate the Order Block. The breach of the opening price instantly changes the state of delivery. A candle body close below confirms a protected swing high.

### **C. Order Flow & Range Sensitivity**

* **Premium Sensitivity**: Standard institutional order flow expects price to respect the **lower half** (premium sensitivity / lower quadrant) of the up-close candle's range.  
* **Forbidden Zone**: Candle bodies must **not** close in the upper half of the Bearish Order Block.

### **D. Inversion Rule**

* If price pushes back up through the Bearish Order Block and settles candle bodies above its upper half, the array inverts into a **Bullish Inversion Order Block**, flipping directional bias immediately.

## **3\. Intraday Validation & Execution Flow**

To trade a CSD effectively across lower timeframes (e.g., 1-minute, 3-minute, or 5-minute charts), you must bound the evaluation inside a structured time container and align it with higher timeframe premise.

**1.1. Establish HTF Narrative & Objective:**HTF Context.  
Identify a higher timeframe PD Array (such as a Daily Fair Value Gap, Volume Imbalance, or RTH Opening Range Gap Consequent Encroachment) to serve as the institutional draw on liquidity.

**2.2. Frame the Time Container:**Intraday Session.  
Restrict CSD evaluation strictly to specific session time windows (e.g., 9:30 AM – 10:30 AM RTH opening hour, or 7:40–8:10 AM / 9:50–10:10 AM Macro windows) to filter out false reversals.

**3.3. Mark the Opening Price:**CSD Anchor.  
Identify the exact Opening Price of the last opposing candle prior to the impulse move toward liquidity (the candidate OB candle).

**4.4. Confirm the CSD Breach:**Execution Trigger.  
Watch price trade through the candidate candle's opening price. This instant price breach confirms that IPDA has changed the state of price delivery.

**5.5. Execute on Retest / Quadrant Refinement:**Order Flow Entry.  
Enter on a retracement back to the candidate candle's opening price or its upper/lower 25% quadrant boundary. Position the stop loss beyond the Order Block extreme (the high/low wick of the candidate candle).

## **4\. Summary Matrix: Bullish vs. Bearish CSD**

| Parameter | Bullish Order Block CSD | Bearish Order Block CSD |
| :---- | :---- | :---- |
| **Candidate Candle** | Down-close candle(s) prior to rally | Up-close candle(s) prior to drop |
| **Critical Price Anchor** | **Opening Price** of down-close candle | **Opening Price** of up-close candle |
| **Trigger Condition** | Price trades **up through** Opening Price | Price trades **down through** Opening Price |
| **Body Close Requirement** | Not required to activate; confirms protected low | Not required to activate; confirms protected high |
| **Protected Range** | Upper half / Upper Quadrant (Discount) | Lower half / Lower Quadrant (Premium) |
| **Invalidation / Inversion** | Candle bodies close in lower half | Candle bodies close in upper half |

