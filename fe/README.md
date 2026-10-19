# AIP491 Frontend

React + TypeScript + Vite dashboard for the AIP491 CV–JD matching platform.

The application lives in **[`my-react-app/`](my-react-app/)** — see [`my-react-app/README.md`](my-react-app/README.md) for features, setup, and structure.

```powershell
cd my-react-app
npm install
copy .env.example .env      # set VITE_API_BASE_URL
npm run dev                 # http://localhost:5173
```

Features: CV–JD Matching (JD via PDF or text), CV Ranking, CV Comparison, CV Search. Talks to the backend (:8000), which proxies ML to the AI service (:8001).

## Chia sẻ demo qua Dev Tunnels

Khi share ra ngoài, đặt `VITE_API_BASE_URL` (trong `my-react-app/.env.local`) thành URL tunnel của backend (cổng 8000) rồi chạy FE ở chế độ tunnel:

```powershell
cd my-react-app
$env:VITE_TUNNEL=1; npm run dev
```

`vite.config.ts` đã cho phép domain `.devtunnels.ms` sẵn. Hướng dẫn đầy đủ (BE + AI + tunnel + push GitHub) xem repo backend: `be/HUONG_DAN_CHAY.md`.
