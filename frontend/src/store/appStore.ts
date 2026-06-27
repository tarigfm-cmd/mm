import { create } from 'zustand'
import { devtools } from 'zustand/middleware'
import type { Material, Scenario, Interaction, UserRead } from '@/types'

interface AppState {
  // Auth
  currentUser: UserRead | null
  accessToken: string | null
  authInitialized: boolean

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

  // Actions — auth
  setCurrentUser: (user: UserRead | null) => void
  setAccessToken: (token: string | null) => void
  setAuthInitialized: (v: boolean) => void
  clearAuth: () => void

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
      currentUser: null,
      accessToken: null,
      authInitialized: false,

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

      setCurrentUser: (user) => set({ currentUser: user }),
      setAccessToken: (token) => set({ accessToken: token }),
      setAuthInitialized: (v) => set({ authInitialized: v }),
      clearAuth: () => set({ currentUser: null, accessToken: null }),

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
