"""The script that writes the second hold-out set: what it does with the prompts, what code checks in a
question before a checker sees it, what a question must pass to reach the draft, how it counts money
across runs, and that it never touches the key.

No model is called and no page is fetched here: a scripted client stands in for the provider and a
fake fetch for the web. The script is loaded by its path because evals/professional is not a package.
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
import re
import sys
import types
from pathlib import Path

import httpx
import pytest

from autornd.knowledge import fetch
from autornd.knowledge.fetch import Source
from autornd.routing.openrouter import ModelResponse, provider_order_for, provider_fallbacks_allowed

ROOT = Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "evals" / "professional" / "write_holdout.py"


def _load():
    spec = importlib.util.spec_from_file_location("write_holdout", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    sys.modules["write_holdout"] = module        # a dataclass resolves its annotations here
    spec.loader.exec_module(module)
    return module


mod = _load()


# ---------------------------------------------------------------------------------------------
# Stand-ins.

def page(n: int) -> str:
    """A page of 79 sentences, each with its own figure, well over the shortest page kept."""
    return " ".join(f"Section {i}. The limit for item {n}-{i} is {n * 10 + i} millimetres, "
                    f"measured as stated in clause {i}." for i in range(1, 80))


def sentence(n: int, i: int) -> str:
    return (f"The limit for item {n}-{i} is {n * 10 + i} millimetres, "
            f"measured as stated in clause {i}.")


URLS = {f"https://example.org/doc-{n}": page(n) for n in (1, 2, 3)}


def question(qid: str, n: int, i: int, **over) -> dict:
    """A question a careful author would write about page n: its answer is the figure printed there."""
    q = {"id": qid, "field": "test limits", "difficulty": ["plain lookup"],
         "question": f"What is the limit for item {n}-{i}, in millimetres, as in force on 2026-11-21?",
         "sources": [{"url": f"https://example.org/doc-{n}", "passage": sentence(n, i)}],
         "key": [{"item": "the limit", "answer": f"{n * 10 + i} millimetres"}],
         "commonly_confused": "The figure of the next clause, which reads alike."}
    q.update(over)
    return q


class FakeClient:
    """Stands in for the harness's client: answers from a script, records every call."""

    def __init__(self, script):
        self.script = script
        self.calls: list[dict] = []
        self.spend_ceiling = None
        self.closed = False
        self.http = types.SimpleNamespace(timeout=None)

    async def chat(self, function, system_prompt, user_message, response_format=None,
                   temperature=0.3, max_tokens=16384, model=None, tools=None, tool_choice=None,
                   reasoning=None):
        call = {"function": function, "system": system_prompt, "user": user_message,
                "json": bool(response_format), "model": model, "reasoning": reasoning,
                "max_tokens": max_tokens, "temperature": temperature}
        self.calls.append(call)
        content, cost, finish = self.script(call)
        return ModelResponse(content=content, model=model or "", prompt_tokens=100,
                             completion_tokens=50, cost=cost, finish_reason=finish,
                             provider="acme/p1")

    async def _get_client(self):
        return self.http

    async def close(self):
        self.closed = True


class Script:
    """What the author and the worker say, stage by stage, for a group of three questions."""

    def __init__(self, recheck: str = "OK"):
        self.recheck = recheck
        self.checks = 0

    def __call__(self, call):
        user, fn = call["user"], call["function"]
        if fn == "author" and "Name " in user and "different public documents" in user:
            docs = [{"url": u, "title": f"Document {i}", "why": "limits"}
                    for i, u in enumerate(URLS, 1)]
            docs += [{"url": "https://example.org/missing", "title": "Gone", "why": "x"},
                     {"url": "https://example.org/stub", "title": "Stub", "why": "x"},
                     {"url": "https://example.org/doc-1-copy", "title": "Copy", "why": "x"},
                     {"url": "https://example.org/earlier", "title": "Used before", "why": "x"}]
            return json.dumps({"documents": docs}), 0.01, "stop"
        if fn == "worker" and "TEXT:" in user:
            n = int(re.search(r"doc-(\d)", user).group(1))
            rows = [{"passage": sentence(n, i), "kind": "limit", "topic": f"limit {i}"}
                    for i in (3, 5, 7, 9)]
            rows.append({"passage": "The limit for item 9-9 is 999 millimetres, a sentence this "
                                    "page never prints anywhere at all.", "kind": "limit",
                         "topic": "made up"})
            return json.dumps({"passages": rows}), 0.001, "stop"
        if fn == "worker" and "THE FILE:" in user:
            ids = re.findall(r'"id": "(Y\d+)"', user)
            self.checks += 1                 # calls 1 and 2 are the two readings; 3 and 4 the re-check
            rows = []
            for qid in ids:
                if self.checks <= 2:
                    verdict = "FIX" if (self.checks == 2 and qid == "Y3") else "OK"
                else:
                    verdict = self.recheck
                rows.append({"id": qid, "verdict": verdict,
                             "problem": "" if verdict == "OK" else "two readings",
                             "fix": "" if verdict == "OK" else "say which clause"})
            return json.dumps({"verdicts": rows}), 0.002, "stop"
        if fn == "author" and "QUESTIONS TO REPAIR" in user:
            fixed = [question("Y2", 2, 5), question("Y3", 3, 7, question="Which limit, in "
                     "millimetres, does clause 7 of document 3 give for item 3-7, as in force on "
                     "2026-11-21?")]
            return json.dumps({"questions": fixed}) + "\nNote: repaired.", 0.02, "stop"
        if fn == "author":
            bad = question("Y2", 2, 5, sources=[{"url": "https://example.org/doc-2",
                           "passage": "A passage the page does not hold, word for word."}])
            return (json.dumps({"questions": [question("Y1", 1, 3), bad, question("Y3", 3, 7)]})
                    + "\nNote: all from the pages.", 0.03, "stop")
        raise AssertionError(f"no script for {fn}: {user[:80]}")


def make_fetch(known: dict[str, str] | None = None):
    pages = dict(known or URLS)
    pages["https://example.org/doc-1-copy"] = pages["https://example.org/doc-1"]
    pages["https://example.org/stub"] = "A page with almost nothing on it."
    pages["https://example.org/earlier"] = page(7)
    seen: list[tuple[str, float]] = []

    async def fake(url: str) -> Source:
        seen.append((url, fetch.FETCH_TIMEOUT_SECONDS))
        if url not in pages:
            return Source(url, "failed", "HTTP 404")
        text = pages[url]
        return Source(url, "fetched", final_url=url, fetched_at="2026-11-21T00:00:00Z",
                      sha256=hashlib.sha256(text.encode()).hexdigest(), text=text)

    fake.seen = seen
    return fake


@pytest.fixture
def small(monkeypatch):
    """Three questions a group, two pages enough, no pause between pages, and the globals the script
    sets put back afterwards."""
    monkeypatch.setattr(mod, "PER_GROUP", 3)
    monkeypatch.setattr(mod, "DOCS_WANTED", 3)
    monkeypatch.setattr(mod, "MIN_PAGES_TO_WRITE", 2)
    monkeypatch.setattr(mod, "OPEN_PAUSE_SECONDS", 0)
    monkeypatch.setattr(fetch, "FETCH_TIMEOUT_SECONDS", fetch.FETCH_TIMEOUT_SECONDS)
    monkeypatch.setattr(mod.settings, "openrouter_provider_order", "")
    monkeypatch.setattr(mod.settings, "openrouter_provider_fallbacks", "")
    monkeypatch.setattr(mod, "EARLIER_SETS", [])
    monkeypatch.setattr(mod, "urls_and_questions",
                        lambda *paths: ({"https://example.org/earlier"}, []))


def make_run(tmp_path, client=None, **over):
    prompt_a, prompt_b = mod.load_prompts(mod.PROMPTS.read_text(encoding="utf-8"))
    args = dict(work=tmp_path, author="acme/author-1", author_provider="acme/p1",
                worker="acme/worker-1", worker_provider="acme/p2", date="2026-11-21", budget=None,
                parallel=2, effort_author="medium", effort_check="low", again=False, dry=False,
                groups=[mod.GROUPS[0]], prompt_a=prompt_a, prompt_b=prompt_b, client=client)
    args.update(over)
    return mod.Run(**args)


async def run_stages(run, stages, monkeypatch=None, fake_fetch=None):
    if fake_fetch is not None:
        monkeypatch.setattr(mod.fetch, "fetch_source", fake_fetch)
    for stage in stages:
        await mod.STAGES[stage](run)


# ---------------------------------------------------------------------------------------------

class TestThePromptsAreTheDocs:
    def test_both_prompts_are_read_from_the_document(self):
        a, b = mod.load_prompts(mod.PROMPTS.read_text(encoding="utf-8"))
        assert "WHAT A GOOD QUESTION IS" in a and "DELIVER a table" in b

    def test_prompt_a_is_used_whole_with_only_its_blanks_filled(self):
        a, _ = mod.load_prompts(mod.PROMPTS.read_text(encoding="utf-8"))
        group = mod.GROUPS[2]
        system = mod.author_system(a, group, "2026-11-21")
        expected = (a.replace("{GROUP}", group.area).replace("{FIRST}", "Y29")
                    .replace("{LAST}", "Y42").replace("{DATE}", "2026-11-21"))
        assert system == mod.AUTHOR_PREFACE + expected
        for blank in ("{GROUP}", "{FIRST}", "{LAST}", "{DATE}"):
            assert blank not in system
        assert '{"version": "professional-holdout-2"' in system, "its JSON shape is untouched"

    def test_a_repair_call_asks_for_the_named_questions_and_not_for_fourteen(self):
        a, _ = mod.load_prompts(mod.PROMPTS.read_text(encoding="utf-8"))
        repair = mod.author_system(a, mod.GROUPS[0], "2026-11-21", repair=True)
        write = mod.author_system(a, mod.GROUPS[0], "2026-11-21")
        assert "Write 14 questions" not in repair and "Repair or replace" in repair
        assert "WHAT A GOOD QUESTION IS" in repair
        assert repair.split("WHAT A GOOD QUESTION IS")[1] == write.split("WHAT A GOOD QUESTION IS")[1]

    def test_a_document_that_changed_its_opening_sentence_stops_the_run(self):
        a, _ = mod.load_prompts(mod.PROMPTS.read_text(encoding="utf-8"))
        with pytest.raises(ValueError, match="Write 14 questions"):
            mod.author_system(a.replace("Write 14 questions", "Write 15 questions"),
                              mod.GROUPS[0], "2026-11-21")

    def test_the_checker_prompt_is_prompt_b_up_to_the_file(self):
        _, b = mod.load_prompts(mod.PROMPTS.read_text(encoding="utf-8"))
        system = mod.checker_system(b)
        assert system.startswith(b.split("THE FILE:")[0].rstrip())
        assert "{paste the author's JSON}" not in system and '{"verdicts"' in system

    def test_the_areas_already_covered_come_from_prompt_a(self):
        a, _ = mod.load_prompts(mod.PROMPTS.read_text(encoding="utf-8"))
        covered = mod.covered_areas(a)
        assert covered.startswith("employment, payroll") and covered.endswith("EPA SPCC.")

    def test_there_are_nine_groups_of_fourteen_numbered_y1_to_y126(self):
        ids = [qid for group in mod.GROUPS for qid in group.ids]
        assert len(mod.GROUPS) == 9 and ids == [f"Y{n}" for n in range(1, 127)]


class TestTheLineUp:
    """Groups 1 to 6 are the first set's ground twice over; groups 7 to 9 are the three engineering
    subjects the owner added on 2026-11-21, described in detail and not by a bare label."""

    SUBJECTS = {7: "electrical power systems and installations",
                8: "mechanical, thermal and materials engineering",
                9: "civil, structural and geotechnical engineering"}

    def test_the_three_engineering_groups_come_after_the_six_and_name_their_subjects(self):
        added = {g.number: g.area for g in mod.GROUPS if g.number > 6}
        assert sorted(added) == [7, 8, 9]
        for number, subject in self.SUBJECTS.items():
            assert added[number].startswith(subject + ":"), number

    def test_each_added_group_is_described_in_detail_and_not_by_a_bare_label(self):
        # "electrical systems" is the label the owner asked to be more detailed than: two words and
        # no topics. The plan call names documents from this text alone.
        for group in mod.GROUPS:
            if group.number <= 6:
                continue
            words = len(group.area.split())
            topics = group.area.count(";") + group.area.count(",")
            assert words >= 60 and topics >= 12, (group.number, words, topics)

    def test_no_two_groups_share_an_area(self):
        assert len({g.area for g in mod.GROUPS}) == len(mod.GROUPS)

    def test_the_default_runs_every_group_so_an_added_group_is_not_left_out(self):
        args = mod.parse_args(["w", "plan", "--author", "a/b", "--author-provider", "p",
                               "--worker", "c/d", "--worker-provider", "q"])
        assert {int(n) for n in args.groups.split(",")} == {g.number for g in mod.GROUPS}

    @pytest.mark.parametrize("number", [7, 8, 9])
    def test_the_whole_area_and_the_groups_own_ids_reach_the_author(self, number):
        a, _ = mod.load_prompts(mod.PROMPTS.read_text(encoding="utf-8"))
        group = next(g for g in mod.GROUPS if g.number == number)
        system = mod.author_system(a, group, "2026-11-21")
        assert group.area in system
        assert f"Number them {group.ids[0]} to {group.ids[-1]}." in system

    async def test_the_whole_area_reaches_the_plan_call(self, tmp_path, small):
        group = next(g for g in mod.GROUPS if g.number == 7)
        client = FakeClient(Script())
        run = make_run(tmp_path, client=client, groups=[group])
        await mod.STAGES["plan"](run)
        plans = [c for c in client.calls if "different public documents" in c["user"]]
        assert len(plans) == 1 and f"The area: {group.area}." in plans[0]["user"]


class TestThePlanReply:
    """The first live run's replies named 91 and 161 documents when 30 were asked for, and one stopped at
    its limit in the middle of an entry. The plan keeps what was finished and takes what was asked."""

    @staticmethod
    def entry(n: int) -> dict:
        return {"url": f"https://example.org/doc-{n}", "title": f"Document {n}", "why": "limits"}

    def cut_reply(self) -> str:
        whole = json.dumps({"documents": [self.entry(1), self.entry(2), self.entry(3)]})
        return whole[:whole.index("doc-3") + 3]

    def test_a_whole_reply_gives_its_documents(self):
        reply = json.dumps({"documents": [self.entry(1), self.entry(2)]}) + "\nA note."
        assert [d["url"] for d in mod.plan_entries(reply)] == [
            "https://example.org/doc-1", "https://example.org/doc-2"]

    def test_a_bare_list_is_read_too(self):
        assert len(mod.plan_entries(json.dumps([self.entry(1), self.entry(2), self.entry(3)]))) == 3

    def test_text_before_the_json_does_not_matter(self):
        reply = "Here are the documents: " + json.dumps({"documents": [self.entry(1)]})
        assert len(mod.plan_entries(reply)) == 1

    def test_a_reply_cut_in_the_middle_of_an_entry_gives_the_entries_finished_before_the_cut(self):
        assert [d["title"] for d in mod.plan_entries(self.cut_reply())] == ["Document 1", "Document 2"]

    def test_a_reply_cut_before_its_first_entry_is_finished_gives_nothing(self):
        assert mod.plan_entries('{"documents": [{"url": "https://exa') == []

    @pytest.mark.parametrize("reply", ["I could not do it.", "", '{"documents": "none"}'])
    def test_a_reply_with_no_entries_gives_nothing(self, reply):
        assert mod.plan_entries(reply) == []

    async def test_only_a_caller_that_says_so_may_keep_a_reply_that_was_cut_off(self, tmp_path):
        client = FakeClient(lambda call: ('{"documents": [', 0.01, "length"))
        run = make_run(tmp_path, client=client)
        kept = await mod.ask(run, "plan", mod.GROUPS[0], "author", "s", "u", max_tokens=10,
                             keep_cut=True)
        assert kept == '{"documents": ['
        with pytest.raises(mod.ReplyCutOff):
            await mod.ask(run, "plan", mod.GROUPS[0], "author", "s", "u", max_tokens=10)
        assert run.spent() == pytest.approx(0.02), "both were paid for"

    async def test_a_plan_reply_that_stopped_at_its_limit_still_gives_its_finished_entries(
            self, tmp_path, small):
        client = FakeClient(lambda call: (self.cut_reply(), 0.01, "length"))
        run = make_run(tmp_path, client=client)
        await mod.STAGES["plan"](run)
        plan = json.loads((tmp_path / "plan-g1.json").read_text())
        assert [d["title"] for d in plan["documents"]] == ["Document 1", "Document 2"]
        assert run.errors == [] and run.spent() == pytest.approx(0.01), "it was paid for and used"

    async def test_no_more_documents_are_taken_than_were_asked_for(self, tmp_path, small, monkeypatch):
        monkeypatch.setattr(mod, "ASK_FIRST", 2)
        entries = [self.entry(n) for n in range(1, 8)]
        client = FakeClient(lambda call: (json.dumps({"documents": entries}), 0.01, "stop"))
        run = make_run(tmp_path, client=client)
        await mod.STAGES["plan"](run)
        plan = json.loads((tmp_path / "plan-g1.json").read_text())
        assert [d["title"] for d in plan["documents"]] == ["Document 1", "Document 2"]

    async def test_a_second_round_takes_only_as_many_as_it_asks_for(self, tmp_path, small, monkeypatch):
        monkeypatch.setattr(mod, "ASK_FIRST", 3)
        monkeypatch.setattr(mod, "ASK_MORE", 1)
        entries = [self.entry(n) for n in range(1, 10)]
        client = FakeClient(lambda call: (json.dumps({"documents": entries}), 0.01, "stop"))
        run = make_run(tmp_path, client=client)
        await mod.STAGES["plan"](run)
        await mod.STAGES["plan"](run)
        plan = json.loads((tmp_path / "plan-g1.json").read_text())
        assert [d["title"] for d in plan["documents"]] == [f"Document {n}" for n in (1, 2, 3, 4)]
        assert plan["asked"] == 2

    async def test_the_plan_call_asks_for_exactly_the_number_wanted_and_for_short_reasons(
            self, tmp_path, small):
        client = FakeClient(Script())
        await mod.STAGES["plan"](make_run(tmp_path, client=client))
        user = client.calls[0]["user"]
        assert f"exactly {mod.ASK_FIRST} different public documents in this area, and no more" in user
        assert "in under 15 words" in user

    async def test_the_plan_reply_ceiling_keeps_a_runaway_to_cents(self, tmp_path, small):
        client = FakeClient(Script())
        await mod.STAGES["plan"](make_run(tmp_path, client=client))
        assert client.calls[0]["max_tokens"] == mod.PLAN_MAX_TOKENS
        assert mod.PLAN_MAX_TOKENS <= 6000


class TestReadingAReply:
    @pytest.mark.parametrize("reply, note", [
        ('{"a": 1}\nA short note.', "A short note."),
        ('Here it is {not json} first.\n```json\n{"a": 1}\n```', ""),
        ('{"a": "a } inside a string"} then', "then"),
    ])
    def test_the_first_json_object_is_found_and_the_rest_is_the_note(self, reply, note):
        value, rest = mod.first_json(reply)
        assert isinstance(value, dict) and rest == note

    def test_a_reply_with_no_json_is_an_error(self):
        with pytest.raises(ValueError):
            mod.first_json("I could not do it.")

    def test_ids_the_author_was_told_to_use_are_kept(self):
        reply = json.dumps({"questions": [question("Y2", 2, 3), question("Y1", 1, 3)]})
        got, _ = mod.read_questions(reply, ["Y1", "Y2", "Y3"])
        assert [q["id"] for q in got] == ["Y1", "Y2"]

    def test_ids_that_are_not_the_groups_are_replaced_in_order(self):
        reply = json.dumps({"questions": [question("Q1", 1, 3), question("Q2", 2, 3)]})
        got, _ = mod.read_questions(reply, ["Y5", "Y6", "Y7"])
        assert [q["id"] for q in got] == ["Y5", "Y6"]

    def test_a_repeated_id_is_treated_as_off_and_replaced_in_order(self):
        reply = json.dumps({"questions": [question("Y1", 1, 3), question("Y1", 2, 3)]})
        got, _ = mod.read_questions(reply, ["Y1", "Y2", "Y3"])
        assert [q["id"] for q in got] == ["Y1", "Y2"]

    def test_a_question_comes_back_in_the_first_sets_shape(self):
        raw = question("Y1", 1, 3)
        raw["difficulty"] = "plain lookup"
        raw["key"][0]["answer"] = 13
        raw["junk"] = "dropped"
        got = mod.clean_question(raw)
        assert got["difficulty"] == ["plain lookup"] and got["key"][0]["answer"] == "13"
        assert list(got) == ["id", "field", "difficulty", "question", "sources", "key",
                             "commonly_confused"]

    def test_a_derived_key_entry_stays_marked(self):
        raw = question("Y1", 1, 3)
        raw["key"][0]["derived"] = True
        assert mod.clean_question(raw)["key"][0]["derived"] is True

    def test_verdicts_are_read_by_id_and_an_unanswered_id_is_missing(self):
        reply = json.dumps({"verdicts": [
            {"id": "Y1", "verdict": "ok", "problem": "", "fix": ""},
            {"id": "Y2", "verdict": "Maybe", "problem": "unsure", "fix": ""},
            {"id": "Y9", "verdict": "OK", "problem": "", "fix": ""}]})
        got = mod.parse_verdicts(reply, ["Y1", "Y2", "Y3"])
        assert got["Y1"]["verdict"] == "OK"
        assert got["Y2"]["verdict"] == "UNREADABLE"
        assert got["Y3"]["verdict"] == "MISSING" and "Y9" not in got


class TestAQuestionIsCheckedByCodeBeforeAnyCheckerSeesIt:
    def test_a_question_whose_passages_and_figures_are_on_its_pages_passes(self):
        assert mod.problems(question("Y1", 1, 3), URLS) == []

    def test_a_passage_that_is_not_on_the_page_is_found_out(self):
        q = question("Y1", 1, 3, sources=[{"url": "https://example.org/doc-1",
                                           "passage": "A sentence this page never prints."}])
        assert any("passage not on the page" in p for p in mod.problems(q, URLS))

    def test_a_source_that_was_never_opened_is_found_out(self):
        q = question("Y1", 1, 3, sources=[{"url": "https://example.org/elsewhere",
                                           "passage": sentence(1, 3)}])
        assert any("not a page that was opened" in p for p in mod.problems(q, URLS))

    def test_a_figure_that_is_on_no_cited_page_is_found_out(self):
        q = question("Y1", 1, 3, key=[{"item": "the limit", "answer": "4711 millimetres"}])
        assert any("figures not on the cited pages" in p for p in mod.problems(q, URLS))

    def test_a_derived_answer_need_not_be_on_the_page(self):
        q = question("Y1", 1, 3, key=[{"item": "a sum", "answer": "4711 millimetres",
                                       "derived": True}])
        assert mod.problems(q, URLS) == []

    def test_an_address_with_a_trailing_slash_names_the_same_page(self):
        q = question("Y1", 1, 3)
        q["sources"][0]["url"] += "/"
        assert mod.problems(q, URLS) == []

    @pytest.mark.parametrize("name", ["field", "question", "commonly_confused", "sources", "key",
                                      "difficulty"])
    def test_a_question_missing_a_part_is_found_out(self, name):
        q = question("Y1", 1, 3)
        q[name] = [] if isinstance(q[name], list) else ""
        assert mod.problems(q, URLS)


class TestTheEarlierSets:
    def test_addresses_and_questions_are_read_whatever_the_shape(self, tmp_path):
        old = tmp_path / "old.json"
        old.write_text(json.dumps({"questions": [
            {"id": "A1", "question": "What is the limit?", "source": "https://a.org/x/"},
            {"id": "A2", "question": "Another?", "sources": [{"url": "https://b.org/y",
                                                             "passage": "p"}]}]}))
        urls, questions = mod.urls_and_questions(old, tmp_path / "absent.json")
        assert urls == {"https://a.org/x", "https://b.org/y"}
        assert questions == [("A1", "What is the limit?"), ("A2", "Another?")]

    def test_a_question_nearly_like_an_earlier_one_is_a_near_duplicate(self):
        q = question("Y1", 1, 3)
        near, same = mod.duplicates(q, set(), [("X7", q["question"] + " Please.")])
        assert near and near[0].startswith("X7") and not same

    def test_a_question_that_cites_an_earlier_page_only_says_so(self):
        near, same = mod.duplicates(question("Y1", 1, 3), {"https://example.org/doc-1"},
                                    [("X7", "A wholly different matter about something else.")])
        assert not near and same == ["https://example.org/doc-1"]


class TestTheMoneyTheKeyAndThePins:
    def test_the_source_never_names_the_key(self):
        """The harness's client reads the key from .env; this script must not."""
        source = SCRIPT.read_text(encoding="utf-8").lower()
        assert "api_key" not in source and "openrouter_api" not in source

    def test_no_model_is_named_in_the_source(self):
        source = SCRIPT.read_text(encoding="utf-8")
        assert not re.search(r"\b(?:tencent|anthropic|openai|moonshot|z-ai|deepseek)/", source)

    async def test_the_budget_counts_what_earlier_runs_spent(self, tmp_path, monkeypatch, small):
        (tmp_path / "calls.jsonl").write_text(
            json.dumps({"stage": "plan", "model": "m", "cost": 0.30, "ok": True}) + "\n")
        fake = FakeClient(Script())

        async def no_pins(run):
            return None

        async def no_models():
            return {}

        monkeypatch.setattr(mod, "verify_pins", no_pins)
        monkeypatch.setattr(mod, "check_models", no_models)
        monkeypatch.setattr(mod, "OpenRouterClient", lambda: fake)
        run = make_run(tmp_path, budget=0.50)
        await mod.open_client(run)
        assert fake.spend_ceiling == pytest.approx(0.20)
        assert fake.http.timeout == httpx.Timeout(mod.REPLY_TIMEOUT_SECONDS)

    async def test_each_function_is_pinned_to_its_provider_with_no_fallback(
            self, tmp_path, monkeypatch, small):
        async def no_pins(run):
            return None

        async def no_models():
            return {}

        monkeypatch.setattr(mod, "verify_pins", no_pins)
        monkeypatch.setattr(mod, "check_models", no_models)
        monkeypatch.setattr(mod, "OpenRouterClient", lambda: FakeClient(Script()))
        monkeypatch.setattr(mod.settings, "openrouter_provider_fallbacks", "true")
        await mod.open_client(make_run(tmp_path, budget=1.0))
        assert provider_order_for("author") == ["acme/p1"]
        assert provider_order_for("worker") == ["acme/p2"]
        assert provider_order_for("triage") == [], "the owner's own tiers are not pinned by this"
        assert not provider_fallbacks_allowed()

    @pytest.mark.parametrize("status, tags, said", [
        (404, [], "does not list a model"),
        (200, ["acme/other"], "is not served by acme/p1"),
    ])
    async def test_an_unknown_model_or_provider_tag_stops_the_run_before_any_call(
            self, tmp_path, monkeypatch, small, status, tags, said):
        def handler(request: httpx.Request) -> httpx.Response:
            body = {"data": {"endpoints": [{"tag": t, "provider_name": t} for t in tags]}}
            return httpx.Response(status, json=body)

        real = httpx.AsyncClient
        monkeypatch.setattr(mod.httpx, "AsyncClient",
                            lambda **kw: real(transport=httpx.MockTransport(handler), **kw))
        with pytest.raises(SystemExit, match=said):
            await mod.verify_pins(make_run(tmp_path))

    async def test_a_known_provider_tag_passes(self, tmp_path, monkeypatch, small):
        def handler(request: httpx.Request) -> httpx.Response:
            tag = "acme/p1" if "author" in str(request.url) else "acme/p2"
            return httpx.Response(200, json={"data": {"endpoints": [{"tag": tag}]}})

        real = httpx.AsyncClient
        monkeypatch.setattr(mod.httpx, "AsyncClient",
                            lambda **kw: real(transport=httpx.MockTransport(handler), **kw))
        await mod.verify_pins(make_run(tmp_path))

    async def test_a_paid_stage_without_an_amount_is_refused(self, tmp_path):
        with pytest.raises(SystemExit, match="--budget"):
            await mod.main([str(tmp_path), "plan", "--author", "a/b", "--author-provider", "p",
                            "--worker", "c/d", "--worker-provider", "q"])

    async def test_a_dry_run_asks_nothing_and_says_what_it_would_cost(
            self, tmp_path, monkeypatch, small, capsys):
        fake = FakeClient(Script())

        async def prices(run):
            run.prices = {"a/b": (1e-6, 2e-6), "c/d": (1e-7, 2e-7)}

        monkeypatch.setattr(mod, "load_prices", prices)
        monkeypatch.setattr(mod, "OpenRouterClient", lambda: fake)
        await mod.main([str(tmp_path), "plan", "--author", "a/b", "--author-provider", "p",
                        "--worker", "c/d", "--worker-provider", "q", "--dry-run", "--groups", "1,2"])
        out = capsys.readouterr().out
        assert fake.calls == [] and not (tmp_path / "calls.jsonl").exists()
        assert "would ask 2 calls" in out and "at most $" in out

    async def test_a_reply_cut_off_at_its_limit_is_paid_for_and_then_refused(self, tmp_path):
        client = FakeClient(lambda call: ("{\"documents\": [", 0.01, "length"))
        run = make_run(tmp_path, client=client)
        with pytest.raises(mod.ReplyCutOff):
            await mod.ask(run, "plan", mod.GROUPS[0], "author", "s", "u", max_tokens=10)
        assert run.spent() == pytest.approx(0.01), "the call is on the ledger before the refusal"
        assert (tmp_path / "raw").exists()

    async def test_once_the_budget_stops_a_stage_no_further_call_is_started(self, tmp_path):
        def script(call):
            raise mod.BudgetExceeded("stopped at $0.05")

        client = FakeClient(script)
        run = make_run(tmp_path, client=client, parallel=1)
        jobs = [(f"job {n}", (lambda: mod.ask(run, "plan", None, "author", "s", "u", max_tokens=1)))
                for n in range(4)]
        assert await mod.each(run, jobs) == 0
        assert len(client.calls) == 1, "the first call was refused and nothing started after it"
        assert len(run.errors) == 4 and run.stopped


class TestTheStagesFromPlanToDraft:
    async def test_every_stage_runs_and_only_checked_questions_reach_the_draft(
            self, tmp_path, monkeypatch, small):
        client = FakeClient(Script())
        run = make_run(tmp_path, client=client)
        await run_stages(run, ["plan", "open", "extract", "write", "check", "fix", "assemble"],
                         monkeypatch, make_fetch())

        opened = json.loads((tmp_path / "opened-g1.json").read_text())
        assert [p["ok"] for p in opened] == [True, True, True, False, False, False, False]
        why = {p["url"].rsplit("/", 1)[1]: p["reason"] for p in opened if not p["ok"]}
        assert "404" in why["missing"] and "characters" in why["stub"]
        assert "same document" in why["doc-1-copy"] and "earlier set" in why["earlier"]

        passages = json.loads((tmp_path / "passages-g1.json").read_text())
        for url, rows in passages.items():
            assert len(rows) == 4, "the made-up passage was dropped"
            assert all(quote_in(url, row["passage"]) for row in rows)

        draft = json.loads((tmp_path / "holdout2-questions.json").read_text())
        assert draft["status"] == "Draft, not approved"
        assert draft["version"] == "professional-holdout-2"
        assert [q["id"] for q in draft["questions"]] == ["Y1", "Y2", "Y3"]
        for q in draft["questions"]:
            assert mod.problems(q, URLS) == []

        checks = [c for c in client.calls if "THE FILE:" in c["user"]]
        first = [c for c in checks if '"Y2"' not in c["user"].split("THE PAGES:")[0]]
        assert len(first) == 2, "the first two readings never carried Y2, whose passage is not on its page"
        assert len(checks) == 4, "two readings, then two more of the repaired questions"

        repair = [c for c in client.calls if "QUESTIONS TO REPAIR" in c["user"]]
        assert len(repair) == 1 and "Repair or replace" in repair[0]["system"]
        assert "Y2" in repair[0]["user"] and "passage not on the page" in repair[0]["user"]
        assert "checker 2: FIX" in repair[0]["user"], "the checker's words reach the author"
        assert "Y1:" in repair[0]["user"], "the accepted question is listed so its topic is not repeated"

        review = (tmp_path / "review.md").read_text()
        assert "3 questions accepted of 3" in review and "| total |" in review

    async def test_a_question_a_checker_still_rejects_after_the_repair_is_held_back(
            self, tmp_path, monkeypatch, small):
        client = FakeClient(Script(recheck="DROP"))
        run = make_run(tmp_path, client=client)
        await run_stages(run, ["plan", "open", "extract", "write", "check", "fix", "assemble"],
                         monkeypatch, make_fetch())
        draft = json.loads((tmp_path / "holdout2-questions.json").read_text())
        assert [q["id"] for q in draft["questions"]] == ["Y1"]
        review = (tmp_path / "review.md").read_text()
        assert "**Y2** HELD BACK" in review and "**Y3** HELD BACK" in review
        assert "1 questions accepted of 3" in review

    async def test_a_question_that_repeats_an_earlier_one_is_held_back(
            self, tmp_path, monkeypatch, small):
        q1 = question("Y1", 1, 3)
        monkeypatch.setattr(mod, "urls_and_questions",
                            lambda *paths: ({"https://example.org/earlier"},
                                            [("X9", q1["question"])]))
        run = make_run(tmp_path, client=FakeClient(Script()))
        await run_stages(run, ["plan", "open", "extract", "write", "check", "fix", "assemble"],
                         monkeypatch, make_fetch())
        review = (tmp_path / "review.md").read_text()
        assert "**Y1** HELD BACK: near-duplicate of X9" in review

    async def test_a_stage_that_is_run_again_asks_only_for_what_is_missing(
            self, tmp_path, monkeypatch, small):
        client = FakeClient(Script())
        run = make_run(tmp_path, client=client)
        stages = ["plan", "open", "extract", "write", "check"]
        await run_stages(run, stages, monkeypatch, make_fetch())
        asked = len(client.calls)
        await run_stages(run, ["open", "extract", "write", "check"], monkeypatch, make_fetch())
        assert len(client.calls) == asked

    async def test_pages_are_read_with_a_longer_limit_than_the_harnesss_own(
            self, tmp_path, monkeypatch, small):
        run = make_run(tmp_path, client=FakeClient(Script()))
        fake = make_fetch()
        await run_stages(run, ["plan", "open"], monkeypatch, fake)
        assert {limit for _, limit in fake.seen} == {mod.OPEN_TIMEOUT_SECONDS}
        assert mod.OPEN_TIMEOUT_SECONDS > 60.0

    async def test_the_author_is_told_where_the_pages_came_from_and_given_only_verified_passages(
            self, tmp_path, monkeypatch, small):
        client = FakeClient(Script())
        run = make_run(tmp_path, client=client)
        await run_stages(run, ["plan", "open", "extract", "write"], monkeypatch, make_fetch())
        write = [c for c in client.calls if c["function"] == "author" and "Write the 3" in c["user"]]
        assert len(write) == 1
        assert write[0]["system"].startswith(mod.AUTHOR_PREFACE)
        assert "999 millimetres" not in write[0]["user"], "a made-up passage never reached the author"
        assert write[0]["reasoning"] == {"effort": "medium"}
        extract = [c for c in client.calls if "TEXT:" in c["user"]]
        assert all(c["reasoning"] == {"enabled": False} and c["json"] for c in extract)
        assert {c["model"] for c in extract} == {"acme/worker-1"}
        assert write[0]["model"] == "acme/author-1"

    async def test_a_group_with_too_few_pages_is_not_written(self, tmp_path, monkeypatch, small):
        monkeypatch.setattr(mod, "MIN_PAGES_TO_WRITE", 5)
        run = make_run(tmp_path, client=FakeClient(Script()))
        await run_stages(run, ["plan", "open", "extract", "write"], monkeypatch, make_fetch())
        assert not (tmp_path / "draft-g1.json").exists()
        assert any("only 3 pages have passages" in line for line in run.errors)

    async def test_the_fix_stage_will_not_repair_what_no_checker_has_read(
            self, tmp_path, monkeypatch, small):
        run = make_run(tmp_path, client=FakeClient(Script()))
        await run_stages(run, ["plan", "open", "extract", "write", "fix"], monkeypatch, make_fetch())
        assert any("run the check stage first" in line for line in run.errors)
        assert not (tmp_path / "fixed-g1.json").exists()

    async def test_the_fix_stage_has_nothing_to_repair_before_a_draft_is_written(
            self, tmp_path, monkeypatch, small):
        client = FakeClient(Script())
        run = make_run(tmp_path, client=client)
        await run_stages(run, ["fix"])
        assert client.calls == []
        assert any("run the write stage first" in line for line in run.errors)

    async def test_naming_documents_is_asked_with_reasoning_off_because_a_level_is_ignored(
            self, tmp_path, monkeypatch, small):
        # The live endpoint ignored low, minimal and none and spent every token on thought; only off
        # let a reply through (see PLAN_EFFORT).
        client = FakeClient(Script())
        await run_stages(make_run(tmp_path, client=client), ["plan"])
        assert client.calls[0]["reasoning"] == {"enabled": False}

    async def test_writing_a_group_again_throws_away_the_checks_of_the_old_draft(
            self, tmp_path, monkeypatch, small):
        run = make_run(tmp_path, client=FakeClient(Script()))
        await run_stages(run, ["plan", "open", "extract", "write", "check"], monkeypatch, make_fetch())
        assert list(tmp_path.glob("check-g1-*.json"))
        (tmp_path / "draft-g1.json").unlink()
        await run_stages(run, ["write"])
        assert not list(tmp_path.glob("check-g1-*.json"))


def quote_in(url: str, passage: str) -> bool:
    from autornd.knowledge.research import quote_found
    return quote_found(passage, URLS[url])
