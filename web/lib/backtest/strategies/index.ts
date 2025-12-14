
import { Strategy } from "../types"
import { SmaCrossoverStrategy } from "./sma-crossover"
import { Nq1MinStrategy } from "./nq-1min-strategy"

export const STRATEGIES: Record<string, Strategy> = {
    "SMA_CROSSOVER": new SmaCrossoverStrategy(),
    "NQ_1MIN": new Nq1MinStrategy()
}
