import AuthProvider from '../components/AuthProvider';
import './globals.css';

export const metadata = {
  title: 'Scalpy',
  description: 'Trading Simulator Interface',
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>
        <AuthProvider>{children}</AuthProvider>
      </body>
    </html>
  );
}
