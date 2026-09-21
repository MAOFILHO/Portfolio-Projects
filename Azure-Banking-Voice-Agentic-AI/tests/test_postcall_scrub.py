"""Phase 8 -- the deterministic number scrub that runs on the redactor's output.

docs/phase8/research-postcall-adapters.md, Q1f: Language does not promise to catch a bare digit
string ("without context, a ten-digit number is just a number"), so the redactor does not trust it
alone. Anything that looks like an account, card or phone number is masked no matter what Language
said -- over-masking a date is fine, leaking an account number is not.
"""
import random
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

    def test_any_common_separator_between_the_groups_is_masked_whole(self):
        # Gate review 2: a slash, comma, en dash, underscore, middle dot, non-breaking space or a
        # line break between the groups left the first two groups behind.
        for sep in ("/", ",", "\u2013", "\u2014", "_", "\u00b7", "\u00a0", "\n", ". ", " - "):
            number = f"416{sep}555{sep}0199"
            with self.subTest(sep=sep):
                scrubbed = scrub_numbers(f"my number is {number} thanks")
                self.assertEqual(scrubbed, f"my number is {MASK} thanks")

    def test_a_slash_between_area_code_and_local_number(self):
        self.assertEqual(scrub_numbers("call 416/555-0199 now"), f"call {MASK} now")

    def test_a_space_inside_the_last_group(self):
        for number in ("(416) 555-01 99", "416 555 01 99", "416-555-0 199"):
            with self.subTest(number=number):
                self.assertEqual(scrub_numbers(f"call {number} now"), f"call {MASK} now")

    def test_a_longer_run_is_masked_whole_not_split(self):
        # Gate review 2: the phone pattern used to take ten digits out of a longer run and leave
        # the tail, a regression from the plain digit-run rule.
        for run in ("41655501991", "416555019912", "4165550199123", "1234567890123", "416-555-0199-123"):
            with self.subTest(run=run):
                self.assertEqual(scrub_numbers(f"id {run} end"), f"id {MASK} end")

    def test_a_separator_of_several_characters_is_masked_whole(self):
        # Gate review 3: the old pattern masked `416 .. 555 .. 0199`; the first rewrite capped the
        # gap at three characters and left the area code and exchange for anything longer.
        for sep in (" .. ", " ... ", " - - ", " -- ", " / / ", " \u2013 \u2013 ", ") - (", "  ", "\n\n", " .  . "):
            number = f"416{sep}555{sep}0199"
            with self.subTest(sep=sep):
                self.assertEqual(scrub_numbers(f"call {number} now"), f"call {MASK} now")

    def test_no_shape_the_generator_can_build_leaves_a_digit(self):
        # The fuzz behind the claim "no leak", kept so the claim can be rerun: 10-16 digits, each
        # gap 0-8 characters drawn from punctuation and whitespace, never a letter or a dollar sign.
        pieces = list(" .-/,_()+\u2013\u2014\u00b7\u00a0\n")
        rng = random.Random(1)
        for _ in range(3000):
            digits = rng.randint(10, 16)
            text = ""
            for i in range(digits):
                text += str(rng.randint(0, 9))
                if i < digits - 1:
                    text += "".join(rng.choice(pieces) for _ in range(rng.randint(0, 8)))
            scrubbed = scrub_numbers(f"my number is {text} thanks")
            self.assertFalse(any(c.isdigit() for c in scrubbed), (text, scrubbed))

    def test_a_gap_of_letters_or_a_dollar_sign_still_separates_numbers(self):
        for text in ("1900 and 1000", "$1,900 and $1,000 and $3.25", "you owe $12.50, $3.25 and $8.75"):
            with self.subTest(text=text):
                self.assertNotEqual(scrub_numbers(text), MASK)
                self.assertNotIn(MASK + MASK, scrub_numbers(text))

    def test_a_dotted_seven_digit_local_number_is_masked(self):
        self.assertFalse(any(c.isdigit() for c in scrub_numbers("call 555.0199 now")))

    def test_the_words_around_it_survive(self):
        self.assertEqual(scrub_numbers("call 416.555.0199 now"), f"call {MASK} now")

    def test_a_local_number_with_a_slash_or_en_dash_is_masked(self):
        for number in ("555/0199", "555\u20130199", "555\u00a00199"):
            with self.subTest(number=number):
                self.assertEqual(scrub_numbers(f"call {number} now"), f"call {MASK} now")

    def test_amounts_and_versions_still_survive(self):
        for text in (
            "You have $12.50 today",
            "rate is 4.25 percent",
            "on 3.5 accounts",
            "page 2.1",
            "you owe $12.50, $3.25 and $8.75",
            "a fee of $1,234.56",
        ):
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
