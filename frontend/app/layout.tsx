import { fetchUserInSSR } from '../lib/serverApi';
import AuthProvider from '../components/AuthProvider';
import './globals.css';

export const metadata = {
  title: 'Scalpy',
  description: 'Trading Simulator Interface',
};

export default async function RootLayout({ children }: { children: React.ReactNode }) {
  const initialUser = await fetchUserInSSR();

  return (
    <html lang="en">
      <body>
        <AuthProvider initialUser={initialUser}>{children}</AuthProvider>
      </body>
    </html>
  );
}
