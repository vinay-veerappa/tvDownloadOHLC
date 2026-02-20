import type { NextConfig } from "next";

const withBundleAnalyzer = require('@next/bundle-analyzer')({
  enabled: process.env.ANALYZE === 'true',
});

const nextConfig: NextConfig = {
  // Enable gzip compression for responses
  compress: true,
  turbopack: {},
  webpack: (config, { dev }) => {
    if (dev) {
      config.watchOptions = {
        ignored: ['**/data/**', '**/node_modules/**'],
        poll: false, // Use native filesystem events
      }
    }
    return config
  },
};

export default withBundleAnalyzer(nextConfig);
