import { cookies } from 'next/headers';
import AuthProvider from '../components/AuthProvider';
import './globals.css';

export const metadata = {
  title: 'Scalpy',
  description: 'Trading Simulator Interface',
};

async function getUser() {
  const cookieStore = cookies();
  const token = cookieStore.get('access_token');

  if (!token) {
    return null;
  }

  try {
    // Next.js server accesses API through NGINX docker network hostname
    const res = await fetch('http://nginx/api/v1/users/me', {
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

export default async function RootLayout({ children }: { children: React.ReactNode }) {
  const initialUser = await getUser();

  return (
    <html lang="en">
      <body>
        <AuthProvider initialUser={initialUser}>{children}</AuthProvider>
      </body>
    </html>
  );
}
