/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  experimental: {
    allowedDevOrigins: ['192.168.137.162'],
  },
}

module.exports = nextConfig
