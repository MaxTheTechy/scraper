// Types mirror the FastAPI Pydantic schemas exactly (api/schemas/*.py) —
// field names are kept as-is (snake_case) per the frontend-ui skill
// convention: don't relabel backend fields in the UI layer.

export type RecipeStatus = 'pending' | 'approved' | 'rejected' | 'duplicate'

export interface Site {
  id: number
  url: string
  name: string | null
  enabled: boolean
  last_scraped: string | null
  consecutive_failures: number
  created_at: string
}

export interface SiteCreate {
  url: string
  name?: string | null
}

export interface SiteUpdate {
  enabled?: boolean
  name?: string
}

export interface Ingredient {
  id: number
  recipe_id: number
  name: string
  quantity: number | null
  unit: string | null
  notes: string | null
}

// Shape returned by GET /recipes and POST /recipes/search — no ingredients
// nested (api/schemas/recipe.py: RecipeListItem).
export interface RecipeListItem {
  id: number
  site_id: number | null
  title: string
  cuisine: string | null
  description: string | null
  prep_time: number | null
  cook_time: number | null
  servings: number | null
  method: string[] | null
  tags: string[] | null
  source_url: string | null
  image_url: string | null
  image_path: string | null
  status: RecipeStatus | string
  duplicate_of_id: number | null
  scraped_at: string
}

// Shape returned by GET /recipes/{id} — includes ingredients
// (api/schemas/recipe.py: RecipeRead).
export interface Recipe extends RecipeListItem {
  ingredients: Ingredient[]
}

export interface RecipeStatusUpdate {
  status: 'pending' | 'approved' | 'rejected' | 'duplicate'
}

// Celery inspect() payloads carry many more fields than we care about
// (delivery_info, worker_pid, time_start, ...) — keep the ones the UI
// renders typed and allow the rest through untyped.
export interface ScrapeJob {
  id: string
  name?: string
  args?: unknown[]
  kwargs?: Record<string, unknown>
  worker: string
  state: 'active' | 'reserved'
  [key: string]: unknown
}

export interface ScrapeJobsResponse {
  jobs: ScrapeJob[]
}

export interface ScrapeTriggerResponse {
  task_id: string
  site_id: number
  status: string
}
