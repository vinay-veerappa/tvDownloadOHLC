"use client";

import React from 'react';

interface HighlightNarrativeProps {
  text: string | string[];
  ticker?: string;
  spot?: number;
}

/**
 * Professional Narrative Highlighter
 * Automatically detects and styles prices, percentages, tickers, and key trading levels.
 */
export const HighlightNarrative = ({ text, ticker = "", spot = 0 }: HighlightNarrativeProps) => {
  if (!text) return null;
  
  const rawStr = Array.isArray(text) ? text.join(" ") : String(text);
  const processed = rawStr
    .replaceAll("{ticker}", ticker)
    .replaceAll("{spot}", spot?.toLocaleString() || "");

  // Regex to capture:
  // 1. Decimals/Prices: (\d+\.?\d*%?)
  // 2. Caps Tickers/Keywords: ([A-Z]{2,}|CALL|PUT|GEX|WALL|MAGNET|FLIP|EM)
  const parts = processed.split(/(\d+\.?\d*%?|\/?[A-Z]{2,}|CALL|PUT|GEX|WALL|MAGNET|FLIP|EM)/g);

  return (
    <span className="leading-relaxed">
      {parts.map((part, i) => {
        // Style numbers/percentages
        if (/^\d+\.?\d*%?$/.test(part)) {
          return (
            <span key={i} className="text-emerald-400 font-mono font-bold mx-0.5">
              {part}
            </span>
          );
        }
        
        // Style keywords and tickers
        if (/^(\/?[A-Z]{2,}|CALL|PUT|GEX|WALL|MAGNET|FLIP|EM)$/.test(part)) {
          return (
            <span 
              key={i} 
              className="text-white font-black tracking-widest text-[0.75em] px-1.5 py-0.5 bg-white/10 rounded-md mx-1 border border-white/5"
            >
              {part}
            </span>
          );
        }
        
        return <span key={i}>{part}</span>;
      })}
    </span>
  );
};
