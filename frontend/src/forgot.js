// Forgot Password Controller
import { initCommonUI, icons } from './app.js'

document.addEventListener('DOMContentLoaded', () => {
  initCommonUI()

  const form = document.getElementById('forgot-form')
  const emailInput = document.getElementById('forgot-email')
  const emailErr = document.getElementById('forgot-email-error')
  const successBanner = document.getElementById('forgot-success')
  const submitBtn = document.getElementById('forgot-submit-btn')

  emailInput?.addEventListener('blur', () => {
    const val = emailInput.value.trim()
    if (!val || !/\S+@\S+\.\S+/.test(val)) {
      emailInput.classList.add('has-error')
      emailErr.innerHTML = `${icons.alertTriangle} <span>Enter a valid work email address.</span>`
      emailErr.style.display = 'flex'
    } else {
      emailInput.classList.remove('has-error')
      emailErr.style.display = 'none'
    }
  })

  form?.addEventListener('submit', (e) => {
    e.preventDefault()
    const val = emailInput.value.trim()
    if (!val || !/\S+@\S+\.\S+/.test(val)) {
      emailInput.classList.add('has-error')
      emailErr.innerHTML = `${icons.alertTriangle} <span>Enter a valid work email address.</span>`
      emailErr.style.display = 'flex'
      return
    }

    submitBtn.disabled = true
    submitBtn.innerHTML = `<span class="spinner" style="width: 16px; height: 16px; border-width: 2px;"></span> <span>Sending link...</span>`

    setTimeout(() => {
      form.style.display = 'none'
      successBanner.style.display = 'flex'
    }, 600)
  })
})
