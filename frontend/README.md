# Frontend applications

This directory contains the shared trolley display and the Component 4 mobile
application workspace. Component 3's research dashboard is maintained separately
under `component3/simulations/navigation_dashboard/`.

## Trolley display

`frontend/trolley-display/` is a React 18 and Vite application. It contains the
shared application shell plus Component 1 validation, Component 2 cart, and
Component 4 billing panels. Component 3 React navigation views remain under
`component3/frontend/navigation/`.

Requires Node.js 20 or newer:

```bash
cd frontend/trolley-display
npm install
npm run dev
```

Build or preview the production bundle with:

```bash
npm run build
npm run preview
```

Important entry points:

- `src/main.jsx` mounts the application.
- `src/app/App.jsx` defines the trolley-screen layout.
- `src/app/routes.jsx` defines screen routing.
- `src/api/client.js` is the shared backend client.

## Component 3 customer and operator dashboard

The actively evaluated navigation UI is served by the existing Python dashboard:

```bash
component3/run/start_dashboard.sh
```

- Customer view: `http://127.0.0.1:8765/customer`
- Operator view: `http://127.0.0.1:8765/`

See `component3/simulations/navigation_dashboard/README.md` for detailed research
and acceptance instructions.

## Mobile application

`frontend/mobile-app/` preserves the Component 4 feature boundaries for lists,
recipes, billing, and notifications. It is currently a scaffold; no mobile
framework or runnable application entry point is claimed.

Frontend applications must use documented API or event contracts rather than
importing backend implementation modules directly.
