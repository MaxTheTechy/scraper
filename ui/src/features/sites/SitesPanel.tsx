import { useState } from 'react'
import styles from './SitesPanel.module.css'
import { useCreateSiteMutation, useSitesQuery, useTriggerScrapeMutation } from './useSites'

function formatTimestamp(value: string | null): string {
  if (!value) return '—'
  return new Date(value).toLocaleString()
}

// TODO: spec Section 7 calls for remove/enable/disable controls here too,
// but api/routers/sites.py only implements GET /sites, POST /sites, and
// POST /sites/{id}/scrape — no PATCH/DELETE /sites/{id} exists yet. Add
// those controls once the backend exposes an endpoint for them; don't
// fabricate one on the frontend.
export function SitesPanel() {
  const sitesQuery = useSitesQuery()
  const createSite = useCreateSiteMutation()
  const triggerScrape = useTriggerScrapeMutation()

  const [url, setUrl] = useState('')
  const [name, setName] = useState('')

  function handleSubmit(event: React.FormEvent) {
    event.preventDefault()
    if (!url.trim()) return
    createSite.mutate(
      { url: url.trim(), name: name.trim() || undefined },
      {
        onSuccess: () => {
          setUrl('')
          setName('')
        },
      },
    )
  }

  return (
    <section className={styles.panel}>
      <h2>Sites</h2>

      <form className={styles.form} onSubmit={handleSubmit}>
        <label className={styles.field}>
          URL
          <input
            type="url"
            placeholder="https://example.com/recipes"
            value={url}
            onChange={(e) => setUrl(e.target.value)}
            required
          />
        </label>
        <label className={styles.field}>
          Name (optional)
          <input
            type="text"
            placeholder="Example Recipes"
            value={name}
            onChange={(e) => setName(e.target.value)}
          />
        </label>
        <button type="submit" disabled={createSite.isPending}>
          {createSite.isPending ? 'Adding…' : 'Add site'}
        </button>
      </form>
      {createSite.isError && (
        <p className={styles.error}>
          Failed to add site: {(createSite.error as Error).message}
        </p>
      )}

      {sitesQuery.isLoading && <p>Loading sites…</p>}
      {sitesQuery.isError && (
        <p className={styles.error}>
          Failed to load sites: {(sitesQuery.error as Error).message}
        </p>
      )}

      {sitesQuery.data && (
        <table className={styles.table}>
          <thead>
            <tr>
              <th>Name</th>
              <th>URL</th>
              <th>Enabled</th>
              <th>Last scraped</th>
              <th>Created</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            {sitesQuery.data.map((site) => (
              <tr key={site.id}>
                <td>{site.name || <em>(unnamed)</em>}</td>
                <td>
                  <a href={site.url} target="_blank" rel="noreferrer">
                    {site.url}
                  </a>
                </td>
                <td className={site.enabled ? styles.badgeEnabled : styles.badgeDisabled}>
                  {site.enabled ? 'Enabled' : 'Disabled'}
                </td>
                <td>{formatTimestamp(site.last_scraped)}</td>
                <td>{formatTimestamp(site.created_at)}</td>
                <td>
                  <button
                    type="button"
                    disabled={triggerScrape.isPending}
                    onClick={() => triggerScrape.mutate(site.id)}
                  >
                    Scrape now
                  </button>
                </td>
              </tr>
            ))}
            {sitesQuery.data.length === 0 && (
              <tr>
                <td colSpan={6}>No sites yet — add one above.</td>
              </tr>
            )}
          </tbody>
        </table>
      )}

      {triggerScrape.isError && (
        <p className={styles.error}>
          Failed to trigger scrape: {(triggerScrape.error as Error).message}
        </p>
      )}
      {triggerScrape.isSuccess && (
        <p>Scrape queued (task {triggerScrape.data.task_id}).</p>
      )}
    </section>
  )
}
