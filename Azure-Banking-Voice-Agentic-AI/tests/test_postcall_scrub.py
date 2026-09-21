"""Phase 8 -- the deterministic number scrub that runs on the redactor's output.

docs/phase8/research-postcall-adapters.md, Q1f: Language does not promise to catch a bare digit
string ("without context, a ten-digit number is just a number"), so the redactor does not trust it
alone. Anything that looks like an account, card or phone number is masked no matter what Language
said -- over-masking a date is fine, leaking an account number is not.
"""
import unittest

from azbank_voice_agent.postcall.scrub import MASK, scrub_numbers


class DigitRunsAreMasked(unittest.TestCase):
    def test_a_bare_account_number(self):
        self.assertEqual(scrub_numbers("Account 1234567890 is open."), f"Account {MASK} is open.")

    def test_four_digits_is_the_smallest_run_masked(self):
        self.assertEqual(scrub_numbers("ending 4821"), f"ending {MASK}")
        self.assertEqual(scrub_numbers("apartment 482"), "apartment 482")

    def test_groups_split_by_spaces_or_hyphens_are_one_run(self):
        self.assertEqual(scrub_numbers("card 4111 1111 1111 1111 ok"), f"card {MASK} ok")
        self.assertEqual(scrub_numbers("call 416-555-0123 now"), f"call {MASK} now")

    def test_two_separate_runs_are_both_masked(self):
        self.assertEqual(scrub_numbers("from 11112222 to 33334444"), f"from {MASK} to {MASK}")

    def test_short_numbers_and_amounts_survive(self):
        text = "You have $12.50 and 3 accounts, 15 transactions."
        self.assertEqual(scrub_numbers(text), text)


class AFormattedPhoneNumberIsMaskedWhole(unittest.TestCase):
    """B2 covers the caller's phone number. The code's own comment says a formatted number leaks
    nothing -- the /code-review gate found it left the area code (parentheses) or six digits (dots)."""

    def test_no_shape_leaves_any_digit_behind(self):
        for number in (
            "(416) 555-0199",
            "(416)555-0199",
            "416.555.0199",
            "416 555 0199",
            "416-555-0199",
            "4165550199",
            "+1 416 555 0199",
            "+1 (416) 555-0199",
            "1-416-555-0199",
            "+1.416.555.0199",
        ):
            with self.subTest(number=number):
                scrubbed = scrub_numbers(f"my number is {number} thanks")
                self.assertFalse(any(c.isdigit() for c in scrubbed), scrubbed)

    def test_a_dotted_seven_digit_local_number_is_masked(self):
        self.assertFalse(any(c.isdigit() for c in scrub_numbers("call 555.0199 now")))

    def test_the_words_around_it_survive(self):
        self.assertEqual(scrub_numbers("call 416.555.0199 now"), f"call {MASK} now")

    def test_amounts_and_versions_still_survive(self):
        for text in ("You have $12.50 today", "rate is 4.25 percent", "on 3.5 accounts", "page 2.1"):
            with self.subTest(text=text):
                self.assertEqual(scrub_numbers(text), text)


class SpokenDigitsAreMaskedToo(unittest.TestCase):
    """A voice transcript often spells numbers out."""

    def test_four_spoken_digits(self):
        self.assertEqual(scrub_numbers("It is four five six seven."), f"It is {MASK}.")

    def test_spoken_digits_with_commas_hyphens_and_oh(self):
        self.assertEqual(scrub_numbers("nine, oh, two-one, six"), MASK)

    def test_case_is_ignored(self):
        self.assertEqual(scrub_numbers("One Two Three Four"), MASK)

    def test_three_spoken_digits_survive(self):
        self.assertEqual(scrub_numbers("one two three"), "one two three")

    def test_a_number_word_inside_another_word_is_not_a_digit(self):
        text = "someone phoned one zero fine"
        self.assertEqual(scrub_numbers(text), text)


class ItNeverFailsOpen(unittest.TestCase):
    def test_empty_text_is_empty(self):
        self.assertEqual(scrub_numbers(""), "")

    def test_it_is_idempotent(self):
        once = scrub_numbers("acct 1234567890 and four five six seven")
        self.assertEqual(scrub_numbers(once), once)

    def test_the_mask_itself_contains_no_digits(self):
        self.assertFalse(any(c.isdigit() for c in MASK))


if __name__ == "__main__":
    unittest.main()
