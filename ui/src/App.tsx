import { useState } from 'react'
import styles from './App.module.css'
import { ScrapeQueuePanel } from './features/scrape-queue/ScrapeQueuePanel'
import { RecipeReviewPanel } from './features/recipe-review/RecipeReviewPanel'
import { SitesPanel } from './features/sites/SitesPanel'

const PANELS = [
  { id: 'sites', label: 'Sites', render: () => <SitesPanel /> },
  { id: 'scrape-queue', label: 'Scrape queue', render: () => <ScrapeQueuePanel /> },
  { id: 'recipe-review', label: 'Recipe review', render: () => <RecipeReviewPanel /> },
] as const

type PanelId = (typeof PANELS)[number]['id']

// Note: this is a simple tab switcher over local state, not a router — the
// skill doc says not to add a state/routing library beyond react-query
// without confirming with the user first, and a handful of internal admin
// panels doesn't need one.
function App() {
  const [activePanel, setActivePanel] = useState<PanelId>('sites')
  const active = PANELS.find((p) => p.id === activePanel) ?? PANELS[0]

  return (
    <div className={styles.layout}>
      <header className={styles.header}>
        <h1>Recipe Scraper — Management UI</h1>
        <p className={styles.subtitle}>Sites, scrape jobs, and recipe review</p>
      </header>

      <nav className={styles.nav}>
        {PANELS.map((panel) => (
          <button
            key={panel.id}
            type="button"
            className={`${styles.navButton} ${
              panel.id === activePanel ? styles.navButtonActive : ''
            }`}
            onClick={() => setActivePanel(panel.id)}
          >
            {panel.label}
          </button>
        ))}
      </nav>

      <main className={styles.main}>{active.render()}</main>
    </div>
  )
}

export default App
