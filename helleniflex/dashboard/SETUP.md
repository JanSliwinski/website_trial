# Running the dashboard

Two paths. Pick whichever fits your situation.

## Path A — Zero setup (open it in a browser)

The fastest way: there's a self-contained `index.html` in this folder that
loads React, Tailwind, and Babel from CDN and embeds the dashboard inline.

```bash
# Either: just double-click index.html in your file manager
open dashboard/index.html         # macOS
xdg-open dashboard/index.html     # Linux
start dashboard/index.html        # Windows

# Or serve it with any tiny static server:
cd dashboard && python3 -m http.server 8000
# then visit http://localhost:8000
```

First load takes ~3-5 seconds because Babel compiles the JSX in the browser.
After that it's instant. Internet connection required for the CDN scripts on
first load — they'll be cached after.

This is the path to use during a live hackathon demo. Zero npm troubles.

## Path B — Vite project (deployable, production)

Use this when you want to deploy the dashboard to a public URL (Vercel,
Netlify, GitHub Pages, etc.) or fold it into a larger app.

```bash
# 1. Scaffold a new Vite + React project
npm create vite@latest helleniflex-app -- --template react
cd helleniflex-app
npm install

# 2. Add Tailwind v3 (arbitrary-value support is on by default)
npm install -D tailwindcss@3 postcss autoprefixer
npx tailwindcss init -p

# 3. Configure Tailwind to scan our source files
#    Edit tailwind.config.js, replace `content: []` with:
#    content: ["./index.html", "./src/**/*.{js,jsx}"]

# 4. Add Tailwind directives to src/index.css (replace its contents):
#    @tailwind base;
#    @tailwind components;
#    @tailwind utilities;

# 5. Drop the dashboard into the project
cp /path/to/HelleniFlexDashboard.jsx src/

# 6. Replace src/App.jsx with:
#    import HelleniFlexDashboard from './HelleniFlexDashboard';
#    export default HelleniFlexDashboard;

# 7. Run it
npm run dev
# → http://localhost:5173
```

For deployment:

```bash
npm run build               # produces dist/
# Then drag dist/ into Netlify, or `vercel deploy`, or push to gh-pages.
```

## Path C — Embed in an existing React project

The dashboard is a single component with a default export and no required
props. Drop `HelleniFlexDashboard.jsx` into your project's source folder
and import it like any other component:

```jsx
import HelleniFlexDashboard from './HelleniFlexDashboard';

function MyPage() {
  return <HelleniFlexDashboard />;
}
```

Requires React 18+ and Tailwind 3+ in the host project. Custom CSS is
injected by the component itself (no external stylesheet needed).
