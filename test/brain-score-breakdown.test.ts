/**
 * Bug 11 — brain_score needs a breakdown + orphan_pages metric is wrong.
 *
 * Assertions:
 *   1. getHealth() returns the new *_score breakdown fields.
 *   2. Breakdown fields sum to brain_score by construction.
 *   3. orphan_pages counts graph-required entity pages with neither inbound
 *      nor outbound links; artifact/catch-all pages are allowed to stand alone.
 *   4. BrainHealth type now carries dead_links.
 */

import { describe, test, expect, beforeAll, afterAll, beforeEach } from 'bun:test';
import { PGLiteEngine } from '../src/core/pglite-engine.ts';

let engine: PGLiteEngine;

beforeAll(async () => {
  engine = new PGLiteEngine();
  await engine.connect({});
  await engine.initSchema();
});

afterAll(async () => {
  await engine.disconnect();
});

beforeEach(async () => {
  for (const t of ['links', 'content_chunks', 'timeline_entries', 'raw_data', 'tags', 'page_versions', 'ingest_log', 'pages']) {
    await (engine as any).db.exec(`DELETE FROM ${t}`);
  }
});

describe('Bug 11 — brain_score breakdown sums to total', () => {
  test('empty brain returns full score (vacuous truth) with all breakdown fields present', async () => {
    // v0.37.10.0: empty brain = no coverage problems = full marks. Pre-fix
    // this returned 0/100, which surprised users running `gbrain doctor`
    // immediately after `gbrain init --pglite`. Each component returns its
    // max weight when pageCount === 0; the sum equals brain_score=100 by
    // construction (same invariant as the non-empty path, see next test).
    const h = await engine.getHealth();
    expect(h.brain_score).toBe(100);
    expect(h.embed_coverage_score).toBe(35);
    expect(h.link_density_score).toBe(25);
    expect(h.timeline_coverage_score).toBe(15);
    expect(h.no_orphans_score).toBe(15);
    expect(h.no_dead_links_score).toBe(10);
    // dead_links is now on the type.
    expect(h.dead_links).toBe(0);
  });

  test('breakdown fields always sum to brain_score', async () => {
    // Seed a small graph — some pages, some links, some embeds.
    for (const slug of ['a', 'b', 'c']) {
      await engine.putPage(slug, { type: 'note', title: slug, compiled_truth: `content of ${slug}`, frontmatter: {} });
    }
    const h = await engine.getHealth();
    const sum =
      h.embed_coverage_score +
      h.link_density_score +
      h.timeline_coverage_score +
      h.no_orphans_score +
      h.no_dead_links_score;
    expect(sum).toBe(h.brain_score);
  });

  test('brain_score caps at 100', async () => {
    const h = await engine.getHealth();
    expect(h.brain_score).toBeGreaterThanOrEqual(0);
    expect(h.brain_score).toBeLessThanOrEqual(100);
  });
});

describe('Bug 11 — orphan_pages is entity-scoped islanded pages', () => {
  test('an entity page with outbound-only links is NOT an orphan', async () => {
    await engine.putPage('people/hub', { type: 'person', title: 'Hub', compiled_truth: 'index', frontmatter: {} });
    await engine.putPage('people/leaf1', { type: 'person', title: 'L1', compiled_truth: 'x', frontmatter: {} });
    await engine.putPage('people/leaf2', { type: 'person', title: 'L2', compiled_truth: 'y', frontmatter: {} });
    await engine.putPage('people/leaf3', { type: 'person', title: 'L3', compiled_truth: 'z', frontmatter: {} });

    const hubId = (await (engine as any).db.query(`SELECT id FROM pages WHERE slug='people/hub'`)).rows[0].id;
    for (const target of ['people/leaf1', 'people/leaf2', 'people/leaf3']) {
      const tid = (await (engine as any).db.query(`SELECT id FROM pages WHERE slug=$1`, [target])).rows[0].id;
      await (engine as any).db.query(
        `INSERT INTO links (from_page_id, to_page_id, link_type) VALUES ($1, $2, 'mentions')`,
        [hubId, tid],
      );
    }

    const h = await engine.getHealth();
    expect(h.orphan_pages).toBe(0);
  });

  test('a note with no links is not a core orphan, but an entity with no links is', async () => {
    await engine.putPage('loner', { type: 'note', title: 'Loner', compiled_truth: 'alone', frontmatter: {} });
    let h = await engine.getHealth();
    expect(h.orphan_pages).toBe(0);

    await engine.putPage('people/loner', { type: 'person', title: 'Loner', compiled_truth: 'alone', frontmatter: {} });
    h = await engine.getHealth();
    expect(h.orphan_pages).toBe(1);
  });

  test('an entity page with inbound links only is NOT an orphan', async () => {
    await engine.putPage('people/sink', { type: 'person', title: 'Sink', compiled_truth: 'target', frontmatter: {} });
    await engine.putPage('people/source', { type: 'person', title: 'Source', compiled_truth: 'origin', frontmatter: {} });
    const sinkId = (await (engine as any).db.query(`SELECT id FROM pages WHERE slug='people/sink'`)).rows[0].id;
    const srcId = (await (engine as any).db.query(`SELECT id FROM pages WHERE slug='people/source'`)).rows[0].id;
    await (engine as any).db.query(
      `INSERT INTO links (from_page_id, to_page_id, link_type) VALUES ($1, $2, 'mentions')`,
      [srcId, sinkId],
    );

    const h = await engine.getHealth();
    expect(h.orphan_pages).toBe(0);
  });
});

describe('Bug 11 — doctor renders brain_score breakdown', () => {
  test('doctor source contains brain_score breakdown rendering', async () => {
    const source = await Bun.file(new URL('../src/commands/doctor.ts', import.meta.url)).text();
    expect(source).toContain('brain_score');
    expect(source).toContain('embed_coverage_score');
    expect(source).toContain('link_density_score');
    expect(source).toContain('no_orphans_score');
    expect(source).toContain('no_dead_links_score');
  });
});

describe('Bug 11 — BrainHealth type shape', () => {
  test('type includes dead_links + breakdown scores', async () => {
    const typesSource = await Bun.file(new URL('../src/core/types.ts', import.meta.url)).text();
    expect(typesSource).toContain('dead_links: number');
    expect(typesSource).toContain('embed_coverage_score: number');
    expect(typesSource).toContain('link_density_score: number');
    expect(typesSource).toContain('timeline_coverage_score: number');
    expect(typesSource).toContain('no_orphans_score: number');
    expect(typesSource).toContain('no_dead_links_score: number');
    // The stale "(0-10)" comment must be corrected to 0-100.
    expect(typesSource).toContain('0-100');
  });
});
