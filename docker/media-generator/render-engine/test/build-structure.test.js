import { test } from 'node:test';
import assert from 'node:assert/strict';
import {
  exportsOf,
  importsOf,
  routesOf,
  decisionsOf,
  openItemsOf,
  duplicateExports,
  buildStructure,
} from '../scripts/build-structure.mjs';

test('exportsOf finds function, const, let and class exports', () => {
  const src = 'export function a() {}\nexport const B = 1;\nexport async function c() {}\nexport class D {}\nfunction hidden() {}';
  assert.deepEqual(exportsOf(src), ['a', 'B', 'c', 'D']);
});

test('importsOf keeps only local lib and bin imports, relative to the engine', () => {
  const src = "import x from '../lib/disk-gate.js';\nimport y from 'node:fs';\nimport z from './helper.js';\nimport w from '../bin/approve.js';";
  assert.deepEqual(importsOf(src), ['bin/approve.js', 'lib/disk-gate.js']);
});

test('routesOf lists method and path for each route', () => {
  const src = "app.get('/health', h);\napp.post('/render', r);\n  app.post('/x', s)";
  assert.deepEqual(routesOf(src), ['GET /health', 'POST /render']);
});

test('decisionsOf and openItemsOf read IDs and status', () => {
  const doc = '| D48 | text | status |\n\n- **O5** CLOSED (D48). text\n- **O18** WAIVED. text';
  assert.deepEqual([...decisionsOf(doc).keys()], ['D48']);
  assert.deepEqual([...openItemsOf(doc)], [['O5', 'CLOSED'], ['O18', 'WAIVED']]);
});

test('duplicateExports reports a name exported by two modules', () => {
  const modules = new Map([
    ['lib/a.js', 'export function same() {}'],
    ['lib/b.js', 'export function same() {}\nexport const other = 1;'],
  ]);
  assert.deepEqual(duplicateExports(modules), [['same', ['lib/a.js', 'lib/b.js']]]);
});

test('buildStructure flags a module with no test and a test outside npm test', () => {
  const sources = {
    modules: new Map([
      ['lib/tested.js', 'export const t = 1;'],
      ['lib/untested.js', 'export const u = 1;'],
    ]),
    tests: new Map([["test/tested.test.js", "import { t } from '../lib/tested.js';"], ['test/loose.test.js', '']]),
    server: "app.get('/health', h);",
    doc: '',
    pkgTestList: ['test/tested.test.js'],
  };
  const md = buildStructure(sources);
  assert.match(md, /Modules with no test: `lib\/untested\.js`/);
  assert.match(md, /Test files not in `npm test`: `test\/loose\.test\.js`/);
  assert.match(md, /- `GET \/health`/);
});
