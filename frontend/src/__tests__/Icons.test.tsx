import { describe, it, expect } from 'vitest'
import { render } from '@testing-library/react'
import { Search, Bookmark, Moon, Sun, Play, Pause } from '../components/Icons'

describe('Icons', () => {
  it('renders Search icon as an svg', () => {
    const { container } = render(<Search />)
    const svg = container.querySelector('svg')
    expect(svg).toBeInTheDocument()
    expect(svg?.tagName).toBe('svg')
  })

  it('renders Bookmark icon with active fill', () => {
    const { container } = render(<Bookmark active />)
    const svg = container.querySelector('svg')
    expect(svg).toHaveAttribute('fill', 'currentColor')
  })

  it('renders Bookmark icon without active fill', () => {
    const { container } = render(<Bookmark active={false} />)
    const svg = container.querySelector('svg')
    expect(svg).toHaveAttribute('fill', 'none')
  })

  it('renders Moon icon', () => {
    const { container } = render(<Moon />)
    expect(container.querySelector('svg')).toBeInTheDocument()
  })

  it('renders Sun icon', () => {
    const { container } = render(<Sun />)
    expect(container.querySelector('svg')).toBeInTheDocument()
  })

  it('renders Play icon with fill', () => {
    const { container } = render(<Play />)
    const svg = container.querySelector('svg')
    expect(svg).toHaveAttribute('fill', 'currentColor')
  })

  it('renders Pause icon', () => {
    const { container } = render(<Pause />)
    expect(container.querySelector('svg')).toBeInTheDocument()
  })

  it('applies custom className', () => {
    const { container } = render(<Search className="custom-class" />)
    const svg = container.querySelector('svg')
    expect(svg).toHaveClass('custom-class')
  })
})
