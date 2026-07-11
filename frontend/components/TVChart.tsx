'use client';
import React, { useEffect, useRef, memo, useState } from 'react';
import { createChart, ColorType, IChartApi, ISeriesApi } from 'lightweight-charts';
import axios from 'axios';

interface TVChartProps {
  symbol?: string; // e.g. "BINANCE:BTCUSD" or "BTC/USD"
  theme?: 'light' | 'dark';
  currentTrade?: { price: number; timestamp: string } | null;
}

const TVChart: React.FC<TVChartProps> = ({ symbol = 'BTC/USD', theme = 'dark', currentTrade }) => {
  const chartContainerRef = useRef<HTMLDivElement>(null);
  const chartRef = useRef<IChartApi | null>(null);
  const seriesRef = useRef<ISeriesApi<'Candlestick'> | null>(null);
  const [loading, setLoading] = useState(true);

  // Convert symbol formats to Binance format (e.g. BTC/USD -> BTCUSDT, BINANCE:BTCUSD -> BTCUSDT)
  const getBinanceSymbol = (sym: string) => {
    let clean = sym.replace('BINANCE:', '').replace('/', '');
    if (clean.endsWith('USD')) {
      clean = clean.slice(0, -3) + 'USDT';
    }
    return clean;
  };

  useEffect(() => {
    if (!chartContainerRef.current) return;

    const handleResize = () => {
      if (chartRef.current && chartContainerRef.current) {
        chartRef.current.applyOptions({
          width: chartContainerRef.current.clientWidth,
          height: chartContainerRef.current.clientHeight,
        });
      }
    };

    const chart = createChart(chartContainerRef.current, {
      layout: {
        background: { type: ColorType.Solid, color: theme === 'dark' ? '#18181b' : '#ffffff' }, // zinc-900
        textColor: theme === 'dark' ? '#a1a1aa' : '#3f3f46', // zinc-400
      },
      grid: {
        vertLines: { color: theme === 'dark' ? '#27272a' : '#e4e4e7' }, // zinc-800
        horzLines: { color: theme === 'dark' ? '#27272a' : '#e4e4e7' },
      },
      crosshair: {
        mode: 0,
      },
      rightPriceScale: {
        borderColor: theme === 'dark' ? '#27272a' : '#e4e4e7',
      },
      timeScale: {
        borderColor: theme === 'dark' ? '#27272a' : '#e4e4e7',
        timeVisible: true,
        secondsVisible: false,
      },
      width: chartContainerRef.current.clientWidth,
      height: chartContainerRef.current.clientHeight,
    });

    chartRef.current = chart;

    const candlestickSeries = chart.addCandlestickSeries({
      upColor: '#34d399', // emerald-400
      downColor: '#fb7185', // rose-400
      borderVisible: false,
      wickUpColor: '#34d399',
      wickDownColor: '#fb7185',
    });

    seriesRef.current = candlestickSeries;

    window.addEventListener('resize', handleResize);

    // Fetch initial data
    const fetchKlines = async () => {
      setLoading(true);
      try {
        const binanceSym = getBinanceSymbol(symbol);
        const res = await axios.get(
          `https://api.binance.com/api/v3/klines?symbol=${binanceSym}&interval=1m&limit=500`,
        );
        const data = res.data.map((d: any) => ({
          time: d[0] / 1000,
          open: parseFloat(d[1]),
          high: parseFloat(d[2]),
          low: parseFloat(d[3]),
          close: parseFloat(d[4]),
        }));
        candlestickSeries.setData(data);
      } catch (err) {
        console.error('Failed to load chart data:', err);
      } finally {
        setLoading(false);
      }
    };

    fetchKlines();

    return () => {
      window.removeEventListener('resize', handleResize);
      chart.remove();
    };
  }, [symbol, theme]);

  // Handle incoming real-time trades
  useEffect(() => {
    if (currentTrade && seriesRef.current) {
      const ts = new Date(currentTrade.timestamp).getTime() / 1000;
      // In lightweight-charts, update replaces the candle for that timestamp.
      // We'll just fake an update to the current 1m candle.
      // A more robust implementation would fetch the current open/high/low/close,
      // but for MVP we just push the price to the current candle.
      const timeRounded = Math.floor(ts / 60) * 60; // 1m precision
      seriesRef.current.update({
        time: timeRounded as any,
        open: currentTrade.price,
        high: currentTrade.price,
        low: currentTrade.price,
        close: currentTrade.price,
      });
    }
  }, [currentTrade]);

  return (
    <div className="w-full h-full min-h-[400px] relative rounded-lg overflow-hidden border border-zinc-800 bg-zinc-900">
      {loading && (
        <div className="absolute inset-0 flex items-center justify-center bg-zinc-900/80 z-10">
          <div className="text-zinc-400 animate-pulse font-medium">Loading Chart...</div>
        </div>
      )}
      <div className="absolute top-4 left-4 z-10 pointer-events-none">
        <h2 className="text-zinc-100 font-bold text-lg drop-shadow-md">
          {symbol.replace('BINANCE:', '')}
        </h2>
      </div>
      <div ref={chartContainerRef} className="w-full h-full" />
    </div>
  );
};

export default memo(TVChart);
