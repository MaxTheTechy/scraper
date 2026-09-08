import { useQuery } from '@tanstack/react-query'
import { fetchScrapeJobs } from '../../api/client'

// Live job status — poll every 5s rather than relying on manual refresh.
export function useScrapeJobsQuery() {
  return useQuery({
    queryKey: ['scrape-jobs'],
    queryFn: fetchScrapeJobs,
    refetchInterval: 5000,
  })
}
