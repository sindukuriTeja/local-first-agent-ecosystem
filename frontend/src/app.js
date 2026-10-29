// Nushift Core Presentation & Interaction Module
// Vanilla JS: Theme Toggle, Spotlight, Tilt, Number Ticker, Toast, Modal, Icons, Offline

export const prefersReducedMotion = () =>
  typeof window !== 'undefined' &&
  window.matchMedia &&
  window.matchMedia('(prefers-reduced-motion: reduce)').matches

/* -------------------------------------------------------------
   10. Theme System
   ------------------------------------------------------------- */
export function getSavedTheme() {
  try {
    const t = localStorage.getItem('nushift_theme') || localStorage.getItem('lfae_theme')
    if (t === 'light' || t === 'dark') return t
  } catch {
    /* ignore */
  }
  if (typeof window !== 'undefined' && window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches) {
    return 'dark'
  }
  return 'light'
}

export function setTheme(theme) {
  document.documentElement.setAttribute('data-theme', theme)
  try {
    localStorage.setItem('nushift_theme', theme)
    localStorage.setItem('lfae_theme', theme)
  } catch {
    /* ignore */
  }
  updateThemeButtons()
}

export function toggleTheme() {
  const current = document.documentElement.getAttribute('data-theme') || 'dark'
  const next = current === 'dark' ? 'light' : 'dark'
  setTheme(next)
}

export function updateThemeButtons() {
  const current = document.documentElement.getAttribute('data-theme') || 'dark'
  const isDark = current === 'dark'
  const btns = document.querySelectorAll('[data-theme-toggle]')
  btns.forEach((btn) => {
    btn.setAttribute('aria-label', isDark ? 'Switch to light theme' : 'Switch to dark theme')
    btn.setAttribute('aria-pressed', isDark ? 'true' : 'false')
    btn.innerHTML = isDark ? icons.sun : icons.moon
  })
}

/* -------------------------------------------------------------
   9. Page Transitions
   ------------------------------------------------------------- */
export function initPageTransitions() {
  // Entrance animation
  if (!prefersReducedMotion()) {
    document.body.classList.add('page-transition-enter')
    requestAnimationFrame(() => {
      document.body.classList.add('page-transition-enter-active')
      document.body.classList.remove('page-transition-enter')
    })
  }

  // Intercept local links for smooth 200ms exit
  document.addEventListener('click', (e) => {
    const a = e.target.closest('a')
    if (!a) return
    const href = a.getAttribute('href')
    if (!href || href.startsWith('#') || href.startsWith('mailto:') || href.startsWith('tel:') || a.target === '_blank') return

    // Internal navigation
    if (a.hostname === window.location.hostname && !e.metaKey && !e.ctrlKey) {
      if (prefersReducedMotion()) return // let browser navigate naturally
      e.preventDefault()
      document.body.classList.add('page-transition-exit-active')
      setTimeout(() => {
        window.location.href = href
      }, 200)
    }
  })
}

/* -------------------------------------------------------------
   7. Glass Card Cursor Spotlight (Aceternity style)
   ------------------------------------------------------------- */
export function initSpotlight() {
  if (prefersReducedMotion()) return

  document.addEventListener('pointermove', (e) => {
    const cards = document.querySelectorAll('.card-spotlight')
    cards.forEach((card) => {
      const rect = card.getBoundingClientRect()
      // Only compute if within reasonable viewport range
      if (
        e.clientX >= rect.left - 100 &&
        e.clientX <= rect.right + 100 &&
        e.clientY >= rect.top - 100 &&
        e.clientY <= rect.bottom + 100
      ) {
        const x = e.clientX - rect.left
        const y = e.clientY - rect.top
        card.style.setProperty('--mx', `${x}px`)
        card.style.setProperty('--my', `${y}px`)
      }
    })
  })
}

/* -------------------------------------------------------------
   7. 3D Tilt Card (Aceternity style)
   ------------------------------------------------------------- */
export function initTilt() {
  if (prefersReducedMotion()) return

  const tiltCards = document.querySelectorAll('.tilt-card')
  tiltCards.forEach((card) => {
    card.addEventListener('pointermove', (e) => {
      const rect = card.getBoundingClientRect()
      const x = e.clientX - rect.left
      const y = e.clientY - rect.top
      const centerX = rect.width / 2
      const centerY = rect.height / 2
      const rotateX = ((y - centerY) / centerY) * -6
      const rotateY = ((x - centerX) / centerX) * 6
      card.style.transform = `perspective(800px) rotateX(${rotateX.toFixed(2)}deg) rotateY(${rotateY.toFixed(2)}deg)`
    })

    card.addEventListener('pointerleave', () => {
      card.style.transform = 'perspective(800px) rotateX(0deg) rotateY(0deg)'
    })
  })
}

/* -------------------------------------------------------------
   7. Number Ticker (Magic UI style)
   ------------------------------------------------------------- */
export function initNumberTickers() {
  const elements = document.querySelectorAll('[data-ticker]')
  if (elements.length === 0) return

  if (prefersReducedMotion()) {
    elements.forEach((el) => {
      const target = Number(el.getAttribute('data-ticker') || el.textContent)
      el.textContent = target.toLocaleString()
    })
    return
  }

  const observer = new IntersectionObserver(
    (entries) => {
      entries.forEach((entry) => {
        if (!entry.isIntersecting) return
        observer.unobserve(entry.target)
        animateCountUp(entry.target)
      })
    },
    { threshold: 0.1 }
  )

  elements.forEach((el) => observer.observe(el))
}

export function animateCountUp(el, duration = 800) {
  const target = Number(el.getAttribute('data-ticker') || el.textContent.replace(/,/g, '')) || 0
  if (!Number.isFinite(target)) return

  const start = performance.now()
  function tick(now) {
    const elapsed = now - start
    const progress = Math.min(elapsed / duration, 1)
    // ease-out cubic
    const eased = 1 - Math.pow(1 - progress, 3)
    const current = Math.round(target * eased)
    el.textContent = current.toLocaleString()
    if (progress < 1) {
      requestAnimationFrame(tick)
    } else {
      el.textContent = target.toLocaleString()
    }
  }
  requestAnimationFrame(tick)
}

/* -------------------------------------------------------------
   7. Toast System (shadcn sonner style)
   ------------------------------------------------------------- */
let toastContainer = null
export function showToast({ title, message = '', type = 'info', duration = 5000, onUndo = null }) {
  if (!toastContainer) {
    toastContainer = document.createElement('div')
    toastContainer.className = 'toast-container'
    toastContainer.setAttribute('role', 'region')
    toastContainer.setAttribute('aria-label', 'Notifications')
    document.body.appendChild(toastContainer)
  }

  const toast = document.createElement('div')
  toast.className = 'glass-card toast-item'
  toast.setAttribute('role', 'alert')

  const iconSvg =
    type === 'success'
      ? icons.checkCircle
      : type === 'error'
      ? icons.alertCircle
      : type === 'warning'
      ? icons.alertTriangle
      : icons.info

  toast.innerHTML = `
    <span class="icon-tile icon-tile-44" style="--role: var(--status-${type === 'error' ? 'error' : type === 'success' ? 'success' : type === 'warning' ? 'warning' : 'info'}-fg); background: var(--status-${type === 'error' ? 'error' : type === 'success' ? 'success' : type === 'warning' ? 'warning' : 'info'}-bg); border-color: currentColor;" aria-hidden="true">
      ${iconSvg}
    </span>
    <div style="flex: 1; min-width: 0;">
      <div style="font-weight: 600; font-size: 14px; color: var(--fg);">${title}</div>
      ${message ? `<div style="font-size: 13px; color: var(--mu); margin-top: 2px;">${message}</div>` : ''}
    </div>
    ${
      onUndo
        ? `<button type="button" class="btn btn-ghost btn-sm toast-undo" style="padding: 0 8px; font-size: 12px;">Undo</button>`
        : ''
    }
    <button type="button" class="btn btn-ghost btn-circle btn-sm toast-close" aria-label="Dismiss notification" style="width: 28px; height: 28px;">
      ${icons.x}
    </button>
  `

  toastContainer.appendChild(toast)
  requestAnimationFrame(() => toast.classList.add('visible'))

  let timer = null
  const dismiss = () => {
    if (timer) clearTimeout(timer)
    toast.classList.remove('visible')
    setTimeout(() => toast.remove(), 250)
  }

  if (onUndo) {
    toast.querySelector('.toast-undo')?.addEventListener('click', () => {
      onUndo()
      dismiss()
    })
  }
  toast.querySelector('.toast-close')?.addEventListener('click', dismiss)

  if (duration > 0) {
    timer = setTimeout(dismiss, duration)
  }
}

/* -------------------------------------------------------------
   7. Modal System (shadcn dialog style)
   ------------------------------------------------------------- */
let activeModal = null
export function openModal(modalId) {
  const modal = typeof modalId === 'string' ? document.getElementById(modalId) : modalId
  if (!modal) return
  modal.classList.add('active')
  activeModal = modal

  // Focus first focusable element
  const focusable = modal.querySelectorAll('button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])')
  if (focusable.length > 0) focusable[0].focus()

  const onKeyDown = (e) => {
    if (e.key === 'Escape') closeModal(modal)
    // Focus trap
    if (e.key === 'Tab' && focusable.length > 0) {
      const first = focusable[0]
      const last = focusable[focusable.length - 1]
      if (e.shiftKey && document.activeElement === first) {
        last.focus()
        e.preventDefault()
      } else if (!e.shiftKey && document.activeElement === last) {
        first.focus()
        e.preventDefault()
      }
    }
  }
  modal._keydownHandler = onKeyDown
  document.addEventListener('keydown', onKeyDown)

  modal.addEventListener('click', (e) => {
    if (e.target === modal) closeModal(modal)
  })
}

export function closeModal(modalId) {
  const modal = typeof modalId === 'string' ? document.getElementById(modalId) : modalId
  if (!modal) return
  modal.classList.remove('active')
  if (modal._keydownHandler) {
    document.removeEventListener('keydown', modal._keydownHandler)
    modal._keydownHandler = null
  }
  if (activeModal === modal) activeModal = null
}

/* -------------------------------------------------------------
   11. Offline Detector
   ------------------------------------------------------------- */
export function initOfflineBanner() {
  const banner = document.createElement('div')
  banner.className = 'offline-banner'
  banner.setAttribute('role', 'status')
  banner.innerHTML = `${icons.wifiOff} <span>You are offline. Changes will not be saved.</span>`
  document.body.prepend(banner)

  const update = () => {
    if (navigator.onLine) {
      banner.classList.remove('visible')
    } else {
      banner.classList.add('visible')
    }
  }
  window.addEventListener('online', update)
  window.addEventListener('offline', update)
  update()
}

/* -------------------------------------------------------------
   7. Lucide SVG Icons Library (vanilla string icons)
   ------------------------------------------------------------- */
export const icons = {
  sun: `<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><circle cx="12" cy="12" r="4"/><path d="M12 2v2"/><path d="M12 20v2"/><path d="m4.93 4.93 1.41 1.41"/><path d="m17.66 17.66 1.41 1.41"/><path d="M2 12h2"/><path d="M20 12h2"/><path d="m6.34 17.66-1.41 1.41"/><path d="m19.07 4.93-1.41 1.41"/></svg>`,
  moon: `<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M12 3a6 6 0 0 0 9 9 9 9 0 1 1-9-9Z"/></svg>`,
  arrowRight: `<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M5 12h14"/><path d="m12 5 7 7-7 7"/></svg>`,
  arrowLeft: `<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="m12 19-7-7 7-7"/><path d="M19 12H5"/></svg>`,
  user: `<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M19 21v-2a4 4 0 0 0-4-4H9a4 4 0 0 0-4 4v2"/><circle cx="12" cy="7" r="4"/></svg>`,
  users: `<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M22 21v-2a4 4 0 0 0-3-3.87"/><path d="M16 3.13a4 4 0 0 1 0 7.75"/></svg>`,
  barChart: `<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><line x1="12" x2="12" y1="20" y2="10"/><line x1="18" x2="18" y1="20" y2="4"/><line x1="6" x2="6" y1="20" y2="16"/></svg>`,
  scale: `<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="m16 16 3-8 3 8c-.87.65-1.92 1-3 1s-2.13-.35-3-1Z"/><path d="m2 16 3-8 3 8c-.87.65-1.92 1-3 1s-2.13-.35-3-1Z"/><path d="M7 21h10"/><path d="M12 3v18"/><path d="M3 7h2c2 0 5-1 7-2 2 1 5 2 7 2h2"/></svg>`,
  building: `<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><rect width="16" height="20" x="4" y="2" rx="2" ry="2"/><path d="M9 22v-4h6v4"/><path d="M8 6h.01"/><path d="M16 6h.01"/><path d="M8 10h.01"/><path d="M16 10h.01"/><path d="M8 14h.01"/><path d="M16 14h.01"/></svg>`,
  home: `<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="m3 9 9-7 9 7v11a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"/><polyline points="9 22 9 12 15 12 15 22"/></svg>`,
  search: `<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><circle cx="11" cy="11" r="8"/><path d="m21 21-4.3-4.3"/></svg>`,
  shield: `<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M20 13c0 5-3.5 7.5-7.66 8.95a1 1 0 0 1-.67-.01C7.5 20.5 4 18 4 13V6a1 1 0 0 1 1-1c2 0 4.5-1.2 6.24-2.72a1.17 1.17 0 0 1 1.52 0C14.51 3.81 17 5 19 5a1 1 0 0 1 1 1z"/></svg>`,
  shieldCheck: `<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M20 13c0 5-3.5 7.5-7.66 8.95a1 1 0 0 1-.67-.01C7.5 20.5 4 18 4 13V6a1 1 0 0 1 1-1c2 0 4.5-1.2 6.24-2.72a1.17 1.17 0 0 1 1.52 0C14.51 3.81 17 5 19 5a1 1 0 0 1 1 1z"/><path d="m9 12 2 2 4-4"/></svg>`,
  checkCircle: `<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"/><polyline points="22 4 12 14.01 9 11.01"/></svg>`,
  alertCircle: `<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><circle cx="12" cy="12" r="10"/><line x1="12" x2="12" y1="8" y2="12"/><line x1="12" x2="12.01" y1="16" y2="16"/></svg>`,
  alertTriangle: `<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="m21.73 18-8-14a2 2 0 0 0-3.48 0l-8 14A2 2 0 0 0 4 21h16a2 2 0 0 0 1.73-3Z"/><line x1="12" x2="12" y1="9" y2="13"/><line x1="12" x2="12.01" y1="17" y2="17"/></svg>`,
  info: `<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><circle cx="12" cy="12" r="10"/><path d="M12 16v-4"/><path d="M12 8h.01"/></svg>`,
  x: `<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M18 6 6 18"/><path d="m6 6 12 12"/></svg>`,
  check: `<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M20 6 9 17l-5-5"/></svg>`,
  eye: `<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M2 12s3-7 10-7 10 7 10 7-3 7-10 7-10-7-10-7Z"/><circle cx="12" cy="12" r="3"/></svg>`,
  eyeOff: `<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M9.88 9.88a3 3 0 1 0 4.24 4.24"/><path d="M10.73 5.08A10.43 10.43 0 0 1 12 5c7 0 10 7 10 7a13.16 13.16 0 0 1-1.67 2.68"/><path d="M6.61 6.61A13.526 13.526 0 0 0 2 12s3 7 10 7a9.74 9.74 0 0 0 5.39-1.61"/><line x1="2" x2="22" y1="2" y2="22"/></svg>`,
  menu: `<svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><line x1="4" x2="20" y1="12" y2="12"/><line x1="4" x2="20" y1="6" y2="6"/><line x1="4" x2="20" y1="18" y2="18"/></svg>`,
  sparkles: `<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="m12 3-1.912 5.813a2 2 0 0 1-1.275 1.275L3 12l5.813 1.912a2 2 0 0 1 1.275 1.275L12 21l1.912-5.813a2 2 0 0 1 1.275-1.275L21 12l-5.813-1.912a2 2 0 0 1-1.275-1.275L12 3Z"/><path d="M5 3v4"/><path d="M19 17v4"/><path d="M3 5h4"/><path d="M17 19h4"/></svg>`,
  fileText: `<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M15 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V7Z"/><path d="M14 2v4a2 2 0 0 0 2 2h4"/><path d="M10 9H8"/><path d="M16 13H8"/><path d="M16 17H8"/></svg>`,
  briefcase: `<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><rect width="20" height="14" x="2" y="7" rx="2" ry="2"/><path d="M16 21V5a2 2 0 0 0-2-2h-4a2 2 0 0 0-2 2v16"/></svg>`,
  percent: `<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><line x1="19" x2="5" y1="5" y2="19"/><circle cx="6.5" cy="6.5" r="2.5"/><circle cx="17.5" cy="17.5" r="2.5"/></svg>`,
  bookOpen: `<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M2 3h6a4 4 0 0 1 4 4v14a3 3 0 0 0-3-3H2z"/><path d="M22 3h-6a4 4 0 0 0-4 4v14a3 3 0 0 1 3-3h7z"/></svg>`,
  mapPin: `<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M20 10c0 6-8 12-8 12s-8-6-8-12a8 8 0 0 1 16 0Z"/><circle cx="12" cy="10" r="3"/></svg>`,
  inbox: `<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><polyline points="22 12 16 12 14 15 10 15 8 12 2 12"/><path d="M5.45 5.11 2 12v6a2 2 0 0 0 2 2h16a2 2 0 0 0 2-2v-6l-3.45-6.89A2 2 0 0 0 16.76 4H7.24a2 2 0 0 0-1.79 1.11z"/></svg>`,
  activity: `<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M22 12h-4l-3 9L9 3l-3 9H2"/></svg>`,
  cpu: `<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><rect width="16" height="16" x="4" y="4" rx="2"/><rect width="6" height="6" x="9" y="9" rx="1"/><path d="M15 2v2"/><path d="M15 20v2"/><path d="M2 15h2"/><path d="M2 9h2"/><path d="M20 15h2"/><path d="M20 9h2"/><path d="M9 2v2"/><path d="M9 20v2"/></svg>`,
  logOut: `<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4"/><polyline points="16 17 21 12 16 7"/><line x1="21" x2="9" y1="12" y2="12"/></svg>`,
  chevronDown: `<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="m6 9 6 6 6-6"/></svg>`,
  send: `<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="m22 2-7 20-4-9-9-4Z"/><path d="M22 2 11 13"/></svg>`,
  upload: `<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="17 8 12 3 7 8"/><line x1="12" x2="12" y1="3" y2="15"/></svg>`,
  refreshCw: `<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M3 12a9 9 0 0 1 9-9 9.75 9.75 0 0 1 6.74 2.74L21 8"/><path d="M21 3v5h-5"/><path d="M21 12a9 9 0 0 1-9 9 9.75 9.75 0 0 1-6.74-2.74L3 16"/><path d="M8 16H3v5"/></svg>`,
  wifiOff: `<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><line x1="2" x2="22" y1="2" y2="22"/><path d="M12 20h.01"/><path d="M8.5 16.429a5 5 0 0 1 7 0"/><path d="M5 12.859a10 10 0 0 1 5.17-2.69"/><path d="M19 12.859a10 10 0 0 0-2.007-1.523"/><path d="M2 8.82a15 15 0 0 1 4.177-2.643"/><path d="M22 8.82a15 15 0 0 0-11.288-3.764"/></svg>`,
  bell: `<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M6 8a6 6 0 0 1 12 0c0 7 3 9 3 9H3s3-2 3-9"/><path d="M10.3 21a1.94 1.94 0 0 0 3.4 0"/></svg>`,
  gavel: `<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="m14 13-7.5 7.5c-.83.83-2.17.83-3 0 0 0 0 0 0 0-.83-.83-.83-2.17 0-3L11 10"/><path d="m16 16 6-6"/><path d="m8 8 6-6"/><path d="m9 7 8 8"/><path d="m21 11-8-8"/></svg>`,
  settings: `<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M12.22 2h-.44a2 2 0 0 0-2 2v.18a2 2 0 0 1-1 1.73l-.43.25a2 2 0 0 1-2 0l-.15-.08a2 2 0 0 0-2.73.73l-.22.38a2 2 0 0 0 .73 2.73l.15.1a2 2 0 0 1 1 1.72v.51a2 2 0 0 1-1 1.74l-.15.09a2 2 0 0 0-.73 2.73l.22.38a2 2 0 0 0 2.73.73l.15-.08a2 2 0 0 1 2 0l.43.25a2 2 0 0 1 1 1.73V20a2 2 0 0 0 2 2h.44a2 2 0 0 0 2-2v-.18a2 2 0 0 1 1-1.73l.43-.25a2 2 0 0 1 2 0l.15.08a2 2 0 0 0 2.73-.73l.22-.39a2 2 0 0 0-.73-2.73l-.15-.08a2 2 0 0 1-1-1.74v-.5a2 2 0 0 1 1-1.74l.15-.09a2 2 0 0 0 .73-2.73l-.22-.38a2 2 0 0 0-2.73-.73l-.15.08a2 2 0 0 1-2 0l-.43-.25a2 2 0 0 1-1-1.73V4a2 2 0 0 0-2-2z"/><circle cx="12" cy="12" r="3"/></svg>`,
  clipboardCheck: `<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><rect width="8" height="4" x="8" y="2" rx="1" ry="1"/><path d="M16 4h2a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2V6a2 2 0 0 1 2-2h2"/><path d="m9 14 2 2 4-4"/></svg>`,
  userCheck: `<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><polyline points="16 11 18 13 22 9"/></svg>`,
  receipt: `<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M4 2v20l2-1 2 1 2-1 2 1 2-1 2 1 2-1 2 1V2l-2 1-2-1-2 1-2-1-2 1-2-1-2 1Z"/><path d="M14 8H8"/><path d="M16 12H8"/><path d="M13 16H8"/></svg>`,
  calendarDays: `<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><rect width="18" height="18" x="3" y="4" rx="2"/><line x1="16" x2="16" y1="2" y2="6"/><line x1="8" x2="8" y1="2" y2="6"/><line x1="3" x2="21" y1="10" y2="10"/><path d="M8 14h.01"/><path d="M12 14h.01"/><path d="M16 14h.01"/><path d="M8 18h.01"/><path d="M12 18h.01"/><path d="M16 18h.01"/></svg>`,
  folder: `<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M20 20a2 2 0 0 0 2-2V8a2 2 0 0 0-2-2h-7.9a2 2 0 0 1-1.69-.9L9.6 3.9A2 2 0 0 0 7.93 3H4a2 2 0 0 0-2 2v13a2 2 0 0 0 2 2Z"/></svg>`,
  wallet: `<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M19 7V4a1 1 0 0 0-1-1H5a2 2 0 0 0 0 4h15a1 1 0 0 1 1 1v4h-3a2 2 0 0 0 0 4h3a1 1 0 0 0 1-1v-2a1 1 0 0 0-1-1"/><path d="M3 5v14a2 2 0 0 0 2 2h15a1 1 0 0 0 1-1v-4"/></svg>`,
  zap: `<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2"/></svg>`,
}

/* -------------------------------------------------------------
   Background Motion Generator (Orbs & Twinkling Dots)
   ------------------------------------------------------------- */
export function injectBackgroundMotion() {
  if (document.querySelector('.bg-motion-wrapper')) return
  const wrap = document.createElement('div')
  wrap.className = 'bg-motion-wrapper'
  wrap.setAttribute('aria-hidden', 'true')

  wrap.innerHTML = `
    <div class="bg-grid"></div>
    <div class="bg-orb bg-orb-1"></div>
    <div class="bg-orb bg-orb-2"></div>
    <div class="bg-orb bg-orb-3"></div>
  `

  // 12 tiny 3px dots
  for (let i = 0; i < 12; i++) {
    const dot = document.createElement('div')
    dot.className = 'bg-dot'
    dot.style.top = `${Math.floor(Math.random() * 90) + 5}%`
    dot.style.left = `${Math.floor(Math.random() * 90) + 5}%`
    dot.style.animationDelay = `${(i * 0.35).toFixed(2)}s`
    dot.style.animationDuration = `${3 + (i % 3)}s`
    wrap.appendChild(dot)
  }

  document.body.prepend(wrap)
}

/* -------------------------------------------------------------
   Role Metadata Dictionary
   ------------------------------------------------------------- */
export const ROLE_CONFIGS = {
  employee: {
    key: 'employee',
    portal: 'employee',
    title: 'Internal Employee',
    desc: 'Manage assigned matters, prepare documents, track deadlines, and complete your daily work.',
    tagline: 'Manage assigned matters, prepare documents, track deadlines, and complete your daily work.',
    iconName: 'briefcase',
    accentDark: '#F59E0B',
    accentLight: '#B45309',
  },
  management: {
    key: 'management',
    portal: 'management',
    title: 'Management / Executive',
    desc: 'Monitor organizational activity, review key decisions, oversee approvals, and track operational performance.',
    tagline: 'Monitor organizational activity, review key decisions, oversee approvals, and track operational performance.',
    iconName: 'barChart',
    accentDark: '#A78BFA',
    accentLight: '#6D28D9',
  },
  advocate: {
    key: 'advocate',
    portal: 'counsel',
    title: 'Advocate',
    desc: 'Review assigned legal matters, prepare case documents, and manage litigation-related workflows.',
    tagline: 'Review assigned legal matters, prepare case documents, and manage litigation-related workflows.',
    iconName: 'scale',
    accentDark: '#EAB308',
    accentLight: '#A16207',
  },
  counsel: {
    key: 'advocate',
    portal: 'counsel',
    title: 'Advocate',
    desc: 'Review assigned legal matters, prepare case documents, and manage litigation-related workflows.',
    tagline: 'Review assigned legal matters, prepare case documents, and manage litigation-related workflows.',
    iconName: 'scale',
    accentDark: '#EAB308',
    accentLight: '#A16207',
  },
  client: {
    key: 'client',
    portal: 'client',
    title: 'Client',
    desc: 'Access your matters, review documents, track updates, and respond to requests securely.',
    tagline: 'Access your matters, review documents, track updates, and respond to requests securely.',
    iconName: 'userCheck',
    accentDark: '#06B6D4',
    accentLight: '#0E7490',
  },
  tenant: {
    key: 'tenant',
    portal: 'tenant',
    title: 'Tenant or Buyer',
    desc: 'Manage property-related documents, review transactions, and track your assigned requirements.',
    tagline: 'Manage property-related documents, review transactions, and track your assigned requirements.',
    iconName: 'home',
    accentDark: '#F97316',
    accentLight: '#C2410C',
  },
  auditor: {
    key: 'auditor',
    portal: 'auditor',
    title: 'Auditor',
    desc: 'Review records, examine supporting evidence, and monitor compliance through authorized read-only access.',
    tagline: 'Review records, examine supporting evidence, and monitor compliance through authorized read-only access.',
    iconName: 'clipboardCheck',
    accentDark: '#EC4899',
    accentLight: '#BE185D',
  },
  admin: {
    key: 'admin',
    portal: 'admin',
    title: 'Administrator',
    desc: 'Manage user access, review approvals, oversee platform operations, and maintain audit records.',
    tagline: 'Manage user access, review approvals, oversee platform operations, and maintain audit records.',
    iconName: 'settings',
    accentDark: '#22D3EE',
    accentLight: '#0E7490',
  },
}

// Global initialization helper for every page
export function initCommonUI() {
  injectBackgroundMotion()
  initPageTransitions()
  initSpotlight()
  initTilt()
  initNumberTickers()
  initOfflineBanner()
  updateThemeButtons()

  document.querySelectorAll('[data-theme-toggle]').forEach((btn) => {
    btn.addEventListener('click', toggleTheme)
  })
}
