import MarketsList from '@/components/MarketsList';
import { fetchInitialSymbols } from '@/lib/serverApi';

export const metadata = {
  title: 'Markets - Scalpy',
  description: 'Explore and trade all available assets on Scalpy.',
};

export default async function MarketsPage() {
  const initialSymbols = await fetchInitialSymbols();

  return <MarketsList initialSymbols={initialSymbols} />;
}
