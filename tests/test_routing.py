"""Routing from the model comparison: the rules that pick each agent's model, the config the page reads, and the Model
routing panel. Nothing here calls a model."""
import json
import math
import re
import unittest

from agents import routing
from tests import helpers


def model(mid, intake=None, prose=None, cost=0.1, seconds=10.0):
    tasks = {}
    if intake is not None:
        exact, harmful = intake
        tasks["intake_mapper"] = {"runs": 12, "exact": exact, "harmful": harmful, "valid": 12, "cost": cost,
                                  "seconds": seconds}
    for t in routing.TASKS[1:]:
        if prose is not None:
            tasks[t] = {"runs": 1, "valid": 1 if prose else 0, "first_try": 1 if prose else 0, "cost": cost,
                        "seconds": seconds}
    return {"id": mid, "tasks": tasks}


class Rules(unittest.TestCase):
    def test_the_cheapest_model_that_clears_the_bar_wins_and_the_rest_fall_back(self):
        comp = {"models": [model("big", (12, 0), True, cost=0.30), model("mid", (11, 0), True, cost=0.05),
                           model("small", (9, 0), True, cost=0.01)]}
        r = routing.route(comp, "intake_mapper", "big")
        self.assertEqual((r["model"], r["fallback"], r["why"], r["cleared"]), ("mid", ["big"], "cheapest", 2))

    def test_a_harmful_miss_disqualifies_however_cheap(self):
        comp = {"models": [model("big", (12, 0), True, cost=0.30), model("cheap", (12, 1), True, cost=0.01)]}
        self.assertEqual(routing.route(comp, "intake_mapper", "big")["model"], "big")

    def test_ties_on_cost_go_to_the_faster_model(self):
        comp = {"models": [model("slow", (12, 0), True, cost=0.05, seconds=30), model("fast", (12, 0), True, cost=0.05,
                                                                                         seconds=8)]}
        self.assertEqual(routing.route(comp, "daily_commentary", "slow")["model"], "fast")

    def test_an_unpriced_model_wins_only_when_no_priced_model_clears(self):
        comp = {"models": [model("priced", (12, 0), True, cost=0.20), model("free", (12, 0), True, cost=None)]}
        self.assertEqual(routing.route(comp, "intake_mapper", "x")["model"], "priced")
        comp = {"models": [model("priced", (12, 0), False, cost=0.20), model("free", (12, 0), True, cost=None)]}
        r = routing.route(comp, "daily_commentary", "x")
        self.assertEqual((r["model"], r["why"]), ("free", "unpriced"))

    def test_nothing_clears_and_the_agent_stays_on_the_default(self):
        comp = {"models": [model("a", None, False), model("b", None, False)]}
        r = routing.route(comp, "memo_writer", "claude-opus")
        self.assertEqual((r["model"], r["why"], r["tested"], r["cleared"]), ("claude-opus", "none", 2, 0))
        self.assertEqual(routing.routes(None)["intake_mapper"]["model"], "claude-opus")

    def test_a_hold_wins_only_when_the_held_model_cleared_the_bar(self):
        comp = {"models": [model("big", (12, 0), True, cost=0.30), model("small", (12, 0), True, cost=0.01)]}
        r = routing.route(comp, "memo_writer", "big", held="big")
        self.assertEqual((r["model"], r["why"], r["fallback"]), ("big", "held", ["small"]))
        self.assertEqual(routing.routes(comp, "big", {"memo_writer": "big"})["deal_analyst"]["model"], "small")
        failed = {"models": [model("big", (12, 0), False, cost=0.30), model("small", (12, 0), True, cost=0.01)]}
        r = routing.route(failed, "memo_writer", "big", held="big")
        self.assertEqual((r["model"], r["why"]), ("small", "only"))

    def test_a_morning_costs_the_sum_of_its_five_agents(self):
        self.assertAlmostEqual(routing.morning_cost(model("m", (12, 0), True, cost=0.1)), 0.5)
        self.assertIsNone(routing.morning_cost(model("m", (12, 0), True, cost=None)))


class Config(unittest.TestCase):
    def test_the_config_names_the_models_and_holds_no_way_to_call_them(self):
        text = helpers.HERE.joinpath("config", "models.json").read_text()
        self.assertIsNone(re.search(r"https?:|sk-[A-Za-z0-9_-]{20,}|AIza[0-9A-Za-z_-]{20,}", text))
        cfg = json.loads(text)
        ids = [m["id"] for m in cfg["models"]]
        self.assertEqual(len(ids), len(set(ids)))
        self.assertIn(cfg["default"], ids)
        for m in cfg["models"]:
            self.assertTrue(m["label"] and m["vendor"], m["id"])
            self.assertIn(m["via"], ("claude-cli", "openai"), m["id"])
            self.assertLessEqual(set(m), {"id", "label", "vendor", "via", "model", "price_in", "price_out"}, m["id"])


class Panel(unittest.TestCase):
    """The Model routing panel, driven by the stand-in comparison the test page is built with."""

    @classmethod
    def setUpClass(cls):
        from app import routing_view, words
        cls.view, cls.w = routing_view, words.load()
        cls.html = routing_view.render(helpers.stand_in_comparison(), cls.w)

    def test_the_panel_and_its_step_wait_for_a_comparison(self):
        import build
        self.assertEqual(self.view.render(None, self.w), "")
        self.assertEqual(self.view.render({"models": []}, self.w), "")
        self.assertNotIn("routing", build.steps_for(""))
        steps = build.steps_for(self.html)
        self.assertEqual(steps[steps.index("how") + 1], "routing")
        index = helpers.site().joinpath("index.html").read_text()
        self.assertEqual(index.count("id=\"how-routing\""), 1)
        self.assertLess(index.index("id=\"how-routing\""), index.index("id=\"how-code\""))

    def test_the_chart_rings_the_intake_route_and_keeps_vendor_colors_fixed(self):
        by_id = {mid: cls for cls, mid in re.findall(r"class=\"sc-pt ([^\"]+)\" data-id=\"([^\"]+)\"", self.html)}
        self.assertEqual(by_id, {"beta-mini": "s2 on", "alpha-large": "s1", "alpha-small": "s1", "gamma-flash": "s3",
                                 "delta-one": "so"})
        self.assertIn("The chart leaves out", self.html)
        self.assertIn("<span class=\"sw so\"></span>Other vendors", self.html)
        self.assertEqual(len(re.findall(r"class=\"sc-lbl", self.html)), 5)
        self.assertIn("<details class=\"tableview\">", self.html)

    def test_each_agent_gets_the_cheapest_model_that_cleared_its_bar(self):
        rows = re.findall(r"<tr><td class=\"who\"><strong>([^<]+)</strong></td><td data-label=\"Runs on\">"
                          r"<span data-src=\"results\">([^<]+)</span>", self.html)
        self.assertEqual(dict(rows), {"Intake mapper": "Beta Mini", "Daily commentary": "Gamma Flash",
                                      "Deal analyst": "Beta Mini", "Board deck writer": "Gamma Flash",
                                      "Memo writer": "Gamma Flash"})
        self.assertNotIn("failed validation", re.sub(r"<[^>]+>", "", self.html))
        self.assertIn("1 wrong and accepted", re.sub(r"<[^>]+>", "", self.html))
        self.assertIn("<span class=\"mid\"><span data-src=\"results\">beta-mini</span></span>", self.html)

    def test_the_cost_note_follows_where_the_costs_came_from(self):
        self.assertIn("come from what the CLI reported.", self.html)
        self.assertNotIn("Every cost here", self.html)
        claude_only = helpers.stand_in_comparison()
        for x in claude_only["models"]:
            x["via"] = "claude-cli"
        self.assertIn("Every cost here is what the Claude CLI reported for its calls.",
                      self.view.render(claude_only, self.w))

    def test_held_agents_say_why_and_the_routed_morning_counts_them(self):
        cfg = {"models": [], "default": "alpha-large",
               "holds": {"daily_commentary": "alpha-large", "memo_writer": "alpha-large"}}
        html = self.view.render(helpers.stand_in_comparison(), self.w, cfg)
        text = re.sub(r"<[^>]+>", "", html)
        self.assertIn("The daily commentary and the memo writer stay on Alpha Large because passing validation isn't "
                      "the same as reading well.", html.replace("&#x27;", "'").replace("<span data-src=\"results\">", "")
                      .replace("</span>", ""))
        rows = dict(re.findall(r"<td class=\"who\"><strong>([^<]+)</strong></td><td data-label=\"Runs on\">"
                               r"<span data-src=\"results\">([^<]+)</span>", html))
        self.assertEqual((rows["Memo writer"], rows["Daily commentary"], rows["Intake mapper"]),
                         ("Alpha Large", "Alpha Large", "Beta Mini"))
        self.assertEqual(text.count("Held for writing quality because a person reads it"), 2)
        self.assertIn("The blended morning$0.29", text)
        self.assertIn("50% below Alpha Large on every agent", text)

    def test_the_tiles_compare_the_routed_morning_with_one_model(self):
        text = re.sub(r"<[^>]+>", "", self.html.split("route-tiles")[1].split("<figure")[0])
        self.assertIn("The blended morning$0.023", text)
        self.assertIn("96% below Alpha Large on every agent", text)
        self.assertIn("Every agent on Alpha Large$0.59", text)

    def test_the_blend_adds_up_by_model_beside_each_model_alone(self):
        table = self.html.split("<table class=\"models blend\">")[1].split("</table>")[0]
        rows = [[re.sub(r"<[^>]+>", "", c) for c in re.findall(r"<td[^>]*>(.*?)</td>", r)]
                for r in re.findall(r"<tr[^>]*>(.*?)</tr>", table.split("<tbody>")[1])]
        # Gamma Flash failed the deal analyst, so it has no morning of its own to compare.
        self.assertEqual([r[0] for r in rows], ["Gamma Flash", "Beta Mini", "The blended morning",
                                                "Alpha Large on every agent", "Beta Mini on every agent"])
        self.assertEqual(rows[0][1], "Commentary, board deck, and memo")
        self.assertEqual(rows[1][1], "Intake and deal analyst")
        self.assertEqual((rows[2][3], rows[3][3]), ("$0.023", "$0.59"))
        self.assertIn("class=\"total\"", table)

    def test_money_and_ticks_read_cleanly(self):
        self.assertEqual([self.view.dollars(x) for x in (0.69, 0.1, 0.045, 0.0065, 0.00052)],
                         ["$0.69", "$0.10", "$0.045", "$0.0065", "$0.00052"])
        self.assertEqual([self.view.tick(10.0 ** e) for e in (-4, -3, -2, -1)], ["$0.0001", "$0.001", "$0.01", "$0.10"])
        from app import charts

        def ticks(lo, hi):
            return [(round(v, 6), minor) for v, minor in charts.log_ticks(math.log10(lo) - 0.35, math.log10(hi) + 0.35)]
        self.assertEqual(ticks(0.00009, 0.031), [(0.0001, False), (0.001, False), (0.01, False)])
        self.assertEqual(ticks(0.0009, 0.031), [(0.0005, True), (0.001, False), (0.002, True), (0.005, True),
                                                (0.01, False), (0.02, True), (0.05, True)])
        self.assertEqual(ticks(0.0021, 0.0029), [(0.001, False), (0.002, False), (0.005, False)])

    def test_the_score_axis_starts_below_the_lowest_score_and_the_bar_runs_between_levels(self):
        self.assertEqual(self.view.y_scale([12, 11, 11, 9, 10], 12, 12), ([8, 9, 10, 11, 12], 7.5, 12.5))
        self.assertEqual(self.view.y_scale([12, 5], 12, 12), ([4, 6, 8, 10, 12], 3.0, 13.0))
        self.assertEqual(self.view.y_scale([12, 0], 12, 12), ([0, 3, 6, 9, 12], -1.5, 13.5))
        self.assertEqual(self.view.y_scale([12, 12], 12, 12), ([10, 11, 12], 9.5, 12.5))
        self.assertIn("<div class=\"sc-line\" style=\"bottom:60.00%\">", self.html)
        self.assertIn("data-tip=\"Alpha Small, Alpha Large, and Epsilon\" tabindex=\"0\">"
                      "<span data-src=\"results\">Alpha Small</span> and <span data-src=\"results\">2</span> more</td>",
                      self.html)


if __name__ == "__main__":
    unittest.main()
