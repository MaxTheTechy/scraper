import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { fetchRecipe, fetchRecipes, updateRecipeStatus } from '../../api/client'
import type { RecipeStatusUpdate } from '../../api/types'

const RECIPES_KEY = ['recipes'] as const

// GET /recipes?status= filters server-side (api/routers/recipes.py) so a
// dedicated view (e.g. "duplicate") doesn't have to fetch every recipe row
// as the dataset grows with multi-site scraping.
export function useRecipesQuery(status?: string) {
  return useQuery({
    queryKey: [...RECIPES_KEY, status ?? 'all'],
    queryFn: () => fetchRecipes({ limit: 200, status }),
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
