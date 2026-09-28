/* ほしのおとしもの — 60秒 2Dアニメーション
 * すべての絵を Canvas 2D で時刻 t の純粋関数として描画する（素材画像なし）。
 * ブラウザでのリアルタイム再生と、フレーム書き出し（MP4化）の両方で同じコードを使う。
 */
(function (global) {
  'use strict';

  const W = 1280, H = 720, FPS = 30, DUR = 60;
  const FONT = '"Zen Maru Gothic","IPAPGothic","Hiragino Maru Gothic ProN","Hiragino Sans",sans-serif';

  // ---------- 汎用 ----------
  function mulberry32(a) {
    return function () {
      a |= 0; a = a + 0x6D2B79F5 | 0;
      let t = Math.imul(a ^ a >>> 15, 1 | a);
      t = t + Math.imul(t ^ t >>> 7, 61 | t) ^ t;
      return ((t ^ t >>> 14) >>> 0) / 4294967296;
    };
  }
  const clamp = (v, a = 0, b = 1) => Math.max(a, Math.min(b, v));
  const lerp = (a, b, k) => a + (b - a) * k;
  const inv = (a, b, v) => clamp((v - a) / (b - a));
  const ss = (a, b, v) => { const x = inv(a, b, v); return x * x * (3 - 2 * x); };
  const easeOut = x => 1 - Math.pow(1 - x, 3);
  const easeIn = x => x * x * x;
  const easeInOut = x => x < .5 ? 4 * x * x * x : 1 - Math.pow(-2 * x + 2, 3) / 2;
  const TAU = Math.PI * 2;

  function hex(c) { const n = parseInt(c.slice(1), 16); return [n >> 16 & 255, n >> 8 & 255, n & 255]; }
  function mix(c1, c2, k) {
    const a = hex(c1), b = hex(c2);
    return `rgb(${Math.round(lerp(a[0], b[0], k))},${Math.round(lerp(a[1], b[1], k))},${Math.round(lerp(a[2], b[2], k))})`;
  }
  function qbez(p0, p1, p2, u) {
    const a = (1 - u) * (1 - u), b = 2 * (1 - u) * u, c = u * u;
    return { x: a * p0.x + b * p1.x + c * p2.x, y: a * p0.y + b * p1.y + c * p2.y };
  }

  // ---------- 台詞 ----------
  const LINES = [
    { id: 'L01', who: 'poko', t: 1.0, end: 4.3, text: '今夜は、星がいっぱいだなあ。' },
    { id: 'L02', who: 'poko', t: 5.2, end: 8.4, text: 'あっ、流れ星！　……え、こっちに来る！？' },
    { id: 'L03', who: 'kira', t: 10.0, end: 13.3, text: 'いたたた……。どうしよう、空に帰れない……。' },
    { id: 'L04', who: 'poko', t: 13.6, end: 16.3, text: 'だいじょうぶ？　ぼく、ポコ。きみは？' },
    { id: 'L05', who: 'kira', t: 16.6, end: 21.8, text: 'キラ。夜明けまでに戻らないと、わたし、消えちゃうの。' },
    { id: 'L06', who: 'poko', t: 22.2, end: 25.0, text: 'まかせて！　ロケットジャンプ！' },
    { id: 'L07', who: 'kira', t: 27.3, end: 29.8, text: '……やっぱり、無理だよ。' },
    { id: 'L08', who: 'poko', t: 30.0, end: 32.8, text: 'ううん、ぜったい、あきらめない！' },
    { id: 'L09', who: 'poko', t: 33.4, end: 37.5, text: '町のみんな！　ちからを貸して！' },
    { id: 'L10', who: 'kira', t: 38.3, end: 42.3, text: 'わあ……町の光が、道になっていく……！' },
    { id: 'L11', who: 'poko', t: 43.0, end: 46.5, text: 'いくよ、キラ！　いっけええ！' },
    { id: 'L12', who: 'kira', t: 48.3, end: 52.2, text: 'ありがとう、ポコ。ずっと、空から見てるね。' },
    { id: 'L13', who: 'poko', t: 52.5, end: 54.9, text: 'うん！　またね、キラ！' },
  ];
  const NAMES = { poko: 'ポコ', kira: 'キラ' };
  const NAME_COL = { poko: '#7fe7ff', kira: '#ffd66b' };
  const LS = () => global.LIPSYNC || {};

  function lineDur(L) { const l = LS()[L.id]; return l ? l.dur : (L.end - L.t - 0.3); }
  function lineAt(who, t) {
    for (const L of LINES) if (L.who === who && t >= L.t && t < L.t + lineDur(L)) return L;
    return null;
  }
  function mouthOf(who, t) {
    const L = lineAt(who, t);
    if (!L) return 0;
    const l = LS()[L.id];
    if (l && l.env && l.env.length) {
      const x = (t - L.t) * 30, i = Math.floor(x), f = x - i, n = l.env.length - 1;
      return clamp(lerp(l.env[Math.min(i, n)] || 0, l.env[Math.min(i + 1, n)] || 0, f));
    }
    const x = t - L.t;
    return clamp(0.35 + 0.35 * Math.sin(x * 23) + 0.25 * Math.sin(x * 37 + 1));
  }
  function blinkOpen(t, seed) {
    const p = (t + seed) % 3.4;
    return p < 0.14 ? Math.abs(p - 0.07) / 0.07 : 1;
  }

  // ---------- ワールド ----------
  const hillY = x => 545 + Math.pow((x - 700) / 700, 2) * 120;

  // 光のらせん階段
  const HX = { y0: 550, len: 2350, turns: 3.4, phi: -0.608 };
  function helix(s) {
    const a = TAU * HX.turns * s + HX.phi, A = 140 + 40 * s;
    return { x: 640 + A * Math.sin(a), y: HX.y0 - s * HX.len, z: Math.cos(a) };
  }

  // 星空
  const R = mulberry32(20260928);
  const STARS = [];
  for (let i = 0; i < 820; i++) {
    const big = R() < 0.06;
    STARS.push({ x: -150 + R() * 1580, y: -720 + R() * 1260, r: big ? 1.2 + R() * 1.3 : 0.35 + R() * 0.9,
      ph: R() * TAU, sp: 0.8 + R() * 2.6, big, hue: R() });
  }
  // 背景の星座（遠景の飾り）
  const FIREFLIES = [];
  for (let i = 0; i < 26; i++) FIREFLIES.push({ x: 250 + R() * 900, y: 470 + R() * 130, ph: R() * TAU, sp: 0.3 + R() * 0.6 });
  const GRASS = [];
  for (let i = 0; i < 260; i++) { const x = -250 + i * 7 + R() * 5; GRASS.push({ x, h: 6 + R() * 16, ph: R() * TAU, lean: (R() - .5) * 6 }); }
  const CLOUDS = [];
  for (let i = 0; i < 14; i++) CLOUDS.push({ x: -100 + R() * 1500, y: -300 - R() * 1500, w: 180 + R() * 260, h: 26 + R() * 30, a: 0.10 + R() * 0.16 });

  // 町（視差0.6）
  const BUILDINGS = [], WINDOWS = [];
  {
    let x = 120;
    while (x < 1180) {
      const w = 20 + R() * 34, h = 14 + R() * 46 * (1 - Math.abs(x - 660) / 900);
      const top = 548 - h;
      BUILDINGS.push({ x, w, top, roof: R() < 0.3 ? 1 : 0, shade: R() });
      for (let wy = top + 5; wy < 546; wy += 6) {
        for (let wx = x + 4; wx < x + w - 5; wx += 6) {
          const vis = wy < hillY(wx) - 6;
          if (!vis) continue;
          WINDOWS.push({ x: wx, y: wy, lit: R() < 0.3, tw: R() * TAU });
        }
      }
      x += w + 3 + R() * 14;
    }
  }
  // 灯りの窓 → らせん階段の光の粒
  const ORBS = [];
  {
    const lit = WINDOWS.filter(w => w.lit);
    // ランダム順に階段位置を割り当て
    const idx = lit.map((_, i) => i);
    for (let i = idx.length - 1; i > 0; i--) { const j = Math.floor(R() * (i + 1)); [idx[i], idx[j]] = [idx[j], idx[i]]; }
    const N = lit.length;
    idx.forEach((wi, k) => {
      const s = N > 1 ? k / (N - 1) : 0;
      const win = lit[wi];
      win.orb = { s, td: 34.4 + (k / N) * 4.8, win, target: helix(s), bob: R() * TAU };
      ORBS.push(win.orb);
    });
  }

  // 星座「つばめ」
  const CON_C = { x: 640, y: -2050 }, CON_S = 0.8;
  const CON_P = [[190, -30], [40, 0], [-120, 10], [-250, -50], [-240, 80], [50, -60], [-40, -150], [-170, -210], [60, 50], [10, 140], [-80, 200]]
    .map(p => ({ x: CON_C.x + p[0] * CON_S, y: CON_C.y + p[1] * CON_S }));
  const CON_E = [[1, 0, 0], [1, 2, 0], [1, 5, 0], [1, 8, 0], [2, 3, 1], [2, 4, 1], [5, 6, 1], [8, 9, 1], [6, 7, 2], [9, 10, 2]];
  const GAP = CON_P[1];

  // ---------- 描画ヘルパ ----------
  function glow(ctx, x, y, r, rgb, a) {
    if (a <= 0.001 || r <= 0) return;
    const g = ctx.createRadialGradient(x, y, 0, x, y, r);
    g.addColorStop(0, `rgba(${rgb},${a})`);
    g.addColorStop(0.35, `rgba(${rgb},${a * 0.35})`);
    g.addColorStop(1, `rgba(${rgb},0)`);
    ctx.save(); ctx.globalCompositeOperation = 'lighter'; ctx.fillStyle = g;
    ctx.beginPath(); ctx.arc(x, y, r, 0, TAU); ctx.fill(); ctx.restore();
  }
  function sparkle(ctx, x, y, r, a, rgb = '255,240,200', rot = 0) {
    if (a <= 0.001) return;
    glow(ctx, x, y, r * 2.4, rgb, a * 0.6);
    ctx.save(); ctx.globalCompositeOperation = 'lighter'; ctx.globalAlpha = clamp(a);
    ctx.translate(x, y); ctx.rotate(rot); ctx.fillStyle = '#fff';
    const k = r * 0.14;
    ctx.beginPath(); ctx.moveTo(0, -r * 2);
    ctx.quadraticCurveTo(k, -k, r * 2, 0); ctx.quadraticCurveTo(k, k, 0, r * 2);
    ctx.quadraticCurveTo(-k, k, -r * 2, 0); ctx.quadraticCurveTo(-k, -k, 0, -r * 2);
    ctx.fill(); ctx.restore();
  }
  function starPath(ctx, r, ri, round) {
    const pts = [];
    for (let i = 0; i < 10; i++) {
      const a = -Math.PI / 2 + i * Math.PI / 5, rr = i % 2 ? ri : r;
      pts.push([Math.cos(a) * rr, Math.sin(a) * rr]);
    }
    const mid = (p, q) => [(p[0] + q[0]) / 2, (p[1] + q[1]) / 2];
    ctx.beginPath();
    const m0 = mid(pts[9], pts[0]); ctx.moveTo(m0[0], m0[1]);
    for (let i = 0; i < 10; i++) {
      const p = pts[i], m = mid(p, pts[(i + 1) % 10]);
      ctx.arcTo(p[0], p[1], m[0], m[1], i % 2 ? round * 0.6 : round);
    }
    ctx.closePath();
  }
  function rrect(ctx, x, y, w, h, r) { ctx.beginPath(); ctx.roundRect(x, y, w, h, r); }

  // ---------- キャラクター：ポコ ----------
  function drawPoko(ctx, o) {
    const s = o.s || 0.6, face = o.face || 1, sq = o.sq || 0;
    ctx.save();
    ctx.translate(o.x, o.y);
    ctx.rotate(o.rot || 0);
    ctx.scale(s * face * (1 + sq * 0.22), s * (1 - sq * 0.22));
    const bodyDy = o.sit ? 12 : 0;
    const wp = o.walk || 0;
    const bob = o.walk ? Math.abs(Math.sin(wp)) * -3 : 0;
    ctx.translate(0, bob);

    // ジェットパック
    ctx.fillStyle = '#7f93ad';
    rrect(ctx, -42, -50 + bodyDy, 15, 34, 6); ctx.fill();
    ctx.fillStyle = '#5d6f88'; rrect(ctx, -40, -20 + bodyDy, 11, 6, 2); ctx.fill();
    if (o.jet > 0) {
      const fl = o.jet * (0.8 + 0.35 * Math.sin(o.tt * 60) + 0.15 * Math.sin(o.tt * 97));
      const L = 46 * fl;
      const g = ctx.createLinearGradient(0, -14, 0, -14 + L);
      g.addColorStop(0, 'rgba(255,255,230,1)'); g.addColorStop(0.3, 'rgba(255,200,80,0.95)');
      g.addColorStop(0.7, 'rgba(255,110,40,0.7)'); g.addColorStop(1, 'rgba(255,60,20,0)');
      ctx.save(); ctx.globalCompositeOperation = 'lighter'; ctx.fillStyle = g;
      ctx.beginPath(); ctx.moveTo(-41, -14 + bodyDy); ctx.quadraticCurveTo(-34, -14 + L * 1.1 + bodyDy, -27, -14 + bodyDy); ctx.fill();
      ctx.restore();
      glow(ctx, -34, -4 + bodyDy + L * 0.3, 40 * fl, '255,170,80', 0.55 * o.jet);
    }

    // 足
    ctx.fillStyle = '#93a8c0';
    if (o.sit) {
      rrect(ctx, -6, -14, 26, 11, 5.5); ctx.fill();
      rrect(ctx, 2, -8, 26, 11, 5.5); ctx.fill();
    } else {
      const l1 = o.walk ? -4 * Math.max(0, Math.sin(wp)) : 0, l2 = o.walk ? -4 * Math.max(0, -Math.sin(wp)) : 0;
      rrect(ctx, -17, -15 + l1, 12, 15, 5.5); ctx.fill();
      rrect(ctx, 5, -15 + l2, 12, 15, 5.5); ctx.fill();
    }

    // 体
    const bg = ctx.createLinearGradient(-26, -52, 26, -10);
    bg.addColorStop(0, '#fbfeff'); bg.addColorStop(1, '#aec5dc');
    ctx.fillStyle = bg; rrect(ctx, -26, -54 + bodyDy, 52, 44, 17); ctx.fill();
    ctx.strokeStyle = 'rgba(80,110,150,0.35)'; ctx.lineWidth = 1.5; ctx.stroke();
    // 胸のハート
    const hb = 0.6 + 0.4 * Math.sin((o.tt || 0) * 5);
    glow(ctx, 2, -34 + bodyDy, 16, '255,110,150', 0.5 * hb);
    ctx.fillStyle = '#ff6f98';
    ctx.save(); ctx.translate(2, -34 + bodyDy); ctx.scale(0.9, 0.9);
    ctx.beginPath(); ctx.moveTo(0, 4); ctx.bezierCurveTo(-8, -2, -4, -9, 0, -4); ctx.bezierCurveTo(4, -9, 8, -2, 0, 4); ctx.fill(); ctx.restore();

    // 腕
    const arm = (side, th) => {
      const sx = side * 25, sy = -44 + bodyDy;
      const dx = Math.sin(th) * side, dy = Math.cos(th);
      ctx.strokeStyle = '#c7d8e8'; ctx.lineWidth = 8; ctx.lineCap = 'round';
      ctx.beginPath(); ctx.moveTo(sx, sy); ctx.lineTo(sx + dx * 20, sy + dy * 20); ctx.stroke();
      ctx.fillStyle = '#eef6fc'; ctx.beginPath(); ctx.arc(sx + dx * 23, sy + dy * 23, 6.5, 0, TAU); ctx.fill();
    };
    arm(-1, o.armL || 0.25); arm(1, o.armR || 0.25);

    // 頭
    const hy = bodyDy;
    const hg = ctx.createLinearGradient(-30, -102 + hy, 30, -50 + hy);
    hg.addColorStop(0, '#ffffff'); hg.addColorStop(1, '#b8cde2');
    ctx.fillStyle = hg; rrect(ctx, -31, -104 + hy, 62, 54, 21); ctx.fill();
    ctx.strokeStyle = 'rgba(80,110,150,0.35)'; ctx.lineWidth = 1.5; ctx.stroke();
    // アンテナ
    ctx.strokeStyle = '#8aa0b8'; ctx.lineWidth = 3;
    ctx.beginPath(); ctx.moveTo(0, -104 + hy); ctx.quadraticCurveTo(-3, -114 + hy, 0, -122 + hy); ctx.stroke();
    const ag = o.ant || 0;
    glow(ctx, 0, -125 + hy, 18 + 60 * ag, '255,220,110', 0.35 + 0.65 * ag);
    ctx.fillStyle = ag > 0.2 ? '#fff6c8' : '#ffd24d';
    ctx.beginPath(); ctx.arc(0, -125 + hy, 5.5, 0, TAU); ctx.fill();
    // 顔スクリーン
    const fg = ctx.createLinearGradient(0, -94 + hy, 0, -58 + hy);
    fg.addColorStop(0, '#16304f'); fg.addColorStop(1, '#0b1b30');
    ctx.fillStyle = fg; rrect(ctx, -23, -95 + hy, 46, 38, 13); ctx.fill();
    ctx.fillStyle = 'rgba(255,255,255,0.08)'; rrect(ctx, -19, -92 + hy, 26, 7, 4); ctx.fill();

    // 目・口（スクリーンの発光）
    const ex = 4, ey = -78 + hy + (o.look || 0), op = o.blink === undefined ? 1 : o.blink;
    ctx.save();
    ctx.shadowColor = 'rgba(110,245,255,0.9)'; ctx.shadowBlur = 8;
    ctx.fillStyle = '#7ff6ff'; ctx.strokeStyle = '#7ff6ff'; ctx.lineWidth = 3; ctx.lineCap = 'round';
    const eyes = o.eyes || 'normal';
    for (const side of [-1, 1]) {
      const x = ex + side * 10;
      if (eyes === 'happy') {
        ctx.beginPath(); ctx.moveTo(x - 5, ey + 2); ctx.quadraticCurveTo(x, ey - 6, x + 5, ey + 2); ctx.stroke();
      } else if (eyes === 'dizzy') {
        ctx.lineWidth = 2; ctx.beginPath();
        for (let a = 0; a < 14; a += 0.3) { const rr = a * 0.42; const px = x + Math.cos(a + (o.tt || 0) * 8) * rr, py = ey + Math.sin(a + (o.tt || 0) * 8) * rr; a === 0 ? ctx.moveTo(px, py) : ctx.lineTo(px, py); }
        ctx.stroke(); ctx.lineWidth = 3;
      } else if (eyes === 'surprised') {
        ctx.beginPath(); ctx.arc(x, ey, 6.5, 0, TAU); ctx.lineWidth = 2.5; ctx.stroke();
        ctx.beginPath(); ctx.arc(x, ey, 2.4, 0, TAU); ctx.fill(); ctx.lineWidth = 3;
      } else {
        ctx.beginPath(); ctx.ellipse(x, ey, 4.6, Math.max(0.6, 6.2 * op), 0, 0, TAU); ctx.fill();
        if (eyes === 'sad') {
          ctx.beginPath(); ctx.moveTo(x - 5, ey - 8 - (side < 0 ? 0 : 3)); ctx.lineTo(x + 5, ey - 8 - (side < 0 ? 3 : 0)); ctx.lineWidth = 2; ctx.stroke(); ctx.lineWidth = 3;
        } else if (eyes === 'determined') {
          ctx.beginPath(); ctx.moveTo(x - 5, ey - 8 - (side < 0 ? 3 : 0)); ctx.lineTo(x + 5, ey - 8 - (side < 0 ? 0 : 3)); ctx.lineWidth = 2.4; ctx.stroke(); ctx.lineWidth = 3;
        }
      }
    }
    const m = o.mouth || 0, my = -65 + hy;
    if (m > 0.06) {
      ctx.beginPath(); ctx.ellipse(ex, my, 3.2 + 2.6 * m, 1.1 + 4.4 * m, 0, 0, TAU); ctx.fill();
    } else if (eyes === 'sad') {
      ctx.lineWidth = 2; ctx.beginPath(); ctx.moveTo(ex - 4, my + 1.5); ctx.quadraticCurveTo(ex, my - 2.5, ex + 4, my + 1.5); ctx.stroke();
    } else if (eyes === 'surprised' || eyes === 'dizzy') {
      ctx.beginPath(); ctx.ellipse(ex, my, 2.6, 2.6, 0, 0, TAU); ctx.fill();
    } else {
      ctx.lineWidth = 2; ctx.beginPath(); ctx.moveTo(ex - 5, my - 1); ctx.quadraticCurveTo(ex, my + 4, ex + 5, my - 1); ctx.stroke();
    }
    ctx.restore();
    ctx.fillStyle = 'rgba(255,120,170,0.5)';
    for (const side of [-1, 1]) { ctx.beginPath(); ctx.ellipse(ex + side * 16.5, -67 + hy, 4, 2.4, 0, 0, TAU); ctx.fill(); }

    // めまいの星
    if (o.dizzyStars) {
      for (let k = 0; k < 3; k++) {
        const a = (o.tt || 0) * 5 + k * TAU / 3;
        sparkle(ctx, Math.cos(a) * 30, -118 + hy + Math.sin(a) * 7, 3.5, o.dizzyStars, '255,230,120');
      }
    }
    ctx.restore();
  }

  function shadow(ctx, x, y, w, a) {
    ctx.save(); ctx.fillStyle = `rgba(0,5,15,${a})`;
    ctx.beginPath(); ctx.ellipse(x, y, w, w * 0.2, 0, 0, TAU); ctx.fill(); ctx.restore();
  }

  // ---------- キャラクター：キラ ----------
  function drawKira(ctx, o) {
    const r = o.r || 22;
    const gl = o.glow === undefined ? 1 : o.glow;
    glow(ctx, o.x, o.y, r * 4.2, '255,214,120', 0.45 * gl);
    glow(ctx, o.x, o.y, r * 1.9, '255,245,200', 0.5 * gl);
    ctx.save();
    ctx.translate(o.x, o.y); ctx.rotate(o.rot || 0);
    starPath(ctx, r, r * 0.58, r * 0.22);
    const g = ctx.createRadialGradient(-r * 0.15, -r * 0.2, r * 0.05, 0, 0, r * 1.05);
    g.addColorStop(0, '#fffdf0'); g.addColorStop(0.45, '#ffe680'); g.addColorStop(1, '#ffb43a');
    ctx.fillStyle = g; ctx.fill();
    ctx.lineWidth = r * 0.06; ctx.strokeStyle = 'rgba(255,250,210,0.9)'; ctx.stroke();
    if (r < 9) { ctx.restore(); return; }

    const expr = o.expr || 'neutral';
    const ey = -r * 0.02, exo = r * 0.22, op = o.blink === undefined ? 1 : o.blink;
    ctx.fillStyle = '#4a2f1f'; ctx.strokeStyle = '#4a2f1f'; ctx.lineCap = 'round'; ctx.lineWidth = r * 0.065;
    for (const side of [-1, 1]) {
      const x = side * exo + (o.lookX || 0) * r * 0.06, y = ey + (o.lookY || 0) * r * 0.05;
      const wink = o.wink && side > 0;
      if (expr === 'happy' || wink) {
        ctx.beginPath(); ctx.moveTo(x - r * 0.09, y + r * 0.03); ctx.quadraticCurveTo(x, y - r * 0.1, x + r * 0.09, y + r * 0.03); ctx.stroke();
      } else {
        const big = expr === 'wonder' || expr === 'surprised' ? 1.25 : 1;
        ctx.beginPath(); ctx.ellipse(x, y, r * 0.075 * big, Math.max(r * 0.012, r * 0.105 * big * op), 0, 0, TAU); ctx.fill();
        if (op > 0.5) {
          ctx.fillStyle = '#fff';
          ctx.beginPath(); ctx.arc(x + r * 0.025, y - r * 0.04, r * 0.03 * big, 0, TAU); ctx.fill();
          if (expr === 'wonder') { ctx.beginPath(); ctx.arc(x - r * 0.03, y + r * 0.035, r * 0.016, 0, TAU); ctx.fill(); }
          ctx.fillStyle = '#4a2f1f';
        }
        if (expr === 'sad') {
          ctx.lineWidth = r * 0.04;
          ctx.beginPath(); ctx.moveTo(x - r * 0.09, y - r * (side < 0 ? 0.15 : 0.2)); ctx.lineTo(x + r * 0.09, y - r * (side < 0 ? 0.2 : 0.15)); ctx.stroke();
          ctx.lineWidth = r * 0.065;
        }
      }
    }
    ctx.fillStyle = 'rgba(255,120,140,0.55)';
    for (const side of [-1, 1]) { ctx.beginPath(); ctx.ellipse(side * r * 0.36, r * 0.13, r * 0.09, r * 0.055, 0, 0, TAU); ctx.fill(); }
    const m = o.mouth || 0, my = r * 0.17;
    ctx.fillStyle = '#7a3a2a';
    if (m > 0.06) {
      ctx.beginPath(); ctx.ellipse(0, my + r * 0.02, r * (0.05 + 0.05 * m), r * (0.02 + 0.09 * m), 0, 0, TAU); ctx.fill();
    } else if (expr === 'sad') {
      ctx.lineWidth = r * 0.04; ctx.beginPath(); ctx.moveTo(-r * 0.07, my + r * 0.04); ctx.quadraticCurveTo(0, my - r * 0.04, r * 0.07, my + r * 0.04); ctx.stroke();
    } else if (expr === 'surprised' || expr === 'wonder') {
      ctx.beginPath(); ctx.ellipse(0, my + r * 0.02, r * 0.05, r * 0.06, 0, 0, TAU); ctx.fill();
    } else {
      ctx.lineWidth = r * 0.04; ctx.beginPath(); ctx.moveTo(-r * 0.08, my - r * 0.01); ctx.quadraticCurveTo(0, my + r * 0.08, r * 0.08, my - r * 0.01); ctx.stroke();
    }
    ctx.restore();

    // 涙
    if (o.tears > 0) {
      for (const side of [-1, 1]) {
        for (let k = 0; k < 2; k++) {
          const ph = ((o.tt || 0) * 0.9 + k * 0.5 + (side > 0 ? 0.23 : 0)) % 1;
          const tx = o.x + side * (r * 0.3 + ph * r * 0.25), ty = o.y + ey + r * 0.1 + ph * r * 0.9;
          ctx.save(); ctx.globalAlpha = o.tears * (1 - ph) * 0.9; ctx.fillStyle = '#9fe2ff';
          ctx.beginPath(); ctx.moveTo(tx, ty - r * 0.09); ctx.quadraticCurveTo(tx + r * 0.06, ty + r * 0.02, tx, ty + r * 0.05);
          ctx.quadraticCurveTo(tx - r * 0.06, ty + r * 0.02, tx, ty - r * 0.09); ctx.fill(); ctx.restore();
        }
      }
    }
  }

  function drawTelescope(ctx, x, y, ang, fallen) {
    ctx.save(); ctx.translate(x, y);
    ctx.strokeStyle = '#3c4a66'; ctx.lineWidth = 2.2; ctx.lineCap = 'round';
    if (!fallen) {
      ctx.beginPath(); ctx.moveTo(0, -24); ctx.lineTo(-10, 0); ctx.moveTo(0, -24); ctx.lineTo(10, 0); ctx.moveTo(0, -24); ctx.lineTo(0, 0); ctx.stroke();
      ctx.translate(0, -24); ctx.rotate(ang);
    } else { ctx.translate(0, -4); ctx.rotate(0.12); }
    const g = ctx.createLinearGradient(0, -5, 0, 5); g.addColorStop(0, '#d98a5a'); g.addColorStop(1, '#8f4a2e');
    ctx.fillStyle = g; rrect(ctx, -16, -4, 34, 8, 3); ctx.fill();
    ctx.fillStyle = '#e8b48e'; rrect(ctx, 16, -5.5, 6, 11, 2); ctx.fill();
    ctx.restore();
  }

  // ---------- 状態（時刻 → カメラ・キャラ） ----------
  function charPos(t) {
    const s = 0.97 * Math.pow(inv(40, 47, t), 1.5);
    const P = helix(s), Q = helix(Math.min(1, s + 0.002));
    return { s, x: P.x, y: P.y, z: P.z, dir: Q.x >= P.x ? 1 : -1 };
  }

  function pokoHeightS3(t) {
    if (t < 23) return 0;
    if (t < 24.5) return 260 * easeOut(inv(23, 24.5, t));
    if (t < 25.2) return 260 - 25 * inv(24.5, 25.2, t) + 6 * Math.sin(t * 40);
    if (t < 26) return 235 * (1 - easeIn(inv(25.2, 26, t)));
    return 0;
  }

  function camAt(t) {
    if (t < 9) { const k = easeInOut(inv(0, 8.5, t)); return { x: lerp(660, 645, k), y: lerp(400, 415, k), z: lerp(1.15, 1.28, k) }; }
    if (t < 22) return { x: 650, y: 470, z: 1.9 + 0.05 * inv(9, 22, t) };
    if (t < 33) { const k = easeInOut(inv(22, 23.2, t)); const h = pokoHeightS3(t); return { x: lerp(650, 660, k), y: lerp(470, 440, k) - h * 0.25, z: lerp(1.95, 1.3, k) }; }
    if (t < 40) { const k = easeInOut(inv(33, 34.4, t)); return { x: lerp(660, 640, k), y: lerp(440, 360, k), z: lerp(1.3, 1.0, k) }; }
    if (t < 47) {
      const P = charPos(t), k = ss(40, 42, t);
      return { x: lerp(640, lerp(640, P.x, 0.35), k), y: lerp(360, P.y - 30, k), z: lerp(1.0, 1.3, ss(40, 41.5, t)) };
    }
    if (t < 55) { const a = camAt(46.999), k = easeInOut(inv(47, 48.4, t)); return { x: lerp(a.x, 640, k), y: lerp(a.y, -1945, k), z: lerp(a.z, 1.06, k) }; }
    const k = inv(55, 60, t);
    return { x: 640, y: lerp(395, 380, k), z: lerp(1.14, 1.1, k) };
  }

  function layer(ctx, cam, p, fn) {
    ctx.save();
    const z = 1 + (cam.z - 1) * p;
    ctx.translate(W / 2 + (cam.sx || 0) * p, H / 2 + (cam.sy || 0) * p);
    ctx.scale(z, z);
    ctx.translate(-(640 + (cam.x - 640) * p), -(360 + (cam.y - 360) * p));
    fn(z);
    ctx.restore();
  }

  // ---------- 天の川（事前描画） ----------
  let MILKY = null;
  function milky() {
    if (MILKY) return MILKY;
    const c = document.createElement('canvas'); c.width = 1600; c.height = 1100;
    const x = c.getContext('2d'), r = mulberry32(7);
    x.translate(800, 550); x.rotate(-0.42);
    for (let i = 0; i < 70; i++) {
      const px = (r() - .5) * 1800, py = (r() - .5) * 170 * (1 - Math.abs(px) / 1200), rad = 60 + r() * 140;
      const g = x.createRadialGradient(px, py, 0, px, py, rad);
      const col = r() < .5 ? '150,120,255' : '110,170,255';
      g.addColorStop(0, `rgba(${col},0.07)`); g.addColorStop(1, `rgba(${col},0)`);
      x.fillStyle = g; x.beginPath(); x.arc(px, py, rad, 0, TAU); x.fill();
    }
    for (let i = 0; i < 5000; i++) {
      const px = (r() - .5) * 1900, gy = (r() + r() + r() - 1.5) * 110;
      x.fillStyle = `rgba(255,255,255,${0.15 + r() * 0.5})`;
      x.fillRect(px, gy, r() < .9 ? 1 : 1.6, r() < .9 ? 1 : 1.6);
    }
    MILKY = c; return c;
  }

  // ---------- メイン描画 ----------
  function render(ctx, t, scale = 1) {
    t = clamp(t, 0, DUR - 1e-6);
    ctx.save();
    ctx.setTransform(scale, 0, 0, scale, 0, 0);
    ctx.imageSmoothingEnabled = true;

    const cam = Object.assign({}, camAt(t));
    // 画面の揺れ
    let shake = 0;
    if (t > 8.5 && t < 9.6) shake = 9 * (1 - inv(8.5, 9.6, t));
    if (t > 26 && t < 26.4) shake = 5 * (1 - inv(26, 26.4, t));
    if (t > 48 && t < 48.5) shake = 3 * (1 - inv(48, 48.5, t));
    cam.sx = shake * Math.sin(t * 91); cam.sy = shake * Math.cos(t * 73);

    const dawn = t >= 55 ? 1 : 0;
    const alt = clamp((360 - cam.y) / 2300);

    // --- 空 ---
    const sky = ctx.createLinearGradient(0, 0, 0, H);
    if (dawn) {
      sky.addColorStop(0, '#223a7a'); sky.addColorStop(0.45, '#7a6cb2'); sky.addColorStop(0.72, '#f0a2a4'); sky.addColorStop(0.9, '#ffd29a');
    } else {
      sky.addColorStop(0, mix('#070b26', '#03041a', alt));
      sky.addColorStop(0.55, mix('#16204f', '#120c3a', alt));
      sky.addColorStop(0.85, mix('#34407a', '#2a1a5e', alt));
      sky.addColorStop(1, mix('#46508a', '#2a1a5e', alt));
    }
    ctx.fillStyle = sky; ctx.fillRect(0, 0, W, H);

    // 天の川・月（視差0.06）
    layer(ctx, cam, 0.06, () => {
      ctx.save(); ctx.globalAlpha = dawn ? 0.08 : 0.9; ctx.drawImage(milky(), -160, -420, 1600, 1100); ctx.restore();
      if (!dawn) {
        glow(ctx, 1085, 118, 140, '190,210,255', 0.35);
        ctx.save();
        ctx.beginPath(); ctx.rect(900, -100, 400, 400); ctx.arc(1100, 107, 30, 0, TAU); ctx.clip('evenodd');
        ctx.fillStyle = '#f6f2dc'; ctx.shadowColor = 'rgba(255,250,220,0.8)'; ctx.shadowBlur = 18;
        ctx.beginPath(); ctx.arc(1085, 118, 34, 0, TAU); ctx.fill(); ctx.restore();
      }
    });

    // 星（視差0.2）
    layer(ctx, cam, 0.2, () => {
      const fade = dawn ? 0.18 : 1;
      for (const s of STARS) {
        const tw = 0.55 + 0.45 * Math.sin(t * s.sp + s.ph);
        const a = fade * (s.big ? 0.75 + 0.25 * tw : 0.35 + 0.55 * tw);
        if (s.big) sparkle(ctx, s.x, s.y, s.r * 1.3, a * 0.8, s.hue < .5 ? '200,220,255' : '255,235,200', 0);
        else { ctx.fillStyle = `rgba(255,255,255,${a})`; ctx.fillRect(s.x - s.r, s.y - s.r, s.r * 2, s.r * 2); }
      }
    });

    // 雲（上昇中に通過）
    layer(ctx, cam, 0.85, () => {
      if (dawn) return;
      for (const c of CLOUDS) {
        const x = c.x + Math.sin(t * 0.1 + c.y) * 20;
        const g = ctx.createRadialGradient(x, c.y, 0, x, c.y, c.w);
        g.addColorStop(0, `rgba(150,140,230,${c.a})`); g.addColorStop(1, 'rgba(150,140,230,0)');
        ctx.save(); ctx.fillStyle = g; ctx.translate(x, c.y); ctx.scale(1, c.h / c.w); ctx.translate(-x, -c.y);
        ctx.beginPath(); ctx.arc(x, c.y, c.w, 0, TAU); ctx.fill(); ctx.restore();
      }
    });

    // 山（遠・近）
    const mount = (p, base, amp, f, col) => layer(ctx, cam, p, () => {
      ctx.fillStyle = col; ctx.beginPath(); ctx.moveTo(-600, 1400);
      for (let x = -600; x <= 1900; x += 20) {
        const y = base - amp * (0.55 * Math.sin(x * 0.006 * f + 1) + 0.3 * Math.sin(x * 0.017 * f + 2) + 0.15 * Math.sin(x * 0.043 * f));
        ctx.lineTo(x, y);
      }
      ctx.lineTo(1900, 1400); ctx.closePath(); ctx.fill();
    });
    mount(0.35, 452, 38, 1.0, dawn ? '#6b5f96' : '#1b2552');
    if (dawn) glow(ctx, 330, 520, 520, '255,200,140', 0.45);
    mount(0.5, 488, 26, 1.6, dawn ? '#4c4478' : '#141c43');

    // 町（視差0.5）
    layer(ctx, cam, 0.5, () => {
      if (!dawn) {
        const hz = ctx.createLinearGradient(0, 430, 0, 560);
        hz.addColorStop(0, 'rgba(255,190,110,0)'); hz.addColorStop(1, `rgba(255,190,110,${0.18 * (1 - ss(34.5, 39.5, t))})`);
        ctx.fillStyle = hz; ctx.fillRect(-300, 430, 1900, 140);
      }
      for (const b of BUILDINGS) {
        ctx.fillStyle = dawn ? mix('#3a3564', '#453e6e', b.shade) : mix('#0d1330', '#141b3e', b.shade);
        ctx.fillRect(b.x, b.top, b.w, 700 - b.top);
        if (b.roof) { ctx.beginPath(); ctx.moveTo(b.x - 2, b.top); ctx.lineTo(b.x + b.w / 2, b.top - 9); ctx.lineTo(b.x + b.w + 2, b.top); ctx.fill(); }
      }
      for (const w of WINDOWS) {
        const on = w.lit && !dawn && (!w.orb || t < w.orb.td);
        if (on) {
          const f = 0.85 + 0.15 * Math.sin(t * 2 + w.tw);
          ctx.fillStyle = `rgba(255,214,130,${f})`; ctx.fillRect(w.x, w.y, 2.6, 3.2);
          // 離陸直前にふくらむ
          if (w.orb && t > w.orb.td - 0.5) glow(ctx, w.x + 1.7, w.y + 2, 14, '255,220,140', inv(w.orb.td - 0.5, w.orb.td, t));
        } else {
          ctx.fillStyle = dawn ? 'rgba(90,80,130,0.8)' : 'rgba(40,48,85,0.9)'; ctx.fillRect(w.x, w.y, 2.6, 3.2);
        }
      }
    });

    // --- 前景（視差1） ---
    layer(ctx, cam, 1, (z) => {
      // 星座
      if (t > 40 && !dawn) drawConstellation(ctx, t);

      // 丘
      const hg = ctx.createLinearGradient(0, 520, 0, 760);
      if (dawn) { hg.addColorStop(0, '#2c2a4e'); hg.addColorStop(1, '#141328'); }
      else { hg.addColorStop(0, '#16303a'); hg.addColorStop(1, '#071218'); }
      ctx.fillStyle = hg; ctx.beginPath(); ctx.moveTo(-500, 1500);
      for (let x = -500; x <= 1800; x += 12) ctx.lineTo(x, hillY(x));
      ctx.lineTo(1800, 1500); ctx.closePath(); ctx.fill();
      ctx.strokeStyle = dawn ? 'rgba(255,190,150,0.5)' : 'rgba(150,200,255,0.28)'; ctx.lineWidth = 1.6;
      ctx.beginPath(); for (let x = -500; x <= 1800; x += 12) x === -500 ? ctx.moveTo(x, hillY(x)) : ctx.lineTo(x, hillY(x)); ctx.stroke();
      // 草
      ctx.strokeStyle = dawn ? '#1d1c38' : '#0c1c22'; ctx.lineWidth = 1.6; ctx.lineCap = 'round';
      ctx.beginPath();
      for (const g of GRASS) {
        const by = hillY(g.x) + 3, sw = Math.sin(t * 1.6 + g.ph) * 3 + g.lean;
        ctx.moveTo(g.x, by); ctx.quadraticCurveTo(g.x + sw * 0.3, by - g.h * 0.6, g.x + sw, by - g.h);
      }
      ctx.stroke();

      // クレーター
      if (t > 8.5) {
        ctx.fillStyle = 'rgba(3,8,12,0.75)';
        ctx.beginPath(); ctx.ellipse(560, 553, 44, 8, 0, 0, TAU); ctx.fill();
        if (!dawn) glow(ctx, 560, 552, 70, '255,200,120', 0.25 * (1 - ss(40, 44, t)) + 0.05);
      }

      // ホタル
      if (t < 33) {
        for (const f of FIREFLIES) {
          const x = f.x + Math.sin(t * f.sp + f.ph) * 30, y = f.y - 25 + Math.cos(t * f.sp * 1.3 + f.ph) * 18;
          if (y > hillY(x) - 3) continue;
          const a = 0.5 + 0.5 * Math.sin(t * 3 + f.ph * 3);
          glow(ctx, x, y, 9, '200,255,150', 0.5 * a); ctx.fillStyle = `rgba(230,255,190,${a})`; ctx.fillRect(x - 0.8, y - 0.8, 1.6, 1.6);
        }
      }

      // 光の粒（町の灯り → らせん階段）
      if (t > 34 && !dawn) drawOrbs(ctx, t);

      // 流れ星
      if (t > 4.5 && t < 8.6) drawShootingStar(ctx, t);
      if (t > 8.5 && t < 9.4) {
        const k = inv(8.5, 9.4, t);
        ctx.save(); ctx.strokeStyle = `rgba(255,240,200,${0.8 * (1 - k)})`; ctx.lineWidth = 4 * (1 - k) + 1;
        ctx.beginPath(); ctx.ellipse(560, 548, 30 + 400 * easeOut(k), 8 + 90 * easeOut(k), 0, 0, TAU); ctx.stroke(); ctx.restore();
      }
      // 衝突の火花
      if (t > 8.5 && t < 11) {
        const r = mulberry32(99);
        for (let i = 0; i < 24; i++) {
          const a = -Math.PI * (0.1 + r() * 0.8), v = 60 + r() * 140, dt = t - 8.5;
          const x = 560 + Math.cos(a) * v * dt, y = 545 + Math.sin(a) * v * dt + 90 * dt * dt;
          sparkle(ctx, x, y, 1.6 + r() * 1.5, (1 - inv(8.5, 11, t)) * 0.9);
        }
      }

      drawCharacters(ctx, t);

      // アンテナの波紋
      if (t > 33.6 && t < 39.5) {
        for (let k = 0; k < 7; k++) {
          const t0 = 33.6 + k * 0.8; if (t < t0) continue;
          const u = inv(t0, t0 + 2.2, t); if (u >= 1) continue;
          ctx.save(); ctx.strokeStyle = `rgba(255,225,140,${0.55 * (1 - u)})`; ctx.lineWidth = 2.5 * (1 - u) + 0.5;
          ctx.beginPath(); ctx.arc(700, 545 - 76, 10 + 700 * easeOut(u), 0, TAU); ctx.stroke(); ctx.restore();
        }
      }
    });

    // --- 画面効果 ---
    // 衝突の白フラッシュ
    let white = 0;
    if (t >= 8.5 && t < 8.62) white = inv(8.5, 8.62, t);
    else if (t >= 8.62 && t < 9.0) white = 1;
    else if (t >= 9.0 && t < 9.9) white = 1 - inv(9.0, 9.9, t);
    // 星座 → 夜明けへの光
    if (t >= 54.2 && t < 55) white = Math.max(white, easeIn(inv(54.2, 55, t)));
    if (t >= 55 && t < 56.2) white = Math.max(white, 1 - easeOut(inv(55, 56.2, t)));
    if (t >= 48 && t < 48.6) white = Math.max(white, 0.35 * (1 - inv(48, 48.6, t)));
    if (white > 0) { ctx.fillStyle = `rgba(255,250,235,${white})`; ctx.fillRect(0, 0, W, H); }

    // ビネット
    const vg = ctx.createRadialGradient(W / 2, H / 2, H * 0.35, W / 2, H / 2, H * 0.95);
    vg.addColorStop(0, 'rgba(0,0,10,0)'); vg.addColorStop(1, 'rgba(0,0,15,0.5)');
    ctx.fillStyle = vg; ctx.fillRect(0, 0, W, H);

    drawSubtitles(ctx, t);
    if (t > 56) drawTitle(ctx, t);

    // フェードイン / アウト
    let black = 0;
    if (t < 1.2) black = 1 - easeOut(inv(0, 1.2, t));
    if (t > 59.1) black = inv(59.1, 60, t);
    if (black > 0) { ctx.fillStyle = `rgba(0,0,0,${black})`; ctx.fillRect(0, 0, W, H); }

    ctx.restore();
  }

  function drawShootingStar(ctx, t) {
    const p0 = { x: -80, y: 60 }, p1 = { x: 260, y: 40 }, p2 = { x: 560, y: 540 };
    const pos = u => qbez(p0, p1, p2, Math.pow(u, 1.7));
    const u = inv(4.5, 8.5, t);
    // 尾
    const n = 28;
    for (let i = n; i >= 0; i--) {
      const uu = u - i * 0.012; if (uu < 0) continue;
      const q = pos(uu), k = 1 - i / n;
      glow(ctx, q.x, q.y, 6 + 26 * k * (0.4 + u), '255,220,150', 0.18 * k);
      if (i % 3 === 0) sparkle(ctx, q.x + Math.sin(i * 7) * 6, q.y + Math.cos(i * 5) * 6, 1.2 * k + 0.4, 0.7 * k);
    }
    const q = pos(u);
    const r = 3 + 20 * easeIn(u);
    if (u < 0.55) { glow(ctx, q.x, q.y, 30 + 30 * u, '255,240,200', 0.9); sparkle(ctx, q.x, q.y, 3 + 4 * u, 1); }
    else drawKira(ctx, { x: q.x, y: q.y, r, rot: t * 9, expr: 'surprised', glow: 1, tt: t });
  }

  function drawOrbs(ctx, t) {
    const cs = t > 40 ? charPos(t).s : -1;
    // 帯（リボン）
    const settled = ORBS.filter(o => t > o.td + 1.5).sort((a, b) => a.s - b.s);
    if (settled.length > 1) {
      ctx.save(); ctx.globalCompositeOperation = 'lighter'; ctx.lineCap = 'round';
      for (let i = 1; i < settled.length; i++) {
        const a = settled[i - 1].target, b = settled[i].target;
        if (Math.abs(settled[i].s - settled[i - 1].s) > 0.03) continue;
        const d = (a.z + b.z) / 2;
        ctx.strokeStyle = `rgba(255,210,140,${0.10 + 0.14 * (d + 1) / 2})`; ctx.lineWidth = 2 + 2 * (d + 1) / 2;
        ctx.beginPath(); ctx.moveTo(a.x, a.y); ctx.lineTo(b.x, b.y); ctx.stroke();
      }
      ctx.restore();
    }
    for (const o of ORBS) {
      if (t < o.td) continue;
      const u = inv(o.td, o.td + 1.5, t);
      const org = { x: o.win.x + 1.7, y: o.win.y + 2 }, tg = o.target;
      if (u < 1) {
        const ctl = { x: (org.x + tg.x) / 2 + (org.x - tg.x) * 0.25, y: Math.min(org.y, tg.y) - 140 };
        for (let k = 4; k >= 0; k--) {
          const q = qbez(org, ctl, tg, easeInOut(Math.max(0, u - k * 0.025)));
          glow(ctx, q.x, q.y, 16 - k * 2, '255,215,140', 0.55 * (1 - k / 5));
        }
        const q = qbez(org, ctl, tg, easeInOut(u));
        ctx.fillStyle = '#fff6da'; ctx.beginPath(); ctx.arc(q.x, q.y, 2.6, 0, TAU); ctx.fill();
      } else {
        const d = (tg.z + 1) / 2;
        const near = cs >= 0 ? Math.max(0, 1 - Math.abs(o.s - cs) / 0.03) : 0;
        const y = tg.y + Math.sin(t * 2 + o.bob) * 1.5;
        const land = 1 - inv(o.td + 1.5, o.td + 1.9, t);
        glow(ctx, tg.x, y, 16 + 8 * d + 20 * near + 20 * land, '255,210,130', 0.35 + 0.35 * d + 0.4 * near + 0.4 * land);
        ctx.save(); ctx.fillStyle = `rgba(255,246,220,${0.55 + 0.45 * d})`;
        ctx.beginPath(); ctx.ellipse(tg.x, y, 7 + 5 * d, 2.2 + 1.4 * d, 0, 0, TAU); ctx.fill(); ctx.restore();
      }
    }
  }

  function drawConstellation(ctx, t) {
    const lock = inv(47.9, 48.1, t);
    const on = t >= 48;
    // 線
    if (on) {
      ctx.save(); ctx.globalCompositeOperation = 'lighter'; ctx.lineCap = 'round';
      for (const [a, b, d] of CON_E) {
        const k = easeOut(inv(48 + d * 0.65, 48.9 + d * 0.65, t)); if (k <= 0) continue;
        const A = CON_P[a], B = CON_P[b], ex = lerp(A.x, B.x, k), ey = lerp(A.y, B.y, k);
        ctx.strokeStyle = 'rgba(160,210,255,0.35)'; ctx.lineWidth = 6;
        ctx.beginPath(); ctx.moveTo(A.x, A.y); ctx.lineTo(ex, ey); ctx.stroke();
        ctx.strokeStyle = 'rgba(230,245,255,0.85)'; ctx.lineWidth = 1.6;
        ctx.beginPath(); ctx.moveTo(A.x, A.y); ctx.lineTo(ex, ey); ctx.stroke();
        if (k < 1) sparkle(ctx, ex, ey, 3, 1, '200,230,255');
      }
      ctx.restore();
    }
    CON_P.forEach((p, i) => {
      if (i === 1) return;
      const lit = on ? ss(48 + 0.3, 49.8, t) : 0;
      const tw = 0.7 + 0.3 * Math.sin(t * 3 + i * 1.7);
      sparkle(ctx, p.x, p.y, 3 + 2.5 * lit, (0.45 + 0.55 * lit) * tw, '190,220,255', 0);
    });
    // 欠けた場所
    if (!on) {
      const a = 0.35 + 0.25 * Math.sin(t * 4);
      ctx.save(); ctx.setLineDash([4, 6]); ctx.strokeStyle = `rgba(200,225,255,${a})`; ctx.lineWidth = 1.5;
      ctx.beginPath(); ctx.arc(GAP.x, GAP.y, 30, 0, TAU); ctx.stroke(); ctx.restore();
    }
    if (on) {
      const k = inv(48, 49.2, t);
      ctx.save(); ctx.strokeStyle = `rgba(255,240,200,${0.8 * (1 - k)})`; ctx.lineWidth = 3;
      ctx.beginPath(); ctx.arc(GAP.x, GAP.y, 30 + 260 * easeOut(k), 0, TAU); ctx.stroke(); ctx.restore();
      void lock;
    }
  }

  function drawCharacters(ctx, t) {
    const pk = { s: 0.6, tt: t, blink: blinkOpen(t, 0.3), mouth: mouthOf('poko', t) };
    const kr = { r: 22, tt: t, blink: blinkOpen(t, 1.7), mouth: mouthOf('kira', t) };
    let showKira = t >= 8.5, pokoGround = null, telescope = null;

    if (t < 9) {
      // S1 夜の丘
      Object.assign(pk, { x: 880, y: hillY(880), face: -1, sit: t < 5.5, look: -2, armL: 0.9, armR: 0.3 });
      telescope = { x: 842, y: hillY(842), ang: -2.5 };
      if (t >= 5.2) pk.eyes = 'surprised';
      if (t >= 5.5 && t < 5.8) pk.y -= 10 * Math.sin(Math.PI * inv(5.5, 5.8, t));
      if (t >= 7.3) {
        pk.armL = pk.armR = lerp(0.3, 2.6, ss(7.3, 7.6, t));
        pk.y -= 22 * Math.sin(Math.PI * inv(7.6, 8.1, t));
        pk.x += 25 * ss(7.6, 8.4, t);
        pk.sq = t > 8.1 && t < 8.35 ? 0.3 * Math.sin(Math.PI * inv(8.1, 8.35, t)) : 0;
      }
      pokoGround = hillY(pk.x);
    } else if (t < 22) {
      // S2 出会い
      const wk = easeInOut(inv(10.8, 13.2, t));
      const x = lerp(905, 700, wk);
      Object.assign(pk, { x, y: hillY(x), face: -1, armL: 0.3, armR: 0.3 });
      if (t < 10.4) { pk.eyes = 'dizzy'; pk.rot = 0.12 * Math.sin(t * 6); pk.dizzyStars = 1 - inv(10, 10.4, t); }
      else if (t < 13.4) pk.eyes = 'surprised';
      else if (t < 16.4) { pk.eyes = 'normal'; pk.rot = 0.06 * ss(13.6, 14.2, t); }
      else if (t < 20.0) pk.eyes = 'sad';
      else { pk.eyes = 'determined'; if (t > 21.2) { pk.armR = lerp(0.3, 2.7, ss(21.2, 21.5, t)); } }
      if (t > 10.8 && t < 13.2) pk.walk = (t - 10.8) * 12;
      if (t > 10.4 && t < 10.8) pk.rot = 0.15 * Math.sin((t - 10.4) * 40);
      telescope = { x: 952, y: hillY(952), fallen: true };
      pokoGround = pk.y;
      Object.assign(kr, { x: 560, y: 522 + 3 * Math.sin(t * 2), rot: 0.08 * Math.sin(t * 1.3), glow: lerp(0.35, 1, ss(9.3, 11, t)), lookX: 0 });
      if (t < 13.4) { kr.expr = 'sad'; kr.tears = ss(10, 10.6, t); }
      else if (t < 16.5) { kr.expr = t < 13.9 ? 'surprised' : 'neutral'; kr.lookX = 1; }
      else { kr.expr = 'sad'; kr.lookY = t < 18.5 ? -1.2 : 0; kr.tears = ss(19, 19.6, t); kr.lookX = t < 18.5 ? 0 : 1; }
      if (t > 21.2) { kr.expr = 'surprised'; kr.tears = 0; kr.lookX = 1; }
      if (t > 21.3 && t < 22) sparkle(ctx, 700 - 3, hillY(700) - 80, 4, 1 - inv(21.3, 22, t));
    } else if (t < 33) {
      // S3 ロケットジャンプ
      const h = pokoHeightS3(t);
      const fly = t >= 23 && t < 26;
      const x = 700 + (fly ? 30 * Math.sin((t - 23) * 5) : (t >= 26 ? 19.5 : 0));
      Object.assign(pk, { x, y: hillY(x) - h, face: -1, eyes: 'happy', armL: 0.3, armR: 2.7 });
      if (t < 23) pk.armR = 2.7;
      if (t >= 23 && t < 24.5) { pk.jet = 1; pk.eyes = 'happy'; pk.armL = 1.2; pk.armR = 1.2; pk.rot = 0.12 * Math.sin((t - 23) * 5); }
      if (t >= 24.5 && t < 25.2) { pk.jet = Math.sin(t * 38) > 0.2 ? 0.5 : 0.05; pk.eyes = 'surprised'; pk.armL = pk.armR = 1.6; }
      if (t >= 25.2 && t < 26) { pk.eyes = 'surprised'; pk.rot = (t - 25.2) * 5; pk.armL = pk.armR = 2.8 + 0.3 * Math.sin(t * 30); }
      if (t >= 26 && t < 28.6) {
        pk.eyes = 'dizzy'; pk.dizzyStars = 1 - inv(28.2, 28.6, t);
        pk.sq = t < 26.45 ? 0.9 * Math.sin(Math.PI * inv(26, 26.45, t)) : 0;
        pk.sit = true; pk.armL = pk.armR = 0.9;
      }
      if (t >= 28.6 && t < 30) { pk.eyes = 'sad'; pk.sit = t < 29.4; }
      if (t >= 30) {
        pk.eyes = 'determined'; pk.armL = pk.armR = lerp(0.3, 1.4, ss(30, 30.3, t));
        pk.y -= 16 * Math.sin(Math.PI * inv(30.05, 30.45, t));
      }
      pokoGround = hillY(x);
      // ジェットの煙
      if (t >= 23 && t < 27) {
        const r = mulberry32(5);
        for (let i = 0; i < 40; i++) {
          const t0 = 23 + i * 0.055; if (t < t0 || t0 > 25.2) continue;
          const u = inv(t0, t0 + 1.4, t); if (u >= 1) continue;
          const hx = 700 + 30 * Math.sin((t0 - 23) * 5) + 20, hy = hillY(700) - pokoHeightS3(t0) - 10;
          const sput = t0 > 24.5;
          ctx.save(); ctx.fillStyle = sput ? `rgba(120,120,140,${0.45 * (1 - u)})` : `rgba(210,215,235,${0.35 * (1 - u)})`;
          ctx.beginPath(); ctx.arc(hx + (r() - .5) * 30 * u, hy + 40 * u, 5 + 16 * u, 0, TAU); ctx.fill(); ctx.restore();
        }
      }
      telescope = { x: 952, y: hillY(952), fallen: true };
      Object.assign(kr, { x: 560, y: 522 + 3 * Math.sin(t * 2), rot: 0.08 * Math.sin(t * 1.3), glow: 1 });
      if (t < 23) { kr.expr = 'neutral'; kr.lookX = 1; }
      else if (t < 25.2) { kr.expr = 'wonder'; kr.lookX = 1; kr.lookY = -1.5; }
      else if (t < 26.3) { kr.expr = 'surprised'; kr.lookX = 1; }
      else if (t < 30) { kr.expr = 'sad'; kr.tears = ss(27.2, 27.7, t) * (1 - ss(30, 30.4, t)); kr.glow = 0.75; }
      else { kr.expr = 'surprised'; kr.lookX = 1; kr.glow = lerp(0.75, 1, ss(30, 31, t)); }
    } else if (t < 40) {
      // S4a 町の光
      const wk = easeInOut(inv(39.0, 40.0, t));
      const x = lerp(700, 560, wk);
      Object.assign(pk, { x, y: hillY(x), face: -1, eyes: 'determined', look: -2 });
      const up = ss(33.2, 33.6, t) * (1 - ss(38.8, 39.1, t));
      pk.armL = pk.armR = lerp(0.3, 2.75, up);
      pk.ant = ss(33.3, 33.9, t) * (1 - 0.4 * ss(39, 40, t)) * (0.85 + 0.15 * Math.sin(t * 9));
      if (t > 37.8) pk.eyes = 'happy';
      if (t > 39 && t < 40) pk.walk = (t - 39) * 12;
      pokoGround = pk.y;
      telescope = { x: 952, y: hillY(952), fallen: true };
      const kx = lerp(560, 600, ss(39.2, 40, t)), ky = lerp(522, 500, ss(39.2, 40, t));
      Object.assign(kr, { x: kx, y: ky + 3 * Math.sin(t * 2), rot: 0.08 * Math.sin(t * 1.3), glow: 1 + 0.3 * ss(34, 36, t), expr: t < 34.4 ? 'surprised' : 'wonder', lookY: -1.5, lookX: 1 });
    } else if (t < 47) {
      // S4b 光の階段をのぼる
      const P = charPos(t);
      const hop = Math.abs(Math.sin(t * 9)) * 7 * ss(40, 40.5, t);
      const sc = 0.6 * (1 + 0.08 * P.z);
      Object.assign(pk, { x: P.x, y: P.y - 6 - hop, s: sc, face: P.dir, eyes: t < 43 ? 'happy' : 'determined', armL: 0.9, armR: 2.2, ant: 0.5 });
      if (t > 43) { pk.armR = 2.8; pk.eyes = 'determined'; }
      pk.walk = t * 14;
      Object.assign(kr, { x: P.x - 44 * P.dir, y: P.y - 66 - hop * 0.5 + 3 * Math.sin(t * 5), r: 22 * (1 + 0.08 * P.z), rot: 0.15 * Math.sin(t * 3), glow: 1.2, expr: t < 42.5 ? 'wonder' : 'happy', lookX: P.dir });
      // 足もとのきらめき
      for (let k = 0; k < 6; k++) {
        const ph = (t * 1.6 + k / 6) % 1;
        sparkle(ctx, P.x - P.dir * 30 * ph + Math.sin(k * 9) * 8, P.y + 20 * ph, 2.2 * (1 - ph), 1 - ph);
      }
    } else if (t < 55) {
      // S5 星座
      const P = charPos(47);
      const face = GAP.x >= P.x ? 1 : -1;
      Object.assign(pk, { x: P.x, y: P.y - 6, s: 0.6 * (1 + 0.08 * P.z), face, look: -3, eyes: t < 48 ? 'determined' : (t < 49 ? 'surprised' : 'happy'), armL: 0.5, armR: 0.5, ant: 0.5 });
      if (t >= 52.4) { pk.armR = 2.5 + 0.45 * Math.sin(t * 11); pk.eyes = 'happy'; }
      const u = easeInOut(inv(47.05, 48.0, t));
      const st = { x: P.x - 44 * charPos(46.99).dir, y: P.y - 66 };
      const ctl = { x: (st.x + GAP.x) / 2 - 140, y: st.y - 60 };
      const q = qbez(st, ctl, GAP, u);
      Object.assign(kr, { x: q.x, y: q.y + (t > 48 ? 2 * Math.sin(t * 2) : 0), r: lerp(22, 30, u) * (1 + 0.06 * Math.sin(t * 3) * inv(48, 49, t)), rot: u < 1 ? u * TAU : 0.06 * Math.sin(t * 1.5), glow: 1 + 0.6 * inv(48, 49, t), expr: t < 48 ? 'wonder' : 'happy', lookY: 1 });
      if (lineAt('kira', t)) kr.expr = 'neutral';
      if (t > 51.3 && t < 52.4) kr.expr = 'happy';
    } else {
      // S6 夜明け
      Object.assign(pk, { x: 880, y: hillY(880), face: 1, sit: true, look: -3, eyes: 'happy', armL: 0.4, armR: 0.3 });
      if (t > 57.5) pk.armR = 2.4 + 0.45 * Math.sin((t - 57.5) * 10) * (1 - ss(58.8, 59.3, t));
      telescope = { x: 925, y: hillY(925), ang: -0.7 };
      pokoGround = pk.y;
      showKira = false;
    }

    if (telescope) drawTelescope(ctx, telescope.x, telescope.y, telescope.ang, telescope.fallen);
    if (pokoGround !== null) {
      const h = pokoGround - pk.y;
      shadow(ctx, pk.x, pokoGround, 20 * clamp(1 - h / 400, 0.35, 1), 0.45 * clamp(1 - h / 300, 0.2, 1));
    }
    if (showKira && t >= 9 && t < 40) glow(ctx, kr.x, 548, 90, '255,200,110', 0.25 * (kr.glow || 1));
    drawPoko(ctx, pk);
    if (showKira && t >= 9) drawKira(ctx, kr);
  }

  function drawSubtitles(ctx, t) {
    for (const L of LINES) {
      const d = lineDur(L), a = inv(L.t - 0.12, L.t + 0.05, t) * (1 - inv(L.t + d + 0.15, L.t + d + 0.45, t));
      if (a <= 0) continue;
      ctx.save(); ctx.globalAlpha = a;
      ctx.textAlign = 'center'; ctx.textBaseline = 'alphabetic';
      ctx.font = `700 34px ${FONT}`;
      const y = 668;
      ctx.lineJoin = 'round'; ctx.lineWidth = 8; ctx.strokeStyle = 'rgba(8,10,30,0.85)';
      ctx.strokeText(L.text, W / 2, y);
      ctx.fillStyle = '#ffffff'; ctx.fillText(L.text, W / 2, y);
      const tw = ctx.measureText(L.text).width;
      ctx.font = `700 20px ${FONT}`; ctx.textAlign = 'left';
      const nx = W / 2 - tw / 2, ny = y - 44;
      ctx.lineWidth = 6; ctx.strokeText(NAMES[L.who], nx, ny);
      ctx.fillStyle = NAME_COL[L.who]; ctx.fillText(NAMES[L.who], nx, ny);
      ctx.restore();
    }
  }

  function drawTitle(ctx, t) {
    // 空に残ったキラ
    const kx = 1010, ky = 128;
    const wink = t > 57.0 && t < 57.45;
    drawKira(ctx, { x: kx, y: ky, r: 15, tt: t, glow: 0.9, expr: 'happy', wink, rot: 0.05 * Math.sin(t * 2), blink: 1 });
    if (t > 57.0) sparkle(ctx, kx + 22, ky - 18, 4 * (1 - inv(57.0, 57.8, t)), 1 - inv(57.0, 57.8, t));

    const a = ss(56.2, 57.4, t);
    if (a <= 0) return;
    ctx.save(); ctx.globalAlpha = a;
    ctx.textAlign = 'center';
    const sc = lerp(1.05, 1, easeOut(inv(56.2, 58, t)));
    ctx.translate(560, 300); ctx.scale(sc, sc);
    ctx.shadowColor = 'rgba(255,210,140,0.9)'; ctx.shadowBlur = 28;
    ctx.font = `700 74px ${FONT}`; ctx.fillStyle = '#fffaf0';
    ctx.fillText('ほしのおとしもの', 0, 0);
    ctx.shadowBlur = 0; ctx.font = `500 20px ${FONT}`; ctx.fillStyle = 'rgba(255,245,230,0.9)';
    ctx.fillText('― The Star That Fell ―', 0, 42);
    ctx.restore();
    const c = ss(57.6, 58.4, t);
    if (c > 0) {
      ctx.save(); ctx.globalAlpha = c * 0.9; ctx.textAlign = 'center'; ctx.font = `500 15px ${FONT}`;
      ctx.fillStyle = '#fff4ea';
      ctx.fillText(global.ANIM_CREDIT || '声：VOICEVOX:ずんだもん / VOICEVOX:春日部つむぎ　｜　脚本・作画・音楽：Claude（すべてコードで生成）', W / 2, 700);
      ctx.restore();
    }
  }

  global.ANIM = { W, H, FPS, DUR, render, LINES, nOrbs: ORBS.length };
})(typeof window !== 'undefined' ? window : globalThis);
