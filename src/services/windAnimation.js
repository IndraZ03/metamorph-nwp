import { WindField, DemoWindField, screenVelocity } from './windField.js';

export class WindOverlay {
  constructor(map, { speed = 1.0, onStatus } = {}) {
    this.map = map;
    this.speed = Math.max(0.2, Math.min(3.0, Number(speed) || 1.0));
    this.onStatus = onStatus;
    this.field = new DemoWindField();
    this.mode = 'demo';
    this.abortController = null;
    this.contextKey = null;
    this.loading = false;
    this.canvas = null;
    this.ctx = null;
    this.animId = null;
    this.running = false;
    this.particles = [];
    this.moving = false;
    this.lastTime = null;
    this.dpr = typeof window !== 'undefined' ? Math.min(window.devicePixelRatio || 1, 2) : 1;

    this.onMoveStart = () => {
      this.moving = true;
      if (this.ctx && this.canvas) {
        this.ctx.clearRect(0, 0, this.canvas.width, this.canvas.height);
      }
    };

    this.onMoveEnd = () => {
      this.moving = false;
      this.initParticles();
    };

    this.onResize = () => {
      this.handleResize();
      this.initParticles();
    };

    this.initCanvas();
  }

  initCanvas() {
    if (!this.map) return;
    const container = this.map.getCanvasContainer();
    if (!container) return;

    this.canvas = document.createElement('canvas');
    this.canvas.className = 'wind-animation-canvas';
    this.canvas.style.position = 'absolute';
    this.canvas.style.top = '0';
    this.canvas.style.left = '0';
    this.canvas.style.width = '100%';
    this.canvas.style.height = '100%';
    this.canvas.style.pointerEvents = 'none';
    this.canvas.style.zIndex = '2';
    container.appendChild(this.canvas);

    this.ctx = this.canvas.getContext('2d', { willReadFrequently: false });
    this.handleResize();

    this.map.on('movestart', this.onMoveStart);
    this.map.on('moveend', this.onMoveEnd);
    this.map.on('resize', this.onResize);
  }

  handleResize() {
    if (!this.canvas || !this.map) return;
    const rect = this.map.getCanvas().getBoundingClientRect();
    const w = Math.round(rect.width);
    const h = Math.round(rect.height);

    this.canvas.width = Math.round(w * this.dpr);
    this.canvas.height = Math.round(h * this.dpr);
    this.canvas.style.width = `${w}px`;
    this.canvas.style.height = `${h}px`;

    if (this.ctx) {
      this.ctx.setTransform(1, 0, 0, 1, 0, 0);
      this.ctx.scale(this.dpr, this.dpr);
    }
  }

  async setContext(context) {
    const contextKey = context ? JSON.stringify([
      context.modelId, context.manifest?.run_id || context.manifest?.run,
      context.step?.token, context.manifest?.updated_at,
    ]) : null;
    if (contextKey && contextKey === this.contextKey && (this.loading || this.mode === 'model')) return;

    this.abortController?.abort();
    const controller = new AbortController();
    this.abortController = controller;
    this.contextKey = contextKey;
    this.loading = false;
    this.field = new DemoWindField(context?.bbox);
    this.mode = 'demo';
    this.initParticles();
    this.ctx?.clearRect(0, 0, this.canvas.width, this.canvas.height);

    if (!context?.modelId || !context?.manifest || !context?.step) {
      this.onStatus?.({ state: 'ready', mode: 'demo', message: 'Simulasi — bukan data model' });
      return;
    }

    this.loading = true;
    this.onStatus?.({ state: 'loading', mode: 'demo', message: 'Memuat data angin U/V...' });
    try {
      const field = new WindField(context);
      await field.load(controller.signal);
      if (controller.signal.aborted || !this.map) return;

      this.field = field;
      this.mode = 'model';
      this.loading = false;
      this.initParticles();
      this.onStatus?.({ state: 'ready', mode: 'model', message: 'Data NWP U/V Aktif' });
    } catch {
      if (controller.signal.aborted || !this.map) return;
      // Keep demo explicitly separate from model forecasts when U/V tiles are unavailable.
      this.field = new DemoWindField(context.bbox || [88, -15, 148, 12]);
      this.mode = 'demo';
      this.loading = false;
      this.initParticles();
      this.onStatus?.({ state: 'ready', mode: 'demo', message: 'Simulasi (U/V model belum tersedia)' });
    }
  }

  initParticles() {
    if (!this.map) return;
    const rect = this.map.getCanvas().getBoundingClientRect();
    // Ventusky density: ~1800 for desktop, ~800 for mobile
    const count = Math.max(700, Math.min(2200, Math.floor((rect.width * rect.height) / 850)));
    this.particles = [];
    for (let i = 0; i < count; i++) {
      this.particles.push(this.createParticle());
    }
  }

  createParticle() {
    if (!this.map) return { lon: 0, lat: 0, age: 0, maxAge: 25, prevX: null, prevY: null };
    const bounds = this.map.getBounds();
    const west = bounds.getWest();
    const east = bounds.getEast();
    const south = bounds.getSouth();
    const north = bounds.getNorth();

    const [fieldWest, fieldSouth, fieldEast, fieldNorth] = this.field.bbox;
    const minLon = Math.max(west, fieldWest), maxLon = Math.min(east, fieldEast);
    const minLat = Math.max(south, fieldSouth), maxLat = Math.min(north, fieldNorth);
    const lon = minLon + Math.random() * Math.max(0, maxLon - minLon);
    const lat = minLat + Math.random() * Math.max(0, maxLat - minLat);

    // Lifetime in seconds, independent of monitor refresh rate.
    const maxAge = 1 + Math.random() * 1.2;
    const pt = this.map.project([lon, lat]);

    return {
      lon,
      lat,
      age: Math.random() * maxAge,
      maxAge,
      prevX: pt.x,
      prevY: pt.y,
    };
  }

  setSpeed(val) {
    this.speed = Math.max(0.2, Math.min(3.0, Number(val) || 1.0));
  }

  start() {
    if (this.running) return;
    this.running = true;
    this.lastTime = null;
    this.initParticles();
    this.animate(performance.now());
  }

  stop() {
    this.running = false;
    if (this.animId) {
      cancelAnimationFrame(this.animId);
      this.animId = null;
    }
    if (this.ctx && this.canvas) {
      this.ctx.clearRect(0, 0, this.canvas.width, this.canvas.height);
    }
  }

  animate(time) {
    if (!this.running || !this.field) {
      this.animId = null;
      return;
    }
    const dt = this.lastTime === null ? 1 / 60 : Math.min(0.05, Math.max(0, (time - this.lastTime) / 1000));
    this.lastTime = time;
    this.render(dt);
    this.animId = requestAnimationFrame(nextTime => this.animate(nextTime));
  }

  render(dt = 1 / 60) {
    if (!this.ctx || !this.map || !this.canvas || !this.field) return;

    const rect = this.map.getCanvas().getBoundingClientRect();
    const w = rect.width;
    const h = rect.height;

    if (this.moving) {
      this.ctx.clearRect(0, 0, w, h);
      return;
    }

    // Ventusky trail fade: 0.18 provides crisp, clean short streaks without spaghetti clutter
    this.ctx.globalCompositeOperation = 'destination-out';
    this.ctx.fillStyle = `rgba(0, 0, 0, ${1 - Math.exp(-dt / 0.12)})`;
    this.ctx.fillRect(0, 0, w, h);

    // Streamline stroke settings
    this.ctx.globalCompositeOperation = 'source-over';
    this.ctx.lineWidth = 0.95;
    this.ctx.lineCap = 'round';
    this.ctx.lineJoin = 'round';

    const bounds = this.map.getBounds();
    const west = bounds.getWest();
    const east = bounds.getEast();
    const south = bounds.getSouth();
    const north = bounds.getNorth();

    for (let i = 0; i < this.particles.length; i++) {
      let p = this.particles[i];

      // Respawn expired or out-of-viewport particles
      if (
        p.age >= p.maxAge ||
        p.lon < west ||
        p.lon > east ||
        p.lat < south ||
        p.lat > north ||
        p.prevX === null ||
        p.prevX < -30 ||
        p.prevX > w + 30 ||
        p.prevY < -30 ||
        p.prevY > h + 30
      ) {
        this.particles[i] = this.createParticle();
        p = this.particles[i];
      }

      const wind = this.field.sample(p.lon, p.lat);
      if (!wind) {
        this.particles[i] = this.createParticle();
        continue;
      }

      const v = screenVelocity(this.map, p.lon, p.lat, wind);
      const nextX = p.prevX + v.x * this.speed * dt;
      const nextY = p.prevY + v.y * this.speed * dt;

      const segDist = Math.hypot(nextX - p.prevX, nextY - p.prevY);

      if (segDist < 30.0) {
        // Ventusky triangular alpha: quick fade-in, crisp peak, quick fade-out
        const lifeRatio = p.age / p.maxAge;
        let alpha = 0.85;
        if (lifeRatio < 0.25) {
          alpha = (lifeRatio / 0.25) * 0.85;
        } else if (lifeRatio > 0.65) {
          alpha = ((1.0 - lifeRatio) / 0.35) * 0.85;
        }

        const spd = Math.hypot(wind.u, wind.v);
        const cyanShimmer = Math.min(255, Math.floor(225 + spd * 1.8));
        this.ctx.strokeStyle = `rgba(240, 248, ${cyanShimmer}, ${alpha.toFixed(3)})`;

        this.ctx.beginPath();
        this.ctx.moveTo(p.prevX, p.prevY);
        this.ctx.lineTo(nextX, nextY);
        this.ctx.stroke();
      }

      // Project back to geographical coordinates
      const nextLngLat = this.map.unproject([nextX, nextY]);
      p.lon = nextLngLat.lng;
      p.lat = nextLngLat.lat;
      p.prevX = nextX;
      p.prevY = nextY;
      p.age += dt;
    }
  }

  destroy() {
    this.stop();
    this.abortController?.abort();
    if (this.map) {
      this.map.off('movestart', this.onMoveStart);
      this.map.off('moveend', this.onMoveEnd);
      this.map.off('resize', this.onResize);
    }
    if (this.canvas && this.canvas.parentNode) {
      this.canvas.parentNode.removeChild(this.canvas);
    }
    this.canvas = null;
    this.ctx = null;
    this.map = null;
    this.field = null;
    this.particles = [];
  }
}
