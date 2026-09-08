import { useState } from 'react'
import { ImagePreview } from '../images/ImagePreview'
import { IngredientEditor } from '../ingredients/IngredientEditor'
import styles from './RecipeDetail.module.css'
import { useRecipeQuery, useUpdateRecipeStatusMutation } from './useRecipes'

interface RecipeDetailProps {
  recipeId: number
}

// TODO: PATCH /recipes/{id}/status (api/schemas/recipe.py: RecipeStatusUpdate)
// only accepts {"status": "approved" | "rejected"} — there is no endpoint to
// save edited content (title/description/tags/method). The fields below are
// editable in local state so a reviewer can see what a "fix before approve"
// flow would look like, but edits are NOT sent anywhere; only the
// approve/reject status change actually persists. Wire up real saving once
// a PATCH /recipes/{id} (content) endpoint exists on the backend — don't
// fabricate one here.
export function RecipeDetail({ recipeId }: RecipeDetailProps) {
  const recipeQuery = useRecipeQuery(recipeId)
  const updateStatus = useUpdateRecipeStatusMutation()
  const recipe = recipeQuery.data

  const [titleDraft, setTitleDraft] = useState('')
  const [descriptionDraft, setDescriptionDraft] = useState('')
  const [tagsDraft, setTagsDraft] = useState('')
  const [initializedFor, setInitializedFor] = useState<number | null>(null)

  if (recipe && initializedFor !== recipe.id) {
    setTitleDraft(recipe.title)
    setDescriptionDraft(recipe.description ?? '')
    setTagsDraft((recipe.tags ?? []).join(', '))
    setInitializedFor(recipe.id)
  }

  if (recipeQuery.isLoading) return <p>Loading recipe…</p>
  if (recipeQuery.isError) {
    return <p className={styles.error}>Failed to load recipe: {(recipeQuery.error as Error).message}</p>
  }
  if (!recipe) return null

  return (
    <div className={styles.detail}>
      <p className={styles.notice}>
        Title/description/tags below are editable for review purposes only — there's no backend
        endpoint yet to save content edits. See the TODO in RecipeDetail.tsx.
      </p>

      <div className={styles.header}>
        <ImagePreview imagePath={recipe.image_path} imageUrl={recipe.image_url} title={recipe.title} />

        <div className={styles.fields}>
          <label className={styles.field}>
            Title
            <input value={titleDraft} onChange={(e) => setTitleDraft(e.target.value)} />
          </label>
          <label className={styles.field}>
            Description
            <textarea
              rows={3}
              value={descriptionDraft}
              onChange={(e) => setDescriptionDraft(e.target.value)}
            />
          </label>
          <label className={styles.field}>
            Tags (comma-separated)
            <input value={tagsDraft} onChange={(e) => setTagsDraft(e.target.value)} />
          </label>

          <div className={styles.metaRow}>
            <span>Cuisine: {recipe.cuisine ?? '—'}</span>
            <span>Prep: {recipe.prep_time != null ? `${recipe.prep_time} min` : '—'}</span>
            <span>Cook: {recipe.cook_time != null ? `${recipe.cook_time} min` : '—'}</span>
            <span>Servings: {recipe.servings ?? '—'}</span>
          </div>
          <div className={styles.metaRow}>
            <span>Status: {recipe.status}</span>
            <span>Scraped: {new Date(recipe.scraped_at).toLocaleString()}</span>
            {recipe.source_url && (
              <a href={recipe.source_url} target="_blank" rel="noreferrer">
                Source
              </a>
            )}
          </div>

          <div className={styles.actions}>
            <button
              type="button"
              className={styles.approveButton}
              disabled={updateStatus.isPending || recipe.status === 'approved'}
              onClick={() => updateStatus.mutate({ id: recipe.id, payload: { status: 'approved' } })}
            >
              Approve
            </button>
            <button
              type="button"
              className={styles.rejectButton}
              disabled={updateStatus.isPending || recipe.status === 'rejected'}
              onClick={() => updateStatus.mutate({ id: recipe.id, payload: { status: 'rejected' } })}
            >
              Reject
            </button>
          </div>
          {updateStatus.isError && (
            <p className={styles.error}>
              Failed to update status: {(updateStatus.error as Error).message}
            </p>
          )}
        </div>
      </div>

      {recipe.method && recipe.method.length > 0 && (
        <div className={styles.section}>
          <h3>Method</h3>
          <ol className={styles.methodList}>
            {recipe.method.map((step, i) => (
              <li key={i}>{step}</li>
            ))}
          </ol>
        </div>
      )}

      <div className={styles.section}>
        <h3>Ingredients</h3>
        <IngredientEditor ingredients={recipe.ingredients} />
      </div>
    </div>
  )
}
