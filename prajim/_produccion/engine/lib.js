// Libreria comun para las composiciones de PRAJIM (render determinista por tiempo).
(function () {
  const P = {};
  P.W = 1080; P.H = 1920;
  P.ASSETS = new URL('../assets/', document.currentScript.src).href;
  P.clamp = (x, a = 0, b = 1) => Math.min(b, Math.max(a, x));
  P.lerp = (a, b, t) => a + (b - a) * t;
  P.prog = (t, a, b) => P.clamp((t - a) / (b - a));
  P.env = (t, a, b, c, d) => Math.min(P.prog(t, a, b), 1 - P.prog(t, c, d));
  const E = {
    linear: x => x,
    inQuad: x => x * x, outQuad: x => 1 - (1 - x) * (1 - x),
    inOutQuad: x => x < .5 ? 2 * x * x : 1 - Math.pow(-2 * x + 2, 2) / 2,
    inCubic: x => x * x * x, outCubic: x => 1 - Math.pow(1 - x, 3),
    inOutCubic: x => x < .5 ? 4 * x * x * x : 1 - Math.pow(-2 * x + 2, 3) / 2,
    outQuart: x => 1 - Math.pow(1 - x, 4), outQuint: x => 1 - Math.pow(1 - x, 5),
    inOutQuart: x => x < .5 ? 8 * x * x * x * x : 1 - Math.pow(-2 * x + 2, 4) / 2,
    outExpo: x => x === 1 ? 1 : 1 - Math.pow(2, -10 * x),
    inExpo: x => x === 0 ? 0 : Math.pow(2, 10 * x - 10),
    inOutExpo: x => x === 0 ? 0 : x === 1 ? 1 : x < .5 ? Math.pow(2, 20 * x - 10) / 2 : (2 - Math.pow(2, -20 * x + 10)) / 2,
    inOutSine: x => -(Math.cos(Math.PI * x) - 1) / 2, outSine: x => Math.sin(x * Math.PI / 2),
    outBack: (x, s = 1.70158) => 1 + (s + 1) * Math.pow(x - 1, 3) + s * Math.pow(x - 1, 2),
    outElastic: x => x === 0 ? 0 : x === 1 ? 1 : Math.pow(2, -10 * x) * Math.sin((x * 10 - 0.75) * (2 * Math.PI) / 3) + 1,
  };
  P.E = E;
  P.ease = (t, a, b, fn = 'outCubic') => (typeof fn === 'function' ? fn : E[fn])(P.prog(t, a, b));

  // aleatorio con semilla
  P.rng = function (seed) {
    let a = seed >>> 0;
    return function () {
      a |= 0; a = a + 0x6D2B79F5 | 0;
      let t = Math.imul(a ^ a >>> 15, 1 | a);
      t = t + Math.imul(t ^ t >>> 7, 61 | t) ^ t;
      return ((t ^ t >>> 14) >>> 0) / 4294967296;
    };
  };
  // ruido suave 1D determinista
  P.noise1 = function (x, seed = 1) {
    const r = i => { const g = P.rng(Math.floor(i) * 7919 + seed * 104729); return g() * 2 - 1; };
    const i = Math.floor(x), f = x - i, u = f * f * (3 - 2 * f);
    return r(i) * (1 - u) + r(i + 1) * u;
  };

  P.$ = (sel, root = document) => root.querySelector(sel);
  P.el = function (tag, cls, parent, html) {
    const e = document.createElement(tag);
    if (cls) e.className = cls;
    if (html !== undefined) e.innerHTML = html;
    if (parent) parent.appendChild(e);
    return e;
  };
  P.style = function (e, s) { for (const k in s) e.style[k] = s[k]; return e; };

  // ---------- secuencias de imagenes (tomas pre-extraidas) ----------
  const pending = [];
  P.waitAll = async function () {
    const list = pending.splice(0);
    await Promise.all(list);
  };
  P.setSrc = function (img, src) {
    if (img._src === src) return;
    img._src = src;
    img.src = src;
    pending.push(img.decode().catch(() => {}));
  };
  class Seq {
    constructor(parent, dir, opts = {}) {
      this.dir = dir.endsWith('/') ? dir : dir + '/';
      this.n = opts.frames || 150;
      this.fps = opts.fps || 30;
      this.loop = opts.loop || false;
      this.pingpong = opts.pingpong || false;
      this.wrap = P.el('div', 'video', parent);
      this.img = P.el('img', '', this.wrap);
      if (opts.z !== undefined) this.wrap.style.zIndex = opts.z;
    }
    frameAt(lt, speed = 1) {
      let i = Math.floor(lt * this.fps * speed + 1e-6);
      if (this.pingpong) { const p = 2 * (this.n - 1); i = ((i % p) + p) % p; if (i >= this.n) i = p - i; }
      else if (this.loop) i = ((i % this.n) + this.n) % this.n;
      else i = P.clamp(i, 0, this.n - 1);
      return i;
    }
    set(lt, speed = 1) {
      const i = this.frameAt(lt, speed);
      P.setSrc(this.img, this.dir + String(i).padStart(5, '0') + '.jpg');
    }
    show(v) { this.wrap.style.display = v ? 'block' : 'none'; }
  }
  P.Seq = Seq;

  // ---------- texto ----------
  // Divide un elemento en palabras con mascara. Devuelve array de .mi
  P.splitWords = function (e) {
    const html = e.innerHTML;
    const tmp = document.createElement('div');
    tmp.innerHTML = html;
    e.innerHTML = '';
    const out = [];
    const walk = (node, target) => {
      node.childNodes.forEach(n => {
        if (n.nodeType === 3) {
          const parts = n.textContent.split(/(\s+)/);
          parts.forEach(p => {
            if (!p) return;
            if (/^\s+$/.test(p)) { target.appendChild(document.createTextNode(' ')); return; }
            const m = P.el('span', 'm', target);
            const mi = P.el('span', 'mi', m);
            mi.textContent = p;
            out.push(mi);
          });
        } else if (n.nodeName === 'BR') {
          target.appendChild(document.createElement('br'));
        } else {
          const c = n.cloneNode(false);
          target.appendChild(c);
          walk(n, c);
        }
      });
    };
    walk(tmp, e);
    return out;
  };
  P.splitChars = function (e) {
    const txt = e.textContent;
    e.textContent = '';
    return [...txt].map(ch => { const s = P.el('span', 'ch', e); s.textContent = ch; return s; });
  };
  // revelado con mascara (palabra sube desde abajo)
  P.maskIn = function (items, t, start, opts = {}) {
    const st = opts.stagger ?? 0.06, dur = opts.dur ?? 0.55, ease = opts.ease || 'outQuart';
    const from = opts.from ?? 110, outAt = opts.outAt, outDur = opts.outDur ?? 0.35;
    items.forEach((it, i) => {
      let y = from * (1 - P.ease(t, start + i * st, start + i * st + dur, ease));
      let o = 1;
      if (outAt !== undefined) {
        const k = P.ease(t, outAt + i * st * 0.5, outAt + i * st * 0.5 + outDur, 'inCubic');
        y -= k * from;
        o = 1 - k;
      }
      it.style.transform = `translateY(${y}%)`;
      it.style.opacity = o;
    });
  };
  // aparicion letra por letra con desenfoque
  P.blurIn = function (chars, t, start, opts = {}) {
    const st = opts.stagger ?? 0.03, dur = opts.dur ?? 0.5;
    chars.forEach((c, i) => {
      const k = P.ease(t, start + i * st, start + i * st + dur, opts.ease || 'outCubic');
      c.style.opacity = k;
      c.style.filter = k >= 1 ? 'none' : `blur(${(1 - k) * (opts.blur ?? 14)}px)`;
      c.style.transform = `translateY(${(1 - k) * (opts.dy ?? 20)}px)`;
    });
  };
  // escribir texto letra por letra (globos de dialogo)
  P.typeText = function (e, full, t, start, cps = 22) {
    const n = Math.floor(P.clamp((t - start) * cps, 0, full.length));
    e.textContent = full.slice(0, n) || '​';
    return n >= full.length;
  };

  // ---------- gatito ----------
  // capas de 1064x1458, pivote de cabeza (720,640)
  P.Cat = class {
    constructor(parent, opts = {}) {
      this.root = P.el('div', 'abs', parent);
      P.style(this.root, { width: '1064px', height: '1458px', transformOrigin: '0 0', left: '0', top: '0' });
      this.inner = P.el('div', 'abs', this.root);
      P.style(this.inner, { width: '1064px', height: '1458px', transformOrigin: '532px 1458px' });
      const A = P.ASSETS + 'gatito/';
      const img = (src, extra = {}) => { const i = P.el('img', 'abs', this.inner); i.src = A + src; P.style(i, Object.assign({ left: 0, top: 0, width: '1064px', height: '1458px' }, extra)); return i; };
      this.shadow = img('cat_shadow.png', { transform: 'translate(10px,22px)' });
      this.outline = img('cat_outline.png');
      this.body = img('cat_body.png');
      this.head = P.el('div', 'abs', this.inner);
      P.style(this.head, { left: 0, top: 0, width: '1064px', height: '1458px', transformOrigin: '720px 640px' });
      this.heads = {};
      for (const k of ['normal', 'blink', 'wink', 'happy']) {
        const i = P.el('img', 'abs', this.head);
        i.src = A + (k === 'normal' ? 'cat_head.png' : `cat_head_${k}.png`);
        P.style(i, { left: 0, top: 0, width: '1064px', height: '1458px', display: k === 'normal' ? 'block' : 'none' });
        this.heads[k] = i;
      }
      const NS = 'http://www.w3.org/2000/svg';
      this.svg = document.createElementNS(NS, 'svg');
      this.svg.setAttribute('viewBox', '0 0 1064 1458');
      P.style(this.svg, { position: 'absolute', left: 0, top: 0, width: '1064px', height: '1458px', overflow: 'visible' });
      this.head.appendChild(this.svg);
      this.mouth = document.createElementNS(NS, 'path');
      this.mouth.setAttribute('fill', '#6e1f2a');
      this.mouth.setAttribute('stroke', '#43121a');
      this.mouth.setAttribute('stroke-width', '3');
      this.svg.appendChild(this.mouth);
      this.acc = document.createElementNS(NS, 'g');   // accesorios (sombrero, etc.)
      this.svg.appendChild(this.acc);
      this.state = {};
    }
    // s: {x, y, scale, rot, face, mouth(0..1), tilt(grados), breathe(true), squash, opacity}
    set(t, s) {
      const sc = s.scale ?? 0.5;
      const sq = s.squash ?? 0;
      this.root.style.transform = `translate(${s.x ?? 0}px, ${s.y ?? 0}px) scale(${sc}) rotate(${s.rot ?? 0}deg)`;
      this.root.style.opacity = s.opacity ?? 1;
      const br = s.breathe === false ? 0 : 0.012 * Math.sin(2 * Math.PI * 0.45 * t);
      this.inner.style.transform = `scale(${1 - sq * 0.5 - br * 0.3}, ${1 + br + sq})`;
      this.head.style.transform = `rotate(${s.tilt ?? 0}deg)`;
      const face = s.face || 'normal';
      for (const k in this.heads) this.heads[k].style.display = k === face ? 'block' : 'none';
      const o = s.mouth ?? 0;
      if (o < 0.06) this.mouth.setAttribute('d', '');
      else this.mouth.setAttribute('d', `M733 598 Q747 591 761 594 Q775 591 790 597 Q778 ${598 + 32 * o} 761 ${600 + 36 * o} Q744 ${600 + 32 * o} 733 598 Z`);
    }
    // apertura de boca al hablar entre a y b (~6 veces por segundo)
    static talk(t, a, b, rate = 6) {
      if (t < a || t > b) return 0;
      const v = Math.abs(Math.sin(Math.PI * rate * (t - a)));
      const fade = Math.min(1, (t - a) * 8, (b - t) * 8);
      return v * fade * (0.75 + 0.25 * Math.sin(t * 17.3));
    }
    // parpadeos automaticos en una lista de instantes
    static blinkAt(t, times, d = 0.15) { return times.some(x => t >= x && t < x + d); }
  };

  // ---------- particulas (canvas) ----------
  P.FX = class {
    constructor(parent, z = 50) {
      this.c = P.el('canvas', 'fx-canvas', parent);
      this.c.width = 1080; this.c.height = 1920;
      this.c.style.zIndex = z;
      this.x = this.c.getContext('2d');
    }
    clear() { this.x.clearRect(0, 0, 1080, 1920); }
    star(x, y, r, a, color = '255,236,190') {
      const c = this.x;
      c.save(); c.globalAlpha = a; c.translate(x, y);
      const g = c.createRadialGradient(0, 0, 0, 0, 0, r * 2.2);
      g.addColorStop(0, `rgba(${color},0.9)`); g.addColorStop(1, `rgba(${color},0)`);
      c.fillStyle = g; c.beginPath(); c.arc(0, 0, r * 2.2, 0, Math.PI * 2); c.fill();
      c.fillStyle = `rgba(255,252,240,1)`;
      c.beginPath();
      for (let k = 0; k < 8; k++) {
        const ang = k * Math.PI / 4, rr = k % 2 === 0 ? r : r * 0.18;
        c.lineTo(Math.cos(ang) * rr, Math.sin(ang) * rr);
      }
      c.closePath(); c.fill(); c.restore();
    }
    dot(x, y, r, a, color = '255,230,170') {
      const c = this.x;
      const g = c.createRadialGradient(x, y, 0, x, y, r);
      g.addColorStop(0, `rgba(${color},${a})`); g.addColorStop(1, `rgba(${color},0)`);
      c.fillStyle = g; c.beginPath(); c.arc(x, y, r, 0, Math.PI * 2); c.fill();
    }
    heart(x, y, s, a, color = '#E46A8C', rot = 0) {
      const c = this.x;
      c.save(); c.globalAlpha = a; c.translate(x, y); c.rotate(rot); c.scale(s / 30, s / 30);
      c.fillStyle = color; c.beginPath();
      c.moveTo(0, 10); c.bezierCurveTo(-30, -12, -12, -32, 0, -16); c.bezierCurveTo(12, -32, 30, -12, 0, 10);
      c.fill(); c.restore();
    }
    // polvo dorado flotante determinista
    dust(t, n, seed, opts = {}) {
      const R = P.rng(seed);
      const area = opts.area || [0, 0, 1080, 1920];
      for (let i = 0; i < n; i++) {
        const x0 = area[0] + R() * area[2], y0 = area[1] + R() * area[3];
        const sp = (opts.speed ?? 30) * (0.4 + R()), ph = R() * 10, sz = (opts.size ?? 5) * (0.4 + R());
        const y = ((y0 - t * sp) - area[1] + area[3] * 10) % area[3] + area[1];
        const x = x0 + Math.sin(t * 0.6 + ph) * 18;
        const tw = 0.5 + 0.5 * Math.sin(t * 2.2 + ph * 3);
        this.dot(x, y, sz * 2.4, (opts.alpha ?? 0.5) * tw, opts.color);
      }
    }
    // rafaga de destellos desde un punto
    burst(t, t0, x, y, n, seed, opts = {}) {
      const dt = t - t0, life = opts.life ?? 1.1;
      if (dt < 0 || dt > life) return;
      const R = P.rng(seed);
      for (let i = 0; i < n; i++) {
        const ang = R() * Math.PI * 2, sp = (opts.speed ?? 380) * (0.4 + R() * 0.8);
        const k = E.outCubic(dt / life);
        const px = x + Math.cos(ang) * sp * k, py = y + Math.sin(ang) * sp * k - (opts.rise ?? 40) * k;
        const a = (1 - dt / life) * (0.6 + 0.4 * Math.sin(dt * 30 + i));
        if (opts.hearts && i % 3 === 0) this.heart(px, py, (opts.size ?? 16) * 1.6, a, opts.heartColor, (R() - .5) * .6);
        else this.star(px, py, (opts.size ?? 16) * (0.5 + R()), a, opts.color);
      }
    }
  };

  // destello de luz (light leak) controlado por tiempo
  P.leak = function (e, t, a, color1 = 'rgba(255,190,120,0.55)', color2 = 'rgba(214,120,160,0.35)') {
    const x = 30 + 40 * Math.sin(t * 0.7), y = 30 + 30 * Math.cos(t * 0.5);
    e.style.background = `radial-gradient(ellipse 60% 40% at ${x}% ${y}%, ${color1}, transparent 70%),` +
      `radial-gradient(ellipse 50% 50% at ${100 - x}% ${80 - y * 0.5}%, ${color2}, transparent 70%)`;
    e.style.opacity = a;
  };

  // icono de chat (WhatsApp genérico dibujado a mano)
  P.chatIcon = (color = '#fff') => `<svg viewBox="0 0 64 64"><path d="M32 5C17.1 5 5 16.6 5 31c0 5 1.5 9.7 4.1 13.7L6 58l13.8-3.5C23.4 56.4 27.6 57 32 57c14.9 0 27-11.6 27-26S46.9 5 32 5z" fill="none" stroke="${color}" stroke-width="4.5" stroke-linejoin="round"/><path d="M24.2 19.5c-.7-1.6-1.4-1.6-2.1-1.6h-1.8c-.6 0-1.6.2-2.5 1.2s-3.2 3.1-3.2 7.6 3.3 8.8 3.7 9.4c.5.6 6.4 10.2 15.8 13.9 7.8 3.1 9.4 2.5 11.1 2.3 1.7-.2 5.5-2.2 6.2-4.4.8-2.2.8-4 .5-4.4-.2-.4-.8-.6-1.8-1.1s-5.5-2.7-6.4-3c-.9-.3-1.5-.5-2.1.5-.6.9-2.4 3-3 3.6-.5.6-1.1.7-2 .2-.9-.5-3.9-1.4-7.4-4.6-2.7-2.4-4.6-5.4-5.1-6.3-.5-.9-.1-1.4.4-1.9.4-.4.9-1.1 1.4-1.6.5-.5.6-.9.9-1.5.3-.6.2-1.1-.1-1.6-.2-.5-2-5-2.8-6.8z" fill="${color}"/></svg>`;

  window.P = P;
})();
