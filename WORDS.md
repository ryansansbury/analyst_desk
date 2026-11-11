# WORDS.md

Every visible word on the page lives here, and wording changes happen in one place. Edit the text under any key heading and run the build again. Words in curly braces are filled in by the build from the ledger and should stay as they are. The tests run the writing-rules check on this file.

## page.title
Analyst Desk

## page.line
One source of truth for the fund's deals and portfolio companies.

## page.footer
Built by Ryan Sansbury. Every company, number, and document here is synthetic.

## page.footer.code
The code is on {link}.

## page.footer.github
GitHub

## page.footer.home
More of Ryan's work is at {link}.

## page.description
A working demo of an AI operations desk for a fund. Agents read and draft, code checks every number, and every figure traces to its source.

## tab.portfolio
Portfolio

## tab.deal
Deal

## tab.board
Board

## tab.hours
Hours

## tab.how
How it works

## strip.received
Received

## strip.mapped
Mapped

## strip.checked
Checked

## strip.tied
Tied out

## strip.published
Published

## strip.held
Held for review

## strip.received.detail
{files} files in by 7 AM

## strip.mapped.detail
{known} by known layouts and {agent} by the intake agent

## strip.mapped.detail_none
{known} by known layouts and {waiting} waiting on intake

## strip.mapped.detail_all
{known} by known layouts

## strip.checked.detail
{checks} checks with {flags} flagged

## strip.tied.detail
{ties} control totals tied

## strip.published.detail
Every figure traced

## strip.held.detail
{flags} unresolved

## controls.run
Run the morning

## controls.replay
Replay the morning

## controls.plant
Plant an error

## controls.lookalike
Show a look-alike

## controls.newfile
New file arrives

## controls.reset
Reset

## controls.upload
Try a new layout

## upload.title
Try a new layout

## upload.close
Close

## upload.text
A file in a new layout goes through the same intake as the morning's files. The intake agent proposes a mapping, and code accepts it only when every check and the control total pass.

## upload.layouts
Twelve layouts the agent had never seen

## upload.demo
Pick one to see what the intake agent did with it in a recorded run.

## upload.none
The eval's recorded runs are missing from this build.

## upload.tag.exact
Matches the key

## upload.tag.same
Same rows

## upload.tag.differs
Differs

## upload.tag.held
Held

## upload.mapping
The intake agent's mapping

## upload.col.file
This file's column

## upload.col.field
Schema field

## upload.accepted
Accepted. Every check passed.

## upload.held
Held for review because of {reasons}.

## upload.reason.dates
the dates

## upload.reason.key_unique
the load IDs

## upload.reason.sum_of_parts
the totals row

## upload.reason.unit_range
the ranges

## upload.reason.control_total
the control total

## upload.exact
The mapping matches the answer key exactly.

## upload.same
The mapping differs from the answer key in a detail the sample rows didn't show, and it still parses every row the same way.

## upload.differs
The mapping differs from the answer key, and the checks decide whether it's accepted.

## upload.how.recorded
Mapped by the intake agent in a run recorded on {when} with {model} in {seconds} seconds.

## controls.skip
Skip to the result

## controls.csv
Download the facts

## controls.print
Print the report

## plant.E1
A solar site reports in the wrong unit

## plant.E2
Duplicate load rows in the freight export

## plant.E3
The freight totals row read as a load

## plant.E4
A solar site's file never arrives

## plant.E5
The night audit's ADR disagrees with room revenue

## plant.E6
A freight credit with its sign flipped

## lookalike.L1
Hotel card deposits land a day late

## lookalike.L2
A solar site curtailed by the grid

## lookalike.L3
The Labor Day dip in freight volume

## prerun.title
Eleven files are waiting

## prerun.text
This is one demo morning at a fund with three synthetic portfolio companies. Their systems sent eleven overnight files before 6 AM. Run the morning to receive, map, check, and tie them out, or press the right arrow for a guided tour.

## banner.published
Published. Every figure ties to its source file and every check passed.

## banner.held
Held for review. {companies} and the report waits for a person.

## banner.held.company
{company} has {count} unresolved error {checks}

## banner.planted
This state is a test. The error was planted on purpose to show the checks catching it.

## tile.revenue
Revenue this month

## tile.ebitda
EBITDA estimate this month

## tile.cash
Cash collected this month

## tile.flags
Open flags

## tile.period
Month to date through {day}

## tile.flags.none
Nothing needs a person this morning

## tile.flags.some
Each one is listed on its company's card

## tile.flags.one
It's listed on its company's card

## company.sideoats.sector
Solar and storage in West Texas

## company.kiskadee.sector
Regional truckload and brokerage

## company.possumhaw.sector
A resort in the Hill Country

## kpi.generation
Generation

## kpi.availability
Availability

## kpi.curtailment
Curtailment

## kpi.performance_ratio
Performance ratio

## kpi.revenue
Revenue

## kpi.ebitda
EBITDA estimate

## kpi.loads
Loads

## kpi.revenue_per_load
Revenue per load

## kpi.gross_margin_pct
Gross margin

## kpi.on_time
On time

## kpi.empty_pct
Empty miles

## kpi.occupancy
Occupancy

## kpi.adr
ADR

## kpi.revpar
RevPAR

## kpi.fb_share
Food and beverage share

## status.final
Final

## status.held
Held for review

## status.affected
Affected by the flag

## card.checks_passed
Every check on this morning's files passed.

## card.checks_title
This morning's checks

## card.commentary_title
Commentary

## check.unit_range.flag.solar
{site} reported {gen} of generation and {curt} of curtailment against a ceiling of {ceiling} from its capacity and the day's sunlight. That's {ratio} of the ceiling and far outside the normal range. A mix-up of kWh and MWh is the usual cause.

## check.unit_range.expected.solar
{site} lost {curt} to grid curtailment on {day}. Generation plus curtailment still came to {ratio} of its ceiling. The check knows curtailment explains a low day and marks it expected.

## check.unit_range.flag.battery
The battery's round trip of {rte} is outside what the battery can deliver.

## check.unit_range.flag.freight
{count} rows in the freight export have miles or charges outside their normal ranges.

## check.unit_range.flag.freight.one
{count} row in the freight export has miles or charges outside their normal ranges.

## check.settlement_tie.flag.solar
{site}'s meter shows {gen} but the utility settled {delivered} from it. Line losses never come close to that gap.

## check.settlement_tie.flag.battery
The battery reported {reported} of revenue and the settlement shows {settled}.

## check.continuity.flag
{site}'s file for {day} never arrived. The utility still settled {delivered} from the site that day. The meter data is missing and the power isn't.

## check.key_unique.flag
The freight export lists {ids} more than once.

## check.key_unique.flag.blank
{count} rows in the freight export have no load ID.

## check.key_unique.flag.blank.one
{count} row in the freight export has no load ID.

## check.sum_of_parts.flag.read
Row {row} is the total of every other row and was read as a load.

## check.sum_of_parts.flag.disagree
The freight export's totals row doesn't equal the rows above it.

## check.sum_of_parts.flag.missing
The freight layout has a totals row and none was found.

## check.sum_of_parts.flag.hotel
The night audit's departments don't add up to its total revenue.

## check.control_total.flag.credit_sign
The export's revenue is {gap} more than the invoicing batch. That's exactly twice the credit on row {row} and the credit's sign flipped.

## check.control_total.flag.duplicates
The duplicated rows add exactly {gap} of revenue the invoicing batch doesn't have.

## check.control_total.flag.totals_row
The export's revenue is {gap} more than the invoicing batch. The gap is exactly the totals row read as a load.

## check.control_total.flag.unexplained
The export's revenue and the invoicing batch differ by {gap}.

## check.dates.flag
{count} rows in the freight export carry a date other than the business day.

## check.dates.flag.one
{count} row in the freight export carries a date other than the business day.

## check.types.flag
Some values in the freight export don't parse with the mapping.

## check.layout.flag
The freight export arrived in a layout no parser knows, and the intake agent's mapping isn't recorded yet.

## check.internal_consistency.flag
The night audit's ADR of {adr} times {rooms} rooms sold is {product}, but room revenue is {room}. A gap of {gap} isn't rounding.

## check.deposit_tie.expected
Yesterday's card settlements of {card} reach the bank a day later. The deposit check expects the one-day lag and doesn't flag it.

## check.deposit_tie.pass
The card settlements of {card} from {day} tie exactly to the deposit of {deposit} that landed the next day.

## check.volume_band.pass
Kiskadee moved {loads} loads on {day} against a budget of {budget}. That's {ratio} of plan and inside the normal band.

## check.volume_band.pass.plan
Kiskadee moved {loads} loads on {day} against a {plan} budget of {budget}. That's {ratio} of plan and inside the normal band.

## check.volume_band.flag
Loads came to {ratio} of the day's budget and fell outside the normal band.

## lookalike.L1.title
Card deposits land a day after the night audit

## lookalike.L1.text
The night audit closes each day's card sales and the processor deposits them a day later. The deposit check pairs each audit with the next day's deposit, and a deposit that lands the day after its sales is the normal state.

## lookalike.L2.title
A low day explained by curtailment

## lookalike.L2.text
The grid operator sometimes tells a site to cut its output. Generation drops on those days and curtailment rises by the same amount. The range check adds the two together before it judges the day.

## lookalike.L3.title
The Labor Day dip in freight volume

## lookalike.L3.text
Shippers close for the holiday and volume falls by about half. The budget plans each day by its type and gives holidays a lighter load. The volume check compares each day with its own budget.

## lookalike.result
Not flagged

## intake.title
A new file layout arrives

## intake.text
Kiskadee's TMS vendor changed the export overnight. Columns were renamed and reordered, the date format changed, and a trailer type column appeared.

## intake.known
The layout the parser knows

## intake.new
This morning's file

## intake.mapping
The intake agent's mapping

## intake.checks
What the mapping had to pass

## intake.ignored
Not needed

## intake.changed
Changed

## intake.accepted
Accepted and saved as {layout}. Tomorrow's file in this layout parses without the agent.

## intake.held
Held in quarantine. {reasons}

## intake.pending
The intake agent's run isn't recorded yet and the file waits in quarantine.

## intake.eval
On twelve held-out layouts the agent's mapping matched the answer key exactly {exact} times.

## intake.eval_caught
Validation held back {caught} of the {wrong} mappings that would have changed the data.

## intake.eval_equivalent
The {wrong} misses named a detail the sample rows didn't show, and each still parsed every row exactly as the answer key does.

## intake.eval_pending
The twelve-layout eval runs once the agent is recorded.

## vcheck.dates
Every row's date is the business day

## vcheck.key_unique
Every load ID is unique

## vcheck.sum_of_parts
The totals row equals the rows above it

## vcheck.unit_range
Miles and charges sit in their normal ranges

## vcheck.control_total
Revenue ties to the invoicing batch

## commentary.label
Drafted by the commentary agent in a recorded run on {date} and tied out by the gate.

## commentary.held
Commentary waits until the flags are resolved.

## commentary.missing
The commentary agent's run isn't recorded yet.

## commentary.invalid
The commentary agent's last run didn't pass validation, and none of it shows until a new run passes.

## drawer.kicker
Where this number comes from

## drawer.kicker.file
A file the desk received

## drawer.source
Source file

## drawer.fingerprint
Fingerprint

## drawer.received
Received

## drawer.layout
Layout

## drawer.location
Exact location

## drawer.steps
How it became this number

## drawer.checks
Checks on it and its file

## drawer.inputs
Built from

## drawer.close
Close

## drawer.more
and {n} more

## drawer.preview
The file

## drawer.quarantined
This file is in quarantine and its numbers stay out of every total.

## deal.title
Brightrow Field Services

## deal.line
A carve-out of a commercial solar operations and maintenance business from a larger electrical contractor

## deal.dataroom
The data room

## deal.file.financials
Three years of monthly P&L and working capital

## deal.file.customers
Revenue by customer for three fiscal years

## deal.file.kpis
Monthly operating measures from contracts to response times

## deal.file.teaser
The seller's two-page teaser

## deal.file.open
Open {name}

## deal.controls.model
Build the model

## deal.controls.claims
Check the teaser's claims

## deal.controls.memo
Draft the memo

## deal.controls.download
Download the .xlsx

## deal.assume.title
The deal analyst's assumptions

## deal.assume.text
The agent read three years of history and proposed each operating assumption with a rationale that cites it. Code accepted each value only inside a range the history sets, and the deal team set the price and the debt.

## deal.assume.label
Proposed by the deal analyst agent from a run recorded on {date}.

## deal.assume.missing
The deal analyst's run isn't recorded yet and the model uses FY2026 history for every assumption.

## deal.assume.invalid
The deal analyst's last run didn't pass validation, and the model uses FY2026 history for every assumption until a new run passes.

## deal.assume.col.input
Assumption

## deal.assume.col.history
FY2026

## deal.assume.col.proposed
Proposed

## deal.assume.col.used
Used

## deal.assume.col.source
Source

## deal.assume.col.why
Rationale

## deal.source.agent
Agent

## deal.source.override
Override

## deal.source.history
History

## deal.kpi.ev
Entry enterprise value

## deal.kpi.equity0
Equity at close

## deal.kpi.moic
MOIC

## deal.kpi.irr
IRR

## deal.kpi.lev
Net leverage at close

## deal.kpi.headroom
Covenant headroom

## deal.model.title
The model

## deal.model.text
Ten tabs of live formulas from the data room and the ledger. Blue is an input, black a formula, and green a link between tabs. Click a cell for its formula.

## deal.formula.hint
Click a cell to see its formula.

## deal.formula.input
A value typed into the model and not a formula.

## deal.formula.trace
Open where it comes from

## deal.claims.title
The teaser's claims against the ledger

## deal.claims.text
The seller's teaser makes three claims with numbers in them. Each one is checked against the ledger and cited.

## deal.claim.supported
Supported

## deal.claim.contradicted
Contradicted

## deal.claim.unverifiable
Unverifiable

## deal.claim.ebitda_margin
The teaser puts the margin above {threshold} and the ledger's FY2026 adjusted EBITDA margin is {ledger}. The teaser adds back the parent's overhead without the standalone cost that replaces it, and that basis comes to {context}.

## deal.claim.customer_concentration
The teaser caps every customer at {threshold} of revenue. The largest customer brought in {context} in FY2026 and that is {ledger} of revenue.

## deal.claim.renewal_rate
The teaser puts renewals above {threshold} and the ledger's FY2026 renewal rate of {ledger} supports it.

## memo.kicker
First draft of the investment committee memo

## memo.title
Brightrow Field Services

## memo.draft
Drafted by the memo agent from recorded run {run} and tied out by the gate. It's a first draft for a person to review.

## memo.missing
The memo agent's run isn't recorded yet. The tables below come straight from the ledger and the model.

## memo.invalid
The memo agent's last run didn't pass validation, and none of its text shows until a new run passes. The tables below come straight from the ledger and the model.

## memo.gate.pass
Tied out by the gate. All {n} figures in the agent's text came from placeholders and none was typed.

## memo.gate.fail
The gate failed the memo. The figure {token} in section {n} was typed by hand and no placeholder supplied it.

## memo.inject
Inject an unsupported number

## memo.inject.note
This is a test. It types one figure into the projections the way a careless edit would.

## memo.remove
Remove it

## memo.print
Print the memo

## memo.conditions
Conditions for the next round

## memo.s.recommendation
The recommendation

## memo.s.business
The business and the carve-out

## memo.s.why_now
Why now

## memo.s.historicals
Historical financials

## memo.s.adjustments
EBITDA adjustments

## memo.s.customers
Customers and concentration

## memo.s.projections
Base-case projections

## memo.s.returns
Returns and sensitivity

## memo.s.debt
Debt capacity

## memo.s.risks
Key risks and diligence questions

## memo.s.next_steps
Next steps

## deck.company
Kiskadee Freight

## deck.meeting
Board meeting for {month}

## deck.slide
Slide

## deck.foot
Every figure traces to the fund's ledger. All data here is synthetic.

## deck.print
Print the deck

## deck.label
Headlines and bullets drafted by the board deck agent from a run recorded on {date}. The charts come from the ledger.

## deck.missing
The board deck agent's run isn't recorded yet.

## deck.invalid
The board deck agent's last run didn't pass validation, and none of it shows until a new run passes.

## deck.topic.1
The month at a glance

## deck.topic.2
The revenue and margin bridge

## deck.topic.3
Operations

## deck.topic.4
Cash and receivables

## deck.topic.5
Risks and asks

## deck.partial
partial

## deck.kpi.loads
Loads

## deck.kpi.revenue
Revenue

## deck.kpi.gross_margin
Gross margin

## deck.kpi.gross_margin_pct
Gross margin share

## deck.kpi.ebitda
EBITDA estimate

## deck.kpi.on_time
On time

## deck.bridge.budget
Budget margin

## deck.bridge.volume
Volume

## deck.bridge.rate
Rate

## deck.bridge.cost
Cost

## deck.bridge.actual
Actual margin

## deck.chart.margin_bridge
Gross margin from budget to actual

## deck.chart.loads_by_week
Loads by week

## deck.chart.on_time_by_week
On-time share by week

## deck.chart.empty_miles_by_week
Empty miles share by week

## deck.chart.invoiced_vs_collected
Invoiced and collected by week

## deck.chart.receivables_by_week
Receivables at each week's end

## deck.summary.margin_bridge
Each step is a ledger value and the steps add up to the actual margin.

## deck.summary.partial
The partial last week of {month} appears only in the table view.

## deck.col.step
Step

## deck.col.amount
Amount

## deck.col.week
Week

## deck.col.value
Value

## deck.col.invoiced
Invoiced

## deck.col.collected
Collected

## header.hours
{h} hours back today

## header.home
Back to the start

## hours.title
Hours back

## hours.text
Every workflow the desk runs is timed against the hours it takes by hand. Run times are measured, and the hours by hand and the review minutes are estimates you can change in the table.

## hours.k.week
Hours back this week

## hours.k.week.foot
Hours by hand less review and run time

## hours.k.today
Hours back today

## hours.k.today.foot
The morning report and the new layout

## hours.k.manual
Hours by hand this week

## hours.k.manual.foot
What the same runs take when they're built by hand

## hours.k.review
Hours of review kept

## hours.k.review.foot
A person still reviews every draft

## hours.col.workflow
Workflow

## hours.col.runs
Runs this week

## hours.col.measured
Measured run time

## hours.col.baseline
Estimated hours by hand

## hours.col.review
Estimated review minutes

## hours.col.back
Hours back

## hours.wf.daily_report
The daily portfolio report

## hours.wf.intake
A new file layout mapped

## hours.wf.deal_model
The deal model's first draft

## hours.wf.memo
The memo's first draft

## hours.wf.deck
The board deck

## hours.total
This week

## hours.note
Hours back is the runs times the hours by hand less the review and the run time. Blue marks an estimate as it does in the deal model, and totals update as you change them.

## hours.chart
Hours by hand against hours with the desk

## hours.legend.manual
By hand

## hours.legend.auto
With the desk and a review

## hours.chart.summary
Each pair compares the hours a workflow's runs take by hand with the hours they take with the desk and a review.

## hours.unit
{h} h

## hours.row.back
{h} h back

## hours.time.none
not recorded yet

## hours.time.under
under a second

## hours.time.seconds
{n} seconds

## hours.time.minutes
{n} minutes

## how.title
How it works

## how.text
One ledger sits under every deliverable. Agents do the reading and the drafting, code checks every number, and nothing reaches a person without passing the gate.

## how.arch
The architecture

## how.d.files
Portfolio files

## how.d.files.sub
Eleven files a morning

## how.d.dataroom
The data room

## how.d.dataroom.sub
The seller's financials, customers, and teaser

## how.d.intake
Intake

## how.d.intake.sub
Parsers for known layouts and an agent for new ones

## how.d.checks
Checks

## how.d.checks.sub
Ranges, keys, and tie-outs

## how.d.ledger
The ledger

## how.d.ledger.sub
Every file, fact, and derived value with its lineage

## how.d.ledger.stats
{sources} files, {facts} facts, and {derived} derived values

## how.d.gate
The gate

## how.d.gate.sub
No typed numbers

## how.d.report
Daily report

## how.d.report.sub
Commentary by an agent

## how.d.model
Deal model

## how.d.model.sub
Assumptions by an agent

## how.d.memo
Investment memo

## how.d.memo.sub
Drafted by an agent

## how.d.deck
Board deck

## how.d.deck.sub
Headlines by an agent

## how.d.legend
The spark marks a step where an agent works, and code bounds every agent.

## how.agents
The agents and their limits

## how.agents.text
Each agent has one job, a fixed input, and an output schema, and code enforces its limits. None of them can publish anything on its own.

## how.mode.recorded.title
Recorded once

## how.mode.recorded.text
The morning's five agents ran on the models routing picked for them, and every reply passed the same validation before it was saved.

## how.mode.recorded.cost
In the recorded runs a morning's five agent calls came to {cost} at API prices.

## how.mode.replay.title
Replayed here

## how.mode.replay.text
The page replays those runs and checks each one again on every build. Nothing on it calls a model or waits on the network, and a visit costs nothing. The invented company names changed after the runs were recorded, and the swap touched nothing else in them.

## how.col.agent
Agent

## how.col.sees
What it sees

## how.col.returns
What it returns

## how.col.limits
Limits enforced in code

## how.a.intake
Intake mapper

## how.a.intake.sees
A new file's header and sample rows

## how.a.intake.returns
Mappings and formats

## how.a.intake.limits
Accepted only when every check and the control total pass, and saved as a layout after that

## how.a.commentary
Daily commentary

## how.a.commentary.sees
Each company's KPIs, variances, and checks

## how.a.commentary.returns
Two to four sentences each

## how.a.commentary.limits
Only placeholders get past the gate

## how.a.deal
Deal analyst

## how.a.deal.sees
Three years of data room history

## how.a.deal.returns
Cited operating assumptions

## how.a.deal.limits
Each value must sit in a band set by history, and manual overrides win

## how.a.memo
Memo writer

## how.a.memo.sees
The model's outputs, the adjustments, the customers, and the claims check

## how.a.memo.returns
Eleven cited sections

## how.a.memo.limits
The gate checks every figure, and the risks section must cite every claim

## how.a.deck
Board deck writer

## how.a.deck.sees
Kiskadee's month and its variances

## how.a.deck.returns
Five headlines with two or three bullets each

## how.a.deck.limits
Charts come only from the ledger

## route.title
Model routing

## route.text
Every model here took the same tests with the same prompts and the same checks. Each agent runs on the cheapest model that clears its quality bar, and the next one that clears it takes over when a call fails.

## route.k.routed
The blended morning

## route.k.routed.foot
The five agents on their routed models at list prices

## route.k.routed.save
{pct} below {model} on every agent

## route.k.single
Every agent on {model}

## route.k.single.foot
The same five agent calls on one model

## route.k.intake
Intake on its route

## route.k.intake.foot
Layouts mapped exactly by {model}

## route.blend
How the blend adds up

## route.blend.runs
Runs

## route.blend.alone
{model} on every agent

## route.short.intake
intake

## route.short.commentary
commentary

## route.short.deal
deal analyst

## route.short.deck
board deck

## route.short.memo
memo

## route.chart.title
Intake quality against cost

## route.chart.y
Layouts mapped exactly

## route.chart.x
Cost of one mapping on a log scale

## route.chart.bar
Within one of the best

## route.chart.other
Other vendors

## route.chart.ring
The ringed dot is the intake agent's model

## route.chart.tip
{model} from {vendor} mapped {exact} of {runs} exactly at {cost} each

## route.chart.col.cost
Cost of one mapping

## route.chart.summary.cheapest
{cleared} of the {tested} models cleared the intake bar, and {model} did it for the least at {cost} a mapping.

## route.chart.summary.only
{model} was the only one of the {tested} models to clear the intake bar and maps a layout for {cost}.

## route.chart.summary.unpriced
{model} cleared the intake bar and no model with a list price did.

## route.chart.summary.none
None of the {tested} models cleared the intake bar and the intake agent stays on {model}.

## route.chart.unpriced
The chart leaves out {models} since no list price was set.

## route.routes
Where each agent runs

## route.col.agent
Agent

## route.col.on
Runs on

## route.col.why
Why

## route.col.fallback
If a call fails

## route.why.cheapest
The cheapest of the {n} models that cleared its bar

## route.why.held
Held for writing quality because a person reads it

## route.text.held
{agents} stay on {model} because passing validation isn't the same as reading well.

## route.why.only
The only model that cleared its bar

## route.why.unpriced
Cleared its bar where no model with a price did

## route.why.none
No model cleared its bar and it stays on the default

## route.why.untested
Not in the comparison yet and it stays on the default

## route.fallback.none
No other model cleared the bar

## route.fallback.more
{model} and {n} more

## route.models
How each model did

## route.col.model
Model

## route.col.vendor
Vendor

## route.col.intake
Intake exact

## route.col.prose
Prose valid first try

## route.col.seconds
Model time a morning

## route.col.cost
Cost a morning

## route.col.routed
Routed agents

## route.none
Not run

## route.unpriced
No price

## route.routed.none
None

## route.harmful
{n} wrong and accepted


## route.bars
The intake agent has to land within one layout of the best model's score, and none of its misses can be a mapping the checks would have let through. Each prose agent has to pass validation on every run within the one repair.

## route.ran
The comparison ran on {date}.

## route.prices
Costs use each vendor's list prices as of {date}, and Claude's come from what the CLI reported.

## route.prices.undated
Costs use each vendor's list prices, and Claude's come from what the CLI reported.

## route.prices.same
Costs use each vendor's list prices that day, and Claude's come from what the CLI reported.

## route.prices.cli
Every cost here is what the Claude CLI reported for its calls.

## code.title
Code excerpts

## code.text
These excerpts of the desk's code are copies made for this page. The page reads only the copies and never the code that runs the desk. Open one below or click a box in the diagram above to see its excerpt.

## code.tree
Files

## code.feat.gate
The gate

## code.feat.checks
The morning's checks

## code.feat.validate
The agent validator

## code.feat.routing
The routing rules

## code.feat.model
The deal model

## code.feat.replay
The run replay

## code.note.gate
Fails any figure in an agent's text that isn't a citation into the ledger.

## code.note.checks
Every check a morning's files face, and what each one compares.

## code.note.validate
What every agent reply has to pass before anything shows, and the repair request when it doesn't.

## code.note.routing
Picks the cheapest model that clears each agent's quality bar in the model comparison.

## code.note.model
The deal model in Python that the workbook's formulas match to the cent.

## code.note.replay
Loads each recorded agent run and checks it again against today's ledger before the page shows it.

## how.results
Results from the tests and evals

## how.results.text
Each result here is read from a file the tests, the evals, or the recordings wrote. None of them is typed.

## how.k.of
{a} of {b}

## how.k.caught
Planted errors caught

## how.k.caught.foot
On held-out seeds {seeds} after the checks were frozen

## how.k.alarms
False alarms

## how.k.alarms.foot
Across the same held-out seeds

## how.k.lookalikes
Look-alikes left alone

## how.k.lookalikes.foot
Normal days that only look like errors

## how.k.intake
New layouts mapped exactly

## how.k.intake.foot
Held-out file layouts the intake agent had never seen

## how.k.intake.equivalent
Held-out layouts the agent had never seen, and the other {wrong} still parsed every row like the answer key

## how.k.tests
Tests passing

## how.k.tests.foot
In the last full run on {when}

## how.k.tests.skipped
In the last full run on {when}, and {skipped} skipped

## how.k.model
Workbook against Python

## how.k.model.value
{n} values

## how.k.model.foot
Each formula's value matches the Python model to the cent

## how.k.lo
LibreOffice recalculation

## how.k.lo.value
{n} formulas

## how.k.lo.foot
Recalculated from scratch, and each one matched to the cent

## how.k.recorded
Agent runs recorded

## how.k.recorded.foot
With {model} on {when}

## how.k.recorded.span
With {model} from {first} to {last}

## how.r.checks_stale
The checks changed after that score, and the next frozen run scores them on fresh seeds.

## how.plan
How I'd roll it out at a fund

## how.p.30.title
The first thirty days

## how.p.30
One portfolio company's daily report on its real files with every tie-out in place.

## how.p.60.title
The first sixty days

## how.p.60
The model and memo template on the fund's real deal process with the gate on every figure.

## how.p.90.title
The first ninety days

## how.p.90
Hours back measured on every automated workflow.

## presenter.label
Step {n} of {total}

## presenter.s.problem
The problem

## presenter.s.run
The morning run

## presenter.s.error
A planted error is caught

## presenter.s.lookalike
A look-alike is left alone

## presenter.s.intake
A new file layout

## presenter.s.upload
Try a new layout

## presenter.s.deal
A deal lands

## presenter.s.model
The model

## presenter.s.returns
The returns

## presenter.s.checks
The model's checks

## presenter.s.claims
The teaser's claims

## presenter.s.memo
The memo

## presenter.s.gate
The gate fails a typed number

## presenter.s.pass
The gate passes again

## presenter.s.board
Board prep

## presenter.s.hours
Hours back

## presenter.s.how
How it's built

## presenter.s.routing
Model routing

## presenter.s.code
Code excerpts

## presenter.s.results
The results

## presenter.s.plan
How I'd roll it out

## presenter.c.problem
Three portfolio companies sent eleven files overnight, and nothing has been checked yet.

## presenter.c.run
The morning run receives each file, maps it, checks it, and ties out the totals.

## presenter.c.error
A planted error in a solar site's file holds the report until a person looks at it.

## presenter.c.lookalike
A card deposit lands a day after the sale, and the check knows that gap is normal.

## presenter.c.intake
The freight company changed its export overnight, and the intake agent maps the new layout.

## presenter.c.upload
Twelve layouts the agent had never seen each faced the same checks as a morning's files.

## presenter.c.deal
A deal lands with a data room, a seller's teaser, and a model to build.

## presenter.c.model
An agent proposes the assumptions inside ranges the history sets, and code builds the model.

## presenter.c.returns
Every return traces back to the data room and the assumptions behind it.

## presenter.c.checks
The model's own checks turn red if any tie-out breaks.

## presenter.c.claims
Each claim in the seller's teaser is checked against the data room.

## presenter.c.memo
The memo agent drafts the investment memo and cites every figure from the ledger.

## presenter.c.gate
A number typed into the memo without a source fails the gate before anything ships.

## presenter.c.pass
Once the typed number comes out every figure traces again and the memo passes.

## presenter.c.board
The same ledger builds the freight company's monthly board deck.

## presenter.c.hours
Each workflow is timed against the same work by hand, and every estimate can be changed.

## presenter.c.how
Agents read and draft, code checks every number, and nothing publishes on its own.

## presenter.c.routing
Seven models took the same tests, and each agent got the cheapest one that passed.

## presenter.c.code
These excerpts show the gate, the checks, the routing, and the model.

## presenter.c.results
Every result here comes from the test and eval runs, and none is typed by hand.

## presenter.c.plan
How the desk would roll out at a fund over its first ninety days.

## labels.memo
- hist.pm = Preventive maintenance contracts
- hist.cr = Corrective repairs restated
- hist.mc = Module cleaning restated
- hist.ms = Monitoring subscriptions
- hist.revenue = Total revenue
- hist.gm = Gross margin
- hist.reported = Reported EBITDA
- hist.adjusted = Adjusted EBITDA
- hist.adjusted_margin = Adjusted EBITDA margin
- adj.reported = Reported EBITDA
- adj.settlement = Add back the legal settlement
- adj.allocation = Add back the parent's overhead allocation
- adj.standalone = Less the standalone corporate cost
- adj.adjusted = Adjusted EBITDA
- cust.largest = The largest customer
- cust.top10 = The ten largest customers
- proj.revenue = Revenue
- proj.ebitda = EBITDA
- ret.ev = Entry enterprise value
- ret.equity0 = Equity at close
- ret.equity_exit = Equity at exit
- ret.moic = MOIC
- ret.irr = IRR
- ret.grid = MOIC by entry multiple down the side and exit multiple across the top
- debt.net_leverage = Net leverage
- debt.headroom = Headroom to the illustrative covenant
- col.line = Fiscal years ending September 30
- col.bridge = From reported to adjusted
- col.customers = Customers in FY2026
- col.revenue = Revenue
- col.share = Share of revenue
- col.year = Fiscal year
- col.returns = Base case
- col.value = Value
- col.entry_exit = Entry and exit
- col.claim = The teaser's claim
- col.result = Result
- col.ledger = The ledger

## labels.entity
- fund = the fund
- sideoats = Sideoats Renewables
- kiskadee = Kiskadee Freight
- possumhaw = Possumhaw Lodge
- brightrow = Brightrow Field Services
- run = This morning's run

## labels.status
- pass = Passed
- flag = Flagged
- expected = Expected
- info = Note

## labels.rule
- unit_range = Range check
- settlement_tie = Settlement tie-out
- continuity = Every file arrived
- key_unique = Unique load IDs
- sum_of_parts = Parts add up to the total
- control_total = Control total
- dates = Dates match the business day
- types = Every value parses
- layout = Known layout
- volume_band = Volume against budget
- internal_consistency = ADR times rooms equals room revenue
- deposit_tie = Card deposits tie to the night audit
- annual_tie = Annual totals tie to the months
- reclass = Reclassification restated
- customer_tie = Customers tie to revenue

## labels.metric
- generation_kwh = Generation from the meter
- curtailment_kwh = Curtailment ordered by the grid
- availability = Availability
- insolation = Sunlight per square meter
- inverter_faults = Inverter faults
- cycles = Battery cycles
- charge_kwh = Energy charged
- discharge_kwh = Energy discharged
- arbitrage_revenue = Arbitrage revenue reported by the battery
- delivered_kwh = Energy delivered and settled
- settlement = Settlement amount
- remittance = Utility remittance received
- market_price = Hub price
- capacity_kw = Capacity
- invoice_count = Invoices in the batch
- invoiced = Invoiced by the billing system
- cash_applied = Cash applied
- ar_balance = Receivables balance
- loads = Loads
- credit_rows = Credit rows
- linehaul = Linehaul revenue
- fuel_surcharge = Fuel surcharge revenue
- accessorials = Accessorial charges
- carrier_cost = Carrier cost
- revenue = Revenue
- loaded_miles = Loaded miles
- empty_miles = Empty miles
- asset_miles = Miles on the company's own trucks
- on_time_loads = Loads delivered on time
- rooms_available = Rooms available
- rooms_sold = Rooms sold
- comp_rooms = Complimentary rooms
- adr_reported = ADR printed on the night audit
- room_revenue = Room revenue
- fb_revenue = Food and beverage revenue
- other_revenue = Spa and other revenue
- total_revenue = Total revenue
- card_settlements = Card settlements
- direct_bill = Direct bill and cash
- deposit_gross = Card deposit before fees
- deposit_fees = Card processing fees
- deposit_net = Card deposit after fees
- budget_generation_kwh = Budgeted generation
- budget_revenue_cents = Budgeted revenue
- budget_opex_cents = Budgeted operating costs
- budget_loads = Budgeted loads
- budget_carrier_cost_cents = Budgeted carrier cost
- budget_asset_miles = Budgeted miles on the company's own trucks
- budget_std_cost_per_mile_cents = Standard cost per mile from the budget
- budget_fixed_cost_cents = Budgeted fixed costs
- budget_rooms_sold = Budgeted rooms sold
- budget_room_revenue_cents = Budgeted room revenue
- budget_fb_revenue_cents = Budgeted food and beverage revenue
- budget_other_revenue_cents = Budgeted spa and other revenue
- budget_room_cost_per_occupied_cents = Cost per occupied room from the budget
- budget_fb_cost_bp = Food and beverage cost rate from the budget
- budget_other_cost_bp = Spa and other cost rate from the budget
- generation = Generation
- generation_budget = Generation budget
- generation_var = Generation against budget
- curtailment = Curtailment
- revenue_budget = Revenue budget
- revenue_var = Revenue against budget
- performance_ratio = Performance ratio
- opex_budget = Operating costs at budget
- ebitda = EBITDA estimate
- ebitda_budget = EBITDA budget
- ebitda_var = EBITDA estimate against budget
- cash = Cash collected
- loads_var = Loads against budget
- revenue_per_load = Revenue per load
- asset_cost = Cost of the company's own trucks
- asset_cost_budget = Budgeted cost of the company's own trucks
- gross_margin = Gross margin
- gross_margin_pct = Gross margin share of revenue
- gross_margin_budget = Gross margin budget
- on_time = On-time delivery
- all_miles = Loaded and empty miles
- empty_pct = Empty miles share
- occupancy = Occupancy
- adr = ADR
- revpar = RevPAR
- fb_share = Food and beverage share
- room_cost = Room costs at budget rates
- fb_cost = Food and beverage costs at budget rates
- other_cost = Spa and other costs at budget rates
- room_cost_budget = Budgeted room costs
- fb_cost_budget = Budgeted food and beverage costs
- other_cost_budget = Budgeted spa and other costs
- expected_kwh = Most the site could make that day
- output_ratio = Output against that ceiling
- line_loss = Line loss
- round_trip = Battery round trip
- control_gap = Gap to the invoicing batch
- volume_ratio = Loads against the day's budget
- adr_times_rooms = ADR times rooms sold
- adr_gap = Gap to room revenue
- files_received = Files received
- files_known = Files in a known layout
- files_agent = Files mapped by the intake agent
- files_waiting = Files waiting on a mapping
- flags_sideoats = Error checks flagged on Sideoats's files
- flags_kiskadee = Error checks flagged on Kiskadee's files
- flags_possumhaw = Error checks flagged on Possumhaw's files
- checks_run = Checks run
- checks_flagged = Error checks flagged
- ties = Control totals tied
- open_flags = Open flags

## labels.model
- readme.title = Brightrow Field Services first-draft model
- readme.1 = A first-draft model of a carve-out built from the data room and the fund's ledger.
- readme.2 = Sources holds the data room's values with the file and cells each came from and they are the only hard-coded history.
- readme.3 = Historicals and Adjustments rebuild three fiscal years and the EBITDA bridge from Sources with formulas.
- readme.4 = The deal analyst agent proposed the operating assumptions and each cites the history it rests on.
- readme.5 = The deal team set the price and the debt terms and Checks turns red if any tie-out breaks.
- readme.6 = Every company and number here is synthetic.
- readme.key = How to read the colors
- readme.key_input = Blue cells are inputs
- readme.key_formula = Black cells are formulas
- readme.key_link = Green cells link to another tab
- readme.version = Version one built for the November 4 2026 review
- sources.title = Data room values
- sources.note = Values from the data room with the file and rows they came from. These are the only hard-coded history in the model.
- sources.line = Line
- sources.from = From
- src.revenue_pm = Preventive maintenance contracts revenue
- src.revenue_cr = Corrective repairs revenue as reported
- src.revenue_mc = Module cleaning revenue
- src.revenue_ms = Monitoring subscriptions revenue
- src.total_revenue = Total revenue
- src.gross_profit = Gross profit
- src.sga_salaries = Salaries and benefits
- src.sga_facilities = Facilities
- src.sga_it = IT and software
- src.sga_insurance = Insurance
- src.sga_allocation = Corporate overhead allocation from the parent
- src.settlement = Legal settlement
- src.reported_ebitda = Reported EBITDA
- src.memo_revenue = Module cleaning booked inside corrective repairs
- src.annual = Annual summary from the data room
- src.annual_revenue = Total revenue in the annual summary
- src.annual_gp = Gross profit in the annual summary
- src.annual_ebitda = Reported EBITDA in the annual summary
- src.standalone = Standalone corporate cost a month from Notes item four
- src.customers = Revenue by customer
- src.customers_total = All customers
- src.largest = The largest customer
- src.balances = Working capital and capital spending
- src.receivables = Accounts receivable at year end
- src.unbilled = Unbilled services at year end
- src.payables = Accounts payable at year end
- src.accrued = Accrued liabilities at year end
- src.capex = Capital expenditures in the year
- src.da = Depreciation and amortization in the year
- hist.title = Three fiscal years ending September 30
- hist.pm = Preventive maintenance contracts
- hist.cr = Corrective repairs as reported
- hist.mc = Module cleaning as reported
- hist.ms = Monitoring subscriptions
- hist.revenue = Total revenue
- hist.memo = Module cleaning booked inside repairs
- hist.cr_restated = Corrective repairs restated
- hist.mc_restated = Module cleaning restated
- hist.revenue_restated = Total revenue restated
- hist.gp = Gross profit
- hist.gm = Gross margin
- hist.sga = SG&A before the parent's allocation
- hist.alloc = Overhead allocation from the parent
- hist.settlement = Legal settlement
- hist.ebitda = Reported EBITDA
- hist.ebitda_rebuilt = Reported EBITDA rebuilt from its lines
- hist.ebitda_margin = Reported EBITDA margin
- hist.sga_pct = SG&A share of revenue
- hist.growth_pm = Growth in preventive maintenance
- hist.growth_cr = Growth in corrective repairs restated
- hist.growth_mc = Growth in module cleaning restated
- hist.growth_ms = Growth in monitoring
- hist.nwc = Net working capital at year end
- hist.nwc_pct = Net working capital share of revenue
- hist.capex_pct = Capital spending share of revenue
- hist.da_pct = Depreciation and amortization share of revenue
- adj.title = From reported to adjusted EBITDA
- adj.why = Why
- adj.reported = Reported EBITDA
- adj.settlement = Add back the legal settlement
- adj.allocation = Add back the parent's overhead allocation
- adj.standalone = Less the standalone corporate cost
- adj.adjusted = Adjusted EBITDA
- adj.margin = Adjusted EBITDA margin
- adj.why_settlement = One-time and resolved in August 2025 as Notes item two says
- adj.why_allocation = The parent's charge ends at the carve-out as Notes item three says
- adj.why_standalone = Management's estimate of what a standalone Brightrow spends from Notes item four
- assume.title = Inputs
- assume.input = Input
- assume.history = FY2026 history
- assume.value = Value
- assume.source = Source
- assume.rationale = Rationale
- assume.operating = Operating assumptions for every projection year
- assume.terms = Deal and debt terms
- assume.growth_pm = Preventive maintenance growth
- assume.growth_cr = Corrective repair growth
- assume.growth_mc = Module cleaning growth
- assume.growth_ms = Monitoring subscription growth
- assume.gross_margin = Gross margin
- assume.sga_pct = SG&A share before standalone cost
- assume.da_pct = D&A share of revenue
- assume.capex_pct = Capex share of revenue
- assume.nwc_pct = NWC share of revenue
- assume.tax = Cash tax rate
- assume.escalation = Yearly increase in the standalone cost
- assume.entry = Entry multiple of FY2026 adjusted EBITDA
- assume.fees = Transaction fees as a share of enterprise value
- assume.exit = Exit multiple of FY2031 EBITDA
- assume.leverage = Senior debt at close as a multiple of EBITDA
- assume.rate = Interest rate on the term loan
- assume.amortization = Yearly amortization as a share of the original loan
- assume.sweep = Share of excess cash swept to the loan
- assume.src_agent = Deal analyst agent recorded {date}
- assume.src_override = Manual override
- assume.src_history = FY2026 history since no agent run is recorded
- assume.src_terms = Deal team
- proj.title = Base case projections
- proj.revenue_head = Revenue by service line
- proj.pm = Preventive maintenance contracts
- proj.cr = Corrective repairs
- proj.mc = Module cleaning
- proj.ms = Monitoring subscriptions
- proj.revenue = Total revenue
- proj.growth = Revenue growth
- proj.gp = Gross profit
- proj.sga = SG&A before the standalone cost
- proj.standalone = Standalone corporate cost
- proj.ebitda = EBITDA
- proj.margin = EBITDA margin
- proj.da = Depreciation and amortization
- proj.ebit = EBIT
- proj.interest = Interest
- proj.taxes = Cash taxes
- proj.capex = Capital expenditures
- proj.nwc = Net working capital
- proj.dnwc = Change in net working capital
- proj.cfads = Cash flow before debt service
- debt.title = Term loan and leverage
- debt.at_close = At close
- debt.opening = Opening balance
- debt.interest = Interest on the opening balance
- debt.mandatory = Mandatory amortization
- debt.avail = Cash after interest and amortization
- debt.sweep = Cash sweep
- debt.closing = Closing balance
- debt.cash = Cash balance
- debt.net_debt = Net debt
- debt.ebitda = EBITDA
- debt.net_leverage = Net leverage
- debt.coverage = Interest coverage
- debt.cov_leverage = Illustrative leverage covenant
- debt.lev_headroom = Headroom to the leverage covenant
- debt.cov_coverage = Illustrative coverage covenant
- debt.cov_headroom = Headroom to the coverage covenant
- debt.note = The covenants are illustrative for a first look and come from no term sheet.
- ret.title = Returns in the base case
- ret.ebitda0 = FY2026 adjusted EBITDA
- ret.entry = Entry multiple
- ret.ev = Entry enterprise value
- ret.fees = Transaction fees
- ret.uses = Total uses
- ret.debt0 = Senior debt at close
- ret.equity0 = Equity at close
- ret.ebitda5 = FY2031 EBITDA
- ret.exit = Exit multiple
- ret.ev_exit = Exit enterprise value
- ret.nd_exit = Net debt at exit
- ret.equity_exit = Equity at exit
- ret.moic = MOIC
- ret.flows_head = Equity cash flows by year
- ret.flows = Equity in and out
- ret.irr = IRR
- ret.irr_check = IRR from MOIC to the one-fifth less one
- sens.title = MOIC by entry and exit multiple
- sens.irr_title = IRR by entry and exit multiple
- sens.rows = Entry multiples run down the side and exit multiples run across the top.
- checks.title = Checks
- checks.all = Every check together
- checks.what = What it checks
- checks.a = Model
- checks.b = Against
- checks.diff = Difference
- checks.status = Status
- checks.c1 = FY2026 revenue equals the data room's annual summary
- checks.c2 = Restated revenue equals reported revenue in FY2026
- checks.c3 = Reported EBITDA rebuilt from its lines equals the data room's
- checks.c4 = Adjusted EBITDA equals the fund's ledger
- checks.c5 = Revenue by customer adds up to FY2026 revenue
- checks.c6 = Sources equal uses at close
- checks.c7 = The loan rolls forward every year
- checks.c8 = The loan never goes negative
- checks.c9 = MOIC equals the Python engine
- checks.c10 = IRR equals the Python engine
- checks.c11 = IRR equals MOIC to the one-fifth less one
