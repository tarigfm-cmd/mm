import { useNavigate, NavLink } from 'react-router-dom'
import {
  HomeIcon,
  ArrowUpTrayIcon,
  BeakerIcon,
  AcademicCapIcon,
  BuildingLibraryIcon,
  ArrowRightStartOnRectangleIcon,
} from '@heroicons/react/24/outline'
import toast from 'react-hot-toast'
import { authApi } from '@/services/api'
import { useAppStore } from '@/store/appStore'

const navItems = [
  { to: '/', label: 'Dashboard', icon: HomeIcon, end: true },
  { to: '/scenarios', label: 'Scenarios', icon: BeakerIcon, end: false },
  { to: '/upload', label: 'Upload', icon: ArrowUpTrayIcon, end: false },
  { to: '/orgs', label: 'Organizations', icon: BuildingLibraryIcon, end: false },
]

function UserAvatar({ name }: { name: string }) {
  const initials = name
    .split(' ')
    .map((p) => p[0])
    .join('')
    .toUpperCase()
    .slice(0, 2)
  return (
    <div className="w-8 h-8 rounded-full bg-primary-100 text-primary-700 flex items-center justify-center text-xs font-semibold flex-shrink-0">
      {initials}
    </div>
  )
}

export default function Navigation() {
  const navigate = useNavigate()
  const { currentUser } = useAppStore()

  const handleLogout = async () => {
    await authApi.logout()
    toast.success('Signed out.')
    navigate('/login', { replace: true })
  }

  const displayName = currentUser?.full_name || currentUser?.username || 'User'

  return (
    <nav className="fixed inset-y-0 left-0 z-40 w-64 bg-white border-r border-gray-200 flex flex-col shadow-sm">
      {/* Logo */}
      <div className="flex items-center gap-3 px-6 py-5 border-b border-gray-100">
        <div className="flex-shrink-0 w-9 h-9 bg-primary-600 rounded-lg flex items-center justify-center">
          <AcademicCapIcon className="w-5 h-5 text-white" />
        </div>
        <div>
          <p className="text-sm font-semibold text-gray-900 leading-tight">PharmLearn</p>
          <p className="text-xs text-primary-600 font-medium">Clinical AI</p>
        </div>
      </div>

      {/* Navigation links */}
      <ul className="flex-1 px-3 py-4 space-y-1">
        {navItems.map(({ to, label, icon: Icon, end }) => (
          <li key={to}>
            <NavLink
              to={to}
              end={end}
              className={({ isActive }) =>
                `flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition-colors ${
                  isActive
                    ? 'bg-primary-50 text-primary-700'
                    : 'text-gray-600 hover:bg-gray-50 hover:text-gray-900'
                }`
              }
            >
              <Icon className="w-5 h-5 flex-shrink-0" />
              {label}
            </NavLink>
          </li>
        ))}
      </ul>

      {/* User section */}
      <div className="px-4 py-4 border-t border-gray-100">
        <div className="flex items-center gap-3 px-2 py-2 rounded-lg">
          <UserAvatar name={displayName} />
          <div className="flex-1 min-w-0">
            <p className="text-xs font-medium text-gray-900 truncate">{displayName}</p>
            <p className="text-xs text-gray-400 truncate">{currentUser?.email}</p>
          </div>
          <button
            onClick={handleLogout}
            title="Sign out"
            className="p-1.5 text-gray-400 hover:text-red-500 hover:bg-red-50 rounded-lg transition-colors flex-shrink-0"
          >
            <ArrowRightStartOnRectangleIcon className="w-4 h-4" />
          </button>
        </div>
      </div>
    </nav>
  )
}
