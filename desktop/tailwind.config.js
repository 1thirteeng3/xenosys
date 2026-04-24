/**
 * XenoSys Design System - Tailwind Configuration
 * Cyber-Minimalist Theme
 * 
 * Color Palette:
 * - bg: #0A0A0A (App Background)
 * - surface: #121212 (Cards and Panels)
 * - border: #2A2A2A (Dividers)
 * - accent.active: #00FF9D (Cyber Green - Active/Approved)
 * - accent.alert: #FFB000 (Amber - Pending/HITL)
 * - accent.error: #FF3366 (Pink/Red - Error/Rejected)
 * - accent.cloud: #00B8FF (Cyan - Cloud/Neutral Action)
 */

export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        xeno: {
          bg: '#0A0A0A',
          surface: '#121212',
          border: '#2A2A2A',
          accent: {
            active: '#00FF9D',
            alert: '#FFB000',
            error: '#FF3366',
            cloud: '#00B8FF',
          },
        },
      },
      fontFamily: {
        sans: ['Inter', 'Geist Sans', 'system-ui', 'sans-serif'],
        mono: ['JetBrains Mono', 'Fira Code', 'monospace'],
      },
      boxShadow: {
        'glow-active': '0 0 20px rgba(0, 255, 157, 0.3)',
        'glow-alert': '0 0 20px rgba(255, 176, 0, 0.3)',
        'glow-error': '0 0 20px rgba(255, 51, 102, 0.3)',
        'glow-cloud': '0 0 20px rgba(0, 184, 255, 0.3)',
      },
      animation: {
        'pulse-slow': 'pulse 3s cubic-bezier(0.4, 0, 0.6, 1) infinite',
        'flash-green': 'flashGreen 0.5s ease-out',
      },
      keyframes: {
        flashGreen: {
          '0%': { backgroundColor: 'rgba(0, 184, 255, 0.5)' },
          '100%': { backgroundColor: 'transparent' },
        },
      },
    },
  },
  plugins: [],
}