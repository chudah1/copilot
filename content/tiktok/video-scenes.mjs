export const CROSSFADE = 0.38;
const CHART_DURATION = 1.6;

export const clamp = (value, min = 0, max = 1) => Math.max(min, Math.min(max, value));

export const smooth = (value) => {
  const x = clamp(value);
  return x * x * (3 - 2 * x);
};

export const esc = (value = "") =>
  String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;");

export const accentTitle = (title, accent) => {
  const parts = accent ? title.split(accent) : [title];
  const escapedParts = parts.map(esc);
  const joined = accent
    ? escapedParts.join(`<span class="accent">${esc(accent)}</span>`)
    : escapedParts[0];
  return joined.replaceAll("\n", "<br>");
};

export const sceneVisibility = (scene, time) => {
  const fadeIn = smooth((time - scene.start) / CROSSFADE);
  const fadeOut = smooth((scene.end - time) / CROSSFADE);
  return Math.min(fadeIn, fadeOut);
};

export const sceneFadeIn = (scene, time) => smooth((time - scene.start) / CROSSFADE);

export const resolveActiveScene = (scenes, time) =>
  scenes.reduce(
    (best, scene) => (sceneVisibility(scene, time) > sceneVisibility(best, time) ? scene : best),
    scenes[0],
  );

export const videoDuration = (video) => video.scenes.reduce((max, scene) => Math.max(max, scene.end), 0);

export const renderDuration = (video) => videoDuration(video) - CROSSFADE;

export const chartProgress = (scene, time) => smooth((time - scene.start) / CHART_DURATION);

export const renderSceneHTML = (scene) => {
  const eyebrow = scene.eyebrow ? `<div class="eyebrow">${esc(scene.eyebrow)}</div>` : "";
  switch (scene.type) {
    case "hook":
      return `${eyebrow}<h1>${accentTitle(scene.title, scene.accent)}</h1>`;
    case "statement": {
      const body = scene.body ? `<p class="subcopy">${esc(scene.body)}</p>` : "";
      return `${eyebrow}<h2>${accentTitle(scene.title, scene.accent)}</h2>${body}`;
    }
    case "stat": {
      const chart = scene.chart
        ? `<div class="chart"><div class="chart-grid"></div><svg viewBox="0 0 940 450" preserveAspectRatio="none"><path d="${esc(scene.chart.path)}" /></svg></div>`
        : "";
      return `${eyebrow}<div class="money">${esc(scene.stat)}</div><p class="subcopy">${esc(scene.body)}</p>${chart}`;
    }
    case "compare":
      return `${eyebrow}<h2>${accentTitle(scene.title, scene.accent)}</h2><div class="compare"><div class="card"><div class="card-label">${esc(scene.compare.left.label)}</div><div class="card-copy">${esc(scene.compare.left.copy)}</div></div><div class="card"><div class="card-label">${esc(scene.compare.right.label)}</div><div class="card-copy">${esc(scene.compare.right.copy)}</div></div></div>`;
    case "quote":
      return `${eyebrow}<div class="question">${esc(scene.quote)}</div>`;
    case "closing": {
      const body = scene.body ? `<p class="subcopy">${esc(scene.body)}</p>` : "";
      return `<div class="closing-mark">BH</div><h2>${accentTitle(scene.title, scene.accent)}</h2>${body}`;
    }
    default:
      throw new Error(`Unknown scene type: ${scene.type}`);
  }
};
