/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,jsx}'],
  theme: {
    extend: {
      colors: {
        paper: '#F7F7F7',
        ink: '#101010',
        panchayat: {
          50: '#F1F1F1',
          100: '#E2E2E2',
          300: '#A8A8A8',
          500: '#4B4B4B',
          600: '#242424',
          700: '#101010',
          900: '#000000',
        },
        marigold: {
          100: '#FFE5E5',
          300: '#FFAAAA',
          500: '#E32626',
          600: '#B91717',
        },
        brick: {
          100: '#F3DAD6',
          500: '#B23A2E',
          600: '#8F2C22',
        },
        sand: '#E9E9E9',
      },
      fontFamily: {
        display: ['"Fraunces"', 'serif'],
        sans: ['"Inter"', 'sans-serif'],
        mono: ['"JetBrains Mono"', 'monospace'],
      },
      borderRadius: {
        sm: '2px',
      },
      keyframes: {
        'nav-in': {
          '0%': { opacity: '0', transform: 'translateX(-10px)' },
          '100%': { opacity: '1', transform: 'translateX(0)' },
        },
        'fade-in': {
          '0%': { opacity: '0' },
          '100%': { opacity: '1' },
        },
        'fade-in-down': {
          '0%': { opacity: '0', transform: 'translateY(-6px)' },
          '100%': { opacity: '1', transform: 'translateY(0)' },
        },
        'scale-in': {
          '0%': { opacity: '0', transform: 'scale(0.94) translateY(-6px)' },
          '100%': { opacity: '1', transform: 'scale(1) translateY(0)' },
        },
        'glow-pulse': {
          '0%, 100%': { opacity: '0.55', transform: 'scale(1)' },
          '50%': { opacity: '1', transform: 'scale(1.12)' },
        },
      },
      animation: {
        'nav-in': 'nav-in 0.45s cubic-bezier(0.16,1,0.3,1) both',
        'fade-in': 'fade-in 0.4s ease-out both',
        'fade-in-down': 'fade-in-down 0.35s cubic-bezier(0.16,1,0.3,1) both',
        'scale-in': 'scale-in 0.16s cubic-bezier(0.16,1,0.3,1) both',
        'glow-pulse': 'glow-pulse 3.5s ease-in-out infinite',
      },
    },
  },
  plugins: [],
}
