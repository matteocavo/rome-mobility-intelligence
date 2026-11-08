import { test, after } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync, mkdtempSync, mkdirSync, writeFileSync, rmSync } from 'node:fs';
import { dirname, resolve, join } from 'node:path';
import { pathToFileURL } from 'node:url';
import ts from 'typescript';
import React, { act } from 'react';
import { renderToStaticMarkup } from 'react-dom/server';
import { createRoot } from 'react-dom/client';
import { JSDOM } from 'jsdom';

const temporary = mkdtempSync(join(resolve('tests'), '.compiled-header-'));
after(() => rmSync(temporary, { recursive: true, force: true }));
for (const file of ['components/Header.tsx', 'components/GithubIcon.tsx', 'i18n/translations.ts',
  'components/CentralMobilityMap.tsx', 'api/geography.ts']) {
  let code = ts.transpileModule(readFileSync(join('src', file), 'utf8'), {
    compilerOptions: { module: ts.ModuleKind.ESNext, target: ts.ScriptTarget.ES2020, jsx: ts.JsxEmit.ReactJSX },
  }).outputText.replace(/(from\s+['"])(\.[^'"]+)(['"])/g,
    (_, prefix, path, quote) => prefix + path + '.js' + quote);
  // SSR checks the actual side panel; browser-only Leaflet effects do not run.
  if (file.endsWith('CentralMobilityMap.tsx')) code = code.replace(/import L from ['"]leaflet['"];?/, 'const L = {};');
  const target = join(temporary, file.replace(/\.tsx?$/, '.js'));
  mkdirSync(dirname(target), { recursive: true });
  writeFileSync(target, code);
}
const { Header } = await import(pathToFileURL(join(temporary, 'components/Header.js')));
const { translations } = await import(pathToFileURL(join(temporary, 'i18n/translations.js')));
const { CentralMobilityMap } = await import(pathToFileURL(join(temporary, 'components/CentralMobilityMap.js')));

function props(language, state = {}) {
  return { language, t: translations[language], setLanguage() {}, activeSection: 'overview',
    onNavigate() {}, isFallback: false, backendOnline: false, unavailable: false,
    isWaking: false, wakingMessage: '', onRefresh() {}, isRefreshing: false, ...state };
}

for (const count of [3, 10]) {
  test(`map-side ranking shows up to seven available routes (${count} available)`, () => {
    const predictions = Array.from({ length: count }, (_, i) => ({ route_id: `route-${i}`,
      stop_id: `stop-${i}`, trip_id: `trip-${i}`, route_type: 3, major_delay_probability: .9 }));
    const dom = new JSDOM(renderToStaticMarkup(React.createElement(CentralMobilityMap, {
      predictions, totalObservations: count, hasActiveFilters: false, selectedLine: null,
      selectedVehicle: null, modeFilter: 'all', onSelectLine() {}, onSelectVehicle() {},
      onSetModeFilter() {}, language: 'it', t: translations.it,
    })));
    try {
      const panel = dom.window.document.querySelector('[class*="lg:col-span-4"]');
      assert.equal(panel.querySelectorAll('button').length, Math.min(count, 7));
      assert.ok(panel.textContent.includes(`route-${Math.min(count, 7) - 1}`));
      assert.ok(!panel.textContent.includes('route-7'));
    } finally { dom.window.close(); }
  });
}

const labels = {
  it: ['Servizio connesso', 'Connessione non ancora verificata', 'Servizio non disponibile'],
  en: ['Service connected', 'Connection not yet checked', 'Service unavailable'],
};

for (const language of ['it', 'en']) {
  const [connected, latest, unavailable] = labels[language];
  for (const [name, state, text, color] of [
    ['connected', { backendOnline: true }, connected, '#10B981'],
    ['last known good', {}, latest, '#FFB300'],
    ['API reachable with retained data', { backendOnline: true, isFallback: true }, connected, '#10B981'],
    ['unavailable', { unavailable: true }, unavailable, '#8E001C'],
    ['checking', { isChecking: true }, translations[language].status.checking, '#FFB300'],
    ['refreshing', { isRefreshing: true, backendOnline: true }, translations[language].status.checking, '#FFB300'],
    ['unreachable despite prior success', { backendOnline: true, unavailable: true }, unavailable, '#8E001C'],
  ]) {
    test(`${language}: desktop status identifies ${name} in text and color`, () => {
      const dom = new JSDOM(renderToStaticMarkup(React.createElement(Header, props(language, state))));
      try {
        const badge = dom.window.document.querySelector('[role="status"]');
        assert.equal(badge.textContent, text);
        assert.ok(badge.querySelector('[aria-hidden="true"]').className.includes(color));
      } finally { dom.window.close(); }
    });
  }

  test(`${language}: open mobile menu updates across connected, saved, unavailable and waking`, async () => {
    const dom = new JSDOM('<div id="root"></div>');
    const saved = { window: globalThis.window, document: globalThis.document,
      IS_REACT_ACT_ENVIRONMENT: globalThis.IS_REACT_ACT_ENVIRONMENT };
    Object.assign(globalThis, { window: dom.window, document: dom.window.document, IS_REACT_ACT_ENVIRONMENT: true });
    const root = createRoot(document.getElementById('root'));
    try {
      await act(() => root.render(React.createElement(Header, props(language, { backendOnline: true }))));
      const menuLabel = language === 'it' ? 'Apri/chiudi menu' : 'Toggle menu';
      await act(() => document.querySelector(`button[aria-label="${menuLabel}"]`)
        .dispatchEvent(new dom.window.MouseEvent('click', { bubbles: true })));
      for (const [state, text, color] of [
        [{ backendOnline: true }, connected, '#10B981'],
        [{}, latest, '#FFB300'],
        [{ unavailable: true }, unavailable, '#8E001C'],
        [{ isWaking: true, unavailable: true }, translations[language].status.checking, '#FFB300'],
      ]) {
        await act(() => root.render(React.createElement(Header, props(language, state))));
        const badge = document.querySelector('[role="status"]');
        assert.equal(badge.textContent, text);
        assert.ok(badge.querySelector('[aria-hidden="true"]').className.includes(color));
      }
    } finally {
      await act(() => root.unmount());
      Object.assign(globalThis, saved);
      dom.window.close();
    }
  });
}

for (const language of ['it', 'en']) {
  for (const state of ['LIVE', 'DELAYED', 'STALE', 'UNAVAILABLE']) {
    test(`${language}: localized freshness ${state} is distinct from connection`, () => {
      const dom = new JSDOM(renderToStaticMarkup(React.createElement(Header,
        props(language, { backendOnline: true, dataStatus: state }))));
      try {
        const status = translations[language].status;
        const badges = [...dom.window.document.querySelectorAll('[role="status"]')];
        assert.ok(badges.some(b => b.getAttribute('aria-label') === `${status.connection}: ${status.connected}`));
        assert.ok(badges.some(b => b.getAttribute('aria-label') === `${status.freshness}: ${status.freshnessLabels[state]}`));
        assert.ok(badges.every(b => !/LIVE|DELAYED|STALE|UNAVAILABLE/.test(b.textContent)));
        assert.equal(dom.window.document.querySelector('button[aria-label="' + status.refresh + '"]').title, status.refresh);
      } finally { dom.window.close(); }
    });
  }
}
