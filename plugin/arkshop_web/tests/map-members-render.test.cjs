const {test} = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const html = fs.readFileSync(path.join(__dirname, '../static/index.html'), 'utf8');

test('todos os scripts inline do portal têm sintaxe válida', () => {
  let count = 0;
  for (const match of html.matchAll(/<script\b([^>]*)>([\s\S]*?)<\/script>/gi)) {
    if (/\bsrc\s*=|application\/ld\+json|application\/json/i.test(match[1])) continue;
    new vm.Script(match[2]);
    count++;
  }
  assert.ok(count > 0);
});

test('mapas atuais mostram IDs e fonte; IDs antigos ficam no histórico separado', () => {
  const elements = new Map();
  const get = id => {
    if (!elements.has(id)) elements.set(id, {innerHTML:'', textContent:'', hidden:true});
    return elements.get(id);
  };
  const start = html.indexOf('function renderMapMembersAdmin()');
  const end = html.indexOf('async function loadMapOnlinePlayers()', start);
  const player = {steam_id:'76561198000000011', character_name:'Jogador', player_data_id:123,
    tribe_id:456, tribe_name:'Tribo', source:'monitor'};
  const context = vm.createContext({
    document: {getElementById:get},
    escHtml: value => String(value).replaceAll('<','&lt;'),
    _mmDash: value => value == null ? '—' : value,
    _mapOnlinePresenceByServer: {current:{status:'online', steamIds:new Set([player.steam_id])}},
    _mapMembersCache: [
      {server_id:'current', label:'Mapa atual', registered:true, total:1, items:[player]},
      {server_id:'old', label:'Mapa antigo', registered:false, total:1, items:[player]},
    ],
  });
  vm.runInContext(html.slice(start, end), context);
  context.renderMapMembersAdmin();
  assert.match(get('map-members-grid').innerHTML, /Mapa atual/);
  assert.doesNotMatch(get('map-members-grid').innerHTML, /Mapa antigo/);
  assert.match(get('map-members-grid').innerHTML, /ID do personagem 123 · ID da tribo 456/);
  assert.match(get('map-members-grid').innerHTML, /Fonte: Monitoramento/);
  assert.match(get('map-members-grid').innerHTML, /badge-success">ONLINE/);
  assert.match(get('map-members-history-grid').innerHTML, /Mapa antigo/);
  assert.equal(get('map-members-history').hidden, false);
  context._mapOnlinePresenceByServer = {};
  context.renderMapMembersAdmin();
  assert.match(get('map-members-grid').innerHTML, /STATUS NÃO VERIFICADO/);
  assert.doesNotMatch(get('map-members-grid').innerHTML, /badge-success">ONLINE/);
});
