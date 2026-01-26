/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    "./pages/**/*.{js,ts,jsx,tsx}",
    "./components/**/*.{js,ts,jsx,tsx}"
  ],
  darkMode: ['class', '[data-theme="dark"]'],
  theme: {
    extend: {
      colors: {
        // iOS-like Design System colors
        base: '#f5f5f7',
        surface: '#ffffff',
        'surface-2': '#fafafa',
        'surface-3': '#ffffff',
        accent: '#3b82f6',
        secondary: '#3b82f6',
        muted: '#86868b',
        faint: '#aeaeb2',
        border: 'rgba(0, 0, 0, 0.1)',
        success: '#10b981',
        warning: '#f59e0b',
        danger: '#ef4444',
        info: '#3b82f6',
      },
      fontFamily: {
        sans: ['-apple-system', 'BlinkMacSystemFont', '"SF Pro Display"', '"SF Pro Text"', '"Segoe UI"', '"Inter"', 'sans-serif'],
      },
      borderRadius: {
        'sm': '8px',
        'md': '10px',
        'lg': '16px',
        'xl': '20px',
      }
    }
  },
  plugins: []
};

