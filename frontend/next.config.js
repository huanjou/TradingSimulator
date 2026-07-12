/** @type {import('next').NextConfig} */
const nextConfig = {
  output: 'standalone',
  reactStrictMode: false,
  async rewrites() {
    return [
      {
        source: '/api/:path*',
        destination: 'http://nginx/api/:path*', // proxy to nginx in docker network
      },
    ];
  },
};
module.exports = nextConfig;
