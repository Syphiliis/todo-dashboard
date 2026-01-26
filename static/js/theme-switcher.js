/**
 * iOS-like Theme Switcher
 * Handles light/dark mode toggle with localStorage persistence
 */

(function() {
  'use strict';

  const THEME_KEY = 'theme';
  const THEME_LIGHT = 'light';
  const THEME_DARK = 'dark';

  /**
   * Set theme on document element and persist to localStorage
   * @param {string} theme - 'light' or 'dark'
   */
  function setTheme(theme) {
    if (theme !== THEME_LIGHT && theme !== THEME_DARK) {
      console.warn(`Invalid theme: ${theme}. Falling back to light.`);
      theme = THEME_LIGHT;
    }

    // Update DOM
    document.documentElement.setAttribute('data-theme', theme);

    // Update Tailwind dark mode class (for backward compatibility)
    if (theme === THEME_DARK) {
      document.documentElement.classList.add('dark');
    } else {
      document.documentElement.classList.remove('dark');
    }

    // Persist to localStorage
    try {
      localStorage.setItem(THEME_KEY, theme);
    } catch (e) {
      console.error('Failed to save theme to localStorage:', e);
    }

    // Dispatch custom event for other scripts to listen
    window.dispatchEvent(new CustomEvent('themechange', { detail: { theme } }));
  }

  /**
   * Get current theme from data attribute
   * @returns {string} 'light' or 'dark'
   */
  function getTheme() {
    return document.documentElement.getAttribute('data-theme') || THEME_LIGHT;
  }

  /**
   * Toggle between light and dark themes
   */
  function toggleTheme() {
    const currentTheme = getTheme();
    const newTheme = currentTheme === THEME_DARK ? THEME_LIGHT : THEME_DARK;
    setTheme(newTheme);
  }

  /**
   * Initialize theme on page load
   * Priority: localStorage > system preference > default (light)
   */
  function initTheme() {
    let theme = THEME_LIGHT;

    // Try to get saved preference from localStorage
    try {
      const savedTheme = localStorage.getItem(THEME_KEY);
      if (savedTheme === THEME_LIGHT || savedTheme === THEME_DARK) {
        theme = savedTheme;
      } else {
        // No valid saved preference, check system preference
        const prefersDark = window.matchMedia('(prefers-color-scheme: dark)').matches;
        theme = prefersDark ? THEME_DARK : THEME_LIGHT;
      }
    } catch (e) {
      console.error('Failed to read theme from localStorage:', e);
      // Fallback to system preference
      const prefersDark = window.matchMedia('(prefers-color-scheme: dark)').matches;
      theme = prefersDark ? THEME_DARK : THEME_LIGHT;
    }

    setTheme(theme);
  }

  /**
   * Listen to system theme changes
   */
  function watchSystemTheme() {
    try {
      const mediaQuery = window.matchMedia('(prefers-color-scheme: dark)');

      // Modern API
      if (mediaQuery.addEventListener) {
        mediaQuery.addEventListener('change', (e) => {
          // Only auto-switch if user hasn't set a preference
          const savedTheme = localStorage.getItem(THEME_KEY);
          if (!savedTheme) {
            setTheme(e.matches ? THEME_DARK : THEME_LIGHT);
          }
        });
      }
      // Legacy API fallback
      else if (mediaQuery.addListener) {
        mediaQuery.addListener((e) => {
          const savedTheme = localStorage.getItem(THEME_KEY);
          if (!savedTheme) {
            setTheme(e.matches ? THEME_DARK : THEME_LIGHT);
          }
        });
      }
    } catch (e) {
      console.error('Failed to watch system theme changes:', e);
    }
  }

  /**
   * Setup theme toggle button
   */
  function setupToggleButton() {
    // Wait for DOM to be ready
    if (document.readyState === 'loading') {
      document.addEventListener('DOMContentLoaded', attachToggleListener);
    } else {
      attachToggleListener();
    }
  }

  /**
   * Attach click listener to theme toggle button
   */
  function attachToggleListener() {
    const toggleButton = document.getElementById('themeToggle');

    if (toggleButton) {
      toggleButton.addEventListener('click', (e) => {
        e.preventDefault();
        toggleTheme();

        // Add a subtle animation feedback
        toggleButton.style.transform = 'scale(0.95)';
        setTimeout(() => {
          toggleButton.style.transform = '';
        }, 150);
      });
    }
  }

  /**
   * Expose API to window for external usage
   */
  window.themeManager = {
    setTheme,
    getTheme,
    toggleTheme,
    THEME_LIGHT,
    THEME_DARK
  };

  // Initialize immediately (before DOM ready to avoid flash)
  initTheme();

  // Setup system theme watcher
  watchSystemTheme();

  // Setup toggle button when DOM is ready
  setupToggleButton();

})();
