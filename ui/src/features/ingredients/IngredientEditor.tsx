import { useState } from 'react'
import type { Ingredient } from '../../api/types'
import styles from './IngredientEditor.module.css'

interface IngredientEditorProps {
  ingredients: Ingredient[]
}

interface DraftIngredient {
  draftId: string
  id: number | null
  name: string
  quantity: string
  unit: string
  notes: string
}

let nextDraftId = 0

function toDraft(ingredient: Ingredient): DraftIngredient {
  return {
    draftId: `existing-${ingredient.id}`,
    id: ingredient.id,
    name: ingredient.name,
    quantity: ingredient.quantity != null ? String(ingredient.quantity) : '',
    unit: ingredient.unit ?? '',
    notes: ingredient.notes ?? '',
  }
}

// TODO: there is no backend endpoint to persist ingredient edits yet
// (api/routers/ingredients.py only implements GET /ingredients for
// name lookup/autocomplete — no POST/PATCH/DELETE for a recipe's
// ingredient rows). This editor is local-state only for now: edits are
// held in this component and are lost on navigation/refresh. Wire it up
// to a real mutation (e.g. PATCH /recipes/{id}/ingredients or per-row
// PATCH /ingredients/{id}) once that endpoint exists — don't invent one
// on the frontend in the meantime.
export function IngredientEditor({ ingredients }: IngredientEditorProps) {
  const [drafts, setDrafts] = useState<DraftIngredient[]>(() => ingredients.map(toDraft))

  function updateField(draftId: string, field: keyof DraftIngredient, value: string) {
    setDrafts((prev) =>
      prev.map((d) => (d.draftId === draftId ? { ...d, [field]: value } : d)),
    )
  }

  function removeRow(draftId: string) {
    setDrafts((prev) => prev.filter((d) => d.draftId !== draftId))
  }

  function addRow() {
    setDrafts((prev) => [
      ...prev,
      {
        draftId: `new-${nextDraftId++}`,
        id: null,
        name: '',
        quantity: '',
        unit: '',
        notes: '',
      },
    ])
  }

  return (
    <div className={styles.wrapper}>
      <p className={styles.notice}>
        Ingredient edits are local only right now — there's no backend endpoint yet to save
        changes to ingredients. See the TODO in IngredientEditor.tsx.
      </p>

      <div className={styles.headerRow}>
        <span>Name</span>
        <span>Qty</span>
        <span>Unit</span>
        <span>Notes</span>
        <span />
      </div>

      {drafts.map((draft) => (
        <div className={styles.row} key={draft.draftId}>
          <input
            value={draft.name}
            onChange={(e) => updateField(draft.draftId, 'name', e.target.value)}
            placeholder="ingredient name"
          />
          <input
            value={draft.quantity}
            onChange={(e) => updateField(draft.draftId, 'quantity', e.target.value)}
            placeholder="qty"
            inputMode="decimal"
          />
          <input
            value={draft.unit}
            onChange={(e) => updateField(draft.draftId, 'unit', e.target.value)}
            placeholder="unit"
          />
          <input
            value={draft.notes}
            onChange={(e) => updateField(draft.draftId, 'notes', e.target.value)}
            placeholder="notes"
          />
          <button
            type="button"
            className={styles.removeButton}
            onClick={() => removeRow(draft.draftId)}
            aria-label="Remove ingredient"
          >
            ✕
          </button>
        </div>
      ))}

      <button type="button" className={styles.addButton} onClick={addRow}>
        + Add ingredient
      </button>
    </div>
  )
}
