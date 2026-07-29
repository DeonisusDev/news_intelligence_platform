# frontend

Discovery-style feed for the News Intelligence Platform - Vite + React + TypeScript + Tailwind +
shadcn/ui, served by nginx in production. See `../docs/adr/0007-frontend-spa.md` for the
architecture decisions and `../README.md` for the full project.

## Local development (outside Docker)

```bash
cp .env.example .env   # points at a locally running FastAPI on :8000
npm install
npm run dev            # http://localhost:5173 (or :3000 if free)
```

## Scripts

- `npm run dev` - Vite dev server with HMR
- `npm run build` - type-check (`tsc -b`) + production build to `dist/`
- `npm run lint` - oxlint
- `npm run preview` - serve the production build locally
