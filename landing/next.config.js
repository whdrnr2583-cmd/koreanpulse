/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  async redirects() {
    return [
      {
        source: '/:path*',
        has: [{ type: 'host', value: 'www.koreanpulse.dev' }],
        destination: 'https://koreanpulse.dev/:path*',
        permanent: true,
      },
    ];
  },
};

module.exports = nextConfig;
