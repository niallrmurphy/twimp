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
| `twimp/agents.py` | The decision interface: `Agent`, with every choice a player makes. Implemented by `GreedyAgent` (simple sensible play) and `RandomAgent` (random legal play, for shaking out bugs). |
| `twimp/cli_agent.py` | `CliAgent`: asks a person at the terminal, suggesting the greedy choice each time. |
| `twimp/tactical.py` | `TakeTacticalAction`: activation, movement, space cannon offense, space combat (with retreats), invasion and production, all validated, with a report. |
| `twimp/play_turn.py` | CLI: `python3 -m twimp.play_turn --human sol` to play a turn, or `--actions 6` to watch the computer. |
| `twimp/combat.py` | `SpaceCombat`: the full rules sequence (AFB, retreat announcements, rolls, validated hit assignment, retreat), with a per-round report. `GroundCombat` shares the round loop. |
| `twimp/simulate_invasion.py` | CLI odds of taking a planet: `python3 -m twimp.simulate_invasion --ships warsun --ground infantry=3 --planet infantry=2,pds --seed 1`. |
| `twimp/invasion.py` | `Invasion`: bombardment, committing ground forces, space cannon defense, ground combat, establishing control, with a report per planet. |
| `twimp/simulate.py` | CLI odds calculator: `python3 -m twimp.simulate dreadnought=2,carrier,fighter=3 destroyer=6 --seed 1`. |
| `twimp/fleet.py` | Older two-sided `Fleet`: building against a budget and plastic limits, plus simple attack rounds. Its damage handling now goes through `GreedyAgent`. |
| `twimp/hexes.py` | Axial hex coordinates: neighbours, distance, rings in map-string order. |
| `twimp/board.py` | `Planet` (controller, exhausted, trait, tech specialty, units), `System` (one tile: planets, wormholes, anomaly, units in space), and `Board` (systems on the grid, loaded from a map string, with wormhole adjacency and a text render). |
| `twimp/data/tiles.json` | Base-game tiles 1–50. |
| `twimp/data/factions.json` | 15 base-game factions: home system, commodities, starting tech and starting units. |
| `twimp/game.py` | `Player`, `GameState`, the event log, `NewGame` setup, a text summary, and JSON save/load. |
| `twimp/limits.py` | Capacity and fleet-pool checks, and removal of excess units. |
| `twimp/game_cli.py` | CLI: `python3 -m twimp.game_cli new --factions sol,hacan,naalu --save game.json`, then `show game.json`. |
| `twimp/movement.py` | Which systems a ship can reach, under the anomaly, wormhole and enemy-ship rules. |
| `twimp/show_map.py` | CLI: `python3 -m twimp.show_map --from 26 --move 2` draws the map and lists where a ship can go. |
| `twimp/cards.py` | Empty. |
| `tests/` | 192 tests. `tests/fakes.py` has `ScriptedDice` for exact dice-by-dice scenarios. |

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

## Stage 1: Correct space combat (in isolation) ✅ done

- `SpaceCombat` runs the rules sequence: anti-fighter barrage in round 1 only
  (hits go to fighters; extra hits are wasted, and if AFB leaves a side with
  no ships the combat ends), then retreat announcements (defender first; if
  the defender retreats the attacker can't), then simultaneous rolls, then
  hit assignment, then the retreat itself. Draws are possible.
- Every hit assignment comes from the side's `Agent` and is validated: the
  right number of hits, only on ships in the combat, and no ship taking more
  hits than it can absorb.
- `GreedyAgent` is the single home of the "lose as little as possible"
  policy; `Fleet` uses it too.
- Scripted-dice tests replay combats exactly, including 2 dreadnoughts vs 4
  destroyers worked through die by die.

Deferred to later stages:
- Where a ship retreats to, and whether it can, depends on the board, so
  for now the caller passes `attacker_can_retreat` and `defender_can_retreat`
  (stage 3/5).
- Space cannon offense is part of the tactical action, not space combat
  (stage 5).
- Removing fighters that exceed capacity after carriers are lost (stage 4,
  with the other capacity rules).
- Unit upgrades and combat modifiers, e.g. the nebula defender +1 (stages 3 and 7).

## Stage 2: Ground combat and invasion (still no board) ✅ done

- Planets hold each player's ground forces and structures, plus a controller
  and an exhausted flag. A newly gained planet is exhausted.
- `GroundCombat`: infantry roll 8, rounds repeat until one or both sides are
  gone, and there's no retreat.
- `Invasion` runs the five steps in order:
  1. **Bombardment**: only planets holding other players' ground forces can
     be targeted. A Planetary Shield (PDS) blocks it unless the active
     player has a war sun in the system. The defender picks its losses.
  2. **Commit ground forces**: the agent chooses which ground forces land on
     which planets. Any not committed stay in space.
  3. **Space cannon defense**: PDS on a planet fire at the ground forces
     just committed to it.
  4. **Ground combat** on each planet with both sides' ground forces.
  5. **Establish control**: the active player gains each planet it still
     has ground forces on, and other players' structures there are destroyed.
     If both sides are wiped out, the defender keeps the planet.
- `python3 -m twimp.simulate_invasion` estimates the odds of taking a planet.
- Every agent choice is validated (`IllegalChoice`). `GreedyAgent` bombards
  the planet with the most defenders and lands everything on the
  weakest-held planet it doesn't control.

Deferred:
- Ground forces in space come in as a plain list. Taking them off carriers
  (`Unit.cargo`) belongs with capacity in stage 4 and movement in stage 5.
- Players are plain strings until stage 4 brings `Player`.
- Mechs, and other PoK units, are out of scope.

## Stage 3: The galaxy ✅ done

- Hex geometry in axial coordinates for flat-topped tiles. Rings run
  clockwise from due north, the order map strings use.
- Tile data for base-game tiles 1–50 in `twimp/data/tiles.json`, checked
  planet by planet against [KeeganW/ti4](https://github.com/KeeganW/ti4). Two
  differences, both deliberate: Maaluuk is 0/2 here (that file has 2/0), and
  Resculon is spelled as on the card. The Maaluuk value is worth confirming
  against a physical card.
- `Board.FromMapString` loads space-separated tile ids ring by ring, with
  Mecatol Rex in the centre unless an explicit `{tile}` is given. `0` leaves
  a gap. A sample 6-player map is in `board.SAMPLE_MAP`.
- Adjacency includes matching wormholes (alpha–alpha, beta–beta).
- `movement.ReachableSystems` gives every legal destination and the route
  there, preferring routes with fewer gravity rift rolls, then shorter ones:
  - supernovas and asteroid fields can't be entered (asteroids can be, with
    an Antimass Deflectors flag);
  - a nebula can be entered but not moved through, and a ship starting in
    one has move 1;
  - each gravity rift moved out of gives +1 move, and the route records the
    roll it costs (`SurvivesGravityRift` destroys on 1–3);
  - systems with other players' ships can be ended in but not moved through.
- `python3 -m twimp.show_map` draws the map as text and shows a ship's reach.

Deferred:
- The Creuss delta wormhole: tile 17 has it, but the Creuss home system (51)
  isn't in the data yet. That comes with factions (stage 4).
- Rules that depend on whose turn it is: command tokens blocking movement,
  and the active system as the only legal destination (stage 5).
- Retreat destinations (stage 5), now that adjacency exists.
- Random map generation, and PoK hyperlanes.

## Stage 4: Players and game state ✅ done

- Faction data for 15 of the 17 base factions, converted from the
  [AsyncTI4 bot](https://github.com/AsyncTI4/TI4_map_generator_bot)'s
  `data/factions/base.json`. It includes which home planet each ground force
  and structure starts on. A test checks that every faction's starting units
  fit within capacity and the fleet pool.
- `Player`: faction, command tokens (3 tactic, 3 fleet, 2 strategy),
  trade goods, commodities and technologies (names only for now).
  Controlled planets are worked out from the board, so there's a single
  source of truth.
- `GameState`: board, players in seat order, speaker, round and phase, the
  custodians token, and an append-only event log.
- `NewGame(factions, map, speaker, seed)`: uses home systems already on the
  map, or puts them in empty outer-ring slots, then places starting units.
  Home planets start controlled and ready. The speaker is chosen at random
  from the seed.
- Limits (`twimp/limits.py`):
  - Capacity: fighters and ground forces in space vs. ship capacity, with 3
    free fighters per space dock in the system.
  - Fleet pool: non-fighter ships vs. fleet tokens.
  - When there's excess, the agent chooses what goes (`ChooseUnitsToRemove`),
    and it's logged.
- JSON save/load stores tile ids plus what changes during a game (control,
  exhaustion, units, damage, players, log). Loading rebuilds planets from
  tile data.
- `python3 -m twimp.game_cli new|show|factions`.

Deferred:
- The Clan of Saar (space docks start in space) and the Ghosts of Creuss
  (home system off the board), until faction abilities exist.
- Winnu's starting tech choice. They start with none for now.
- Reinforcements (the plastic limit across the whole board), command token
  supply (16 per player), and faction-specific units such as flagships.
- Calling the limit checks at the right moments: capacity after combat,
  both after movement and production. That's stage 5's job.

## Stage 5: The tactical action ✅ done: **Milestone A**

`tactical.TakeTacticalAction(state, player, agents, dice)` runs a full turn:

1. **Activation**: spends a tactic token. You can't activate a system that
   already has your command token.
2. **Movement**: offers each ship that can reach the active system, with its
   route. Ships can't leave (or pass through) systems with their own command
   token, and Antimass Deflectors lets them cross asteroid fields. Each ship
   carries up to its capacity in fighters and ground forces, taken from the
   system it starts in. Ships leaving a gravity rift roll to survive (losing
   their cargo if they don't). Units left behind without capacity are lost.
   **Space cannon offense** follows: PDS in the active system fire, starting
   with the active player.
3. **Space combat** if another player has ships there. A retreat is only
   possible to an adjacent system with no enemy ships that holds the
   player's units or a planet they control, and it places a command token
   there from reinforcements. Fleet pool and capacity are checked where the
   retreating ships land. Excess fighters and ground forces are destroyed at
   the end of the step.
4. **Invasion**: you can't land on Mecatol Rex while the custodians token
   is there.
5. **Production**: each space dock adds its planet's resources + 2 to the
   production limit. The fleet pool, capacity and reinforcements are
   checked, war suns need their technology, a blockaded dock can't build
   ships, and payment wastes as few resources as possible.

Players:
- **`GreedyAgent`** takes the most valuable unguarded planets it can reach
  with a carrier, leaving one ground force on each planet it takes them from.
  If there's nothing to take, it builds at home: a cruiser if the fleet pool
  has room, then infantry.
- **`RandomAgent`** makes random legal choices.
- **`CliAgent`** prompts a person, with the greedy choice as the default.

Testing:
- Scenario tests are worked die by die: combat, space cannon offense and
  defense, retreats (including fleet pool overflow at the destination),
  gravity rifts, the Mecatol custodians, production rules and payment.
- A random-play test runs games of random agents and checks after every
  action that no system exceeds capacity or the fleet pool, and that saving
  and reloading changes nothing. Before it was added, a longer version of this
  run found three real bugs: stranded units, space cannon fire leaving
  fighters over capacity, and removing fighters that the space dock was
  already covering.

Deferred:
- Picking up units from systems a ship moves through (only the start
  system for now).
- PDS II firing into adjacent systems, and other technology effects (stage 7).
- The "3 free fighters" bonus applies anywhere the player has a space dock.
  Production is also simplified: everything a dock builds lands on the first
  dock planet.
- Space combat with more than two players in one system.

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
