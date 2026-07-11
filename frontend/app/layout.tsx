import './globals.css';

export const metadata = {
  title: 'Antigravity Exchange',
  description: 'Trading Simulator Interface',
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
