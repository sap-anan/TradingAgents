"""PowerFactory-style HTML5 Canvas renderer for architecture monitoring diagram."""

import json
from typing import Dict, List


def render_architecture_html(
    events: List[Dict],
    node_statuses: Dict[str, str],
    width: int = 1400,
    height: int = 800,
) -> str:
    """Return a complete HTML string with an interactive architecture diagram.

    The canvas is fully responsive — it fills the container width and
    dynamically rescales its backing store on zoom so rendering stays
    crisp at any zoom level. Supports pan (drag) and zoom (scroll).
    """
    events_json = json.dumps(events)
    statuses_json = json.dumps(node_statuses)

    return f"""<!DOCTYPE html>
<html><head><meta charset="utf-8">
<style>
* {{ margin:0; padding:0; box-sizing:border-box; }}
html, body {{ width:100%; height:100%; background:#0f1218; overflow:hidden;
  font-family:Consolas,Monaco,monospace; }}
canvas {{ display:block; width:100%; height:{height}px; cursor:grab; }}
canvas:active {{ cursor:grabbing; }}
#tooltip {{
  display:none; position:absolute; background:#1c2030; border:1px solid #3a4560;
  border-radius:6px; padding:8px 12px; color:#c0c8d8; font-size:11px;
  pointer-events:none; z-index:10; max-width:260px; line-height:1.5;
  box-shadow: 0 4px 16px rgba(0,0,0,0.6);
}}
#zoom-badge {{
  position:absolute; bottom:8px; right:12px; color:#4a5568; font-size:10px;
  font-family:Consolas,Monaco,monospace; pointer-events:none;
}}
</style></head><body>
<canvas id="c"></canvas>
<div id="tooltip"></div>
<div id="zoom-badge"></div>
<script>
(function() {{
  const EVENTS = {events_json};
  const STATUSES = {statuses_json};

  const canvas = document.getElementById('c');
  const ctx = canvas.getContext('2d');
  const tooltip = document.getElementById('tooltip');
  const zoomBadge = document.getElementById('zoom-badge');

  // ── Responsive canvas sizing ──
  let W = {width}, H = {height}, dpr = window.devicePixelRatio || 1;
  function resizeCanvas() {{
    dpr = window.devicePixelRatio || 1;
    // Use container size if available, otherwise fallback to defaults
    const cw = canvas.clientWidth || canvas.parentElement.clientWidth || {width};
    const ch = canvas.clientHeight || canvas.parentElement.clientHeight || {height};
    if (cw > 0) W = cw;
    if (ch > 0) H = ch;
    // Scale backing store for crisp rendering at current zoom
    const backingScale = dpr * Math.max(1, zoom);
    canvas.width = W * backingScale;
    canvas.height = H * backingScale;
    ctx.setTransform(backingScale, 0, 0, backingScale, 0, 0);
  }}
  // Delay initial resize to let iframe layout complete
  resizeCanvas();
  setTimeout(resizeCanvas, 100);
  setTimeout(resizeCanvas, 500);
  window.addEventListener('resize', resizeCanvas);

  // ── Pan / Zoom ──
  let panX = 0, panY = 0, zoom = 1;
  let dragging = false, dragStartX = 0, dragStartY = 0, panStartX = 0, panStartY = 0;

  canvas.addEventListener('mousedown', e => {{
    dragging = true; dragStartX = e.clientX; dragStartY = e.clientY;
    panStartX = panX; panStartY = panY;
  }});
  canvas.addEventListener('mousemove', e => {{
    if (dragging) {{
      panX = panStartX + (e.clientX - dragStartX);
      panY = panStartY + (e.clientY - dragStartY);
    }}
    handleHover(e);
  }});
  canvas.addEventListener('mouseup', () => {{ dragging = false; }});
  canvas.addEventListener('mouseleave', () => {{ dragging = false; tooltip.style.display='none'; }});
  canvas.addEventListener('wheel', e => {{
    e.preventDefault();
    const factor = e.deltaY < 0 ? 1.1 : 1/1.1;
    const newZoom = Math.max(0.2, Math.min(5, zoom * factor));
    // Zoom toward mouse pointer
    const rect = canvas.getBoundingClientRect();
    const mx = e.clientX - rect.left, my = e.clientY - rect.top;
    panX = mx - (mx - panX) * (newZoom / zoom);
    panY = my - (my - panY) * (newZoom / zoom);
    zoom = newZoom;
    // Resize backing store for crisp rendering at new zoom level
    resizeCanvas();
  }}, {{ passive: false }});

  // ── Node definitions ──
  const nodes = [
    {{ id:'market_data', label:'MARKET DATA', sub:['Bitkub WS','REST API'], color:'#4a9eff', x:80, y:300, w:180, h:120 }},
    {{ id:'fundamental', label:'FUNDAMENTAL', sub:['Valuation','Growth','Catalyst'], color:'#00c853', x:380, y:100, w:180, h:130 }},
    {{ id:'technical', label:'TECHNICAL', sub:['RSI(14)','MACD','Bollinger'], color:'#00c853', x:380, y:280, w:180, h:130 }},
    {{ id:'sentiment', label:'SENTIMENT', sub:['News NLP','Social'], color:'#00c853', x:380, y:460, w:180, h:120 }},
    {{ id:'debate', label:'DEBATE ENGINE', sub:['Bull Agent','Bear Agent','Moderator'], color:'#ff9100', x:700, y:260, w:190, h:140 }},
    {{ id:'risk_manager', label:'RISK MANAGER', sub:['Position','Exposure','Stop-Loss'], color:'#ff1744', x:1000, y:280, w:180, h:130 }},
    {{ id:'broker', label:'BROKER', sub:['Order Exec'], color:'#aa00ff', x:1250, y:310, w:140, h:90 }},
    {{ id:'llm', label:'LLM PROVIDER', sub:['Gemini','DeepSeek'], color:'#00e5ff', x:550, y:580, w:170, h:100 }}
  ];
  const nodeMap = {{}};
  nodes.forEach(n => nodeMap[n.id] = n);

  // ── Connections ──
  const connections = [
    {{ from:'market_data', to:'fundamental', signal:'price[]' }},
    {{ from:'market_data', to:'technical', signal:'ohlcv[]' }},
    {{ from:'market_data', to:'sentiment', signal:'price[]' }},
    {{ from:'fundamental', to:'debate', signal:'score' }},
    {{ from:'technical', to:'debate', signal:'score' }},
    {{ from:'sentiment', to:'debate', signal:'score' }},
    {{ from:'debate', to:'risk_manager', signal:'decision' }},
    {{ from:'risk_manager', to:'broker', signal:'order' }},
    {{ from:'llm', to:'fundamental', signal:'response' }},
    {{ from:'llm', to:'technical', signal:'response' }},
    {{ from:'llm', to:'sentiment', signal:'response' }},
    {{ from:'llm', to:'debate', signal:'response' }}
  ];

  // ── Particle system ──
  let particles = [];
  function spawnParticle(conn) {{
    particles.push({{ conn, t: 0, speed: 0.003 + Math.random()*0.004 }});
  }}
  let spawnTimer = 0;

  // ── Derive live values from events ──
  function latestSignalValue(signal) {{
    for (let i = EVENTS.length - 1; i >= 0; i--) {{
      if (EVENTS[i].signal === signal && EVENTS[i].value !== undefined) return EVENTS[i].value;
    }}
    return null;
  }}
  function latestNodeLatency(nodeId) {{
    for (let i = EVENTS.length - 1; i >= 0; i--) {{
      if (EVENTS[i].source === nodeId && EVENTS[i].latency_ms !== undefined) return EVENTS[i].latency_ms;
    }}
    return null;
  }}
  function nodeStatus(id) {{
    return STATUSES[id] || 'idle';
  }}

  // ── Terminal positions ──
  function outTerminal(n, idx, total) {{
    const spacing = n.h / (total + 1);
    return {{ x: n.x + n.w, y: n.y + spacing * (idx + 1) }};
  }}
  function inTerminal(n, idx, total) {{
    const spacing = n.h / (total + 1);
    return {{ x: n.x, y: n.y + spacing * (idx + 1) }};
  }}

  // Pre-compute terminal indices
  connections.forEach(c => {{
    const outsFrom = connections.filter(x => x.from === c.from);
    const insTo = connections.filter(x => x.to === c.to);
    c.outIdx = outsFrom.indexOf(c);
    c.outTotal = outsFrom.length;
    c.inIdx = insTo.indexOf(c);
    c.inTotal = insTo.length;
  }});

  // ── Bezier helper ──
  function bezierPt(p0, p1, p2, p3, t) {{
    const u=1-t;
    return {{
      x: u*u*u*p0.x + 3*u*u*t*p1.x + 3*u*t*t*p2.x + t*t*t*p3.x,
      y: u*u*u*p0.y + 3*u*u*t*p1.y + 3*u*t*t*p2.y + t*t*t*p3.y
    }};
  }}

  function connPoints(c) {{
    const fn = nodeMap[c.from], tn = nodeMap[c.to];
    const p0 = outTerminal(fn, c.outIdx, c.outTotal);
    const p3 = inTerminal(tn, c.inIdx, c.inTotal);
    const dx = Math.abs(p3.x - p0.x) * 0.45;
    const p1 = {{ x: p0.x + dx, y: p0.y }};
    const p2 = {{ x: p3.x - dx, y: p3.y }};
    return [p0, p1, p2, p3];
  }}

  // ── Status color ──
  function statusColor(s) {{
    if (s === 'running' || s === 'ok' || s === 'pass') return '#00e676';
    if (s === 'error' || s === 'reject') return '#ff1744';
    return '#555';
  }}

  // ── Hover detection ──
  function handleHover(e) {{
    const rect = canvas.getBoundingClientRect();
    const mx = (e.clientX - rect.left - panX) / zoom;
    const my = (e.clientY - rect.top - panY) / zoom;
    let hit = null;
    for (const n of nodes) {{
      if (mx >= n.x && mx <= n.x+n.w && my >= n.y && my <= n.y+n.h) {{ hit = n; break; }}
    }}
    if (hit) {{
      const st = nodeStatus(hit.id);
      const lat = latestNodeLatency(hit.id);
      tooltip.innerHTML = '<b>'+hit.label+'</b><br>Status: '+st
        +(lat!==null?'<br>Latency: '+lat+'ms':'')
        +'<br>Sub: '+hit.sub.join(', ');
      tooltip.style.display = 'block';
      tooltip.style.left = (e.clientX+12)+'px';
      tooltip.style.top = (e.clientY+12)+'px';
    }} else {{
      tooltip.style.display = 'none';
    }}
  }}

  // ── Draw ──
  function draw() {{
    // Reset transform and clear entire backing store
    const backingScale = dpr * Math.max(1, zoom);
    ctx.setTransform(backingScale, 0, 0, backingScale, 0, 0);
    ctx.clearRect(0, 0, W, H);

    // Background
    ctx.fillStyle = '#0f1218';
    ctx.fillRect(0, 0, W, H);

    // Apply pan/zoom
    ctx.translate(panX, panY);
    ctx.scale(zoom, zoom);

    // Dot grid — compute visible area in world coords and only draw visible dots
    const visX0 = -panX / zoom - 100;
    const visY0 = -panY / zoom - 100;
    const visX1 = (W - panX) / zoom + 100;
    const visY1 = (H - panY) / zoom + 100;
    const gridStep = 30;
    ctx.fillStyle = '#1a1f2a';
    const gx0 = Math.floor(visX0/gridStep)*gridStep;
    const gy0 = Math.floor(visY0/gridStep)*gridStep;
    for (let gx=gx0; gx<visX1; gx+=gridStep) {{
      for (let gy=gy0; gy<visY1; gy+=gridStep) {{
        ctx.fillRect(gx, gy, 1, 1);
      }}
    }}

    // ── Connections ──
    connections.forEach(c => {{
      const [p0,p1,p2,p3] = connPoints(c);
      ctx.beginPath();
      ctx.moveTo(p0.x, p0.y);
      ctx.bezierCurveTo(p1.x,p1.y,p2.x,p2.y,p3.x,p3.y);
      ctx.strokeStyle = '#4a5568';
      ctx.lineWidth = 1.5;
      ctx.stroke();

      // Arrow
      const tip = p3;
      const near = bezierPt(p0,p1,p2,p3, 0.96);
      const angle = Math.atan2(tip.y-near.y, tip.x-near.x);
      ctx.beginPath();
      ctx.moveTo(tip.x, tip.y);
      ctx.lineTo(tip.x - 8*Math.cos(angle-0.35), tip.y - 8*Math.sin(angle-0.35));
      ctx.lineTo(tip.x - 8*Math.cos(angle+0.35), tip.y - 8*Math.sin(angle+0.35));
      ctx.closePath();
      ctx.fillStyle = '#4a5568';
      ctx.fill();

      // Signal label + value
      const mid = bezierPt(p0,p1,p2,p3, 0.5);
      const val = latestSignalValue(c.signal);
      const txt = val !== null ? c.signal+'='+val : c.signal;
      ctx.font = '11px Consolas,Monaco,monospace';
      ctx.fillStyle = '#c0c8d8';
      ctx.fillText(txt, mid.x - ctx.measureText(txt).width/2, mid.y - 6);
    }});

    // ── Particles ──
    spawnTimer++;
    if (spawnTimer % 30 === 0) {{
      const ci = Math.floor(Math.random()*connections.length);
      spawnParticle(connections[ci]);
    }}
    particles.forEach(p => {{
      p.t += p.speed;
      const [p0,p1,p2,p3] = connPoints(p.conn);
      const pt = bezierPt(p0,p1,p2,p3, p.t);
      ctx.beginPath();
      ctx.arc(pt.x, pt.y, 3, 0, Math.PI*2);
      ctx.fillStyle = '#00e676';
      ctx.shadowColor = '#00e676';
      ctx.shadowBlur = 6;
      ctx.fill();
      ctx.shadowBlur = 0;
    }});
    particles = particles.filter(p => p.t < 1);

    // ── Nodes ──
    nodes.forEach(n => {{
      const r = 6;
      // Body
      ctx.fillStyle = '#1c2030';
      ctx.strokeStyle = '#3a4560';
      ctx.lineWidth = 1;
      ctx.beginPath();
      ctx.roundRect(n.x, n.y, n.w, n.h, r);
      ctx.fill();
      ctx.stroke();

      // Header bar
      const hh = 26;
      ctx.save();
      ctx.beginPath();
      ctx.roundRect(n.x, n.y, n.w, hh, [r,r,0,0]);
      ctx.clip();
      ctx.fillStyle = n.color;
      ctx.fillRect(n.x, n.y, n.w, hh);
      ctx.restore();

      ctx.font = 'bold 11px Consolas,Monaco,monospace';
      ctx.fillStyle = '#0f1218';
      ctx.fillText(n.label, n.x + 8, n.y + 17);

      // Sub-blocks
      const subTop = n.y + hh + 6;
      const subH = 18, subGap = 4, subPad = 8;
      n.sub.forEach((s, i) => {{
        const sy = subTop + i * (subH + subGap);
        ctx.fillStyle = '#252b3d';
        ctx.beginPath();
        ctx.roundRect(n.x + subPad, sy, n.w - subPad*2, subH, 3);
        ctx.fill();
        ctx.font = '10px Consolas,Monaco,monospace';
        ctx.fillStyle = '#8892a8';
        ctx.fillText(s, n.x + subPad + 6, sy + 13);
      }});

      // Terminals — inputs (left)
      const insCount = connections.filter(c => c.to === n.id).length;
      for (let i=0; i<insCount; i++) {{
        const tp = inTerminal(n, i, insCount);
        ctx.beginPath(); ctx.arc(tp.x, tp.y, 4, 0, Math.PI*2);
        ctx.fillStyle = '#3a4560'; ctx.fill();
      }}
      // Terminals — outputs (right)
      const outsCount = connections.filter(c => c.from === n.id).length;
      for (let i=0; i<outsCount; i++) {{
        const tp = outTerminal(n, i, outsCount);
        ctx.beginPath(); ctx.arc(tp.x, tp.y, 4, 0, Math.PI*2);
        ctx.fillStyle = '#3a4560'; ctx.fill();
      }}

      // Status dot
      const st = nodeStatus(n.id);
      const sc = statusColor(st);
      ctx.beginPath();
      ctx.arc(n.x + 10, n.y + n.h - 10, 4, 0, Math.PI*2);
      ctx.fillStyle = sc;
      if (sc === '#00e676') {{ ctx.shadowColor = sc; ctx.shadowBlur = 8; }}
      ctx.fill();
      ctx.shadowBlur = 0;

      // Perf label
      const lat = latestNodeLatency(n.id);
      const perfTxt = st + (lat !== null ? ' \\u00b7 ' + lat + 'ms' : '');
      ctx.font = '9px Consolas,Monaco,monospace';
      ctx.fillStyle = '#6b7280';
      ctx.fillText(perfTxt, n.x + 20, n.y + n.h - 6);
    }});

    ctx.setTransform(1,0,0,1,0,0);
    // Zoom badge (screen space)
    zoomBadge.textContent = (zoom*100).toFixed(0) + '%';

    requestAnimationFrame(draw);
  }}

  requestAnimationFrame(draw);
}})();
</script></body></html>"""
