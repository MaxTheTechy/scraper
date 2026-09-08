import styles from './ScrapeQueuePanel.module.css'
import { useScrapeJobsQuery } from './useScrapeJobs'

export function ScrapeQueuePanel() {
  const jobsQuery = useScrapeJobsQuery()
  const jobs = jobsQuery.data?.jobs ?? []

  return (
    <section className={styles.panel}>
      <h2>Scrape queue</h2>
      <p className={styles.hint}>Refreshes automatically every 5 seconds.</p>

      {jobsQuery.isLoading && <p>Loading jobs…</p>}
      {jobsQuery.isError && (
        <p className={styles.error}>
          Failed to load scrape jobs: {(jobsQuery.error as Error).message}
        </p>
      )}

      {jobsQuery.data && (
        <table className={styles.table}>
          <thead>
            <tr>
              <th>Task ID</th>
              <th>Task</th>
              <th>Worker</th>
              <th>State</th>
              <th>Args</th>
            </tr>
          </thead>
          <tbody>
            {jobs.map((job) => (
              <tr key={job.id}>
                <td>{job.id}</td>
                <td>{job.name ?? '—'}</td>
                <td>{job.worker}</td>
                <td className={job.state === 'active' ? styles.stateActive : styles.stateReserved}>
                  {job.state}
                </td>
                <td className={styles.args}>
                  {job.args && job.args.length > 0 ? JSON.stringify(job.args) : '—'}
                </td>
              </tr>
            ))}
            {jobs.length === 0 && (
              <tr>
                <td colSpan={5}>No active or queued scrape jobs.</td>
              </tr>
            )}
          </tbody>
        </table>
      )}
    </section>
  )
}
