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
    listSteps as listNwpSteps,
    nearestStep,
    pickStep as pickNwpStep,
    sourceKey as nwpSourceKey,
    tileUrl as nwpTileUrl,
  } from './services/nwp.js';
  import ForecastTimeline from './components/ForecastTimeline.svelte';
  import { inspectValues, reverseGeocode } from './services/numericTiles.js';
  import { bboxOf, colorFor, countByGeometry, layerDefs } from './services/userLayers.js';
  import { WindOverlay } from './services/windAnimation.js';

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
  let nwpManifest = null;
  let nwpSteps = $state([]);
  let nwpStepToken = $state(null);
  let nwpPlaying = $state(false);
  let nwpLoop = $state(false);
  let nwpWantValid = null;
  let nwpSlot = 0;
  let nwpPlayTimer = null;
  let nwpPlayWait = null;
  let nwpSeekGen = 0;
  let nwpPendingGen = 0;
  let nwpPendingToken = null;
  const NWP_OPACITY = 0.85;
  const NWP_PLAY_MS = 700;
  const NWP_LOAD_MS = 2500;

  // Wind animation state
  let windActive = $state(false);
  let windSpeed = $state(1.0);
  let windOverlay = null;
  let windStatus = $state({ state: 'ready', mode: 'demo', message: 'Simulasi — bukan data model' });

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

    m.on('click', (e) => {
      handleNwpClick(e).catch((err) => console.warn('NWP click', err));
    });

    return () => {
      stopNwpPoll();
      stopNwpPlay();
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

  function nwpLayerId(slot) {
    return slot ? 'nwp-layer-b' : 'nwp-layer';
  }

  function nwpSourceId(slot) {
    return slot ? 'nwp-source-b' : 'nwp-source';
  }

  function nwpBeforeLayer() {
    if (map.getLayer('radar-layer')) return 'radar-layer';
    if (map.getLayer('satellite-layer')) return 'satellite-layer';
    return overlayBeforeLayer();
  }

  function dropNwpSlot(slot) {
    const lid = nwpLayerId(slot);
    const sid = nwpSourceId(slot);
    if (map.getLayer(lid)) map.removeLayer(lid);
    if (map.getSource(sid)) map.removeSource(sid);
  }

  function stopNwpPlay() {
    nwpPlaying = false;
    if (nwpPlayTimer) {
      clearTimeout(nwpPlayTimer);
      nwpPlayTimer = null;
    }
    if (nwpPlayWait) {
      const done = nwpPlayWait;
      nwpPlayWait = null;
      done();
    }
  }

  function removeNwpLayer() {
    if (!map) return;
    stopNwpPlay();
    closeNwpPopup();
    nwpInspect = null;
    nwpManifest = null;
    nwpSteps = [];
    nwpStepToken = null;
    nwpWantValid = null;
    nwpSlot = 0;
    nwpSeekGen += 1;
    nwpPendingGen = 0;
    nwpPendingToken = null;
    if (map.getCanvas()) map.getCanvas().style.cursor = '';
    dropNwpSlot(0);
    dropNwpSlot(1);
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

  function commitNwpStep(modelId, manifest, step) {
    const spec = MODELS[modelId];
    const varId = nwpVar || defaultVar(modelId);
    nwpKey = nwpSourceKey(modelId, manifest, varId, step);
    nwpInspect = { modelId, manifest, step };
    nwpStepToken = step.token;
    nwpWantValid = step.t ?? Date.parse(step.validTime);
    if (map.getCanvas()) map.getCanvas().style.cursor = 'crosshair';
    nwpData = {
      modelId,
      title: spec.title,
      badge: spec.badge,
      varId,
      runTime: modelRunTime(modelId, manifest),
      validTime: step.validTime,
      runId: modelRunId(modelId, manifest),
      step: step.step,
    };
    if (windOverlay && windActive) {
      windOverlay.setContext({
        modelId,
        manifest,
        step,
        bbox: modelBbox(modelId, manifest),
        zoom: modelZoom(modelId, manifest),
      });
    }
  }

  function addNwpRaster(slot, modelId, manifest, step) {
    const spec = MODELS[modelId];
    const varId = nwpVar || defaultVar(modelId);
    const sid = nwpSourceId(slot);
    const lid = nwpLayerId(slot);
    const template = nwpTileUrl(modelId, manifest, varId, step);
    const bbox = modelBbox(modelId, manifest);
    const zoom = modelZoom(modelId, manifest);
    const runTime = modelRunTime(modelId, manifest);
    const attrib = `${manifest.attribution || spec.attribution} · run ${runTime} · valid ${step.validTime}`;
    dropNwpSlot(slot);
    map.addSource(sid, {
      type: 'raster',
      scheme: 'xyz',
      tiles: [template],
      tileSize: manifest.tile_size || 256,
      minzoom: zoom.minzoom,
      maxzoom: zoom.maxzoom,
      bounds: bbox,
      attribution: attrib,
    });
    map.addLayer(
      {
        id: lid,
        type: 'raster',
        source: sid,
        paint: {
          'raster-opacity': 0,
          'raster-opacity-transition': { duration: 0, delay: 0 },
          'raster-fade-duration': 0,
        },
      },
      nwpBeforeLayer()
    );
    return { sid, lid, attrib };
  }

  function waitNwpSource(sid, gen, ms = NWP_LOAD_MS) {
    return new Promise((resolve) => {
      if (!map) {
        resolve(false);
        return;
      }
      let done = false;
      const finish = (ok) => {
        if (done) return;
        done = true;
        map.off('sourcedata', onData);
        map.off('idle', onIdle);
        resolve(ok && gen === nwpSeekGen);
      };
      const ready = () => {
        try {
          return map.isSourceLoaded(sid) && map.areTilesLoaded();
        } catch {
          return false;
        }
      };
      const onData = (e) => {
        if (e.sourceId === sid && e.isSourceLoaded && map.areTilesLoaded()) finish(true);
      };
      const onIdle = () => {
        if (ready()) finish(true);
      };
      map.on('sourcedata', onData);
      map.on('idle', onIdle);
      if (ready()) {
        finish(true);
        return;
      }
      setTimeout(() => finish(ready()), ms);
    });
  }

  function abortOwnedSlot(gen, slot) {
    if (nwpPendingGen === gen) {
      dropNwpSlot(slot);
      nwpPendingGen = 0;
      nwpPendingToken = null;
    }
  }

  function sleepPlay(ms) {
    return new Promise((resolve) => {
      if (ms <= 0) {
        resolve();
        return;
      }
      nwpPlayWait = resolve;
      nwpPlayTimer = setTimeout(() => {
        nwpPlayTimer = null;
        nwpPlayWait = null;
        resolve();
      }, ms);
    });
  }

  function snapNwpOpacity(lid, opacity) {
    if (!map.getLayer(lid)) return;
    map.setPaintProperty(lid, 'raster-opacity-transition', { duration: 0, delay: 0 });
    map.setPaintProperty(lid, 'raster-opacity', opacity);
  }

  async function prepareNwpStep(modelId, manifest, step) {
    if (!map || !step) return null;
    const varId = nwpVar || defaultVar(modelId);
    const key = nwpSourceKey(modelId, manifest, varId, step);
    if (key === nwpKey && map.getLayer(nwpLayerId(nwpSlot))) {
      commitNwpStep(modelId, manifest, step);
      return null;
    }
    if (step.token === nwpPendingToken && nwpPendingGen === nwpSeekGen) return null;

    const gen = ++nwpSeekGen;
    nwpPendingGen = gen;
    nwpPendingToken = step.token;
    const from = nwpSlot;
    const to = from ^ 1;
    const added = addNwpRaster(to, modelId, manifest, step);
    await waitNwpSource(added.sid, gen);
    if (gen !== nwpSeekGen) {
      abortOwnedSlot(gen, to);
      return null;
    }
    return { gen, from, to, lid: added.lid, modelId, manifest, step };
  }

  function revealNwp(prepared) {
    if (!prepared || !map) return false;
    const { gen, from, to, lid, modelId, manifest, step } = prepared;
    if (gen !== nwpSeekGen) {
      abortOwnedSlot(gen, to);
      return false;
    }
    const fromLid = nwpLayerId(from);
    snapNwpOpacity(lid, NWP_OPACITY);
    snapNwpOpacity(fromLid, 0);
    nwpSlot = to;
    nwpPendingGen = 0;
    nwpPendingToken = null;
    if (!nwpAttribControl) {
      nwpAttribControl = new maplibregl.AttributionControl({ compact: true });
      map.addControl(nwpAttribControl, 'bottom-right');
    }
    commitNwpStep(modelId, manifest, step);
    requestAnimationFrame(() => {
      if (gen !== nwpSeekGen) return;
      dropNwpSlot(from);
    });
    return true;
  }

  async function showNwpStep(modelId, manifest, step) {
    const prepared = await prepareNwpStep(modelId, manifest, step);
    if (!prepared) return;
    revealNwp(prepared);
  }

  function seekNwpStep(step) {
    if (!step || !activeModel || !nwpManifest) return;
    nwpStepToken = step.token;
    nwpWantValid = step.t ?? Date.parse(step.validTime);
    showNwpStep(activeModel, nwpManifest, step).catch((err) => console.warn('NWP seek', err));
  }

  function stepBy(delta) {
    if (!nwpSteps.length) return;
    const i = Math.max(0, nwpSteps.findIndex((s) => s.token === nwpStepToken));
    let next = nwpSteps[i + delta];
    if (!next && nwpLoop) {
      next = delta > 0 ? nwpSteps[0] : nwpSteps[nwpSteps.length - 1];
    }
    if (next) seekNwpStep(next);
    return next;
  }

  function startNwpPlay() {
    if (!nwpSteps.length || nwpPlaying) return;
    nwpPlaying = true;
    const tick = async () => {
      while (nwpPlaying) {
        const i = Math.max(0, nwpSteps.findIndex((s) => s.token === nwpStepToken));
        let next = nwpSteps[i + 1];
        if (!next) {
          if (nwpLoop) next = nwpSteps[0];
          else {
            stopNwpPlay();
            return;
          }
        }
        const t0 = performance.now();
        let prepared;
        try {
          prepared = await prepareNwpStep(activeModel, nwpManifest, next);
        } catch (err) {
          console.warn('NWP play', err);
          stopNwpPlay();
          return;
        }
        if (!nwpPlaying) {
          if (prepared) abortOwnedSlot(prepared.gen, prepared.to);
          return;
        }
        await sleepPlay(Math.max(0, NWP_PLAY_MS - (performance.now() - t0)));
        if (!nwpPlaying) {
          if (prepared) abortOwnedSlot(prepared.gen, prepared.to);
          return;
        }
        if (prepared) revealNwp(prepared);
      }
    };
    tick();
  }

  async function applyNwp(modelId) {
    if (!map || !mapLoaded) return;
    if (!modelId || !GLOBAL_MODELS.includes(modelId)) {
      stopNwpPoll();
      removeNwpLayer();
      return;
    }

    const spec = MODELS[modelId];
    let manifest;
    try {
      manifest = await fetchNwpLatest(modelId);
    } catch (err) {
      console.warn(`${spec.title} latest not ready`, err);
      startNwpPoll(modelId);
      return;
    }

    if (activeModel !== modelId) return;
    const varId = nwpVar || defaultVar(modelId);
    const steps = listNwpSteps(modelId, manifest, varId);
    nwpManifest = manifest;
    nwpSteps = steps;
    const prefer = nwpWantValid;
    const step = prefer
      ? nearestStep(steps, prefer)
      : pickNwpStep(modelId, manifest, varId);
    if (!step) {
      console.warn(`${spec.title} manifest has no ready steps`);
      startNwpPoll(modelId);
      return;
    }

    const key = nwpSourceKey(modelId, manifest, varId, step);
    if (key === nwpKey && map.getLayer(nwpLayerId(nwpSlot))) {
      commitNwpStep(modelId, manifest, step);
      startNwpPoll(modelId);
      return;
    }

    await showNwpStep(modelId, manifest, step);
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
    activeModel = next;
    stopNwpPlay();

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
        nwpWantValid = null;
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

<main
    class="relative w-screen h-screen overflow-hidden bg-slate-100"
    class:nwp-timeline-on={GLOBAL_MODELS.includes(activeModel) && nwpSteps.length > 0}
  >
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
    raised={GLOBAL_MODELS.includes(activeModel) && nwpSteps.length > 0}
    onCloseRadar={() => applyRadar(null)}
    onCloseSatellite={() => applySatellite(null)}
    onCloseNwp={closeNwp}
    onChangeSatelliteBaserun={changeSatelliteBaserun}
  />

  {#if GLOBAL_MODELS.includes(activeModel)}
    <ForecastTimeline
      steps={nwpSteps}
      selectedToken={nwpStepToken}
      playing={nwpPlaying}
      loop={nwpLoop}
      disabled={!nwpSteps.length}
      modelTitle={nwpData?.title || MODELS[activeModel]?.title || ''}
      runTime={nwpData?.runTime || (nwpManifest ? modelRunTime(activeModel, nwpManifest) : null)}
      onSeek={seekNwpStep}
      onPlay={startNwpPlay}
      onPause={stopNwpPlay}
      onPrev={() => stepBy(-1)}
      onNext={() => stepBy(1)}
      onLoop={(on) => (nwpLoop = on)}
    />
  {/if}

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
</main>
