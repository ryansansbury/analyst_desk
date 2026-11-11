# Architecture

Analyst Desk is one build that turns a seed into a static page. The build generates a synthetic world, ingests it into a ledger, and runs the checks. It replays the agents' recorded runs through the same validation they passed when they ran, builds the deliverables, and renders every state of the page ahead of time. Nothing runs on a server, and nothing on the page calls a model or waits on the network.

```
seed -> generate/ -> overnight files -> intake -> checks -> ledger -> gate -> deliverables/ -> app/ -> site/
                                          ^                              ^
                                          +---- agents' recorded runs ---+
```

## The world

`generate/` builds three portfolio companies from one seed. They're a solar and storage operator, a regional freight company, and a resort. It simulates their days from July through December and writes 96 mornings of the files their systems would send overnight. It also writes budgets, a carve-out deal's data room, and twelve freight layouts for the intake eval.

The generator plants six errors and three look-alikes in known places. Their answer keys were frozen before any check existed, and the checks never see them.

## Intake and the checks

`engine/intake.py` parses each file with a known layout and records every value as a fact in the ledger with its file, row, column, and transform. A file in a new layout goes to the intake agent, and code accepts its mapping only when every check and the control total pass.

`engine/checks.py` holds the rules each morning's files face. They run from unit ranges and settlement ties to control totals and deposit ties. An error holds that company's report for a person. A look-alike is marked expected and the report publishes. A solar site the grid curtailed and a card deposit that lands a day later are two of them. The checks were frozen and scored once on seeds they had never seen.

## The ledger and the gate

`engine/ledger.py` is SQLite. Facts come from files, derived values keep their inputs and their formula, and checks keep the IDs they used. That lineage is what lets any figure on the page open a trace down to the cell it came from.

`engine/gate.py` stands between the agents and anything a person reads. Agent text may carry a figure only as a placeholder that cites a ledger ID, and the renderer writes in the verified value. A digit an agent typed fails the deliverable, and so does a placeholder that doesn't exist or sits next to the wrong unit.

## The agents

Five agents read and draft. The intake mapper maps a new file layout, the daily commentary writes the morning's notes, and the deal analyst proposes the model's assumptions inside ranges the history sets. The memo writer drafts the investment memo, and the board deck writer writes the slides' headlines and bullets. Each one has a fixed input, an output schema, and limits that code enforces, and none of them can publish anything on its own.

Every reply passes the same validation before it's used. That means the schema, the limits, the gate, and the writing rules. A reply that fails gets one repair request. `agents/replay.py` loads the recorded runs in `data/ai_runs/` and puts each one through that validation again on every build. A run that no longer holds against the ledger never shows.

## Routing

Seven models from Anthropic, OpenAI, and Google took the same tests with the same prompts and validation, and `evals/model_comparison.json` holds the result. `agents/routing.py` puts each agent on the cheapest model that cleared its quality bar. The intake mapper has to match the answer key within one layout of the best model with no harmful miss, and a prose agent has to pass validation every time.

Validation can't judge how prose reads. `config/models.json` holds the commentary, the deck, and the memo on the strongest writer because a person read every model's drafts.

## The deliverables and the page

`deliverables/` builds the deal model as a workbook with live formulas, the investment memo, the board deck, and the hours ledger. The workbook's values match the Python model in `engine/model.py` to the cent, and LibreOffice recalculating it from its formulas alone matches too.

`app/` renders every state of the page into `site/` ahead of time. That covers the clean morning and each planted error. Every visible figure is a trace link, and `WORDS.md` holds every word the page shows apart from the agents' drafts and the ledger's notes on each figure. The script in `app/ui/app.js` switches between the states and draws nothing it wasn't given.

## Tests and evals

`tests/` covers the generator, the engine, the agents' validators, the routing rules, the workbook, and the page itself. A click-through runs the page's own script against a small DOM through every state and presenter step. `scripts/screenshots.sh` checks the page in real Chrome at desktop, tablet, and phone widths for the line rule, overlaps, console errors, and network requests.

`evals/` holds the frozen catalog and answer keys, the frozen intake prompt, the check scores on held-out seeds, and the model comparison.
