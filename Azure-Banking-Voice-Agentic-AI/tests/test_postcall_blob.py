"""Phase 8 ticket 3 -- the real transcript store, driven with an injected container client.

No Azure and no SDK: the container client is a stand-in, so what is proved here is what this module
decides -- the blob's name, its content, that it never overwrites -- and not what Azure does. The
SDK's own surface is unverified until the live call, the same standing `TableStorageCallRecordStore`
had until its first real deploy.
"""
import asyncio
import json
import unittest

from azbank_voice_agent.postcall.blob import TRANSCRIPT_CONTAINER, BlobTranscriptStore


class _FakeContainer:
    def __init__(self, fail_with=None):
        self.fail_with = fail_with
        self.uploads = []
        self.closed = False

    async def upload_blob(self, name, data, overwrite=False):
        if self.fail_with is not None:
            raise self.fail_with
        self.uploads.append((name, data, overwrite))

    async def close(self):
        self.closed = True


class TheStoreWritesOneImmutableJsonBlobPerCall(unittest.TestCase):
    def test_the_blob_is_named_for_the_call_and_holds_the_turns(self):
        container = _FakeContainer()
        name = asyncio.run(BlobTranscriptStore(container).write("corr-1", ["Hi.", "Bye."]))
        self.assertEqual(name, "corr-1.json")
        [(uploaded_name, data, _)] = container.uploads
        self.assertEqual(uploaded_name, "corr-1.json")
        self.assertEqual(json.loads(data), {"agent_turns": ["Hi.", "Bye."]})

    def test_it_never_overwrites_an_existing_transcript(self):
        container = _FakeContainer()
        asyncio.run(BlobTranscriptStore(container).write("corr-1", ["Hi."]))
        self.assertIs(container.uploads[0][2], False)

    def test_the_blob_says_whose_words_these_are(self):
        # D14: agent speech only -- the record must not read as a two-sided conversation.
        container = _FakeContainer()
        asyncio.run(BlobTranscriptStore(container).write("corr-1", ["Hi."]))
        self.assertIn("agent_turns", json.loads(container.uploads[0][1]))

    def test_a_failed_upload_propagates_for_the_pipeline_to_record(self):
        container = _FakeContainer(fail_with=RuntimeError("storage down"))
        with self.assertRaises(RuntimeError):
            asyncio.run(BlobTranscriptStore(container).write("corr-1", ["Hi."]))

    def test_a_correlation_id_that_could_escape_the_container_is_refused(self):
        store = BlobTranscriptStore(_FakeContainer())
        for bad in ("../x", "a/b", "", "a\\b", "a#b", "a?b", "a b", "a\nb"):
            with self.assertRaises(ValueError, msg=bad):
                asyncio.run(store.write(bad, ["Hi."]))

    def test_closing_the_store_closes_the_client(self):
        container = _FakeContainer()
        asyncio.run(BlobTranscriptStore(container).aclose())
        self.assertTrue(container.closed)

    def test_the_container_has_a_fixed_name(self):
        self.assertEqual(TRANSCRIPT_CONTAINER, "transcripts")


if __name__ == "__main__":
    unittest.main()
