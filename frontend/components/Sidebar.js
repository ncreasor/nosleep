'use client'

import Link from 'next/link'
import { usePathname } from 'next/navigation'
import { FileText, BarChart3, Folder, HelpCircle, LogOut } from 'lucide-react'
import { useAuth } from './useAuth'

export default function Sidebar() {
  const pathname = usePathname()
  const { user, logout } = useAuth({ redirect: false })

  const navItem = (href, icon, label) => {
    const active = pathname === href
    return (
      <Link
        href={href}
        className={`flex items-center gap-3 px-2 py-2.5 rounded-lg transition-colors text-sm ${
          active ? 'bg-white bg-opacity-80 text-ink font-semibold' : 'text-gray-600 hover:bg-white hover:bg-opacity-60'
        }`}
      >
        <span className={`flex-shrink-0 ${active ? 'text-brand-hover' : ''}`}>{icon}</span>
        <span className="nav-label font-medium">{label}</span>
      </Link>
    )
  }

  return (
    <div className="sidebar flex flex-col py-5 gap-6">
      {/* Logo + Company Name */}
      <div className="flex items-center px-3">
        <Link href="/" className="flex items-center gap-3 flex-1">
          <img src="/inlawlogo.svg" alt="inLaw" className="w-10 h-10 rounded-xl flex-shrink-0" />
          <div className="flex flex-col">
            <span className="nav-label font-semibold text-sm text-gray-800">Company Name</span>
            <span className="text-xs text-gray-400">Free plan</span>
          </div>
        </Link>
      </div>

      {/* Nav */}
      <nav className="flex flex-col gap-1 px-3">
        {navItem('/documents', <FileText size={20} />, 'Документы')}
        {navItem('/templates', <Folder size={20} />, 'Шаблоны')}
        {navItem('/statistics', <BarChart3 size={20} />, 'Статистика')}
      </nav>

      {/* Bottom */}
      <div className="flex-1 flex flex-col justify-end gap-1 px-3">
        <button className="flex items-center gap-3 px-2 py-2.5 rounded-lg text-gray-600 hover:bg-white hover:bg-opacity-60 transition-colors text-sm w-full">
          <span className="flex-shrink-0"><HelpCircle size={20} /></span>
          <span className="nav-label font-medium">Help</span>
        </button>

        {user && (
          <div className="flex items-center gap-3 px-2 py-2.5 rounded-lg">
            <span className="w-5 h-5 bg-gray-300 rounded-full flex-shrink-0 flex items-center justify-center text-xs font-bold text-gray-600">
              {user.email?.[0]?.toUpperCase()}
            </span>
            <span className="nav-label text-xs text-gray-500 truncate flex-1 min-w-0">{user.email}</span>
            <button onClick={logout} className="nav-label flex-shrink-0 text-gray-400 hover:text-red-500 transition-colors">
              <LogOut size={14} />
            </button>
          </div>
        )}
      </div>
    </div>
  )
}
