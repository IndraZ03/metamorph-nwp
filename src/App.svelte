<script>
  import { mount, onMount, unmount, untrack } from 'svelte';
  import maplibregl from 'maplibre-gl';
  import { DEFAULT_LAYER_ORDER, moveActiveLayer, applyLayerOrder } from './services/layerOrder.js';
  import Toolbar from './components/Toolbar.svelte';
  import ParamToolbar from './components/ParamToolbar.svelte';
  import RadarModal from './components/RadarModal.svelte';
  import SatelliteModal from './components/SatelliteModal.svelte';
  import UserLayers from './components/UserLayers.svelte';
  import DrawingSidebar from './components/DrawingSidebar.svelte';
  import NwpPopup from './components/NwpPopup.svelte';
  import MeteogramSheet from './components/MeteogramSheet.svelte';
  import { fetchMeteogram, meteogramManifestKey } from './services/meteogram.js';
  import { proxyCuaca, proxySatelliteTile, satelliteFrames, verifySatellite } from './services/bmkg.js';
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
    paramsAvailable,
    availableVars,
    listSteps as listNwpSteps,
    nearestStep,
    pickStep as pickNwpStep,
    sourceKey as nwpSourceKey,
    tileUrl as nwpTileUrl,
  } from './services/nwp.js';
  import ForecastTimeline from './components/ForecastTimeline.svelte';
  import { inspectValues, reverseGeocode } from './services/numericTiles.js';
  import { inspectPop } from './services/inspectPop.svelte.js';
  import { bboxOf, colorFor, countByGeometry, layerDefs } from './services/userLayers.js';
  import { WindOverlay } from './services/windAnimation.js';
  import { timelineTime, reconcileTimeline } from './services/forecastTimeline.js';
  import { fetchFloodMetadata, floodTileUrl, fetchFloodPoint, pointContent as floodPointContent } from './services/flood.js';
  import { fetchLandslideMetadata, landslideTileUrl, fetchLandslidePoint, pointContent } from './services/landslide.js';
  import { DrawingController } from './services/drawing/controller.js';
  import {
    drawing,
    hydrate as hydrateDrawings,
    setLayerVisible,
    toggleSidebar,
  } from './services/drawing/store.svelte.js';
  import { spartanTileTemplate, SPARTAN_PRODUCTS, buildSpartanFrames, findLatestValidSpartanStart, verifySpartan } from './services/spartan.js';

  // State management using Svelte 5 runes
  let mapContainer = $state(null);
  let map = $state(null);
  let mapLoaded = $state(false);

  // Modals visibility
  let showRadarModal = $state(false);
  let showSatelliteModal = $state(false);
  let spartanActive = $state(false);
  let spartanProduct = $state(SPARTAN_PRODUCTS[0]);
  let spartanFrames = $state([]);
  let spartanToken = $state(null);
  let spartanStatus = $state('');
  let spartanLoading = $state(false);
  let spartanPlaying = $state(false);
  let spartanLoop = $state(false);
  let satelliteSteps = $state([]);
  let satellitePlaying = $state(false);
  let satelliteLoop = $state(false);
  let satelliteLoading = $state(false);
  let satelliteStatus = $state('');
  let satelliteRequest = 0;
  let satelliteAbort;
  let satelliteTimer;
  let satelliteSeekTimer;
  function stopSatellitePlay() { clearTimeout(satelliteTimer); satellitePlaying = false; }
  function cancelSatellite() {
    ++satelliteRequest;
    satelliteAbort?.abort();
    clearTimeout(satelliteSeekTimer);
    stopSatellitePlay();
    satelliteLoading = false;
  }
  async function seekSatellite(frame) {
    if (!satelliteData || !frame) return;
    satelliteAbort?.abort();
    const generation = ++satelliteRequest;
    const controller = new AbortController();
    satelliteAbort = controller;
    const data = satelliteData;
    satelliteLoading = true;
    satelliteStatus = 'Memuat satelit…';
    try {
      const ok = await verifySatellite(data.product, frame.token, controller.signal);
      if (generation !== satelliteRequest || !satelliteData) return;
      if (!ok) throw new Error('Citra tidak tersedia. Menampilkan citra terakhir.');
      renderSatellite({ ...data, currentBaserun: frame.token });
      satelliteStatus = '';
    } catch (error) {
      if (generation === satelliteRequest && !controller.signal.aborted) {
        satelliteStatus = error.message;
        stopSatellitePlay();
      }
    } finally { if (generation === satelliteRequest) satelliteLoading = false; }
  }
  function queueSatellite(frame) {
    cancelSatellite();
    satelliteSeekTimer = setTimeout(() => seekSatellite(frame), 160);
  }
  async function stepSatellite(delta) {
    clearTimeout(satelliteSeekTimer);
    const index = satelliteSteps.findIndex(f => f.token === satelliteData?.currentBaserun);
    let next = index + delta;
    if (next < 0 || next >= satelliteSteps.length) {
      if (!satelliteLoop) { stopSatellitePlay(); return; }
      next = (next + satelliteSteps.length) % satelliteSteps.length;
    }
    await seekSatellite(satelliteSteps[next]);
  }
  function startSatellitePlay() {
    if (satellitePlaying || satelliteLoading || satelliteSteps.length < 2) return;
    satellitePlaying = true;
    const tick = async () => {
      if (!satellitePlaying) return;
      await stepSatellite(1);
      if (satellitePlaying) satelliteTimer = setTimeout(tick, 1200);
    };
    satelliteTimer = setTimeout(tick, 1200);
  }
  function applySatellite(data) {
    cancelSatellite();
    satelliteSteps = satelliteFrames(data?.baseruns);
    satelliteStatus = '';
    renderSatellite(data);
    if (data) selectTimeline('satellite');
  }
  let timelineContext = $state('nwp');
  let spartanRequest = 0;
  let spartanAbort;
  let spartanTimer;
  let spartanSeekTimer;
  let spartanRefreshAbort;
  let spartanAvailableFrames = $state(null);
  const SPARTAN_POLL_MS = 5 * 60 * 1000;

  async function refreshSpartanLatest() {
    if (!spartanActive || !mapLoaded || spartanLoading || spartanSeekTimer || spartanRefreshAbort || document.hidden) return;
    const product = spartanProduct;
    const request = spartanRequest;
    const token = spartanToken;
    const context = timelineContext;
    const controller = new AbortController();
    spartanRefreshAbort = controller;
    try {
      const start = await findLatestValidSpartanStart(product.id, 5, controller.signal);
      if (controller.signal.aborted || !spartanActive || product.id !== spartanProduct.id || request !== spartanRequest) return;
      if (!start) {
        spartanStatus = 'Data KARHUTLA terbaru belum tersedia. Lapisan terakhir tetap ditampilkan jika ada.';
        return;
      }
      const frames = buildSpartanFrames(start);
      if (frames[0].startDate <= (spartanFrames[0]?.startDate || '') && spartanData?.product.id === product.id) {
        if (spartanStatus === 'Gagal memeriksa pembaruan KARHUTLA. Menampilkan data terakhir.' ||
          spartanStatus === 'Data KARHUTLA terbaru belum tersedia. Lapisan terakhir tetap ditampilkan jika ada.') spartanStatus = '';
        return;
      }
      const followLatest = token === spartanFrames[0]?.token && token === spartanToken &&
        context === 'spartan' && timelineContext === context && !spartanPlaying && !spartanLoading && !spartanSeekTimer;
      if (followLatest || !spartanFrames.length) {
        applySpartan({ product, startDate: frames[0].startDate, endDate: frames[0].endDate, opacity: spartanData?.opacity ?? 0.9 });
        spartanFrames = frames;
        spartanToken = frames[0].token;
        spartanAvailableFrames = null;
        spartanStatus = '';
      } else {
        spartanAvailableFrames = frames;
      }
    } catch (error) {
      if (!controller.signal.aborted && spartanActive && product.id === spartanProduct.id && request === spartanRequest) {
        spartanStatus = 'Gagal memeriksa pembaruan KARHUTLA. Menampilkan data terakhir.';
      }
    } finally {
      if (spartanRefreshAbort === controller) spartanRefreshAbort = null;
    }
  }

  $effect(() => {
    if (!spartanActive) return;
    const productId = spartanProduct.id;
    return untrack(() => {
      let lastCheck = Date.now();
      const check = () => {
        if (productId !== spartanProduct.id || document.hidden || Date.now() - lastCheck < 30000) return;
        lastCheck = Date.now();
        void refreshSpartanLatest();
      };
      const timer = setInterval(check, SPARTAN_POLL_MS);
      window.addEventListener('focus', check);
      document.addEventListener('visibilitychange', check);
      return () => {
        clearInterval(timer);
        window.removeEventListener('focus', check);
        document.removeEventListener('visibilitychange', check);
        spartanRefreshAbort?.abort();
        spartanRefreshAbort = null;
      };
    });
  });

  function stopSpartanPlay() {
    clearTimeout(spartanTimer);
    spartanPlaying = false;
  }
  function selectTimeline(context) {
    stopNwpPlay();
    stopSpartanPlay();
    cancelSatellite();
    timelineContext = context;
  }
  async function selectSpartan(product, frame = null, availableFrames = null) {
    spartanActive = true;
    if (!frame) selectTimeline('spartan');
    if (!frame && product.id === spartanProduct.id && spartanData?.product.id === product.id && !spartanLoading) {
      void refreshSpartanLatest();
      return;
    }
    spartanRefreshAbort?.abort();
    spartanRefreshAbort = null;
    spartanAvailableFrames = null;
    clearTimeout(spartanSeekTimer);
    spartanSeekTimer = null;
    spartanAbort?.abort();
    const generation = ++spartanRequest;
    const controller = new AbortController();
    spartanAbort = controller;
    spartanProduct = product;
    spartanLoading = true;
    spartanStatus = 'Memuat KARHUTLA…';
    try {
      let frames = availableFrames || spartanFrames;
      if (!frame) {
        const start = await findLatestValidSpartanStart(product.id, 5, controller.signal);
        if (!start) throw new Error('Data KARHUTLA tidak tersedia.');
        frames = buildSpartanFrames(start);
        frame = frames[0];
      }
      const ok = await verifySpartan({ product: product.id, start: frame.startDate, end: frame.endDate, signal: controller.signal });
      if (generation !== spartanRequest || !spartanActive) return;
      if (!ok) throw new Error('Tanggal prakiraan KARHUTLA tidak tersedia. Lapisan tetap pada tanggal terakhir yang berhasil dimuat.');
      applySpartan({ product, startDate: frame.startDate, endDate: frame.endDate, opacity: 0.9 });
      spartanFrames = frames;
      spartanToken = frame.token;
      spartanStatus = '';
    } catch (error) {
      if (generation === spartanRequest && spartanActive && !controller.signal.aborted) {
        spartanStatus = error.message;
        stopSpartanPlay();
      }
    } finally {
      if (generation === spartanRequest) spartanLoading = false;
    }
  }
  function seekSpartan(frame) {
    stopSpartanPlay();
    spartanAbort?.abort();
    ++spartanRequest;
    clearTimeout(spartanSeekTimer);
    spartanSeekTimer = setTimeout(() => selectSpartan(spartanProduct, frame), 160);
  }
  async function stepSpartan(delta) {
    const index = spartanFrames.findIndex((f) => f.token === spartanToken);
    let next = index + delta;
    if (next < 0 || next >= spartanFrames.length) {
      if (!spartanLoop) { stopSpartanPlay(); return; }
      next = (next + spartanFrames.length) % spartanFrames.length;
    }
    await selectSpartan(spartanProduct, spartanFrames[next]);
  }
  function startSpartanPlay() {
    if (spartanLoading || !spartanFrames.length) return;
    spartanPlaying = true;
    const tick = async () => {
      if (!spartanPlaying) return;
      await stepSpartan(1);
      if (spartanPlaying) spartanTimer = setTimeout(tick, 1200);
    };
    spartanTimer = setTimeout(tick, 1200);
  }
  function toggleSpartan() {
    if (spartanActive) {
      spartanActive = false;
      ++spartanRequest;
      spartanAbort?.abort();
      clearTimeout(spartanSeekTimer);
      cancelSatellite();
      stopSpartanPlay();
      spartanFrames = [];
      spartanToken = null;
      spartanAvailableFrames = null;
      spartanRefreshAbort?.abort();
      spartanRefreshAbort = null;
      spartanSeekTimer = null;
      spartanStatus = '';
      spartanLoading = false;
      applySpartan(null);
      selectTimeline(satelliteData ? 'satellite' : 'nwp');
    } else {
      spartanActive = true;
      selectTimeline('spartan');
      selectSpartan(SPARTAN_PRODUCTS[0]);
    }
  }
  $effect(() => {
    const active = { nwp: GLOBAL_MODELS.includes(activeModel), spartan: spartanActive, satellite: !!satelliteData };
    if (!active[timelineContext]) selectTimeline(active.satellite ? 'satellite' : active.spartan ? 'spartan' : 'nwp');
  });

  // Active layer records
  let radarData = $state(null);
  let satelliteData = $state(null);
  let spartanData = $state(null);
  let activeModel = $state(null);
  let nwpVar = $state(defaultVar('ecmwf'));
  let nwpData = $state(null);
  let nwpKey = $state(null);
  let nwpPollId = null;
  let nwpInspect = null;
  let nwpPopup = null;
  let nwpPopupApp = null;
  let nwpHost = null;
  let nwpClickSeq = 0;
  let meteogramOpen = $state(false);
  let meteogramSeries = $state(null);
  let meteogramLoading = $state(false);
  let meteogramError = $state(null);
  let meteogramLocation = null;
  let meteogramRequest = null;
  let meteogramGeneration = 0;
  let meteogramSignature = '';
  let meteogramMarker = null;
  let nwpManifest = $state(null);
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

  // 'land' hides the forecast over water; 'full' paints land and sea.
  let nwpExtent = $state('full');

  // Wind animation state
  let windActive = $state(false);
  let windSpeed = $state(1.0);
  let windOverlay = null;
  let windStatus = $state({ state: 'ready', mode: 'unavailable', message: 'Data U/V belum dimuat' });

  // Longsor dan banjir hidup sendiri, tidak lewat activeModel, supaya bisa
  // tampil bersamaan dengan layer lain. Urutan tumpukan: elemen pertama paling bawah.
  let landslideOn = $state(false);
  let floodOn = $state(false);
  let layerOrder = $state([...DEFAULT_LAYER_ORDER]);
  const hazardOrder = $derived(layerOrder.filter(kind => kind === 'landslide' || kind === 'flood'));
  const activeLayerOrder = $derived(layerOrder.filter(kind => ({
    radar: !!radarData, satellite: !!satelliteData, spartan: !!spartanData,
    nwp: !!nwpData, landslide: landslideOn, flood: floodOn,
  })[kind]));
  // Timeline mana yang ditampilkan saat kedua hazard aktif.
  let hazardContext = $state('landslide');
  let landslideRows = $state([]);
  let landslideStep = $state(null);
  let landslideRunTime = $state('');
  let floodRows = $state([]);
  let floodStep = $state(null);
  let floodRunTime = $state('');
  let landslideMeta = $state(null);
  let landslideOpacity = $state(0.6);
  let landslideVisible = $state(true);
  let landslideRequest = null;
  let landslidePointRequest = null;
  let landslidePopup = null;
  let landslidePoll = null;
  // Overlay statis BNPB InaRISK di bawah prakiraan. Tile lewat proxy Vite
  // karena WMS gis.bnpb.go.id tanpa CORS. layer membedakan layanan longsor/banjir.
  let inariskVisible = $state(false);
  const INARISK_LAYERS = {
    landslide: {
      layer: 'landslide',
      bounds: [95.010641, -11.008308, 141.019655, 6.077582],
      attribution: 'BNPB InaRISK · Indeks Kerentanan Tanah Longsor',
    },
    flood: {
      layer: 'flood',
      bounds: [95.078913, -11.008308, 141.019655, 5.861726],
      attribution: 'BNPB InaRISK · Kerentanan Banjir',
    },
  };
  let nwpRequestSeq = 0;

  let floodMeta = $state(null);
  let floodOpacity = $state(0.6);
  let floodRequest, floodPointRequest, floodPopup, floodPoll;
  let floodGeneration = 0;
  let timelineAnchor = null;
  let timelineNotice = $state('');

  function currentTimelineAnchor() {
    const rows = hazardContext === 'flood' ? floodRows : landslideRows;
    const step = hazardContext === 'flood' ? floodStep : landslideStep;
    const runTime = hazardContext === 'flood' ? floodRunTime : landslideRunTime;
    const row = rows.find((r) => Number(r.step) === step);
    return row ? { runTime, validTime: timelineTime(row, runTime) } : timelineAnchor;
  }

  let inariskOwner = null;

  function clearInarisk(owner) {
    if (inariskOwner !== owner) return;
    if (map?.getLayer('inarisk-layer')) map.removeLayer('inarisk-layer');
    if (map?.getSource('inarisk-source')) map.removeSource('inarisk-source');
    inariskOwner = null;
  }

  function clearFlood() {
    floodGeneration++;
    floodPointRequest?.abort();
    floodPopup?.remove();
    floodPopup = null;
    if (map?.getLayer('flood-layer')) map.removeLayer('flood-layer');
    if (map?.getSource('flood-source')) map.removeSource('flood-source');
    clearInarisk('flood');
  }

  let hazardPlaying = $state(false);
  let hazardLoop = $state(false);
  let hazardTimer;

  function stopHazardPlay() {
    clearTimeout(hazardTimer);
    hazardPlaying = false;
  }

  function stopFlood() {
    stopHazardPlay();
    floodRequest?.abort();
    clearInterval(floodPoll);
    floodPoll = null;
    clearFlood();
  }

  function renderFlood() {
    clearFlood();
    if (!map?.isStyleLoaded() || !floodOn || !floodMeta) return;
    const row = floodMeta.steps.find((r) => r.step === floodStep);
    if (!row?.ready) return;
    // InaRISK satu slot. Saat longsor juga aktif dan berada di bawah, biarkan
    // renderLandslide yang menggambarnya supaya tidak saling timpa.
    if (inariskVisible && !(landslideOn && hazardOrder[0] === 'landslide')) {
      clearInarisk(inariskOwner);
      inariskOwner = 'flood';
      const spec = INARISK_LAYERS.flood;
      map.addSource('inarisk-source', {
        type: 'raster',
        tiles: [`${location.origin}/api/proxy-inarisk-tile/{z}/{x}/{y}.png?layer=${spec.layer}&v=2`],
        tileSize: 256,
        bounds: spec.bounds,
        minzoom: 4,
        maxzoom: 12,
        attribution: spec.attribution,
      });
      map.addLayer({
        id: 'inarisk-layer', type: 'raster', source: 'inarisk-source',
        paint: { 'raster-opacity': 0.8, 'raster-fade-duration': 0 },
      }, overlayBeforeLayer());
    }
    map.addSource('flood-source', { type: 'raster', tiles: [floodTileUrl(floodMeta, floodStep, 'rainfall')],
      tileSize: 256, bounds: floodMeta.bbox, minzoom: floodMeta.minzoom, maxzoom: floodMeta.maxzoom,
      attribution: 'ECMWF IFS × InaRISK BNPB · Eksperimental, bukan peringatan resmi' });
    // overlayBeforeLayer, bukan landBeforeLayer: landBeforeLayer menyisipkan raster
    // di bawah layer 'water' Carto, jadi seluruh peta menutupnya. Banjir tidak punya
    // sea-mask seperti longsor, jadi harus di atas air.
    map.addLayer({ id: 'flood-layer', type: 'raster', source: 'flood-source',
      paint: { 'raster-opacity': floodOpacity, 'raster-resampling': 'nearest', 'raster-fade-duration': 0 } }, overlayBeforeLayer());
    applyHazardOrder();
  }

  async function applyFlood() {
    floodRequest?.abort();
    const request = new AbortController();
    floodRequest = request;
    try {
      const metadata = await fetchFloodMetadata(request.signal);
      if (request.signal.aborted || floodRequest !== request || !floodOn) return;
      const anchor = currentTimelineAnchor();
      floodMeta = metadata;
      floodRows = metadata.steps.map((r) => ({ ...r, validTime: timelineTime(r, metadata.run_time) }));
      floodRunTime = metadata.run_time;
      const selection = reconcileTimeline(floodRows, floodRunTime, anchor);
      floodStep = selection.step;
      timelineNotice = selection.notice;
      timelineAnchor = null;
      renderFlood();
    } catch (error) {
      if (request.signal.aborted || floodRequest !== request || !floodOn) return;
      clearFlood();
      floodMeta = null;
      floodRows = [];
    }
  }

  async function handleFloodClick(event) {
    if (!floodMeta || !map?.getLayer('flood-layer')) return;
    floodPointRequest?.abort();
    floodPopup?.remove();
    const request = new AbortController();
    floodPointRequest = request;
    const generation = ++floodGeneration;
    const metadata = floodMeta, step = floodStep;
    try {
      const data = await fetchFloodPoint(metadata, step, event.lngLat.lat, event.lngLat.lng, request.signal);
      if (request.signal.aborted || generation !== floodGeneration || !floodOn || metadata !== floodMeta || step !== floodStep) return;
      floodPopup = new maplibregl.Popup({ maxWidth: '340px' }).setLngLat(event.lngLat).setDOMContent(floodPointContent(data)).addTo(map);
    } catch {
      // Klik gagal: tidak ada banner status.
    }
  }

  function clearLandslide() {
    landslidePointRequest?.abort();
    landslidePopup?.remove();
    landslidePopup = null;
    if (map?.getLayer('landslide-sea-mask')) map.removeLayer('landslide-sea-mask');
    clearInarisk('landslide');
    if (map?.getLayer('landslide-layer')) map.removeLayer('landslide-layer');
    if (map?.getSource('landslide-source')) map.removeSource('landslide-source');
  }

  function stopLandslide() {
    stopHazardPlay();
    landslideRequest?.abort();
    clearInterval(landslidePoll);
    landslidePoll = null;
    clearLandslide();
  }

  function renderLandslide() {
    clearLandslide();
    if (!map?.isStyleLoaded() || !landslideOn || !landslideMeta) return;
    const row = landslideMeta.steps.find((s) => s.step === landslideStep);
    if (!row?.ready) return;
    if (inariskVisible && !(floodOn && hazardOrder[0] === 'flood')) {
      clearInarisk(inariskOwner);
      inariskOwner = 'landslide';
      const spec = INARISK_LAYERS.landslide;
      map.addSource('inarisk-source', {
        type: 'raster',
        tiles: [`${location.origin}/api/proxy-inarisk-tile/{z}/{x}/{y}.png?layer=${spec.layer}&v=2`],
        tileSize: 256,
        bounds: spec.bounds,
        minzoom: 4,
        maxzoom: 12,
        attribution: spec.attribution,
      });
      map.addLayer({
        id: 'inarisk-layer', type: 'raster', source: 'inarisk-source',
        // Di atas air basemap: layer 'water' Carto menutup seluruh laut, jadi
        // raster di bawahnya tampak hitam. Sama seperti overlayBeforeLayer.
        paint: { 'raster-opacity': 0.8, 'raster-fade-duration': 0 },
      }, overlayBeforeLayer());
    }
    map.addSource('landslide-source', {
      type: 'raster', tiles: [landslideTileUrl(landslideMeta, row.step)], tileSize: 256,
      bounds: landslideMeta.bbox, minzoom: landslideMeta.minzoom, maxzoom: landslideMeta.maxzoom,
      attribution: 'BNPB InaRISK × ECMWF IFS · Eksperimental, bukan peringatan resmi',
    });
    map.addLayer({ id: 'landslide-layer', type: 'raster', source: 'landslide-source',
      layout: { visibility: landslideVisible ? 'visible' : 'none' },
      paint: { 'raster-opacity': landslideOpacity, 'raster-resampling': 'nearest', 'raster-fade-duration': 0 },
    }, landBeforeLayer());
    // Tile longsor grid kotak ~25 km yang nyembul ke laut. Tutup dengan polygon
    // air basemap (source protomaps, sama seperti mask daratan model cuaca global)
    // yang diwarnai persis warna background peta, jadi tepinya ikut garis pantai.
    if (map.getSource('protomaps') && !map.getLayer('landslide-sea-mask')) {
      const bg = map.getPaintProperty('background', 'background-color');
      map.addLayer({
        id: 'landslide-sea-mask',
        type: 'fill',
        source: 'protomaps',
        'source-layer': 'water',
        filter: ['==', '$type', 'Polygon'],
        paint: {
          'fill-color': typeof bg === 'string' && bg ? bg : '#0b1220',
          'fill-opacity': 1,
        },
      }, landBeforeLayer());
    }
    applyHazardOrder();
  }

  function applyHazardOrder() {
    if (!map) return;
    applyLayerOrder(map, layerOrder, overlayBeforeLayer(), inariskOwner);
  }

  function moveHazard(kind, direction) {
    layerOrder = moveActiveLayer(layerOrder, activeLayerOrder, kind, direction);
    if (inariskVisible) {
      if (landslideOn) renderLandslide();
      if (floodOn) renderFlood();
    }
    applyHazardOrder();
  }

  async function applyLandslide() {
    landslideRequest?.abort();
    const request = new AbortController();
    landslideRequest = request;
    clearLandslide();
    try {
      const metadata = await fetchLandslideMetadata(request.signal);
      if (request.signal.aborted || !landslideOn) return;
      const anchor = currentTimelineAnchor();
      landslideMeta = metadata;
      landslideRows = metadata.steps.map((row) => ({ ...row, validTime: timelineTime(row, metadata.run_time) }));
      landslideRunTime = metadata.run_time;
      const selection = reconcileTimeline(landslideRows, landslideRunTime, anchor);
      landslideStep = selection.step;
      timelineNotice = selection.notice;
      timelineAnchor = null;
      renderLandslide();
    } catch (error) {
      if (request.signal.aborted) return;
      landslideMeta = null;
      landslideRows = [];
    }
  }

  async function handleLandslideClick(event) {
    if (!landslideMeta || !landslideVisible || !map.getLayer('landslide-layer')) return;
    landslidePointRequest?.abort();
    landslidePopup?.remove();
    const request = new AbortController();
    landslidePointRequest = request;
    const metadata = landslideMeta;
    const step = landslideStep;
    try {
      const data = await fetchLandslidePoint(metadata, step, event.lngLat.lat, event.lngLat.lng, request.signal);
      if (request.signal.aborted || !landslideOn || metadata !== landslideMeta || step !== landslideStep) return;
      landslidePopup = new maplibregl.Popup({ maxWidth: '320px' }).setLngLat(event.lngLat).setDOMContent(pointContent(data)).addTo(map);
    } catch {
      // Klik gagal: tidak ada banner status.
    }
  }

  const hazardActive = $derived(landslideOn || floodOn);
  const hazardRows = $derived(hazardContext === 'flood' ? floodRows : landslideRows);
  const hazardStep = $derived(hazardContext === 'flood' ? floodStep : landslideStep);
  const hazardRunTime = $derived(hazardContext === 'flood' ? floodRunTime : landslideRunTime);
  const timelineSteps = $derived(hazardActive
    ? hazardRows.map((row) => ({ ...row, token: String(row.step), t: Date.parse(row.validTime) || 0 }))
    : nwpSteps);
  const timelineToken = $derived(hazardActive ? (hazardStep == null ? null : String(hazardStep)) : nwpStepToken);
  const timelinePlaying = $derived(hazardActive ? hazardPlaying : nwpPlaying);
  const timelineLoop = $derived(hazardActive ? hazardLoop : nwpLoop);
  const timelineRun = $derived(hazardActive ? (hazardRunTime || null) : (nwpData?.runTime || (nwpManifest ? modelRunTime(activeModel, nwpManifest) : null)));
  const timelineTitle = $derived(hazardActive ? (hazardContext === 'landslide' ? 'Potensi Tanah Longsor' : 'Potensi Banjir') : (nwpData?.title || MODELS[activeModel]?.title || ''));

  function seekTimeline(step) {
    if (hazardActive) { stopHazardPlay(); changeForecastStep(Number(step.step)); }
    else seekNwpStep(step);
  }
  function stepTimeline(delta) {
    if (!hazardActive) return stepBy(delta);
    stopHazardPlay();
    const index = hazardRows.findIndex((row) => Number(row.step) === hazardStep);
    let next = index + delta;
    if (next < 0 || next >= hazardRows.length) {
      if (!hazardLoop) return;
      next = (next + hazardRows.length) % hazardRows.length;
    }
    changeForecastStep(Number(hazardRows[next].step));
  }
  function startTimelinePlay() {
    if (!hazardActive) return startNwpPlay();
    if (hazardPlaying || !hazardRows.length) return;
    hazardPlaying = true;
    const tick = () => {
      if (!hazardPlaying) return;
      const index = hazardRows.findIndex((row) => Number(row.step) === hazardStep);
      let next = index + 1;
      if (next >= hazardRows.length) {
        if (!hazardLoop) { stopHazardPlay(); return; }
        next = 0;
      }
      changeForecastStep(Number(hazardRows[next].step));
      hazardTimer = setTimeout(tick, NWP_PLAY_MS);
    };
    hazardTimer = setTimeout(tick, NWP_PLAY_MS);
  }
  function stopTimelinePlay() {
    if (hazardActive) stopHazardPlay();
    else stopNwpPlay();
  }
  function setTimelineLoop(on) {
    if (hazardActive) hazardLoop = on;
    else nwpLoop = on;
  }

  function changeForecastStep(step) {
    nwpClickSeq++;
    if (hazardContext === 'flood') {
      floodStep = step;
      renderFlood();
    } else {
      landslideStep = step;
      renderLandslide();
    }
  }

  function changeFloodOpacity(value) {
    floodOpacity = value;
    if (map?.getLayer('flood-layer')) map.setPaintProperty('flood-layer', 'raster-opacity', value);
  }

  function changeLandslideOpacity(value) {
    landslideOpacity = value;
    if (map?.getLayer('landslide-layer')) map.setPaintProperty('landslide-layer', 'raster-opacity', value);
  }

  function toggleInarisk() {
    inariskVisible = !inariskVisible;
    if (landslideOn) renderLandslide();
    if (floodOn) renderFlood();
  }

  // User overlays (GeoJSON / GPX)
  let userLayers = $state([]);
  let userLayerSeq = 0;
  let drawCtrl = null;

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
    if (!m.getLayer('coastline_outline') && m.getSource('protomaps')) {
      m.addLayer(
        {
          id: 'coastline_outline',
          type: 'line',
          source: 'protomaps',
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
      hydrateDrawings().then(() => {
        if (drawCtrl) drawCtrl.sync();
        else if (map) {
          drawCtrl = new DrawingController(map);
        }
      });
      console.log('MapLibre GL Carto Dark Matter loaded successfully');
    });

    m.on('styledata', () => {
      if (m.isStyleLoaded()) {
        setupCartoBoundaries(m);
        restoreUserLayers();
        if (drawCtrl) drawCtrl.restore();
      }
    });

    m.on('error', (e) => {
      console.error('MapLibre error:', e?.error?.message || e?.error || e);
    });

    m.on('style.load', () => {
      if (floodOn) renderFlood();
      if (landslideOn) renderLandslide();
    });
    m.on('click', (e) => {
      if (drawing.sidebarOpen || drawCtrl?.blocksInspect()) return;
      if (floodOn) handleFloodClick(e).catch(console.warn);
      if (landslideOn) handleLandslideClick(e).catch(console.warn);
      if (GLOBAL_MODELS.includes(activeModel)) handleNwpClick(e).catch((err) => console.warn('NWP click', err));
    });

    return () => {
      ++spartanRequest;
      spartanAbort?.abort();
      clearTimeout(spartanSeekTimer);
      cancelSatellite();
      stopSpartanPlay();
      stopNwpPoll();
      stopFlood();
      stopLandslide();
      stopNwpPlay();
      closeNwpPopup();
      if (drawCtrl) {
        drawCtrl.destroy();
        drawCtrl = null;
      }
      if (windOverlay) {
        windOverlay.destroy();
        windOverlay = null;
      }
      closeMeteogram();
      m.remove();
    };
  });

  // Longsor & banjir harus di BAWAH fill air basemap. Layer `water` Carto
  // (source-layer water, kind=ocean) menutupi seluruh laut, jadi tile yang
  // luber melewati garis pantai tertutup dan hanya tersisa di pulau.
  function landBeforeLayer() {
    if (map.getLayer('water')) return 'water';
    if (map.getLayer('water_shadow')) return 'water_shadow';
    return undefined;
  }

  function overlayBeforeLayer() {
    if (map.getLayer('coastline_outline')) return 'coastline_outline';
    if (map.getLayer('boundary_county')) return 'boundary_county';
    if (map.getLayer('boundary_state')) return 'boundary_state';
    if (map.getLayer('boundary_country_inner')) return 'boundary_country_inner';
    if (map.getLayer('waterway_label')) return 'waterway_label';
    if (map.getLayer('place_hamlet')) return 'place_hamlet';
    // Fill air basemap menutup seluruh laut. Raster harus di atasnya,
    // kalau tidak forecast hanya terlihat di daratan.
    if (map.getLayer('water_shadow')) return 'water_shadow';
    if (map.getLayer('water')) return 'water';
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
    inspectPop.loading = false;
    inspectPop.data = null;
    inspectPop.error = null;
    if (nwpPopup) {
      const p = nwpPopup;
      nwpPopup = null;
      p.remove();
    }
  }

  function closeMeteogram() {
    meteogramGeneration += 1;
    meteogramRequest?.abort();
    meteogramRequest = null;
    meteogramOpen = false;
    meteogramLoading = false;
    meteogramSeries = null;
    meteogramLocation = null;
    meteogramSignature = '';
    meteogramMarker?.remove();
    meteogramMarker = null;
    mapContainer?.parentElement?.style.removeProperty('--meteogram-visible-height');
  }

  async function loadMeteogram() {
    if (!meteogramLocation || !nwpManifest || !GLOBAL_MODELS.includes(activeModel)) return;
    meteogramRequest?.abort();
    const request = new AbortController();
    const generation = ++meteogramGeneration;
    meteogramRequest = request;
    meteogramSignature = meteogramManifestKey(activeModel, nwpManifest);
    meteogramLoading = true;
    meteogramError = null;
    meteogramSeries = null;
    try {
      const result = await fetchMeteogram({ modelId: activeModel, manifest: nwpManifest,
        latitude: meteogramLocation.lat, longitude: meteogramLocation.lon, signal: request.signal });
      if (request.signal.aborted || generation !== meteogramGeneration) return;
      meteogramSeries = result;
    } catch (error) {
      if (request.signal.aborted || generation !== meteogramGeneration) return;
      meteogramError = error.message || 'Gagal memuat meteogram';
    } finally {
      if (generation === meteogramGeneration) meteogramLoading = false;
    }
  }

  function openMeteogram(data) {
    if (!data || data.modelId !== activeModel || !nwpManifest
      || data.runId !== modelRunId(activeModel, nwpManifest)) return;
    meteogramLocation = { lat: data.lat, lon: data.lon };
    meteogramOpen = true;
    meteogramMarker?.remove();
    meteogramMarker = new maplibregl.Marker({ color: '#F08D82' })
      .setLngLat([data.lon, data.lat]).addTo(map);
    // Keep popup mounted for focus return; a new map click never opens the sheet itself.
    loadMeteogram();
  }

  function selectMeteogramTime(time) {
    const step = nearestStep(nwpSteps, time);
    if (!step) return;
    selectTimeline('nwp');
    seekNwpStep(step);
  }

  $effect(() => {
    const modelId = activeModel;
    const manifest = nwpManifest;
    if (!meteogramOpen || !manifest || !GLOBAL_MODELS.includes(modelId)) return;
    const signature = meteogramManifestKey(modelId, manifest);
    untrack(() => {
      if (signature !== meteogramSignature) loadMeteogram();
    });
  });

  function setNwpPopupProps(lngLat, props) {
    if (!map) return;
    inspectPop.loading = props.loading ?? false;
    inspectPop.data = props.data ?? null;
    inspectPop.error = props.error ?? null;
    if (!nwpHost) nwpHost = document.createElement('div');
    if (!nwpPopupApp) {
      nwpPopupApp = mount(NwpPopup, { target: nwpHost, props: { onMeteogram: openMeteogram } });
    }
    if (!nwpPopup) {
      nwpPopup = new maplibregl.Popup({
        closeButton: true,
        closeOnClick: false,
        focusAfterOpen: false,
        maxWidth: '240px',
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
    if (!nwpPopup.isOpen()) {
      nwpPopup.setLngLat(lngLat).setDOMContent(nwpHost).addTo(map);
    } else {
      nwpPopup.setLngLat(lngLat);
    }
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
      modelId,
      runId: modelRunId(modelId, manifest),
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
        params: paramsAvailable(modelId, manifest),
        lat,
        lon: lng,
        zoom: map.getZoom(),
        onPartial: (partial) => {
          if (seq !== nwpClickSeq) return;
          setNwpPopupProps([lng, lat], {
            loading: true,
            error: null,
            data: { ...base, ...partial, lokasi: inspectPop.data?.lokasi ?? null },
          });
        },
      });
      if (seq !== nwpClickSeq) return;
      setNwpPopupProps([lng, lat], {
        loading: false,
        error: null,
        data: { ...base, ...result, lokasi: inspectPop.data?.lokasi ?? null },
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

  function nwpMaskId(slot) {
    return slot ? 'nwp-sea-mask-b' : 'nwp-sea-mask';
  }

  function seaMaskColor() {
    if (!map) return '#0b1220';
    const bg = map.getPaintProperty('background', 'background-color');
    return typeof bg === 'string' && bg ? bg : '#0b1220';
  }

  function applyNwpExtent() {
    if (!map) return;
    for (const slot of [0, 1]) {
      const mask = nwpMaskId(slot);
      const lid = nwpLayerId(slot);
      if (nwpExtent === 'land' && map.getLayer(lid) && map.getSource('protomaps')) {
        if (!map.getLayer(mask)) {
          map.addLayer(
            {
              id: mask,
              type: 'fill',
              source: 'protomaps',
              'source-layer': 'water',
              filter: ['==', '$type', 'Polygon'],
              paint: { 'fill-color': seaMaskColor(), 'fill-opacity': 1 },
            },
            overlayBeforeLayer()
          );
        }
        applyHazardOrder();
        continue;
      }
      if (map.getLayer(mask)) map.removeLayer(mask);
    }
  }

  function setNwpExtent(extent) {
    if (extent !== 'land' && extent !== 'full') return;
    nwpExtent = extent;
    applyNwpExtent();
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
    const mask = nwpMaskId(slot);
    const lid = nwpLayerId(slot);
    const sid = nwpSourceId(slot);
    if (map.getLayer(mask)) map.removeLayer(mask);
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
    closeMeteogram();
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
    applyNwpExtent();
    // nwpBeforeLayer menyisipkan raster di bawah hazard yang sudah ada.
    applyHazardOrder();
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
    const readyVars = availableVars(modelId, manifest);
    const fallback = defaultVar(modelId);
    if (readyVars.length && nwpVar && !readyVars.includes(nwpVar)) {
      nwpVar = readyVars.includes(fallback) ? fallback : readyVars[0];
    }
    const varId = nwpVar || fallback;
    const steps = listNwpSteps(modelId, manifest, varId);
    const anchor = currentTimelineAnchor();
    nwpManifest = manifest;
    nwpSteps = steps;
    const preferred = nwpWantValid != null
      ? nearestStep(steps, nwpWantValid)
      : pickNwpStep(modelId, manifest, varId);
    const selection = reconcileTimeline(steps, modelRunTime(modelId, manifest), anchor, preferred ? Number(preferred.step) : null);
    timelineNotice = selection.notice;
    timelineAnchor = null;
    const step = steps.find((s) => Number(s.step) === selection.step);
    if (!step) {
      removeNwpLayer();
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
    applyHazardOrder();
  }

  // Manage Satellite Layer on Map
  function renderSatellite(data) {
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
    applyHazardOrder();
  }

  // Manage SPARTAN Layer on Map (BMKG fire-weather tiles, TMS scheme)
  function applySpartan(data) {
    if (!map || !mapLoaded) return;

    // Remove existing SPARTAN layer & source
    if (map.getLayer('spartan-layer')) {
      map.removeLayer('spartan-layer');
    }
    if (map.getSource('spartan-source')) {
      map.removeSource('spartan-source');
    }

    if (!data) {
      spartanData = null;
      return;
    }

    const { product, startDate, endDate, opacity } = data;
    const tileUrl = spartanTileTemplate({ product: product.id, start: startDate, end: endDate });
    console.log('Applying SPARTAN tile URL template:', tileUrl);

    map.addSource('spartan-source', {
      type: 'raster',
      scheme: 'tms',
      tiles: [tileUrl],
      tileSize: 256,
      minzoom: 0,
      maxzoom: 12,
    });

    // Place SPARTAN above satellite but below radar, coastline, boundaries & labels
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
        id: 'spartan-layer',
        type: 'raster',
        source: 'spartan-source',
        paint: {
          'raster-opacity': opacity ?? 0.9,
          'raster-fade-duration': 200,
        },
      },
      beforeLayer
    );

    spartanData = data;
    applyHazardOrder();
  }

  function toggleHazard(kind) {
    const on = kind === 'flood' ? floodOn : landslideOn;
    timelineNotice = '';
    if (on) {
      if (kind === 'flood') { stopFlood(); floodMeta = null; floodRows = []; floodOn = false; }
      else { stopLandslide(); landslideMeta = null; landslideRows = []; landslideOn = false; }
      if (landslideOn || floodOn) hazardContext = landslideOn ? 'landslide' : 'flood';
      return;
    }
    timelineAnchor = currentTimelineAnchor();
    hazardContext = kind;
    if (kind === 'flood') { floodOn = true; applyFlood(); floodPoll = setInterval(() => applyFlood(), ECMWF_POLL_MS); }
    else { landslideOn = true; applyLandslide(); landslidePoll = setInterval(() => applyLandslide(), ECMWF_POLL_MS); }
  }

  function handleSelectModel(modelId) {
    // Longsor dan banjir independen dari model NWP: bisa aktif bersamaan,
    // urutan tumpukannya diatur di card lapisan.
    if (modelId === 'flood' || modelId === 'landslide') {
      toggleHazard(modelId);
      return;
    }
    const next = activeModel === modelId ? null : modelId;
    nwpRequestSeq += 1;
    nwpClickSeq += 1;
    timelineAnchor = currentTimelineAnchor();
    timelineNotice = '';
    removeNwpLayer();
    activeModel = next;
    selectTimeline(next ? 'nwp' : (spartanActive ? 'spartan' : 'nwp'));
    stopNwpPlay();

    if (next && GLOBAL_MODELS.includes(next) && !windActive) {
      toggleWind();
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
        nwpManifest = null;
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
    const ready = availableVars(activeModel, nwpManifest);
    if (ready.length && !ready.includes(varId)) return;
    nwpVar = varId;
    if (GLOBAL_MODELS.includes(activeModel)) {
      applyNwp(activeModel).catch((err) => console.warn('NWP var', err));
    }
  }

  function currentWindContext() {
    if (!GLOBAL_MODELS.includes(activeModel)) return null;
    if (!nwpInspect || nwpInspect.modelId !== activeModel || !nwpInspect.manifest || !nwpInspect.step) {
      return null;
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

  function syncDraw() {
    drawCtrl?.sync();
    drawCtrl?.applyMode();
  }

  function cancelDrawDraft() {
    drawCtrl?.cancelDraft();
    drawCtrl?.applyMode();
  }

  function finishDrawDraft() {
    drawCtrl?.finishIfPossible();
    drawCtrl?.applyMode();
  }

  function adoptDrawTool(id) {
    drawCtrl?.adoptTool(id);
  }

  function handleToggleDrawing() {
    if (drawing.sidebarOpen) cancelDrawDraft();
    toggleSidebar();
    syncDraw();
  }

  function toggleDrawGroup(id) {
    const layer = drawing.layers.find((l) => l.id === id);
    if (!layer) return;
    setLayerVisible(id, !layer.visible);
    syncDraw();
  }

  function exportDrawPng() {
    if (!map) return;
    try {
      const canvas = map.getCanvas();
      const url = canvas.toDataURL('image/png');
      const a = document.createElement('a');
      a.href = url;
      a.download = `map-drawing-${Date.now()}.png`;
      a.click();
    } catch (err) {
      drawing.error = 'PNG gagal (raster silang origin). Coba GeoJSON.';
      console.warn('PNG export', err);
    }
  }
</script>

<main
    class="relative w-screen h-screen overflow-hidden bg-slate-100"
    class:nwp-timeline-on={!!satelliteData || spartanActive || (GLOBAL_MODELS.includes(activeModel) && nwpSteps.length > 0) || landslideRows.length > 0 || floodRows.length > 0}
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
    drawingActive={drawing.sidebarOpen}
    {spartanActive}
    spartanProduct={spartanProduct.id}
    onSelectSpartan={(product) => { stopSpartanPlay(); selectSpartan(product); }}
    onOpenRadar={() => (showRadarModal = true)}
    onOpenSatellite={() => (showSatelliteModal = true)}
    onOpenSpartan={toggleSpartan}
    onSelectModel={handleSelectModel}
    onToggleDrawing={handleToggleDrawing}
    landslideActive={landslideOn}
    floodActive={floodOn}
  />

  <DrawingSidebar
    onSync={syncDraw}
    onCancelDraft={cancelDrawDraft}
    onFinishDraft={finishDrawDraft}
    onAdoptTool={adoptDrawTool}
    onExportPng={exportDrawPng}
  />

  <!-- Active layers + user overlays — button at top-right -->
  <UserLayers
    layers={userLayers}
    drawGroups={drawing.layers}
    onAdd={addUserLayer}
    onToggle={toggleUserLayer}
    onFit={fitUserLayer}
    onRemove={removeUserLayer}
    onClearAll={clearUserLayers}
    onRename={renameUserLayer}
    onToggleDraw={toggleDrawGroup}
    {spartanData}
    {radarData}
    {satelliteData}
    {nwpData}
    landslideData={landslideOn && landslideMeta ? {
      runTime: landslideMeta.run_time,
      validTime: landslideRows.find((r) => Number(r.step) === landslideStep)?.validTime,
      opacity: landslideOpacity,
      inarisk: inariskVisible,
      vulnerabilityLowMax: landslideMeta.hazard_low_max,
      vulnerabilityMediumMax: landslideMeta.hazard_medium_max,
    } : null}
    onCloseRadar={() => applyRadar(null)}
    onCloseSatellite={() => applySatellite(null)}
    onCloseNwp={closeNwp}
    onCloseSpartan={() => { if (spartanActive) toggleSpartan(); }}
    onCloseLandslide={() => handleSelectModel('landslide')}
    onChangeLandslideOpacity={changeLandslideOpacity}
    onToggleInarisk={toggleInarisk}
    floodData={floodOn && floodMeta ? {
      runTime: floodMeta.run_time,
      validTime: floodRows.find((r) => Number(r.step) === floodStep)?.validTime,
      opacity: floodOpacity,
      inarisk: inariskVisible,
    } : null}
    onCloseFlood={() => handleSelectModel('flood')}
    onChangeFloodOpacity={changeFloodOpacity}
    hazardOrder={activeLayerOrder}
    onMoveHazard={moveHazard}
  />

  {#if GLOBAL_MODELS.includes(activeModel)}
    <ParamToolbar
      params={paramsAvailable(activeModel, nwpManifest)}
      activeVar={nwpVar}
      readyIds={availableVars(activeModel, nwpManifest)}
      onSelectVar={handleSelectNwpVar}
      {windActive}
      {windSpeed}
      {windStatus}
      onToggleWind={toggleWind}
      onChangeWindSpeed={changeWindSpeed}
      extent={nwpExtent}
      onSetExtent={setNwpExtent}
    />
  {/if}

  {#if spartanActive && timelineContext === 'spartan'}
    <div class="karhutla-status" role="status">
      {spartanStatus || 'Slot tanggal diperiksa saat dipilih; data BMKG belum tentu tersedia.'}
      {#if spartanAvailableFrames}
        <button type="button" disabled={spartanLoading} onclick={() => { stopSpartanPlay(); selectSpartan(spartanProduct, spartanAvailableFrames[0], spartanAvailableFrames); }}>Tampilkan data terbaru</button>
      {/if}
    </div>
  {/if}
  {#if Number(spartanActive) + Number(GLOBAL_MODELS.includes(activeModel)) + Number(!!satelliteData) > 1}
    <div class="timeline-context" aria-label="Konteks timeline">
      {#if GLOBAL_MODELS.includes(activeModel)}<button type="button" aria-pressed={timelineContext === 'nwp'} onclick={() => selectTimeline('nwp')}>NWP</button>{/if}
      {#if spartanActive}<button type="button" aria-pressed={timelineContext === 'spartan'} onclick={() => selectTimeline('spartan')}>KARHUTLA</button>{/if}
      {#if satelliteData}<button type="button" aria-pressed={timelineContext === 'satellite'} onclick={() => selectTimeline('satellite')}>Satelit</button>{/if}
    </div>
  {/if}
  {#if satelliteData}<div class="karhutla-status" role="status">{satelliteStatus}</div>{/if}
  {#key `${timelineContext}:${satelliteData?.product.id || ''}`}
  {#if satelliteData && timelineContext === 'satellite'}
    <ForecastTimeline observation={true} steps={satelliteSteps} selectedToken={satelliteData.currentBaserun}
      playing={satellitePlaying} loop={satelliteLoop} disabled={!satelliteSteps.length}
      modelTitle={satelliteData.product.label || 'Satelit'} onSeek={queueSatellite}
      onPlay={startSatellitePlay} onPause={stopSatellitePlay}
      onPrev={() => { stopSatellitePlay(); stepSatellite(-1); }} onNext={() => { stopSatellitePlay(); stepSatellite(1); }}
      onLoop={(on) => (satelliteLoop = on)} />
  {:else if spartanActive && timelineContext === 'spartan'}
    <ForecastTimeline daily={true} steps={spartanFrames} selectedToken={spartanToken}
      playing={spartanPlaying} loop={spartanLoop} disabled={!spartanFrames.length}
      modelTitle={`KARHUTLA ${spartanData?.product.code || spartanProduct.code}`} onSeek={seekSpartan}
      onPlay={startSpartanPlay} onPause={stopSpartanPlay}
      onPrev={() => { stopSpartanPlay(); stepSpartan(-1); }} onNext={() => { stopSpartanPlay(); stepSpartan(1); }}
      onLoop={(on) => (spartanLoop = on)} />
  {:else if (GLOBAL_MODELS.includes(activeModel) && nwpSteps.length > 0) || hazardRows.length > 0}
    <ForecastTimeline
      steps={timelineSteps}
      selectedToken={timelineToken}
      playing={timelinePlaying}
      loop={timelineLoop}
      disabled={!timelineSteps.length}
      modelTitle={timelineTitle}
      runTime={timelineRun}
      onSeek={seekTimeline}
      onPlay={startTimelinePlay}
      onPause={stopTimelinePlay}
      onPrev={() => stepTimeline(-1)}
      onNext={() => stepTimeline(1)}
      onLoop={(on) => setTimelineLoop(on)}
    />
  {/if}

  {/key}

  {#if meteogramOpen}
    <MeteogramSheet series={meteogramSeries} loading={meteogramLoading} error={meteogramError}
      activeTime={nwpSteps.find(step => step.token === nwpStepToken)?.t ?? null}
      onClose={closeMeteogram} onRetry={loadMeteogram} onSelectTime={selectMeteogramTime}/>
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

<style>
  .karhutla-status { position: absolute; z-index: 35; top: 88px; left: 16px; right: 88px; max-width: 420px; color: #fff; background: #172033; border-radius: 6px; font-size: 12px; padding: 6px; }
  .karhutla-status:empty { display: none; }
  .karhutla-status button { display: block; margin-top: 6px; padding: 4px 10px; border: 1px solid #93c5fd; border-radius: 9999px; background: #2563eb; color: #fff; cursor: pointer; }
  .karhutla-status button:disabled { opacity: 0.5; cursor: wait; }
  .timeline-context button { background: #172033; color: #fff; border: 1px solid #64748b; border-radius: 8px; padding: 8px 10px; font-size: 12px; cursor: pointer; }
  .timeline-context button[aria-pressed='true'] { background: #2563eb; border-color: #93c5fd; }
  .timeline-context { position: absolute; z-index: 36; bottom: calc(var(--meteogram-visible-height, 0px) + 130px); left: 16px; display: flex; gap: 6px; }
  @media (max-width: 640px) { .timeline-context { bottom: calc(var(--meteogram-visible-height, 0px) + 180px); } }
</style>
