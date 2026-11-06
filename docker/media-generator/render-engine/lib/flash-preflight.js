// Flash gate for the render path (WCAG 2.3.1, design D49). Pure function with no I/O.
// The caller runs checkFlashes (flash-check.js) on the rendered video and passes its findings in.
// Returns null when the render may be delivered (or when enforcement is off), otherwise { status, stage, message, findings }.

export function flashFailure({ enforce, findings }) {
  if (enforce !== true) return null;
  if (!Array.isArray(findings) || findings.length === 0) return null;
  return {
    status: 422,
    stage: 'flash',
    message: 'Render blocked: the video fails the WCAG 2.3.1 flash check.',
    findings,
  };
}
