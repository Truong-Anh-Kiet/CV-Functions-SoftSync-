import type { ReactNode } from 'react';
import type { MenuType } from '../../types/dashboard';

interface SidebarProps {
  menuItems: MenuType[];
  activeMenu: MenuType;
  onChangeMenu: (menu: MenuType) => void;
  userName?: string;
  userEmail?: string;
  onLogout: () => void;
  collapsed: boolean;
  onToggleCollapse: () => void;
}

const MENU_ICON: Record<MenuType, ReactNode> = {
  'CV Storage': (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <path d="M3 7a2 2 0 0 1 2-2h4l2 2h8a2 2 0 0 1 2 2v9a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z" />
    </svg>
  ),
  'CV-JD Matching': (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <rect x="3" y="3" width="7" height="7" rx="1" />
      <rect x="14" y="14" width="7" height="7" rx="1" />
      <path d="M10 7h4M7 10v4M17 10v4M14 17h-4" />
    </svg>
  ),
  'CV Ranking': (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <path d="M4 19h4V11H4zM10 19h4V5h-4zM16 19h4v-6h-4z" />
    </svg>
  ),
  'CV Comparison': (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <path d="M12 3v18" />
      <path d="M6 8 3 11l3 3M6 11h6" />
      <path d="m18 8 3 3-3 3M18 11h-6" />
    </svg>
  ),
  'CV Searching': (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <circle cx="11" cy="11" r="7" />
      <path d="m21 21-4.3-4.3" />
    </svg>
  ),
};

const IconChevron = ({ direction }: { direction: 'left' | 'right' }) => (
  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
    {direction === 'left' ? <path d="m15 18-6-6 6-6" /> : <path d="m9 6 6 6-6 6" />}
  </svg>
);

const IconLogout = () => (
  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
    <path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4" />
    <path d="m16 17 5-5-5-5" />
    <path d="M21 12H9" />
  </svg>
);

export default function Sidebar({
  menuItems, activeMenu, onChangeMenu,
  userName, userEmail, onLogout,
  collapsed, onToggleCollapse,
}: SidebarProps) {
  const initials = (userName || userEmail || '?')
    .split(/\s+/)
    .map((p) => p[0])
    .filter(Boolean)
    .slice(0, 2)
    .join('')
    .toUpperCase();

  return (
    <aside className={`sidebar ${collapsed ? 'sidebar-collapsed' : ''}`}>
      <button
        type="button"
        className="sidebar-toggle"
        onClick={onToggleCollapse}
        aria-label={collapsed ? 'Mở rộng sidebar' : 'Thu gọn sidebar'}
        title={collapsed ? 'Mở rộng' : 'Thu gọn'}
      >
        <IconChevron direction={collapsed ? 'right' : 'left'} />
      </button>

      <div className="sidebar-brand">
        <div className="logo-icon">JD</div>
        {!collapsed && <h2>Recruitment</h2>}
      </div>

      <nav className="sidebar-nav">
        {menuItems.map((item) => (
          <button
            key={item}
            className={`menu-button ${activeMenu === item ? 'active' : ''}`}
            onClick={() => onChangeMenu(item)}
            title={collapsed ? item : undefined}
            aria-label={item}
          >
            <span className="menu-button-icon">{MENU_ICON[item]}</span>
            {!collapsed && <span className="menu-button-label">{item}</span>}
          </button>
        ))}
      </nav>

      <div className="sidebar-footer">
        {collapsed ? (
          <>
            <div className="user-avatar" title={`${userName ?? ''}\n${userEmail ?? ''}`.trim()}>
              {initials}
            </div>
            <button
              className="logout-button logout-button-collapsed"
              onClick={onLogout}
              title="Log out"
              aria-label="Log out"
            >
              <IconLogout />
            </button>
          </>
        ) : (
          <>
            <div className="user-profile">
              <span className="user-name">{userName}</span>
              <span className="user-email">{userEmail}</span>
            </div>
            <button className="logout-button" onClick={onLogout}>Log Out</button>
          </>
        )}
      </div>
    </aside>
  );
}
