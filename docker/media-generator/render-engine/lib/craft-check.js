// Craft checks for film scenes. Pure functions, no I/O, no dependencies.
// Rules: read speed, minimum on-screen time, cut budget, and a short last scene.

export const CRAFT_RULES = {
  READ_SPEED: 'read-speed',
  MIN_EXPOSURE: 'min-exposure',
  CUT_BUDGET: 'cut-budget',
  LAST_SCENE: 'last-scene',
};

const MAX_CHARS_PER_SECOND = 20;
const MIN_SCENE_SECONDS = 0.83;
const CUTS_PER_30_SECONDS = 12;
const LAST_SCENE_MAX_SECONDS = 5;

// scenes: [{id, start, duration, readText, cuts?}] where cuts is the number of hard cuts
// inside the scene, not counting the scene boundary. Returns {ok, findings:[{scene, rule, message}]}.
export function checkScenes(scenes) {
  const findings = [];
  if (!Array.isArray(scenes) || scenes.length === 0) {
    return { ok: true, findings };
  }

  for (const scene of scenes) {
    const readText = typeof scene.readText === 'string' ? scene.readText : '';
    const chars = readText.replace(/\s/g, '').length;
    if (scene.duration > 0 && chars / scene.duration > MAX_CHARS_PER_SECOND) {
      findings.push({
        scene: scene.id,
        rule: CRAFT_RULES.READ_SPEED,
        message: `${chars} characters in ${scene.duration}s is faster than ${MAX_CHARS_PER_SECOND} characters per second`,
      });
    }
    if (scene.duration < MIN_SCENE_SECONDS) {
      findings.push({
        scene: scene.id,
        rule: CRAFT_RULES.MIN_EXPOSURE,
        message: `scene is ${scene.duration}s, shorter than ${MIN_SCENE_SECONDS}s`,
      });
    }
  }

  const L = Math.max(...scenes.map((s) => s.start + s.duration));
  const allowed = (CUTS_PER_30_SECONDS * L) / 30;
  const sceneCuts = scenes.reduce((sum, s) => sum + (s.cuts || 0), 0);
  const total = sceneCuts + (scenes.length - 1);
  if (total > allowed) {
    findings.push({
      scene: 'film',
      rule: CRAFT_RULES.CUT_BUDGET,
      message: `${total} cuts in a ${L}s film exceeds the budget of ${allowed.toFixed(2)}`,
    });
  }

  const last = scenes.reduce((a, b) => (b.start > a.start ? b : a));
  if (last.duration > LAST_SCENE_MAX_SECONDS) {
    findings.push({
      scene: last.id,
      rule: CRAFT_RULES.LAST_SCENE,
      message: `last scene is ${last.duration}s, longer than ${LAST_SCENE_MAX_SECONDS}s`,
    });
  }

  return { ok: findings.length === 0, findings };
}

// Builds the craft-check timeline from validated scenes: [{id, start, duration, readText, cuts}].
export function toTimeline(scenes) {
  let start = 0;
  return scenes.map((scene, i) => {
    const entry = {
      id: `scene-${i + 1}`,
      start,
      duration: scene.seconds,
      readText: `${scene.text} ${scene.sub || ''}`,
      cuts: 0,
    };
    start += scene.seconds;
    return entry;
  });
}

// Scenes requests are rejected (400) on any craft finding. Title-only requests are never rejected:
// their findings come back as warnings.
export function applyCraftPolicy(hasScenes, findings) {
  if (hasScenes) {
    return { reject: findings.length > 0, warnings: [] };
  }
  return { reject: false, warnings: findings };
}
