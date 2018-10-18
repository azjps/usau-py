"""
Load and clean player/team tournament data from play.usaultimate.org.
"""

from __future__ import print_function

from collections import OrderedDict
import logging
import os
import re
import sys

from bs4 import BeautifulSoup
import pandas as pd
import requests
from six import string_types  # py2/3 compat

_logger = logging.getLogger(__name__)

_table_cache = {}
def memoize_read_html(url, match, header):
    """Memoized wrapper around pandas.read_html"""
    global _table_cache
    key = (url, match, header)
    if key not in _table_cache:
        _table_cache[key] = pd.read_html(url, match=match, header=header)
    return _table_cache[key]


def title_name(name):
    """Capitalize first letter of each name"""
    if name.isupper():
        return name.title()
    return name  # Leave capitalizations in middle of names, like 'McCray'


class PickleSoup(object):
    """Minor helper for pickling a few pieces of a BeautifulSoup object"""

    def __init__(self, soup):
        self.attrs = dict(soup.attrs)
        self.text = soup.text


class USAUResults(object):
    """Container and helpers for accessing player statistics on USAU website"""
    BASE_URL = "http://play.usaultimate.org"

    def __init__(self, event_info, gender, year,
                 executor=None):
        assert gender in self.__class__._GENDERS
        self.event_info = event_info
        self.gender = gender
        self.year = year
        self.event_full = event_info["url"].format(y=year)
        # TODO: flesh out competition parser?
        self.competition = ("College" if "college" in self.event_info["level"]
                            else "Club")

        if "full_url" in event_info:
            self.event_url = event_info["full_url"]
        else:
            self.event_url = ("{url}/events/{evt}/schedule/"
                              "{gender}/{comp}-{gender}"
                              .format(url=self.BASE_URL,
                                      evt=self.event_full,
                                      comp=self.competition,
                                      gender=self.gender.capitalize()))

        self.event_page_soup = None
        self.roster_dfs = None
        self.match_report_dfs = None
        self.match_result_dfs = None
        self.score_progression_dfs = None
        self.data_dir = None
        self.executor = executor

    def __str__(self):
        # TODO:
        return repr(self)

    def __repr__(self):
        return ("USAUResults<{name}>"
                .format(name=self._name()))

    def _name(self):
        event = self.event_info["event"][0].replace(' ', '-')
        name = ("{year}_{level}_{event}_{gender}"
                .format(year=self.year,
                        level=self.event_info["level"],
                        event=event,
                        gender=self.gender,
                        ))
        return name

    def set_executor(self, mode, max_workers=4):
        if mode == "thread":
            from concurrent.futures import ThreadPoolExecutor
            self.executor = ThreadPoolExecutor(max_workers=max_workers)
        elif mode == "process":
            from concurrent.futures import ProcessPoolExecutor
            self.executor = ProcessPoolExecutor(max_workers=max_workers)

    def to_csvs(self, data_dir=None, encoding='utf-8'):
        """Write data to given directory in the form of csv files"""
        if data_dir is None:
            data_dir = os.path.join(os.path.dirname(
                os.path.abspath(__file__)), "data")
        assert isinstance(data_dir, string_types)

        # TODO: put in subfolders instead?
        base_path = os.path.join(os.path.expanduser(data_dir),
                                 self._name())

        self.rosters.to_csv(
            base_path + "_rosters.csv", encoding=encoding)
        self.match_reports.to_csv(
            base_path + "_match_reports.csv", encoding=encoding)
        self.match_results.to_csv(
            base_path + "_match_results.csv", encoding=encoding)
        self.score_progressions.to_csv(
            base_path + "_scores.csv", encoding=encoding)

        print("Finished writing CSVs to {data_dir}".format(data_dir=data_dir))

    def load_from_csvs(self, data_dir=None, mandatory=True, write=True):
        """Load data from offline csv files"""
        if data_dir is None:
            data_dir = os.path.join(os.path.dirname(
                os.path.abspath(__file__)), "data")
        assert isinstance(data_dir, string_types)
        base_path = os.path.join(os.path.expanduser(data_dir),
                                 self._name())

        try:
            self.roster_dfs = pd.read_csv(
                base_path + "_rosters.csv")
            self.match_report_dfs = pd.read_csv(
                base_path + "_match_reports.csv")
            self.match_result_dfs = pd.read_csv(
                base_path + "_match_results.csv")
            self.score_progression_dfs = pd.read_csv(
                base_path + "_scores.csv")
            self.data_dir = data_dir
        except IOError:
            print("Unable to open downloaded CSVs at {path}"
                  .format(path=base_path))
            if not mandatory:
                self.to_csvs(data_dir=data_dir)
                return self
            raise
        return self

    @classmethod
    def from_csvs(cls, data_dir=None, *args, **kwargs):
        """Constructor from offline csv data"""
        return (cls.from_event(*args, **kwargs)
                   .load_from_csvs(data_dir=data_dir))

    @property
    def event_soup(self):
        """BeautifulSoup-parsed HTML from tournament schedule page"""
        if self.event_page_soup is None:
            # print("Downloading from URL: {url}".format(url=self.event_url))
            _logger.info("Downloading from URL: {url}".format(
                url=self.event_url))
            # page = urllib.urlopen(self.event_url).read().decode('utf-8')
            request = requests.get(self.event_url)
            self.event_page_soup = BeautifulSoup(request.text, "html.parser")
        return self.event_page_soup

    @classmethod
    def _scrape_roster(cls, team_link, verbose=True):
        """Read overall roster statistics from given URL"""
        url = team_link.attrs["href"]
        team = team_link.text
        if verbose:
            print("Reading roster from url: {url}".format(url=url))
        name, seed = cls.split_team_seed(team)
        # Match tables containing 'Position', i.e. cutter/handler
        try:
            roster_table = cls.get_html_tables(url, match="Position")[0]
            roster_table["url"] = url
            roster_table["Team"] = name
            roster_table["Seed"] = seed
            return roster_table
        except Exception:
            _logger.exception("Unable to read HTML table for {team}: {url}"
                              .format(url=url, team=team))
            return None

    @property
    def rosters(self):
        """Scrape player contributions/statistics aggregated over tournament

        Returns:
            pd.DataFrame: Player/team statistics aggregated across tournament
        """
        if self.roster_dfs is not None:
            return self.roster_dfs

        team_links = []
        for pool in self.event_soup.findAll("div", attrs={"class": "pool"}):
            team_links += pool.findAll("a",
                                       attrs={"href": re.compile("EventTeamId")})
        # NOTE: beautifulsoup objects are not pickle-able
        team_links = [PickleSoup(l) for l in team_links]

        _logger.info("For {event} reading {n} rosters"
                     .format(event=self, n=len(team_links)))
        if self.executor is None:  # Run serially
            rosters = [self._scrape_roster(link) for link in team_links]
        else:
            rosters = list(self.executor.map(self.__class__._scrape_roster,
                                             team_links,
                                             chunksize=5))
        self.roster_dfs = pd.concat(rosters)

        # idempotent
        self.roster_dfs["Name"] = self.roster_dfs["Name"].apply(title_name)
        self.roster_dfs["UpperName"] = self.roster_dfs["Name"].str.upper()
        return self.roster_dfs

    @classmethod
    def split_team_seed(cls, text):
        """Split '(N) Team' into team name and seed"""
        name, seed = text.rsplit(" (", 1)
        seed = int(seed[:-1])  # Remove trailing parenthesis
        return name, seed

    @classmethod
    def split_total_score(cls, text):
        """Parse 'Total: N' to N"""
        assert text.startswith('Total:')
        try:
            return int(text.split()[-1])
        except ValueError:
            return 0

    @classmethod
    def clean_match_report_stats(cls, table):
        """Normalize match report column names and contents"""
        def split_no(text):
            """Parse '#N First Last' to N"""
            if text.startswith("#"):
                return int(text.split()[0][1:])
            return -1

        def split_name(text):
            """Parse '#N First Last' to First Last"""
            if text.startswith("#"):
                return text.split(" ", 1)[1]
            return text

        if all((c in table.columns for c in ("No.", "Name", "UpperName",
                                             "Gs", "As", "Ds", "Ts"))):
            # Make idempotent
            return table

        table["No."] = table["Players"].apply(split_no)
        table["Name"] = table["Players"].apply(split_name)
        table["Name"] = table["Name"].apply(title_name)
        table["UpperName"] = table["Name"].str.upper()
        # These columns are duplicated for expressiveness;
        # also df.T is already the transpose operator
        table["Gs"] = table["Goals"] = table["G"]
        table["As"] = table["Assists"] = table["A"]
        table["Ds"] = table["D"]
        table["Ts"] = table["Turns"] = table["T"]
        table.drop(["Players", "G", "A", "D", "T"], inplace=True, axis=1)
        return table

    @classmethod
    def _scrape_match(cls, url, verbose=True):
        print("Reading match report from url: {url}".format(url=url))
        # Score-line, i.e. 1-0 1-1 1-2 1-3 2-3
        scores = cls.get_html_tables(url, match="Total:")[0].T
        assert len(scores.columns) == 2
        home_team, away_team = scores.iloc[0]
        if home_team == "TBD" and away_team == "TBD":
            # See for example the consolation game b/w Cincinnati and Illinois
            # in D-I Men's 2015, which links to the following empty match report
            # http://play.usaultimate.org/teams/events/match_report/?
            # EventGameId=tu5uM3hYbU6FDLJw%2byP1b33zbjMeXu%2bbIJiyiqteRbo%3d
            _logger.warning("Empty or malformed match report: {url}"
                            .format(url=cls.BASE_URL + url))
            return
        home_name, home_seed = cls.split_team_seed(home_team)
        away_name, away_seed = cls.split_team_seed(away_team)
        home_total_score, away_total_score = scores.iloc[-1]
        home_total_score = cls.split_total_score(home_total_score)
        away_total_score = cls.split_total_score(away_total_score)

        # Cleanup score progressions
        scores.iloc[0] = 0
        scores = scores[:-1].dropna(how='all').fillna(0).astype(int)
        if scores.iloc[-1].sum() < home_total_score + away_total_score:
            if scores.iloc[-1].sum() == home_total_score + away_total_score - 1:
                # Some data entry omits the final point
                # TODO: do full consistency check for these?
                scores = scores.append({0: home_total_score,
                                        1: away_total_score}, ignore_index=True)
            else:
                error_message = ("In {url} score progression is not complete: "
                                 "final scores {score} mismatch {home}-{away}"
                                 .format(url=url,
                                         home=home_total_score,
                                         away=away_total_score,
                                         score=scores.iloc[-1].values))
                _logger.warn(error_message)
                print(error_message, file=sys.stderr)

        # To get the point winners, with 1 for score:
        # scores.diff()[1:].astype(int)
        # Adjoin context. Using lower_case column names since this
        # should just be for internal reading.
        scores.columns = ["home_score", "away_score"]
        scores["url"] = url
        scores["home_team"] = home_name
        scores["away_team"] = away_name
        scores["home_seed"] = home_seed
        scores["away_seed"] = away_seed
        # Including these two columns only for data integrity reasons:
        # on many score reports the score progressions don't match
        # the final scores!
        scores["home_final_score"] = home_total_score
        scores["away_final_score"] = away_total_score

        # "Players" search string may also pick up sidebar, unfortunately
        # Since the G D A T is in a <tr>, need to give header= explicitly.
        home_roster, away_roster = cls.get_html_tables(
            url, match="Players", header=0)[0:2]
        home_roster = cls.clean_match_report_stats(home_roster)
        away_roster = cls.clean_match_report_stats(away_roster)

        # Attach metadata for context with the players statistics
        # This can be determined by joining with the match_results table also,
        # by joining on url, but we'll offer these fields for convenience, since
        # there isn't much data to save anyway.
        home_roster["url"] = url
        away_roster["url"] = url
        home_roster["Team"] = home_name
        away_roster["Team"] = away_name
        home_roster["Seed"] = home_seed
        away_roster["Seed"] = away_seed
        home_roster["Score"] = home_total_score
        away_roster["Score"] = away_total_score
        home_roster["Opp Team"] = away_name
        away_roster["Opp Team"] = home_name
        home_roster["Opp Seed"] = away_seed
        away_roster["Opp Seed"] = home_seed
        home_roster["Opp Score"] = away_total_score
        away_roster["Opp Score"] = home_total_score

        match_results = pd.DataFrame([{
            "url": url,
            "Team": home_name,
            "Opponent": away_name,
            "Score": home_total_score,
            "Opp Score": away_total_score,
            "Seed": home_seed,
            "Opp Seed": away_seed,
            "Gs": sum(home_roster.Goals),
            "As": sum(home_roster.Assists),
            "Ds": sum(home_roster.Ds),
            "Ts": sum(home_roster.Turns),
        }, {
            "url": url,
            "Team": away_name,
            "Opponent": home_name,
            "Score": away_total_score,
            "Opp Score": home_total_score,
            "Seed": away_seed,
            "Opp Seed": home_seed,
            "Gs": sum(away_roster.Goals),
            "As": sum(away_roster.Assists),
            "Ds": sum(away_roster.Ds),
            "Ts": sum(away_roster.Turns),
        }])
        return (match_results,
                pd.concat([home_roster, away_roster]),
                scores)

    @property
    def match_reports(self):
        """Retrieve USAU match reports

        Returns:
            pd.DataFrame: Per-match breakdown of player scoring statistics. Games are
                uniquely identified by the "url" field, which is the link to the USAU
                page of the corresponding match report.
        """
        if self.match_report_dfs is not None:
            return self.match_report_dfs

        match_links = self.event_soup.findAll(
            "a", attrs={"href": re.compile("EventGameId")})

        # NOTE: sometimes scraper can pick up duplicate URLs, so make sure
        # to unique-ify the URL set.
        urls = set([link.attrs["href"] for link in match_links])
        _logger.info("For {event} reading {n} reports"
                     .format(event=self, n=len(urls)))
        if self.executor is None:
            scrapes = [self._scrape_match(url) for url in urls]
        else:
            scrapes = self.executor.map(self.__class__._scrape_match,
                                        urls,
                                        chunksize=5)

        match_results = []  # Scores, broken down by player contributions
        match_reports = []  # Just the final scores
        score_progressions = []
        for scraped in scrapes:
            if scraped is None:
                continue
            match_result, match_report, score_progression = scraped
            match_results.append(match_result)
            match_reports.append(match_report)
            score_progressions.append(score_progression)

        self.match_report_dfs = pd.concat(match_reports)
        self.match_result_dfs = pd.concat(match_results)
        self.score_progression_dfs = pd.concat(score_progressions)
        return self.match_report_dfs

    @property
    def match_results(self):
        """Returns pd.DataFrame of final score for each match"""
        _ = self.match_reports
        return self.match_result_dfs

    @property
    def score_progressions(self):
        """Returns pd.DataFrame of point-per-point scores for each match"""
        _ = self.match_reports
        return self.score_progression_dfs

    @property
    def missing_tallies(self):
        """Returns pd.DataFrame of matches where goals/assists do not match final result"""
        results = self.match_results
        return results[(results.Gs < results.Score) |
                       (results.As < results.Score)]

    @property
    def team_results(self):
        """Returns pd.DataFrame of teams to games played, won, etc"""
        matches = self.match_results
        matches["is_win"] = matches["Score"] > matches["Opp Score"]
        gb = matches.groupby("Team")
        return pd.DataFrame(OrderedDict([("Games Played", gb["Score"].count()),
                                         ("Games Won", gb["is_win"].sum()),
                                         ("Points Scored", gb["Score"].sum()),
                                         ("Points Lost", gb["Opp Score"].sum()),
                                         ("Ds", gb["Ds"].sum()),
                                         ("Ts", gb["Ts"].sum()),
                                         ]))

    @classmethod
    def get_html_tables(cls, url, match, header=None):
        """Helper method for fetching a HTML table, memoized"""
        if not url.startswith(cls.BASE_URL):
            url = cls.BASE_URL + url
        return memoize_read_html(url, match=match, header=header)

    @classmethod
    def from_url(cls, url, level=None, event=None, **kwargs):
        """Convenience method for loading directly from tournament page URL

        This is not advised; prefer to use :func:`from_event` instead.
        """
        # Try to deduce metadata from url
        tokens = url.split('/')
        # Expecting URL of form:
        # "{url}/events/{evt}/schedule/{gender}/{comp}-{gender}"
        assert tokens[-3] == "schedule"
        if tokens[-2].lower() not in cls._GENDERS:
            raise ValueError("Unable to deduce gender from url: {url}"
                             .format(url=url))
        event_full = tokens[-4]
        year = re.match(r"\d{4}", event_full).group(0)
        competition, gender = tokens[-1].split("-")
        if level is None:
          level = "college" if "college" in competition.lower() else "club"
        assert gender == tokens[-2]
        return cls({"full_url": url,
                    "url": event_full,
                    "event": event or event_full,  # TODO: parse event_full?
                    "level": level,
                   }, gender=gender, year=year)

    @classmethod
    def from_nationals(cls, level, year, gender):
        """Refer to :func:`from_event`"""
        if level not in cls._NATIONALS_LEVELS:
            raise ValueError("Unrecognized competition level {level}, choices: {choices}"
                             .format(level=level, choices=_NATIONALS_LEVELS))
        return cls.from_event(level=level, year=year, gender=gender,
                              event="nationals")

    @classmethod
    def from_event(cls, level, year, gender, event="nationals",
                   **kwargs):
        """Load competition results from human-readable string inputs

        Args:
            level (str): One of "club", "d1college", "d3college"
            year (int | str): 20xx
            gender (str): One of "Men", "Mixed", "Women"
        """
        year = int(year)
        level = level.lower()
        event = event.lower().replace('-', ' ').replace('_', ' ')
        gender = gender.lower()
        if gender not in cls._GENDERS:
            raise ValueError("Unknown gender input: {gender}"
                             .format(gender=gender))
        if level.lower() not in cls._NATIONALS_LEVELS:
            raise ValueError("Unknown competition level: {level}; "
                             "expected one of {choices}"
                             .format(level=level,
                                     choices=cls._NATIONALS_LEVELS))

        event_info_found = None
        for event_info in cls._EVENT_TO_URL:
            assert isinstance(event_info["event"], list)
            start_year = event_info.get("start_year", None)
            end_year = event_info.get("end_year", None)
            if start_year is not None and year < start_year:
                continue
            if end_year is not None and year > end_year:
                continue

            if (level == event_info["level"] and
                    event in event_info["event"]):
                event_info_found = event_info
                break

        if event_info_found is None:
            raise ValueError("Unable to find USAU event for filter: "
                             "level {level} year {year} event {event}"
                             .format(level=level, year=year, event=event))

        return cls(event_info, gender=gender, year=year, **kwargs)

    # Class members
    _NATIONALS_LEVELS = ["club", "d1college", "d3college"]
    _GENDERS = ["men", "mixed", "women"]
    # below, start year and end year are inclusive!
    _EVENT_TO_URL = \
        [
            {
                "level": "club",
                "event": ["nationals", "nats"],
                "start_year": 2014,
                "end_year": 2014,
                "url": "USA-Ultimate-National-Championships",
            },
            {
                "level": "club",
                "event": ["nationals", "nats"],
                "start_year": 2015,
                "url": "USA-Ultimate-National-Championships-{y}",
            },
            {
                "level": "d1college",
                "event": ["nationals", "nats"],
                "start_year": 2018,
                "url": "USA-Ultimate-D-I-College-Championships-{y}",
            },
            {
                "level": "d1college",
                "event": ["nationals", "nats"],
                "start_year": 2017,
                "end_year": 2017,
                "url": "{y}-USA-Ultimate-College-Championships",
            },
            {
                "level": "d1college",
                "event": ["nationals", "nats"],
                "start_year": 2015,
                "end_year": 2016,
                "url": "USA-Ultimate-D-I-College-Championships-{y}",
            },
            {
                "level": "d1college",
                "event": ["nationals", "nats"],
                "start_year": 2014,
                "end_year": 2014,
                "url": "USA-Ultimate-D-I-College-Championships",
            },
            {
                "level": "d3college",
                "event": ["nationals", "nats"],
                "start_year": 2015,
                "url": "USA-Ultimate-D-III-College-Championships-{y}",
            },
            {
                "level": "d3college",
                "event": ["nationals", "nats"],
                "start_year": 2014,
                "end_year": 2014,
                "url": "USA-Ultimate-D-III-College-Championships",
            },
            {
                "level": "club",
                "event": ["us open"],
                "start_year": 2017,
                "url": "{y}-US-Open-Club-Championships",
            },
            {
                "level": "club",
                "event": ["us open"],
                "start_year": 2015,
                "end_year": 2016,
                "url": "US-Open-Ultimate-Championships-{y}",
            },
            {
                "level": "club",
                "event": ["tct pro", "pro flight", "pro champs"],
                "start_year": 2017,
                "url": "TCT-Pro-Championships-{y}",
            },
            {
                "level": "club",
                "event": ["tct pro", "pro flight", "pro champs"],
                "start_year": 2016,
                "end_year": 2016,
                "url": "TCT-Pro-Flight-Finale-{y}",
            },
            {
                "level": "club",
                "event": ["tct pro", "pro flight", "pro champs"],
                "start_year": 2015,
                "end_year": 2015,
                "url": "TCT-Pro-Flight-Finale",
            },
            {
                "level": "club",
                "event": ["pro elite"],
                # competition started earlier, but stats not tracked
                "start_year": 2018,
                "url": "TCT-Pro-Elite-Challenge-{y}",
            },
            {
                "level": "club",
                "event": ["tct select", "select flight"],
                "start_year": 2016,
                "url": "TCT-Select-Flight-Invite-{y}",
            },
        ]

# For tab-completion convenience
for level in ("d1college", "d3college", "club"):
    for gender in ("Men", "Women", "Mixed"):
        if gender == "Mixed" and level != "club":
            continue
        for year in range(2015, 2018):
            key = ("{lvl}_nats_{gender}_{year}"
                   .format(lvl=level, gender=gender.lower(), year=year))
            globals()[key] = USAUResults.from_event(level=level,
                                                    gender=gender,
                                                    year=year,
                                                    event="nationals")
