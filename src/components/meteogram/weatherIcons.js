// Hand-drawn static SVG paths, 24x24 viewBox. No third-party icon assets.
const sun = '<circle cx="12" cy="12" r="4" fill="none" stroke="currentColor" stroke-width="1.6"/>'
  + '<g stroke="currentColor" stroke-width="1.6" stroke-linecap="round">'
  + '<path d="M12 2.5v2.2M12 19.3v2.2M2.5 12h2.2M19.3 12h2.2M5.1 5.1l1.6 1.6M17.3 17.3l1.6 1.6M18.9 5.1l-1.6 1.6M6.7 17.3l-1.6 1.6"/></g>';
const moon = '<path d="M15.5 3.8a7.2 7.2 0 1 0 4.6 12.6 6 6 0 1 1-4.6-12.6z" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linejoin="round"/>';
const cloud = '<path d="M7 17.5h9.2a3.6 3.6 0 0 0 .5-7.2 4.6 4.6 0 0 0-8.8-1.2A3.3 3.3 0 0 0 7 17.5z" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linejoin="round"/>';
const drops = '<g stroke="currentColor" stroke-width="1.4" stroke-linecap="round"><path d="M8 19.2l-1.1 2M12 19.2v2M16 19.2l1.1 2"/></g>';
const heavy = '<g stroke="currentColor" stroke-width="1.5" stroke-linecap="round"><path d="M7.4 18.4l-1.4 2.6M12 18.4v2.6M16.6 18.4l1.4 2.6"/></g>';

export const WEATHER_ICONS = {
  clear_day: sun,
  clear_night: moon,
  partly_cloudy_day: `<g transform="translate(-3,-2) scale(.72)">${sun}</g><g transform="translate(2,3)">${cloud}</g>`,
  partly_cloudy_night: `<g transform="translate(-3,-2) scale(.72)">${moon}</g><g transform="translate(2,3)">${cloud}</g>`,
  cloudy: cloud,
  rain: `${cloud}${drops}`,
  heavy_rain: `${cloud}${heavy}`,
};

export function weatherIconSvg(id) {
  return WEATHER_ICONS[id] || '';
}
