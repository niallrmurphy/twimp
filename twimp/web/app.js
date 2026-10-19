// twimp in the browser: a lobby for creating games, and a game view that
// polls the server, draws the map, and answers decisions for this seat.
'use strict';

const params = new URLSearchParams(location.search);
const GAME = params.get('game');
const SEAT = params.get('seat');
const app = document.getElementById('app');
const statusLine = document.getElementById('status');

// ---------- Helpers ----------

// Build an element. Text is always set with textContent, never as HTML.
function el(tag, attrs, ...children) {
  const node = document.createElement(tag);
  for (const [key, value] of Object.entries(attrs || {})) {
    if (key === 'class') node.className = value;
    else if (key.startsWith('on')) node.addEventListener(key.slice(2), value);
    else if (value === true) node.setAttribute(key, '');
    else if (value !== false && value != null) node.setAttribute(key, value);
  }
  for (const child of children.flat()) {
    if (child == null || child === false) continue;
    node.append(child instanceof Node ? child : document.createTextNode(String(child)));
  }
  return node;
}

function svg(tag, attrs, ...children) {
  const node = document.createElementNS('http://www.w3.org/2000/svg', tag);
  for (const [key, value] of Object.entries(attrs || {})) {
    if (key.startsWith('on')) node.addEventListener(key.slice(2), value);
    else if (value != null) node.setAttribute(key, value);
  }
  for (const child of children.flat()) {
    if (child == null) continue;
    node.append(child instanceof Node ? child : document.createTextNode(String(child)));
  }
  return node;
}

async function api(path, body) {
  const options = body === undefined ? {} : {
    method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(body)};
  const response = await fetch(path, options);
  const data = await response.json();
  if (!response.ok) throw new Error(data.error || response.statusText);
  return data;
}

const ABBREVIATIONS = {
  warsun: 'WS', flagship: 'FS', dreadnought: 'DN', carrier: 'CV', cruiser: 'CA',
  destroyer: 'DD', fighter: 'FF', infantry: 'IN', pds: 'PDS', spacedock: 'SD'};
const UNIT_ORDER = Object.keys(ABBREVIATIONS);

function unitSummary(counts) {
  return UNIT_ORDER.filter(t => counts[t])
    .map(t => ABBREVIATIONS[t] + counts[t] + (counts[t + '_damaged'] ? '*' : ''))
    .join(' ');
}

function plural(n, word) { return n + ' ' + word + (n === 1 ? '' : 's'); }

const UNIT_NAMES = {
  warsun: ['war sun', 'war suns'], flagship: ['flagship', 'flagships'],
  dreadnought: ['dreadnought', 'dreadnoughts'], carrier: ['carrier', 'carriers'],
  cruiser: ['cruiser', 'cruisers'], destroyer: ['destroyer', 'destroyers'],
  fighter: ['fighter', 'fighters'], infantry: ['infantry', 'infantry'],
  pds: ['PDS', 'PDS'], spacedock: ['space dock', 'space docks']};

// "2 carriers, 1 destroyer (damaged)" — the long form of unitSummary.
function unitWords(counts) {
  return UNIT_ORDER.filter(t => counts[t]).map(t => {
    const n = counts[t], damaged = counts[t + '_damaged'];
    return n + ' ' + UNIT_NAMES[t][n === 1 ? 0 : 1] +
      (damaged ? ' (' + (damaged === n ? 'damaged' : damaged + ' damaged') + ')' : '');
  }).join(', ');
}

// ---------- Lobby ----------

async function Lobby() {
  statusLine.textContent = 'New game';
  const factions = await api('/api/factions');
  const sample = ['sol', 'letnev', 'jolnar', 'sardakk', 'xxcha', 'yssaril'];
  const rows = factions.map(f => {
    const play = el('input', {type: 'checkbox', checked: sample.includes(f.key),
                              'aria-label': 'Play ' + f.name});
    const human = el('input', {type: 'checkbox', checked: f.key === 'sol',
                               'aria-label': f.name + ' is played by a person'});
    return {key: f.key, play, human,
            node: el('label', {}, play, ' ', f.name, ' ', el('span', {class: 'muted'}, '(human: '),
                     human, el('span', {class: 'muted'}, ')'))};
  });
  const roundsInput = el('input', {type: 'number', min: 1, max: 20, value: 5});
  const seedInput = el('input', {type: 'number', placeholder: 'random', style: 'width:6.5em'});
  const computer = el('select', {}, el('option', {value: 'greedy'}, 'greedy'),
                      el('option', {value: 'random'}, 'random'));
  const error = el('div', {class: 'error'});
  const result = el('div');

  async function Create() {
    error.textContent = '';
    const chosen = rows.filter(r => r.play.checked);
    const body = {
      factions: chosen.map(r => r.key),
      humans: chosen.filter(r => r.human.checked).map(r => r.key),
      rounds: Number(roundsInput.value),
      computer: computer.value,
    };
    if (seedInput.value !== '') body.seed = Number(seedInput.value);
    try {
      const created = await api('/api/games', body);
      ShowLinks(created);
    } catch (e) {
      error.textContent = e.message;
    }
  }

  function ShowLinks(created) {
    const base = location.origin + '/?game=' + encodeURIComponent(created.game);
    const seats = Object.entries(created.seats);
    result.replaceChildren(el('div', {class: 'panel'},
      el('h2', {}, 'Game created'),
      el('p', {class: 'muted'}, seats.length
        ? 'Send each player their own link: the link is their seat. Keep yours to yourself.'
        : 'No human seats: everyone can watch.'),
      el('ul', {class: 'links'},
        seats.map(([name, token]) => {
          const link = base + '&seat=' + encodeURIComponent(token);
          return el('li', {}, el('strong', {}, name), ': ',
                    el('a', {class: 'button', href: link, target: '_blank'}, 'Open'), ' ',
                    el('button', {onclick: () => navigator.clipboard.writeText(link)}, 'Copy link'),
                    el('div', {}, el('code', {}, link)));
        }),
        el('li', {}, el('strong', {}, 'Watch'), ': ',
           el('a', {class: 'button', href: base, target: '_blank'}, 'Open'),
           el('div', {}, el('code', {}, base))))));
  }

  app.replaceChildren(el('div', {class: 'lobby'},
    el('div', {class: 'panel'},
      el('h2', {}, 'Set up a game'),
      el('p', {class: 'muted'},
        'Choose 2–6 factions and tick "human" for the seats people will play. ',
        'The computer plays the rest. Strategy cards and objectives are not in yet: ',
        'rounds are action phase plus a cut-down status phase.'),
      el('div', {class: 'faction-list'}, rows.map(r => r.node)),
      el('h3', {}, 'Options'),
      el('div', {class: 'row'},
        el('label', {}, 'Rounds ', roundsInput),
        el('label', {}, 'Computer plays ', computer),
        el('label', {}, 'Seed ', seedInput)),
      el('div', {class: 'actions', style: 'margin-top:12px'},
        el('button', {class: 'primary', onclick: Create}, 'Create game')),
      error),
    result));
}

// ---------- Game view ----------

let view = null;          // the latest state from the server
let shownDecision = null; // id of the decision currently in the panel
let selected = null;      // a system key chosen on the map, for some decisions
let mapNode = null;

const HEX = 62;
const SQRT3 = Math.sqrt(3);

function hexCenter(s) {
  return [HEX * 1.5 * s.q, HEX * SQRT3 * (s.r + s.q / 2)];
}

function hexPoints(cx, cy, size) {
  const points = [];
  for (let i = 0; i < 6; i++) {
    const a = Math.PI / 3 * i;
    points.push((cx + size * Math.cos(a)).toFixed(1) + ',' + (cy + size * Math.sin(a)).toFixed(1));
  }
  return points.join(' ');
}

function playerColor(name) {
  const p = view.players.find(p => p.name === name);
  return p ? p.color : '#888';
}

const ANOMALY_FILL = {
  nebula: '#3c2f5c', supernova: '#5c2418', asteroid_field: '#3f3e2c', gravity_rift: '#24183a'};

function selectableSystems() {
  const pending = view.pending;
  if (!pending || !pending.kind) return {};
  if (pending.kind === 'activation') {
    const result = {};
    for (const s of pending.data.systems) result[s.key] = s.movers > 0 ? 'strong' : 'weak';
    return result;
  }
  if (pending.kind === 'retreat_system') {
    return Object.fromEntries(pending.data.systems.map(s => [s.key, 'strong']));
  }
  return {};
}

function DrawMap() {
  const systems = view.board.systems;
  const selectable = selectableSystems();
  const homes = Object.fromEntries(view.players.map(p => [p.home, p.name]));
  let minX = Infinity, minY = Infinity, maxX = -Infinity, maxY = -Infinity;
  const hexes = systems.map(s => {
    const [cx, cy] = hexCenter(s);
    minX = Math.min(minX, cx - HEX); maxX = Math.max(maxX, cx + HEX);
    minY = Math.min(minY, cy - HEX); maxY = Math.max(maxY, cy + HEX);
    const kind = selectable[s.key];
    const isSelected = selected === s.key;
    let fill = '#1c2333';
    if (s.anomaly) fill = ANOMALY_FILL[s.anomaly];
    if (s.tile === '18') fill = '#3a3320';
    const stroke = isSelected ? '#ffffff' : kind === 'strong' ? '#f5c542' : '#33405c';
    const width = isSelected ? 4 : kind === 'strong' ? 3 : 1;
    const parts = [
      svg('polygon', {points: hexPoints(cx, cy, HEX - 2), fill, stroke, 'stroke-width': width}),
    ];
    if (homes[s.key]) {
      parts.push(svg('polygon', {points: hexPoints(cx, cy, HEX - 7), fill: 'none',
                                 stroke: playerColor(homes[s.key]), 'stroke-width': 3,
                                 opacity: 0.8}));
    }
    // A dashed edge when every planet here belongs to one player (other
    // than a player's own home, which already has its solid edge).
    const owners = new Set(s.planets.map(p => p.controller));
    const owner = s.planets.length && owners.size === 1 ? [...owners][0] : null;
    if (owner && homes[s.key] !== owner) {
      parts.push(svg('polygon', {points: hexPoints(cx, cy, HEX - 10), fill: 'none',
                                 stroke: playerColor(owner), 'stroke-width': 3,
                                 'stroke-dasharray': '7 5', opacity: 0.9}));
    }
    // Tile label and command tokens along the top.
    parts.push(svg('text', {x: cx, y: cy - HEX * 0.62, 'text-anchor': 'middle',
                            'font-size': 10, fill: '#8f9ab3'}, s.label));
    s.command_tokens.forEach((name, i) => parts.push(svg('circle', {
      cx: cx + HEX * 0.38 + i * 9, cy: cy - HEX * 0.66, r: 4, fill: playerColor(name),
      stroke: '#000', 'stroke-width': 0.5, class: 'tip'},
      svg('title', {}, name + "'s command token"))));
    // Planets, each with its controller and units.
    let y = cy - HEX * 0.36;
    for (const planet of s.planets) {
      const color = planet.controller ? playerColor(planet.controller) : '#5d6782';
      const name = planet.name.length > 11 ? planet.name.slice(0, 10) + '…' : planet.name;
      parts.push(svg('circle', {cx: cx - HEX * 0.62, cy: y - 3.5, r: 3.5, fill: color}));
      const about = planet.name + ': ' + planet.resources + ' resources, ' +
        planet.influence + ' influence' +
        (planet.trait ? ', ' + planet.trait : '') +
        (planet.specialty ? ', ' + planet.specialty + ' specialty' : '') +
        '\n' + (planet.controller ? 'Controlled by ' + planet.controller : 'Not controlled') +
        (planet.exhausted ? ' (exhausted)' : '');
      parts.push(svg('text', {x: cx - HEX * 0.52, y, 'font-size': 10, class: 'tip',
                              fill: planet.exhausted ? '#6b7590' : '#e4e8f1'},
                     svg('title', {}, about),
                     name + ' ' + planet.resources + '/' + planet.influence));
      y += 11;
      for (const [player, counts] of Object.entries(planet.units)) {
        parts.push(svg('text', {x: cx - HEX * 0.52, y, 'font-size': 9, class: 'tip',
                                fill: playerColor(player)},
                       svg('title', {}, player + ' on ' + planet.name + ': ' + unitWords(counts)),
                       unitSummary(counts)));
        y += 10;
      }
    }
    // Ships and anything else in space, along the bottom.
    let sy = cy + HEX * 0.5;
    for (const [player, counts] of Object.entries(s.space).reverse()) {
      parts.push(svg('text', {x: cx, y: sy, 'text-anchor': 'middle', 'font-size': 10,
                              'font-weight': 600, fill: playerColor(player), class: 'tip'},
                     svg('title', {}, player + ' in space: ' + unitWords(counts)),
                     unitSummary(counts)));
      sy -= 11;
    }
    return svg('g', {class: 'hex' + (kind ? ' selectable' : ''),
                     onclick: kind ? () => { selected = s.key; Render(true); } : null},
               svg('title', {}, s.label + (s.planets.length ? ': ' +
                   s.planets.map(p => p.name).join(', ') : '')),
               parts);
  });
  const width = maxX - minX, height = maxY - minY;
  return svg('svg', {viewBox: [minX - 4, minY - 4, width + 8, height + 8].join(' '),
                     role: 'img', 'aria-label': 'Galaxy map'}, hexes);
}

function Legend() {
  return el('div', {class: 'legend'}, view.players.map(p =>
    el('span', {class: 'legend-item', title: p.faction},
       el('span', {class: 'swatch', style: 'background:' + p.color}),
       el('strong', {}, p.name), ' ', p.faction, p.name === view.seat ? ' (you)' : '')),
    el('span', {class: 'legend-item muted'},
       'solid edge: home system · dashed edge: all planets held by one player'));
}

function PlayersPanel() {
  const deciding = view.pending ? view.pending.player : null;
  return el('div', {class: 'panel'},
    el('h2', {}, 'Players'),
    el('table', {},
      el('tr', {}, el('th', {}, ''), el('th', {class: 'num', title: 'Victory points'}, 'VP'),
         el('th', {class: 'num', title: 'Tactic / fleet / strategy tokens'}, 'T/F/S'),
         el('th', {class: 'num', title: 'Trade goods'}, 'TG'),
         el('th', {class: 'num', title: 'Ready / total resources'}, 'Res'),
         el('th', {class: 'num', title: 'Ready / total influence'}, 'Inf'),
         el('th', {}, '')),
      view.players.map(p => el('tr', {title: p.faction + (p.technologies.length
                                         ? '\n' + p.technologies.join(', ') : '')},
        el('td', {}, el('span', {class: 'swatch', style: 'background:' + p.color}),
           p.name, p.name === view.seat ? ' (you)' : '', p.name === view.speaker ? ' ★' : ''),
        el('td', {class: 'num'}, p.victory_points),
        el('td', {class: 'num'}, p.tactic + '/' + p.fleet + '/' + p.strategy),
        el('td', {class: 'num'}, p.trade_goods),
        el('td', {class: 'num'}, p.resources[0] + '/' + p.resources[1]),
        el('td', {class: 'num'}, p.influence[0] + '/' + p.influence[1]),
        el('td', {class: 'muted'}, p.name === deciding ? 'deciding…'
           : p.passed ? 'passed' : p.human ? '' : 'computer')))),
    el('p', {class: 'muted', style: 'margin:8px 0 0'}, '★ speaker. Map: unit counts like CV2 = 2 carriers; ',
       '* = damaged. Dots on planets show who controls them; dots at the top are command tokens.'));
}

function LogPanel() {
  const log = el('div', {class: 'log'}, view.narrative.join('\n'));
  requestAnimationFrame(() => { log.scrollTop = log.scrollHeight; });
  return el('div', {class: 'panel'}, el('h2', {}, 'Log'), log,
            el('div', {class: 'row', style: 'margin-top:8px'},
               el('a', {class: 'button', href: '/api/games/' + encodeURIComponent(GAME) + '/save',
                        download: 'twimp-' + GAME + '.json'}, 'Download save')));
}

// ---------- Decisions ----------

function DecisionPanel() {
  const pending = view.pending;
  if (view.status !== 'running') {
    return el('div', {class: 'panel decision waiting'},
      el('h2', {}, view.status === 'error' ? 'Stopped' : 'Game over'),
      el('p', {}, view.error || (view.winner ? view.winner + ' wins.' : 'All rounds played.')));
  }
  if (!pending) {
    return el('div', {class: 'panel decision waiting'}, el('p', {class: 'muted'},
      'The computer is playing…'));
  }
  if (!pending.kind) {
    return el('div', {class: 'panel decision waiting'}, el('p', {class: 'muted'},
      'Waiting for ' + pending.player + ' to decide…'));
  }
  const error = el('div', {class: 'error'});
  async function Send(answer) {
    error.textContent = '';
    try {
      await api('/api/games/' + encodeURIComponent(GAME) + '/answer',
                {seat: SEAT, id: pending.id, answer});
      Poll(true);
    } catch (e) {
      error.textContent = e.message;
    }
  }
  const body = (FORMS[pending.kind] || UnknownForm)(pending, Send);
  return el('div', {class: 'panel decision'},
    el('h2', {}, 'Your decision'),
    el('p', {class: 'prompt'}, pending.prompt),
    body, error);
}

function Buttons(choices, value, send) {
  return el('div', {class: 'actions'}, choices.map(([label, answer]) =>
    el('button', {class: answer === value ? 'primary' : '', onclick: () => send(answer)}, label)));
}

function Confirm(onclick, label) {
  return el('div', {class: 'actions'},
    el('button', {class: 'primary', onclick}, label || 'Confirm'));
}

function NumberInput(value, min, max, onchange, label) {
  return el('input', {type: 'number', value, min, max, 'aria-label': label,
                      oninput: e => onchange(parseInt(e.target.value || '0', 10))});
}

const FORMS = {
  action(p, send) {
    const labels = {tactical: 'Tactical action', pass: 'Pass'};
    return el('div', {},
      el('p', {class: 'muted'}, plural(p.data.tactic_tokens, 'tactic token') + ' left.'),
      Buttons(p.data.options.map(o => [labels[o] || o, o]), p.default, send));
  },

  custodians(p, send) {
    return Buttons([['Yes, remove it', true], ['No', false]], p.default, send);
  },

  retreat(p, send) {
    return el('div', {},
      el('p', {class: 'muted'}, 'You: ' + (p.data.own || 'nothing') + '. Them: ' +
         (p.data.enemy || 'nothing') + '.'),
      Buttons([['Retreat', true], ['Keep fighting', false]], p.default, send));
  },

  activation(p, send) {
    if (selected === null || !p.data.systems.some(s => s.key === selected)) selected = p.default;
    const choice = p.data.systems.find(s => s.key === selected);
    const reachable = p.data.systems.filter(s => s.movers > 0)
      .sort((a, b) => b.movers - a.movers);
    return el('div', {},
      el('p', {class: 'muted'}, 'Click a system on the map, or pick one here.'),
      el('div', {class: 'row'}, reachable.map(s =>
        el('button', {class: s.key === selected ? 'primary' : '',
                      onclick: () => { selected = s.key; Render(true); }},
           s.label + ' (' + s.movers + ')'))),
      el('p', {}, 'Selected: ', el('strong', {}, choice ? choice.label : '—'),
         choice && choice.enemies.length ? el('span', {class: 'error'},
           ' enemy ships: ' + choice.enemies.join(', ')) : ''),
      Confirm(() => send(selected), 'Activate'));
  },

  retreat_system(p, send) {
    if (selected === null || !p.data.systems.some(s => s.key === selected)) selected = p.default;
    return el('div', {},
      el('div', {class: 'row'}, p.data.systems.map(s =>
        el('button', {class: s.key === selected ? 'primary' : '',
                      onclick: () => { selected = s.key; Render(true); }}, s.label))),
      Confirm(() => send(selected), 'Retreat'));
  },

  movement(p, send) {
    const plan = {};
    for (const m of p.default) plan[m.ship] = {move: true, ground: m.ground, fighters: m.fighters};
    const rows = p.data.ships.map(ship => {
      const entry = plan[ship.index] || (plan[ship.index] = {move: false, ground: 0, fighters: 0});
      const avail = p.data.available[ship.start] || {ground: 0, fighters: 0};
      return el('tr', {},
        el('td', {}, el('input', {type: 'checkbox', checked: entry.move,
                                  'aria-label': 'Move ' + ship.unit + ' from ' + ship.start_label,
                                  onchange: e => { entry.move = e.target.checked; }})),
        el('td', {}, ship.unit + (ship.damaged ? '*' : '')),
        el('td', {class: 'muted'}, ship.route.join(' › ') +
           (ship.rifts ? ' ⚠ ' + plural(ship.rifts, 'rift roll') : '')),
        el('td', {}, ship.capacity ? el('span', {},
          NumberInput(entry.ground, 0, Math.min(ship.capacity, avail.ground), v => { entry.ground = v; },
                      'Ground forces on this ' + ship.unit),
          ' ', NumberInput(entry.fighters, 0, Math.min(ship.capacity, avail.fighters),
                           v => { entry.fighters = v; }, 'Fighters on this ' + ship.unit)) : ''));
    });
    const available = Object.entries(p.data.available).map(([key, a]) => {
      const ship = p.data.ships.find(s => s.start === key);
      return (ship ? ship.start_label : key) + ': ' + a.ground + ' ground, ' + a.fighters + ' fighters';
    });
    return el('div', {},
      el('table', {}, el('tr', {}, el('th', {}, 'Move'), el('th', {}, 'Ship'),
                         el('th', {}, 'Route'), el('th', {}, 'Carry: ground, fighters')), rows),
      available.length ? el('p', {class: 'muted'}, 'Available to carry — ' + available.join('; ')) : '',
      Confirm(() => send(Object.entries(plan).filter(([, e]) => e.move)
        .map(([ship, e]) => ({ship: Number(ship), ground: e.ground, fighters: e.fighters}))),
        'Move'));
  },

  hits(p, send) {
    const counts = p.data.units.map(u => p.default.filter(i => i === u.index).length);
    const total = el('span', {});
    const update = () => { total.textContent = counts.reduce((a, b) => a + b, 0) + ' of ' + p.data.hits; };
    update();
    return el('div', {},
      el('table', {}, p.data.units.map(u => el('tr', {},
        el('td', {}, u.unit + (u.damaged ? ' (damaged)' : '')),
        el('td', {}, NumberInput(counts[u.index], 0, u.can_take,
                                 v => { counts[u.index] = v; update(); }, 'Hits on ' + u.unit))))),
      el('p', {class: 'muted'}, 'Assigned: ', total),
      Confirm(() => send(counts.flatMap((n, i) => Array(Math.max(0, n)).fill(i))), 'Assign hits'));
  },

  remove(p, send) {
    const picks = new Set(p.default);
    return el('div', {},
      el('p', {class: 'muted'}, 'Choose ' + p.data.count + '.'),
      p.data.units.map(u => el('label', {style: 'display:block'},
        el('input', {type: 'checkbox', checked: picks.has(u.index),
                     onchange: e => e.target.checked ? picks.add(u.index) : picks.delete(u.index)}),
        ' ', u.unit)),
      Confirm(() => send([...picks]), 'Remove'));
  },

  bombardment(p, send) {
    let choice = p.default;
    const name = 'bombard-' + p.id;
    return el('div', {},
      p.data.planets.map(pl => el('label', {style: 'display:block'},
        el('input', {type: 'radio', name, checked: choice === pl.index,
                     onchange: () => { choice = pl.index; }}),
        ' ', pl.name, el('span', {class: 'muted'}, ' (' + (pl.controller || 'neutral') + ', ' +
                                   plural(pl.defenders, 'defender') + ')'))),
      el('label', {style: 'display:block'},
        el('input', {type: 'radio', name, checked: choice === null, onchange: () => { choice = null; }}),
        ' Don\'t bombard'),
      Confirm(() => send(choice), 'Bombard'));
  },

  landing(p, send) {
    const counts = p.default.slice();
    const left = el('span', {});
    const update = () => { left.textContent = p.data.forces - counts.reduce((a, b) => a + b, 0); };
    update();
    return el('div', {},
      el('table', {}, p.data.planets.map(pl => el('tr', {},
        el('td', {}, pl.name, el('span', {class: 'muted'}, ' (' + (pl.controller || 'neutral') + ', ' +
                                  plural(pl.defenders, 'defender') + ')')),
        el('td', {}, NumberInput(counts[pl.index], 0, p.data.forces,
                                 v => { counts[pl.index] = v; update(); }, 'Land on ' + pl.name))))),
      el('p', {class: 'muted'}, 'Staying in space: ', left),
      Confirm(() => send(counts), 'Land'));
  },

  production(p, send) {
    const counts = Object.fromEntries(p.data.units.map(u => [u.type, p.default[u.type] || 0]));
    const summary = el('span', {});
    const update = () => {
      let units = 0, cost = 0;
      for (const u of p.data.units) {
        const n = counts[u.type] || 0;
        units += n;
        cost += Math.ceil(n / u.per_cost) * u.cost;
      }
      summary.textContent = units + ' of ' + p.data.limit + ' units, costing ' + cost +
        ' of ' + p.data.budget + ' resources';
    };
    update();
    return el('div', {},
      el('p', {class: 'muted'}, 'Room for ' + plural(p.data.fleet_room, 'more non-fighter ship') +
         ' (fleet pool) and ' + plural(p.data.fighter_room, 'fighter') + '.' +
         (p.data.can_produce_ships ? '' : ' Blockaded: ground forces only.')),
      el('table', {}, el('tr', {}, el('th', {}, 'Unit'), el('th', {}, 'Cost'), el('th', {}, 'Left'),
                         el('th', {}, 'Build')),
        p.data.units.map(u => el('tr', {},
          el('td', {}, u.type),
          el('td', {class: 'muted'}, u.per_cost > 1 ? u.cost + ' for ' + u.per_cost : u.cost),
          el('td', {class: 'muted'}, u.room == null ? '∞' : u.room),
          el('td', {}, NumberInput(counts[u.type], 0, p.data.limit,
                                   v => { counts[u.type] = v; update(); }, 'Build ' + u.type))))),
      el('p', {}, summary),
      Confirm(() => send(counts), 'Produce'));
  },

  command_tokens(p, send) {
    const split = p.default.slice();
    const total = el('span', {});
    const update = () => { total.textContent = split.reduce((a, b) => a + b, 0) + ' of ' + p.data.total; };
    update();
    const names = ['Tactic', 'Fleet', 'Strategy'];
    return el('div', {},
      el('p', {class: 'muted'}, 'Before: ' + p.data.current.join(' / ') + ' (tactic / fleet / strategy).'),
      el('div', {class: 'row'}, names.map((name, i) => el('label', {}, name + ' ',
        NumberInput(split[i], 0, p.data.total, v => { split[i] = v; update(); }, name + ' tokens')))),
      el('p', {class: 'muted'}, 'Total: ', total),
      Confirm(() => send(split), 'Confirm'));
  },
};

function UnknownForm(p, send) {
  return el('div', {}, el('p', {class: 'muted'}, 'No form for "' + p.kind + '" yet.'),
            Confirm(() => send(p.default), 'Accept the suggestion'));
}

// ---------- Battles ----------

// Battles this browser has already seen and closed. Kept per game in
// sessionStorage so a reload doesn't replay them; works without it too.
const SEEN_KEY = 'twimp-seen-battles-' + GAME;
let seenBattles = null;

function LoadSeen() {
  try {
    const stored = sessionStorage.getItem(SEEN_KEY);
    if (stored) return new Set(JSON.parse(stored));
  } catch (e) { /* storage unavailable */ }
  return null;
}

function SaveSeen() {
  try { sessionStorage.setItem(SEEN_KEY, JSON.stringify([...seenBattles])); } catch (e) { }
}

function CurrentBattle() {
  if (seenBattles === null) {
    // First time we see this game: don't replay battles that already ended.
    seenBattles = LoadSeen() ||
      new Set(view.battles.filter(b => b.status === 'over').map(b => b.id));
    SaveSeen();
  }
  return view.battles.find(b => !seenBattles.has(b.id)) || null;
}

const COMBAT_DECISIONS = ['hits', 'retreat', 'retreat_system'];

// Should the pending decision be shown inside the battle overlay?
function DecisionInBattle(battle) {
  const pending = view.pending;
  if (!battle || !pending || !pending.kind || !COMBAT_DECISIONS.includes(pending.kind)) return false;
  const latest = view.battles[view.battles.length - 1];
  if (battle !== latest) return false;
  if (pending.kind === 'retreat_system') return battle.retreated === view.seat;
  return battle.status === 'fighting' && [battle.attacker, battle.defender].includes(view.seat);
}

function Side(battle, index) {
  const name = index === 0 ? battle.attacker : battle.defender;
  return el('div', {class: 'battle-side'},
    el('h3', {}, el('span', {class: 'swatch', style: 'background:' + playerColor(name)}),
       name, el('span', {class: 'muted'}, index === 0 ? ' attacking' : ' defending')),
    el('div', {}, battle.now[index] || el('span', {class: 'muted'}, 'nothing left')),
    el('div', {class: 'muted'}, 'started with ' + (battle.before[index] || 'nothing')));
}

function BattleOverlay(battle, decision) {
  const where = battle.kind === 'space' ? 'Space combat at ' + battle.system
    : 'Ground combat on ' + battle.planet + ' (' + battle.system + ')';
  let result;
  if (battle.status === 'fighting') {
    result = el('p', {class: 'muted'}, battle.rolling ? ''
      : battle.round ? 'Round ' + (battle.round + 1) + ' next…' : 'The fight is starting…');
  } else if (battle.retreated) {
    result = el('p', {}, el('strong', {}, battle.retreated + ' retreats.'));
  } else if (battle.winner) {
    result = el('p', {}, el('strong', {}, battle.winner + ' wins.'));
  } else {
    result = el('p', {}, el('strong', {}, 'Both sides are destroyed.'));
  }
  const hitsText = (r, i) => (r.afb[i] ? 'barrage: ' + plural(r.afb[i], 'hit') + '; ' : '') +
    plural(r.hits[i], 'hit');
  const rows = battle.rounds.map(r => el('tr', {},
    el('td', {}, r.round),
    [0, 1].map(i => el('td', {}, hitsText(r, i),
      r.losses[i] ? el('div', {class: 'muted'}, 'lost ' + r.losses[i]) : '')),
    el('td', {class: 'muted'}, r.retreat ? r.retreat + ' retreats' : '')));
  if (battle.rolling) {
    const r = battle.rolling;
    rows.push(el('tr', {}, el('td', {}, r.round),
      [0, 1].map(i => el('td', {}, hitsText(r, i))),
      el('td', {class: 'muted'}, 'assigning hits…')));
  }
  return el('div', {class: 'overlay-backdrop'},
    el('div', {class: 'overlay panel', role: 'dialog', 'aria-label': where},
      el('h2', {}, where, battle.status === 'fighting' ? el('span', {class: 'live'}, ' · live') : ''),
      el('div', {class: 'battle-sides'}, Side(battle, 0), el('div', {class: 'vs'}, 'vs'),
         Side(battle, 1)),
      rows.length ? el('table', {class: 'battle-rounds'},
        el('tr', {}, el('th', {}, 'Round'), el('th', {}, battle.attacker), el('th', {}, battle.defender),
           el('th', {}, '')), rows) : '',
      result,
      decision || '',
      el('div', {class: 'actions'},
        el('button', {disabled: !!decision, onclick: () => {
          seenBattles.add(battle.id); SaveSeen(); Render(true); }},
          battle.status === 'fighting' ? 'Hide' : 'Close'))));
}

// ---------- Rendering and polling ----------

let decisionNode = null;

function Render(selectionChanged) {
  const pending = view.pending;
  const decisionId = pending && pending.kind ? pending.id : null;
  if (decisionId !== shownDecision) {
    selected = null;
    if (pending && (pending.kind === 'activation' || pending.kind === 'retreat_system')) {
      selected = pending.default;
    }
  }
  statusLine.textContent = 'Round ' + view.round + ' · ' + view.phase + ' phase' +
    (view.custodians ? ' · custodians on Mecatol Rex' : '') +
    (view.seat ? ' · you are ' + view.seat : ' · watching');
  const newMap = DrawMap();
  // Keep the decision form (and anything typed into it) unless the decision
  // changed, or a map click changed the selection.
  if (decisionId !== shownDecision || selectionChanged || !decisionNode) {
    decisionNode = DecisionPanel();
    shownDecision = decisionId;
  }
  if (!mapNode) {
    mapNode = el('div', {class: 'map-wrap'});
    app.replaceChildren(el('div', {class: 'game'}, mapNode,
                           el('div', {class: 'side'}, el('div', {id: 'decision'}),
                              el('div', {id: 'players'}), el('div', {id: 'log'}))));
  }
  mapNode.replaceChildren(Legend(), newMap);
  const battle = CurrentBattle();
  const inBattle = DecisionInBattle(battle);
  document.getElementById('decision').replaceChildren(inBattle
    ? el('div', {class: 'panel decision'}, el('p', {}, 'Your decision is in the battle window.'))
    : decisionNode);
  document.getElementById('overlay').replaceChildren(
    battle ? BattleOverlay(battle, inBattle ? decisionNode : null) : '');
  document.getElementById('players').replaceChildren(PlayersPanel());
  document.getElementById('log').replaceChildren(LogPanel());
}

let polling = false;

async function Poll(force) {
  if (polling) return;
  polling = true;
  try {
    const q = '?seat=' + encodeURIComponent(SEAT || '') +
      (view && !force ? '&version=' + view.version : '');
    const next = await api('/api/games/' + encodeURIComponent(GAME) + q);
    if (!next.unchanged) {
      view = next;
      Render(false);
    }
  } catch (e) {
    statusLine.textContent = 'Connection problem: ' + e.message;
  } finally {
    polling = false;
  }
}

function Game() {
  app.replaceChildren(el('p', {class: 'muted'}, 'Loading…'));
  Poll(true);
  setInterval(() => Poll(false), 700);
}

if (GAME) Game(); else Lobby();
