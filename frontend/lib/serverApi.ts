import { cookies } from 'next/headers';
import { SymbolData } from '@/components/MarketsList';

const API_BASE = 'http://nginx/api/v1';

export async function fetchUserInSSR() {
  const cookieStore = cookies();
  const token = cookieStore.get('access_token');

  if (!token) {
    return null;
  }

  try {
    const res = await fetch(`${API_BASE}/users/me`, {
      headers: {
        Cookie: `access_token=${token.value}`,
      },
      cache: 'no-store',
    });

    if (res.ok) {
      return await res.json();
    }
    return null;
  } catch (error) {
    console.error('Failed to fetch user in SSR:', error);
    return null;
  }
}

export async function fetchInitialSymbols(): Promise<SymbolData[]> {
  try {
    const res = await fetch(`${API_BASE}/symbols?limit=30&offset=0`, {
      cache: 'no-store', // Always fetch fresh list of markets
    });

    if (res.ok) {
      return await res.json();
    }
    return [];
  } catch (error) {
    console.error('Failed to fetch initial symbols for markets page:', error);
    return [];
  }
}
