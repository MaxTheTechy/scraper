// Single home for all fetch calls (frontend-ui skill convention: no inline
// fetch() in components). Base path is /api — in production Nginx proxies
// /api/ -> http://127.0.0.1:8000/ (spec Section 9); in dev, vite.config.ts
// proxies the same way so components never need to know the difference.
import type {
  Ingredient,
  Recipe,
  RecipeListItem,
  RecipeStatusUpdate,
  ScrapeJobsResponse,
  ScrapeTriggerResponse,
  Site,
  SiteCreate,
} from './types'

const BASE = '/api'

export class ApiError extends Error {
  status: number
  constructor(status: number, message: string) {
    super(message)
    this.name = 'ApiError'
    this.status = status
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    headers: { 'Content-Type': 'application/json', ...(init?.headers ?? {}) },
    ...init,
  })
  if (!res.ok) {
    const detail = await res.text().catch(() => '')
    throw new ApiError(res.status, detail || `${res.status} ${res.statusText}`)
  }
  if (res.status === 204) return undefined as T
  return (await res.json()) as T
}

// --- Sites ---

export function fetchSites(): Promise<Site[]> {
  return request<Site[]>('/sites')
}

export function createSite(payload: SiteCreate): Promise<Site> {
  return request<Site>('/sites', {
    method: 'POST',
    body: JSON.stringify(payload),
  })
}

export function triggerScrape(siteId: number): Promise<ScrapeTriggerResponse> {
  return request<ScrapeTriggerResponse>(`/sites/${siteId}/scrape`, {
    method: 'POST',
  })
}

// --- Scrape jobs ---

export function fetchScrapeJobs(): Promise<ScrapeJobsResponse> {
  return request<ScrapeJobsResponse>('/scrape/jobs')
}

// --- Recipes ---

export interface ListRecipesParams {
  cuisine?: string
  tag?: string
  limit?: number
  offset?: number
}

export function fetchRecipes(params: ListRecipesParams = {}): Promise<RecipeListItem[]> {
  const search = new URLSearchParams()
  if (params.cuisine) search.set('cuisine', params.cuisine)
  if (params.tag) search.set('tag', params.tag)
  if (params.limit != null) search.set('limit', String(params.limit))
  if (params.offset != null) search.set('offset', String(params.offset))
  const qs = search.toString()
  return request<RecipeListItem[]>(`/recipes${qs ? `?${qs}` : ''}`)
}

export function fetchRecipe(id: number): Promise<Recipe> {
  return request<Recipe>(`/recipes/${id}`)
}

export function searchRecipes(q: string, limit = 50, offset = 0): Promise<RecipeListItem[]> {
  return request<RecipeListItem[]>('/recipes/search', {
    method: 'POST',
    body: JSON.stringify({ q, limit, offset }),
  })
}

// Approve/reject only — the backend's PATCH /recipes/{id}/status endpoint
// (api/schemas/recipe.py: RecipeStatusUpdate) accepts nothing but
// {"status": "approved" | "rejected"}. There is no content-editing endpoint
// yet, so this client intentionally does not expose one — see the TODO in
// features/recipe-review/RecipeDetail.tsx.
export function updateRecipeStatus(id: number, payload: RecipeStatusUpdate): Promise<Recipe> {
  return request<Recipe>(`/recipes/${id}/status`, {
    method: 'PATCH',
    body: JSON.stringify(payload),
  })
}

// --- Ingredients ---

// GET /ingredients returns distinct ingredient *names* (list[str]) per
// api/routers/ingredients.py — it's a name lookup/autocomplete endpoint,
// not a list of Ingredient objects.
export function fetchIngredientNames(q?: string, limit = 20): Promise<string[]> {
  const search = new URLSearchParams()
  if (q) search.set('q', q)
  search.set('limit', String(limit))
  return request<string[]>(`/ingredients?${search.toString()}`)
}

export type { Ingredient, Recipe, RecipeListItem, Site, SiteCreate }
