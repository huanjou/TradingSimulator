import { cookies } from 'next/headers';
import { SymbolData } from '@/components/MarketsList';

const API_BASE = 'http://nginx/api/v1';

export async function fetchUserInSSR() {
  const cookieStore = cookies();
  const token = cookieStore.get('access_token');

  console.log('[SSR] access_token cookie:', token ? 'FOUND' : 'NOT FOUND');

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

    console.log('[SSR] /users/me response status:', res.status);

    if (res.ok) {
      const user = await res.json();
      console.log('[SSR] user fetched:', user?.email);
      return user;
    }
    return null;
  } catch (error) {
    console.error('[SSR] Failed to fetch user in SSR:', error);
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
