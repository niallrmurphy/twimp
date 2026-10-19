# twimp roadmap: from unit stubs to a playable round

Target ruleset: **Twilight Imperium 4th Edition, base game** (no Prophecy of Kings).
The code already leans 4e; the 3e branches (e.g. carrier capacity 6) should be
dropped rather than maintained in parallel.

Two milestones define "a turn end-to-end":

- **Milestone A (stage 5):** one player takes a complete *tactical action*:
  activate a system, move, space cannon, space combat, invasion, production.
- **Milestone B (stage 9):** a full *game round* (strategy, action, status and
  agenda phases) played by scripted or random-legal players, reproducible from
  a seed, with a readable log.

Each stage below ends in a working, tested state. Stages are kept small on
purpose.

---

## Where things stand

Run the tests from the repo root with `python3 -m unittest`.

| Area | State |
|---|---|
| `twimp/units.py` | 4e unit data table (`UNIT_STATS`) and a single `Unit` class keyed by `UnitType`. Handles sustain damage, cargo, and combat, AFB, bombardment and space cannon rolls. |
| `twimp/dice.py` | Seedable `Dice`; every roll goes through an injected instance. |
| `twimp/fleet.py` | Two-sided `Fleet`: attack rounds, greedy hit assignment with sustain damage, building against a budget and plastic limits. |
| `twimp/board.py` | `Hex` and `Planet` with no geometry; most methods are stubs. |
| `twimp/cards.py` | Empty. |
| `tests/` | 45 tests. `tests/fakes.py` has `ScriptedDice` for exact dice-by-dice scenarios. |

---

## Stage 0: Foundations ✅ done

- Code is in a `twimp` package with tests under `tests/`, and the 3e branches are gone.
- Dice are seedable and passed into every roll.
- One unit data table holds the 4e stats. Dreadnought move and capacity,
  bombardment and war sun capacity are now correct; infantry are added; PDS
  and space docks are structures and don't absorb space combat hits.
- Bugs fixed, each with a regression test: the undefined `Dice` in dreadnought
  and AFB rolls, `Flagship`'s wrong `super`, `RemoveFromCargo`, hits soaked by
  sustain damage going uncounted, carriers never being assigned hits, the
  budget never being spent, player `0` aliasing player 2, and failed builds
  reporting success.

Still open: space docks can be "built" through `Fleet.AddShipToFleet`, which
the rules don't allow (they come from the Construction strategy card). This can
stay until production is done properly in stage 5.

## Stage 1: Correct space combat (in isolation)

Goal: a faithful 4e space combat between two forces in one system, with no board yet.

- The combat sequence in rules order: anti-fighter barrage (first round only),
  then retreat declaration (stub it for now), then simultaneous rolls, then hit
  assignment, repeating until one side is gone.
- Treat Sustain Damage as a choice: a damaged ship is flipped, not removed, and
  the hit counts as assigned.
- **Introduce the decision interface here**: a `Player`/`Agent` protocol with
  a first method such as `assign_hits(units, n) -> assignment`. Ship the
  current greedy logic as the default policy. Every later player choice goes
  through this same seam.
- A small CLI combat simulator that prints win probabilities for two fleets
  over N runs. This is useful right away and a good check on correctness.

**Done when:** scripted scenarios (e.g. 2 dreadnoughts vs 4 destroyers with fixed
dice) resolve exactly as worked by hand from the rules.

## Stage 2: Ground combat and invasion (still no board)

- Infantry as units, planets carrying ground forces per player.
- Invasion steps: bombardment (blocked by planetary shield), commit ground
  forces, space cannon defense, ground combat, establish control.
- Planet ownership changes hands and the planet becomes exhausted on capture.

**Done when:** scripted invasions resolve correctly, including the PDS
planetary shield blocking bombardment.

## Stage 3: The galaxy

Goal: a real map with positions, adjacency and movement legality.

- Hex geometry using axial/cube coordinates: neighbours, distance, rings.
- Tile data as a data file: base-game system tiles 18–50 and home systems,
  with planets (resources, influence, trait, tech specialty), wormholes and
  anomalies. Mecatol Rex at the centre.
- Load a fixed map from a "tile string" (the space-separated tile-ID format
  used by community map tools). Random generation can wait.
- Adjacency includes matching alpha/beta wormholes.
- Anomaly movement rules: supernova and asteroid field impassable, nebula
  stops movement and gives defenders +1, gravity rift gives +1 move and can
  destroy ships passing through.
- Pathfinding: given a ship's move value and the board, find which systems it
  can reach. It can't move through systems containing enemy ships.
- An ASCII board display, good enough to debug with.

**Done when:** tests on a known map give the correct reachable systems for each
unit type, including wormhole and anomaly cases.

## Stage 4: Players and game state

- `Player`: a faction (start with one or two simple factions' starting units,
  home system and starting tech, or one generic faction), command tokens in
  tactic, fleet and strategy pools, trade goods, commodities, controlled
  planets (ready or exhausted), and owned technologies.
- `GameState`: board, players, units placed in systems (in space and on
  planets), round number, speaker, custodians token on Mecatol Rex.
- Constraints: fleet pool limits non-fighter ships per system, and capacity
  limits fighters and ground forces in space.
- Serialise to and from JSON so tests and debugging can start from a saved
  state.
- An append-only event log, so every state change is a recorded event. You
  will need this for debugging and replays.

**Done when:** a game can be set up from a map and factions, saved, reloaded,
and printed.

## Stage 5: The tactical action ← **Milestone A**

Wire stages 1–4 together into a single player turn:

1. **Activation:** place a tactic token. You can't activate a system that
   already holds your own token.
2. **Movement:** choose ships that can reach the system and aren't in systems
   holding your tokens, then carry fighters and ground forces within capacity.
3. **Space cannon offense:** PDS in and adjacent to the system fire.
4. **Space combat** (stage 1).
5. **Invasion** (stage 2).
6. **Production:** limit of space dock production (resources + 2), paid by
   exhausting planets or spending trade goods, within fleet pool and unit limits.

- Model each choice as an **action object** that the engine validates and
  applies, with a function that lists legal moves. This lets a random-legal
  agent and a CLI human agent use the same code.
- Agents: `ScriptedAgent` (for tests), `RandomLegalAgent`, and a basic
  `CliAgent`.

**Done when:** one player moves from their home system, fights a neutral or
enemy fleet, lands infantry and builds units, all from a seeded test and
playable from the CLI.

## Stage 6: The action phase loop

- The other action types: **pass**, **strategic action** (needs stage 7) and
  **component action** (stub it until cards exist).
- Players act one at a time in initiative order until everyone has passed.
- Claiming Mecatol Rex: spend 6 influence to remove the custodians token and
  gain 1 victory point. This unlocks the agenda phase.

**Done when:** several players alternate tactical actions until all pass.

## Stage 7: The strategy phase and strategy cards

- Players pick strategy cards in order starting with the speaker, and
  unchosen cards gain a trade good. Initiative order follows from the picks.
- The 8 cards, each with a primary and a secondary ability:
  Leadership, Diplomacy, Politics, Construction, Trade, Warfare, Technology,
  Imperial. Secondaries cost a strategy token.
- Technology needs a tech tree with colours and prerequisites. Add all
  techs as data first, then implement effects only for a handful, starting
  with unit upgrades (Cruiser II, Destroyer II, …) and Gravity Drive, since
  combat and movement already exist.
- Politics and Imperial reach into stages 8–9. Implement what you can and
  stub the rest (e.g. Politics "draw 2 action cards" can be a no-op until
  cards exist).

**Done when:** a strategy phase followed by an action phase runs with
strategic actions included.

## Stage 8: Status phase and objectives

- Public objectives: Stage I deck as data, with predicates over `GameState`
  (e.g. "control 4 cultural planets"). Secret objectives can start as a few
  examples.
- Status phase steps: score objectives, reveal the next public objective,
  draw action cards (stub until cards exist), remove command tokens, gain
  and redistribute 2 command tokens, ready cards, repair units, return
  strategy cards.
- This is where `cards/` gets real content: action cards as data, with a
  small number given effects at first.

## Stage 9: Agenda phase, setup, and the full round ← **Milestone B**

- Agenda phase, which happens only once the custodians token is removed (so in
  most first rounds it is skipped, legitimately): reveal 2 agendas and vote with
  influence. Start with a few laws and directives.
- Game setup: choose a map, assign factions and the speaker, place home
  systems, starting units, starting tech and command tokens, and reveal the
  first objectives.
- `play_round(state, agents, seed)`: strategy, action, status, then agenda.

**Done when:** a seeded game of 3–6 `RandomLegalAgent`s plays a full round
without errors and gives the same log every time; a human can take one seat
through the CLI.

---

## Design notes

- **Rules engine vs decisions.** The engine never makes a choice a player
  would make; it asks the agent. This keeps rules testable and makes AI agents
  possible later.
- **Data over code.** Units, tiles, techs, strategy cards, objectives and
  agendas live in data files. Code only implements effects that data can't express.
- **Timing windows.** Much of TI4 is "when X happens / after X happens"
  abilities (action cards, faction abilities, techs). Don't build a general
  hook system yet, but make each phase and step an explicit, named point in
  the engine so hooks can be added there later.
- **Determinism.** One seeded RNG, threaded through everything.

## Deliberately out of scope until after Milestone B

Promissory notes, transactions between players, most faction abilities,
leaders, the full action-card deck, Prophecy of Kings content, random map
generation, and any UI beyond a CLI.
