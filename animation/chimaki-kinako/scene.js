/* いつも、となりに。 〜ちまきと、きなこ〜
 * 60秒 2Dアニメーション。すべての絵を Canvas 2D で時刻 t の純粋関数として描く。
 * 最後だけ本物の写真（window.DOG_PHOTO）を使う。
 */
(function (global) {
  'use strict';

  const W = 1280, H = 720, FPS = 30, DUR = 60;
  const FONT = '"Zen Maru Gothic","Hiragino Maru Gothic ProN","Hiragino Sans",sans-serif';
  const HAND = '"Klee One","Zen Maru Gothic",sans-serif';
  const TAU = Math.PI * 2;

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
  const easeInOut = x => x < .5 ? 4 * x * x * x : 1 - Math.pow(-2 * x + 2, 3) / 2;
  const bump = (a, b, v) => Math.sin(Math.PI * inv(a, b, v));

  // ---------- 台詞 ----------
  const LINES = [
    { id: 'L01', who: 'kinako', t: 1.2, end: 4.7, text: 'ねえ、ちまき。どうしていつも、そこにいるの？' },
    { id: 'L02', who: 'chimaki', t: 5.1, end: 8.7, text: '……ここからなら、きなこが、よく見えるから。' },
    { id: 'L03', who: 'kinako_puppy', t: 11.0, end: 14.4, text: 'くぅん……こわいよ……ひとりぼっち……。' },
    { id: 'L04', who: 'chimaki', t: 17.8, end: 21.2, text: '泣かないで。ぼくが、ずっと見ててあげる。' },
    { id: 'L05', who: 'kinako', t: 28.2, end: 30.8, text: 'ちまき……ふるえてるの？' },
    { id: 'L06', who: 'chimaki', t: 31.0, end: 33.8, text: 'ふ、ふるえてなんか……ないよ。' },
    { id: 'L07', who: 'chimaki', t: 34.25, end: 35.3, text: 'きゃんっ！' },
    { id: 'L08', who: 'kinako', t: 40.6, end: 44.2, text: 'だいじょうぶ。今度は、わたしが守る番だよ。' },
    { id: 'L09', who: 'chimaki', t: 44.6, end: 47.8, text: '……きなこ。大きくなったね。' },
    { id: 'L10', who: 'kinako', t: 49.6, end: 52.4, text: 'これからも、ずっといっしょだよ。' },
    { id: 'L11', who: 'chimaki', t: 52.7, end: 54.8, text: 'うん。ずっと、ね。' },
  ];
  const NAMES = { chimaki: 'ちまき', kinako: 'きなこ', kinako_puppy: 'きなこ' };
  const NAME_COL = { chimaki: '#c9d3ff', kinako: '#ffd08a', kinako_puppy: '#ffd08a' };
  const LS = () => global.LIPSYNC || {};
  const lineDur = L => { const l = LS()[L.id]; return l ? l.dur : (L.end - L.t - 0.3); };
  const sameWho = (a, b) => a === b || (a.startsWith('kinako') && b.startsWith('kinako'));
  function lineAt(who, t) {
    for (const L of LINES) if (sameWho(L.who, who) && t >= L.t && t < L.t + lineDur(L)) return L;
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
    const p = (t + seed) % 3.7;
    return p < 0.15 ? Math.abs(p - 0.075) / 0.075 : 1;
  }

  // ---------- 形のヘルパ ----------
  // ふわふわの毛並みの楕円
  function fluffy(ctx, cx, cy, rx, ry, n, amp, rot = 0, ph = 0) {
    const c = Math.cos(rot), s = Math.sin(rot);
    const P = (a, k) => { const x = Math.cos(a) * rx * k, y = Math.sin(a) * ry * k; return [cx + x * c - y * s, cy + x * s + y * c]; };
    ctx.beginPath();
    const p0 = P(ph, 1); ctx.moveTo(p0[0], p0[1]);
    for (let i = 1; i <= n; i++) {
      const a = ph + i / n * TAU, am = ph + (i - 0.5) / n * TAU;
      const cp = P(am, 1 + amp * (0.8 + 0.4 * Math.sin(i * 12.9898))), e = P(a, 1);
      ctx.quadraticCurveTo(cp[0], cp[1], e[0], e[1]);
    }
    ctx.closePath();
  }
  function ell(ctx, x, y, rx, ry, r = 0) { ctx.beginPath(); ctx.ellipse(x, y, Math.max(0.01, rx), Math.max(0.01, ry), r, 0, TAU); }
  function glow(ctx, x, y, r, rgb, a, op = 'lighter') {
    if (a <= 0.001 || r <= 0) return;
    const g = ctx.createRadialGradient(x, y, 0, x, y, r);
    g.addColorStop(0, `rgba(${rgb},${a})`); g.addColorStop(0.4, `rgba(${rgb},${a * 0.35})`); g.addColorStop(1, `rgba(${rgb},0)`);
    ctx.save(); ctx.globalCompositeOperation = op; ctx.fillStyle = g;
    ctx.beginPath(); ctx.arc(x, y, r, 0, TAU); ctx.fill(); ctx.restore();
  }
  function rrect(ctx, x, y, w, h, r) { ctx.beginPath(); ctx.roundRect(x, y, w, h, r); }

  // タータンチェック（ブランケット）で現在のパスを塗る
  function plaidFill(ctx, x0, y0, w, h, rot, worn) {
    ctx.save(); ctx.clip();
    ctx.translate(x0, y0); ctx.rotate(rot);
    ctx.fillStyle = worn ? '#27304a' : '#1e2944'; ctx.fillRect(-w, -h, w * 3, h * 3);
    const band = (horiz, pos, wd, col) => { ctx.fillStyle = col; horiz ? ctx.fillRect(-w, pos, w * 3, wd) : ctx.fillRect(pos, -h, wd, h * 3); };
    for (let k = -w; k < w * 2; k += 46) {
      band(false, k, 16, 'rgba(92,62,40,0.75)'); band(false, k + 22, 3, 'rgba(214,104,44,0.85)'); band(false, k + 33, 2, 'rgba(10,12,20,0.6)');
    }
    for (let k = -h; k < h * 2; k += 46) {
      band(true, k, 16, 'rgba(92,62,40,0.6)'); band(true, k + 22, 3, 'rgba(214,104,44,0.8)'); band(true, k + 33, 2, 'rgba(10,12,20,0.5)');
    }
    ctx.restore();
  }

  // コーデュロイの畝
  function corduroy(ctx, x, y, w, h, base, dir = 0, gap = 8) {
    ctx.save(); ctx.clip();
    ctx.fillStyle = base; ctx.fillRect(x - 5, y - 5, w + 10, h + 10);
    ctx.translate(x + w / 2, y + h / 2); ctx.rotate(dir);
    const L = Math.max(w, h) * 1.6;
    for (let k = -L; k < L; k += gap) {
      ctx.fillStyle = 'rgba(120,80,30,0.16)'; ctx.fillRect(k, -L, 2.2, L * 2);
      ctx.fillStyle = 'rgba(255,240,200,0.10)'; ctx.fillRect(k + 3.2, -L, 2, L * 2);
    }
    ctx.restore();
  }

  // ---------- ちまき（ポメチワ・正面・伏せ） ----------
  const CH_BLACK = '#1c1c22', CH_WHITE = '#f3efe8', CH_TAN = '#b8773e';
  function chimakiBody(ctx, o) {
    ctx.save(); ctx.translate(o.x, o.y); ctx.scale(o.s, o.s);
    // しっぽ
    const tw = Math.sin((o.tt || 0) * 3) * 0.08 * (o.wag || 0);
    ctx.fillStyle = CH_BLACK; fluffy(ctx, -150, -52, 44, 30, 16, 0.2, -0.5 + tw); ctx.fill();
    // 体
    const bg = ctx.createLinearGradient(0, -40, 0, 60); bg.addColorStop(0, '#2c2c34'); bg.addColorStop(1, '#141418');
    ctx.fillStyle = bg; fluffy(ctx, -72, 6, 104, 50, 26, 0.12); ctx.fill();
    // 胸の白いふわ毛
    ctx.fillStyle = CH_WHITE; fluffy(ctx, 0, 12, 44, 40, 16, 0.2, 0, 0.3); ctx.fill();
    // 前足（茶色の脚＋白い足先）
    for (const sd of [-1, 1]) {
      const px = sd * 27, py = sd < 0 ? 58 : 54;
      ctx.fillStyle = CH_TAN; rrect(ctx, px - 11, 22, 22, py - 22, 9); ctx.fill();
      ctx.fillStyle = '#ece0cf'; ell(ctx, px, py, 15, 10.5); ctx.fill();
      ctx.strokeStyle = 'rgba(80,60,40,0.55)'; ctx.lineWidth = 1.4;
      for (const k of [-5, 0, 5]) { ctx.beginPath(); ctx.moveTo(px + k, py + 3); ctx.lineTo(px + k, py + 9); ctx.stroke(); }
    }
    ctx.restore();
  }
  function chimakiHead(ctx, o) {
    const m = o.mouth || 0, e = o.eyes || 'normal', age = o.age || 0;
    ctx.save(); ctx.translate(o.x + (o.shake || 0), o.y); ctx.scale(o.s, o.s); ctx.rotate(o.rot || 0);
    // 耳
    const ea = o.earFlat || 0;
    for (const sd of [-1, 1]) {
      ctx.save(); ctx.translate(sd * 28, -80); ctx.rotate(sd * (0.18 + ea * 0.95));
      ctx.fillStyle = CH_BLACK;
      ctx.beginPath(); ctx.moveTo(-sd * 20, 10); ctx.quadraticCurveTo(sd * 2, -30, sd * 8, -44); ctx.quadraticCurveTo(sd * 20, -18, sd * 24, 12); ctx.closePath(); ctx.fill();
      ctx.fillStyle = age > 0.3 ? '#c9c9d0' : '#a9a9b4';
      ctx.beginPath(); ctx.moveTo(-sd * 8, 6); ctx.quadraticCurveTo(sd * 4, -22, sd * 7, -32); ctx.quadraticCurveTo(sd * 14, -12, sd * 15, 8); ctx.closePath(); ctx.fill();
      ctx.restore();
    }
    // 頭
    const hg = ctx.createRadialGradient(-10, -70, 5, 0, -48, 60); hg.addColorStop(0, '#34343e'); hg.addColorStop(1, CH_BLACK);
    ctx.fillStyle = hg; fluffy(ctx, 0, -50, 52, 45, 22, 0.08); ctx.fill();
    for (const sd of [-1, 1]) { fluffy(ctx, sd * 40, -30, 22, 19, 9, 0.2); ctx.fill(); }
    // 麻呂眉
    ctx.fillStyle = '#e8dccb';
    for (const sd of [-1, 1]) { ell(ctx, sd * 17 + (o.brow || 0) * sd * -1, -68 - (o.browUp || 0) * 4, 7.5, 5, sd * 0.2); ctx.fill(); }
    // 目のまわり（年齢で白く）
    if (age > 0) for (const sd of [-1, 1]) { ctx.fillStyle = `rgba(215,212,210,${0.5 * age})`; ell(ctx, sd * 18, -47, 13.5, 12.5); ctx.fill(); }
    // 口もと
    ctx.fillStyle = CH_WHITE; fluffy(ctx, 0, -22, 26, 21, 12, 0.12, 0, 0.2); ctx.fill();
    // 目
    eyesDog(ctx, o, -47, 18, 8.8, '#2a140a', '#6b3a1f');
    // 鼻
    const ng = ctx.createLinearGradient(0, -36, 0, -24); ng.addColorStop(0, '#2b2b2e'); ng.addColorStop(1, '#0c0c0e');
    ctx.fillStyle = ng; ctx.beginPath(); ctx.moveTo(-9, -33); ctx.quadraticCurveTo(0, -38, 9, -33); ctx.quadraticCurveTo(8, -25, 0, -24); ctx.quadraticCurveTo(-8, -25, -9, -33); ctx.fill();
    ctx.fillStyle = 'rgba(255,255,255,0.45)'; ell(ctx, -3, -33.5, 3, 1.5); ctx.fill();
    mouthDog(ctx, 0, -24, m, o.smile || 0, 1);
    ctx.restore();
  }

  // ---------- きなこ（ロングヘアード・ダックス） ----------
  const KI_BASE = '#e8c896', KI_LIGHT = '#f6e6c8', KI_EAR = '#d4a466';
  function kinakoBody(ctx, o) {
    ctx.save(); ctx.translate(o.x, o.y); ctx.scale(o.s, o.s);
    const pose = o.pose || 'belly';
    if (pose === 'belly') {
      const bg = ctx.createLinearGradient(-120, 40, 40, 200); bg.addColorStop(0, '#e2bf88'); bg.addColorStop(1, '#f1dcb6');
      // 後ろ足・しっぽ
      ctx.fillStyle = '#d9b27a'; fluffy(ctx, -150, 150, 26, 18, 10, 0.15, 0.3); ctx.fill();
      fluffy(ctx, -40, 178, 24, 16, 10, 0.15, -0.2); ctx.fill();
      ctx.fillStyle = bg; fluffy(ctx, -70, 108, 104, 56, 26, 0.09, -0.55); ctx.fill();
      ctx.fillStyle = 'rgba(248,236,212,0.9)'; ell(ctx, -62, 116, 60, 30, -0.55); ctx.fill();
      // 下の前足
      ctx.fillStyle = KI_BASE; fluffy(ctx, -122, 72, 17, 28, 10, 0.12, 0.5); ctx.fill();
      // 上げた前足（写真のポーズ）
      const wig = Math.sin((o.tt || 0) * 2.4) * 0.08 + (o.pawWave || 0);
      ctx.save(); ctx.translate(-32, 34); ctx.rotate(-0.25 + wig);
      ctx.strokeStyle = KI_BASE; ctx.lineCap = 'round'; ctx.lineWidth = 24;
      ctx.beginPath(); ctx.moveTo(-28, 44); ctx.lineTo(-6, -8); ctx.stroke();
      ctx.fillStyle = KI_LIGHT; ell(ctx, 2, 14, 14, 18, -0.2); ctx.fill();
      ctx.fillStyle = '#3a2a22'; for (const k of [-6, 0, 6]) { ell(ctx, 3 + k, 30, 1.8, 2.4); ctx.fill(); }
      ctx.restore();
    } else if (pose === 'loaf') {
      ctx.fillStyle = '#e2bf88'; fluffy(ctx, 0, 58, 86, 40, 22, 0.1); ctx.fill();
      ctx.fillStyle = KI_BASE;
      for (const sd of [-1, 1]) { rrect(ctx, sd * 24 - 12, 40, 24, 44, 11); ctx.fill(); }
      ctx.fillStyle = KI_LIGHT; for (const sd of [-1, 1]) { ell(ctx, sd * 24, 84, 14, 9); ctx.fill(); }
    } else if (pose === 'puppy') {
      ctx.fillStyle = '#e6c38e'; fluffy(ctx, 0, 40, 60, 36, 18, 0.1); ctx.fill();
      ctx.fillStyle = KI_LIGHT; for (const sd of [-1, 1]) { ell(ctx, sd * 18, 52, 12, 8); ctx.fill(); }
    }
    ctx.restore();
  }
  function kinakoHead(ctx, o) {
    const pup = o.pose === 'puppy';
    const m = o.mouth || 0;
    ctx.save(); ctx.translate(o.x, o.y); ctx.scale(o.s, o.s); ctx.rotate(o.rot || 0);
    if (pup) ctx.scale(1.12, 1.12);
    // 垂れ耳（長い巻き毛）
    for (const sd of [-1, 1]) {
      const sw = Math.sin((o.tt || 0) * 1.7 + sd) * 0.03;
      const eg = ctx.createLinearGradient(sd * 40, -50, sd * 55, 40); eg.addColorStop(0, '#dcae70'); eg.addColorStop(1, '#c99352');
      ctx.fillStyle = eg; fluffy(ctx, sd * 47, pup ? -18 : -10, pup ? 20 : 23, pup ? 36 : 50, 18, 0.14, sd * -0.18 + sw, 0.4); ctx.fill();
    }
    // 頭
    const hg = ctx.createRadialGradient(-8, -62, 4, 0, -40, 55); hg.addColorStop(0, '#f6e2bd'); hg.addColorStop(1, KI_BASE);
    ctx.fillStyle = hg; ell(ctx, 0, -44, 39, 36); ctx.fill();
    // マズル（長い鼻すじ）
    ctx.fillStyle = KI_LIGHT; ell(ctx, 0, pup ? -18 : -10, 21, pup ? 19 : 26); ctx.fill();
    ctx.fillStyle = 'rgba(246,230,200,0.9)'; ell(ctx, 0, -34, 10, 18); ctx.fill();
    // 目
    eyesDog(ctx, o, -44, 17, pup ? 10.5 : 8.6, '#1d100a', '#4a2a18');
    // 鼻
    const ny = pup ? -4 : 6;
    const ng = ctx.createLinearGradient(0, ny - 8, 0, ny + 7); ng.addColorStop(0, '#2c2627'); ng.addColorStop(1, '#0d0a0a');
    ctx.fillStyle = ng; ell(ctx, 0, ny, 11.5, 8.5); ctx.fill();
    ctx.fillStyle = 'rgba(255,255,255,0.4)'; ell(ctx, -3.5, ny - 3.5, 3.5, 1.8); ctx.fill();
    mouthDog(ctx, 0, ny + 8, m, o.smile || 0, 0.9);
    ctx.restore();
  }

  // 目（表情つき）
  function eyesDog(ctx, o, ey, ex, r, dark, iris) {
    const e = o.eyes || 'normal', op = o.blink === undefined ? 1 : o.blink;
    const lx = (o.lookX || 0) * r * 0.25, ly = (o.lookY || 0) * r * 0.25;
    for (const sd of [-1, 1]) {
      const x = sd * ex, y = ey;
      ctx.lineCap = 'round';
      if (e === 'happy' || e === 'sleep') {
        ctx.strokeStyle = dark; ctx.lineWidth = r * 0.36;
        ctx.beginPath();
        if (e === 'happy') { ctx.moveTo(x - r * 0.85, y + r * 0.2); ctx.quadraticCurveTo(x, y - r * 0.9, x + r * 0.85, y + r * 0.2); }
        else { ctx.moveTo(x - r * 0.85, y - r * 0.1); ctx.quadraticCurveTo(x, y + r * 0.7, x + r * 0.85, y - r * 0.1); }
        ctx.stroke();
        continue;
      }
      if (e === 'squeeze') {
        ctx.strokeStyle = dark; ctx.lineWidth = r * 0.34;
        ctx.beginPath(); ctx.moveTo(x - sd * r * 0.9, y - r * 0.6); ctx.lineTo(x + sd * r * 0.5, y); ctx.lineTo(x - sd * r * 0.9, y + r * 0.6); ctx.stroke();
        continue;
      }
      const big = e === 'surprised' ? 1.18 : (e === 'scared' ? 1.08 : 1);
      const rr = r * big;
      ctx.save();
      ell(ctx, x, y, rr, rr * Math.max(0.08, op)); ctx.clip();
      ctx.fillStyle = iris; ell(ctx, x + lx, y + ly, rr, rr); ctx.fill();
      ctx.fillStyle = dark; ell(ctx, x + lx, y + ly, rr * (e === 'scared' ? 0.55 : 0.78), rr * (e === 'scared' ? 0.55 : 0.78)); ctx.fill();
      ctx.fillStyle = '#fff'; ell(ctx, x + lx + rr * 0.3, y + ly - rr * 0.35, rr * 0.3, rr * 0.3); ctx.fill();
      ctx.fillStyle = 'rgba(255,255,255,0.7)'; ell(ctx, x + lx - rr * 0.3, y + ly + rr * 0.35, rr * 0.13, rr * 0.13); ctx.fill();
      // 涙の潤み
      if (o.tears > 0) {
        ctx.fillStyle = `rgba(170,220,255,${0.55 * o.tears})`; ell(ctx, x, y + rr * 0.75, rr * 0.95, rr * 0.38); ctx.fill();
        ctx.fillStyle = `rgba(255,255,255,${0.8 * o.tears})`; ell(ctx, x + rr * 0.35, y + rr * 0.55, rr * 0.18, rr * 0.1); ctx.fill();
      }
      ctx.restore();
      if (e === 'scared' || e === 'worried') {
        ctx.strokeStyle = 'rgba(40,25,20,0.55)'; ctx.lineWidth = r * 0.18;
        ctx.beginPath(); ctx.moveTo(x - sd * r * 0.2, y - r * 1.55); ctx.lineTo(x + sd * r * 0.9, y - r * 1.25); ctx.stroke();
      }
    }
    // 涙のしずく
    if (o.drop > 0) {
      const ph = o.drop;
      const x = ex + 2, y = ey + r + ph * r * 3.5;
      ctx.fillStyle = `rgba(185,228,255,${0.9 * (1 - Math.max(0, ph - 0.7) / 0.3)})`;
      ctx.beginPath(); ctx.moveTo(x, y - r * 0.5); ctx.quadraticCurveTo(x + r * 0.35, y + r * 0.1, x, y + r * 0.3); ctx.quadraticCurveTo(x - r * 0.35, y + r * 0.1, x, y - r * 0.5); ctx.fill();
    }
    // ほっぺ
    if (o.blush > 0) {
      ctx.fillStyle = `rgba(255,130,150,${0.35 * o.blush})`;
      for (const sd of [-1, 1]) { ell(ctx, sd * (ex + r * 0.9), ey + r * 1.6, r * 0.9, r * 0.45); ctx.fill(); }
    }
  }
  function mouthDog(ctx, x, y, m, smile, k) {
    ctx.strokeStyle = '#2a1a1a'; ctx.lineWidth = 2 * k; ctx.lineCap = 'round';
    if (m > 0.06) {
      ctx.fillStyle = '#5a2226'; ell(ctx, x, y + 4 * k + 3 * m * k, (5 + 3 * m) * k, (2 + 6 * m) * k); ctx.fill();
      ctx.fillStyle = '#ef7d8a'; ell(ctx, x, y + (6 + 6 * m) * k, (3.5 + 2 * m) * k, (1 + 2.6 * m) * k); ctx.fill();
    }
    ctx.beginPath(); ctx.moveTo(x, y - 1); ctx.lineTo(x, y + 3 * k);
    const up = smile * 3 * k;
    ctx.moveTo(x - 7 * k, y + 3 * k - up); ctx.quadraticCurveTo(x - 3.5 * k, y + 7 * k, x, y + 3 * k);
    ctx.quadraticCurveTo(x + 3.5 * k, y + 7 * k, x + 7 * k, y + 3 * k - up); ctx.stroke();
  }

  // ---------- 部屋・ソファ ----------
  const SOFA = { x0: 300, x1: 980, top: 238, seat: 470, bottom: 590 };
  function drawRoom(ctx, t, id, L) {
    // 壁
    const wg = ctx.createLinearGradient(0, 0, 0, 600);
    wg.addColorStop(0, '#efe0c4'); wg.addColorStop(1, '#e6d2af');
    ctx.fillStyle = wg; ctx.fillRect(-400, -300, 2100, 900);
    // 腰壁
    ctx.fillStyle = '#d9c09a'; ctx.fillRect(-400, 520, 2100, 50);
    ctx.fillStyle = 'rgba(120,80,40,0.25)'; ctx.fillRect(-400, 520, 2100, 3);
    // 床
    const fg = ctx.createLinearGradient(0, 570, 0, 900); fg.addColorStop(0, '#a87a50'); fg.addColorStop(1, '#7c5332');
    ctx.fillStyle = fg; ctx.fillRect(-400, 570, 2100, 500);
    ctx.strokeStyle = 'rgba(60,35,15,0.25)'; ctx.lineWidth = 1.5;
    for (let y = 600; y < 900; y += 34) { ctx.beginPath(); ctx.moveTo(-400, y); ctx.lineTo(1700, y); ctx.stroke(); }
    // ラグ
    ctx.fillStyle = '#c9b08c'; ell(ctx, 640, 660, 460, 60); ctx.fill();
    ctx.strokeStyle = 'rgba(150,110,70,0.5)'; ctx.lineWidth = 3; ell(ctx, 640, 660, 440, 52); ctx.stroke();

    drawWindow(ctx, t, id, L);

    // 壁の額
    ctx.save(); ctx.translate(215, -20);
    ctx.fillStyle = '#8a6440'; rrect(ctx, 70, 110, 170, 130, 4); ctx.fill();
    ctx.fillStyle = '#f4ead6'; ctx.fillRect(82, 122, 146, 106);
    ctx.fillStyle = '#9cc0c9'; ctx.fillRect(90, 130, 130, 60);
    ctx.fillStyle = '#7fa27a'; ctx.beginPath(); ctx.moveTo(90, 190); ctx.quadraticCurveTo(140, 150, 175, 175); ctx.quadraticCurveTo(200, 160, 220, 172); ctx.lineTo(220, 220); ctx.lineTo(90, 220); ctx.fill();
    ctx.fillStyle = '#f7e3a0'; ell(ctx, 190, 150, 10, 10); ctx.fill(); ctx.restore();
    // フロアランプ
    ctx.fillStyle = '#5a4634'; ctx.fillRect(147, 250, 6, 330);
    ell(ctx, 150, 582, 30, 7); ctx.fill();
    ctx.fillStyle = L.lamp > 0.1 ? '#ffe7b0' : '#f1dfc0';
    ctx.beginPath(); ctx.moveTo(110, 250); ctx.lineTo(190, 250); ctx.lineTo(172, 190); ctx.lineTo(128, 190); ctx.closePath(); ctx.fill();
    // 観葉植物
    ctx.fillStyle = '#b76c43'; rrect(ctx, 1110, 520, 70, 62, 8); ctx.fill();
    ctx.fillStyle = '#5f8a57';
    for (let i = 0; i < 9; i++) { const a = -Math.PI / 2 + (i - 4) * 0.28 + Math.sin(t * 0.8 + i) * 0.02; ctx.save(); ctx.translate(1145, 525); ctx.rotate(a); ell(ctx, 55, 0, 55, 13); ctx.fill(); ctx.restore(); }

    drawSofa(ctx, t, id);
  }

  function drawWindow(ctx, t, id, L) {
    const x = 890, y = 70, w = 300, h = 330;
    ctx.save(); ctx.beginPath(); ctx.rect(x, y, w, h); ctx.clip();
    const sg = ctx.createLinearGradient(0, y, 0, y + h);
    if (id === 'day') { sg.addColorStop(0, '#8fc3ea'); sg.addColorStop(1, '#d9ecf5'); }
    else if (id === 'morning') { sg.addColorStop(0, '#f7d9a6'); sg.addColorStop(1, '#fff1d6'); }
    else { sg.addColorStop(0, '#0e1422'); sg.addColorStop(1, '#1d2536'); }
    ctx.fillStyle = sg; ctx.fillRect(x, y, w, h);
    if (id === 'day' || id === 'morning') {
      ctx.fillStyle = id === 'day' ? 'rgba(255,255,255,0.85)' : 'rgba(255,240,215,0.8)';
      const cx = x + ((t * 6) % 420) - 60;
      for (const [dx, dy, r] of [[0, 90, 26], [26, 80, 30], [55, 92, 22]]) { ell(ctx, cx + dx, y + dy, r * 1.4, r * 0.8); ctx.fill(); }
      ctx.fillStyle = id === 'day' ? '#6f9a63' : '#8a9a62';
      ell(ctx, x + 60, y + h - 20, 110, 70); ctx.fill(); ell(ctx, x + 240, y + h - 10, 90, 60); ctx.fill();
    } else {
      // 雨
      const inten = L.rain;
      ctx.strokeStyle = `rgba(170,190,230,${0.35 * inten})`; ctx.lineWidth = 1.2;
      const r = mulberry32(3);
      ctx.beginPath();
      for (let i = 0; i < 90 * inten; i++) {
        const rx = x + r() * w, sp = 700 + r() * 300, ry = y + ((r() * h + t * sp) % (h + 60)) - 30;
        ctx.moveTo(rx, ry); ctx.lineTo(rx - 6, ry + 22);
      }
      ctx.stroke();
      ctx.fillStyle = '#0a0f18'; ell(ctx, x + 60, y + h - 10, 110, 70); ctx.fill(); ell(ctx, x + 240, y + h, 90, 60); ctx.fill();
      if (L.flash > 0) { ctx.fillStyle = `rgba(215,225,255,${L.flash})`; ctx.fillRect(x, y, w, h); }
    }
    // ガラスの水滴
    if (L.drops > 0) {
      const r = mulberry32(11);
      for (let i = 0; i < 40; i++) {
        const dx = x + r() * w, dy = y + ((r() * h + t * (8 + r() * 30)) % h), dr = 1.5 + r() * 3;
        ctx.fillStyle = `rgba(230,240,255,${0.35 * L.drops})`; ell(ctx, dx, dy, dr, dr * 1.2); ctx.fill();
      }
    }
    ctx.restore();
    // 窓枠・カーテン
    ctx.strokeStyle = '#f6efe3'; ctx.lineWidth = 12; ctx.strokeRect(x, y, w, h);
    ctx.lineWidth = 7; ctx.beginPath(); ctx.moveTo(x + w / 2, y); ctx.lineTo(x + w / 2, y + h); ctx.moveTo(x, y + h / 2); ctx.lineTo(x + w, y + h / 2); ctx.stroke();
    for (const sd of [0, 1]) {
      const cx = sd ? x + w + 10 : x - 10, sway = Math.sin(t * 0.9 + sd) * 3;
      ctx.fillStyle = '#c86f4f';
      ctx.beginPath(); ctx.moveTo(cx - 34, y - 20); ctx.lineTo(cx + 34, y - 20);
      ctx.quadraticCurveTo(cx + 22 + sway, y + h / 2, cx + 30, y + h + 40); ctx.lineTo(cx - 30, y + h + 40); ctx.quadraticCurveTo(cx - 22 + sway, y + h / 2, cx - 34, y - 20); ctx.fill();
      ctx.strokeStyle = 'rgba(90,40,20,0.3)'; ctx.lineWidth = 2;
      for (const k of [-14, 0, 14]) { ctx.beginPath(); ctx.moveTo(cx + k, y - 18); ctx.lineTo(cx + k * 0.9 + sway, y + h + 38); ctx.stroke(); }
    }
    ctx.fillStyle = '#7a5838'; ctx.fillRect(x - 60, y - 26, w + 120, 8);
  }

  function drawSofa(ctx, t, id) {
    const S = SOFA, base = '#d3a864';
    // 影
    ctx.fillStyle = 'rgba(60,35,15,0.35)'; ell(ctx, 640, 594, 390, 16); ctx.fill();
    // 脚
    ctx.fillStyle = '#5a3b22'; for (const lx of [300, 960]) { rrect(ctx, lx, 580, 20, 18, 3); ctx.fill(); }
    // 背もたれ
    rrect(ctx, S.x0, S.top, S.x1 - S.x0, 280, 48); corduroy(ctx, S.x0, S.top, S.x1 - S.x0, 280, base);
    ctx.save(); rrect(ctx, S.x0, S.top, S.x1 - S.x0, 280, 48); ctx.clip();
    const sh = ctx.createLinearGradient(0, S.top, 0, S.top + 280); sh.addColorStop(0, 'rgba(255,240,210,0.18)'); sh.addColorStop(1, 'rgba(90,55,20,0.28)');
    ctx.fillStyle = sh; ctx.fillRect(S.x0, S.top, 700, 280); ctx.restore();
    // 花柄クッション（左奥）
    ctx.save(); ctx.translate(385, 360); ctx.rotate(-0.15);
    rrect(ctx, -70, -62, 140, 124, 30); ctx.fillStyle = '#f0c85a'; ctx.fill(); ctx.clip();
    const r = mulberry32(21);
    for (let i = 0; i < 18; i++) {
      const fx = -70 + r() * 140, fy = -62 + r() * 124;
      ctx.fillStyle = r() < 0.5 ? '#d9557a' : '#9a6fc4';
      for (let p = 0; p < 5; p++) { ell(ctx, fx + Math.cos(p * 1.26) * 6, fy + Math.sin(p * 1.26) * 6, 5, 5); ctx.fill(); }
      ctx.fillStyle = '#6c9b5b'; ell(ctx, fx + 9, fy + 7, 5, 2.5, 0.6); ctx.fill();
    }
    ctx.restore();
    // 座面
    rrect(ctx, S.x0 + 30, S.seat, S.x1 - S.x0 - 60, 110, 26); corduroy(ctx, S.x0 + 30, S.seat, S.x1 - S.x0 - 60, 110, '#d8ae6a', 0, 8);
    ctx.save(); rrect(ctx, S.x0 + 30, S.seat, S.x1 - S.x0 - 60, 110, 26); ctx.clip();
    const sg = ctx.createLinearGradient(0, S.seat, 0, S.seat + 110); sg.addColorStop(0, 'rgba(255,245,215,0.2)'); sg.addColorStop(1, 'rgba(80,50,20,0.35)');
    ctx.fillStyle = sg; ctx.fillRect(S.x0, S.seat, 700, 110); ctx.restore();
    // ひじ掛け
    for (const ax of [S.x0 - 40, S.x1 - 50]) {
      rrect(ctx, ax, 350, 90, 240, 40); corduroy(ctx, ax, 350, 90, 240, '#cfa35e', 0, 8);
      ctx.save(); rrect(ctx, ax, 350, 90, 240, 40); ctx.clip();
      const ag = ctx.createLinearGradient(ax, 0, ax + 90, 0); ag.addColorStop(0, 'rgba(255,240,210,0.15)'); ag.addColorStop(1, 'rgba(80,50,20,0.3)');
      ctx.fillStyle = ag; ctx.fillRect(ax, 350, 90, 240); ctx.restore();
    }
    // 背もたれの上の「特等席」クッション
    ctx.save();
    ctx.beginPath(); ctx.moveTo(400, 300);
    ctx.bezierCurveTo(400, 230, 470, 222, 560, 226); ctx.bezierCurveTo(660, 222, 760, 232, 770, 292);
    ctx.bezierCurveTo(772, 330, 700, 336, 560, 334); ctx.bezierCurveTo(440, 334, 398, 330, 400, 300); ctx.closePath();
    corduroy(ctx, 390, 215, 390, 125, '#e0bb7a', 0.45, 9);
    ctx.restore();
    ctx.save(); ctx.strokeStyle = 'rgba(120,80,30,0.25)'; ctx.lineWidth = 2;
    ctx.beginPath(); ctx.moveTo(430, 312); ctx.quadraticCurveTo(560, 300, 740, 318); ctx.stroke(); ctx.restore();
  }

  // ブランケットの形状
  function blanketShape(ctx, pts) {
    ctx.beginPath(); ctx.moveTo(pts[0][0], pts[0][1]);
    for (let i = 1; i < pts.length; i++) {
      const p = pts[i], q = pts[(i + 1) % pts.length];
      ctx.quadraticCurveTo(p[0], p[1], (p[0] + q[0]) / 2, (p[1] + q[1]) / 2);
    }
    ctx.closePath();
  }
  function drawBlanket(ctx, pts, worn, rot = 0.3) {
    blanketShape(ctx, pts);
    const xs = pts.map(p => p[0]), ys = pts.map(p => p[1]);
    const x0 = Math.min(...xs), y0 = Math.min(...ys);
    plaidFill(ctx, x0, y0, Math.max(...xs) - x0 + 60, Math.max(...ys) - y0 + 60, rot, worn);
    blanketShape(ctx, pts);
    ctx.save(); ctx.clip();
    const g = ctx.createLinearGradient(0, y0, 0, Math.max(...ys)); g.addColorStop(0, 'rgba(255,255,255,0.08)'); g.addColorStop(1, 'rgba(0,0,0,0.3)');
    ctx.fillStyle = g; ctx.fillRect(x0 - 10, y0 - 10, Math.max(...xs) - x0 + 20, Math.max(...ys) - y0 + 20);
    ctx.restore();
    if (worn) { ctx.strokeStyle = 'rgba(220,160,110,0.35)'; ctx.lineWidth = 1.5; blanketShape(ctx, pts); ctx.stroke(); }
  }
  const lerpPts = (A, B, k) => A.map((p, i) => [lerp(p[0], B[i][0], k), lerp(p[1], B[i][1], k)]);

  function drawBasket(ctx, x, y, front) {
    if (!front) {
      ctx.fillStyle = '#6e4a2a'; ell(ctx, x, y - 18, 92, 22); ctx.fill();
      ctx.fillStyle = '#e9dcc5'; ell(ctx, x, y - 14, 80, 16); ctx.fill();
      return;
    }
    ctx.save();
    ctx.beginPath(); ctx.moveTo(x - 94, y - 18); ctx.lineTo(x + 94, y - 18); ctx.lineTo(x + 80, y + 48); ctx.quadraticCurveTo(x, y + 62, x - 80, y + 48); ctx.closePath();
    ctx.fillStyle = '#b07a44'; ctx.fill(); ctx.clip();
    ctx.strokeStyle = 'rgba(90,55,25,0.55)'; ctx.lineWidth = 3;
    for (let k = y - 12; k < y + 60; k += 10) { ctx.beginPath(); ctx.moveTo(x - 100, k); ctx.quadraticCurveTo(x, k + 8, x + 100, k); ctx.stroke(); }
    for (let k = x - 100; k < x + 100; k += 16) { ctx.beginPath(); ctx.moveTo(k, y - 20); ctx.lineTo(k + 4, y + 60); ctx.stroke(); }
    ctx.restore();
    ctx.strokeStyle = '#8a5a30'; ctx.lineWidth = 9; ctx.lineCap = 'round';
    ctx.beginPath(); ctx.moveTo(x - 92, y - 18); ctx.lineTo(x + 92, y - 18); ctx.stroke();
  }

  // ---------- シーン別の状態 ----------
  function camFor(id, t) {
    if (id === 'day') { const k = easeInOut(inv(0, 9, t)); return { x: lerp(660, 660, k), y: lerp(370, 345, k), z: lerp(1.2, 1.4, k) }; }
    if (id === 'flash') {
      const k1 = easeInOut(inv(15.6, 17.4, t)), k2 = easeInOut(inv(20.5, 25, t));
      return { x: lerp(lerp(650, 670, k1), 675, k2), y: lerp(lerp(455, 505, k1), 525, k2), z: lerp(lerp(1.22, 1.6, k1), 1.8, k2) };
    }
    if (id === 'storm') {
      if (t < 36) { const k = easeInOut(inv(25, 33, t)); return { x: lerp(640, 650, k), y: lerp(330, 320, k), z: lerp(1.3, 1.42, k) }; }
      if (t < 40.4) { const k = easeInOut(inv(36, 37.4, t)); return { x: lerp(650, 660, k), y: lerp(320, 360, k), z: lerp(1.42, 1.25, k) }; }
      const k = easeInOut(inv(40.2, 42, t));
      return { x: lerp(660, 628, k), y: lerp(360, 250, k), z: lerp(1.25, 2.0, k) + 0.08 * inv(42, 48, t) };
    }
    const k = easeInOut(inv(48, 55, Math.min(t, 55)));
    return { x: lerp(640, 660, k), y: lerp(380, 350, k), z: lerp(1.05, 1.35, k) };
  }

  function lightFor(id, t) {
    const L = { night: 0, lamp: 0, rain: 0, flash: 0, drops: 0, sepia: 0, sun: 0 };
    if (id === 'day') { L.sun = 0.6; }
    if (id === 'flash') { L.night = 0.75; L.lamp = 1; L.rain = 0.6; L.drops = 1; L.sepia = 1; }
    if (id === 'storm') {
      L.night = 0.82; L.lamp = 0.85; L.rain = 1 - 0.7 * ss(44, 48, t); L.drops = 1;
      const f1 = t > 27 && t < 27.6 ? (1 - inv(27, 27.6, t)) * (0.6 + 0.4 * Math.sin(t * 90)) : 0;
      const f2 = t > 34 && t < 34.9 ? (1 - inv(34, 34.9, t)) * (0.75 + 0.25 * Math.sin(t * 70)) : 0;
      L.flash = clamp(Math.max(f1 * 0.8, f2));
    }
    if (id === 'morning') { L.sun = 1; L.drops = 0.6; }
    return L;
  }

  function drawScene(ctx, t, id) {
    const cam = camFor(id, t), L = lightFor(id, t);
    let shake = 0;
    if (id === 'storm' && t > 34 && t < 34.6) shake = 6 * (1 - inv(34, 34.6, t));
    ctx.save();
    ctx.translate(W / 2 + shake * Math.sin(t * 97), H / 2 + shake * Math.cos(t * 83));
    ctx.scale(cam.z, cam.z); ctx.translate(-cam.x, -cam.y);

    drawRoom(ctx, t, id, L);
    if (id === 'day' || id === 'morning') sceneDaylight(ctx, t, id);
    else if (id === 'flash') sceneFlashback(ctx, t);
    else sceneStorm(ctx, t);

    // 光の演出
    if (L.sun > 0) {
      ctx.save(); ctx.globalCompositeOperation = 'screen';
      for (let i = 0; i < 4; i++) {
        const g = ctx.createLinearGradient(900, 100, 500, 650);
        const a = (0.07 + 0.03 * Math.sin(t * 0.7 + i)) * L.sun;
        g.addColorStop(0, `rgba(255,236,190,${a * 2})`); g.addColorStop(1, 'rgba(255,236,190,0)');
        ctx.fillStyle = g; ctx.beginPath();
        const o = i * 70;
        ctx.moveTo(905 + o * 0.9, 80); ctx.lineTo(960 + o * 0.9, 80); ctx.lineTo(620 + o, 700); ctx.lineTo(480 + o, 700); ctx.closePath(); ctx.fill();
      }
      ctx.restore();
      // ほこりのきらめき
      const r = mulberry32(8);
      for (let i = 0; i < 36; i++) {
        const px = 500 + r() * 520 + Math.sin(t * 0.3 + i) * 20, py = 120 + ((r() * 500 + t * (4 + r() * 6)) % 520);
        glow(ctx, px, py, 4, '255,240,200', 0.5 * L.sun * (0.5 + 0.5 * Math.sin(t * 2 + i)));
      }
    }
    if (L.night > 0) {
      ctx.save(); ctx.globalCompositeOperation = 'multiply';
      ctx.fillStyle = `rgba(${Math.round(lerp(255, 62, L.night))},${Math.round(lerp(255, 76, L.night))},${Math.round(lerp(255, 132, L.night))},1)`;
      ctx.fillRect(-500, -400, 2300, 1400); ctx.restore();
      glow(ctx, 150, 225, 520, '255,190,110', 0.28 * L.lamp, 'screen');
      glow(ctx, 150, 220, 90, '255,230,170', 0.6 * L.lamp);
      glow(ctx, 620, 300, 460, '255,185,110', 0.22 * L.lamp, 'screen');
      if (L.flash > 0) {
        ctx.save(); ctx.globalCompositeOperation = 'screen';
        const g = ctx.createLinearGradient(1190, 100, 300, 600);
        g.addColorStop(0, `rgba(200,215,255,${L.flash})`); g.addColorStop(1, `rgba(150,170,230,${L.flash * 0.35})`);
        ctx.fillStyle = g; ctx.fillRect(-500, -400, 2300, 1400); ctx.restore();
      }
    }
    ctx.restore();

    if (L.sepia > 0) {
      ctx.save();
      ctx.globalCompositeOperation = 'color'; ctx.fillStyle = 'rgba(176,132,80,0.62)'; ctx.fillRect(0, 0, W, H);
      ctx.globalCompositeOperation = 'soft-light'; ctx.fillStyle = 'rgba(255,220,170,0.35)'; ctx.fillRect(0, 0, W, H);
      ctx.restore();
      const vg = ctx.createRadialGradient(W / 2, H / 2, H * 0.25, W / 2, H / 2, H * 0.85);
      vg.addColorStop(0, 'rgba(255,240,215,0)'); vg.addColorStop(1, 'rgba(255,236,205,0.55)');
      ctx.fillStyle = vg; ctx.fillRect(0, 0, W, H);
      // 「あの日」
      const a = ss(10.2, 11, t) * (1 - ss(14, 15, t));
      if (a > 0) {
        ctx.save(); ctx.globalAlpha = a; ctx.font = `600 34px ${HAND}`; ctx.fillStyle = '#6a4a2a'; ctx.textAlign = 'left';
        ctx.fillText('― あの日 ―', 70, 90); ctx.restore();
      }
    }
  }

  // 現在：昼 / 朝（写真と同じ構図）
  function sceneDaylight(ctx, t, id) {
    const tf = id === 'morning' ? Math.min(t, 55) : t;
    // ブランケット（座面）
    drawBlanket(ctx, [[640, 480], [760, 462], [930, 470], [950, 540], [900, 588], [700, 590], [620, 560]], true, 0.35);
    const ch = { x: 560, y: 262, s: 0.82, age: 1, tt: tf, blink: blinkOpen(tf, 0.4), mouth: mouthOf('chimaki', tf), lookX: 0.3, lookY: 0.3 };
    const ki = { x: 805, y: 405, s: 0.86, pose: 'belly', tt: tf, blink: blinkOpen(tf, 1.9), mouth: mouthOf('kinako', tf), rot: 0.12 };
    if (id === 'day') {
      ki.lookY = -1; ki.lookX = -0.6; ki.rot = 0.18;
      if (tf > 5) { ch.lookX = 0.8; ch.lookY = 1.2; ch.smile = ss(7.5, 8.3, tf); ch.blush = ss(7.2, 8.2, tf); }
      if (tf > 8.3) ki.eyes = 'happy';
    } else {
      ch.lookX = 0; ch.lookY = 0; ki.lookX = 0; ki.lookY = 0;
      ki.smile = 1; ch.smile = 0.8;
      if (tf < 52.6) ki.eyes = lineAt('kinako', tf) ? 'normal' : 'happy';
      if (tf > 51.5 && tf < 52.7) { ch.lookX = 0.9; ch.lookY = 1; }
      if (tf > 52.7 && tf < 54.3) ch.eyes = lineAt('chimaki', tf) ? 'normal' : 'happy';
      if (tf > 54.3) { ki.eyes = 'normal'; ch.eyes = 'normal'; }
      ki.pawWave = tf > 50 && tf < 53 ? 0.25 * Math.sin((tf - 50) * 8) * bump(50, 53, tf) : 0;
      ch.wag = 1;
    }
    chimakiBody(ctx, ch); chimakiHead(ctx, ch);
    kinakoBody(ctx, ki); kinakoHead(ctx, ki);
  }

  // 回想
  function sceneFlashback(ctx, t) {
    const bx = 740, by = 612;
    // ブランケット：背もたれの上 → 落ちる → カゴに
    const onTop = [[640, 250], [720, 232], [790, 246], [800, 300], [770, 360], [700, 352], [650, 320]];
    const onBasket = [[640, 588], [740, 574], [842, 590], [850, 640], [820, 668], [660, 668], [630, 640]];
    const nudge = bump(14.5, 15.1, t);
    const fall = easeInOut(inv(15.0, 16.2, t));
    const ch = { x: 560, y: 262, s: 0.78, age: 0, tt: t, blink: blinkOpen(t, 0.4), mouth: mouthOf('chimaki', t) };
    ch.lookX = 0.8; ch.lookY = 1.2;
    if (t < 13.4) { ch.lookX = 0.6; ch.lookY = 1.4; ch.eyes = 'normal'; ch.earFlat = 0; }
    if (t > 13.4 && t < 14.5) { ch.eyes = 'surprised'; ch.lookX = 1; ch.lookY = 1.5; }
    ch.x += 18 * nudge; ch.y += 6 * nudge;
    // ちまき：ぴょんと降りる
    if (t > 16.2) {
      const k = easeInOut(inv(16.2, 16.75, t));
      ch.x = lerp(578, 610, k); ch.y = lerp(262, 598, k) - 90 * Math.sin(Math.PI * k);
      if (t > 16.75) { ch.x = 612; ch.y = 598; }
      ch.s = 0.74;
    }
    const pup = { x: bx, y: by - 26, s: 0.6, pose: 'puppy', tt: t, blink: blinkOpen(t, 2.2), mouth: mouthOf('kinako', t) };
    pup.eyes = 'normal'; pup.tears = t < 17.6 ? 1 : 1 - inv(17.6, 19.5, t); pup.lookY = -0.5;
    const shiver = t < 16.5 ? Math.sin(t * 55) * 1.6 : Math.sin(t * 55) * 1.6 * (1 - inv(16.5, 18, t));
    pup.x += shiver;
    if (t > 11.5 && t < 16.2) pup.drop = ((t - 11.5) % 1.6) / 1.6;
    if (t > 16.2 && t < 17.6) { pup.eyes = 'surprised'; pup.lookX = -1; pup.lookY = -0.2; }
    if (t > 17.6) { pup.lookX = -1; pup.lookY = -0.3; }
    if (t > 19.6) { pup.eyes = 'happy'; pup.smile = 1; pup.blush = ss(19.6, 20.5, t); pup.rot = -0.18 * ss(19.8, 20.8, t); pup.x -= 14 * ss(19.8, 20.8, t); }
    if (t > 21.6) { pup.eyes = 'sleep'; pup.rot = -0.25; }
    if (t > 17.8) { ch.lookX = 1; ch.lookY = 0.6; }
    if (t > 21.3) { ch.eyes = 'happy'; ch.smile = 0.7; }
    if (t > 22.2) { ch.eyes = 'sleep'; ch.rot = 0.12 * ss(22.2, 23, t); }

    // 描画順：カゴの奥 → 子犬 → カゴの前 → ブランケット → ちまき
    drawBasket(ctx, bx, by, false);
    kinakoBody(ctx, pup); kinakoHead(ctx, pup);
    drawBasket(ctx, bx, by, true);
    if (t < 16.2) {
      chimakiBody(ctx, ch); chimakiHead(ctx, ch);
      // 落ちていくブランケット
      let pts = lerpPts(onTop, onBasket, fall);
      if (fall > 0 && fall < 1) {
        const fl = Math.sin(fall * Math.PI);
        pts = pts.map((p, i) => [p[0] + Math.sin(t * 12 + i) * 10 * fl, p[1] + Math.cos(t * 10 + i * 2) * 8 * fl]);
      }
      if (t < 15.0) pts = pts.map(p => [p[0] + 14 * nudge, p[1] + 4 * nudge]);
      if (fall < 1) drawBlanket(ctx, pts, false, 0.3 + fall * 0.4);
    }
    if (t >= 16.2) {
      drawBlanket(ctx, onBasket.map((p, i) => [p[0], p[1] - (i < 3 ? 6 * bump(16.2, 16.6, t) : 0)]), false, 0.7);
      // 子犬の顔はブランケットから出す
      kinakoHead(ctx, pup);
      chimakiBody(ctx, ch); chimakiHead(ctx, ch);
    }
    // zzz
    if (t > 22.3) {
      for (let k = 0; k < 3; k++) {
        const ph = ((t - 22.3) * 0.6 + k / 3) % 1;
        ctx.save(); ctx.globalAlpha = Math.sin(ph * Math.PI) * 0.8; ctx.fillStyle = '#6a4a2a'; ctx.font = `700 ${14 + ph * 12}px ${FONT}`;
        ctx.fillText('z', 690 + ph * 40 + k * 4, 540 - ph * 70); ctx.restore();
      }
    }
  }

  // 現在：嵐の夜 → 恩返し
  function sceneStorm(ctx, t) {
    const worn = true;
    const seatBl = [[800, 486], [880, 470], [960, 482], [965, 540], [930, 580], [820, 584], [790, 550]];
    const hanging = (x, y) => [[x - 18, y + 4], [x + 18, y + 4], [x + 30, y + 40], [x + 26, y + 90], [x, y + 100], [x - 26, y + 88], [x - 28, y + 40]];
    const cover = [[425, 284], [560, 264], [750, 270], [800, 330], [780, 400], [560, 392], [415, 382]];

    const ch = { x: 560, y: 262, s: 0.82, age: 1, tt: t, blink: blinkOpen(t, 0.4), mouth: mouthOf('chimaki', t), lookX: 0.5, lookY: 0.4 };
    let tremble = 0;
    if (t > 26.8) tremble = 0.5 + 0.5 * ss(26.8, 27.4, t);
    if (t > 34) tremble = 1.4;
    if (t > 40.2) tremble = 1.4 * (1 - ss(40.2, 42.5, t)) + 0.15 * (1 - ss(44, 46, t));
    ch.shake = Math.sin(t * 70) * 1.8 * tremble;
    ch.earFlat = clamp(tremble * 0.8) * (t > 44 ? 1 - ss(44, 46, t) : 1);
    ch.eyes = t > 27 ? 'scared' : 'normal';
    if (t > 31 && t < 34) { ch.eyes = 'worried'; ch.lookX = 0.8; ch.lookY = 1; }
    if (t > 34 && t < 35.3) { ch.eyes = 'squeeze'; ch.y -= 12 * bump(34, 34.35, t); }
    if (t > 35.3) { ch.eyes = 'scared'; ch.tears = ss(35.3, 36, t); }
    if (t > 40.2) { ch.eyes = 'surprised'; ch.lookX = 1; ch.lookY = 0.2; ch.tears = 0.6; }
    if (t > 44.4) { ch.eyes = 'normal'; ch.tears = 1; ch.smile = ss(45.5, 46.5, t); ch.lookX = 0.9; }
    if (t > 46.0) { ch.drop = inv(46.0, 47.4, t); }
    if (t > 46.8) { ch.eyes = 'happy'; ch.rot = 0.1 * ss(46.8, 47.6, t); ch.blush = 1; }

    const ki = { x: 800, y: 438, s: 0.82, pose: 'loaf', tt: t, blink: blinkOpen(t, 1.9), mouth: mouthOf('kinako', t), lookX: -0.9, lookY: -1.2 };
    ki.eyes = t > 27.2 ? 'worried' : 'normal';
    if (t < 27.2) { ki.lookX = 0.3; ki.lookY = -0.2; }
    if (t > 34 && t < 35) ki.eyes = 'surprised';
    if (t > 35.6) { ki.eyes = 'normal'; }
    let carry = false, landed = false;
    // 毛布をくわえに行く
    if (t > 36.6 && t < 38.0) { const k = easeInOut(inv(36.6, 37.4, t)); ki.x = lerp(800, 860, k); ki.y = lerp(438, 452, k); ki.lookX = 0.6; ki.lookY = 1; ki.rot = 0.15 * k; }
    if (t >= 37.4) carry = true;
    if (t >= 38.0) {
      ki.rot = 0; ki.lookX = -0.9; ki.lookY = -1; ki.eyes = 'normal';
      const P0 = { x: 860, y: 452 }, P1 = { x: 780, y: 360 }, P2 = { x: 705, y: 262 };
      if (t < 39.4) { const k = easeInOut(inv(38.4, 38.8, t)); ki.x = lerp(P0.x, P1.x, k); ki.y = lerp(P0.y, P1.y, k) - 50 * Math.sin(Math.PI * k); }
      else { const k = easeInOut(inv(39.4, 39.8, t)); ki.x = lerp(P1.x, P2.x, k); ki.y = lerp(P1.y, P2.y, k) - 50 * Math.sin(Math.PI * k); }
      if (t > 39.8) landed = true;
    }
    if (t > 40.2) { ki.eyes = 'normal'; ki.lookX = -1; ki.lookY = 0.2; ki.smile = 0.6; }
    if (t > 44.4) { ki.eyes = lineAt('kinako', t) ? 'normal' : 'happy'; ki.smile = 1; ki.rot = -0.14 * ss(45, 46.5, t); ki.x = lerp(705, 690, ss(45, 46.5, t)); ki.blush = ss(45, 46, t); }
    if (t > 46.8) ki.eyes = 'sleep';

    // 描画
    if (!carry) drawBlanket(ctx, seatBl, worn, 0.35);
    chimakiBody(ctx, ch);
    const covering = t >= 39.8;
    if (!covering || t < 40.35) kinakoBody(ctx, ki);
    if (carry && !covering) {
      const hx = ki.x, hy = ki.y - 4;
      const grab = t < 38.0 ? ss(37.4, 38.0, t) : 1;
      drawBlanket(ctx, lerpPts(seatBl, hanging(hx, hy + 8), grab), worn, 0.35);
    }
    if (covering) {
      const k = easeOut(inv(39.8, 40.35, t));
      const from = hanging(ki.x, ki.y + 4);
      drawBlanket(ctx, lerpPts(from, cover, k), worn, 0.35);
    }
    chimakiHead(ctx, ch);
    kinakoHead(ctx, ki);
    // ハートのきらめき
    if (t > 46.6) {
      for (let k = 0; k < 4; k++) {
        const ph = ((t - 46.6) * 0.5 + k / 4) % 1;
        const hx = 625 + Math.sin(k * 5 + t) * 30, hy = 200 - ph * 70;
        ctx.save(); ctx.globalAlpha = Math.sin(ph * Math.PI) * 0.8; ctx.fillStyle = '#ff8fa6';
        ctx.translate(hx, hy); ctx.scale(0.6 + ph * 0.3, 0.6 + ph * 0.3);
        ctx.beginPath(); ctx.moveTo(0, 6); ctx.bezierCurveTo(-12, -2, -6, -12, 0, -5); ctx.bezierCurveTo(6, -12, 12, -2, 0, 6); ctx.fill(); ctx.restore();
      }
    }
  }

  // ---------- 仕上げ ----------
  let OFF = null;
  function offscreen(w, h) {
    if (!OFF) OFF = document.createElement('canvas');
    if (OFF.width !== w || OFF.height !== h) { OFF.width = w; OFF.height = h; }
    return OFF;
  }
  const TRANS = [
    { t0: 8.8, t1: 10.2, a: 'day', b: 'flash' },
    { t0: 23.6, t1: 25.4, a: 'flash', b: 'storm' },
    { t0: 47.4, t1: 48.8, a: 'storm', b: 'morning' },
  ];
  function sceneAt(t) { return t < 9.5 ? 'day' : t < 24.5 ? 'flash' : t < 48 ? 'storm' : 'morning'; }

  function render(ctx, t, scale = 1) {
    t = clamp(t, 0, DUR - 1e-6);
    ctx.save(); ctx.setTransform(scale, 0, 0, scale, 0, 0);
    const tr = TRANS.find(x => t >= x.t0 && t < x.t1);
    if (tr) {
      drawScene(ctx, t, tr.a);
      const oc = offscreen(ctx.canvas.width, ctx.canvas.height), ox = oc.getContext('2d');
      ox.setTransform(scale, 0, 0, scale, 0, 0);
      drawScene(ox, t, tr.b);
      const k = easeInOut(inv(tr.t0, tr.t1, t));
      ctx.save(); ctx.setTransform(1, 0, 0, 1, 0, 0); ctx.globalAlpha = k; ctx.drawImage(oc, 0, 0); ctx.restore();
      // 回想の出入りはふわっと光る
      if (tr.a === 'flash' || tr.b === 'flash') {
        const b = Math.sin(Math.PI * k) * 0.55;
        const g = ctx.createRadialGradient(W / 2, H / 2, 0, W / 2, H / 2, W * 0.7);
        g.addColorStop(0, `rgba(255,248,230,${b})`); g.addColorStop(1, `rgba(255,248,230,${b * 0.3})`);
        ctx.fillStyle = g; ctx.fillRect(0, 0, W, H);
      }
    } else {
      drawScene(ctx, t, sceneAt(t));
    }

    // ビネット
    const vg = ctx.createRadialGradient(W / 2, H / 2, H * 0.4, W / 2, H / 2, H);
    vg.addColorStop(0, 'rgba(20,10,0,0)'); vg.addColorStop(1, 'rgba(20,10,0,0.38)');
    ctx.fillStyle = vg; ctx.fillRect(0, 0, W, H);

    if (t >= 55) drawEnding(ctx, t, scale);
    drawSubtitles(ctx, t);

    let black = 0;
    if (t < 1.0) black = 1 - easeOut(inv(0, 1.0, t));
    if (t > 59.1) black = inv(59.1, 60, t);
    if (black > 0) { ctx.fillStyle = `rgba(0,0,0,${black})`; ctx.fillRect(0, 0, W, H); }
    ctx.restore();
  }

  function drawEnding(ctx, t, scale) {
    // 背景を暗く・ぼかし気味に
    const d = ss(55.3, 56.6, t);
    ctx.fillStyle = `rgba(40,24,10,${0.55 * d})`; ctx.fillRect(0, 0, W, H);
    // ポラロイド
    const k = easeOut(inv(55.4, 56.8, t));
    const photo = global.DOG_PHOTO;
    const ph = 470, pw = photo ? ph * photo.width / photo.height : 352;
    ctx.save();
    ctx.translate(lerp(400, 400, k), lerp(980, 350, k));
    ctx.rotate(lerp(-0.2, -0.05, k));
    ctx.shadowColor = 'rgba(0,0,0,0.45)'; ctx.shadowBlur = 30; ctx.shadowOffsetY = 12;
    ctx.fillStyle = '#fbf8f1'; ctx.fillRect(-pw / 2 - 18, -ph / 2 - 18, pw + 36, ph + 100);
    ctx.shadowColor = 'transparent';
    // 写真は現像されるように浮かび上がる
    const dev = ss(56.0, 57.6, t);
    ctx.fillStyle = '#2a2622'; ctx.fillRect(-pw / 2, -ph / 2, pw, ph);
    if (photo) { ctx.globalAlpha = dev; ctx.drawImage(photo, -pw / 2, -ph / 2, pw, ph); ctx.globalAlpha = 1; }
    ctx.fillStyle = '#4a3a2e'; ctx.font = `600 30px ${HAND}`; ctx.textAlign = 'center';
    ctx.globalAlpha = ss(57.2, 58, t);
    ctx.fillText('ちまき ＆ きなこ', 0, ph / 2 + 56);
    ctx.restore();
    // タイトル
    const a = ss(57.0, 58.2, t);
    if (a > 0) {
      ctx.save(); ctx.globalAlpha = a; ctx.textAlign = 'center';
      ctx.shadowColor = 'rgba(255,200,140,0.7)'; ctx.shadowBlur = 24;
      ctx.fillStyle = '#fff8ec'; ctx.font = `700 64px ${FONT}`;
      ctx.fillText('いつも、', 900, 300);
      ctx.fillText('となりに。', 930, 385);
      ctx.shadowBlur = 0; ctx.font = `500 22px ${FONT}`; ctx.fillStyle = 'rgba(255,240,220,0.9)';
      ctx.fillText('〜 ちまきと、きなこ 〜', 915, 440);
      ctx.restore();
    }
    const c = ss(58.0, 58.6, t);
    if (c > 0) {
      ctx.save(); ctx.globalAlpha = c * 0.85; ctx.textAlign = 'center'; ctx.font = `500 14px ${FONT}`; ctx.fillStyle = '#fff1e0';
      ctx.fillText(global.ANIM_CREDIT || '声：VOICEVOX:玄野武宏 / VOICEVOX:雨晴はう　｜　脚本・作画・音楽：Claude（すべてコードで生成）', 915, 690);
      ctx.restore();
    }
    // シャッターの閃光
    if (t < 55.7) {
      const f = t < 55.06 ? inv(55.0, 55.06, t) : 1 - inv(55.06, 55.7, t);
      ctx.fillStyle = `rgba(255,255,255,${f})`; ctx.fillRect(0, 0, W, H);
    }
  }

  function drawSubtitles(ctx, t) {
    for (const L of LINES) {
      const d = lineDur(L), a = inv(L.t - 0.12, L.t + 0.05, t) * (1 - inv(L.t + d + 0.15, L.t + d + 0.45, t));
      if (a <= 0) continue;
      ctx.save(); ctx.globalAlpha = a; ctx.textAlign = 'center';
      ctx.font = `700 34px ${FONT}`;
      const y = 668;
      ctx.lineJoin = 'round'; ctx.lineWidth = 8; ctx.strokeStyle = 'rgba(30,18,8,0.85)';
      ctx.strokeText(L.text, W / 2, y); ctx.fillStyle = '#fff'; ctx.fillText(L.text, W / 2, y);
      const tw = ctx.measureText(L.text).width;
      ctx.font = `700 20px ${FONT}`; ctx.textAlign = 'left';
      ctx.lineWidth = 6; ctx.strokeText(NAMES[L.who], W / 2 - tw / 2, y - 44);
      ctx.fillStyle = NAME_COL[L.who]; ctx.fillText(NAMES[L.who], W / 2 - tw / 2, y - 44);
      ctx.restore();
    }
  }

  global.ANIM = { W, H, FPS, DUR, render, LINES };
})(typeof window !== 'undefined' ? window : globalThis);
