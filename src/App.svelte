<script>
  import { mount, onMount, unmount } from 'svelte';
  import maplibregl from 'maplibre-gl';
  import Toolbar from './components/Toolbar.svelte';
  import ParamToolbar from './components/ParamToolbar.svelte';
  import RadarModal from './components/RadarModal.svelte';
  import SatelliteModal from './components/SatelliteModal.svelte';
  import LayerControl from './components/LayerControl.svelte';
  import UserLayers from './components/UserLayers.svelte';
  import NwpPopup from './components/NwpPopup.svelte';
  import { proxyCuaca, proxySatelliteTile } from './services/bmkg.js';
  import {
    ECMWF_POLL_MS,
    GLOBAL_MODELS,
    MODELS,
    defaultVar,
    fetchLatest as fetchNwpLatest,
    modelBbox,
    modelRunId,
    modelRunTime,
    modelZoom,
    paramsFor,
    pickStep as pickNwpStep,
    sourceKey as nwpSourceKey,
    tileUrl as nwpTileUrl,
  } from './services/nwp.js';
  import { inspectValues, reverseGeocode } from './services/numericTiles.js';
  import { bboxOf, colorFor, countByGeometry, layerDefs } from './services/userLayers.js';
  import { WindOverlay } from './services/windAnimation.js';
  import ForecastControl from './components/ForecastControl.svelte';
  import { timelineTime, reconcileTimeline } from './services/forecastTimeline.js';
  import LandslideLegend from './components/LandslideLegend.svelte';
  import FloodLegend from './components/FloodLegend.svelte';
  import { fetchFloodMetadata, floodTileUrl, fetchFloodPoint, pointContent as floodPointContent } from './services/flood.js';
  import { fetchLandslideMetadata, landslideTileUrl, fetchLandslidePoint, pointContent } from './services/landslide.js';

  // State management using Svelte 5 runes
  let mapContainer = $state(null);
  let map = $state(null);
  let mapLoaded = $state(false);

  // Modals visibility
  let showRadarModal = $state(false);
  let showSatelliteModal = $state(false);

  // Active layer records
  let radarData = $state(null);
  let satelliteData = $state(null);
  let activeModel = $state(null);
  let nwpVar = $state(defaultVar('ecmwf'));
  let nwpData = $state(null);
  let nwpKey = $state(null);
  let nwpPollId = null;
  let nwpAttribControl = null;
  let nwpInspect = null;
  let nwpPopup = null;
  let nwpPopupApp = null;
  let nwpHost = null;
  let nwpClickSeq = 0;
  let nwpPop = $state({ loading: false, data: null, error: null });

  // Wind animation state
  let windActive = $state(false);
  let windSpeed = $state(1.0);
  let windOverlay = null;
  let windStatus = $state({ state: 'ready', mode: 'demo', message: 'Simulasi — bukan data model' });

  let forecastRows = $state([]);
  let forecastStep = $state(null);
  let forecastRunTime = $state('');
  let landslideMeta = $state(null);
  let landslideError = $state('');
  let landslideOpacity = $state(0.6);
  let landslideVisible = $state(true);
  let landslideRequest = null;
  let landslidePointRequest = null;
  let landslidePopup = null;
  let landslidePoll = null;
  let nwpRequestSeq = 0;

  let floodMeta = $state(null);
  let floodError = $state('');
  let floodNotice = $state('');
  let floodOpacity = $state(0.6);
  let floodVisible = $state(true);
  let floodIndicator = $state('rainfall');
  let floodMode = $state('screening');
  let floodRequest, floodPointRequest, floodPopup, floodPoll;
  let floodGeneration = 0;
  let timelineAnchor = null;
  let timelineNotice = $state('');

  function currentTimelineAnchor() {
    const row = forecastRows.find((r) => Number(r.step) === forecastStep);
    return row ? { runTime: forecastRunTime, validTime: timelineTime(row, forecastRunTime) } : timelineAnchor;
  }

  function clearFlood() {
    floodGeneration++;
    floodPointRequest?.abort();
    floodPopup?.remove();
    floodPopup = null;
    if (map?.getLayer('flood-layer')) map.removeLayer('flood-layer');
    if (map?.getSource('flood-source')) map.removeSource('flood-source');
  }

  function stopFlood() {
    floodRequest?.abort();
    clearInterval(floodPoll);
    floodPoll = null;
    clearFlood();
  }

  function renderFlood() {
    clearFlood();
    if (!map?.isStyleLoaded() || activeModel !== 'flood' || !floodMeta || !floodVisible) return;
    const row = floodMeta.steps.find((r) => r.step === forecastStep);
    if (!row?.ready) { floodError = 'Jendela P24 belum lengkap atau tidak tersedia'; return; }
    floodError = '';
    map.addSource('flood-source', { type: 'raster', tiles: [floodTileUrl(floodMeta, forecastStep, floodIndicator)],
      tileSize: 256, bounds: floodMeta.bbox, minzoom: floodMeta.minzoom, maxzoom: floodMeta.maxzoom,
      attribution: 'ECMWF IFS × InaRISK BNPB · Eksperimental, bukan peringatan resmi' });
    map.addLayer({ id: 'flood-layer', type: 'raster', source: 'flood-source',
      paint: { 'raster-opacity': floodOpacity, 'raster-resampling': 'nearest', 'raster-fade-duration': 0 } }, overlayBeforeLayer());
  }

  async function applyFlood() {
    floodRequest?.abort();
    const request = new AbortController();
    floodRequest = request;
    floodError = 'Memuat indikator banjir…';
    try {
      const metadata = await fetchFloodMetadata(request.signal);
      if (request.signal.aborted || floodRequest !== request || activeModel !== 'flood') return;
      const anchor = currentTimelineAnchor();
      floodMeta = metadata;
      forecastRows = metadata.steps.map((r) => ({ ...r, validTime: timelineTime(r, metadata.run_time) }));
      forecastRunTime = metadata.run_time;
      const selection = reconcileTimeline(forecastRows, forecastRunTime, anchor);
      forecastStep = selection.step;
      floodNotice = selection.notice;
      timelineNotice = selection.notice;
      timelineAnchor = null;
      renderFlood();
    } catch (error) {
      if (request.signal.aborted || floodRequest !== request || activeModel !== 'flood') return;
      clearFlood();
      floodMeta = null;
      forecastRows = [];
      floodError = error.message;
    }
  }

  async function handleFloodClick(event) {
    if (!floodMeta || !floodVisible || !map?.getLayer('flood-layer')) return;
    floodPointRequest?.abort();
    floodPopup?.remove();
    const request = new AbortController();
    floodPointRequest = request;
    const generation = ++floodGeneration;
    const metadata = floodMeta, step = forecastStep;
    try {
      const data = await fetchFloodPoint(metadata, step, event.lngLat.lat, event.lngLat.lng, request.signal);
      if (request.signal.aborted || generation !== floodGeneration || !floodVisible || activeModel !== 'flood' || metadata !== floodMeta || step !== forecastStep) return;
      floodPopup = new maplibregl.Popup({ maxWidth: '340px' }).setLngLat(event.lngLat).setDOMContent(floodPointContent(data)).addTo(map);
    } catch (error) {
      if (!request.signal.aborted && generation === floodGeneration) floodError = error.message;
    }
  }

  function clearLandslide() {
    landslidePointRequest?.abort();
    landslidePopup?.remove();
    landslidePopup = null;
    if (map?.getLayer('landslide-layer')) map.removeLayer('landslide-layer');
    if (map?.getSource('landslide-source')) map.removeSource('landslide-source');
  }

  function stopLandslide() {
    landslideRequest?.abort();
    clearInterval(landslidePoll);
    landslidePoll = null;
    clearLandslide();
  }

  function renderLandslide() {
    clearLandslide();
    if (!map?.isStyleLoaded() || activeModel !== 'landslide' || !landslideMeta) return;
    const row = landslideMeta.steps.find((s) => s.step === forecastStep);
    if (!row?.ready) {
      landslideError = `Jendela +${forecastStep} sampai +${forecastStep + 24} jam tidak tersedia`;
      return;
    }
    landslideError = '';
    map.addSource('landslide-source', {
      type: 'raster', tiles: [landslideTileUrl(landslideMeta, row.step)], tileSize: 256,
      bounds: landslideMeta.bbox, minzoom: landslideMeta.minzoom, maxzoom: landslideMeta.maxzoom,
      attribution: 'BNPB InaRISK × ECMWF IFS · Eksperimental, bukan peringatan resmi',
    });
    map.addLayer({ id: 'landslide-layer', type: 'raster', source: 'landslide-source',
      layout: { visibility: landslideVisible ? 'visible' : 'none' },
      paint: { 'raster-opacity': landslideOpacity, 'raster-resampling': 'nearest', 'raster-fade-duration': 0 },
    }, overlayBeforeLayer());
  }

  async function applyLandslide() {
    landslideRequest?.abort();
    const request = new AbortController();
    landslideRequest = request;
    clearLandslide();
    landslideError = 'Memuat data BNPB/ECMWF…';
    try {
      const metadata = await fetchLandslideMetadata(request.signal);
      if (request.signal.aborted || activeModel !== 'landslide') return;
      const anchor = currentTimelineAnchor();
      landslideMeta = metadata;
      forecastRows = metadata.steps.map((row) => ({ ...row, validTime: timelineTime(row, metadata.run_time) }));
      forecastRunTime = metadata.run_time;
      const selection = reconcileTimeline(forecastRows, forecastRunTime, anchor);
      forecastStep = selection.step;
      timelineNotice = selection.notice;
      timelineAnchor = null;
      renderLandslide();
    } catch (error) {
      if (request.signal.aborted) return;
      landslideMeta = null;
      forecastRows = [];
      landslideError = error.message;
    }
  }

  async function handleLandslideClick(event) {
    if (!landslideMeta || !landslideVisible || !map.getLayer('landslide-layer')) return;
    landslidePointRequest?.abort();
    landslidePopup?.remove();
    const request = new AbortController();
    landslidePointRequest = request;
    const metadata = landslideMeta;
    const step = forecastStep;
    try {
      const data = await fetchLandslidePoint(metadata, step, event.lngLat.lat, event.lngLat.lng, request.signal);
      if (request.signal.aborted || activeModel !== 'landslide' || metadata !== landslideMeta || step !== forecastStep) return;
      landslidePopup = new maplibregl.Popup({ maxWidth: '320px' }).setLngLat(event.lngLat).setDOMContent(pointContent(data)).addTo(map);
    } catch (error) {
      if (!request.signal.aborted) landslideError = error.message;
    }
  }

  function changeForecastStep(step) {
    nwpClickSeq++;
    forecastStep = step;
    if (activeModel === 'flood') renderFlood();
    else if (activeModel === 'landslide') renderLandslide();
    else if (GLOBAL_MODELS.includes(activeModel)) {
      removeNwpLayer();
      applyNwp(activeModel).catch(console.warn);
    }
  }

  function changeLandslideOpacity(value) {
    landslideOpacity = value;
    if (map?.getLayer('landslide-layer')) map.setPaintProperty('landslide-layer', 'raster-opacity', value);
  }

  function toggleLandslideVisibility() {
    landslideVisible = !landslideVisible;
    landslidePopup?.remove();
    if (map?.getLayer('landslide-layer')) map.setLayoutProperty('landslide-layer', 'visibility', landslideVisible ? 'visible' : 'none');
  }

  // User overlays (GeoJSON / GPX)
  let userLayers = $state([]);
  let userLayerSeq = 0;

  function setupCartoBoundaries(m) {
    if (!m) return;

    // Batas Provinsi & Negara ala Karhutla BMKG / Carto Dark Matter yang rapih:
    // Garis tidak terlalu tebal dan tidak menusuk mata (subtle refined lines)
    // 1. boundary_state (Batas Provinsi)
    if (m.getLayer('boundary_state')) {
      m.setLayoutProperty('boundary_state', 'visibility', 'visible');
      m.setPaintProperty('boundary_state', 'line-color', 'rgba(210, 215, 225, 0.75)');
      m.setPaintProperty('boundary_state', 'line-opacity', 0.85);
      m.setPaintProperty('boundary_state', 'line-width', [
        'interpolate',
        ['linear'],
        ['zoom'],
        3, 0.6,
        6, 1.0,
        10, 1.5
      ]);
      m.setPaintProperty('boundary_state', 'line-dasharray', [3, 2]);
    }

    // 2. boundary_county (Batas Kabupaten/Kota)
    if (m.getLayer('boundary_county')) {
      m.setPaintProperty('boundary_county', 'line-color', 'rgba(180, 185, 195, 0.4)');
      m.setPaintProperty('boundary_county', 'line-width', [
        'interpolate',
        ['linear'],
        ['zoom'],
        8, 0.5,
        10, 0.9
      ]);
      m.setPaintProperty('boundary_county', 'line-dasharray', [2, 2]);
    }

    // 3. boundary_country_inner (Batas Antar Negara - solid halus)
    if (m.getLayer('boundary_country_inner')) {
      m.setPaintProperty('boundary_country_inner', 'line-color', 'rgba(240, 245, 255, 0.9)');
      m.setPaintProperty('boundary_country_inner', 'line-opacity', 0.9);
      m.setPaintProperty('boundary_country_inner', 'line-width', [
        'interpolate',
        ['linear'],
        ['zoom'],
        3, 0.9,
        6, 1.4,
        10, 2.0
      ]);
    }

    // 4. boundary_country_outline (Outline bayangan luar)
    if (m.getLayer('boundary_country_outline')) {
      m.setPaintProperty('boundary_country_outline', 'line-color', '#000000');
      m.setPaintProperty('boundary_country_outline', 'line-opacity', 0.4);
      m.setPaintProperty('boundary_country_outline', 'line-width', [
        'interpolate',
        ['linear'],
        ['zoom'],
        6, 2,
        10, 4
      ]);
    }

    // 5. Outline Garis Pantai / Pesisir Pulau (Coastline)
    // Carto Dark Matter tidak punya layer stroke untuk pulau/pantai secara default
    // Ditempatkan sebelum waterway_label agar selalu berada di atas layer satelit/radar/daratan
    if (!m.getLayer('coastline_outline') && m.getSource('carto')) {
      m.addLayer(
        {
          id: 'coastline_outline',
          type: 'line',
          source: 'carto',
          'source-layer': 'water',
          filter: ['all', ['==', '$type', 'Polygon']],
          paint: {
            'line-color': 'rgba(235, 240, 250, 0.85)',
            'line-opacity': 0.85,
            'line-width': [
              'interpolate',
              ['linear'],
              ['zoom'],
              3, 0.6,
              6, 1.0,
              10, 1.5
            ]
          }
        },
        m.getLayer('waterway_label') ? 'waterway_label' : undefined
      );
    }
  }

  onMount(() => {
    // Carto Dark Matter GL Style (exact basemap as used in kalteng.bmkg.go.id/apps/karhutla)
    const m = new maplibregl.Map({
      container: mapContainer,
      style: 'https://basemaps.cartocdn.com/gl/dark-matter-gl-style/style.json',
      center: [117.0, -0.5], // Center over Indonesia
      zoom: 4.8,
      attributionControl: false,
    });

    m.addControl(new maplibregl.NavigationControl({ showCompass: true }), 'bottom-right');

    m.on('load', () => {
      map = m;
      mapLoaded = true;

      setupCartoBoundaries(m);
      console.log('MapLibre GL Carto Dark Matter loaded successfully');
    });

    m.on('styledata', () => {
      if (m.isStyleLoaded()) {
        setupCartoBoundaries(m);
        restoreUserLayers();
      }
    });

    m.on('error', (e) => {
      console.error('MapLibre error:', e);
    });

    m.on('style.load', () => {
      if (activeModel === 'flood') renderFlood();
    else if (activeModel === 'landslide') renderLandslide();
    });
    m.on('click', (e) => {
      if (activeModel === 'flood') handleFloodClick(e).catch(console.warn);
      else if (activeModel === 'landslide') handleLandslideClick(e).catch(console.warn);
      else handleNwpClick(e).catch((err) => console.warn('NWP click', err));
    });

    return () => {
      stopNwpPoll();
      stopFlood();
      stopLandslide();
      closeNwpPopup();
      if (windOverlay) {
        windOverlay.destroy();
        windOverlay = null;
      }
      m.remove();
    };
  });

  function overlayBeforeLayer() {
    if (map.getLayer('coastline_outline')) return 'coastline_outline';
    if (map.getLayer('boundary_county')) return 'boundary_county';
    if (map.getLayer('boundary_state')) return 'boundary_state';
    if (map.getLayer('boundary_country_inner')) return 'boundary_country_inner';
    if (map.getLayer('waterway_label')) return 'waterway_label';
    if (map.getLayer('place_hamlet')) return 'place_hamlet';
    return undefined;
  }

  function stopNwpPoll() {
    if (nwpPollId) {
      clearInterval(nwpPollId);
      nwpPollId = null;
    }
  }

  function startNwpPoll(modelId) {
    stopNwpPoll();
    nwpPollId = setInterval(() => {
      applyNwp(modelId).catch((err) => console.warn('NWP poll', err));
    }, ECMWF_POLL_MS);
  }

  function closeNwpPopup() {
    if (nwpPopupApp) {
      try {
        unmount(nwpPopupApp);
      } catch {
        /* already gone */
      }
      nwpPopupApp = null;
    }
    nwpHost = null;
    nwpPop.loading = false;
    nwpPop.data = null;
    nwpPop.error = null;
    if (nwpPopup) {
      const p = nwpPopup;
      nwpPopup = null;
      p.remove();
    }
  }

  function setNwpPopupProps(lngLat, props) {
    if (!map) return;
    nwpPop.loading = props.loading ?? false;
    nwpPop.data = props.data ?? null;
    nwpPop.error = props.error ?? null;
    if (!nwpHost) nwpHost = document.createElement('div');
    if (!nwpPopupApp) {
      nwpPopupApp = mount(NwpPopup, { target: nwpHost, props: nwpPop });
    }
    if (!nwpPopup) {
      nwpPopup = new maplibregl.Popup({
        closeButton: true,
        closeOnClick: false,
        focusAfterOpen: false,
        maxWidth: '300px',
        className: 'nwp-inspect-popup',
      });
      nwpPopup.on('close', () => {
        if (nwpPopupApp) {
          try {
            unmount(nwpPopupApp);
          } catch {
            /* already gone */
          }
          nwpPopupApp = null;
        }
        nwpPopup = null;
        nwpHost = null;
      });
    }
    nwpPopup.setLngLat(lngLat).setDOMContent(nwpHost);
    if (!nwpPopup.isOpen()) nwpPopup.addTo(map);
  }

  async function handleNwpClick(e) {
    if (!map || !nwpInspect || !GLOBAL_MODELS.includes(activeModel)) return;
    const { lng, lat } = e.lngLat;
    const seq = ++nwpClickSeq;
    const { modelId, manifest, step } = nwpInspect;
    const spec = MODELS[modelId];
    const base = {
      lat,
      lon: lng,
      modelTitle: spec.title,
      varId: nwpVar,
      runTime: modelRunTime(modelId, manifest),
      validTime: step.validTime,
      tanggal: null,
      nilai: {},
      lokasi: null,
    };
    setNwpPopupProps([lng, lat], { loading: true, data: base, error: null });
    const geoP = reverseGeocode(lat, lng).catch(() => null);
    try {
      const result = await inspectValues({
        modelId,
        manifest,
        step,
        params: paramsFor(modelId),
        lat,
        lon: lng,
        zoom: map.getZoom(),
        onPartial: (partial) => {
          if (seq !== nwpClickSeq) return;
          setNwpPopupProps([lng, lat], {
            loading: true,
            error: null,
            data: { ...base, ...partial, lokasi: nwpPop.data?.lokasi ?? null },
          });
        },
      });
      if (seq !== nwpClickSeq) return;
      setNwpPopupProps([lng, lat], {
        loading: false,
        error: null,
        data: { ...base, ...result, lokasi: nwpPop.data?.lokasi ?? null },
      });
      const lokasi = await geoP;
      if (seq !== nwpClickSeq) return;
      if (lokasi) {
        setNwpPopupProps([lng, lat], {
          loading: false,
          error: null,
          data: { ...base, ...result, lokasi },
        });
      }
    } catch (err) {
      if (seq !== nwpClickSeq) return;
      setNwpPopupProps([lng, lat], {
        loading: false,
        data: base,
        error: err?.message || 'Gagal membaca nilai',
      });
    }
  }

  function removeNwpLayer() {
    if (!map) return;
    closeNwpPopup();
    nwpInspect = null;
    if (map.getCanvas()) map.getCanvas().style.cursor = '';
    if (map.getLayer('nwp-layer')) map.removeLayer('nwp-layer');
    if (map.getSource('nwp-source')) map.removeSource('nwp-source');
    if (map.getLayer('ecmwf-layer')) map.removeLayer('ecmwf-layer');
    if (map.getSource('ecmwf-source')) map.removeSource('ecmwf-source');
    if (nwpAttribControl) {
      try {
        map.removeControl(nwpAttribControl);
      } catch {
        /* already gone */
      }
      nwpAttribControl = null;
    }
    nwpKey = null;
    nwpData = null;
  }

  async function applyNwp(modelId) {
    if (!map || !mapLoaded) return;
    if (!modelId || !GLOBAL_MODELS.includes(modelId)) {
      stopNwpPoll();
      removeNwpLayer();
      return;
    }

    const requestSeq = ++nwpRequestSeq;
    const spec = MODELS[modelId];
    let manifest;
    try {
      manifest = await fetchNwpLatest(modelId);
    } catch (err) {
      if (activeModel !== modelId || requestSeq !== nwpRequestSeq) return;
      removeNwpLayer();
      console.warn(`${spec.title} latest not ready`, err);
      startNwpPoll(modelId);
      return;
    }

    if (activeModel !== modelId || requestSeq !== nwpRequestSeq) return;
    const varId = nwpVar || defaultVar(modelId);
    const rows = modelId === 'ecmwf'
      ? (manifest.steps || []).filter((s) => s.ready && (!s.vars?.length || s.vars.includes(varId))).map((s) => ({ step: s.step, validTime: s.valid_time, token: String(s.step) }))
      : (manifest.timesteps || []).filter((s) => !s.error && (s.valid || s.valid_time) && (!s.params?.length || s.params.includes(varId))).map((s) => ({
          step: s.forecast_hour ?? s.step, validTime: s.valid || s.valid_time,
          token: modelId === 'gfs' ? String(s.valid).replace(/[-:TZ]/g, '').slice(0, 10) : s.step_str || String(s.step).padStart(3, '0'),
        }));
    const anchor = currentTimelineAnchor();
    forecastRows = rows;
    forecastRunTime = modelRunTime(modelId, manifest);
    const preferred = pickNwpStep(modelId, manifest, varId);
    const selection = reconcileTimeline(rows, forecastRunTime, anchor, preferred ? Number(preferred.step) : null);
    forecastStep = selection.step;
    timelineNotice = selection.notice;
    timelineAnchor = null;
    const step = rows.find((s) => Number(s.step) === forecastStep);
    if (!step) {
      removeNwpLayer();
      console.warn(`${spec.title} manifest has no ready steps`);
      startNwpPoll(modelId);
      return;
    }

    const key = nwpSourceKey(modelId, manifest, varId, step);
    if (key === nwpKey && map.getSource('nwp-source')) {
      nwpInspect = { modelId, manifest, step };
      if (map.getCanvas()) map.getCanvas().style.cursor = 'crosshair';
      startNwpPoll(modelId);
      return;
    }

    const template = nwpTileUrl(modelId, manifest, varId, step);
    const bbox = modelBbox(modelId, manifest);
    const zoom = modelZoom(modelId, manifest);
    const runTime = modelRunTime(modelId, manifest);
    const attrib = `${manifest.attribution || spec.attribution} · run ${runTime} · valid ${step.validTime}`;

    removeNwpLayer();

    map.addSource('nwp-source', {
      type: 'raster',
      scheme: 'xyz',
      tiles: [template],
      tileSize: manifest.tile_size || 256,
      minzoom: zoom.minzoom,
      maxzoom: zoom.maxzoom,
      bounds: bbox,
      attribution: attrib,
    });

    let beforeLayer;
    if (map.getLayer('radar-layer')) {
      beforeLayer = 'radar-layer';
    } else if (map.getLayer('satellite-layer')) {
      beforeLayer = 'satellite-layer';
    } else {
      beforeLayer = overlayBeforeLayer();
    }

    map.addLayer(
      {
        id: 'nwp-layer',
        type: 'raster',
        source: 'nwp-source',
        paint: {
          'raster-opacity': 0.85,
          'raster-fade-duration': 200,
        },
      },
      beforeLayer
    );

    nwpAttribControl = new maplibregl.AttributionControl({ compact: true });
    map.addControl(nwpAttribControl, 'bottom-right');
    nwpKey = key;
    nwpInspect = { modelId, manifest, step };
    if (map.getCanvas()) map.getCanvas().style.cursor = 'crosshair';
    nwpData = {
      modelId,
      title: spec.title,
      badge: spec.badge,
      varId,
      runTime,
      validTime: step.validTime,
      runId: modelRunId(modelId, manifest),
      step: step.step,
    };
    if (windOverlay) {
      windOverlay.setContext({
        modelId,
        manifest,
        step,
        bbox,
        zoom,
      });
    }
    startNwpPoll(modelId);
  }

  // Manage Radar Layer on Map
  function applyRadar(data) {
    if (!map || !mapLoaded) return;

    // Remove existing radar layer & source
    if (map.getLayer('radar-layer')) {
      map.removeLayer('radar-layer');
    }
    if (map.getSource('radar-source')) {
      map.removeSource('radar-source');
    }

    if (!data) {
      radarData = null;
      return;
    }

    const { site, manifest, opacity } = data;
    const latestFile = manifest?.latest?.file;
    if (!latestFile) {
      console.warn('No radar frame file found in manifest');
      return;
    }

    const base = (data.base || 'https://cuaca.bmkg.go.id/data/public/nwp-viewer/data/wxr').replace(/\/+$/, '');
    const imageUrl = `${base}/${site.code}/${data.product}/${latestFile}`;
    const proxiedImageUrl = proxyCuaca(imageUrl);

    // MapLibre requires 4 corner coordinates in [NW, NE, SE, SW] order
    // site.bounds = { overlayTLC: [lat, lon], overlayBRC: [lat, lon] }
    // Note: GeoJSON / MapLibre coordinate order is [longitude, latitude]
    const tlc = site.bounds.overlayTLC; // [lat, lon]
    const brc = site.bounds.overlayBRC; // [lat, lon]

    const nw = [parseFloat(tlc[1]), parseFloat(tlc[0])]; // [lon, lat]
    const ne = [parseFloat(brc[1]), parseFloat(tlc[0])]; // [lon, lat]
    const se = [parseFloat(brc[1]), parseFloat(brc[0])]; // [lon, lat]
    const sw = [parseFloat(tlc[1]), parseFloat(brc[0])]; // [lon, lat]

    const coordinates = [nw, ne, se, sw];

    map.addSource('radar-source', {
      type: 'image',
      url: proxiedImageUrl,
      coordinates,
    });

    // Place radar above satellite but BELOW coastline, boundaries & labels
    let beforeLayer;
    if (map.getLayer('coastline_outline')) {
      beforeLayer = 'coastline_outline';
    } else if (map.getLayer('boundary_county')) {
      beforeLayer = 'boundary_county';
    } else if (map.getLayer('boundary_state')) {
      beforeLayer = 'boundary_state';
    } else if (map.getLayer('boundary_country_inner')) {
      beforeLayer = 'boundary_country_inner';
    } else if (map.getLayer('waterway_label')) {
      beforeLayer = 'waterway_label';
    } else if (map.getLayer('place_hamlet')) {
      beforeLayer = 'place_hamlet';
    }

    map.addLayer(
      {
        id: 'radar-layer',
        type: 'raster',
        source: 'radar-source',
        paint: {
          'raster-opacity': opacity ?? 0.85,
          'raster-fade-duration': 200,
        },
      },
      beforeLayer
    );

    // Fly to radar station
    if (site.lon && site.lat) {
      map.flyTo({
        center: [parseFloat(site.lon), parseFloat(site.lat)],
        zoom: 7.2,
        speed: 1.2,
      });
    }

    radarData = { ...data, currentFile: latestFile };
  }

  // Manage Satellite Layer on Map
  function applySatellite(data) {
    if (!map || !mapLoaded) return;

    // Remove existing satellite layer & source
    if (map.getLayer('satellite-layer')) {
      map.removeLayer('satellite-layer');
    }
    if (map.getSource('satellite-source')) {
      map.removeSource('satellite-source');
    }

    if (!data) {
      satelliteData = null;
      return;
    }

    const { product, currentBaserun, opacity } = data;
    const tileUrl = proxySatelliteTile(product.url || product.tile_url, currentBaserun);
    console.log('Applying satellite tile URL template:', tileUrl);

    map.addSource('satellite-source', {
      type: 'raster',
      scheme: 'tms',
      tiles: [tileUrl],
      tileSize: 256,
      minzoom: 0,
      maxzoom: 12,
    });

    // Add satellite layer underneath radar layer, or under coastline, boundaries & label layers
    let beforeLayer;
    if (map.getLayer('radar-layer')) {
      beforeLayer = 'radar-layer';
    } else if (map.getLayer('coastline_outline')) {
      beforeLayer = 'coastline_outline';
    } else if (map.getLayer('boundary_county')) {
      beforeLayer = 'boundary_county';
    } else if (map.getLayer('boundary_state')) {
      beforeLayer = 'boundary_state';
    } else if (map.getLayer('boundary_country_inner')) {
      beforeLayer = 'boundary_country_inner';
    } else if (map.getLayer('waterway_label')) {
      beforeLayer = 'waterway_label';
    } else if (map.getLayer('place_hamlet')) {
      beforeLayer = 'place_hamlet';
    }

    map.addLayer(
      {
        id: 'satellite-layer',
        type: 'raster',
        source: 'satellite-source',
        paint: {
          'raster-opacity': opacity ?? 0.85,
          'raster-fade-duration': 200,
        },
      },
      beforeLayer
    );

    satelliteData = data;
  }

  function changeSatelliteBaserun(newBaserun) {
    if (!satelliteData) return;
    applySatellite({
      ...satelliteData,
      currentBaserun: newBaserun,
    });
  }

  function handleSelectModel(modelId) {
    const next = activeModel === modelId ? null : modelId;
    nwpRequestSeq += 1;
    nwpClickSeq += 1;
    timelineAnchor = currentTimelineAnchor();
    timelineNotice = '';
    stopFlood();
    floodMeta = null;
    stopLandslide();
    removeNwpLayer();
    forecastRows = [];
    forecastStep = null;
    activeModel = next;
    if (next === 'flood') {
      stopNwpPoll();
      applyFlood();
      floodPoll = setInterval(() => applyFlood(), ECMWF_POLL_MS);
    }
    if (next === 'landslide') {
      stopNwpPoll();
      applyLandslide();
      landslidePoll = setInterval(() => applyLandslide(), ECMWF_POLL_MS);
    }

    if (windOverlay) {
      if (next && GLOBAL_MODELS.includes(next) && windActive) {
        const ctx = currentWindContext();
        if (ctx) windOverlay.setContext(ctx);
      } else if (!next || !GLOBAL_MODELS.includes(next)) {
        windOverlay.stop();
        windActive = false;
      }
    }

    if (GLOBAL_MODELS.includes(modelId)) {
      if (next) {
        nwpVar = defaultVar(next);
        applyNwp(next).catch((err) => console.warn('NWP toggle', err));
      } else {
        applyNwp(null);
      }
    } else if (nwpKey) {
      applyNwp(null);
    }
  }

  function handleSelectNwpVar(varId) {
    if (nwpVar === varId) return;
    nwpVar = varId;
    if (GLOBAL_MODELS.includes(activeModel)) {
      applyNwp(activeModel).catch((err) => console.warn('NWP var', err));
    }
  }

  function currentWindContext() {
    if (!GLOBAL_MODELS.includes(activeModel)) return null;
    if (!nwpInspect || nwpInspect.modelId !== activeModel) {
      return { modelId: activeModel, bbox: MODELS[activeModel].bbox };
    }
    const { modelId, manifest, step } = nwpInspect;
    return {
      modelId,
      manifest,
      step,
      bbox: modelBbox(modelId, manifest),
      zoom: modelZoom(modelId, manifest),
    };
  }

  function toggleWind() {
    windActive = !windActive;
    if (windActive) {
      if (!windOverlay && map) {
        windOverlay = new WindOverlay(map, {
          speed: windSpeed,
          onStatus: (st) => {
            windStatus = st;
          },
        });
      }
      windOverlay?.setSpeed(windSpeed);
      const ctx = currentWindContext();
      windOverlay?.setContext(ctx);
      windOverlay?.start();
    } else {
      windOverlay?.stop();
    }
  }

  function changeWindSpeed(spd) {
    windSpeed = spd;
    windOverlay?.setSpeed(spd);
  }

  function closeNwp() {
    activeModel = null;
    if (windOverlay) {
      windOverlay.stop();
      windActive = false;
    }
    applyNwp(null);
  }

  // ---- User overlays (GeoJSON / GPX) ----
  function addUserLayerToMap(layer) {
    if (!map || map.getSource(`user-${layer.id}`)) return;
    map.addSource(`user-${layer.id}`, { type: 'geojson', data: layer.geojson });
    const before = overlayBeforeLayer();
    for (const def of layerDefs(layer.id, layer.color)) {
      map.addLayer(
        { ...def, layout: { visibility: layer.visible ? 'visible' : 'none' } },
        before
      );
    }
  }

  function removeUserLayerFromMap(id) {
    if (!map) return;
    const src = `user-${id}`;
    for (const suffix of ['fill', 'line', 'circle']) {
      const lid = `${src}-${suffix}`;
      if (map.getLayer(lid)) map.removeLayer(lid);
    }
    if (map.getSource(src)) map.removeSource(src);
  }

  function addUserLayer({ name, kind, geojson, color }) {
    if (!map || !mapLoaded) return false;
    const id = `u${Date.now().toString(36)}${(userLayerSeq++).toString(36)}`;
    const counts = countByGeometry(geojson);
    const layer = {
      id,
      name,
      kind,
      geojson,
      color: color || colorFor(userLayers.length),
      visible: true,
      count: counts.total,
      counts,
      bbox: bboxOf(geojson),
    };
    userLayers = [...userLayers, layer];
    addUserLayerToMap(layer);
    if (layer.bbox) {
      map.fitBounds(
        [
          [layer.bbox[0], layer.bbox[1]],
          [layer.bbox[2], layer.bbox[3]],
        ],
        { padding: 48, maxZoom: 12 }
      );
    }
    return true;
  }

  function toggleUserLayer(id) {
    const layer = userLayers.find((l) => l.id === id);
    if (!layer) return;
    layer.visible = !layer.visible;
    if (map) {
      for (const suffix of ['fill', 'line', 'circle']) {
        const lid = `user-${id}-${suffix}`;
        if (map.getLayer(lid)) {
          map.setLayoutProperty(lid, 'visibility', layer.visible ? 'visible' : 'none');
        }
      }
    }
    userLayers = [...userLayers];
  }

  function fitUserLayer(id) {
    const layer = userLayers.find((l) => l.id === id);
    if (!layer?.bbox || !map) return;
    map.fitBounds(
      [
        [layer.bbox[0], layer.bbox[1]],
        [layer.bbox[2], layer.bbox[3]],
      ],
      { padding: 48, maxZoom: 12 }
    );
  }

  function removeUserLayer(id) {
    removeUserLayerFromMap(id);
    userLayers = userLayers.filter((l) => l.id !== id);
  }

  function renameUserLayer(id, name) {
    const layer = userLayers.find((l) => l.id === id);
    if (!layer) return;
    layer.name = name;
    userLayers = [...userLayers];
  }

  function clearUserLayers() {
    for (const l of userLayers) removeUserLayerFromMap(l.id);
    userLayers = [];
  }

  function restoreUserLayers() {
    if (!map) return;
    for (const layer of userLayers) {
      if (!map.getSource(`user-${layer.id}`)) addUserLayerToMap(layer);
    }
  }
</script>

<main class="relative w-screen h-screen overflow-hidden bg-slate-100">
  <!-- MapLibre Container -->
  <div bind:this={mapContainer} class="absolute inset-0 w-full h-full z-0"></div>

  <!-- Top-Left Branding Card (White / Light theme) -->
  <div class="fixed top-5 left-5 z-40">
    <div
      class="flex items-center gap-3.5 px-4 py-2.5 rounded-2xl bg-white/95 backdrop-blur-md border border-slate-200/90 shadow-xl"
    >
      <!-- BMKG Logo -->
      <img
        src="/img/image.png"
        alt="BMKG Logo"
        class="h-9 w-auto object-contain filter drop-shadow-sm"
      />
      <p class="text-[11px] font-semibold text-slate-800 leading-tight">
        Badan Meteorologi,<br />Klimatologi, dan Geofisika
      </p>
    </div>
  </div>

  <!-- Vertical Circular Action Toolbar (Right Pinned) -->
  <Toolbar
    {activeModel}
    radarActive={!!radarData}
    satelliteActive={!!satelliteData}
    onOpenRadar={() => (showRadarModal = true)}
    onOpenSatellite={() => (showSatelliteModal = true)}
    onSelectModel={handleSelectModel}
  />

  <!-- User overlays (GeoJSON / GPX) — button at top-right -->
  <UserLayers
    layers={userLayers}
    onAdd={addUserLayer}
    onToggle={toggleUserLayer}
    onFit={fitUserLayer}
    onRemove={removeUserLayer}
    onClearAll={clearUserLayers}
    onRename={renameUserLayer}
  />

  {#if GLOBAL_MODELS.includes(activeModel)}
    <ParamToolbar
      params={paramsFor(activeModel)}
      activeVar={nwpVar}
      onSelectVar={handleSelectNwpVar}
      {windActive}
      {windSpeed}
      {windStatus}
      onToggleWind={toggleWind}
      onChangeWindSpeed={changeWindSpeed}
    />
  {/if}

  <!-- Active Layer Legend & Timeline Controls (Bottom Left) -->
  <LayerControl
    {radarData}
    {satelliteData}
    {nwpData}
    onCloseRadar={() => applyRadar(null)}
    onCloseSatellite={() => applySatellite(null)}
    onCloseNwp={closeNwp}
    onChangeSatelliteBaserun={changeSatelliteBaserun}
  />

  <!-- Radar Modal -->
  {#if showRadarModal}
    <RadarModal
      currentStation={radarData?.site}
      currentOpacity={radarData?.opacity ?? 0.85}
      onSelect={applyRadar}
      onClose={() => (showRadarModal = false)}
    />
  {/if}

  <!-- Satellite Modal -->
  {#if showSatelliteModal}
    <SatelliteModal
      currentProduct={satelliteData?.product}
      currentOpacity={satelliteData?.opacity ?? 0.9}
      onSelect={applySatellite}
      onClose={() => (showSatelliteModal = false)}
    />
  {/if}

  {#if activeModel === 'landslide' && landslideError}
    <div class="fixed top-20 left-1/2 -translate-x-1/2 z-50 px-4 py-2 bg-red-950/90 text-red-200 text-xs rounded-xl border border-red-700/60 shadow-xl backdrop-blur-md flex items-center gap-2">
      <span class="w-2 h-2 rounded-full bg-red-500"></span>
      <span>{landslideError}</span>
    </div>
  {/if}

  {#if activeModel === 'landslide' && landslideMeta}
    <LandslideLegend
      metadata={landslideMeta}
      step={forecastStep}
      opacity={landslideOpacity}
      visible={landslideVisible}
      onChangeOpacity={changeLandslideOpacity}
      onToggleVisibility={toggleLandslideVisibility}
      onClose={() => handleSelectModel('landslide')}
    />
  {/if}

  {#if activeModel === 'flood'}
    <FloodLegend metadata={floodMeta} step={forecastStep} error={floodError} notice={floodNotice}
      opacity={floodOpacity} visible={floodVisible} indicator={floodIndicator} mode={floodMode}
      onIndicator={(value) => { floodIndicator = value; renderFlood(); }}
      onMode={(value) => { floodMode = value; clearFlood(); renderFlood(); }}
      onOpacity={(value) => { floodOpacity = value; if (map?.getLayer('flood-layer')) map.setPaintProperty('flood-layer', 'raster-opacity', value); }}
      onVisibility={() => { floodVisible = !floodVisible; floodRequest?.abort(); renderFlood(); if (floodVisible) applyFlood(); }}
      onClose={() => handleSelectModel('flood')}/>
  {/if}

  {#if (GLOBAL_MODELS.includes(activeModel) || activeModel === 'landslide' || activeModel === 'flood') && forecastRows.length > 0}
    <ForecastControl
      rows={forecastRows}
      selected={forecastStep}
      runTime={forecastRunTime}
      notice={timelineNotice}
      onchange={changeForecastStep}
    />
  {/if}
</main>
