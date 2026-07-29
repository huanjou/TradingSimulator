'use client';
import React, { useState, useEffect } from 'react';
import dynamic from 'next/dynamic';
import OrderEntry from '@/components/OrderEntry';
import OrderHistory from '@/components/OrderHistory';
import Navbar from '@/components/Navbar';
import { useMarketStore } from '@/store/useMarketStore';
import { useSearchParams, useRouter } from 'next/navigation';

// @ts-ignore - Type resolution issue with Next.js
import {
  Responsive,
  WidthProvider,
  Layout,
  LayoutItem,
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

const generateDefaultLayout = (): LayoutItem[] => {
  if (typeof window === 'undefined') {
    return [
      { i: 'chart', x: 0, y: 0, w: 12, h: 16, minW: 4, minH: 6 },
      { i: 'order-history', x: 0, y: 16, w: 10, h: 7, minW: 4, minH: 5 },
      { i: 'order-entry', x: 10, y: 16, w: 2, h: 7, minW: 2, minH: 7 },
    ];
  }

  // Calculate available rows to fit the screen without scrolling
  // Offsets: Navbar (~64px) + Padding (~24px) + Container margins (~16px) = ~104px
  // We subtract 135px to mathematically guarantee that grid rows never snap perfectly to
  // the edge of the window in a way that causes a 1px border subpixel overflow scrollbar.
  const availableHeight = window.innerHeight - 135;

  // Each row is 40px + 16px margin = 56px
  const totalRows = Math.floor((availableHeight + 16) / 56);

  const bottomRows = 6;
  const chartRows = Math.max(6, totalRows - bottomRows);

  return [
    { i: 'chart', x: 0, y: 0, w: 12, h: chartRows, minW: 4, minH: 6 },
    { i: 'order-history', x: 0, y: chartRows, w: 10, h: bottomRows, minW: 4, minH: 5 },
    { i: 'order-entry', x: 10, y: chartRows, w: 2, h: bottomRows, minW: 2, minH: 6 },
  ];
};

export default function Dashboard() {
  const hasHydrated = useMarketStore((s) => s._hasHydrated);
  const layoutResetTrigger = useMarketStore((s) => s.layoutResetTrigger);
  const setSymbol = useMarketStore((s) => s.setSymbol);
  const currentSymbol = useMarketStore((s) => s.symbol);

  const [layouts, setLayouts] = useState<Layouts>({ lg: [] }); // Init empty, set in useEffect
  const [mounted, setMounted] = useState(false);

  const searchParams = useSearchParams();
  const router = useRouter();

  useEffect(() => {
    // TradingView's embed script reads ?symbol= from the page URL and
    // overrides the widget config.  We use ?market= instead so TV never
    // sees our param.  If someone arrives with the old ?symbol= link we
    // migrate them silently.
    const oldParam = searchParams.get('symbol');
    const newParam = searchParams.get('market');
    const urlSymbol = newParam || oldParam;

    if (urlSymbol && urlSymbol !== currentSymbol) {
      setSymbol(urlSymbol);
    }

    // Strip ?symbol= from URL so TradingView cannot hijack it
    if (oldParam) {
      router.replace(urlSymbol ? `/?market=${urlSymbol}` : '/');
    }
  }, [searchParams, currentSymbol, setSymbol, router]);

  useEffect(() => {
    setMounted(true);
    const saved = localStorage.getItem('dashboard-layouts-v8');
    if (saved) {
      try {
        setLayouts(JSON.parse(saved));
      } catch (e) {
        console.error('Failed to parse layouts', e);
        setLayouts({ lg: generateDefaultLayout() });
      }
    } else {
      setLayouts({ lg: generateDefaultLayout() });
    }
  }, []);

  useEffect(() => {
    if (layoutResetTrigger > 0) {
      const defaultLayouts = { lg: generateDefaultLayout() };
      setLayouts(defaultLayouts);
      localStorage.setItem('dashboard-layouts-v8', JSON.stringify(defaultLayouts));
    }
  }, [layoutResetTrigger]);

  const onLayoutChange = (currentLayout: Layout, allLayouts: Layouts) => {
    setLayouts(allLayouts);
    localStorage.setItem('dashboard-layouts-v8', JSON.stringify(allLayouts));
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
            <div
              className="drag-handle h-6 bg-zinc-800/50 hover:bg-zinc-800 flex items-center justify-center cursor-move transition-colors shrink-0"
              style={{ touchAction: 'none' }}
            >
              <GripHorizontal className="w-4 h-4 text-zinc-500 pointer-events-none" />
            </div>
            <div className="flex-1 min-h-0 relative">
              <TVChart theme="dark" />
            </div>
          </div>

          <div
            key="order-entry"
            data-grid={{ minW: 2, minH: 6 }}
            className="flex flex-col bg-zinc-900 rounded-lg border border-zinc-800 overflow-hidden"
          >
            <div
              className="drag-handle h-6 bg-zinc-800/50 hover:bg-zinc-800 flex items-center justify-center cursor-move transition-colors shrink-0"
              style={{ touchAction: 'none' }}
            >
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
            <div
              className="drag-handle h-6 bg-zinc-800/50 hover:bg-zinc-800 flex items-center justify-center cursor-move transition-colors shrink-0"
              style={{ touchAction: 'none' }}
            >
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
