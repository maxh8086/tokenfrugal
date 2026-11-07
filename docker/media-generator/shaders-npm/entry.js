// HyperFrames wrapper for the npm shaders@4.0.0 renderer, bundled by esbuild into one IIFE so it
// loads from file:// (module scripts cannot load from file://). Same renderer calls, synthetic-time seek
// and buildReady / hf-seek contract as the vendored wrapper it replaces. Shader definitions come from
// each shader's module default export, as the vendored bundle did (the core registry is not populated).
import {
  shaderRendererGPU,
  createGpuUniformsMap,
  resolveBoundingBox,
  rootPassthrough,
} from './node_modules/shaders/dist/core/index.js';
import S_Aurora from './node_modules/shaders/dist/core/shaders/Aurora/index.js';
import S_Blob from './node_modules/shaders/dist/core/shaders/Blob/index.js';
import S_Chrome from './node_modules/shaders/dist/core/shaders/Chrome/index.js';
import S_ColorWheel from './node_modules/shaders/dist/core/shaders/ColorWheel/index.js';
import S_FallingLines from './node_modules/shaders/dist/core/shaders/FallingLines/index.js';
import S_FlowingGradient from './node_modules/shaders/dist/core/shaders/FlowingGradient/index.js';
import S_FractalNoise from './node_modules/shaders/dist/core/shaders/FractalNoise/index.js';
import S_Frost from './node_modules/shaders/dist/core/shaders/Frost/index.js';
import S_GaborNoise from './node_modules/shaders/dist/core/shaders/GaborNoise/index.js';
import S_Godrays from './node_modules/shaders/dist/core/shaders/Godrays/index.js';
import S_Goo from './node_modules/shaders/dist/core/shaders/Goo/index.js';
import S_Heatmap from './node_modules/shaders/dist/core/shaders/Heatmap/index.js';
import S_Hologram from './node_modules/shaders/dist/core/shaders/Hologram/index.js';
import S_Holographic from './node_modules/shaders/dist/core/shaders/Holographic/index.js';
import S_LensFlare from './node_modules/shaders/dist/core/shaders/LensFlare/index.js';
import S_LightEdge from './node_modules/shaders/dist/core/shaders/LightEdge/index.js';
import S_LiquidMetal from './node_modules/shaders/dist/core/shaders/LiquidMetal/index.js';
import S_Marble from './node_modules/shaders/dist/core/shaders/Marble/index.js';
import S_MeshGradient from './node_modules/shaders/dist/core/shaders/MeshGradient/index.js';
import S_Nebula from './node_modules/shaders/dist/core/shaders/Nebula/index.js';
import S_Obsidian from './node_modules/shaders/dist/core/shaders/Obsidian/index.js';
import S_Plasma from './node_modules/shaders/dist/core/shaders/Plasma/index.js';
import S_Plastic from './node_modules/shaders/dist/core/shaders/Plastic/index.js';
import S_Prism from './node_modules/shaders/dist/core/shaders/Prism/index.js';
import S_Ripples from './node_modules/shaders/dist/core/shaders/Ripples/index.js';
import S_SineWave from './node_modules/shaders/dist/core/shaders/SineWave/index.js';
import S_Spiral from './node_modules/shaders/dist/core/shaders/Spiral/index.js';
import S_Strands from './node_modules/shaders/dist/core/shaders/Strands/index.js';
import S_Stripes from './node_modules/shaders/dist/core/shaders/Stripes/index.js';
import S_SunBurst from './node_modules/shaders/dist/core/shaders/SunBurst/index.js';
import S_Swirl from './node_modules/shaders/dist/core/shaders/Swirl/index.js';
import S_ThinFilm from './node_modules/shaders/dist/core/shaders/ThinFilm/index.js';
import S_Voronoi from './node_modules/shaders/dist/core/shaders/Voronoi/index.js';
import S_Water from './node_modules/shaders/dist/core/shaders/Water/index.js';
import S_Waveform from './node_modules/shaders/dist/core/shaders/Waveform/index.js';
import S_WorleyNoise from './node_modules/shaders/dist/core/shaders/WorleyNoise/index.js';
const SHADERS = {
  Aurora: S_Aurora,
  Blob: S_Blob,
  Chrome: S_Chrome,
  ColorWheel: S_ColorWheel,
  FallingLines: S_FallingLines,
  FlowingGradient: S_FlowingGradient,
  FractalNoise: S_FractalNoise,
  Frost: S_Frost,
  GaborNoise: S_GaborNoise,
  Godrays: S_Godrays,
  Goo: S_Goo,
  Heatmap: S_Heatmap,
  Hologram: S_Hologram,
  Holographic: S_Holographic,
  LensFlare: S_LensFlare,
  LightEdge: S_LightEdge,
  LiquidMetal: S_LiquidMetal,
  Marble: S_Marble,
  MeshGradient: S_MeshGradient,
  Nebula: S_Nebula,
  Obsidian: S_Obsidian,
  Plasma: S_Plasma,
  Plastic: S_Plastic,
  Prism: S_Prism,
  Ripples: S_Ripples,
  SineWave: S_SineWave,
  Spiral: S_Spiral,
  Strands: S_Strands,
  Stripes: S_Stripes,
  SunBurst: S_SunBurst,
  Swirl: S_Swirl,
  ThinFilm: S_ThinFilm,
  Voronoi: S_Voronoi,
  Water: S_Water,
  Waveform: S_Waveform,
  WorleyNoise: S_WorleyNoise,
};

const canvas = document.querySelector('canvas[data-shader]');
const shaderName = canvas.dataset.shader;
const def = SHADERS[shaderName];

const renderer = shaderRendererGPU();
let chain = Promise.resolve();

function renderAt(t) {
  chain = chain.then(() =>
    renderer.renderSyntheticFrame(t - renderer.__testing.getFrameDiagnostics().globalElapsedTime)
  );
  return chain;
}

const ready = (async () => {
  if (!def) throw new Error(`shaders: no shader named "${shaderName}" in this bundle`);
  await renderer.initialize({ canvas, observeElement: false, colorSpace: 'srgb' });
  const reason = renderer.getFailureReason();
  if (reason) throw new Error(`shaders: WebGPU unavailable (${reason})`);
  renderer.registerNode('root', rootPassthrough.fragment, null, null, {}, rootPassthrough);
  const props = JSON.parse(canvas.dataset.shaderProps || '{}');
  const values = Object.fromEntries(
    Object.entries(def.props).map(([k, cfg]) => [k, k in props ? props[k] : cfg.default])
  );
  renderer.registerNode(
    'fx',
    def.fragment,
    'root',
    { blendMode: 'normal', renderOrder: 1, id: 'fx', boundingBox: resolveBoundingBox(undefined) },
    createGpuUniformsMap(def, values, 'fx'),
    def
  );
  renderer.stopAnimation();
  await renderAt(window.__hfTypegpuTime ?? 0);
})();

window.__hf = window.__hf || {};
window.__hf.buildReady = window.__hf.buildReady || {};
window.__hf.buildReady.shaders = ready;
ready.catch((e) => console.error(String(e)));
window.addEventListener('hf-seek', (e) => {
  const t = ready.then(() => renderAt(e.detail.time));
  if (typeof e.detail.waitUntil === 'function') e.detail.waitUntil(t);
});
