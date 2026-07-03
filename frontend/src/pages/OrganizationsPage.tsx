import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import {
  BuildingLibraryIcon,
  PlusIcon,
  UsersIcon,
  ChevronRightIcon,
} from '@heroicons/react/24/outline'
import toast from 'react-hot-toast'
import { orgsApi } from '@/services/api'
import type { OrgType, OrgWithRole } from '@/types'
import LoadingSpinner from '@/components/LoadingSpinner'

const ORG_TYPE_LABELS: Record<OrgType, string> = {
  university: 'University',
  pharmacy_chain: 'Pharmacy Chain',
  hospital: 'Hospital',
  training_center: 'Training Center',
  enterprise: 'Enterprise',
  individual_workspace: 'Personal Workspace',
}

const ORG_TYPE_COLORS: Record<OrgType, string> = {
  university: 'bg-blue-50 text-blue-700',
  pharmacy_chain: 'bg-primary-50 text-primary-700',
  hospital: 'bg-red-50 text-red-700',
  training_center: 'bg-amber-50 text-amber-700',
  enterprise: 'bg-purple-50 text-purple-700',
  individual_workspace: 'bg-gray-100 text-gray-700',
}

function slugify(name: string): string {
  return name
    .toLowerCase()
    .replace(/[^a-z0-9\s-]/g, '')
    .replace(/\s+/g, '-')
    .replace(/-+/g, '-')
    .slice(0, 100)
}

interface CreateOrgModalProps {
  onClose: () => void
  onCreated: (org: OrgWithRole) => void
}

function CreateOrgModal({ onClose, onCreated }: CreateOrgModalProps) {
  const [name, setName] = useState('')
  const [slug, setSlug] = useState('')
  const [orgType, setOrgType] = useState<OrgType>('individual_workspace')
  const [autoSlug, setAutoSlug] = useState(true)
  const [loading, setLoading] = useState(false)

  const handleNameChange = (v: string) => {
    setName(v)
    if (autoSlug) setSlug(slugify(v))
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!name.trim() || !slug.trim()) return

    setLoading(true)
    try {
      const org = await orgsApi.create({ name: name.trim(), slug: slug.trim(), org_type: orgType })
      toast.success(`Organization "${org.name}" created!`)
      onCreated({ ...org, member_role: 'institution_admin', member_count: 1 })
    } catch {
      // toast shown by interceptor
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/40 backdrop-blur-sm">
      <div className="bg-white rounded-2xl shadow-2xl w-full max-w-md p-6">
        <h2 className="text-lg font-semibold text-gray-900 mb-4">Create organization</h2>

        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label className="block text-xs font-medium text-gray-700 mb-1">
              Name <span className="text-red-500">*</span>
            </label>
            <input
              type="text"
              required
              value={name}
              onChange={(e) => handleNameChange(e.target.value)}
              placeholder="City University Pharmacy School"
              className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-primary-500"
            />
          </div>

          <div>
            <label className="block text-xs font-medium text-gray-700 mb-1">
              Slug <span className="text-red-500">*</span>
              <span className="text-gray-400 font-normal ml-1">(URL identifier)</span>
            </label>
            <input
              type="text"
              required
              value={slug}
              onChange={(e) => { setAutoSlug(false); setSlug(e.target.value) }}
              placeholder="city-university"
              pattern="^[a-z0-9-]+$"
              className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm font-mono focus:outline-none focus:ring-2 focus:ring-primary-500"
            />
          </div>

          <div>
            <label className="block text-xs font-medium text-gray-700 mb-1">
              Organization type
            </label>
            <select
              value={orgType}
              onChange={(e) => setOrgType(e.target.value as OrgType)}
              className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-primary-500"
            >
              {Object.entries(ORG_TYPE_LABELS).map(([value, label]) => (
                <option key={value} value={value}>{label}</option>
              ))}
            </select>
          </div>

          <div className="flex gap-3 pt-2">
            <button
              type="button"
              onClick={onClose}
              className="flex-1 px-4 py-2 border border-gray-300 text-gray-700 text-sm font-medium rounded-lg hover:bg-gray-50 transition-colors"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={loading || !name.trim() || !slug.trim()}
              className="flex-1 px-4 py-2 bg-primary-600 text-white text-sm font-medium rounded-lg hover:bg-primary-700 disabled:opacity-50 transition-colors"
            >
              {loading ? 'Creating…' : 'Create'}
            </button>
          </div>
        </form>
      </div>
    </div>
  )
}

export default function OrganizationsPage() {
  const navigate = useNavigate()
  const [orgs, setOrgs] = useState<OrgWithRole[]>([])
  const [loading, setLoading] = useState(true)
  const [showCreate, setShowCreate] = useState(false)

  useEffect(() => {
    loadOrgs()
  }, [])

  const loadOrgs = async () => {
    setLoading(true)
    try {
      const data = await orgsApi.list()
      setOrgs(data)
    } finally {
      setLoading(false)
    }
  }

  const handleCreated = (org: OrgWithRole) => {
    setOrgs((prev) => [org, ...prev])
    setShowCreate(false)
  }

  return (
    <div className="space-y-6">
      <div className="flex items-start justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Organizations</h1>
          <p className="mt-1 text-sm text-gray-500">
            Manage your workspaces and team memberships
          </p>
        </div>
        <button
          onClick={() => setShowCreate(true)}
          className="inline-flex items-center gap-2 px-4 py-2 bg-primary-600 text-white text-sm font-medium rounded-lg hover:bg-primary-700 transition-colors"
        >
          <PlusIcon className="w-4 h-4" />
          New organization
        </button>
      </div>

      {loading ? (
        <LoadingSpinner label="Loading organizations…" />
      ) : orgs.length === 0 ? (
        <div className="text-center py-16 bg-gray-50 rounded-xl border border-dashed border-gray-300">
          <BuildingLibraryIcon className="mx-auto h-10 w-10 text-gray-300 mb-3" />
          <p className="text-sm font-medium text-gray-500">No organizations yet</p>
          <p className="text-xs text-gray-400 mt-1">
            Create a workspace to collaborate with your team
          </p>
          <button
            onClick={() => setShowCreate(true)}
            className="mt-4 px-4 py-2 bg-primary-600 text-white text-sm font-medium rounded-lg hover:bg-primary-700 transition-colors"
          >
            Create organization
          </button>
        </div>
      ) : (
        <ul className="space-y-3">
          {orgs.map((org) => (
            <li key={org.id}>
              <button
                onClick={() => navigate(`/orgs/${org.slug}`)}
                className="w-full flex items-center gap-4 bg-white rounded-xl border border-gray-200 px-5 py-4 hover:shadow-sm hover:border-gray-300 transition-all text-left"
              >
                <div className="flex-shrink-0 w-10 h-10 bg-primary-50 rounded-xl flex items-center justify-center">
                  <BuildingLibraryIcon className="w-5 h-5 text-primary-600" />
                </div>
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 flex-wrap">
                    <p className="text-sm font-semibold text-gray-900 truncate">{org.name}</p>
                    <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${ORG_TYPE_COLORS[org.org_type]}`}>
                      {ORG_TYPE_LABELS[org.org_type]}
                    </span>
                  </div>
                  <div className="flex items-center gap-3 mt-1">
                    <span className="text-xs text-gray-400 font-mono">{org.slug}</span>
                    <span className="text-xs text-gray-300">·</span>
                    <span className="inline-flex items-center gap-1 text-xs text-gray-400">
                      <UsersIcon className="w-3.5 h-3.5" />
                      {org.member_count} member{org.member_count !== 1 ? 's' : ''}
                    </span>
                    <span className="text-xs text-gray-300">·</span>
                    <span className="text-xs text-gray-500 capitalize">
                      {org.member_role.replace(/_/g, ' ')}
                    </span>
                  </div>
                </div>
                <ChevronRightIcon className="w-4 h-4 text-gray-400 flex-shrink-0" />
              </button>
            </li>
          ))}
        </ul>
      )}

      {showCreate && (
        <CreateOrgModal onClose={() => setShowCreate(false)} onCreated={handleCreated} />
      )}
    </div>
  )
}
