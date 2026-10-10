
import unittest

from prescription_guard import (
    check_query,
    check_medicine,
    MANDATED_PROMPT,
)


class TestPrescriptionGuard(unittest.TestCase):

    def test_restricted_queries(self):
        queries = [
            "What is Augmentin 625 Duo?",
            "Find cheaper Augmentin alternatives",
            "Tell me about Alprazolam 0.5mg",
            "What is azithromycin?",
            "Compare Clavam 625 prices",
        ]

        for q in queries:
            with self.subTest(q=q):
                self.assertEqual(
                    check_query(q),
                    MANDATED_PROMPT
                )

    def test_restricted_composition(self):
        medicine = {
            "name": "Example Antibiotic",
            "short_composition1": "Amoxycillin (500mg)",
            "short_composition2": "Clavulanic Acid (125mg)",
        }

        self.assertEqual(
            check_medicine(medicine),
            MANDATED_PROMPT
        )

    def test_unrestricted_examples(self):
        queries = [
            "What is Dolo 650 Tablet?",
            "What is the price of Crocin?",
            "Compare paracetamol 650mg products",
        ]

        for q in queries:
            with self.subTest(q=q):
                self.assertIsNone(check_query(q))


if __name__ == "__main__":
    unittest.main()
