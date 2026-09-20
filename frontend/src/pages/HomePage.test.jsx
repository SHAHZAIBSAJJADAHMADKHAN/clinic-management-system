import { fireEvent, render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { HomePage } from './HomePage'

describe('HomePage navigation and interactive landing content', () => {
  it('preserves the existing sign-in entry point for appointment and sign-in actions', () => {
    render(<MemoryRouter><HomePage /></MemoryRouter>)
    expect(screen.getByRole('link', { name: 'Sign In' })).toHaveAttribute('href', '/sign-in')
    expect(screen.getByRole('link', { name: /Book an Appointment/ })).toHaveAttribute('href', '/sign-in')
  })

  it('provides anatomy controls and resets the selected view safely', () => {
    render(<MemoryRouter><HomePage /></MemoryRouter>)
    fireEvent.click(screen.getByRole('button', { name: 'Brain' }))
    expect(screen.getByRole('button', { name: 'Brain' })).toHaveClass('is-selected')
    fireEvent.click(screen.getByRole('button', { name: 'Reset view' }))
    expect(screen.getByRole('button', { name: 'Heart' })).toHaveClass('is-selected')
  })

  it('keeps headline words readable and applies the controlled fragment state on hover', () => {
    render(<MemoryRouter><HomePage /></MemoryRouter>)
    const health = screen.getByLabelText('Health')
    fireEvent.pointerEnter(health)
    expect(health.closest('.fragment-word')).toHaveClass('is-fragmenting')
  })

  it('uses four distinct doctor portraits and keeps header navigation out of the footer', () => {
    render(<MemoryRouter><HomePage /></MemoryRouter>)
    const portraits = [
      screen.getByAltText('Dr. Ali Raza, Cardiologist'),
      screen.getByAltText('Dr. Sarah Khan, General Physician'),
      screen.getByAltText('Dr. Usman Malik, Orthopedic Surgeon'),
      screen.getByAltText('Dr. Ayesha Siddiqui, Pediatrician'),
    ]

    expect(new Set(portraits.map((portrait) => portrait.getAttribute('src'))).size).toBe(4)
    expect(document.querySelector('.landing-footer')).not.toHaveTextContent('Home')
  })
})
