/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  async rewrites() {
    const backend = process.env.NIC_API_URL || 'http://127.0.0.1:8000';
    return ['/api/health', '/api/validate-nic', '/api/verify', '/api/scan-barcode', '/api/train/:id'].map((path) => ({
      source: path,
      destination: `${backend}${path}`,
    }));
  },
  images: {
    unoptimized: true
  }
};

export default nextConfig;
