import { test } from 'node:test';
import assert from 'node:assert/strict';
import { buildReport } from '../scripts/licence-report.js';

const GENERATED = '2026-11-07T00:00:00.000Z';

test('buildReport sorts rows by package name', () => {
  const md = buildReport(
    [
      { name: 'zeta', version: '1.0.0', license: 'MIT' },
      { name: 'alpha', version: '2.0.0', license: 'Apache-2.0' },
      { name: 'mid', version: '0.1.0', license: 'ISC' },
    ],
    GENERATED
  );
  const rows = md.split('\n').filter((line) => /^\| (?!Package \||--- \|)/.test(line));
  assert.deepEqual(rows, [
    '| alpha | 2.0.0 | Apache-2.0 |',
    '| mid | 0.1.0 | ISC |',
    '| zeta | 1.0.0 | MIT |',
  ]);
});

test('buildReport uses UNKNOWN when the licence is missing or empty', () => {
  const md = buildReport(
    [
      { name: 'no-licence', version: '1.0.0', license: undefined },
      { name: 'empty-licence', version: '1.0.0', license: '' },
    ],
    GENERATED
  );
  assert.match(md, /\| no-licence \| 1\.0\.0 \| UNKNOWN \|/);
  assert.match(md, /\| empty-licence \| 1\.0\.0 \| UNKNOWN \|/);
});

test('buildReport header states the generated date and the not-legal-advice note', () => {
  const md = buildReport([], GENERATED);
  assert.equal(md.split('\n')[0], '# Licence report');
  assert.ok(md.includes(`Generated: ${GENERATED}`));
  assert.ok(md.includes('not legal advice'));
});

test('buildReport defaults the generated date to an ISO timestamp', () => {
  const md = buildReport([]);
  assert.match(md, /Generated: \d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{3}Z/);
});
