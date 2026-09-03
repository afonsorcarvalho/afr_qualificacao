import type { Config } from 'tailwindcss'

const config: Config = {
  content: [
    './pages/**/*.{js,ts,jsx,tsx,mdx}',
    './components/**/*.{js,ts,jsx,tsx,mdx}',
    './app/**/*.{js,ts,jsx,tsx,mdx}',
  ],
  darkMode: 'class',
  theme: {
    extend: {
      colors: {
        dark: {
          900: '#030712',
          800: '#0a0f1e',
          700: '#0d1424',
          600: '#111827',
          500: '#1a2234',
        },
        neon: {
          blue:   '#00d4ff',
          purple: '#a855f7',
          pink:   '#ec4899',
          green:  '#10b981',
          orange: '#f59e0b',
          cyan:   '#06b6d4',
        },
      },
      backgroundImage: {
        'gradient-radial': 'radial-gradient(var(--tw-gradient-stops))',
        'gradient-cyber': 'linear-gradient(135deg, #00d4ff 0%, #a855f7 50%, #ec4899 100%)',
        'mesh-gradient': [
          'radial-gradient(at 40% 20%, hsla(228,100%,74%,0.15) 0px, transparent 50%)',
          'radial-gradient(at 80% 0%, hsla(189,100%,56%,0.1) 0px, transparent 50%)',
          'radial-gradient(at 0% 50%, hsla(355,100%,93%,0.05) 0px, transparent 50%)',
          'radial-gradient(at 80% 50%, hsla(340,100%,76%,0.1) 0px, transparent 50%)',
          'radial-gradient(at 0% 100%, hsla(22,100%,77%,0.05) 0px, transparent 50%)',
        ].join(', '),
      },
      boxShadow: {
        'glow-blue':   '0 0 20px rgba(0, 212, 255, 0.3), 0 0 60px rgba(0, 212, 255, 0.1)',
        'glow-purple': '0 0 20px rgba(168, 85, 247, 0.3), 0 0 60px rgba(168, 85, 247, 0.1)',
        'glow-pink':   '0 0 20px rgba(236, 72, 153, 0.3), 0 0 60px rgba(236, 72, 153, 0.1)',
        'glow-sm':     '0 0 10px rgba(0, 212, 255, 0.2)',
        'glass':       '0 8px 32px rgba(0, 0, 0, 0.4), inset 0 1px 0 rgba(255,255,255,0.1)',
        'glass-lg':    '0 25px 50px rgba(0, 0, 0, 0.5), inset 0 1px 0 rgba(255,255,255,0.1)',
      },
      animation: {
        'float':          'float 6s ease-in-out infinite',
        'pulse-glow':     'pulseGlow 2s ease-in-out infinite',
        'shimmer':        'shimmer 2s linear infinite',
        'gradient-shift': 'gradientShift 8s ease infinite',
      },
      keyframes: {
        float: {
          '0%, 100%': { transform: 'translateY(0px)' },
          '50%':      { transform: 'translateY(-10px)' },
        },
        pulseGlow: {
          '0%, 100%': { opacity: '1', boxShadow: '0 0 20px rgba(0, 212, 255, 0.3)' },
          '50%':      { opacity: '0.8', boxShadow: '0 0 40px rgba(0, 212, 255, 0.6)' },
        },
        shimmer: {
          '0%':   { backgroundPosition: '-200% center' },
          '100%': { backgroundPosition: '200% center' },
        },
        gradientShift: {
          '0%, 100%': { backgroundPosition: '0% 50%' },
          '50%':      { backgroundPosition: '100% 50%' },
        },
      },
    },
  },
  plugins: [],
}

export default config
