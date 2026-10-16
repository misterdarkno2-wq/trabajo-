// Ilustraciones botanicas en linea (SVG) generadas por codigo, animables trazo a trazo.
// Cada lamina mide 600x760. Cada trazo lleva data-o (0..1) = orden de dibujo.
(function () {
  const B = {};
  const R = (seed) => P.rng(seed);
  const f = n => n.toFixed(1);

  // Catmull-Rom -> Bezier
  B.cr = function (pts, closed = false, tension = 0.5) {
    if (pts.length < 2) return '';
    const p = closed ? [pts[pts.length - 1], ...pts, pts[0], pts[1]] : [pts[0], ...pts, pts[pts.length - 1]];
    let d = `M${f(p[1][0])} ${f(p[1][1])}`;
    for (let i = 1; i < p.length - 2; i++) {
      const p0 = p[i - 1], p1 = p[i], p2 = p[i + 1], p3 = p[i + 2];
      const c1 = [p1[0] + (p2[0] - p0[0]) * tension / 3, p1[1] + (p2[1] - p0[1]) * tension / 3];
      const c2 = [p2[0] - (p3[0] - p1[0]) * tension / 3, p2[1] - (p3[1] - p1[1]) * tension / 3];
      d += ` C${f(c1[0])} ${f(c1[1])} ${f(c2[0])} ${f(c2[1])} ${f(p2[0])} ${f(p2[1])}`;
    }
    return closed ? d + ' Z' : d;
  };
  const rot = (x, y, a) => [x * Math.cos(a) - y * Math.sin(a), x * Math.sin(a) + y * Math.cos(a)];
  const deg = a => a * Math.PI / 180;
  // transforma puntos locales (u a lo largo, v ancho) a globales
  const tf = (pts, x, y, ang) => pts.map(([u, v]) => { const [a, b] = rot(u, v, ang); return [x + a, y + b]; });

  B.path = (d, o, w = 2.6, cls = '') => `<path class="bt ${cls}" d="${d}" pathLength="1" data-o="${o.toFixed(3)}" stroke-width="${w}"/>`;
  B.circle = (cx, cy, r, o, w = 2.2, cls = '') => B.path(`M${f(cx + r)} ${f(cy)} A${r} ${r} 0 1 1 ${f(cx - r)} ${f(cy)} A${r} ${r} 0 1 1 ${f(cx + r)} ${f(cy)}`, o, w, cls);

  // hoja: base (x,y), angulo (grados), largo L, ancho W
  B.leaf = function (x, y, a, L, W, o, opt = {}) {
    const n = 22, ang = deg(a), rnd = R(opt.seed || 7);
    const shape = opt.shape || 'ovate';
    const half = u => {
      const s = u / L;
      if (shape === 'lance') return W / 2 * Math.pow(Math.sin(Math.PI * Math.min(1, s * 1.0)), 0.9) * (1 - 0.25 * s);
      if (shape === 'round') return W / 2 * Math.pow(Math.sin(Math.PI * s), 0.62);
      if (shape === 'obovate') return W / 2 * Math.pow(Math.sin(Math.PI * Math.pow(s, 0.7)), 0.8);
      return W / 2 * Math.pow(Math.sin(Math.PI * s), 0.8) * (1 - 0.15 * s);
    };
    const side = sgn => {
      const pts = [];
      for (let i = 0; i <= n; i++) {
        const u = L * i / n;
        let v = half(u);
        if (opt.serrate && i > 1 && i < n - 1) v *= (i % 2 ? 1.07 : 0.95);
        if (opt.crenate && i > 0 && i < n) v *= 1 + 0.06 * Math.sin(i * 2.2);
        v += (rnd() - .5) * 1.2;
        pts.push([u, sgn * v]);
      }
      return pts;
    };
    const left = side(-1), right = side(1).reverse();
    const outline = tf([...left, ...right.slice(1)], x, y, ang);
    let out = B.path(B.cr(outline, false), o, opt.w || 2.4);
    // nervio central
    const mid = tf([[0, 0], [L * 0.5, (opt.curl || 0) * L * 0.04], [L * 0.94, 0]], x, y, ang);
    out += B.path(B.cr(mid), o + 0.04, 1.6, 'fino');
    // nervaduras
    const nv = opt.veins ?? 5;
    for (let k = 1; k <= nv; k++) {
      const u = L * (0.12 + 0.72 * k / (nv + 1));
      for (const s of [-1, 1]) {
        const v = half(u + L * 0.12) * 0.8;
        const pts = tf([[u, 0], [u + L * 0.07, s * v * 0.55], [u + L * 0.13, s * v]], x, y, ang);
        out += B.path(B.cr(pts), o + 0.06 + k * 0.01, 1.2, 'fino');
      }
    }
    return out;
  };

  // petalo: desde el centro (cx,cy) en angulo a
  B.petal = function (cx, cy, a, r0, L, W, o, opt = {}) {
    const ang = deg(a), rnd = R(opt.seed || 3);
    const pts = [];
    const w0 = opt.w0 ?? W * 0.12;
    pts.push([r0, -w0]);
    pts.push([r0 + L * 0.35, -W * 0.36]);
    pts.push([r0 + L * 0.68, -W * 0.5]);
    const tipN = 9;
    for (let i = 0; i <= tipN; i++) {
      const th = -Math.PI / 2 + Math.PI * i / tipN;
      let rr = 1 + (opt.wavy ? (rnd() - 0.5) * opt.wavy : 0);
      if (opt.notch && Math.abs(i - tipN / 2) < 0.6) rr *= 0.9;
      pts.push([r0 + L * 0.72 + Math.cos(th) * L * 0.28 * rr, Math.sin(th) * W * 0.5 * (0.98 + (opt.wavy ? (rnd() - .5) * opt.wavy * .5 : 0))]);
    }
    pts.push([r0 + L * 0.68, W * 0.5]);
    pts.push([r0 + L * 0.35, W * 0.36]);
    pts.push([r0, w0]);
    let out = B.path(B.cr(tf(pts, cx, cy, ang)), o, opt.w || 2.5);
    if (opt.lines) {
      for (let k = -1; k <= 1; k++) {
        const l = tf([[r0 + L * 0.08, k * W * 0.05], [r0 + L * 0.45, k * W * 0.16], [r0 + L * (0.7 - Math.abs(k) * 0.1), k * W * 0.24]], cx, cy, ang);
        out += B.path(B.cr(l), o + 0.08, 1.1, 'fino');
      }
    }
    return out;
  };

  B.stamens = function (cx, cy, n, r0, r1, o, seed = 5, anther = 3.2) {
    const rnd = R(seed);
    let out = '';
    for (let i = 0; i < n; i++) {
      const a = Math.PI * 2 * i / n + rnd() * 0.3;
      const rr = r1 * (0.75 + rnd() * 0.35);
      const bend = (rnd() - .5) * 0.25;
      const p = [[cx + Math.cos(a) * r0, cy + Math.sin(a) * r0],
                 [cx + Math.cos(a + bend) * (r0 + rr) * 0.55, cy + Math.sin(a + bend) * (r0 + rr) * 0.55],
                 [cx + Math.cos(a) * rr, cy + Math.sin(a) * rr]];
      out += B.path(B.cr(p), o + i * 0.004, 1.2, 'fino');
      out += B.circle(p[2][0], p[2][1], anther, o + 0.05 + i * 0.004, 1.4);
    }
    return out;
  };

  B.flower5 = function (cx, cy, rot0, L, W, o, opt = {}) {
    let out = '';
    const n = opt.n || 5;
    for (let i = 0; i < n; i++) out += B.petal(cx, cy, rot0 + i * 360 / n, opt.r0 ?? 6, L, W, o + i * 0.02, Object.assign({ seed: 11 + i }, opt));
    if (opt.stamens !== false) out += B.stamens(cx, cy, opt.ns || 16, opt.sr0 ?? 6, opt.sr1 ?? L * 0.45, o + 0.12, opt.seed || 9, opt.anther ?? 3);
    out += B.circle(cx, cy, opt.center ?? 5, o + 0.1, 2);
    return out;
  };

  B.bud = function (x, y, a, L, W, o) {
    const ang = deg(a);
    const body = tf([[0, -W * 0.2], [L * 0.4, -W * 0.5], [L * 0.85, -W * 0.3], [L, 0], [L * 0.85, W * 0.3], [L * 0.4, W * 0.5], [0, W * 0.2]], x, y, ang);
    let out = B.path(B.cr(body), o, 2.2);
    const sep = tf([[0, 0], [L * 0.35, -W * 0.55], [L * 0.55, -W * 0.25]], x, y, ang);
    const sep2 = tf([[0, 0], [L * 0.35, W * 0.55], [L * 0.55, W * 0.25]], x, y, ang);
    out += B.path(B.cr(sep), o + 0.04, 1.6, 'fino') + B.path(B.cr(sep2), o + 0.04, 1.6, 'fino');
    return out;
  };

  // ---------------- laminas ----------------
  B.rockRose = function () {
    let s = '';
    s += B.path(B.cr([[300, 374], [296, 440], [304, 520], [292, 640], [298, 745]]), 0.0, 3);
    s += B.path(B.cr([[298, 540], [340, 500], [395, 455], [430, 405]]), 0.06, 2.4);
    s += B.bud(430, 405, -60, 70, 34, 0.12);
    s += B.leaf(300, 455, -150, 125, 34, 0.1, { shape: 'lance', seed: 21, veins: 3 });
    s += B.leaf(300, 455, -32, 118, 32, 0.12, { shape: 'lance', seed: 22, veins: 3 });
    s += B.leaf(297, 600, -160, 105, 30, 0.16, { shape: 'lance', seed: 23, veins: 3 });
    s += B.leaf(297, 600, -18, 110, 30, 0.18, { shape: 'lance', seed: 24, veins: 3 });
    s += B.flower5(300, 245, -90, 150, 158, 0.3, { wavy: 0.14, lines: true, ns: 26, sr1: 60, r0: 10, center: 8, seed: 31 });
    return s;
  };

  B.mimulus = function () {
    let s = '';
    s += B.path(B.cr([[300, 410], [306, 470], [296, 540], [303, 650], [298, 745]]), 0.0, 3);
    // flor frontal: labio superior (2) e inferior (3)
    const cx = 300, cy = 250;
    s += B.petal(cx, cy, -122, 28, 92, 96, 0.22, { wavy: 0.08, seed: 41 });
    s += B.petal(cx, cy, -58, 28, 92, 96, 0.24, { wavy: 0.08, seed: 42 });
    s += B.petal(cx, cy, 168, 30, 112, 108, 0.27, { wavy: 0.1, seed: 43, lines: true });
    s += B.petal(cx, cy, 12, 30, 112, 108, 0.29, { wavy: 0.1, seed: 44, lines: true });
    s += B.petal(cx, cy, 90, 32, 130, 124, 0.31, { wavy: 0.1, seed: 45, lines: true, notch: true });
    s += B.path(B.cr([[cx - 34, cy + 2], [cx - 20, cy - 20], [cx, cy - 26], [cx + 20, cy - 20], [cx + 34, cy + 2], [cx + 18, cy + 24], [cx, cy + 28], [cx - 18, cy + 24]], true), 0.33, 2.2);
    // manchitas (guttatus)
    const rnd = R(77);
    for (let i = 0; i < 14; i++) {
      const a = deg(30 + rnd() * 120), r = 50 + rnd() * 70;
      s += B.circle(cx + Math.cos(a) * r, cy + Math.sin(a) * r, 2.5 + rnd() * 3.5, 0.5 + i * 0.01, 1.4);
    }
    // tallito lateral con boton
    s += B.path(B.cr([[302, 545], [360, 500], [420, 430], [450, 380]]), 0.08, 2.2);
    s += B.bud(450, 380, -65, 74, 34, 0.36);
    // hojas dentadas opuestas
    s += B.leaf(300, 470, -165, 120, 78, 0.12, { serrate: true, seed: 51, veins: 4 });
    s += B.leaf(300, 470, -15, 120, 78, 0.14, { serrate: true, seed: 52, veins: 4 });
    s += B.leaf(300, 620, -150, 105, 66, 0.18, { serrate: true, seed: 53, veins: 4 });
    s += B.leaf(300, 620, -30, 105, 66, 0.2, { serrate: true, seed: 54, veins: 4 });
    return s;
  };

  B.cherryPlum = function () {
    let s = '';
    s += B.path(B.cr([[90, 745], [150, 640], [215, 545], [300, 430], [380, 320], [455, 215], [520, 120]]), 0.0, 4);
    s += B.path(B.cr([[215, 545], [170, 490], [140, 430]]), 0.05, 2.6);
    s += B.path(B.cr([[380, 320], [440, 300], [500, 300]]), 0.07, 2.6);
    s += B.path(B.cr([[300, 430], [350, 455], [400, 470]]), 0.06, 2.4);
    const blossom = (x, y, r, o, seed, rot0) => B.flower5(x, y, rot0, r, r * 1.05, o, { r0: 4, wavy: 0.05, notch: true, ns: 16, sr1: r * 0.75, center: 4, seed, anther: 2.6 });
    s += blossom(140, 410, 54, 0.25, 61, -80);
    s += blossom(305, 400, 62, 0.32, 62, -100);
    s += blossom(470, 195, 56, 0.4, 63, -60);
    s += blossom(410, 475, 46, 0.46, 64, -30);
    s += B.bud(500, 300, -20, 34, 26, 0.5);
    s += B.bud(520, 120, -50, 36, 26, 0.52);
    s += B.bud(215, 545, 160, 30, 22, 0.5);
    s += B.leaf(380, 320, -150, 70, 30, 0.2, { seed: 65, veins: 3 });
    s += B.leaf(215, 545, 30, 66, 28, 0.22, { seed: 66, veins: 3 });
    s += B.leaf(455, 215, 160, 60, 26, 0.24, { seed: 67, veins: 3 });
    return s;
  };

  B.aspen = function () {
    let s = '';
    s += B.path(B.cr([[300, 745], [292, 640], [304, 520], [296, 400], [306, 270], [300, 150]]), 0.0, 3.4);
    s += B.path(B.cr([[302, 470], [360, 430], [420, 410]]), 0.05, 2.4);
    s += B.path(B.cr([[298, 360], [240, 320], [190, 300]]), 0.06, 2.4);
    s += B.path(B.cr([[302, 600], [240, 585], [175, 600]]), 0.07, 2.4);
    const leafP = (x, y, a, L, W, pet, o, seed) => {
      const ang = deg(a);
      const ex = x + Math.cos(ang) * pet, ey = y + Math.sin(ang) * pet;
      return B.path(B.cr([[x, y], [(x + ex) / 2 + 6, (y + ey) / 2 - 4], [ex, ey]]), o, 1.8) +
        B.leaf(ex, ey, a, L, W, o + 0.04, { shape: 'round', crenate: true, seed, veins: 4 });
    };
    s += leafP(420, 410, -20, 120, 112, 40, 0.15, 71);
    s += leafP(190, 300, -170, 112, 104, 38, 0.18, 72);
    s += leafP(175, 600, 175, 108, 100, 36, 0.21, 73);
    s += leafP(302, 520, 20, 100, 94, 46, 0.24, 74);
    s += leafP(300, 150, -80, 96, 90, 34, 0.27, 75);
    // amentos colgantes
    const catkin = (x, y, L, o, seed) => {
      const rnd = R(seed);
      const n = 34, wid = u => 15 * Math.pow(Math.sin(Math.PI * (0.08 + 0.92 * u)), 0.6);
      const sway = u => Math.sin(u * 2.4) * 10 * u;
      let pts = [];
      for (let i = 0; i <= n; i++) { const u = i / n; pts.push([x - wid(u) - (i % 2 ? 3.5 : 0) + sway(u), y + L * u]); }
      for (let i = n; i >= 0; i--) { const u = i / n; pts.push([x + wid(u) + (i % 2 ? 3.5 : 0) + sway(u), y + L * u]); }
      let out = B.path(B.cr(pts), o, 1.8);
      for (let i = 3; i < n - 2; i += 2) {
        const u = i / n, cx = x + sway(u), cy = y + L * u, w = wid(u) * 0.7;
        out += B.path(`M${f(cx - w)} ${f(cy - 3)} L${f(cx)} ${f(cy + 4)} L${f(cx + w)} ${f(cy - 3)}`, o + 0.04 + i * 0.004, 1.0, 'fino');
      }
      return out;
    };
    s += B.path(B.cr([[306, 270], [350, 255], [372, 262]]), 0.3, 2);
    s += catkin(372, 262, 170, 0.34, 81);
    s += B.path(B.cr([[296, 400], [262, 420], [250, 440]]), 0.38, 2);
    s += catkin(250, 440, 140, 0.42, 82);
    return s;
  };

  B.redChestnut = function () {
    let s = '';
    s += B.path(B.cr([[300, 745], [303, 650], [298, 560], [300, 480]]), 0.0, 3.4);
    // eje de la panicula (vela)
    s += B.path(B.cr([[300, 480], [301, 360], [299, 230], [300, 95]]), 0.08, 2.2);
    // floretes en cono
    const rnd = R(91);
    let k = 0, row = 0;
    for (let y = 445; y >= 108; y -= 25, row++) {
      const w = 100 * Math.pow((y - 92) / 353, 0.8);
      const cnt = Math.max(1, Math.round(2 * w / 31));
      for (let i = 0; i < cnt; i++) {
        const side = cnt === 1 ? 0 : (i / (cnt - 1)) * 2 - 1;
        const x = 300 + side * w + (row % 2 ? 7 : -7) + (rnd() - .5) * 6;
        const yy = y + (rnd() - .5) * 8;
        const r = 12 + rnd() * 5;
        if (Math.abs(x - 300) > 20) s += B.path(B.cr([[300 + (x - 300) * 0.45, yy + 7], [x, yy]]), 0.15 + k * 0.004, 1.0, 'fino');
        s += B.flower5(x, yy, -90 + rnd() * 70, r, r * 1.05, 0.18 + k * 0.006, { n: 4, r0: 2, ns: 4, sr1: r * 1.3, center: 2, seed: 100 + k, anther: 1.6, w: 1.6, wavy: 0.12 });
        k++;
      }
    }
    // hojas palmeadas
    const palm = (x, y, dir, o, seed) => {
      let out = B.path(B.cr([[300, 600], [300 + dir * 50, 590], [x, y]]), o, 2.2);
      const angs = [-70, -35, 0, 35, 70];
      angs.forEach((a, i) => {
        const L = 165 - Math.abs(a) * 0.7;
        out += B.leaf(x, y, (dir > 0 ? -15 : 195) + a * (dir > 0 ? 1 : -1), L, L * 0.34, o + 0.05 + i * 0.02, { shape: 'obovate', serrate: true, seed: seed + i, veins: 4 });
      });
      return out;
    };
    s += palm(390, 610, 1, 0.1, 120);
    s += palm(210, 610, -1, 0.12, 130);
    return s;
  };

  // monta una lamina en un contenedor y devuelve el controlador de dibujo
  B.mount = function (parent, name, opts = {}) {
    const NS = 'http://www.w3.org/2000/svg';
    const svg = document.createElementNS(NS, 'svg');
    svg.setAttribute('viewBox', '0 0 600 760');
    svg.innerHTML = `<g fill="none" stroke="${opts.color || '#E3C58E'}" stroke-linecap="round" stroke-linejoin="round">${B[name]()}</g>`;
    parent.appendChild(svg);
    const paths = [...svg.querySelectorAll('.bt')].map(p => ({ el: p, o: parseFloat(p.dataset.o) }));
    paths.forEach(p => { p.el.style.strokeDasharray = '1 1'; p.el.style.strokeDashoffset = '1'; });
    return {
      svg, paths,
      // dibuja entre t0 y t0+span; cada trazo tarda 'each'
      draw(t, t0, span = 1.8, each = 0.55) {
        for (const p of paths) {
          const a = t0 + p.o * span;
          const k = P.ease(t, a, a + each, 'inOutSine');
          p.el.style.strokeDashoffset = (1 - k).toFixed(4);
        }
      },
    };
  };

  window.B = B;
})();
