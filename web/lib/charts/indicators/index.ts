import { ChartIndicator } from "./types";
import { SMAIndicator } from "./sma";
import { EMAIndicator } from "./ema";
import { VWAPIndicator } from "./vwap";
import { RSIIndicator } from "./rsi";
import { MACDIndicator } from "./macd";

export const INDICATOR_REGISTRY: Record<string, ChartIndicator> = {
    'sma': SMAIndicator,
    'ema': EMAIndicator,
    'vwap': VWAPIndicator,
    'rsi': RSIIndicator,
    'macd': MACDIndicator,
};

export * from './types';
