'use client';
import React from 'react';
import dynamic from 'next/dynamic';
import OrderEntry from '@/components/OrderEntry';
import OrderHistory from '@/components/OrderHistory';
import TradesFeed from '@/components/TradesFeed';
import Navbar from '@/components/Navbar';
import { useMarketStore } from '@/store/useMarketStore';
import { Panel, Group, Separator } from 'react-resizable-panels';

// Disable SSR for TradingView chart as it requires window object
const TVChart = dynamic(() => import('@/components/TVChart'), {
  ssr: false,
  loading: () => (
    <div className="w-full h-full rounded-lg border border-zinc-800 bg-zinc-900 flex items-center justify-center">
      <span className="text-zinc-500 text-sm animate-pulse">Loading chart...</span>
    </div>
  ),
});

const ResizeHandle = ({
  className = '',
  orientation = 'horizontal',
}: {
  className?: string;
  orientation?: 'horizontal' | 'vertical';
}) => (
  <Separator
    className={`relative flex items-center justify-center bg-transparent group transition-colors ${
      orientation === 'horizontal'
        ? 'w-2 h-full mx-1 cursor-col-resize'
        : 'h-2 w-full my-1 cursor-row-resize'
    } ${className}`}
  >
    <div
      className={`z-10 flex items-center justify-center rounded-sm bg-zinc-800 group-hover:bg-emerald-500/50 transition-colors ${
        orientation === 'horizontal' ? 'h-8 w-1' : 'w-8 h-1'
      }`}
    />
  </Separator>
);

export default function Dashboard() {
  const hasHydrated = useMarketStore((s) => s._hasHydrated);

  // Prevent flash: show skeleton until Zustand has loaded persisted state from localStorage
  if (!hasHydrated) {
    return (
      <div className="h-screen w-screen overflow-hidden bg-black text-zinc-100 font-sans flex items-center justify-center">
        <span className="text-zinc-500 text-sm animate-pulse">Loading...</span>
      </div>
    );
  }

  return (
    <div className="h-screen w-screen overflow-hidden bg-black text-zinc-100 font-sans flex flex-col">
      {/* Header */}
      <div className="shrink-0 pt-4 px-4 pb-2">
        <Navbar />
      </div>

      {/* Main Grid */}
      <div className="flex-1 w-full p-4 pt-2 min-h-0">
        <Group orientation="horizontal" className="h-full w-full">
          {/* Left Column: Chart & Order History */}
          <Panel defaultSize={75} minSize={30} className="flex flex-col h-full">
            <Group orientation="vertical">
              <Panel defaultSize={70} minSize={20} className="h-full">
                <TVChart theme="dark" />
              </Panel>

              <ResizeHandle orientation="vertical" />

              <Panel
                defaultSize={30}
                minSize={15}
                className="h-full bg-zinc-900 rounded-lg border border-zinc-800 overflow-hidden"
              >
                <OrderHistory />
              </Panel>
            </Group>
          </Panel>

          <ResizeHandle orientation="horizontal" />

          {/* Right Column: Order Entry & Trades Feed */}
          <Panel defaultSize={25} minSize={20} className="flex flex-col h-full">
            <Group orientation="vertical">
              <Panel defaultSize={40} minSize={30} className="h-full">
                <OrderEntry />
              </Panel>

              <ResizeHandle orientation="vertical" />

              <Panel
                defaultSize={60}
                minSize={20}
                className="h-full bg-zinc-900 rounded-lg border border-zinc-800 overflow-hidden"
              >
                <TradesFeed />
              </Panel>
            </Group>
          </Panel>
        </Group>
      </div>
    </div>
  );
}
