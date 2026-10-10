
import unittest
from conversation import expand_followup


class TestConversation(unittest.TestCase):

    def test_price_followup(self):
        result = expand_followup(
            "What's its price?",
            "Dolo 650 Tablet"
        )
        self.assertEqual(
            result,
            "What is the price of Dolo 650 Tablet?"
        )

    def test_composition_followup(self):
        result = expand_followup(
            "What is its composition?",
            "Dolo 650 Tablet"
        )
        self.assertEqual(
            result,
            "What is the composition of Dolo 650 Tablet?"
        )

    def test_no_previous_medicine(self):
        result = expand_followup(
            "What's its price?",
            None
        )
        self.assertEqual(result, "What's its price?")

    def test_safety_question_unchanged(self):
        result = expand_followup(
            "Can I take this medicine?",
            "Dolo 650 Tablet"
        )
        self.assertEqual(
            result,
            "Can I take this medicine?"
        )


if __name__ == "__main__":
    unittest.main()
