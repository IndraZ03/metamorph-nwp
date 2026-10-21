const { join } = require('path');
const { skeleton } = require('@skeletonlabs/tw-plugin');

/** @type {import('tailwindcss').Config} */
module.exports = {
  darkMode: 'class',
  content: [
    './index.html',
    './src/**/*.{html,js,svelte,ts}',
    join(require.resolve('@skeletonlabs/skeleton'), '../**/*.{html,js,svelte,ts}')
  ],
  theme: {
    extend: {
      fontFamily: {
        sans: ['Inter', 'system-ui', '-apple-system', 'Segoe UI', 'Roboto', 'sans-serif'],
      }
    },
  },
  plugins: [
    skeleton({
      themes: {
        preset: [
          { name: 'skeleton', enhancements: true },
          { name: 'modern', enhancements: true },
        ]
      }
    })
  ],
};
