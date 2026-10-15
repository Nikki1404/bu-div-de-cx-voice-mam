import unittest

from profiling.age.service import age_from_gender_age, format_age_result
from profiling.config import AGE_LABELS, GENDER_AGE_LABELS
from profiling.gender.service import format_gender_result, gender_from_gender_age


class AgeGenderServiceTests(unittest.TestCase):
    def test_age_result_picks_most_likely_group_and_bucket(self):
        probs = dict.fromkeys(AGE_LABELS, 0.05) | {"thirties": 0.75}
        result = format_age_result({"age": probs})
        self.assertEqual(result["age_group"], "thirties")
        self.assertEqual(result["age_bucket"], "30-40")
        self.assertEqual(result["age_confidence"], 0.75)
        self.assertEqual(list(result["age_probabilities"]), AGE_LABELS)

    def test_age_buckets_cover_edges(self):
        teens = format_age_result({"age": dict.fromkeys(AGE_LABELS, 0.0) | {"teens": 1.0}})
        sixties = format_age_result({"age": dict.fromkeys(AGE_LABELS, 0.0) | {"sixties": 1.0}})
        self.assertEqual(teens["age_bucket"], "Under 20")
        self.assertEqual(sixties["age_bucket"], "60+")

    def test_gender_prediction_formats_class_and_probabilities(self):
        result = format_gender_result({"gender": {"female": 0.8, "male": 0.2}})
        self.assertEqual(result["gender"], "Female")
        self.assertEqual(result["gender_confidence"], 0.8)
        self.assertEqual(result["gender_probabilities"], {"female": 0.8, "male": 0.2})

    def test_gender_age_head_marginalises_to_age_and_gender(self):
        joint = dict.fromkeys(GENDER_AGE_LABELS, 0.0) | {"male-twenties": 0.6, "female-twenties": 0.1, "male-fifties": 0.3}
        age = age_from_gender_age(joint)
        gender = gender_from_gender_age(joint)
        self.assertAlmostEqual(age["twenties"], 0.7)
        self.assertAlmostEqual(age["fifties"], 0.3)
        self.assertAlmostEqual(gender["male"], 0.9)
        self.assertAlmostEqual(gender["female"], 0.1)

    def test_gender_age_labels_match_training_encoder(self):
        self.assertEqual(GENDER_AGE_LABELS[0], "female-teens")
        self.assertEqual(GENDER_AGE_LABELS[5], "female-sixties")
        self.assertEqual(GENDER_AGE_LABELS[6], "male-teens")
        self.assertEqual(GENDER_AGE_LABELS[11], "male-sixties")


if __name__ == "__main__":
    unittest.main()
