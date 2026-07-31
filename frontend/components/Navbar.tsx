'use client';
import React, { useState, useEffect, useRef } from 'react';
import { TrendingUp, LogOut, Search, LayoutDashboard, Menu, X } from 'lucide-react';
import { useAuthStore } from '@/store/useAuthStore';
import { useMarketStore } from '@/store/useMarketStore';
import { useDebounce } from '@/lib/hooks/useDebounce';
import api from '@/lib/axios';
import { useRouter, usePathname } from 'next/navigation';

export default function Navbar() {
  const { user, logout } = useAuthStore();
  const setSymbol = useMarketStore((s) => s.setSymbol);
  const triggerLayoutReset = useMarketStore((s) => s.triggerLayoutReset);

  const [searchQuery, setSearchQuery] = useState('');
  const debouncedSearch = useDebounce(searchQuery, 300);

  const [searchResults, setSearchResults] = useState<{ name: string; is_active: boolean }[]>([]);
  const [isSearchOpen, setIsSearchOpen] = useState(false);
  const [isMobileMenuOpen, setIsMobileMenuOpen] = useState(false);

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
    router.push(`/?market=${symbol}`);
  };

  const SearchBox = () => (
    <div className="relative w-full md:w-auto" ref={searchRef}>
      <div className="relative w-full">
        <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-zinc-500" />
        <input
          type="text"
          placeholder="Search assets..."
          value={searchQuery}
          onChange={(e) => setSearchQuery(e.target.value)}
          className="bg-zinc-900 border border-zinc-800 rounded-full pl-10 pr-4 py-2 text-sm text-zinc-100 outline-none focus:border-emerald-500 transition-colors w-full md:w-64"
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
  );

  return (
    <header className="sticky top-0 z-50 bg-black/95 backdrop-blur-md flex flex-col border-b border-zinc-800 pb-4 pt-4 gap-4 -mx-4 px-4">
      <div className="flex items-center justify-between gap-3">
        <div
          className="flex items-center gap-2 cursor-pointer shrink-0"
          onClick={() => router.push('/')}
        >
          <TrendingUp className="w-6 h-6 text-emerald-500" />
          <h1 className="text-xl font-bold tracking-tight hidden sm:block">Scalpy</h1>
          <span className="bg-zinc-800 text-zinc-400 text-xs px-2 py-1 rounded ml-2 hidden md:inline-block">
            {user?.email}
          </span>
        </div>

        {/* Mobile Search */}
        <div className="flex-1 md:hidden">
          <SearchBox />
        </div>

        {/* Desktop Nav */}
        <div className="hidden md:flex items-center gap-6">
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

          <SearchBox />

          {pathname === '/' && (
            <button
              onClick={triggerLayoutReset}
              className="p-2 text-zinc-400 hover:text-white bg-zinc-900 border border-zinc-800 hover:bg-zinc-800 rounded-md transition-colors mr-2"
              title="Reset Dashboard Layout"
            >
              <LayoutDashboard className="w-4 h-4" />
            </button>
          )}

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

        {/* Mobile Burger */}
        <div className="md:hidden flex items-center shrink-0">
          <button
            onClick={() => setIsMobileMenuOpen(!isMobileMenuOpen)}
            className="p-2 text-zinc-400 hover:text-zinc-100 bg-zinc-900 border border-zinc-800 rounded-md transition-colors"
          >
            {isMobileMenuOpen ? <X className="w-5 h-5" /> : <Menu className="w-5 h-5" />}
          </button>
        </div>
      </div>

      {/* Mobile Menu Dropdown */}
      {isMobileMenuOpen && (
        <div className="flex flex-col gap-4 md:hidden pt-4 border-t border-zinc-800/50">
          <button
            onClick={() => {
              setIsMobileMenuOpen(false);
              router.push('/');
            }}
            className={`text-left text-sm font-medium p-2 rounded-md ${
              pathname === '/'
                ? 'text-emerald-500 bg-emerald-500/10'
                : 'text-zinc-400 hover:text-zinc-100 hover:bg-zinc-800/50'
            }`}
          >
            Trade
          </button>
          <button
            onClick={() => {
              setIsMobileMenuOpen(false);
              router.push('/markets');
            }}
            className={`text-left text-sm font-medium p-2 rounded-md ${
              pathname === '/markets'
                ? 'text-emerald-500 bg-emerald-500/10'
                : 'text-zinc-400 hover:text-zinc-100 hover:bg-zinc-800/50'
            }`}
          >
            Markets
          </button>

          <div className="border-t border-zinc-800/50 my-1"></div>

          {pathname === '/' && (
            <button
              onClick={() => {
                setIsMobileMenuOpen(false);
                triggerLayoutReset();
              }}
              className="flex items-center gap-3 text-left text-sm font-medium p-2 rounded-md text-zinc-400 hover:text-zinc-100 hover:bg-zinc-800/50"
            >
              <LayoutDashboard className="w-4 h-4" />
              Reset Dashboard Layout
            </button>
          )}

          <button
            onClick={async () => {
              setIsMobileMenuOpen(false);
              await logout();
            }}
            className="flex items-center gap-3 text-left text-sm font-medium p-2 rounded-md text-rose-400 hover:text-rose-300 hover:bg-rose-500/10"
          >
            <LogOut className="w-4 h-4" />
            Sign Out
          </button>
        </div>
      )}
    </header>
  );
}
