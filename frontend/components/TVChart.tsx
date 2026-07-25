'use client';
import React, { memo } from 'react';
import { AdvancedRealTimeChart } from 'react-ts-tradingview-widgets';
import { useMarketStore } from '@/store/useMarketStore';

interface TVChartProps {
  theme?: 'light' | 'dark';
}

const TVChart: React.FC<TVChartProps> = ({ theme = 'dark' }) => {
  const symbol = useMarketStore((s) => s.symbol);

  // Convert symbol formats to Binance format for TradingView
  const getTradingViewSymbol = (sym: string) => {
    let clean = sym.replace('BINANCE:', '').replace('/', '');
    if (clean.endsWith('USD')) {
      clean = clean.slice(0, -3) + 'USDT';
    }
    return `BINANCE:${clean}`;
  };

  return (
    <div className="w-full h-full relative min-h-0">
      <AdvancedRealTimeChart
        key={symbol}
        theme={theme}
        symbol={getTradingViewSymbol(symbol)}
        interval="1"
        timezone="Etc/UTC"
        style="1"
        locale="en"
        enable_publishing={false}
        allow_symbol_change={false}
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
