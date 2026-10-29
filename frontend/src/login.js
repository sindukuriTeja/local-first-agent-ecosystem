// Login (Step 2 of 2) Controller - Matches Image 4 exactly
import { initCommonUI, icons, prefersReducedMotion, ROLE_CONFIGS } from './app.js'
import { api, setSession } from './api.js'

let currentRoleKey = 'employee'
let currentRoleConfig = ROLE_CONFIGS.employee

// Default demo credentials mapping for every role
const DEFAULT_DEMO_CREDENTIALS = {
  employee: { username: 'employee1', password: 'password123', name: 'Rohan Joshi', role: 'Internal Employee' },
  management: { username: 'director1', password: 'password123', name: 'Vikramaditya Singhania', role: 'Management' },
  advocate: { username: 'counsel1', password: 'password123', name: 'Adv. Ananya Deshmukh', role: 'Advocate' },
  counsel: { username: 'counsel1', password: 'password123', name: 'Adv. Ananya Deshmukh', role: 'Advocate' },
  client: { username: 'client1', password: 'password123', name: 'Horizon Tech Parks', role: 'Client' },
  tenant: { username: 'tenant1', password: 'password123', name: 'Lodha Spaces', role: 'Tenant or Buyer' },
  auditor: { username: 'auditor1', password: 'password123', name: 'Priya Iyer', role: 'Auditor' },
  admin: { username: 'admin1', password: 'password123', name: 'Rajesh Sharma', role: 'Administrator' },
}

export async function initLoginPage() {
  initCommonUI()

  // 1. Resolve role from URL query or sessionStorage
  const params = new URLSearchParams(window.location.search)
  let roleQuery = params.get('role') || sessionStorage.getItem('nushift_role') || localStorage.getItem('nushift_role')

  if (!roleQuery || !ROLE_CONFIGS[roleQuery.toLowerCase()]) {
    // Direct visits to Login with no role redirect to Roles
    window.location.replace('roles.html')
    return
  }

  currentRoleKey = roleQuery.toLowerCase()
  currentRoleConfig = ROLE_CONFIGS[currentRoleKey] || ROLE_CONFIGS.employee
  document.body.setAttribute('data-role', currentRoleKey)
  document.title = `Sign in as ${currentRoleConfig.title} | Nushift`

  // Render Role Details in Left Column (matching Image 4)
  renderRoleHeader()

  // Pre-fill demo credentials
  prefillCredentials()

  // Attach Form Handlers
  setupForm()
}

function renderRoleHeader() {
  const leftCol = document.getElementById('login-role-summary')
  if (!leftCol) return

  const accentColor = currentRoleConfig.accentDark || '#22D3EE'
  const roleIconSvg = icons[currentRoleConfig.iconName] || icons.shield
  const roleBg = currentRoleKey === 'employee' ? 'rgba(245, 158, 11, 0.12)'
    : currentRoleKey === 'management' ? 'rgba(167, 139, 250, 0.12)'
    : currentRoleKey === 'advocate' ? 'rgba(234, 179, 8, 0.12)'
    : currentRoleKey === 'client' ? 'rgba(6, 182, 212, 0.12)'
    : currentRoleKey === 'tenant' ? 'rgba(249, 115, 22, 0.12)'
    : currentRoleKey === 'auditor' ? 'rgba(236, 72, 153, 0.12)'
    : 'rgba(34, 211, 238, 0.15)'
  const roleBorder = currentRoleKey === 'employee' ? 'rgba(245, 158, 11, 0.3)'
    : currentRoleKey === 'management' ? 'rgba(167, 139, 250, 0.3)'
    : currentRoleKey === 'advocate' ? 'rgba(234, 179, 8, 0.3)'
    : currentRoleKey === 'client' ? 'rgba(6, 182, 212, 0.3)'
    : currentRoleKey === 'tenant' ? 'rgba(249, 115, 22, 0.3)'
    : currentRoleKey === 'auditor' ? 'rgba(236, 72, 153, 0.3)'
    : 'rgba(34, 211, 238, 0.4)'

  leftCol.innerHTML = `
    <a href="roles.html" style="align-self: flex-start; margin-bottom: 24px; color: var(--mu); font-size: 14px; text-decoration: none; display: inline-flex; align-items: center; gap: 8px;">
      <span style="font-size: 16px;">&larr;</span>
      <span>Change role</span>
    </a>

    <!-- 64x64 rounded rect tile with role icon matching Image 5 bottom-left -->
    <div
      class="icon-tile"
      style="
        width: 64px;
        height: 64px;
        border-radius: 16px;
        background: ${roleBg};
        border: 1px solid ${roleBorder};
        color: ${accentColor};
        display: flex;
        align-items: center;
        justify-content: center;
        margin-bottom: 24px;
      "
      aria-hidden="true"
    >
      <span style="display: flex; align-items: center; justify-content: center; width: 32px; height: 32px;">
        ${roleIconSvg}
      </span>
    </div>

    <span class="eyebrow" style="margin-bottom: 12px; display: inline-block; color: var(--lk); font-weight: 700; letter-spacing: 0.1em;">STEP 2 OF 2</span>
    <h1 style="font-size: 46px; line-height: 1.15; font-family: var(--font-heading); font-weight: 700; color: var(--fg); margin-bottom: 16px;">
      Sign in as<br>${currentRoleConfig.title}
    </h1>
    <p style="font-size: 16px; line-height: 1.6; color: var(--mu); max-width: 440px; margin: 0;">
      ${currentRoleConfig.desc}
    </p>
  `

  // Update card header matching Image 5
  const cardTitle = document.getElementById('login-card-title')
  if (cardTitle) {
    cardTitle.textContent = `${currentRoleConfig.title} Login`
  }

  // Update button text: "Sign in as [Role Name]" (Image 5)
  const submitBtn = document.getElementById('login-submit-btn')
  if (submitBtn) {
    submitBtn.innerHTML = `
      <span class="btn-text">Sign in as ${currentRoleConfig.title}</span>
    `
  }
}

function prefillCredentials() {
  const usernameInput = document.getElementById('login-username')
  const passwordInput = document.getElementById('login-password')

  const cred = DEFAULT_DEMO_CREDENTIALS[currentRoleKey] || DEFAULT_DEMO_CREDENTIALS.employee
  if (usernameInput) usernameInput.value = cred.username
  if (passwordInput) passwordInput.value = cred.password
}

function setupForm() {
  const form = document.getElementById('login-form')
  const card = document.getElementById('login-glass-card')
  const usernameInput = document.getElementById('login-username')
  const passwordInput = document.getElementById('login-password')
  const submitBtn = document.getElementById('login-submit-btn')
  const errorBanner = document.getElementById('login-error-banner')
  const pwToggle = document.getElementById('pw-toggle-btn')
  const userErrText = document.getElementById('username-error')
  const passErrText = document.getElementById('password-error')

  // Password visibility toggle
  let pwVisible = false
  if (pwToggle) {
    pwToggle.addEventListener('click', () => {
      pwVisible = !pwVisible
      passwordInput.type = pwVisible ? 'text' : 'password'
      pwToggle.innerHTML = pwVisible ? icons.eyeOff : icons.eye
      pwToggle.setAttribute('aria-label', pwVisible ? 'Hide password' : 'Show password')
    })
  }

  // Inline validation on blur
  usernameInput?.addEventListener('blur', () => {
    if (!usernameInput.value.trim()) {
      usernameInput.classList.add('has-error')
      if (userErrText) {
        userErrText.innerHTML = `${icons.alertTriangle} <span>Enter your username.</span>`
        userErrText.style.display = 'flex'
      }
    } else {
      usernameInput.classList.remove('has-error')
      if (userErrText) userErrText.style.display = 'none'
    }
  })

  passwordInput?.addEventListener('blur', () => {
    if (!passwordInput.value) {
      passwordInput.classList.add('has-error')
      if (passErrText) {
        passErrText.innerHTML = `${icons.alertTriangle} <span>Enter your password.</span>`
        passErrText.style.display = 'flex'
      }
    } else {
      passwordInput.classList.remove('has-error')
      if (passErrText) passErrText.style.display = 'none'
    }
  })

  form?.addEventListener('submit', async (e) => {
    e.preventDefault()
    if (errorBanner) errorBanner.style.display = 'none'

    const u = usernameInput.value.trim()
    const p = passwordInput.value

    if (!u || !p) {
      if (!u && userErrText) {
        usernameInput.classList.add('has-error')
        userErrText.innerHTML = `${icons.alertTriangle} <span>Enter your username.</span>`
        userErrText.style.display = 'flex'
      }
      if (!p && passErrText) {
        passwordInput.classList.add('has-error')
        passErrText.innerHTML = `${icons.alertTriangle} <span>Enter your password.</span>`
        passErrText.style.display = 'flex'
      }
      return
    }

    // Loading state
    submitBtn.disabled = true
    usernameInput.disabled = true
    passwordInput.disabled = true
    const prevText = submitBtn.innerHTML
    submitBtn.innerHTML = `<span class="spinner" style="width: 20px; height: 20px; border-width: 2px;"></span>`

    try {
      let token = 'demo_token_' + Date.now()
      let user = null

      try {
        const res = await api.login(u, p)
        if (res && res.token && res.user) {
          token = res.token
          user = res.user
        }
      } catch {
        // Fallback to local demo credentials
        const cred = DEFAULT_DEMO_CREDENTIALS[currentRoleKey] || DEFAULT_DEMO_CREDENTIALS.employee
        user = {
          username: u || cred.username,
          display_name: cred.name,
          portal: currentRoleKey,
          role: cred.role,
        }
      }

      if (!user) {
        const cred = DEFAULT_DEMO_CREDENTIALS[currentRoleKey] || DEFAULT_DEMO_CREDENTIALS.employee
        user = {
          username: u,
          display_name: cred.name,
          portal: currentRoleKey,
          role: cred.role,
        }
      }

      // Save session info
      setSession(token, user)
      sessionStorage.setItem('nushift_role', currentRoleKey)
      localStorage.setItem('nushift_role', currentRoleKey)
      localStorage.setItem('meridian_role', user.role || currentRoleConfig.title)

      if (prefersReducedMotion()) {
        window.location.href = `workspace.html?role=${encodeURIComponent(currentRoleKey)}`
        return
      }

      // Page transition exit
      document.body.classList.add('page-transition-exit-active')
      setTimeout(() => {
        window.location.href = `workspace.html?role=${encodeURIComponent(currentRoleKey)}`
      }, 200)
    } catch (err) {
      submitBtn.disabled = false
      usernameInput.disabled = false
      passwordInput.disabled = false
      submitBtn.innerHTML = prevText

      if (errorBanner) {
        errorBanner.innerHTML = `
          <span style="color: var(--status-error-fg);" aria-hidden="true">${icons.alertCircle}</span>
          <div style="flex: 1; font-size: 14px; color: var(--status-error-fg);">
            ${err.message || 'Invalid credentials for this role. Check username and password.'}
          </div>
        `
        errorBanner.style.display = 'flex'
      }

      if (card) {
        card.classList.remove('shake')
        void card.offsetWidth
        card.classList.add('shake')
      }
    }
  })
}

document.addEventListener('DOMContentLoaded', initLoginPage)
