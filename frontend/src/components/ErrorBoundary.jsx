import { Component } from 'react'

export default class ErrorBoundary extends Component {
  constructor(props) {
    super(props)
    this.state = { hasError: false }
  }

  static getDerivedStateFromError() {
    return { hasError: true }
  }

  componentDidCatch(error, info) {
    // eslint-disable-next-line no-console
    console.error('Unhandled UI error:', error, info)
  }

  render() {
    if (this.state.hasError) {
      return (
        <div className="min-h-screen flex items-center justify-center bg-paper px-6">
          <div className="max-w-sm text-center">
            <h1 className="font-display text-2xl text-panchayat-700 mb-2">Something went wrong</h1>
            <p className="text-sm text-ink/60 mb-5">
              This screen ran into an unexpected error. Your data is safe — reloading usually fixes it.
            </p>
            <button
              onClick={() => window.location.reload()}
              className="px-5 py-2.5 bg-panchayat-600 text-paper text-sm rounded-sm hover:bg-panchayat-700"
            >
              Reload page
            </button>
          </div>
        </div>
      )
    }
    return this.props.children
  }
}
