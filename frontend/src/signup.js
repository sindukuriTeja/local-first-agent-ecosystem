// Signup Controller
import { initCommonUI, icons } from './app.js'

document.addEventListener('DOMContentLoaded', () => {
  initCommonUI()

  const form = document.getElementById('signup-form')
  const nameInput = document.getElementById('signup-name')
  const emailInput = document.getElementById('signup-email')
  const passInput = document.getElementById('signup-pass')
  const nameErr = document.getElementById('signup-name-error')
  const emailErr = document.getElementById('signup-email-error')
  const passErr = document.getElementById('signup-pass-error')
  const submitBtn = document.getElementById('signup-submit-btn')
  const successBox = document.getElementById('signup-success')

  nameInput?.addEventListener('blur', () => {
    if (!nameInput.value.trim()) {
      nameInput.classList.add('has-error')
      nameErr.innerHTML = `${icons.alertTriangle} <span>Please enter your full legal or professional name.</span>`
      nameErr.style.display = 'flex'
    } else {
      nameInput.classList.remove('has-error')
      nameErr.style.display = 'none'
    }
  })

  emailInput?.addEventListener('blur', () => {
    const val = emailInput.value.trim()
    if (!val || !/\S+@\S+\.\S+/.test(val)) {
      emailInput.classList.add('has-error')
      emailErr.innerHTML = `${icons.alertTriangle} <span>Please provide a valid work email address.</span>`
      emailErr.style.display = 'flex'
    } else {
      emailInput.classList.remove('has-error')
      emailErr.style.display = 'none'
    }
  })

  passInput?.addEventListener('blur', () => {
    const val = passInput.value
    if (val.length < 12) {
      passInput.classList.add('has-error')
      passErr.innerHTML = `${icons.alertTriangle} <span>Password must be at least 12 characters long.</span>`
      passErr.style.display = 'flex'
    } else if (!/[0-9]/.test(val) || !/[!@#$%^&*(),.?":{}|<>]/.test(val)) {
      passInput.classList.add('has-error')
      passErr.innerHTML = `${icons.alertTriangle} <span>Password needs at least one number and one symbol.</span>`
      passErr.style.display = 'flex'
    } else {
      passInput.classList.remove('has-error')
      passErr.style.display = 'none'
    }
  })

  form?.addEventListener('submit', (e) => {
    e.preventDefault()
    const name = nameInput.value.trim()
    const email = emailInput.value.trim()
    const pass = passInput.value

    if (!name || !email || pass.length < 12) {
      if (!name) nameInput.focus()
      else if (!email) emailInput.focus()
      else passInput.focus()
      return
    }

    submitBtn.disabled = true
    submitBtn.innerHTML = `<span class="spinner" style="width: 16px; height: 16px; border-width: 2px;"></span> <span>Creating account...</span>`

    setTimeout(() => {
      form.style.display = 'none'
      successBox.style.display = 'flex'
    }, 600)
  })
})
