'use client';
import React, { useState, useEffect, useRef } from 'react';
import { TrendingUp, LogOut, Search } from 'lucide-react';
import { useAuthStore } from '@/store/useAuthStore';
import { useMarketStore } from '@/store/useMarketStore';
import { useDebounce } from '@/lib/hooks/useDebounce';
import api from '@/lib/axios';
import { useRouter, usePathname } from 'next/navigation';

export default function Navbar() {
  const { user, logout } = useAuthStore();
  const setSymbol = useMarketStore((s) => s.setSymbol);

  const [searchQuery, setSearchQuery] = useState('');
  const debouncedSearch = useDebounce(searchQuery, 300);

  const [searchResults, setSearchResults] = useState<{ name: string; is_active: boolean }[]>([]);
  const [isSearchOpen, setIsSearchOpen] = useState(false);
  const router = useRouter();
  const pathname = usePathname();
  const searchRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (searchRef.current && !searchRef.current.contains(event.target as Node)) {
        setIsSearchOpen(false);
      }
    };
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  useEffect(() => {
    if (debouncedSearch.trim().length > 0) {
      api
        .get(`/api/v1/symbols?q=${debouncedSearch}&limit=5`)
        .then((res) => {
          setSearchResults(res.data);
          setIsSearchOpen(true);
        })
        .catch((err) => console.error(err));
    } else {
      setSearchResults([]);
      setIsSearchOpen(false);
    }
  }, [debouncedSearch]);

  const handleSelect = (symbol: string) => {
    setSearchQuery('');
    setIsSearchOpen(false);
    setSymbol(symbol);

    // Navigate to dashboard if not on it
    if (pathname !== '/') {
      router.push(`/?symbol=${symbol}`);
    }
  };

  return (
    <header className="flex items-center justify-between border-b border-zinc-800 pb-4 mb-4 pt-2">
      <div className="flex items-center gap-2 cursor-pointer" onClick={() => router.push('/')}>
        <TrendingUp className="w-6 h-6 text-emerald-500" />
        <h1 className="text-xl font-bold tracking-tight">Scalpy</h1>
        <span className="bg-zinc-800 text-zinc-400 text-xs px-2 py-1 rounded ml-2 hidden md:inline-block">
          {user?.email}
        </span>
      </div>

      <div className="flex items-center gap-6">
        <div className="flex gap-4">
          <button
            onClick={() => router.push('/')}
            className={`text-sm font-medium transition-colors ${
              pathname === '/' ? 'text-emerald-500' : 'text-zinc-400 hover:text-zinc-100'
            }`}
          >
            Trade
          </button>
          <button
            onClick={() => router.push('/markets')}
            className={`text-sm font-medium transition-colors ${
              pathname === '/markets' ? 'text-emerald-500' : 'text-zinc-400 hover:text-zinc-100'
            }`}
          >
            Markets
          </button>
        </div>

        <div className="relative" ref={searchRef}>
          <div className="relative">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-zinc-500" />
            <input
              type="text"
              placeholder="Search assets..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="bg-zinc-900 border border-zinc-800 rounded-full pl-10 pr-4 py-2 text-sm text-zinc-100 outline-none focus:border-emerald-500 transition-colors w-64"
            />
          </div>

          {isSearchOpen && searchResults.length > 0 && (
            <div className="absolute top-full mt-2 w-full bg-zinc-900 border border-zinc-800 rounded-lg shadow-xl overflow-hidden z-50">
              {searchResults.map((s) => (
                <div
                  key={s.name}
                  onClick={() => handleSelect(s.name)}
                  className="px-4 py-3 hover:bg-zinc-800 cursor-pointer flex justify-between items-center"
                >
                  <span className="font-medium text-zinc-200">{s.name}</span>
                  {!s.is_active && <span className="text-xs text-rose-500">Offline</span>}
                </div>
              ))}
            </div>
          )}
        </div>

        <button
          onClick={async () => {
            await logout();
          }}
          className="p-2 text-zinc-400 hover:text-white bg-zinc-900 border border-zinc-800 hover:bg-zinc-800 rounded-md transition-colors"
          title="Sign Out"
        >
          <LogOut className="w-4 h-4" />
        </button>
      </div>
    </header>
  );
}
