'use client';
import React, { useState, useEffect } from 'react';
import dynamic from 'next/dynamic';
import OrderEntry from '@/components/OrderEntry';
import OrderHistory from '@/components/OrderHistory';
import Navbar from '@/components/Navbar';
import { useMarketStore } from '@/store/useMarketStore';

// @ts-ignore - Type resolution issue with Next.js
import {
  Responsive,
  WidthProvider,
  Layout,
  ResponsiveLayouts as Layouts,
} from 'react-grid-layout/legacy';
import 'react-grid-layout/css/styles.css';
import 'react-resizable/css/styles.css';
import { GripHorizontal } from 'lucide-react';

const ResponsiveGridLayout = WidthProvider(Responsive);

// Disable SSR for TradingView chart as it requires window object
const TVChart = dynamic(() => import('@/components/TVChart'), {
  ssr: false,
  loading: () => (
    <div className="w-full h-full rounded-lg border border-zinc-800 bg-zinc-900 flex items-center justify-center">
      <span className="text-zinc-500 text-sm animate-pulse">Loading chart...</span>
    </div>
  ),
});

const DEFAULT_LAYOUT: Layout[] = [
  { i: 'chart', x: 0, y: 0, w: 9, h: 14, minW: 4, minH: 8 },
  { i: 'order-entry', x: 9, y: 0, w: 3, h: 14, minW: 2, minH: 7 },
  { i: 'order-history', x: 0, y: 14, w: 12, h: 10, minW: 4, minH: 5 },
];

export default function Dashboard() {
  const hasHydrated = useMarketStore((s) => s._hasHydrated);
  const [layouts, setLayouts] = useState<Layouts>({ lg: DEFAULT_LAYOUT });
  const [mounted, setMounted] = useState(false);

  useEffect(() => {
    setMounted(true);
    const saved = localStorage.getItem('dashboard-layouts');
    if (saved) {
      try {
        setLayouts(JSON.parse(saved));
      } catch (e) {
        console.error('Failed to parse layouts', e);
      }
    }
  }, []);

  const onLayoutChange = (currentLayout: Layout[], allLayouts: Layouts) => {
    setLayouts(allLayouts);
    localStorage.setItem('dashboard-layouts', JSON.stringify(allLayouts));
  };

  // Prevent flash: show skeleton until Zustand has loaded persisted state from localStorage
  if (!hasHydrated || !mounted) {
    return (
      <div className="h-screen w-screen overflow-hidden bg-black text-zinc-100 font-sans flex items-center justify-center">
        <span className="text-zinc-500 text-sm animate-pulse">Loading...</span>
      </div>
    );
  }

  return (
    <div className="min-h-screen w-full bg-black text-zinc-100 font-sans flex flex-col">
      {/* Header */}
      <div className="shrink-0 pt-4 px-4 pb-2">
        <Navbar />
      </div>

      {/* Main Grid */}
      <div className="flex-1 w-full p-2">
        <ResponsiveGridLayout
          className="layout"
          layouts={layouts}
          breakpoints={{ lg: 1200, md: 996, sm: 768, xs: 480, xxs: 0 }}
          cols={{ lg: 12, md: 10, sm: 6, xs: 4, xxs: 2 }}
          rowHeight={40}
          onLayoutChange={onLayoutChange}
          draggableHandle=".drag-handle"
          margin={[16, 16]}
        >
          <div
            key="chart"
            data-grid={{ minW: 4, minH: 8 }}
            className="flex flex-col bg-zinc-900 rounded-lg border border-zinc-800 overflow-hidden"
          >
            <div className="drag-handle h-6 bg-zinc-800/50 hover:bg-zinc-800 flex items-center justify-center cursor-move transition-colors shrink-0">
              <GripHorizontal className="w-4 h-4 text-zinc-500 pointer-events-none" />
            </div>
            <div className="flex-1 min-h-0 relative">
              <TVChart theme="dark" />
            </div>
          </div>

          <div
            key="order-entry"
            data-grid={{ minW: 2, minH: 7 }}
            className="flex flex-col bg-zinc-900 rounded-lg border border-zinc-800 overflow-hidden"
          >
            <div className="drag-handle h-6 bg-zinc-800/50 hover:bg-zinc-800 flex items-center justify-center cursor-move transition-colors shrink-0">
              <GripHorizontal className="w-4 h-4 text-zinc-500 pointer-events-none" />
            </div>
            <div className="flex-1 min-h-0 relative">
              <OrderEntry />
            </div>
          </div>

          <div
            key="order-history"
            data-grid={{ minW: 4, minH: 5 }}
            className="flex flex-col bg-zinc-900 rounded-lg border border-zinc-800 overflow-hidden"
          >
            <div className="drag-handle h-6 bg-zinc-800/50 hover:bg-zinc-800 flex items-center justify-center cursor-move transition-colors shrink-0">
              <GripHorizontal className="w-4 h-4 text-zinc-500 pointer-events-none" />
            </div>
            <div className="flex-1 min-h-0 relative overflow-hidden">
              <OrderHistory />
            </div>
          </div>
        </ResponsiveGridLayout>
      </div>
    </div>
  );
}
