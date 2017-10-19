"""
Load and clean player/team tournament data from play.usaultimate.org.
"""

from __future__ import print_function

from collections import OrderedDict
import os
import re
import urllib

from bs4 import BeautifulSoup
import pandas as pd

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

class USAUResults(object):
  """Container and helpers for accessing player statistics on USAU website"""
  BASE_URL = "http://play.usaultimate.org"

  def __init__(self, event, gender, competition="College"):
    assert isinstance(event, basestring) and isinstance(gender, basestring)
    self.event = event
    self.gender = gender
    self.competition = competition

    self.event_url = self.BASE_URL + ("/events/{evt}/schedule/{gender}/{comp}-{gender}"
                                      .format(evt=event, comp=competition, gender=gender))
    self.event_page_soup = None
    self.roster_dfs = None
    self.match_report_dfs = None
    self.match_result_dfs = None
    self.score_progression_dfs = None

  def to_csvs(self, data_dir=None, encoding='utf-8'):
    """Write data to given directory in the form of csv files"""
    if data_dir is None:
      data_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
    assert isinstance(data_dir, basestring)
    base_path = os.path.join(os.path.expanduser(data_dir), self.event + "-" + self.gender)

    self.rosters.to_csv(base_path + "-Rosters.csv", encoding=encoding)
    self.match_reports.to_csv(base_path + "-Match-Reports.csv", encoding=encoding)
    self.match_results.to_csv(base_path + "-Match-Results.csv", encoding=encoding)
    # self.score_progressions.to_csv(base_path + "-Scores.csv")

    print("Finished writing CSVs to {data_dir}".format(data_dir=data_dir))

  def load_from_csvs(self, data_dir=None, mandatory=True, write=True):
    """Load data from offline csv files"""
    if data_dir is None:
      data_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
    assert isinstance(data_dir, basestring)
    base_path = os.path.join(os.path.expanduser(data_dir), self.event + "-" + self.gender)

    try:
      self.roster_dfs = pd.read_csv(base_path + "-Rosters.csv")
      self.match_report_dfs = pd.read_csv(base_path + "-Match-Reports.csv")
      self.match_result_dfs = pd.read_csv(base_path + "-Match-Results.csv")
      # self.score_progression_dfs = pd.read_csv(base_path + "-Scores.csv")
    except IOError:
      print("Unable to open downloaded CSVs at {path}"
            .format(path=base_path))
      if not mandatory:
        self.to_csvs(data_dir=data_dir)
        return self
      raise
    return self

  @classmethod
  def from_csvs(cls, event, gender, data_dir=None):
    """Constructor from offline csv data"""
    return cls(event, gender).load_from_csvs(data_dir=data_dir)

  @property
  def event_soup(self):
    """BeautifulSoup-parsed HTML from tournament schedule page"""
    if self.event_page_soup is None:
      print("Downloading from URL:", self.event_url)
      page = urllib.urlopen(self.event_url).read().decode('utf-8')
      self.event_page_soup = BeautifulSoup(page, "lxml")
    return self.event_page_soup

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
      team_links += pool.findAll("a", attrs={"href": re.compile("EventTeamId")})

    roster_dfs = []
    # This is trivially parallelizable, but since we have data cached in csvs
    # don't really need to worry about speeding this up.
    for team_link in team_links:
      url = team_link.attrs["href"]
      name, seed = self.split_team_seed(team_link.text)
      # Match tables containing 'Position', i.e. cutter/handler
      roster_table = self.get_html_tables(url, match="Position")[0]
      roster_table["url"] = url
      roster_table["Team"] = name
      roster_table["Seed"] = seed
      roster_dfs.append(roster_table)
    self.roster_dfs = pd.concat(roster_dfs)

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
    # These columns are duplicated for expressiveness; also df.T is already the transpose operator
    table["Gs"] = table["Goals"] = table["G"]
    table["As"] = table["Assists"] = table["A"]
    table["Ds"] = table["D"]
    table["Ts"] = table["Turns"] = table["T"]
    table.drop(["Players", "G", "A", "D", "T"], inplace=True, axis=1)
    return table

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

    match_links = self.event_soup.findAll("a", attrs={"href": re.compile("EventGameId")})

    match_results = []  # Scores, broken down by player contributions
    match_reports = []  # Just the final scores
    score_progressions = []
    # This is trivially parallelizable, but since we have data cached in csvs
    # don't really need to worry about speeding this up.
    # NOTE: sometimes scraper can pick up duplicate URLs, so make sure
    # to unique-ify the URL set.
    for url in set([link.attrs["href"] for link in match_links]):
      # Score-line, i.e. 1-0 1-1 1-2 1-3 2-3
      scores = self.get_html_tables(url, match="Total:")[0].T
      assert len(scores.columns) == 2
      home_team, away_team = scores.iloc[0]
      if home_team == "TBD" and away_team == "TBD":
        # See for example the consolation game b/w Cincinnati and Illinois in D-I Men's 2015,
        # which links to the following empty match report
        # http://play.usaultimate.org/teams/events/match_report/?
        # EventGameId=tu5uM3hYbU6FDLJw%2byP1b33zbjMeXu%2bbIJiyiqteRbo%3d
        print("Empty or malformed match report:", self.BASE_URL + url)
        continue
      home_name, home_seed = self.split_team_seed(home_team)
      away_name, away_seed = self.split_team_seed(away_team)
      home_total_score, away_total_score = scores.iloc[-1]
      home_total_score = self.split_total_score(home_total_score)
      away_total_score = self.split_total_score(away_total_score)

      # Cleanup score progressions
      # scores.iloc[0] = 0
      # scores = scores[:-1].dropna(how='all').fillna(0).diff()[1:]
      # Dataframes of 1 for score, 0 for lose

      # "Players" search string may also pick up sidebar, unfortunately
      # Since the G D A T is in a <tr>, need to give header= explicitly.
      home_roster, away_roster = self.get_html_tables(url, match="Players", header=0)[0:2]
      home_roster = self.clean_match_report_stats(home_roster)
      away_roster = self.clean_match_report_stats(away_roster)

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

      match_results.append({
          "url": url,
          "Team": home_name,
          "Opponent": away_name,
          "Score": home_total_score,
          "Opp Score": away_total_score,
          "Gs": sum(home_roster.Goals),
          "As": sum(home_roster.Assists),
          "Ds": sum(home_roster.Ds),
          "Ts": sum(home_roster.Turns),
          })
      match_results.append({
          "url": url,
          "Team": away_name,
          "Opponent": home_name,
          "Score": away_total_score,
          "Opp Score": home_total_score,
          "Gs": sum(away_roster.Goals),
          "As": sum(away_roster.Assists),
          "Ds": sum(away_roster.Ds),
          "Ts": sum(away_roster.Turns),
          })

      match_reports.append(home_roster)
      match_reports.append(away_roster)
      score_progressions.append(scores)

    self.match_report_dfs = pd.concat(match_reports)
    self.match_result_dfs = pd.DataFrame(match_results)
    return self.match_report_dfs

  @property
  def match_results(self):
    """Returns pd.DataFrame of final score for each match"""
    _ = self.match_reports
    return self.match_result_dfs

  @property
  def missing_tallies(self):
    """Returns pd.DataFrame of matches where goals/assists do not match final result"""
    results = self.match_results
    return results[(results.Gs < results.Score) | (results.As < results.Score)]

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
  def from_nationals(cls, level, year, gender):
    """Refer to :func:`from_event`"""
    if level not in cls._NATIONALS_LEVELS:
      raise ValueError("Unrecognized competition level {level}, choices: {choices}"
                       .format(level=level, choices=_NATIONALS_LEVELS))
    return cls.from_event(level=level, year=year, gender=gender,
                          event="nationals")

  @classmethod
  def from_event(cls, level, year, gender, event="nationals"):
    """Load competition results from human-readable string inputs

    Args:
        level (str): One of "club", "d1college", "d3college"
        year (int | str): 20xx
        gender (str): One of "Men", "Mixed", "Women"
    """
    assert gender in ("Men", "Mixed", "Women"), \
        "Unknown gender input: {gender}".format(gender=gender)
    year = int(year)
    level = level.lower()
    event = event.lower().replace('-', ' ').replace('_', ' ')
    url = None
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
        url = event_info["url"]

    if url is None:
      raise ValueError("Unable to find USAU event for filter: "
                       "level {level} year {year} event {event}"
                       .format(level=level, year=year, event=event))

    # TODO: fix this competition logic
    competition = "College"
    if level == "club":
      competition = "Club"
    return cls(url.format(y=year), gender, competition=competition)

  # Class members
  _NATIONALS_LEVELS = ["club", "d1college", "d3college"]
  # below, start year and end year are inclusive!
  _EVENT_TO_URL = \
    [
      {
        "level": "club",
        "event": ["nationals", "nats"],
        "start_year": 2015,
        "url": "USA-Ultimate-National-Championships-{y}",
      },
      {
        "level": "d1college",
        "event": ["nationals", "nats"],
        "start_year": 2017,
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
        "level": "d3college",
        "event": ["nationals", "nats"],
        "start_year": 2015,
        "url": "USA-Ultimate-D-III-College-Championships-{y}",
      },
      {
        "level": "club",
        "event": ["us open"],
        "start_year": 2017,
        "url": "{y}-US-Open-Club-Championships",
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
        "start_year": 2015,
        "end_year": 2016,
        "url": "TCT-Pro-Flight-Finale-{y}",
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
        "start_year": 2015,
        "end_year": 2016,
        "url": "TCT-Pro-Flight-Finale-{y}",
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
      globals()[key] = USAUResults.from_event(level=level, gender=gender, year=year,
                                              event="nationals")

# TODO: have a better organization for this!
# d1_college_nats_men_2014 = USAUResults("USA-Ultimate-D-I-College-Championships", "Men")
# d1_college_nats_women_2014 = USAUResults("USA-Ultimate-D-I-College-Championships", "Women")
# d3_college_nats_men_2014 = USAUResults("USA-Ultimate-D-III-College-Championships", "Men")
# d3_college_nats_women_2014 = USAUResults("USA-Ultimate-D-III-College-Championships", "Women")
# d1_college_nats_men_2015 = USAUResults("USA-Ultimate-D-I-College-Championships-2015", "Men")
# d1_college_nats_women_2015 = USAUResults("USA-Ultimate-D-I-College-Championships-2015", "Women")
# d3_college_nats_men_2015 = USAUResults("USA-Ultimate-D-III-College-Championships-2015", "Men")
# d3_college_nats_women_2015 = USAUResults("USA-Ultimate-D-III-College-Championships-2015", "Women")
# d1_college_nats_men_2016 = USAUResults("USA-Ultimate-D-I-College-Championships-2016", "Men")
# d1_college_nats_women_2016 = USAUResults("USA-Ultimate-D-I-College-Championships-2016", "Women")
# d3_college_nats_men_2016 = USAUResults("USA-Ultimate-D-III-College-Championships-2016", "Men")
# d3_college_nats_women_2016 = USAUResults("USA-Ultimate-D-III-College-Championships-2016", "Women")
# d1_college_nats_men_2017 = USAUResults("2017-USA-Ultimate-College-Championships", "Men")
# d1_college_nats_women_2017 = USAUResults("2017-USA-Ultimate-College-Championships", "Women")
# d3_college_nats_men_2017 = USAUResults("USA-Ultimate-D-III-College-Championships-2017", "Men")
# d3_college_nats_women_2017 = USAUResults("USA-Ultimate-D-III-College-Championships-2017", "Women")
# 
# club_nats_men_2015 = USAUResults("USA-Ultimate-National-Championships-2015", "Men")
# club_nats_women_2015 = USAUResults("USA-Ultimate-National-Championships-2015", "Women")
# club_nats_mixed_2015 = USAUResults("USA-Ultimate-National-Championships-2015", "Mixed")
# club_nats_men_2016 = USAUResults("USA-Ultimate-National-Championships-2016", "Men")
# club_nats_women_2016 = USAUResults("USA-Ultimate-National-Championships-2016", "Women")
# club_nats_mixed_2016 = USAUResults("USA-Ultimate-National-Championships-2016", "Mixed")
