import os
import sys
import base64
from pathlib import Path

sys.stdout.reconfigure(encoding='utf-8')

project_root = Path(__file__).resolve().parent.parent
docs_dir = project_root / "docs"
assets_dir = docs_dir / "assets"

def get_base64_img(filename):
    p = assets_dir / filename
    if not p.exists():
        return ""
    with open(p, "rb") as f:
        data = f.read()
    b64 = base64.b64encode(data).decode("ascii")
    return f"data:image/png;base64,{b64}"

b64_header = get_base64_img("doc_interactive_header.png")
b64_dlg = get_base64_img("doc_compute_cache_dialog.png")
b64_insp = get_base64_img("doc_right_panel_inspector.png")
b64_gallery = get_base64_img("doc_left_gallery_modes.png")
b64_viewer = get_base64_img("doc_plot_viewer.png")

# -------------------------------------------------------------
# 1. BUILD HOW_TO_USE.md
# -------------------------------------------------------------
md_content = """# 🚀 Many-Body Studio Pro: User & Feature Guide

A visual, 2–5 minute practical guide to navigating **Many-Body Studio Pro**. Rather than a rigid sequence, this guide is divided into three focused sections:

1. [Section 1: ⚡ Interactive Plots Viewport](#section-1--interactive-plots-viewport)
2. [Section 2: ⚙️ Right Panel (Parameter Inspector & Job Execution)](#section-2-️-right-panel-parameter-inspector--job-execution)
3. [Section 3: 📊 Plot Viewer Viewport & Left Panel](#section-3--plot-viewer-viewport--left-panel)

---

## Workspace Architecture Overview
* **Global Workspace**:
  * `[ 🔬 Simulation Studio ]`: Full numerical physics modeling, batch queueing, and dataset generation.
  * *(Note: Standalone Figure Composer workspace plan was scrapped in favor of direct integrated viewports).*
* **Central Viewports** (Center Header Bar):
  * `[ 📊 Plot Viewer ]`: High-DPI zoomable plot canvas with split-view comparison and direct PNG export.
  * `[ ⚡ Interactive Plots ]`: Instant 60 FPS analytical scaling, k-probing, and real-time sliders.

---

## Section 1: ⚡ Interactive Plots Viewport
Switch to this viewport by clicking **`[ ⚡ Interactive Plots ]`** on the central header bar.

![Interactive Plots Header](./assets/doc_interactive_header.png)
*Figure 1.1: The Interactive Plots control strip with Viewport switcher.*
* **① Viewport Switcher**: Toggle to `[ ⚡ Interactive Plots ]` (highlighted in blue).
* **② Mode Selector**: Choose from 6 analytical experiment modes.
* **③ Cache Selector**: Select an existing pre-computed foundation array (filter by chemical potential $\\mu$).
* **④ ▶ Compute Cache**: Open the direct dialog if no cache exists or if you need a new regime.
* **⑤ Continuous $J_K$ Slider**: Drag to scale the Kondo coupling continuously at 60 FPS.

---

### 1.1 Mode Selection
Select an analytical mode from the **Mode** dropdown:
1. **Brillouin Zone $k$-Probe**: Click or drag anywhere in $[-\\pi, \\pi]^2$ to evaluate spectral function $A(\\mathbf{k}, \\omega)$, $\\text{Re}\\,\\Sigma$, and $\\text{Im}\\,\\Sigma$ in $<1\\text{ ms}$.
2. **Fermi Surface & Energy Slice**: Dynamically sweep energy $\\omega$ to watch Fermi surface warping and gap openings.
3. **Band Dispersion**: Track quasiparticle dispersions along high-symmetry paths ($\\Gamma \\to X \\to M \\to \\Gamma$).
4. **Static RPA Susceptibility**: 2D momentum map of bare and RPA-enhanced magnetic susceptibility $\\chi(\\mathbf{q})$.
5. **Dynamic Susceptibility**: Frequency-dependent magnetic response $\\chi(\\mathbf{q}, \\omega)$.
6. **Electrical Conductivity**: Real-time optical and DC conductivity $\\sigma(\\omega)$.

---

### 1.2 Foundation Cache & The "▶ Compute Cache" Dialog
The real-time engine requires a pre-computed base array (`results/cache/`). If none is loaded, click the blue **`▶ Compute Cache`** button:

<div align="center">
  <img src="./assets/doc_compute_cache_dialog.png" width="440" alt="Compute Cache Dialog">
</div>

*Figure 1.2: In-situ Compute Cache dialog.*
* **① Target Selector**: Choose what foundation array to compute:
  * *Self-Energy $\\Sigma(\\mathbf{k}, \\omega)$* (1-loop + 3-loop FFT convolutions)
  * *Bare Static Susceptibility $\\chi_0(\\mathbf{q})$*
  * *Bare Dynamic Susceptibility $\\chi_0(\\mathbf{q}, \\omega)$*
* **② Cache Parameters**: Set chemical potential $\\mu$, interlayer coupling $J_\\perp$, and grid resolution $N$.
* **③ Compute Cache Button**: Starts the calculation immediately in the background (~0.3–2s on GPU) and auto-loads into the interactive canvas upon completion.

---

### 1.3 Mode-Specific Sliders & Real-Time Controls
Row 2 adapts dynamically based on the active mode:
* **Universal Coupling ($J_K$)**: A continuous slider ($0.5$ to $12.0\\text{ eV}$) with 60 FPS analytical scaling.
* **$k$-Probe Controls**: Select standard high-symmetry points (`Antinodal`, `Nodal`, `Center Γ`, `Corner M`, `Custom`) or click directly on the 2D map.
* **Energy Slice ($\\\\omega$) Slider**: Available in Fermi Surface mode; sweeps slice energy from $-2.0\\text{ eV}$ to $+2.0\\text{ eV}$.
* **Susceptibility ($J_\\perp$) Slider & $K$ Selector**: Available in RPA Susceptibility modes; controls interlayer coupling ($4.01 - 12.00\\text{ eV}$) and exchange channel ($+1$ AFM vs. $-1$ FM).
* **Electrical Conductivity Device**: Switch between `Auto`, `GPU (CUDA)`, or `CPU (Multi-core)`.

---

## Section 2: ⚙️ Right Panel (Parameter Inspector & Job Execution)
The Right Dock is split into two balanced halves to present all cards without excessive vertical scrolling:

![Right Panel Inspector](./assets/doc_right_panel_inspector.png)
*Figure 2.1: The Parameter Inspector & Execution cards (divided side-by-side).*
* **① Active Study Selector**: Choose which physics study to configure.
* **② Cache Status Badge**: Real-time detection of pre-computed results (`🟢 Cached` vs `🟡 Uncached`) & Force Recompute.
* **③ Grid & Resolution Presets**: Choose between speed and publication-grade resolution.
* **④ Execution Controls**: `▶ Run Calculation` (green), `⏹ Cancel` (red), and `➕ Queue`.

---

### 2.1 Inspector Cards Overview
* **Part 1 (Left Column — Physics Study & Backend)**:
  * **Active Calculation Study**: Select solver (Spectral Sweep, Quasiparticle Spectral, Phase Diagram, RPA Susceptibility).
  * **Computation & Cache Status**: Real-time cache badge, *Force Recompute* checkbox, and *Cache Manager* button (`🧹 Cache (X MB)`).
  * **Study-Specific Parameters**: Sweep targets ($J_K$ vs. $J_\\perp$), comma-separated values, fixed coupling, and panel layouts.
  * **Compute & Solver Backend**: Switch between *CUDA GPU (RTX 5060 64-bit CuPy)* and *CPU 64-bit* with core throttling ($50\\% - 100\\%$).
* **Part 2 (Right Column — Grid Presets & Execution)**:
  * **Numerical Grid & Presets**: Fast Preview ($64\\times 64$), Standard ($100\\times 100$), High-Res Production ($256\\times 256$), or Custom Grid.
  * **Common Model Hamiltonian**: Set hopping $t$, next-nearest hopping $t'$, chemical potential $\\mu$, and exchange $K$.
  * **Results Output Directory**: Destination folder for plots, caches, and datasets.
  * **Execution Controls**:
    * **`▶ Run Calculation`** (Emerald Green): Dispatches to background child process without freezing GUI.
    * **`⏹ Cancel / Stop`** (Vivid Red): Immediately terminates the calculation.
    * **`➕ Add Active to Queue`**: Enqueues parameter runs for sequential unattended processing.

---

## Section 3: 📊 Plot Viewer Viewport & Left Panel
Switch to this viewport by clicking **`[ 📊 Plot Viewer ]`** on the central header bar.

![Plot Viewer Viewport](./assets/doc_plot_viewer.png)
*Figure 3.1: Central high-DPI plot canvas.*
* **① Viewport Switcher**: Toggle to `[ 📊 Plot Viewer ]`.
* **② High-DPI Canvas**: Interactive zoom, pan, and coordinate tracking.

---

### 3.1 Central Plot Viewer Canvas
* **Smooth Zooming**: Use the **Mouse Scroll Wheel** anywhere on the canvas to zoom in/out on sharp spectral peaks.
* **Panning**: Click and drag with the **Left Mouse Button** to pan across momentum or frequency ranges.
* **🔍 Fit Window**: Click the toolbar button to reset zoom and center the figure.
* **⚏ Split View (Compare)**: Compare two calculation runs side-by-side.
* **Exporting Figures**: Right-click or use toolbar to copy to clipboard (300 DPI) or save as vector `.pdf`, `.svg`, or `.png`.

---

### 3.2 Left Dock: Plot Gallery Browser
The Left Dock ($260\\text{ px}$) provides a browser for all computed runs in the output directory:

![Gallery Modes](./assets/doc_left_gallery_modes.png)
*Figure 3.2: Left Gallery in Thumbnail Card Mode (left) and Compact List Mode (right).*
* **① View Mode Toggle**:
  * **🖼️ Thumbnail Card Mode**: Displays visual preview cards with observable titles, parameter chips, and timestamps.
  * **📋 Compact List Mode**: Dense row layout optimized for scanning through dozens of simulation runs quickly.
* **② Category Pills & Search**:
  * Quick filter pills: `All`, `🌊 Spectral`, `🧲 Susceptibility`, `⚡ Conductivity`.
  * Instant search bar matches parameters (e.g., typing `mu=1.0` or `JK=6.0` filters immediately).

---

### 3.3 Output Directory Structure (`results/`)
All generated simulation files are organized deterministically under the `results/` folder:
* **`results/cache/`**: Pre-computed, bit-groomed 1/8th IBZ foundation arrays (`sigma_base_*.npz`, `chi0_static_*.npz`, `chi0_dynamic_*.npz`).
* **`results/plots/`**: High-resolution publication-ready figures (`.png`, `.pdf`, `.svg`).
* **`results/data/`**: Full raw numerical NumPy datasets (`.npz`) for custom analysis.
"""

with open(docs_dir / "HOW_TO_USE.md", "w", encoding="utf-8") as f:
    f.write(md_content)
print("Generated docs/HOW_TO_USE.md")

# -------------------------------------------------------------
# 2. BUILD HOW_TO_USE.html (Portable Single-File HTML with Base64 Assets)
# -------------------------------------------------------------
html_content = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Many-Body Studio Pro — User & Feature Guide</title>
  <style>
    :root {{
      --bg: #0f172a;
      --surface: #1e293b;
      --surface-hover: #334155;
      --border: #334155;
      --text: #f8fafc;
      --text-muted: #94a3b8;
      --primary: #3b82f6;
      --primary-dark: #2563eb;
      --cyan: #0891b2;
      --emerald: #10b981;
      --red: #ef4444;
      --font: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
    }}
    * {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body {{
      background: var(--bg);
      color: var(--text);
      font-family: var(--font);
      line-height: 1.6;
      display: flex;
    }}
    /* Sidebar Navigation */
    #sidebar {{
      width: 280px;
      height: 100vh;
      position: sticky;
      top: 0;
      background: #090d16;
      border-right: 1px solid var(--border);
      padding: 24px 16px;
      display: flex;
      flex-direction: column;
      gap: 16px;
      overflow-y: auto;
    }}
    .brand {{
      font-size: 16px;
      font-weight: 800;
      color: #ffffff;
      display: flex;
      align-items: center;
      gap: 8px;
    }}
    .brand-subtitle {{
      font-size: 11px;
      color: var(--text-muted);
      font-weight: 500;
    }}
    .nav-group {{
      display: flex;
      flex-direction: column;
      gap: 4px;
    }}
    .nav-title {{
      font-size: 10px;
      font-weight: 700;
      text-transform: uppercase;
      letter-spacing: 0.05em;
      color: #64748b;
      margin-top: 12px;
      margin-bottom: 4px;
      padding-left: 8px;
    }}
    .nav-link {{
      color: var(--text-muted);
      text-decoration: none;
      font-size: 13px;
      font-weight: 500;
      padding: 8px 10px;
      border-radius: 6px;
      transition: all 0.15s;
    }}
    .nav-link:hover, .nav-link.active {{
      background: var(--surface);
      color: #ffffff;
    }}
    /* Main Content */
    #content {{
      flex: 1;
      max-width: 960px;
      padding: 40px 48px;
      margin: 0 auto;
    }}
    h1 {{
      font-size: 28px;
      font-weight: 800;
      color: #ffffff;
      margin-bottom: 8px;
      letter-spacing: -0.02em;
    }}
    .lead {{
      font-size: 15px;
      color: var(--text-muted);
      margin-bottom: 32px;
    }}
    h2 {{
      font-size: 20px;
      font-weight: 700;
      color: #ffffff;
      margin-top: 48px;
      margin-bottom: 16px;
      padding-bottom: 8px;
      border-bottom: 1px solid var(--border);
      display: flex;
      align-items: center;
      gap: 8px;
    }}
    h3 {{
      font-size: 16px;
      font-weight: 600;
      color: #e2e8f0;
      margin-top: 24px;
      margin-bottom: 12px;
    }}
    p {{
      font-size: 14px;
      color: #cbd5e1;
      margin-bottom: 14px;
    }}
    ul, ol {{
      margin-left: 20px;
      margin-bottom: 16px;
      color: #cbd5e1;
      font-size: 14px;
    }}
    li {{ margin-bottom: 6px; }}
    /* Visual Cards & Callouts */
    .feature-card {{
      background: var(--surface);
      border: 1px solid var(--border);
      border-radius: 10px;
      padding: 20px;
      margin: 20px 0;
    }}
    .img-container {{
      background: #020617;
      border: 1px solid var(--border);
      border-radius: 8px;
      padding: 12px;
      text-align: center;
      margin: 16px auto;
    }}
    .img-container.compact-dialog {{
      max-width: 440px;
      margin: 16px auto;
    }}
    .img-container.compact-inspector {{
      max-width: 780px;
      margin: 16px auto;
    }}
    .img-container.compact-gallery {{
      max-width: 660px;
      margin: 16px auto;
    }}
    .img-container img {{
      max-width: 100%;
      height: auto;
      border-radius: 4px;
      display: block;
      margin: 0 auto;
    }}
    .img-caption {{
      font-size: 12px;
      color: var(--text-muted);
      margin-top: 8px;
      text-align: center;
    }}
    .badge-legend {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(240px, 1fr));
      gap: 10px;
      margin-top: 14px;
    }}
    .legend-item {{
      display: flex;
      align-items: flex-start;
      gap: 8px;
      font-size: 12px;
      background: rgba(255, 255, 255, 0.03);
      padding: 8px 10px;
      border-radius: 6px;
      border: 1px solid rgba(255, 255, 255, 0.05);
    }}
    .badge {{
      display: inline-flex;
      align-items: center;
      justify-content: center;
      width: 22px;
      height: 22px;
      border-radius: 50%;
      background: var(--primary);
      color: #ffffff;
      font-size: 11px;
      font-weight: 700;
      flex-shrink: 0;
    }}
    .badge.cyan {{ background: var(--cyan); }}
    .badge.emerald {{ background: var(--emerald); }}
    .pill {{
      display: inline-block;
      padding: 2px 8px;
      border-radius: 4px;
      font-size: 11px;
      font-weight: 600;
      background: rgba(59, 130, 246, 0.15);
      color: #60a5fa;
      border: 1px solid rgba(59, 130, 246, 0.3);
    }}
    .pill.cyan {{
      background: rgba(8, 145, 178, 0.15);
      color: #22d3ee;
      border-color: rgba(8, 145, 178, 0.3);
    }}
    .pill.emerald {{
      background: rgba(16, 185, 129, 0.15);
      color: #34d399;
      border-color: rgba(16, 185, 129, 0.3);
    }}
    code {{
      font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
      font-size: 12px;
      background: rgba(0, 0, 0, 0.3);
      padding: 2px 6px;
      border-radius: 4px;
      color: #93c5fd;
    }}
    /* Print Styles */
    @media print {{
      #sidebar {{ display: none; }}
      body {{ background: #ffffff; color: #000000; }}
      #content {{ max-width: 100%; padding: 0; }}
      h1, h2, h3 {{ color: #000000; }}
      p, li {{ color: #333333; }}
      .feature-card {{ border: 1px solid #cccccc; background: #fafafa; }}
      .img-container {{ background: #ffffff; border: 1px solid #cccccc; }}
    }}
  </style>
</head>
<body>

  <!-- Navigation Sidebar -->
  <div id="sidebar">
    <div class="brand">
      <span>🔬</span>
      <div>
        <div>Many-Body Studio</div>
        <div class="brand-subtitle">Feature & Workflow Guide</div>
      </div>
    </div>

    <div class="nav-group">
      <div class="nav-title">Overview</div>
      <a href="#overview" class="nav-link">Workspace Architecture</a>

      <div class="nav-title">Feature Sections</div>
      <a href="#interactive" class="nav-link">1. ⚡ Interactive Plots</a>
      <a href="#interactive-modes" class="nav-link" style="padding-left: 20px;">• Analytical Modes</a>
      <a href="#compute-cache" class="nav-link" style="padding-left: 20px;">• Compute Cache Dialog</a>
      <a href="#interactive-sliders" class="nav-link" style="padding-left: 20px;">• Mode-Specific Sliders</a>

      <a href="#inspector" class="nav-link">2. ⚙️ Right Panel Inspector</a>
      <a href="#inspector-cards" class="nav-link" style="padding-left: 20px;">• Cards Breakdown (2-Col)</a>
      <a href="#execution-controls" class="nav-link" style="padding-left: 20px;">• Run, Queue & Cancel</a>

      <a href="#viewer" class="nav-link">3. 📊 Plot Viewer & Gallery</a>
      <a href="#viewer-canvas" class="nav-link" style="padding-left: 20px;">• Canvas Zoom & Pan</a>
      <a href="#gallery-modes" class="nav-link" style="padding-left: 20px;">• Cards vs. List Mode</a>
      <a href="#results-layout" class="nav-link" style="padding-left: 20px;">• Storage Layout (results/)</a>
    </div>
  </div>

  <!-- Main Content -->
  <div id="content">
    <h1>Many-Body Studio Pro</h1>
    <p class="lead">A visual reference guide to real-time interactive physics, parameter inspection, and high-DPI plot viewing.</p>

    <!-- ARCHITECTURE OVERVIEW -->
    <div id="overview" class="feature-card">
      <h3>🏛️ Global Architecture: Simulation Studio & Dual Viewports</h3>
      <p>The studio provides a unified, un-cramped scientific layout:</p>
      <ul>
        <li><strong>Simulation Studio</strong>:
          Full-featured numerical physics modeling, background process isolation, and batch execution queue.
          <em>(Note: Standalone Figure Composer workspace plan was scrapped in favor of direct integrated viewports).</em>
        </li>
        <li><strong>Center Header Bar (Dual Viewports)</strong>:
          <span class="pill">📊 Plot Viewer</span> (high-DPI static inspection & PNG export) and
          <span class="pill">⚡ Interactive Plots</span> (instant 60 FPS real-time exploration).
        </li>
      </ul>
    </div>

    <!-- SECTION 1 -->
    <h2 id="interactive">⚡ Section 1: Interactive Plots Viewport</h2>
    <p>Switch to this viewport by clicking <strong><code>[ ⚡ Interactive Plots ]</code></strong> on the central header bar.</p>

    <div class="img-container">
      <img src="{b64_header}" alt="Interactive Plots Control Strip">
      <div class="img-caption">Figure 1.1: Interactive Plots Viewport Header & Real-Time Controls</div>
    </div>

    <div class="badge-legend">
      <div class="legend-item"><span class="badge">1</span> <div><strong>Viewport Switcher:</strong> Shows <code>[ ⚡ Interactive Plots ]</code> actively highlighted in blue.</div></div>
      <div class="legend-item"><span class="badge">2</span> <div><strong>Mode Selector:</strong> Switch between the 6 real-time experiment modes.</div></div>
      <div class="legend-item"><span class="badge cyan">3</span> <div><strong>Cache Selector:</strong> Choose an existing pre-computed foundation array. Filter by μ.</div></div>
      <div class="legend-item"><span class="badge cyan">4</span> <div><strong>▶ Compute Cache:</strong> Launch direct modal if no cache exists.</div></div>
      <div class="legend-item"><span class="badge">5</span> <div><strong>Continuous J_K Slider:</strong> Real-time coupling scaling at 60 FPS.</div></div>
    </div>

    <h3 id="interactive-modes">1.1 Analytical Mode Selector</h3>
    <ul>
      <li><strong>Brillouin Zone k-Probe</strong>: Click or drag anywhere on the 2D momentum map to evaluate spectral function <code>A(k, ω)</code>, <code>Re Σ</code>, and <code>Im Σ</code> in &lt;1 ms.</li>
      <li><strong>Fermi Surface & Energy Slice</strong>: Dynamic Fermi contour evolution across energies with the <code>ω</code> slider.</li>
      <li><strong>Band Dispersion</strong>: Track quasiparticle dispersion along high-symmetry paths (Γ → X → M → Γ).</li>
      <li><strong>Static RPA Susceptibility</strong>: 2D momentum map of magnetic instability peaks <code>χ(q)</code>.</li>
      <li><strong>Dynamic Susceptibility</strong>: Frequency-dependent spin/charge response <code>χ(q, ω)</code>.</li>
      <li><strong>Electrical Conductivity</strong>: Real-time optical and DC conductivity <code>σ(ω)</code>.</li>
    </ul>

    <h3 id="compute-cache">1.2 Foundation Cache & The "▶ Compute Cache" Dialog</h3>
    <p>Before sliding parameters, the app requires a base numerical array. Click the blue <strong><code>▶ Compute Cache</code></strong> button to synthesize one in seconds:</p>

    <div class="img-container compact-dialog">
      <img src="{b64_dlg}" alt="Compute Cache Dialog">
      <div class="img-caption">Figure 1.2: The Compute Cache Dialog</div>
    </div>

    <div class="badge-legend">
      <div class="legend-item"><span class="badge cyan">1</span> <div><strong>Target:</strong> Select Self-Energy Σ(k, ω), Bare Static χ₀(q), or Bare Dynamic χ₀(q, ω).</div></div>
      <div class="legend-item"><span class="badge">2</span> <div><strong>Parameters:</strong> Set chemical potential μ, interlayer coupling J_⊥, and grid size N.</div></div>
      <div class="legend-item"><span class="badge cyan">3</span> <div><strong>Compute:</strong> Dispatches to the engine (~0.3–2s) and auto-loads into the canvas.</div></div>
    </div>

    <h3 id="interactive-sliders">1.3 Mode-Specific Sliders & Controls</h3>
    <p>Row 2 adapts dynamically based on the selected mode:</p>
    <ul>
      <li><strong>Universal J_K Slider</strong>: Continuous scaling from 0.5 to 12.0 eV at 60 FPS without waiting for batch runs.</li>
      <li><strong>k-Probe Controls</strong>: Quick presets (<code>Antinodal</code>, <code>Nodal</code>, <code>Center Γ</code>, <code>Corner M</code>, or <code>Custom</code>) or direct clicking on the 2D map.</li>
      <li><strong>Energy Slice (ω) Slider</strong>: Active in Fermi Surface mode (sweeps -2.0 eV to +2.0 eV).</li>
      <li><strong>Susceptibility (J_⊥) Slider & K Selector</strong>: Active in Susceptibility modes; controls interlayer coupling and exchange (+1 AFM vs -1 FM).</li>
      <li><strong>Conductivity Device Selector</strong>: Switch between <code>Auto</code>, <code>GPU (CUDA)</code>, or <code>CPU (Multi-core)</code> with live <code>DC σ(0)</code> readout.</li>
    </ul>

    <!-- SECTION 2 -->
    <h2 id="inspector">⚙️ Section 2: Right Panel (Parameter Inspector & Job Execution)</h2>
    <p>The Right Dock is split into two balanced halves to present all cards without excessive vertical scrolling:</p>

    <div class="img-container compact-inspector">
      <img src="{b64_insp}" alt="Right Panel Inspector">
      <div class="img-caption">Figure 2.1: The Parameter Inspector & Execution cards (divided side-by-side)</div>
    </div>

    <div class="badge-legend">
      <div class="legend-item"><span class="badge">1</span> <div><strong>Active Study:</strong> Select Self-Energy, Spectral, Phase Diagram, or Susceptibility.</div></div>
      <div class="legend-item"><span class="badge cyan">2</span> <div><strong>Cache Status Badge:</strong> Instant feedback (🟢 Cached vs 🟡 Uncached) & Force Recompute.</div></div>
      <div class="legend-item"><span class="badge">3</span> <div><strong>Grid Presets:</strong> Fast Preview (64²), Standard (100²), High-Res (256²), or Custom.</div></div>
      <div class="legend-item"><span class="badge emerald">4</span> <div><strong>Execution Controls:</strong> <code>▶ Run Calculation</code> (green), <code>⏹ Cancel</code> (red), and <code>➕ Queue</code>.</div></div>
    </div>

    <h3 id="inspector-cards">2.1 Breakdown of Inspector Cards</h3>
    <ul>
      <li><strong>Part 1 (Left Column — Physics Study & Backend)</strong>:
        <ul>
          <li><strong>Active Calculation Study</strong>: Select the physics solver to configure.</li>
          <li><strong>Computation & Cache Status</strong>: Live cache status badge, <code>Force Recompute</code> checkbox, and <code>🧹 Cache (X MB)</code> cleanup button.</li>
          <li><strong>Study-Specific Parameters</strong>: Set sweep targets (J_K vs J_⊥), comma-separated values (e.g. <code>3.0, 6.0, 9.0</code>), and panel layouts.</li>
          <li><strong>Compute & Solver Backend</strong>: Toggle NVIDIA CUDA GPU (RTX 5060) vs. CPU 64-bit with core throttling (50% to 100%).</li>
        </ul>
      </li>
      <li><strong>Part 2 (Right Column — Grid Presets & Execution)</strong>:
        <ul>
          <li><strong>Numerical Grid & Presets</strong>: Fast Preview (64²), Standard (100²), High-Res (256²), or Custom Grid.</li>
          <li><strong>Common Model Hamiltonian</strong>: Set hopping t, next-nearest hopping t', chemical potential μ, and exchange K.</li>
          <li><strong>Results Output Directory</strong>: Destination folder for outputs (defaults to <code>results/</code>).</li>
          <li><strong>Execution Controls</strong>:
            <ul>
              <li><strong>▶ Run Calculation</strong> (Emerald Green): Starts execution in background child process.</li>
              <li><strong>⏹ Cancel / Stop</strong> (Vivid Red): Safely halts active calculation immediately.</li>
              <li><strong>➕ Add Active to Queue</strong>: Stacks parameter runs in the bottom Execution Queue table.</li>
            </ul>
          </li>
        </ul>
      </li>
    </ul>

    <!-- SECTION 3 -->
    <h2 id="viewer">📊 Section 3: Plot Viewer Viewport & Left Panel</h2>
    <p>Switch to this viewport by clicking <strong><code>[ 📊 Plot Viewer ]</code></strong> on the central header bar.</p>

    <div class="img-container">
      <img src="{b64_viewer}" alt="Plot Viewer Viewport">
      <div class="img-caption">Figure 3.1: Central High-DPI Plot Canvas</div>
    </div>

    <div class="badge-legend">
      <div class="legend-item"><span class="badge">1</span> <div><strong>Viewport Switcher:</strong> Toggle between [ 📊 Plot Viewer ] and [ ⚡ Interactive Plots ].</div></div>
      <div class="legend-item"><span class="badge">2</span> <div><strong>Plot Canvas:</strong> Interactive smooth zooming (mouse wheel) and panning (left-click drag).</div></div>
    </div>

    <h3 id="viewer-canvas">3.1 Central Plot Canvas Navigation</h3>
    <ul>
      <li><strong>Zooming</strong>: Mouse Scroll Wheel zooms smoothly into fine spectral features.</li>
      <li><strong>Panning</strong>: Left-click and drag across momentum or frequency axes.</li>
      <li><strong>🔍 Fit Window</strong>: Resets zoom and centers the figure.</li>
      <li><strong>⚏ Split View (Compare)</strong>: Compare two plots side-by-side.</li>
      <li><strong>Exporting Figures</strong>: Right-click or use toolbar to copy to clipboard (300 DPI) or save as vector <code>.pdf</code>, <code>.svg</code>, or <code>.png</code>.</li>
    </ul>

    <h3 id="gallery-modes">3.2 Left Dock: Plot Gallery Browser</h3>
    <p>The Left Dock (260 px) scans the results directory and provides instant navigation between runs:</p>

    <div class="img-container compact-gallery">
      <img src="{b64_gallery}" alt="Gallery Browser Modes">
      <div class="img-caption">Figure 3.2: Left Gallery in Thumbnail Card Mode (left) and Compact List Mode (right)</div>
    </div>

    <div class="badge-legend">
      <div class="legend-item"><span class="badge">1</span> <div><strong>View Mode Toggle:</strong> Switch between 🖼️ Thumbnail Cards and 📋 Compact List view.</div></div>
      <div class="legend-item"><span class="badge">2</span> <div><strong>Search & Category Pills:</strong> Filter by category (Spectral, Susceptibility) or type parameters.</div></div>
    </div>

    <h3 id="results-layout">3.3 Results Storage Layout (results/)</h3>
    <div class="feature-card">
      <ul>
        <li><code>results/cache/</code>: Bit-groomed 1/8th IBZ cached arrays (<code>sigma_base_*.npz</code>, <code>chi0_static_*.npz</code>, <code>chi0_dynamic_*.npz</code>). Powers instant loads.</li>
        <li><code>results/plots/</code>: High-resolution publication figures (<code>.png</code>, <code>.pdf</code>, <code>.svg</code>).</li>
        <li><code>results/data/</code>: Full raw numerical NumPy datasets (<code>.npz</code>) for custom analysis and plotting scripts.</li>
      </ul>
    </div>

  </div>

</body>
</html>
"""

with open(docs_dir / "HOW_TO_USE.html", "w", encoding="utf-8") as f:
    f.write(html_content)
print("Generated docs/HOW_TO_USE.html")
