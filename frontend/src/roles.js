// Roles (Step 1 of 2) Controller - Matches Image 5 top-right exactly
import { initCommonUI, icons, prefersReducedMotion } from './app.js'

const ROLES = [
  {
    key: 'employee',
    title: 'Internal Employee',
    desc: 'Manage assigned matters, prepare documents, track deadlines, and complete your daily work.',
    accentColor: '#F59E0B',
    accentBg: 'rgba(245, 158, 11, 0.12)',
    accentBorder: 'rgba(245, 158, 11, 0.3)',
    iconSvg: icons.briefcase,
    isActive: false,
  },
  {
    key: 'management',
    title: 'Management / Executive',
    desc: 'Monitor organizational activity, review key decisions, oversee approvals, and track operational performance.',
    accentColor: '#A78BFA',
    accentBg: 'rgba(167, 139, 250, 0.12)',
    accentBorder: 'rgba(167, 139, 250, 0.3)',
    iconSvg: icons.barChart,
    isActive: false,
  },
  {
    key: 'advocate',
    title: 'Advocate',
    desc: 'Review assigned legal matters, prepare case documents, and manage litigation-related workflows.',
    accentColor: '#EAB308',
    accentBg: 'rgba(234, 179, 8, 0.12)',
    accentBorder: 'rgba(234, 179, 8, 0.3)',
    iconSvg: icons.scale,
    isActive: false,
  },
  {
    key: 'client',
    title: 'Client',
    desc: 'Access your matters, review documents, track updates, and respond to requests securely.',
    accentColor: '#06B6D4',
    accentBg: 'rgba(6, 182, 212, 0.12)',
    accentBorder: 'rgba(6, 182, 212, 0.3)',
    iconSvg: icons.userCheck || icons.user,
    isActive: false,
  },
  {
    key: 'tenant',
    title: 'Tenant or Buyer',
    desc: 'Manage property-related documents, review transactions, and track your assigned requirements.',
    accentColor: '#F97316',
    accentBg: 'rgba(249, 115, 22, 0.12)',
    accentBorder: 'rgba(249, 115, 22, 0.3)',
    iconSvg: icons.home,
    isActive: false,
  },
  {
    key: 'auditor',
    title: 'Auditor',
    desc: 'Review records, examine supporting evidence, and monitor compliance through authorized read-only access.',
    accentColor: '#EC4899',
    accentBg: 'rgba(236, 72, 153, 0.12)',
    accentBorder: 'rgba(236, 72, 153, 0.3)',
    iconSvg: icons.clipboardCheck || icons.search,
    isActive: false,
  },
  {
    key: 'admin',
    title: 'Administrator',
    desc: 'Manage user access, review approvals, oversee platform operations, and maintain audit records.',
    accentColor: '#22D3EE',
    accentBg: 'rgba(34, 211, 238, 0.15)',
    accentBorder: 'rgba(34, 211, 238, 0.5)',
    iconSvg: icons.settings,
    isActive: true, // Shown active in reference Image 5
  },
]

export function renderRolesGrid(containerId = 'roles-grid') {
  const container = document.getElementById(containerId)
  if (!container) return

  container.innerHTML = ROLES.map(
    (r) => `
    <a
      href="login.html?role=${r.key}"
      class="glass-card card-spotlight glass-card-interactive role-card ${r.isActive ? 'role-card-active' : ''}"
      data-role="${r.key}"
      style="
        padding: 24px;
        display: flex;
        flex-direction: column;
        justify-content: flex-start;
        gap: 16px;
        min-height: 220px;
        text-decoration: none;
        border-radius: var(--r-20);
        transition: transform 150ms ease, box-shadow 150ms ease, border-color 150ms ease;
        ${r.isActive ? 'border: 1.5px solid #22D3EE; box-shadow: 0 0 24px rgba(34, 211, 238, 0.25);' : ''}
      "
      aria-label="Select role: ${r.title}"
    >
      <!-- Refined Icon Tile with meaningful role icon -->
      <div
        class="icon-tile"
        style="
          width: 44px;
          height: 44px;
          border-radius: 12px;
          background: ${r.accentBg};
          border: 1px solid ${r.accentBorder};
          color: ${r.accentColor};
          display: flex;
          align-items: center;
          justify-content: center;
          flex-shrink: 0;
        "
        aria-hidden="true"
      >
        <span style="display: flex; align-items: center; justify-content: center; width: 22px; height: 22px;">
          ${r.iconSvg}
        </span>
      </div>

      <!-- Title & Professional Description -->
      <div style="margin-top: 2px;">
        <h3 style="font-size: 19px; font-weight: 600; color: var(--fg); margin-bottom: 8px; letter-spacing: -0.01em;">
          ${r.title}
        </h3>
        <p style="font-size: 13.5px; color: var(--mu); line-height: 1.55; margin: 0;">
          ${r.desc}
        </p>
      </div>

      <!-- Continue Link with Arrow matching Image 5 -->
      <div style="display: flex; align-items: center; gap: 6px; font-size: 14px; font-weight: 600; color: var(--lk); margin-top: auto; padding-top: 14px;">
        <span>Continue</span>
        <span style="font-size: 16px; display: inline-block; transform: translateY(-0.5px);">&rarr;</span>
      </div>
    </a>
  `
  ).join('')

  // Handoff click handler
  const cards = container.querySelectorAll('.role-card')
  cards.forEach((card) => {
    card.addEventListener('click', (e) => {
      e.preventDefault()
      const roleKey = card.getAttribute('data-role')
      sessionStorage.setItem('nushift_role', roleKey)
      localStorage.setItem('nushift_role', roleKey)
      const targetUrl = `login.html?role=${encodeURIComponent(roleKey)}`

      if (prefersReducedMotion()) {
        window.location.href = targetUrl
        return
      }

      // Role card select animation
      card.style.transform = 'scale(1.025)'
      card.style.transition = 'transform 150ms ease-out'
      setTimeout(() => {
        document.body.classList.add('page-transition-exit-active')
        setTimeout(() => {
          window.location.href = targetUrl
        }, 180)
      }, 120)
    })
  })
}

document.addEventListener('DOMContentLoaded', () => {
  initCommonUI()
  renderRolesGrid()
})
