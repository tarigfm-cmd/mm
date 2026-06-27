import { create } from 'zustand'
import { devtools } from 'zustand/middleware'
import type { Material, Scenario, Interaction } from '@/types'

/**
 * Platform-wide Zustand store.
 *
 * Phase 1 holds content (materials) and learning (scenarios/interactions).
 * Future slices — users, assessments, analytics, OSCE, games — will be
 * added here or in dedicated sibling stores as the platform grows.
 */
interface AppState {
  // Content
  materials: Material[]
  materialsTotal: number
  materialsLoading: boolean

  // Learning — scenario list
  scenarios: Scenario[]
  scenariosTotal: number
  scenariosLoading: boolean

  // Learning — active session
  currentScenario: Scenario | null
  currentInteractions: Interaction[]
  interactionsLoading: boolean
  answerSubmitting: boolean

  // Actions — content
  setMaterials: (items: Material[], total: number) => void
  setMaterialsLoading: (v: boolean) => void
  addMaterial: (m: Material) => void
  removeMaterial: (id: string) => void

  // Actions — scenarios
  setScenarios: (items: Scenario[], total: number) => void
  setScenariosLoading: (v: boolean) => void
  addScenario: (s: Scenario) => void

  // Actions — active session
  setCurrentScenario: (s: Scenario | null) => void
  setCurrentInteractions: (items: Interaction[]) => void
  appendInteraction: (i: Interaction) => void
  setInteractionsLoading: (v: boolean) => void
  setAnswerSubmitting: (v: boolean) => void
}

export const useAppStore = create<AppState>()(
  devtools(
    (set) => ({
      materials: [],
      materialsTotal: 0,
      materialsLoading: false,

      scenarios: [],
      scenariosTotal: 0,
      scenariosLoading: false,

      currentScenario: null,
      currentInteractions: [],
      interactionsLoading: false,
      answerSubmitting: false,

      setMaterials: (items, total) => set({ materials: items, materialsTotal: total }),
      setMaterialsLoading: (v) => set({ materialsLoading: v }),
      addMaterial: (m) => set((s) => ({ materials: [m, ...s.materials], materialsTotal: s.materialsTotal + 1 })),
      removeMaterial: (id) =>
        set((s) => ({
          materials: s.materials.filter((m) => m.id !== id),
          materialsTotal: Math.max(0, s.materialsTotal - 1),
        })),

      setScenarios: (items, total) => set({ scenarios: items, scenariosTotal: total }),
      setScenariosLoading: (v) => set({ scenariosLoading: v }),
      addScenario: (s) =>
        set((st) => ({ scenarios: [s, ...st.scenarios], scenariosTotal: st.scenariosTotal + 1 })),

      setCurrentScenario: (s) => set({ currentScenario: s, currentInteractions: [] }),
      setCurrentInteractions: (items) => set({ currentInteractions: items }),
      appendInteraction: (i) =>
        set((s) => ({ currentInteractions: [...s.currentInteractions, i] })),
      setInteractionsLoading: (v) => set({ interactionsLoading: v }),
      setAnswerSubmitting: (v) => set({ answerSubmitting: v }),
    }),
    { name: 'pharmlearn-ai' },
  ),
)

/** @deprecated Use useAppStore */
export const useScenarioStore = useAppStore
