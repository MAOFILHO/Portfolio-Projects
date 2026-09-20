"""Phase 8 -- the real summarizer: `gpt-5.4-mini` chat completions on the Azure OpenAI v1 path.

Shapes derived from docs/phase8/research-postcall-adapters.md (Q2), which cites the Learn reasoning
and structured-outputs pages and the v1 OpenAPI spec. No live call has been made; the scripted
`httpx.MockTransport` pins the wire format and the first live call proves it.

Two rules carry most of this file. The summarizer accepts only a clean, complete, well-formed answer
and raises on everything else (the pipeline records a failed summary and moves on). And the B3 text
pin (ADR-006 Decision 4) is checked before every call -- raising, never blocking anything a caller
is doing, since this runs after the call.
"""
import asyncio
import json
import unittest

import httpx
from azbank_voice_agent import boot
from azbank_voice_agent.postcall import summarizer
from azbank_voice_agent.postcall.pipeline import Summary

ENDPOINT = "https://aoai-test.openai.azure.com/"
DEPLOYMENT = "gpt-5.4-mini"
TURNS = ["Hello, how can I help?", "Your balance is [REDACTED]."]


async def _token():
    return "test-token"


def _good_completion(**overrides):
    content = overrides.pop("content", json.dumps({"summary": "The caller asked for a balance.",
                                                    "intent": "balance_enquiry"}))
    choice = {"index": 0, "finish_reason": overrides.pop("finish_reason", "stop"),
              "message": {"role": "assistant", "content": content,
                          "refusal": overrides.pop("refusal", None)}}
    body = {"model": "gpt-5.4-mini-2026-03-17", "choices": [choice],
            "usage": {"prompt_tokens": 50, "completion_tokens": 40,
                      "completion_tokens_details": {"reasoning_tokens": 10}}}
    body.update(overrides)
    return body


class FakeOpenAI:
    def __init__(self, status=200, body=None):
        self.status = status
        self.body = body if body is not None else _good_completion()
        self.requests = []

    def transport(self):
        def handle(request):
            self.requests.append(request)
            return httpx.Response(self.status, json=self.body)
        return httpx.MockTransport(handle)


def _reader(live=boot.ACTIVE_TEXT_MODEL, calls=None):
    def read(deployment):
        if calls is not None:
            calls.append(deployment)
        if isinstance(live, Exception):
            raise live
        return live
    return read


def _summarize(server=None, turns=TURNS, reader=None):
    server = server or FakeOpenAI()

    async def go():
        async with httpx.AsyncClient(transport=server.transport()) as http:
            s = summarizer.OpenAISummarizer(ENDPOINT, DEPLOYMENT, http, _token, reader or _reader())
            return await s.summarize(turns)

    return asyncio.run(go()), server


class TheRequestIsWhatTheDocsSay(unittest.TestCase):
    def test_a_post_to_the_v1_chat_completions_path_with_no_api_version_and_a_bearer_token(self):
        _, server = _summarize()
        [request] = server.requests
        self.assertEqual(request.method, "POST")
        self.assertEqual(request.url.host, "aoai-test.openai.azure.com")
        self.assertEqual(request.url.path, "/openai/v1/chat/completions")
        self.assertNotIn("api-version", request.url.params)
        self.assertEqual(request.headers["Authorization"], "Bearer test-token")

    def test_the_model_is_the_deployment_name_and_the_turns_are_the_user_message(self):
        _, server = _summarize()
        body = json.loads(server.requests[0].content)
        self.assertEqual(body["model"], DEPLOYMENT)
        roles = [m["role"] for m in body["messages"]]
        self.assertEqual(roles, ["developer", "user"])
        self.assertEqual(body["messages"][1]["content"], "\n".join(TURNS))

    def test_only_parameters_a_reasoning_model_accepts_are_sent(self):
        _, server = _summarize()
        body = json.loads(server.requests[0].content)
        for rejected in ("max_tokens", "temperature", "top_p", "presence_penalty",
                         "frequency_penalty", "logprobs", "top_logprobs", "logit_bias"):
            self.assertNotIn(rejected, body)
        self.assertGreaterEqual(body["max_completion_tokens"], 1000)
        self.assertIn(body["reasoning_effort"], {"low", "medium"})

    def test_the_answer_is_constrained_to_a_strict_two_field_schema(self):
        _, server = _summarize()
        fmt = json.loads(server.requests[0].content)["response_format"]
        self.assertEqual(fmt["type"], "json_schema")
        schema = fmt["json_schema"]
        self.assertIs(schema["strict"], True)
        self.assertEqual(schema["schema"]["required"], ["summary", "intent"])
        self.assertIs(schema["schema"]["additionalProperties"], False)
        self.assertEqual(set(schema["schema"]["properties"]["intent"]["enum"]), summarizer.INTENTS)

    def test_the_developer_message_says_the_transcript_is_data_not_instructions(self):
        _, server = _summarize()
        instructions = json.loads(server.requests[0].content)["messages"][0]["content"].lower()
        self.assertIn("redacted", instructions)
        self.assertIn("not instructions", instructions)


class AGoodAnswerBecomesASummary(unittest.TestCase):
    def test_summary_and_intent_come_back(self):
        result, _ = _summarize()
        self.assertEqual(result, Summary("The caller asked for a balance.", "balance_enquiry"))


class AnythingLessThanACleanCompleteAnswerRaises(unittest.TestCase):
    def _assert_raises(self, server):
        with self.assertRaises(Exception):  # noqa: B017 -- the contract is "raises", not a type
            _summarize(server)

    def test_http_errors(self):
        for status in (400, 401, 403, 404, 429, 500, 503):
            self._assert_raises(FakeOpenAI(status=status, body={"error": {"code": "x", "message": "y"}}))

    def test_an_answer_cut_off_by_the_token_cap(self):
        self._assert_raises(FakeOpenAI(body=_good_completion(finish_reason="length", content="")))

    def test_an_answer_the_content_filter_stopped(self):
        self._assert_raises(FakeOpenAI(body=_good_completion(finish_reason="content_filter", content=None)))

    def test_a_refusal(self):
        self._assert_raises(FakeOpenAI(body=_good_completion(refusal="I can't help with that.")))

    def test_no_choices(self):
        self._assert_raises(FakeOpenAI(body={"choices": []}))
        self._assert_raises(FakeOpenAI(body={}))

    def test_content_that_is_not_json(self):
        self._assert_raises(FakeOpenAI(body=_good_completion(content="The caller wanted a balance.")))
        self._assert_raises(FakeOpenAI(body=_good_completion(content="")))
        self._assert_raises(FakeOpenAI(body=_good_completion(content=None)))

    def test_json_that_is_not_the_two_fields(self):
        for content in ('[]', '"x"', '{"summary": "s"}', '{"intent": "unknown"}',
                        '{"summary": 3, "intent": "unknown"}', '{"summary": "s", "intent": 3}'):
            self._assert_raises(FakeOpenAI(body=_good_completion(content=content)))

    def test_an_empty_summary(self):
        self._assert_raises(FakeOpenAI(body=_good_completion(
            content=json.dumps({"summary": "  ", "intent": "unknown"}))))

    def test_an_intent_outside_the_known_set(self):
        self._assert_raises(FakeOpenAI(body=_good_completion(
            content=json.dumps({"summary": "s", "intent": "wire_the_money_offshore"}))))


class TheIntentSetMatchesWhatTheAgentCanDo(unittest.TestCase):
    def test_every_value_is_a_lowercase_label_and_unknown_is_there(self):
        self.assertIn("unknown", summarizer.INTENTS)
        for intent in summarizer.INTENTS:
            self.assertRegex(intent, r"^[a-z_]+$")


class TheTextModelPinIsCheckedBeforeEveryCall(unittest.TestCase):
    def test_the_pinned_deployment_is_read_and_the_call_proceeds(self):
        calls = []
        _, server = _summarize(reader=_reader(calls=calls))
        self.assertEqual(calls, [DEPLOYMENT])
        self.assertEqual(len(server.requests), 1)

    def test_a_deployment_that_moved_to_another_version_makes_no_call(self):
        server = FakeOpenAI()
        with self.assertRaises(boot.TextModelUnsafe):
            _summarize(server, reader=_reader(live=("gpt-5.4-mini", "2099-01-01")))
        self.assertEqual(server.requests, [])

    def test_an_unreadable_deployment_makes_no_call(self):
        server = FakeOpenAI()
        with self.assertRaises(boot.TextModelUnsafe):
            _summarize(server, reader=_reader(live=RuntimeError("ARM is down")))
        self.assertEqual(server.requests, [])

    def test_it_is_checked_again_on_every_call_not_cached(self):
        calls = []

        async def go():
            server = FakeOpenAI()
            async with httpx.AsyncClient(transport=server.transport()) as http:
                s = summarizer.OpenAISummarizer(ENDPOINT, DEPLOYMENT, http, _token, _reader(calls=calls))
                await s.summarize(TURNS)
                await s.summarize(TURNS)

        asyncio.run(go())
        self.assertEqual(len(calls), 2)


class TheEndpointIsCheckedAtConstruction(unittest.TestCase):
    def test_an_endpoint_that_is_not_https_is_refused(self):
        for bad in ("http://x.openai.azure.com/", "not a url", ""):
            with self.assertRaises(ValueError):
                summarizer.OpenAISummarizer(bad, DEPLOYMENT, None, _token, _reader())


if __name__ == "__main__":
    unittest.main()
