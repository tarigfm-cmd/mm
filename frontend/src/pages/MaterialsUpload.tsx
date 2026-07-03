import { useEffect, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import {
  TrashIcon,
  SparklesIcon,
  DocumentTextIcon,
  CheckCircleIcon,
  ClockIcon,
} from '@heroicons/react/24/outline'
import toast from 'react-hot-toast'
import { materialsApi, scenariosApi } from '@/services/api'
import { useScenarioStore } from '@/store/appStore'
import UploadDropzone from '@/components/UploadDropzone'
import LoadingSpinner from '@/components/LoadingSpinner'
import type { Material, DifficultyLevel, UploadProgress } from '@/types'
import { format } from 'date-fns'

function formatBytes(bytes: number) {
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1_048_576) return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / 1_048_576).toFixed(1)} MB`
}

export default function MaterialsUpload() {
  const navigate = useNavigate()
  const { materials, materialsTotal, setMaterials, setMaterialsLoading, addMaterial, removeMaterial, materialsLoading } =
    useScenarioStore()

  const [uploadState, setUploadState] = useState<UploadProgress | null>(null)
  const [titleInput, setTitleInput] = useState('')
  const [descInput, setDescInput] = useState('')
  const [pendingFile, setPendingFile] = useState<File | null>(null)
  const [generatingFor, setGeneratingFor] = useState<string | null>(null)
  const [difficulty, setDifficulty] = useState<DifficultyLevel>('intermediate')
  const pollingRef = useRef<ReturnType<typeof setInterval> | null>(null)

  useEffect(() => {
    loadMaterials()
    return () => {
      if (pollingRef.current) clearInterval(pollingRef.current)
    }
  }, [])

  const loadMaterials = async () => {
    setMaterialsLoading(true)
    try {
      const res = await materialsApi.list()
      setMaterials(res.items, res.total)
    } finally {
      setMaterialsLoading(false)
    }
  }

  const handleFilesSelected = (files: File[]) => {
    const file = files[0] ?? null
    setPendingFile(file)
    if (file && !titleInput) {
      setTitleInput(file.name.replace(/\.[^.]+$/, '').replace(/[-_]/g, ' '))
    }
  }

  const handleUpload = async () => {
    if (!pendingFile || !titleInput.trim()) {
      toast.error('Please select a file and enter a title.')
      return
    }

    setUploadState({ fileName: pendingFile.name, progress: 0, status: 'uploading' })

    try {
      const material = await materialsApi.upload(
        pendingFile,
        titleInput.trim(),
        descInput.trim(),
        (pct) => setUploadState((s) => s && { ...s, progress: pct }),
      )
      setUploadState({ fileName: pendingFile.name, progress: 100, status: 'processing' })
      addMaterial(material)
      setPendingFile(null)
      setTitleInput('')
      setDescInput('')
      toast.success('Material uploaded! Text extraction in progress…')

      // Poll until content_text is available (background task)
      const poll = setInterval(async () => {
        const refreshed = await materialsApi.get(material.id)
        if (refreshed.has_content) {
          clearInterval(poll)
          setUploadState((s) => s && { ...s, status: 'done', materialId: material.id })
          setMaterials(
            materials.map((m) => (m.id === material.id ? { ...m, has_content: true } : m)),
            materialsTotal,
          )
          toast.success('Content extracted — ready to generate scenarios!')
        }
      }, 3000)
      pollingRef.current = poll
    } catch {
      setUploadState((s) => s && { ...s, status: 'error' })
    }
  }

  const handleDelete = async (id: string) => {
    if (!confirm('Delete this material and all its scenarios?')) return
    try {
      await materialsApi.delete(id)
      removeMaterial(id)
      toast.success('Material deleted.')
    } catch {}
  }

  const handleGenerate = async (material: Material) => {
    if (!material.has_content) {
      toast.error('Content is still being extracted. Please wait a moment.')
      return
    }
    setGeneratingFor(material.id)
    try {
      const scenario = await scenariosApi.generate({
        material_id: material.id,
        difficulty_level: difficulty,
      })
      toast.success(`Scenario "${scenario.title}" created!`)
      navigate(`/scenarios/${scenario.id}`)
    } catch {
      // error toast handled by interceptor
    } finally {
      setGeneratingFor(null)
    }
  }

  return (
    <div className="space-y-8">
      <div>
        <h1 className="text-2xl font-bold text-gray-900">Upload Study Material</h1>
        <p className="mt-1 text-sm text-gray-500">
          Upload clinical resources — drug monographs, guidelines, textbook chapters — to generate AI case scenarios.
        </p>
      </div>

      {/* Upload form */}
      <div className="bg-white rounded-xl border border-gray-200 p-6 space-y-4">
        <UploadDropzone onFilesSelected={handleFilesSelected} />

        {pendingFile && (
          <div className="space-y-3">
            <div>
              <label className="block text-xs font-medium text-gray-700 mb-1">
                Title <span className="text-red-500">*</span>
              </label>
              <input
                type="text"
                value={titleInput}
                onChange={(e) => setTitleInput(e.target.value)}
                className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-primary-500"
                placeholder="e.g. Metformin Pharmacology Overview"
              />
            </div>
            <div>
              <label className="block text-xs font-medium text-gray-700 mb-1">Description</label>
              <textarea
                value={descInput}
                onChange={(e) => setDescInput(e.target.value)}
                rows={2}
                className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-primary-500 resize-none"
                placeholder="Optional description of the material"
              />
            </div>
            <button
              onClick={handleUpload}
              disabled={!!uploadState && uploadState.status === 'uploading'}
              className="px-5 py-2 bg-primary-600 text-white text-sm font-medium rounded-lg hover:bg-primary-700 disabled:opacity-50 transition-colors"
            >
              {uploadState?.status === 'uploading'
                ? `Uploading… ${uploadState.progress}%`
                : 'Upload'}
            </button>
          </div>
        )}

        {uploadState && uploadState.status === 'processing' && (
          <div className="flex items-center gap-2 text-sm text-amber-600 bg-amber-50 rounded-lg px-3 py-2">
            <ClockIcon className="w-4 h-4 animate-pulse" />
            Extracting text from document…
          </div>
        )}
        {uploadState && uploadState.status === 'done' && (
          <div className="flex items-center gap-2 text-sm text-clinical-700 bg-clinical-50 rounded-lg px-3 py-2">
            <CheckCircleIcon className="w-4 h-4" />
            Ready to generate scenarios!
          </div>
        )}
      </div>

      {/* Materials list */}
      <section>
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-lg font-semibold text-gray-900">
            Your Materials
            <span className="ml-2 text-sm font-normal text-gray-400">({materialsTotal})</span>
          </h2>
          <div className="flex items-center gap-2">
            <label className="text-xs text-gray-500">Difficulty:</label>
            <select
              value={difficulty}
              onChange={(e) => setDifficulty(e.target.value as DifficultyLevel)}
              className="text-xs border border-gray-300 rounded-lg px-2 py-1 focus:outline-none focus:ring-1 focus:ring-primary-500"
            >
              <option value="beginner">Beginner</option>
              <option value="intermediate">Intermediate</option>
              <option value="advanced">Advanced</option>
            </select>
          </div>
        </div>

        {materialsLoading ? (
          <LoadingSpinner label="Loading materials…" />
        ) : materials.length === 0 ? (
          <p className="text-center py-10 text-sm text-gray-400">No materials uploaded yet.</p>
        ) : (
          <ul className="space-y-3">
            {materials.map((m) => (
              <li
                key={m.id}
                className="flex items-center gap-4 bg-white rounded-xl border border-gray-200 px-5 py-4"
              >
                <div className="flex-shrink-0 w-9 h-9 bg-gray-100 rounded-lg flex items-center justify-center">
                  <DocumentTextIcon className="w-5 h-5 text-gray-500" />
                </div>
                <div className="flex-1 min-w-0">
                  <p className="text-sm font-medium text-gray-900 truncate">{m.title}</p>
                  <p className="text-xs text-gray-400 mt-0.5">
                    {m.file_type.toUpperCase()} · {formatBytes(m.file_size)} ·{' '}
                    {format(new Date(m.created_at), 'MMM d, yyyy')} ·{' '}
                    {m.scenario_count} scenario{m.scenario_count !== 1 ? 's' : ''}
                  </p>
                </div>
                <div className="flex items-center gap-2">
                  {!m.has_content && (
                    <span className="text-xs text-amber-600 bg-amber-50 px-2 py-0.5 rounded-full">
                      Extracting…
                    </span>
                  )}
                  <button
                    onClick={() => handleGenerate(m)}
                    disabled={!m.has_content || generatingFor === m.id}
                    className="inline-flex items-center gap-1.5 px-3 py-1.5 bg-primary-600 text-white text-xs font-medium rounded-lg hover:bg-primary-700 disabled:opacity-50 transition-colors"
                  >
                    {generatingFor === m.id ? (
                      <>
                        <LoadingSpinner size="sm" />
                        Generating…
                      </>
                    ) : (
                      <>
                        <SparklesIcon className="w-3.5 h-3.5" />
                        Generate
                      </>
                    )}
                  </button>
                  <button
                    onClick={() => handleDelete(m.id)}
                    className="p-1.5 text-gray-400 hover:text-red-500 transition-colors rounded-lg hover:bg-red-50"
                    title="Delete material"
                  >
                    <TrashIcon className="w-4 h-4" />
                  </button>
                </div>
              </li>
            ))}
          </ul>
        )}
      </section>
    </div>
  )
}
