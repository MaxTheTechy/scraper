import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { createSite, fetchSites, triggerScrape } from '../../api/client'
import type { SiteCreate } from '../../api/types'

const SITES_KEY = ['sites'] as const

export function useSitesQuery() {
  return useQuery({ queryKey: SITES_KEY, queryFn: fetchSites })
}

export function useCreateSiteMutation() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (payload: SiteCreate) => createSite(payload),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: SITES_KEY })
    },
  })
}

export function useTriggerScrapeMutation() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (siteId: number) => triggerScrape(siteId),
    onSuccess: () => {
      // A newly queued job should show up in the scrape queue panel, and
      // last_scraped will eventually update once the job completes.
      queryClient.invalidateQueries({ queryKey: ['scrape-jobs'] })
    },
  })
}
