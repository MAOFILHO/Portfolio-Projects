"""Phase 8 -- the real redactor: Azure AI Language's Conversation PII job API, over HTTP.

Every shape here is derived from docs/phase8/research-postcall-adapters.md (Q1b), which cites the
`2024-11-01` OpenAPI spec. No live call has been made: the wire format is pinned by these fixtures and
proven against the real service by the first live call. The server is a scripted `httpx.MockTransport`.

The properties that matter, in order: nothing unredacted comes back (ADR-007), the bearer token only
ever goes to the Language host, and any surprise in the response is a raise -- the pipeline turns a
raise into "no transcript", never into a fallback.
"""
import asyncio
import json
import unittest

import httpx
from azbank_voice_agent.postcall import language, scrub

ENDPOINT = "https://lang-test.cognitiveservices.azure.com/"
JOBS_PATH = "/language/analyze-conversations/jobs"
POLL_URL = "https://lang-test.cognitiveservices.azure.com/language/analyze-conversation/jobs/job-42?api-version=2024-11-01"


async def _token():
    return "test-token"


class FakeLanguage:
    """Scripts the Language service. `mask` says which substrings its 'model' redacts."""

    def __init__(self, mask=("SECRET",), statuses=("succeeded",), shuffle=False, mutate=None,
                 submit_status=202, location=POLL_URL):
        self.mask = mask
        self.statuses = list(statuses)
        self.shuffle = shuffle
        self.mutate = mutate
        self.submit_status = submit_status
        self.location = location
        self.requests = []
        self.submitted = None

    def transport(self):
        return httpx.MockTransport(self._handle)

    def _redact(self, text):
        for term in self.mask:
            text = text.replace(term, "*" * len(term))
        return text

    def _state(self, status):
        items = [
            {"id": item["id"], "redactedContent": {"text": self._redact(item["text"])}, "entities": []}
            for item in self.submitted["analysisInput"]["conversations"][0]["conversationItems"]
        ]
        if self.shuffle:
            items.reverse()
        conversation_id = self.submitted["analysisInput"]["conversations"][0]["id"]
        state = {
            "jobId": "job-42", "status": status, "errors": [],
            "tasks": {"completed": 1, "failed": 0, "inProgress": 0, "total": 1, "items": [{
                "kind": "conversationalPIIResults", "taskName": "pii", "status": "succeeded",
                "results": {"errors": [], "modelVersion": "x", "conversations": [
                    {"id": conversation_id, "warnings": [], "conversationItems": items}
                ]},
            }]},
        }
        if self.mutate:
            self.mutate(state)
        return state

    def _handle(self, request):
        self.requests.append(request)
        if request.method == "POST":
            self.submitted = json.loads(request.content)
            headers = {"Operation-Location": self.location} if self.location else {}
            return httpx.Response(self.submit_status, headers=headers)
        status = self.statuses.pop(0) if len(self.statuses) > 1 else self.statuses[0]
        return httpx.Response(200, json=self._state(status))


def _redact(turns, server=None, **kwargs):
    server = server or FakeLanguage()

    async def go():
        async with httpx.AsyncClient(transport=server.transport()) as http:
            redactor = language.LanguagePIIRedactor(
                ENDPOINT, http, _token, poll_interval_seconds=0, **kwargs
            )
            return await redactor.redact(turns)

    return asyncio.run(go()), server


class TheRequestIsWhatTheSpecSays(unittest.TestCase):
    def test_one_post_to_the_jobs_path_with_the_ga_api_version_and_a_bearer_token(self):
        _, server = _redact(["Hello."])
        post = server.requests[0]
        self.assertEqual(post.method, "POST")
        self.assertEqual(post.url.host, "lang-test.cognitiveservices.azure.com")
        self.assertEqual(post.url.path, JOBS_PATH)
        self.assertEqual(post.url.params["api-version"], "2024-11-01")
        self.assertEqual(post.headers["Authorization"], "Bearer test-token")

    def test_the_body_is_one_text_conversation_of_agent_turns(self):
        _redact(["Hello.", "How can I help?"], server := FakeLanguage())
        body = server.submitted
        [conversation] = body["analysisInput"]["conversations"]
        self.assertEqual(conversation["language"], "en")
        self.assertEqual(conversation["modality"], "text")
        self.assertTrue(conversation["id"])
        self.assertEqual(
            [(i["id"], i["participantId"], i["role"], i["text"]) for i in conversation["conversationItems"]],
            [("0", "agent", "agent", "Hello."), ("1", "agent", "agent", "How can I help?")],
        )

    def test_the_task_is_conversational_pii_with_service_logging_off(self):
        _redact(["Hello."], server := FakeLanguage())
        [task] = server.submitted["tasks"]
        self.assertEqual(task["kind"], "ConversationalPIITask")
        self.assertIs(task["parameters"]["loggingOptOut"], True)
        self.assertEqual(task["parameters"]["piiCategories"], ["All"])

    def test_the_poll_is_a_get_on_the_operation_location_verbatim(self):
        _, server = _redact(["Hello."])
        get = server.requests[1]
        self.assertEqual(get.method, "GET")
        self.assertEqual(str(get.url), POLL_URL)
        self.assertEqual(get.headers["Authorization"], "Bearer test-token")


class WhatComesBackIsRedactedAndInOrder(unittest.TestCase):
    def test_the_service_masks_are_returned_in_the_original_order(self):
        result, _ = _redact(["Your SECRET is set.", "Anything else?"])
        self.assertEqual(result, ["Your ****** is set.", "Anything else?"])

    def test_items_are_matched_by_id_not_by_position(self):
        result, _ = _redact(["first SECRET", "second", "third"], FakeLanguage(shuffle=True))
        self.assertEqual(result, ["first ******", "second", "third"])

    def test_it_polls_until_the_job_finishes(self):
        server = FakeLanguage(statuses=("notStarted", "running", "running", "succeeded"))
        result, server = _redact(["Hello."], server)
        self.assertEqual(result, ["Hello."])
        self.assertEqual(len(server.requests), 5)  # one POST, four polls

    def test_digits_the_service_left_behind_are_masked_afterwards(self):
        result, _ = _redact(["Your account is 1234567890.", "one two three four"])
        self.assertEqual(result, [f"Your account is {scrub.MASK}.", scrub.MASK])

    def test_empty_turns_are_not_sent_and_come_back_empty_in_place(self):
        result, server = _redact(["Hello SECRET", "", "  ", "Bye"])
        self.assertEqual(result, ["Hello ******", "", "", "Bye"])
        items = server.submitted["analysisInput"]["conversations"][0]["conversationItems"]
        self.assertEqual([i["text"] for i in items], ["Hello SECRET", "Bye"])

    def test_nothing_to_redact_means_no_request_at_all(self):
        result, server = _redact(["", " "])
        self.assertEqual(result, ["", ""])
        self.assertEqual(server.requests, [])


class AnySurpriseIsARaiseNeverAnUnredactedReturn(unittest.TestCase):
    def _assert_raises(self, server, turns=("Hello SECRET",)):
        with self.assertRaises(Exception):  # noqa: B017 -- the contract is "raises", not a type
            _redact(list(turns), server)

    def test_a_submit_the_service_rejects(self):
        for status in (400, 401, 403, 429, 500):
            self._assert_raises(FakeLanguage(submit_status=status, location=None))

    def test_a_submit_with_no_operation_location(self):
        self._assert_raises(FakeLanguage(location=None))

    def test_a_job_that_fails_cancels_or_only_partly_completes(self):
        for status in ("failed", "cancelled", "partiallyCompleted"):
            self._assert_raises(FakeLanguage(statuses=(status,)))

    def test_a_job_level_error(self):
        self._assert_raises(FakeLanguage(mutate=lambda s: s.update(errors=[{"code": "InternalServerError"}])))

    def test_a_conversation_level_error(self):
        def mutate(state):
            state["tasks"]["items"][0]["results"]["errors"] = [{"id": "x", "error": {"code": "InvalidDocument"}}]
        self._assert_raises(FakeLanguage(mutate=mutate))

    def test_a_task_that_did_not_succeed(self):
        def mutate(state):
            state["tasks"]["items"][0]["status"] = "failed"
        self._assert_raises(FakeLanguage(mutate=mutate))

    def test_no_task_results_at_all(self):
        self._assert_raises(FakeLanguage(mutate=lambda s: s["tasks"].update(items=[])))

    def test_an_item_missing_from_the_results(self):
        def mutate(state):
            state["tasks"]["items"][0]["results"]["conversations"][0]["conversationItems"].pop()
        self._assert_raises(FakeLanguage(mutate=mutate), turns=("a SECRET", "b"))

    def test_an_item_returned_twice(self):
        def mutate(state):
            items = state["tasks"]["items"][0]["results"]["conversations"][0]["conversationItems"]
            items.append(dict(items[0]))
        self._assert_raises(FakeLanguage(mutate=mutate))

    def test_an_item_that_was_never_submitted(self):
        def mutate(state):
            items = state["tasks"]["items"][0]["results"]["conversations"][0]["conversationItems"]
            items.append({"id": "99", "redactedContent": {"text": "x"}})
        self._assert_raises(FakeLanguage(mutate=mutate))

    def test_a_conversation_the_request_did_not_name(self):
        def mutate(state):
            state["tasks"]["items"][0]["results"]["conversations"][0]["id"] = "someone-else"
        self._assert_raises(FakeLanguage(mutate=mutate))

    def test_an_item_with_no_redacted_text(self):
        for bad in ({}, {"redactedContent": {}}, {"redactedContent": {"text": None}},
                    {"redactedContent": {"text": 7}}, {"redactedContent": {"lexical": "x"}}):
            def mutate(state, bad=bad):
                item = state["tasks"]["items"][0]["results"]["conversations"][0]["conversationItems"][0]
                item.pop("redactedContent", None)
                item.update(bad)
            self._assert_raises(FakeLanguage(mutate=mutate))

    def test_a_turn_longer_than_the_documented_item_limit_is_refused_without_a_call(self):
        server = FakeLanguage()
        with self.assertRaises(ValueError):
            _redact(["x" * 1001], server)
        self.assertEqual(server.requests, [])


class TheBearerTokenOnlyEverGoesToTheLanguageHost(unittest.TestCase):
    def test_an_operation_location_on_another_host_is_refused_and_never_called(self):
        server = FakeLanguage(location="https://evil.example.com/steal?api-version=2024-11-01")
        with self.assertRaises(Exception):  # noqa: B017
            _redact(["Hello."], server)
        self.assertEqual([r.method for r in server.requests], ["POST"])

    def test_a_plain_http_operation_location_is_refused(self):
        server = FakeLanguage(location=POLL_URL.replace("https://", "http://"))
        with self.assertRaises(Exception):  # noqa: B017
            _redact(["Hello."], server)
        self.assertEqual([r.method for r in server.requests], ["POST"])


class TheEndpointIsCheckedAtConstruction(unittest.TestCase):
    def test_an_endpoint_that_is_not_https_is_refused(self):
        with self.assertRaises(ValueError):
            language.LanguagePIIRedactor("http://x.example.com/", None, _token)
        with self.assertRaises(ValueError):
            language.LanguagePIIRedactor("Endpoint=sb://x;Key=y", None, _token)


if __name__ == "__main__":
    unittest.main()
