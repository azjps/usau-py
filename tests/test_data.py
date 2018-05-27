import unittest

from usau import reports

class TestCollegeNationalsData(unittest.TestCase):
    def test_csv_data_source(self):
        # Quick data presence test
        reports.d1_college_nats_men_2015.load_from_csvs()
        assert not reports.d1_college_nats_men_2015.rosters.empty
        reports.d1_college_nats_women_2015.load_from_csvs()
        assert not reports.d1_college_nats_women_2015.rosters.empty
        reports.d1_college_nats_men_2016.load_from_csvs()
        assert not reports.d1_college_nats_men_2016.rosters.empty
        reports.d1_college_nats_women_2016.load_from_csvs()
        assert not reports.d1_college_nats_women_2016.rosters.empty

if __name__ == "__main__":
    unittest.main()
