// Nushift Landing Page Controller
// Orbit Math, GSAP Reveal, Animated Beams, Hamburger Menu
import { initCommonUI, icons, prefersReducedMotion } from './app.js'

const PRACTICE_AREAS = [
  { name: 'Tax', iconSvg: icons.receipt || icons.fileText },
  { name: 'Legal', iconSvg: icons.scale },
  { name: 'Litigation', iconSvg: icons.gavel || icons.scale },
  { name: 'Corporate', iconSvg: icons.building },
  { name: 'Property', iconSvg: icons.home },
  { name: 'Projects', iconSvg: icons.barChart },
  { name: 'Compliance', iconSvg: icons.shieldCheck || icons.shield },
]

export function initLandingPage() {
  initCommonUI()
  setupOrbit()
  setupMobileNav()
  setupGSAPAnimations()
}

// 5.1 Rotating Orbit: Seven glass pills placed evenly on a radius of 230px
function setupOrbit() {
  const ringGroup = document.getElementById('orbit-ring-group')
  if (!ringGroup) return

  const total = PRACTICE_AREAS.length
  const radius = 230 // radius on desktop; on mobile CSS scales with container

  ringGroup.innerHTML = PRACTICE_AREAS.map((area, i) => {
    // 360/7 degrees, starting at the top (-90deg or 0deg if top is -90)
    const angleDeg = (360 / total) * i - 90
    const angleRad = (angleDeg * Math.PI) / 180
    const x = Math.round(radius * Math.cos(angleRad))
    const y = Math.round(radius * Math.sin(angleRad))

    return `
      <div class="orbit-pill-holder" style="transform: translate(${x}px, ${y}px);">
        <a
          href="#practice-areas"
          class="orbit-pill"
          aria-label="Practice area: ${area.name}"
        >
          <span class="orbit-pill-icon" style="display:inline-flex; align-items:center; justify-content:center; width:15px; height:15px; margin-right:7px; color:var(--lk); flex-shrink:0;">
            ${area.iconSvg}
          </span>
          <span>${area.name}</span>
        </a>
      </div>
    `
  }).join('')

  // Adjust radius on window resize for smaller screens
  function handleResize() {
    const isMobile = window.innerWidth <= 768
    const r = isMobile ? 120 : 230
    const holders = ringGroup.querySelectorAll('.orbit-pill-holder')
    holders.forEach((holder, idx) => {
      const angleDeg = (360 / total) * idx - 90
      const angleRad = (angleDeg * Math.PI) / 180
      const x = Math.round(r * Math.cos(angleRad))
      const y = Math.round(r * Math.sin(angleRad))
      holder.style.transform = `translate(${x}px, ${y}px)`
    })
  }

  window.addEventListener('resize', handleResize)
  handleResize()
}

function setupMobileNav() {
  const btn = document.getElementById('mobile-menu-btn')
  const panel = document.getElementById('mobile-nav-panel')
  if (!btn || !panel) return

  let open = false
  btn.addEventListener('click', () => {
    open = !open
    btn.setAttribute('aria-expanded', open ? 'true' : 'false')
    btn.innerHTML = open ? icons.x : icons.menu
    panel.classList.toggle('open', open)
  })

  panel.querySelectorAll('a').forEach((link) => {
    link.addEventListener('click', () => {
      open = false
      btn.innerHTML = icons.menu
      panel.classList.remove('open')
    })
  })
}

// 9. GSAP animations with exact values
function setupGSAPAnimations() {
  if (prefersReducedMotion() || typeof window === 'undefined' || !window.gsap) return

  const gsap = window.gsap
  const ScrollTrigger = window.ScrollTrigger
  if (ScrollTrigger) gsap.registerPlugin(ScrollTrigger)

  // 1. Hero text reveal: words y 20 to 0, opacity 0 to 1, blur 8px to 0, duration 0.5, stagger 0.06, ease power2.out
  const h1 = document.querySelector('.hero-h1-reveal')
  if (h1) {
    const text = h1.textContent.trim()
    const words = text.split(/\s+/)
    h1.innerHTML = words
      .map((w) => `<span class="word-span" style="display: inline-block; filter: blur(8px); opacity: 0; transform: translateY(20px);">${w}&nbsp;</span>`)
      .join('')

    gsap.to(h1.querySelectorAll('.word-span'), {
      y: 0,
      opacity: 1,
      filter: 'blur(0px)',
      duration: 0.5,
      stagger: 0.06,
      ease: 'power2.out',
      delay: 0.1,
    })
  }

  // 2. Hero buttons and subtext: y 24 to 0, opacity, duration 0.5, stagger 0.1
  const heroItems = document.querySelectorAll('.hero-fade-item')
  if (heroItems.length > 0) {
    gsap.fromTo(
      heroItems,
      { y: 24, opacity: 0 },
      { y: 0, opacity: 1, duration: 0.5, stagger: 0.1, ease: 'power2.out', delay: 0.4 }
    )
  }

  // 3. Scroll reveal for sections: y 32 to 0, opacity 0 to 1, duration 0.5, start: "top 85%", once
  if (ScrollTrigger) {
    const sections = document.querySelectorAll('.scroll-reveal-section')
    sections.forEach((sec) => {
      gsap.fromTo(
        sec,
        { y: 32, opacity: 0 },
        {
          y: 0,
          opacity: 1,
          duration: 0.5,
          ease: 'power2.out',
          scrollTrigger: {
            trigger: sec,
            start: 'top 85%',
            once: true,
          },
        }
      )
    })

    // Subtle parallax on background orbs: move y -60 over hero scroll, scrub 0.6
    const orbs = document.querySelectorAll('.bg-orb')
    if (orbs.length > 0) {
      gsap.to(orbs, {
        y: -60,
        ease: 'none',
        scrollTrigger: {
          trigger: 'body',
          start: 'top top',
          end: 'bottom bottom',
          scrub: 0.6,
        },
      })
    }
  }
}

document.addEventListener('DOMContentLoaded', initLandingPage)
