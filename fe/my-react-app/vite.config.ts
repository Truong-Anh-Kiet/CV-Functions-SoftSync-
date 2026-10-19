import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// Bật cấu hình dành cho Dev Tunnels bằng cách chạy với VITE_TUNNEL=1.
// Khi chạy local bình thường (không đặt biến này) mọi thứ giữ nguyên như cũ.
const isTunnel = process.env.VITE_TUNNEL === '1'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  server: {
    // Lắng nghe trên mọi network interface (cần cho Dev Tunnels / chia sẻ LAN).
    // Không ảnh hưởng khi vẫn mở bằng localhost.
    host: true,
    // Cho phép truy cập qua domain Dev Tunnels; nếu thiếu, Vite báo "host not allowed".
    // Thêm domain khác nếu dùng ngrok/cloudflare, ví dụ '.ngrok-free.app'.
    allowedHosts: ['.devtunnels.ms'],
    // Chỉ ép HMR qua HTTPS:443 khi chạy chế độ tunnel; local giữ HMR mặc định.
    ...(isTunnel ? { hmr: { clientPort: 443, protocol: 'wss' as const } } : {}),
  },
})
