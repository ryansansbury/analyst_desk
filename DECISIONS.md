# Decisions

Each one is a choice that shaped the desk and the reason behind it.

**A synthetic world with planted errors.** Real portfolio data can't be published, and a demo with no known errors can't prove anything. One seed builds three companies, a deal, and their files. It plants six errors and three look-alikes with an answer key.

**Freeze the answer keys before writing the checks.** The planted catalog, the intake eval's answer keys, and the intake prompt were hashed before any check or prompt existed. The checks were frozen next and scored once on seeds no earlier run used. The tests fail if any frozen file changes.

**Look-alikes count as much as errors.** A check that flags a normal day costs as much trust as one that misses a real error. Each look-alike is a day that looks wrong and isn't, and a check passes only if it leaves all three alone.

**A ledger with lineage.** Every value keeps the file, row, and column it came from, and every derived value keeps its inputs and formula. That's what lets anyone open any figure and see where it came from, and it's what the gate checks agent text against.

**Agents propose and code decides.** No agent can publish. The intake agent proposes a mapping and code accepts it only when the data passes every check. The deal analyst proposes assumptions inside ranges the history sets. The writers draft, and the gate decides whether a draft ships.

**Figures only by citation.** An agent never types a number. It cites ledger IDs, and the renderer writes in the verified values. A typo or an invented figure has nowhere to hide, and the memo's gate step shows one typed number failing the whole memo.

**Route by eval and hold prose by reading.** Each agent runs on the cheapest model that cleared its bar in the same tests. Validation can't judge how prose reads. The commentary, the deck, and the memo stay on the strongest writer because a person read every model's drafts.

**Replay on the public page.** The page replays runs recorded once on real models, and it checks each one again on every build. It needs no key and costs nothing to visit, and it can't drift from what the agents actually wrote.

**Names checked before going public.** Three checks against real companies ran on the invented names before the page went up. Every name with a real counterpart changed by a one-to-one swap of words across the code, the frozen files, and the recorded runs, and undoing the swap gives back the old files exactly, which was checked before release.

**A static page.** Every state is rendered ahead of time. The page opens from a file, and nothing waits on a network call.

**The page's words in one file.** `WORDS.md` holds every word the page shows apart from the agents' drafts and the ledger's short note on how each figure was made. A writing-rules check runs on all of it, and the same rules reach the agents' prose through validation and the ledger's notes through a test.

**Code excerpts are copies.** The page's code section shows excerpts kept in `excerpts/` and never reads the code that runs the desk. A test checks that every excerpt still matches its module.

**Lines run the full width.** Paragraphs fill their column, and the last three words of any paragraph stay together. The screenshot check measures every block at desktop, tablet, and phone widths.
