import * as axe from 'axe-core';
import type { ElementContext, ImpactValue, Result, RunOptions } from 'axe-core';

/**
 * jsdom does not perform real layout/paint, so a handful of axe rules that
 * depend on rendered geometry or cascaded computed style are unreliable
 * (they either false-positive or silently no-op) in a unit-test DOM. These
 * are explicitly out of scope here and are covered instead by manual
 * design-review against design/THEME.md's contrast tokens.
 */
const JSDOM_UNSUPPORTED_RULES = ['color-contrast', 'target-size', 'scrollable-region-focusable'] as const;

/**
 * Rules that only make sense against a full document (one <main>, full
 * landmark coverage of the page, skip-link/bypass mechanisms, etc). Isolated
 * component fixtures render a fragment, not the full page — the Shell owns
 * page-level landmark structure and is asserted separately in
 * `shell.a11y.spec.ts` / `app.a11y.spec.ts`.
 */
const PAGE_LEVEL_ONLY_RULES = ['region', 'landmark-one-main', 'landmark-unique', 'bypass', 'page-has-heading-one'] as const;

export type A11yScope = 'page' | 'fragment';

function disabledRulesFor(scope: A11yScope): Record<string, { enabled: false }> {
  const ids: readonly string[] = scope === 'page' ? JSDOM_UNSUPPORTED_RULES : [...JSDOM_UNSUPPORTED_RULES, ...PAGE_LEVEL_ONLY_RULES];
  return Object.fromEntries(ids.map((id) => [id, { enabled: false as const }]));
}

function formatViolations(violations: Result[]): string {
  return violations
    .map((violation) => {
      const nodes = violation.nodes.map((node) => `    - ${node.target.join(' ')}\n      ${node.failureSummary?.replace(/\n/g, '\n      ')}`).join('\n');
      return `[${violation.impact as ImpactValue}] ${violation.id}: ${violation.help} (${violation.helpUrl})\n${nodes}`;
    })
    .join('\n\n');
}

/**
 * Runs axe-core against `context` and throws (failing the test) with a
 * readable report if any violations are found.
 *
 * @param scope `'page'` keeps landmark/region rules enabled (use for the
 *   Shell/App, which own the real page structure); `'fragment'` also
 *   disables those page-level-only rules (use for feature components
 *   rendered in isolation, e.g. Login/Callback/Studio test fixtures).
 */
export async function expectNoA11yViolations(context: ElementContext, scope: A11yScope = 'fragment', options: RunOptions = {}): Promise<void> {
  const results = await axe.run(context, {
    ...options,
    rules: {
      ...disabledRulesFor(scope),
      ...(options.rules ?? {}),
    },
  });

  if (results.violations.length > 0) {
    throw new Error(`Accessibility violations found:\n\n${formatViolations(results.violations)}`);
  }
}
