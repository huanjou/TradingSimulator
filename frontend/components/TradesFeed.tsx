'use client';
import React, { useEffect, useState, useRef } from 'react';
import { format } from 'date-fns';

interface TradeEvent {
  event_type: string;
  symbol: string;
  price: number;
  timestamp: string;
}

interface TradesFeedProps {
  symbol: string;
  onTradeUpdate?: (trade: { price: number; timestamp: string }) => void;
}

export default function TradesFeed({ symbol, onTradeUpdate }: TradesFeedProps) {
  const [trades, setTrades] = useState<TradeEvent[]>([]);
  const eventSourceRef = useRef<EventSource | null>(null);

  useEffect(() => {
    // Close existing connection
    if (eventSourceRef.current) {
      eventSourceRef.current.close();
    }

    const url = `/api/v1/stream?symbol=${symbol}`;
    const sse = new EventSource(url);
    eventSourceRef.current = sse;

    sse.addEventListener('price', (e) => {
      try {
        const data = JSON.parse(e.data);
        if (data.symbol && data.bid_price !== undefined) {
          const tradePrice = (data.bid_price + data.ask_price) / 2;
          const tradeData = {
            event_type: 'trade',
            symbol: data.symbol,
            price: tradePrice,
            timestamp: data.timestamp || new Date().toISOString(),
          };

          setTrades((prev) => {
            const updated = [tradeData, ...prev].slice(0, 50); // Keep last 50
            return updated;
          });
          if (onTradeUpdate) {
            onTradeUpdate({ price: tradePrice, timestamp: tradeData.timestamp });
          }
        }
      } catch (err) {
        console.error('Failed to parse SSE data', err);
      }
    });

    sse.onerror = (error) => {
      console.error('SSE error', error);
      sse.close();
      // Simple reconnect logic could go here
      setTimeout(() => {
        // trigger reconnect if needed
      }, 5000);
    };

    return () => {
      sse.close();
    };
  }, [symbol]);

  return (
    <div className="bg-zinc-900 border border-zinc-800 rounded-lg p-4 h-full flex flex-col">
      <h2 className="text-zinc-100 font-semibold text-lg mb-4">Market Trades</h2>

      <div className="flex-1 overflow-auto pr-2">
        <table className="w-full text-sm text-left">
          <thead className="text-xs text-zinc-500 uppercase sticky top-0 bg-zinc-900 z-10">
            <tr>
              <th className="py-2 px-2 font-medium">Price</th>
              <th className="py-2 px-2 font-medium text-right">Time</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-zinc-800/30">
            {trades.length === 0 ? (
              <tr>
                <td colSpan={2} className="text-center py-8 text-zinc-600 italic">
                  Waiting for trades...
                </td>
              </tr>
            ) : (
              trades.map((trade, i) => {
                // simple color logic: compare to previous trade if exists
                const prevTrade = trades[i + 1];
                const color =
                  !prevTrade || trade.price >= prevTrade.price
                    ? 'text-emerald-400'
                    : 'text-rose-400';

                return (
                  <tr key={`${trade.timestamp}-${i}`} className="hover:bg-zinc-800/20">
                    <td className={`py-2 px-2 font-mono ${color}`}>${trade.price.toFixed(2)}</td>
                    <td className="py-2 px-2 text-zinc-500 text-right font-mono">
                      {format(new Date(trade.timestamp), 'HH:mm:ss')}
                    </td>
                  </tr>
                );
              })
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
