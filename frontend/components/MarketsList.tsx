'use client';

import React, { useState, useEffect, useRef, useCallback } from 'react';
import Navbar from '@/components/Navbar';
import { Search, Loader2 } from 'lucide-react';
import { useRouter } from 'next/navigation';
import api from '@/lib/axios';

export interface SymbolData {
  name: string;
  is_active: boolean;
  last_price?: number | null;
}

interface MarketsListProps {
  initialSymbols: SymbolData[];
}

const PriceCell = ({ price }: { price?: number }) => {
  const [flash, setFlash] = useState<'up' | 'down' | null>(null);
  const prevPriceRef = useRef<number | undefined>(price);

  useEffect(() => {
    if (
      price !== undefined &&
      prevPriceRef.current !== undefined &&
      price !== prevPriceRef.current
    ) {
      if (price > prevPriceRef.current) {
        setFlash('up');
      } else {
        setFlash('down');
      }

      const timer = setTimeout(() => {
        setFlash(null);
      }, 300);

      prevPriceRef.current = price;
      return () => clearTimeout(timer);
    }
    prevPriceRef.current = price;
  }, [price]);

  if (price === undefined) {
    return <span className="text-zinc-600 font-mono">--</span>;
  }

  let colorClass = 'text-zinc-100';
  let bgClass = 'bg-transparent';

  if (flash === 'up') {
    colorClass = 'text-emerald-400';
    bgClass = 'bg-emerald-500/20';
  } else if (flash === 'down') {
    colorClass = 'text-rose-400';
    bgClass = 'bg-rose-500/20';
  }

  return (
    <span
      className={`font-mono text-lg font-medium tabular-nums px-2 py-1 rounded transition-colors duration-500 ${colorClass} ${bgClass}`}
    >
      ${price.toFixed(2)}
    </span>
  );
};

const seedPricesFrom = (symbolList: SymbolData[]): Record<string, number> => {
  const seeded: Record<string, number> = {};
  for (const s of symbolList) {
    if (s.last_price !== undefined && s.last_price !== null) {
      seeded[s.name] = s.last_price;
    }
  }
  return seeded;
};

const CoinIcon = ({ symbol }: { symbol: string }) => {
  const [error, setError] = useState(false);
  const baseCurrency = symbol.split('/')[0].toLowerCase();

  if (error) {
    return (
      <div className="w-8 h-8 rounded-full bg-zinc-800 flex items-center justify-center text-xs font-bold text-emerald-500 border border-zinc-700 shrink-0">
        {symbol.split('/')[0].substring(0, 2).toUpperCase()}
      </div>
    );
  }

  return (
    <img
      src={`https://cdn.jsdelivr.net/gh/atomiclabs/cryptocurrency-icons@1a63530be6e374711a8554f31b17e4cb92c25fa5/svg/color/${baseCurrency}.svg`}
      alt={baseCurrency}
      className="w-8 h-8 rounded-full shrink-0"
      onError={() => setError(true)}
    />
  );
};

export default function MarketsList({ initialSymbols }: MarketsListProps) {
  const [symbols, setSymbols] = useState<SymbolData[]>(initialSymbols);
  // Seed with last known prices from the API so prices are visible
  // immediately on page load; live stream updates overwrite them.
  const [prices, setPrices] = useState<Record<string, number>>(() =>
    seedPricesFrom(initialSymbols),
  );
  const [loading, setLoading] = useState(false);
  const [hasMore, setHasMore] = useState(initialSymbols.length === 30);
  const [searchQuery, setSearchQuery] = useState('');

  const observer = useRef<IntersectionObserver | null>(null);
  const limit = 30;
  const router = useRouter();

  const fetchSymbols = async (offset: number, query: string, append: boolean) => {
    if (loading || (!hasMore && offset !== 0)) return;

    setLoading(true);
    try {
      const res = await api.get(`/api/v1/symbols?q=${query}&limit=${limit}&offset=${offset}`);
      const newSymbols = res.data;

      if (newSymbols.length < limit) {
        setHasMore(false);
      } else {
        setHasMore(true);
      }

      setSymbols((prev) => (append ? [...prev, ...newSymbols] : newSymbols));
      // Seed last known prices for newly loaded symbols without
      // clobbering fresher values already received from the stream.
      setPrices((prev) => ({ ...seedPricesFrom(newSymbols), ...prev }));
    } catch (err) {
      console.error('Failed to fetch symbols', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    const timer = setTimeout(() => {
      if (searchQuery) {
        fetchSymbols(0, searchQuery, false);
      } else if (symbols.length === 0 || symbols.length !== initialSymbols.length) {
        setSymbols(initialSymbols);
        setHasMore(initialSymbols.length === 30);
      }
    }, 300);
    return () => clearTimeout(timer);
  }, [searchQuery, initialSymbols]);

  const lastElementRef = useCallback(
    (node: HTMLDivElement | HTMLTableRowElement) => {
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

  useEffect(() => {
    if (symbols.length === 0) return;

    const symbolString = symbols.map((s) => s.name).join(',');
    const eventSource = new EventSource(
      `/api/v1/stream?symbol=${encodeURIComponent(symbolString)}`,
    );

    eventSource.addEventListener('price', (e) => {
      try {
        const data = JSON.parse(e.data);
        if (data.symbol && data.bid_price !== undefined) {
          const tradePrice = (data.bid_price + data.ask_price) / 2;
          setPrices((prev) => ({
            ...prev,
            [data.symbol]: parseFloat(tradePrice.toFixed(2)),
          }));
        }
      } catch (err) {
        console.error('Failed to parse price data', err);
      }
    });

    return () => {
      eventSource.close();
    };
  }, [symbols]);

  return (
    <div className="min-h-screen bg-black text-zinc-100 font-sans px-4 flex flex-col gap-4 pb-10">
      <Navbar />

      <div className="max-w-5xl mx-auto w-full mt-6 flex flex-col gap-6">
        <div className="flex flex-col sm:flex-row sm:justify-between sm:items-end gap-4">
          <div>
            <h2 className="text-2xl font-bold tracking-tight mb-2">Markets</h2>
            <p className="text-zinc-400 text-sm">
              Explore and trade all available assets on Scalpy.
            </p>
          </div>

          <div className="relative w-full sm:w-64">
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

        <div className="bg-transparent md:bg-zinc-900/50 md:border md:border-zinc-800/50 rounded-xl md:overflow-hidden md:shadow-xl">
          {/* Mobile View */}
          <div className="flex flex-col gap-3 md:hidden">
            {symbols.map((symbol, index) => {
              const isLast = index === symbols.length - 1;
              return (
                <div
                  key={`mobile-${symbol.name}`}
                  ref={(node) => {
                    if (isLast && node) lastElementRef(node);
                  }}
                  className="bg-zinc-900/50 border border-zinc-800/50 rounded-lg p-4 flex flex-col gap-4 active:bg-zinc-800/50 transition-colors cursor-pointer"
                  onClick={() => router.push(`/?market=${symbol.name}`)}
                >
                  <div className="flex justify-between items-center">
                    <div className="flex items-center gap-3">
                      <CoinIcon symbol={symbol.name} />
                      <span className="font-semibold text-zinc-200">{symbol.name}</span>
                    </div>
                    <PriceCell price={prices[symbol.name]} />
                  </div>
                  <div className="flex justify-between items-center">
                    {symbol.is_active ? (
                      <span className="inline-flex items-center gap-1.5 px-2 py-1 rounded-md bg-emerald-500/10 text-emerald-500 text-xs font-medium border border-emerald-500/20">
                        <span className="w-1.5 h-1.5 rounded-full bg-emerald-500 animate-pulse"></span>
                        Trading
                      </span>
                    ) : (
                      <span className="inline-flex items-center gap-1.5 px-2 py-1 rounded-md bg-rose-500/10 text-rose-500 text-xs font-medium border border-rose-500/20">
                        <span className="w-1.5 h-1.5 rounded-full bg-rose-500"></span>
                        Offline
                      </span>
                    )}
                    <span className="text-xs font-medium text-emerald-500 opacity-80 flex items-center gap-1">
                      Spot <span className="text-lg leading-none">&rarr;</span>
                    </span>
                  </div>
                </div>
              );
            })}
          </div>

          {/* Desktop View */}
          <table className="hidden md:table w-full table-fixed text-left text-sm">
            <thead className="bg-zinc-900 border-b border-zinc-800 text-zinc-400">
              <tr>
                <th className="px-6 py-4 font-medium w-1/3">Asset Name</th>
                <th className="px-6 py-4 font-medium text-right w-1/4">Live Price</th>
                <th className="px-6 py-4 font-medium text-right w-1/4">Status</th>
                <th className="px-6 py-4 font-medium text-right w-1/6">Action</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-zinc-800/50">
              {symbols.map((symbol, index) => {
                const isLast = index === symbols.length - 1;
                return (
                  <tr
                    key={symbol.name}
                    ref={(node) => {
                      if (isLast && node) lastElementRef(node);
                    }}
                    className="hover:bg-zinc-800/30 transition-colors group cursor-pointer"
                    onClick={() => router.push(`/?market=${symbol.name}`)}
                  >
                    <td className="px-6 py-4">
                      <div className="flex items-center gap-3">
                        <CoinIcon symbol={symbol.name} />
                        <span className="font-semibold text-zinc-200">{symbol.name}</span>
                      </div>
                    </td>
                    <td className="px-6 py-4 text-right">
                      <PriceCell price={prices[symbol.name]} />
                    </td>
                    <td className="px-6 py-4 text-right">
                      {symbol.is_active ? (
                        <span className="inline-flex items-center gap-1.5 px-2 py-1 rounded-md bg-emerald-500/10 text-emerald-500 text-xs font-medium border border-emerald-500/20">
                          <span className="w-1.5 h-1.5 rounded-full bg-emerald-500 animate-pulse"></span>
                          Trading
                        </span>
                      ) : (
                        <span className="inline-flex items-center gap-1.5 px-2 py-1 rounded-md bg-rose-500/10 text-rose-500 text-xs font-medium border border-rose-500/20">
                          <span className="w-1.5 h-1.5 rounded-full bg-rose-500"></span>
                          Offline
                        </span>
                      )}
                    </td>
                    <td className="px-6 py-4 text-right">
                      <button
                        onClick={(e) => {
                          e.stopPropagation();
                          router.push(`/?market=${symbol.name}`);
                        }}
                        className="px-4 py-2 bg-emerald-600/10 hover:bg-emerald-600 text-emerald-500 hover:text-white rounded-lg text-xs font-medium transition-colors"
                      >
                        Spot
                      </button>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>

          {loading && (
            <div className="flex justify-center p-8 border-t border-zinc-800/50">
              <Loader2 className="w-6 h-6 text-emerald-500 animate-spin" />
            </div>
          )}

          {!loading && symbols.length === 0 && (
            <div className="flex flex-col items-center justify-center p-12 text-zinc-500 border-t border-zinc-800/50">
              <Search className="w-12 h-12 mb-4 opacity-20" />
              <p>No assets found matching your criteria.</p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
