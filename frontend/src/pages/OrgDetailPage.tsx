import { useEffect, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import {
  ArrowLeftIcon,
  UserPlusIcon,
  TrashIcon,
  ShieldCheckIcon,
} from '@heroicons/react/24/outline'
import toast from 'react-hot-toast'
import { orgsApi, rolesApi } from '@/services/api'
import { useAppStore } from '@/store/appStore'
import type { Member, OrgWithRole, SystemRole } from '@/types'
import LoadingSpinner from '@/components/LoadingSpinner'

const ROLE_ORDER = ['student', 'pharmacist', 'educator', 'content_reviewer', 'institution_admin', 'platform_admin']

function isAdmin(role: string) {
  return role === 'institution_admin' || role === 'platform_admin'
}

function MemberRow({
  member,
  roles,
  isCurrentUser,
  canManage,
  onRoleChange,
  onRemove,
}: {
  member: Member
  roles: SystemRole[]
  isCurrentUser: boolean
  canManage: boolean
  onRoleChange: (userId: string, role: string) => Promise<void>
  onRemove: (userId: string, name: string) => Promise<void>
}) {
  const [updating, setUpdating] = useState(false)

  const handleRoleChange = async (newRole: string) => {
    setUpdating(true)
    try {
      await onRoleChange(member.user_id, newRole)
    } finally {
      setUpdating(false)
    }
  }

  const displayName = member.full_name || member.username

  return (
    <li className="flex items-center gap-4 py-3">
      <div className="w-8 h-8 rounded-full bg-primary-100 text-primary-700 flex items-center justify-center text-xs font-semibold flex-shrink-0">
        {displayName.slice(0, 2).toUpperCase()}
      </div>
      <div className="flex-1 min-w-0">
        <p className="text-sm font-medium text-gray-900 truncate">
          {displayName}
          {isCurrentUser && <span className="ml-2 text-xs text-gray-400">(you)</span>}
        </p>
        <p className="text-xs text-gray-400 truncate">{member.email}</p>
      </div>

      {canManage && !isCurrentUser ? (
        <select
          value={member.role_name}
          onChange={(e) => handleRoleChange(e.target.value)}
          disabled={updating}
          className="text-xs border border-gray-300 rounded-lg px-2 py-1.5 focus:outline-none focus:ring-1 focus:ring-primary-500 disabled:opacity-50"
        >
          {roles.map((r) => (
            <option key={r.name} value={r.name}>{r.display_name}</option>
          ))}
        </select>
      ) : (
        <span className="text-xs text-gray-500 bg-gray-100 px-2 py-1 rounded-lg">
          {member.role_display_name}
        </span>
      )}

      {(canManage || isCurrentUser) && (
        <button
          onClick={() => onRemove(member.user_id, displayName)}
          className="p-1.5 text-gray-400 hover:text-red-500 hover:bg-red-50 rounded-lg transition-colors"
          title={isCurrentUser ? 'Leave organization' : 'Remove member'}
        >
          <TrashIcon className="w-4 h-4" />
        </button>
      )}
    </li>
  )
}

export default function OrgDetailPage() {
  const { slug } = useParams<{ slug: string }>()
  const navigate = useNavigate()
  const { currentUser } = useAppStore()

  const [org, setOrg] = useState<OrgWithRole | null>(null)
  const [members, setMembers] = useState<Member[]>([])
  const [roles, setRoles] = useState<SystemRole[]>([])
  const [loading, setLoading] = useState(true)
  const [addEmail, setAddEmail] = useState('')
  const [addRole, setAddRole] = useState('student')
  const [adding, setAdding] = useState(false)

  useEffect(() => {
    if (!slug) return
    loadData(slug)
  }, [slug])

  const loadData = async (orgSlug: string) => {
    setLoading(true)
    try {
      const [orgData, memberData, roleData] = await Promise.all([
        orgsApi.list().then((list) => list.find((o) => o.slug === orgSlug) ?? null),
        orgsApi.listMembers(orgSlug),
        rolesApi.list(),
      ])
      setOrg(orgData)
      setMembers(memberData)
      setRoles(roleData.sort((a, b) => ROLE_ORDER.indexOf(a.name) - ROLE_ORDER.indexOf(b.name)))
    } catch {
      navigate('/orgs')
    } finally {
      setLoading(false)
    }
  }

  const handleAddMember = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!addEmail.trim() || !slug) return

    setAdding(true)
    try {
      const member = await orgsApi.addMember(slug, { email: addEmail.trim(), role_name: addRole })
      setMembers((prev) => [...prev, member])
      setAddEmail('')
      toast.success(`${member.username} added to organization.`)
    } catch {
      // toast from interceptor
    } finally {
      setAdding(false)
    }
  }

  const handleRoleChange = async (userId: string, roleName: string) => {
    if (!slug) return
    const updated = await orgsApi.updateMemberRole(slug, userId, roleName)
    setMembers((prev) => prev.map((m) => (m.user_id === userId ? { ...m, ...updated } : m)))
    toast.success('Role updated.')
  }

  const handleRemove = async (userId: string, name: string) => {
    if (!slug) return
    const isSelf = userId === currentUser?.id
    const msg = isSelf
      ? 'Leave this organization? You will lose access.'
      : `Remove ${name} from this organization?`
    if (!confirm(msg)) return

    try {
      await orgsApi.removeMember(slug, userId)
      if (isSelf) {
        navigate('/orgs')
      } else {
        setMembers((prev) => prev.filter((m) => m.user_id !== userId))
        toast.success(`${name} removed.`)
      }
    } catch {
      // toast from interceptor
    }
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <LoadingSpinner label="Loading organization…" />
      </div>
    )
  }

  if (!org) return null

  const userMemberRole = members.find((m) => m.user_id === currentUser?.id)?.role_name ?? ''
  const canManage = isAdmin(userMemberRole) || (currentUser?.is_superuser ?? false)

  return (
    <div className="space-y-6 max-w-3xl">
      {/* Header */}
      <div className="flex items-center gap-4">
        <button
          onClick={() => navigate('/orgs')}
          className="p-1.5 text-gray-400 hover:text-gray-600 rounded-lg hover:bg-gray-100 transition-colors"
        >
          <ArrowLeftIcon className="w-4 h-4" />
        </button>
        <div className="flex-1 min-w-0">
          <h1 className="text-2xl font-bold text-gray-900 truncate">{org.name}</h1>
          <p className="text-sm text-gray-400 font-mono mt-0.5">{org.slug}</p>
        </div>
        <span className="inline-flex items-center gap-1.5 px-3 py-1 bg-primary-50 text-primary-700 text-sm font-medium rounded-full">
          <ShieldCheckIcon className="w-3.5 h-3.5" />
          {userMemberRole.replace(/_/g, ' ')}
        </span>
      </div>

      {/* Members section */}
      <div className="bg-white rounded-xl border border-gray-200 p-6">
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-base font-semibold text-gray-900">
            Members
            <span className="ml-2 text-sm font-normal text-gray-400">({members.length})</span>
          </h2>
        </div>

        <ul className="divide-y divide-gray-100">
          {members.map((member) => (
            <MemberRow
              key={member.user_id}
              member={member}
              roles={roles}
              isCurrentUser={member.user_id === currentUser?.id}
              canManage={canManage}
              onRoleChange={handleRoleChange}
              onRemove={handleRemove}
            />
          ))}
        </ul>

        {/* Add member form (admins only) */}
        {canManage && (
          <form onSubmit={handleAddMember} className="mt-5 pt-5 border-t border-gray-100">
            <p className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-3 flex items-center gap-1.5">
              <UserPlusIcon className="w-3.5 h-3.5" />
              Add member
            </p>
            <div className="flex gap-2">
              <input
                type="email"
                required
                value={addEmail}
                onChange={(e) => setAddEmail(e.target.value)}
                placeholder="user@example.com"
                className="flex-1 px-3 py-2 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-primary-500"
              />
              <select
                value={addRole}
                onChange={(e) => setAddRole(e.target.value)}
                className="px-3 py-2 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-1 focus:ring-primary-500"
              >
                {roles.map((r) => (
                  <option key={r.name} value={r.name}>{r.display_name}</option>
                ))}
              </select>
              <button
                type="submit"
                disabled={adding || !addEmail.trim()}
                className="px-4 py-2 bg-primary-600 text-white text-sm font-medium rounded-lg hover:bg-primary-700 disabled:opacity-50 transition-colors whitespace-nowrap"
              >
                {adding ? 'Adding…' : 'Add'}
              </button>
            </div>
          </form>
        )}
      </div>
    </div>
  )
}
