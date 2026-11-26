const {test} = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const path = require('node:path');

const source = fs.readFileSync(path.join(__dirname, '../static/system-status-center.js'), 'utf8');
const tick = () => new Promise(resolve => setImmediate(resolve));

function portal() {
  const elements = new Map();
  const element = id => {
    if (!elements.has(id)) elements.set(id, {
      hidden: true, value: '', textContent: '', innerHTML: '', checked: false,
      classList: {contains: name => name === 'active'}, querySelectorAll: () => [],
    });
    return elements.get(id);
  };
  const system = {system_key: 'test-system', name: 'Sistema', category: 'Teste',
    maturity: 'NAO_AVALIADO', operational: 'NAO_MONITORADO', is_public: true};
  const requests = [], changes = [];
  let failure = false, delay = null;
  const context = vm.createContext({
    console, Intl, Date,
    document: {getElementById: element},
    fetch: async (url, options = {}) => {
      requests.push({url, method: options.method || 'GET'});
      let body;
      if (url.startsWith('/api/public/')) body = {systems: [system], incidents: []};
      else if (url.endsWith('/audit')) body = {entries: changes};
      else if (options.method === 'PUT') {
        const update = JSON.parse(options.body);
        changes.push({actor: 'admin', before: {...system}, after: update});
        Object.assign(system, update);
        body = {ok: true};
      } else {
        if (delay) await delay;
        if (failure) return {ok: false, status: 503, json: async () => ({error: 'Serviço indisponível'})};
        body = {systems: [system], incidents: []};
      }
      return {ok: true, status: 200, json: async () => body};
    },
  });
  context.window = context;
  // Reproduz a sessão real: declaração lexical global, ausente em window._auth.
  vm.runInContext('let _auth = {authenticated: false, is_admin: false};', context);
  vm.runInContext(source, context);
  return {context, element, requests, changes, system,
    auth: value => vm.runInContext(`_auth = ${JSON.stringify(value)};`, context),
    fail: value => { failure = value; }, defer: value => { delay = value; }};
}

test('sessão lexical abre editor após login e salva situação com recarga e histórico', async () => {
  const p = portal();
  await tick();
  assert.equal(p.context._auth, undefined);
  assert.equal(p.element('system-status-admin').hidden, true);
  assert.equal(p.requests.filter(r => r.url === '/api/admin/systems-status').length, 0);
  p.auth({authenticated: true, is_admin: true});
  await p.context.systemStatusRefreshAdmin();
  assert.equal(p.element('system-status-admin').hidden, false);
  assert.equal(p.element('ssa-name').value, 'Sistema');
  p.element('ssa-operational').value = 'OPERACIONAL';
  await p.context.systemStatusAdminSave();
  await tick();
  assert.equal(p.system.operational, 'OPERACIONAL');
  assert.equal(p.changes.length, 1);
  assert.equal(p.element('ssa-operational').value, 'OPERACIONAL');
  assert.match(p.element('system-status-audit').innerHTML, /admin/);
  p.auth({authenticated: true, is_admin: false});
  await p.context.systemStatusRefreshAdmin();
  assert.equal(p.element('system-status-admin').hidden, true);
});

test('erro administrativo é informado e permite nova consulta', async () => {
  const p = portal(); await tick();
  p.auth({authenticated: true, is_admin: true}); p.fail(true);
  await p.context.systemStatusLoad(true);
  assert.equal(p.element('system-status-admin-error').hidden, false);
  assert.match(p.element('system-status-admin-error').textContent, /Serviço indisponível/);
  p.fail(false); await p.context.systemStatusLoad(true);
  assert.equal(p.element('system-status-admin').hidden, false);
  assert.equal(p.element('system-status-admin-error').hidden, true);
});

test('resposta pendente não reabre editor depois de sair da conta', async () => {
  const p = portal(); await tick();
  let resolve; p.defer(new Promise(done => { resolve = done; }));
  p.auth({authenticated: true, is_admin: true});
  const loading = p.context.systemStatusRefreshAdmin();
  p.auth({authenticated: false, is_admin: false});
  await p.context.systemStatusRefreshAdmin();
  resolve(); await loading;
  assert.equal(p.element('system-status-admin').hidden, true);
});
