import { NavLink, Outlet } from 'react-router-dom'
import {
  HomeModernIcon,
  ArrowUpTrayIcon,
  CheckBadgeIcon,
  DocumentMagnifyingGlassIcon,
  BookOpenIcon,
  GlobeAltIcon,
  ClockIcon,
} from '@heroicons/react/24/outline'

const GOV_NAV = [
  { to: '/admin/governance',                        label: 'Overview',        icon: HomeModernIcon,             end: true  },
  { to: '/admin/governance/import',                 label: 'Import',          icon: ArrowUpTrayIcon,            end: true  },
  { to: '/admin/governance/import/batches',         label: 'Import History',  icon: ClockIcon,                  end: false },
  { to: '/admin/governance/approval-batches',       label: 'Approval Batches',icon: CheckBadgeIcon,             end: false },
  { to: '/admin/governance/content',                label: 'Content Library', icon: DocumentMagnifyingGlassIcon,end: false },
  { to: '/admin/governance/evidence',               label: 'Evidence',        icon: BookOpenIcon,               end: false },
  { to: '/admin/governance/regions',                label: 'Regions',         icon: GlobeAltIcon,               end: false },
]

export default function GovernanceLayout() {
  return (
    <div className="space-y-6">
      {/* Section header */}
      <div>
        <h1 className="text-xl font-bold text-gray-900">Content Governance</h1>
        <p className="text-sm text-gray-500 mt-0.5">
          Admin-only · Manage the community pharmacy content lifecycle
        </p>
      </div>

      {/* Sub-navigation */}
      <nav className="flex gap-1 border-b border-gray-200 pb-0 overflow-x-auto">
        {GOV_NAV.map(({ to, label, icon: Icon, end }) => (
          <NavLink
            key={to}
            to={to}
            end={end}
            className={({ isActive }) =>
              `flex items-center gap-1.5 px-3 py-2.5 text-sm font-medium whitespace-nowrap border-b-2 transition-colors ${
                isActive
                  ? 'border-primary-600 text-primary-700'
                  : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
              }`
            }
          >
            <Icon className="w-4 h-4 flex-shrink-0" />
            {label}
          </NavLink>
        ))}
      </nav>

      {/* Page content */}
      <Outlet />
    </div>
  )
}
