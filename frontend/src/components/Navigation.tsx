import { NavLink } from 'react-router-dom'
import {
  HomeIcon,
  ArrowUpTrayIcon,
  BeakerIcon,
  AcademicCapIcon,
} from '@heroicons/react/24/outline'

const navItems = [
  { to: '/', label: 'Dashboard', icon: HomeIcon, end: true },
  { to: '/upload', label: 'Upload', icon: ArrowUpTrayIcon, end: false },
  { to: '/scenarios', label: 'Scenarios', icon: BeakerIcon, end: false },
]

export default function Navigation() {
  return (
    <nav className="fixed inset-y-0 left-0 z-40 w-64 bg-white border-r border-gray-200 flex flex-col shadow-sm">
      {/* Logo */}
      <div className="flex items-center gap-3 px-6 py-5 border-b border-gray-100">
        <div className="flex-shrink-0 w-9 h-9 bg-primary-600 rounded-lg flex items-center justify-center">
          <AcademicCapIcon className="w-5 h-5 text-white" />
        </div>
        <div>
          <p className="text-sm font-semibold text-gray-900 leading-tight">Pharmacy</p>
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

      {/* Footer */}
      <div className="px-6 py-4 border-t border-gray-100">
        <p className="text-xs text-gray-400">Pharmacy Clinical AI v1.0</p>
        <p className="text-xs text-gray-400 mt-0.5">Powered by Claude AI</p>
      </div>
    </nav>
  )
}
