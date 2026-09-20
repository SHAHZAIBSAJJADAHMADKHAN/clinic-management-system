import { render, screen } from '@testing-library/react'
import { App } from './App'

describe('application foundation', () => {
  it('renders the home screen', () => {
    render(<App />)

    expect(screen.getByRole('heading', { name: /your health.*our priority/i })).toBeInTheDocument()
    expect(screen.getByRole('link', { name: /book appointment/i })).toHaveAttribute('href', '/sign-in')
  })
})
