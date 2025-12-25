import type { NextConfig } from "next";

const withBundleAnalyzer = require('@next/bundle-analyzer')({
  enabled: process.env.ANALYZE === 'true',
});

const nextConfig: NextConfig = {
  // Enable gzip compression for responses
  compress: true,
};

export default withBundleAnalyzer(nextConfig);
