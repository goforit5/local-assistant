# Local Assistant UI

Minimal, Apple-inspired React UI for testing all Local Assistant features.

## Features

- **Chat Interface** - Real-time messaging with the assistant
- **Vision Service** - Upload and extract data from documents
- **Reasoning** - Multi-step problem solving interface
- **Computer Use** - Browser/desktop automation controls
- **Cost Tracking** - Real-time spending dashboard

## Setup

```bash
cd ui
npm install
npm run dev
```

Open [http://localhost:3001](http://localhost:3001)

## Tech Stack

- React 18
- Vite
- Lucide Icons
- Pure CSS (Apple design system)

## Design Principles

- Minimal, clean interface
- Dark mode optimized
- Smooth animations
- Apple SF Pro font stack
- 10x dev speed over beauty

## Structure

```
ui/
├── src/
│   ├── App.jsx          # Main component with all views
│   ├── App.css          # Styles (Apple aesthetic)
│   ├── index.css        # Global styles
│   └── main.jsx         # Entry point
├── index.html
├── vite.config.js
└── package.json
```

## Usage

### Development
```bash
npm run dev       # Start dev server on :3001
```

### Production
```bash
npm run build     # Build to dist/
npm run preview   # Preview production build
```

## API Integration

Currently mocked. To integrate with backend:

1. Update proxy in `vite.config.js`
2. Replace mock API calls in `App.jsx`
3. Connect to FastAPI endpoints

Example:
```js
const response = await fetch('/api/chat', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({ messages, model: 'auto' })
})
```

## Customization

Colors in `src/index.css`:
```css
--accent: #007aff        /* Primary blue */
--success: #30d158       /* Green */
--warning: #ff9f0a       /* Orange */
--error: #ff453a         /* Red */
```

## License

MIT
