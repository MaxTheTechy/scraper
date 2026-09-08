import { useState } from 'react'
import type { RecipeStatus } from '../../api/types'
import { RecipeDetail } from './RecipeDetail'
import styles from './RecipeReviewPanel.module.css'
import { useRecipesQuery } from './useRecipes'

type StatusFilter = RecipeStatus | 'all'

const STATUS_CLASS: Record<string, string> = {
  pending: styles.statusPending,
  approved: styles.statusApproved,
  rejected: styles.statusRejected,
}

export function RecipeReviewPanel() {
  const recipesQuery = useRecipesQuery()
  // GET /recipes has no status filter param, so we filter the returned list
  // client-side, defaulting to "pending" (the review queue).
  const [statusFilter, setStatusFilter] = useState<StatusFilter>('pending')
  const [selectedId, setSelectedId] = useState<number | null>(null)

  const recipes = recipesQuery.data ?? []
  const filtered =
    statusFilter === 'all' ? recipes : recipes.filter((r) => r.status === statusFilter)

  return (
    <section>
      <h2>Recipe review</h2>
      <div className={styles.layout}>
        <div className={styles.listColumn}>
          <div className={styles.filterRow}>
            <label htmlFor="status-filter">Status:</label>
            <select
              id="status-filter"
              value={statusFilter}
              onChange={(e) => setStatusFilter(e.target.value as StatusFilter)}
            >
              <option value="pending">Pending</option>
              <option value="approved">Approved</option>
              <option value="rejected">Rejected</option>
              <option value="all">All</option>
            </select>
          </div>

          {recipesQuery.isLoading && <p>Loading recipes…</p>}
          {recipesQuery.isError && (
            <p className={styles.error}>
              Failed to load recipes: {(recipesQuery.error as Error).message}
            </p>
          )}

          {recipesQuery.data && (
            <div className={styles.list}>
              {filtered.map((recipe) => (
                <button
                  key={recipe.id}
                  type="button"
                  className={`${styles.listItem} ${
                    recipe.id === selectedId ? styles.listItemSelected : ''
                  }`}
                  onClick={() => setSelectedId(recipe.id)}
                >
                  <span className={styles.listItemTitle}>{recipe.title}</span>
                  <span className={styles.listItemMeta}>
                    {recipe.cuisine ?? 'Uncategorized'} ·{' '}
                    <span className={STATUS_CLASS[recipe.status] ?? ''}>{recipe.status}</span>
                  </span>
                </button>
              ))}
              {filtered.length === 0 && (
                <div className={styles.empty}>No recipes match this filter.</div>
              )}
            </div>
          )}
        </div>

        <div>{selectedId != null && <RecipeDetail key={selectedId} recipeId={selectedId} />}</div>
      </div>
    </section>
  )
}
