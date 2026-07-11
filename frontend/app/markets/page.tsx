'use client';

import React, { useState, useEffect, useRef, useCallback } from 'react';
import Navbar from '@/components/Navbar';
import AuthScreen from '@/components/AuthScreen';
import { useAuthStore } from '@/store/useAuthStore';
import api from '@/lib/axios';
import { Search, Loader2 } from 'lucide-react';
import { useRouter } from 'next/navigation';

interface SymbolData {
  name: string;
  is_active: boolean;
}

export default function MarketsPage() {
  const { user } = useAuthStore();
  const [symbols, setSymbols] = useState<SymbolData[]>([]);
  const [prices, setPrices] = useState<Record<string, number>>({});
  const [loading, setLoading] = useState(false);
  const [hasMore, setHasMore] = useState(true);
  const [searchQuery, setSearchQuery] = useState('');

  const observer = useRef<IntersectionObserver | null>(null);
  const limit = 30;
  const router = useRouter();

  const fetchSymbols = async (offset: number, query: string, append: boolean) => {
    if (loading || (!hasMore && offset !== 0)) return;

    setLoading(true);
    try {
      const res = await api.get(`/api/v1/symbols/?q=${query}&limit=${limit}&offset=${offset}`);
      const newSymbols = res.data;

      if (newSymbols.length < limit) {
        setHasMore(false);
      } else {
        setHasMore(true);
      }

      setSymbols((prev) => (append ? [...prev, ...newSymbols] : newSymbols));
    } catch (err) {
      console.error('Failed to fetch symbols', err);
    } finally {
      setLoading(false);
    }
  };

  // Debounced search
  useEffect(() => {
    const timer = setTimeout(() => {
      fetchSymbols(0, searchQuery, false);
    }, 300);
    return () => clearTimeout(timer);
  }, [searchQuery]);

  const lastElementRef = useCallback(
    (node: HTMLDivElement) => {
      if (loading) return;
      if (observer.current) observer.current.disconnect();

      observer.current = new IntersectionObserver((entries) => {
        if (entries[0].isIntersecting && hasMore) {
          fetchSymbols(symbols.length, searchQuery, true);
        }
      });

      if (node) observer.current.observe(node);
    },
    [loading, hasMore, symbols.length, searchQuery],
  );

  // Live prices via SSE
  useEffect(() => {
    // Only connect if there are symbols
    const eventSource = new EventSource('/api/v1/stream');

    eventSource.addEventListener('price', (e) => {
      try {
        const data = JSON.parse(e.data);
        if (data.symbol && data.price) {
          setPrices((prev) => ({
            ...prev,
            [data.symbol]: parseFloat(data.price),
          }));
        }
      } catch (err) {
        console.error('Failed to parse price data', err);
      }
    });

    return () => {
      eventSource.close();
    };
  }, []);

  if (!user) {
    return <AuthScreen />;
  }

  return (
    <div className="min-h-screen bg-black text-zinc-100 font-sans px-4 flex flex-col gap-4 pb-10">
      <Navbar onSymbolSelect={(s) => router.push(`/?symbol=${s}`)} />

      <div className="max-w-5xl mx-auto w-full mt-6 flex flex-col gap-6">
        <div className="flex justify-between items-end">
          <div>
            <h2 className="text-2xl font-bold tracking-tight mb-2">Markets</h2>
            <p className="text-zinc-400 text-sm">
              Explore and trade all available assets on Scalpy.
            </p>
          </div>

          <div className="relative w-64">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-zinc-500" />
            <input
              type="text"
              placeholder="Filter assets..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="bg-zinc-900 border border-zinc-800 rounded-lg pl-10 pr-4 py-2 text-sm text-zinc-100 outline-none focus:border-emerald-500 transition-colors w-full"
            />
          </div>
        </div>

        <div className="bg-zinc-900/50 border border-zinc-800/50 rounded-xl overflow-hidden">
          <table className="w-full text-left text-sm">
            <thead className="bg-zinc-900 border-b border-zinc-800 text-zinc-400">
              <tr>
                <th className="px-6 py-4 font-medium">Asset Name</th>
                <th className="px-6 py-4 font-medium text-right">Live Price</th>
                <th className="px-6 py-4 font-medium text-right">Status</th>
                <th className="px-6 py-4 font-medium text-right">Action</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-zinc-800/50">
              {symbols.map((symbol, index) => {
                const isLast = index === symbols.length - 1;
                return (
                  <tr
                    key={symbol.name}
                    ref={isLast ? lastElementRef : null}
                    className="hover:bg-zinc-800/30 transition-colors group"
                  >
                    <td className="px-6 py-4">
                      <div className="flex items-center gap-3">
                        <div className="w-8 h-8 rounded-full bg-zinc-800 flex items-center justify-center text-xs font-bold text-emerald-500">
                          {symbol.name.split('/')[0].substring(0, 2)}
                        </div>
                        <span className="font-semibold text-zinc-200">{symbol.name}</span>
                      </div>
                    </td>
                    <td className="px-6 py-4 text-right">
                      {prices[symbol.name] ? (
                        <span className="font-mono text-lg font-medium text-zinc-100">
                          ${prices[symbol.name].toFixed(2)}
                        </span>
                      ) : (
                        <span className="text-zinc-600 font-mono">--</span>
                      )}
                    </td>
                    <td className="px-6 py-4 text-right">
                      {symbol.is_active ? (
                        <span className="inline-flex items-center gap-1.5 px-2 py-1 rounded-md bg-emerald-500/10 text-emerald-500 text-xs font-medium">
                          <span className="w-1.5 h-1.5 rounded-full bg-emerald-500 animate-pulse"></span>
                          Trading
                        </span>
                      ) : (
                        <span className="inline-flex items-center gap-1.5 px-2 py-1 rounded-md bg-rose-500/10 text-rose-500 text-xs font-medium">
                          <span className="w-1.5 h-1.5 rounded-full bg-rose-500"></span>
                          Offline
                        </span>
                      )}
                    </td>
                    <td className="px-6 py-4 text-right">
                      <button
                        onClick={() => router.push(`/?symbol=${symbol.name}`)}
                        className="px-4 py-2 bg-zinc-800 hover:bg-emerald-600 hover:text-white text-zinc-300 rounded-lg text-xs font-medium transition-colors opacity-0 group-hover:opacity-100"
                      >
                        Trade
                      </button>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>

          {loading && (
            <div className="flex justify-center p-8">
              <Loader2 className="w-6 h-6 text-emerald-500 animate-spin" />
            </div>
          )}

          {!loading && symbols.length === 0 && (
            <div className="flex flex-col items-center justify-center p-12 text-zinc-500">
              <Search className="w-12 h-12 mb-4 opacity-20" />
              <p>No assets found matching your criteria.</p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
