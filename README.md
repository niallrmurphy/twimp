# twimp

A Twilight Imperium (4th edition, base game) engine in Python, with a
browser UI. No dependencies beyond Python 3.9+.

## Play in the browser

```
python3 -m twimp.server
```

Open http://localhost:8000/, choose factions, tick "human" for the seats
people will play, and create the game. Each human seat gets its own link;
send each player theirs. The computer plays the other seats.

To let people on other machines join, run `python3 -m twimp.server --host 0.0.0.0`
and give them links using your machine's address instead of `localhost`.

What's in: setup for 15 factions, tactical actions (movement, space cannon,
space combat with retreats, invasion, production), passing, taking Mecatol
Rex, and a cut-down status phase. Not in yet: strategy cards, objectives,
technology effects, action cards and agendas. See [ROADMAP.md](ROADMAP.md).

## Command-line tools

```
python3 -m twimp.play_turn --human sol --rounds 3     # play in the terminal
python3 -m twimp.game_cli new --save game.json        # set up and save a game
python3 -m twimp.show_map --from 26 --move 2          # where can a ship go?
python3 -m twimp.simulate dreadnought=2 destroyer=4   # space combat odds
python3 -m twimp.simulate_invasion --ground infantry=3 --planet infantry=2,pds
```

## Tests

```
python3 -m unittest
```
