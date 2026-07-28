/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  output: 'standalone',
  // Do not advertise the framework/version in the X-Powered-By header.
  poweredByHeader: false,
  // NOTE: HTTP security headers (HSTS, X-Frame-Options, X-Content-Type-Options,
  // Referrer-Policy, ...) are applied centrally at the nginx edge
  // (infra/nginx/nginx.prod.conf) so they cover every upstream service, not
  // just the frontend. They are intentionally not duplicated here to avoid
  // conflicting/duplicated headers.
};

module.exports = nextConfig;
