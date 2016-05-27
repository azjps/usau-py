"""
"""

import re
import urllib

from bs4 import BeautifulSoup
import pandas as pd

_table_cache = {}
def memoize_read_html(url, match):
  global _table_cache
  key = (url, match)
  if key not in _table_cache:
    _table_cache[key] = pd.read_html(url, match)
  return _table_cache[(url, match)]

def title_name(name):
  """Capitalize first letter of each name"""
  if name.isupper():
    return name.title()
  return name  # Leave capitalizations in middle of names, like 'McCray'

class USAUResults(object):
  BASE_URL = "http://play.usaultimate.org"

  def __init__(self, event, gender, competition="College"):
    self.event_url = self.BASE_URL + ("/events/{evt}/schedule/{gender}/{comp}-{gender}"
                                      .format(evt=event, comp=competition, gender=gender))
    page = urllib.urlopen(self.event_url).read().decode('utf-8')
    self.event_soup = BeautifulSoup(page, "lxml")
    self.roster_dfs = None

  @property
  def rosters(self):
    if self.roster_dfs is not None:
      return self.roster_dfs

    team_links = []
    for pool in self.event_soup.findAll("div", attrs={"class": "pool"}):
      team_links += pool.findAll("a", attrs={"href": re.compile("EventTeamId")})

    roster_dfs = []
    for team_link in team_links:
      url = team_link.attrs["href"]
      name, seed = team_link.text.rsplit(" (", 1)
      seed = int(seed[:-1])  # Remove trailing parenthesis
      roster_table = self.get_roster_table(url)
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
  def get_roster_table(cls, url):
    if not url.startswith(cls.BASE_URL):
      url = cls.BASE_URL + url
    return memoize_read_html(url, match='Position')[0]

  def fantasy_results(self, goal_weight=1, assist_weight=1, d_weight=0.2, turn_weight=-0.2):
    fantasy_columns = ["No.", "Name", "Position", "Fantasy", "Goals", "Assists", "Ds", "Turns", "Team", "Seed"]
    rosters = self.rosters
    rosters["Fantasy"] = (goal_weight * rosters.Goals + assist_weight * rosters.Assists +
                          d_weight * rosters.Ds + turn_weight * rosters.Turns)
    return rosters.sort('Fantasy', ascending=False)[fantasy_columns]
