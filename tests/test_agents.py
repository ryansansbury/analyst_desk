"""The agents' inputs and validators against a scripted stand-in. No model is called. The stand-in answers the way a
good model would, and once the way a careless one would, so the validators are tested on both."""
import json
import unittest

from agents import prompts, validate
from tests import helpers


def ph(local):
    return "{" + local[0] + ":" + local[1:] + "}"


def find(listing, label):
    return next(f["id"] for f in listing if f["label"] == label)


class StandIn:
    """Answers a task from its input, like a careful model. careless=True types a number into the first commentary
    reply, which the validator has to send back."""

    def __init__(self, model, careless=False):
        self.model, self.careless = model, careless

    def daily_commentary(self, inp, repair):
        out = []
        for c in inp["companies"]:
            var = find(c["figures"], "Revenue against budget")
            eb = find(c["figures"], "EBITDA estimate, month to date")
            first = f"Revenue for the month came in {ph(var)} and every check this morning passed."
            if self.careless and not repair and c["company"] == "sideoats":
                first = "Revenue for the month reached $5.3 million and every check this morning passed."
            out.append({"company": c["company"], "sentences": [first, f"The EBITDA estimate stands at {ph(eb)}."]})
        return {"companies": out}

    def deal_analyst(self, inp, repair):
        cite = inp["history"][-1]["figures"][0]["id"]
        return {"assumptions": [{"key": a["key"], "value": round(sum(a["allowed_range"]) / 2, 4),
                                 "rationale": f"The value follows the history in {ph(cite)} and stays near the recent trend.",
                                 "cites": [cite]} for a in inp["propose"]]}

    def memo_writer(self, inp, repair):
        from agents.validate import MEMO_SECTIONS
        moic = find(inp["model_outputs"], "MOIC")
        irr = find(inp["model_outputs"], "IRR")
        claims = " ".join(f"The teaser claim on line {i} of the claims check came out {ph(c['id'])}."
                          .replace(f"line {i} of ", "") for i, c in enumerate(inp["claims_check"], 1))
        sections = []
        for s in MEMO_SECTIONS:
            text = claims if s == "risks" else f"The base case returns {ph(moic)} on equity and an IRR of {ph(irr)}."
            sections.append({"id": s, "paragraphs": [text]})
        return {"sections": sections, "conditions": ["Confirm the standalone cost with the seller.",
                                                      "Review the largest customer's contract."]}


class Validators(unittest.TestCase):
    def setUp(self):
        from app.desk import Desk
        if not hasattr(Validators, "desk"):
            Validators.desk = Desk(runs={})
        self.d = Validators.desk

    def test_the_desk_holds_the_new_layout_until_a_mapping_is_recorded(self):
        self.assertIsNone(self.d.mapping)
        self.assertEqual(self.d.clean["tms_status"][helpers.DEMO_DAY]["reasons"], ["no mapping"])

    def test_intake_schema_problems_are_plain(self):
        inp, _ = self.d.input_for("intake_demo")
        self.assertIn("last_rows", inp)
        bad = {"header_rows": 3, "columns": [["Load ID", "load_id"]], "date_format": "Y-m-d", "money_format": "dollars",
               "on_time": {"true": True}}
        problems = validate.intake_mapper(bad, inp)
        self.assertTrue(any("header_rows" in p for p in problems))
        self.assertTrue(any("strptime" in p for p in problems))

    def test_exact_match_needs_every_part(self):
        key = self.d.world["key"]["intake"]["V00"]
        reply = {k: key[k] for k in ("header_rows", "columns", "date_format", "money_format", "on_time", "totals_label")}
        self.assertTrue(validate.exact_match(reply, key))
        self.assertFalse(validate.exact_match(dict(reply, date_format="%m/%d/%Y"), key))

    def test_commentary_with_a_typed_number_or_a_foreign_id_fails(self):
        inp, ids = self.d.input_for("daily_commentary")
        mapping = validate.resolve(self.d.ledger, ids.keys())
        good = StandIn("x").daily_commentary(inp, False)
        self.assertEqual(validate.validate("daily_commentary", good, inp, self.d.ledger, mapping), [])
        typed = StandIn("x", careless=True).daily_commentary(inp, False)
        self.assertTrue(validate.validate("daily_commentary", typed, inp, self.d.ledger, mapping))
        first = validate.LOCAL.search(json.dumps(good)).group(0)
        foreign = json.loads(json.dumps(good).replace(first, "{D:999}", 1))
        self.assertTrue(any("isn't one of the IDs" in p
                            for p in validate.validate("daily_commentary", foreign, inp, self.d.ledger, mapping)))

    def test_commentary_breaking_the_writing_rules_fails(self):
        inp, ids = self.d.input_for("daily_commentary")
        mapping = validate.resolve(self.d.ledger, ids.keys())
        reply = StandIn("x").daily_commentary(inp, False)
        reply["companies"][0]["sentences"][1] = "The estimate held up; the checks passed."
        problems = validate.validate("daily_commentary", reply, inp, self.d.ledger, mapping)
        self.assertTrue(any("semicolon" in p for p in problems))

    def test_deal_values_outside_their_band_fail(self):
        inp, ids = self.d.input_for("deal_analyst")
        mapping = validate.resolve(self.d.ledger, ids.keys())
        reply = StandIn("x").deal_analyst(inp, False)
        self.assertEqual(validate.validate("deal_analyst", reply, inp, self.d.ledger, mapping), [])
        reply["assumptions"][0]["value"] = 0.9
        self.assertTrue(validate.validate("deal_analyst", reply, inp, self.d.ledger, mapping))

    def test_local_ids_resolve_by_meaning(self):
        inp, ids = self.d.input_for("daily_commentary")
        mapping = validate.resolve(self.d.ledger, ids.keys())
        for local, item in ids.keys().items():
            row = self.d.ledger.get(mapping[local])
            self.assertEqual([local[0], row["entity"], row["metric"], row["period"]], item["key"])

    def test_every_prompt_loads_with_its_front_matter(self):
        for task in ("intake_mapper", "daily_commentary", "deal_analyst", "memo_writer", "board_deck"):
            p = prompts.load(task)
            self.assertEqual(p["id"], task)
            self.assertTrue(p["system"] and p["sha256"] and p["output"])


class WritingRules(unittest.TestCase):
    def test_a_comma_before_so_is_a_problem_for_agents_and_copy(self):
        self.assertTrue(any("comma before the word so" in p for p in validate.lint("Generation came in low, so revenue fell.")))
        self.assertEqual(validate.lint("Generation came in low and revenue fell."), [])
        self.assertTrue(helpers.text_problems("Rates rose, so the loan cost more."))

    def test_the_prose_prompts_never_invite_a_comma_before_so(self):
        for task in ("daily_commentary", "deal_analyst", "memo_writer", "board_deck"):
            text = helpers.HERE.joinpath("prompts", task + ".md").read_text()
            self.assertNotIn(", so ", text, task)
            self.assertIn("Never put a comma before so", text, task)


if __name__ == "__main__":
    unittest.main()
