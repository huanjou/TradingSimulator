'use client';
import React, { memo } from 'react';
import { AdvancedRealTimeChart } from 'react-ts-tradingview-widgets';

interface TVChartProps {
  symbol?: string; // e.g. "BINANCE:BTCUSD" or "BTC/USD"
  theme?: 'light' | 'dark';
  currentTrade?: { price: number; timestamp: string } | null;
}

const TVChart: React.FC<TVChartProps> = ({ symbol = 'BTC/USD', theme = 'dark', currentTrade }) => {
  // Convert symbol formats to Binance format for TradingView
  const getTradingViewSymbol = (sym: string) => {
    let clean = sym.replace('BINANCE:', '').replace('/', '');
    if (clean.endsWith('USD')) {
      clean = clean.slice(0, -3) + 'USDT';
    }
    return `BINANCE:${clean}`;
  };

  return (
    <div className="w-full h-full relative rounded-lg overflow-hidden border border-zinc-800 bg-zinc-900 min-h-0">
      <AdvancedRealTimeChart
        theme={theme}
        symbol={getTradingViewSymbol(symbol)}
        interval="1"
        timezone="Etc/UTC"
        style="1"
        locale="en"
        enable_publishing={false}
        hide_top_toolbar={false}
        hide_side_toolbar={false}
        hide_legend={false}
        save_image={false}
        container_id="tradingview_chart"
        autosize={true}
      />
    </div>
  );
};

export default memo(TVChart);
