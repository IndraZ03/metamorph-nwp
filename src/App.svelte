<script>
  import { onMount } from 'svelte';
  import maplibregl from 'maplibre-gl';
  import Toolbar from './components/Toolbar.svelte';
  import ParamToolbar from './components/ParamToolbar.svelte';
  import RadarModal from './components/RadarModal.svelte';
  import SatelliteModal from './components/SatelliteModal.svelte';
  import LayerControl from './components/LayerControl.svelte';
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
      }
    });

    m.on('error', (e) => {
      console.error('MapLibre error:', e);
    });

    return () => {
      stopNwpPoll();
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

  function removeNwpLayer() {
    if (!map) return;
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

    const spec = MODELS[modelId];
    let manifest;
    try {
      manifest = await fetchNwpLatest(modelId);
    } catch (err) {
      console.warn(`${spec.title} latest not ready`, err);
      startNwpPoll(modelId);
      return;
    }

    const varId = nwpVar || defaultVar(modelId);
    const step = pickNwpStep(modelId, manifest, varId);
    if (!step) {
      console.warn(`${spec.title} manifest has no ready steps`);
      startNwpPoll(modelId);
      return;
    }

    const key = nwpSourceKey(modelId, manifest, varId, step);
    if (key === nwpKey && map.getSource('nwp-source')) {
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

  function closeNwp() {
    activeModel = null;
    applyNwp(null);
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
      <!-- Separator -->
      <div class="w-px h-8 bg-slate-200"></div>
      <!-- METAMORPH Logo (enlarged for balance with BMKG) -->
      <img
        src="/img/metamorph.png"
        alt="METAMORPH Logo"
        class="h-14 w-auto object-contain filter drop-shadow-sm"
      />
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

  {#if GLOBAL_MODELS.includes(activeModel)}
    <ParamToolbar
      params={paramsFor(activeModel)}
      activeVar={nwpVar}
      onSelectVar={handleSelectNwpVar}
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
</main>
