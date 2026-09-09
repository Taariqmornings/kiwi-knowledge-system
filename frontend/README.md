# Kiwi — Frontend

Desktop & web client for **Kiwi**, the offline knowledge base system. Built with
React 19, TypeScript, Vite and Electron.

## Tech stack

| Layer | Technology |
|---|---|
| UI | React 19, TypeScript, Tailwind CSS 4 |
| Build / dev server | Vite |
| Desktop shell | Electron 30 |
| Tests | Vitest + Testing Library |

## Scripts

From the `frontend/` directory:

```bash
npm install        # install dependencies
npm run dev        # start the Vite dev server (http://localhost:5173)
npm run start      # Vite dev server + Electron window
npm run build      # type-check + production build into dist/
npm run lint       # ESLint
npm run test       # Vitest unit tests
npm run test:watch # Vitest in watch mode
npm run electron:pack  # build + package a native installer into release/
```

## Backend connection

The app talks to the FastAPI backend on `http://127.0.0.1:8000` by default.

- **Electron mode** — the backend URL is provided via IPC (`electronAPI.getBackendUrl()`).
- **Browser mode** — falls back to the `VITE_BACKEND_URL` environment variable,
  then to `http://127.0.0.1:8000`.

All API access is centralised in [`src/services/api.ts`](src/services/api.ts).

## Project structure

```
frontend/
├── electron/            # Electron main + preload processes
├── public/              # Static assets (favicon, app icon source)
├── build/               # Generated packaging icons
├── src/
│   ├── __tests__/       # Component tests
│   ├── assets/          # (removed unused scaffold assets)
│   ├── components/      # React components (search, reader, chat, settings…)
│   ├── context/         # Global app state (AppContext)
│   ├── hooks/           # Custom React hooks
│   ├── services/        # API client
│   ├── test/            # Test setup
│   └── types/           # TypeScript interfaces
├── index.html
├── package.json
└── vite.config.ts
```

## Tests

```bash
npm run test
```

The suite covers the API client (host resolution, request building) and the
icon components. Component tests use Vitest with jsdom and Testing Library.

## Code style

- Strict TypeScript — no `any`.
- React functional components only; global state via `AppContext`.
- Styling in `src/index.css` using the project theme (deep slate + cyan `#0ea5e9`).
- Run `npm run lint` before opening a pull request.