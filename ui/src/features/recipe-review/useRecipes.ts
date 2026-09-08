import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { fetchRecipe, fetchRecipes, updateRecipeStatus } from '../../api/client'
import type { RecipeStatusUpdate } from '../../api/types'

const RECIPES_KEY = ['recipes'] as const

// GET /recipes has no status filter param (api/routers/recipes.py only
// supports cuisine/tag/limit/offset) — fetch a reasonably large page and
// filter by status client-side, as instructed by the task brief.
export function useRecipesQuery() {
  return useQuery({
    queryKey: RECIPES_KEY,
    queryFn: () => fetchRecipes({ limit: 200 }),
  })
}

export function useRecipeQuery(id: number | null) {
  return useQuery({
    queryKey: ['recipe', id],
    queryFn: () => fetchRecipe(id as number),
    enabled: id != null,
  })
}

export function useUpdateRecipeStatusMutation() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({ id, payload }: { id: number; payload: RecipeStatusUpdate }) =>
      updateRecipeStatus(id, payload),
    onSuccess: (updated) => {
      queryClient.invalidateQueries({ queryKey: RECIPES_KEY })
      queryClient.setQueryData(['recipe', updated.id], updated)
    },
  })
}
