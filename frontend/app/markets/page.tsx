import MarketsList, { SymbolData } from '@/components/MarketsList';

export const metadata = {
  title: 'Markets - Scalpy',
  description: 'Explore and trade all available assets on Scalpy.',
};

async function getInitialSymbols(): Promise<SymbolData[]> {
  try {
    const res = await fetch('http://nginx/api/v1/symbols?limit=30&offset=0', {
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

export default async function MarketsPage() {
  const initialSymbols = await getInitialSymbols();

  return <MarketsList initialSymbols={initialSymbols} />;
}
