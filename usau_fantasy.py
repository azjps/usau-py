from __future__ import print_function

import numpy as np
import pandas as pd

import markdown
import usau_results as usau

def compute_d1_fantasy_picks():
  """ """
  d1_mens = usau.USAUResults("USA-Ultimate-D-I-College-Championships-2016", "Men")
  d1_womens = usau.USAUResults("USA-Ultimate-D-I-College-Championships-2016", "Women")

  fantasy_mens = d1_mens.rosters
  fantasy_womens = d1_womens.rosters

  for user, fantasy_lines in get_fantasy_input().iteritems():
    fantasy_mens[user] = 0
    fantasy_womens[user] = 0

    for gender, fantasy_line in fantasy_lines.iteritems():
      for player in fantasy_line:
        captain_multiplier = 2 if player.endswith("*") else 1
        if captain_multiplier == 2:
          player = player[:-1]
        player = player.strip()

        if gender == "Men":
          fantasy = fantasy_mens
        elif gender == "Women":
          fantasy = fantasy_womens

        mask = fantasy.UpperName.str.contains(player.upper())
        if sum(mask) == 1:
          fantasy[user] += mask * captain_multiplier
        elif sum(mask) > 1:
          print(user, player)
          # print(fantasy[mask]["UpperName"])
        else:
          mask = fantasy.UpperName.str.contains(player.split()[-1].upper())
          if sum(mask) == 1:
            fantasy[user] += mask * captain_multiplier
          else:
            print(user, player, fantasy[mask]["UpperName"])

  users = sorted(get_fantasy_input().keys(), key=lambda x: x.upper())
  assert all(fantasy_mens[users].sum() == 8)
  assert all(fantasy_womens[users].sum() == 8)

  fantasy_mens["Fantasy Picks"] = fantasy_mens[users].sum(axis=1)
  fantasy_womens["Fantasy Picks"] = fantasy_womens[users].sum(axis=1)

  return fantasy_mens, fantasy_womens, users

def print_d1_fantasy_results(num_players=20, use_markdown=False):
  import IPython.display
  mens, womens, users = compute_d1_fantasy_picks()
  for df in (mens, womens):
    df["Fantasy Score"] = df.Goals + df.Assists + 0.2 * df.Ds - 0.2 * df.Turns
    top_fantasy_players = np.zeros(len(df), dtype=np.bool)
    top_fantasy_players[df["Fantasy Score"].argsort()[::-1][:num_players]] = True
    # IPython.display.display(df[top_fantasy_players][["Name", "Fantasy Score"]])
    result = (df[(df["Fantasy Picks"] > 0) | top_fantasy_players]
                  [["No.", "Name", "Fantasy Score", "Position", "Height",
                    "Goals", "Assists", "Ds", "Turns",
                    "Team", "Seed", "Fantasy Picks"]]
                  .sort(["Fantasy Score", "Seed"], ascending=False))
    if use_markdown:
      print(markdown.pandas_to_markdown(result))
    else:
      IPython.display.display(result)

  results = []
  for user in users:
    results.append({"User": user,
                    "Men's": sum(mens["Fantasy Score"] * mens[user]),
                    "Women's": sum(womens["Fantasy Score"] * womens[user])})
  results = pd.DataFrame(results)
  results["Total"] = results["Men's"] + results["Women's"]
  results = results.sort("Total", ascending=False)[["User", "Total", "Men's", "Women's"]]
  if use_markdown:
    print(markdown.pandas_to_markdown(results))
  else:
    IPython.display.display(results)
  return results

def get_fantasy_input():
  """Captain marked by asterisk"""
  return {
      "scottyskin96": {
        "Men": ["Dalton Smith", "John Stubbs*", "Xavier Maxstadt", "Ben Jagt", "Joe Marmerstein", "Khalif", "Trent Dillon"],
        "Women": ["Shofner*", "Kaylor", "Wahlroos", "Marisa Rafter", "Claire revere", "Mira Donaldson", "Han Chen"],
        },
      "chubs45": {
        "Men": ["Ben Jagt*", "Jack Williams", "John Stubbs", "Connor Kline", "Max Thorne", "Dalton Smith", "Jeff Babbitt"],
        "Women": ["Jesse Shofner*", "Marisa Rafter", "Han Chen", "Mira Donaldson", "Janina Freystaetter", "Jacyln Verzuh", "Kirstin Johnson"],
        },
      "duthracht": {
        "Men": ["John Stubbs", "Aaron Speiss", "Khalif El-Salaam", "Dalton Smith", "Ben Jagt", "Xavier Maxstadt*", "Jack Williams"],
        "Women": ["Marisa Rafter", "Jesse Shofner*", "Han Chen", "Mira Donaldson", "Kristin Pojunis", "Janina Freystaetter", "Angela Zhu"],
        },
      "giftedbadly": {
        "Men": ["Dalton Smith*", "Tannor Johnson", "Trent Dillon", "Pat Earles", "Jack Williams", "John Stubbs", "Jeff Babbitt"],
        "Women": ["Mira Donaldson*", "Jesse Shofner", "Janina Freystaetter", "Claire Revere", "Marisa Rafter", "Angela Zhu", "Kristen Pojunis"],
        },
      "krdonnie": {
        "Men": ["John Stubbs", "Pat Earles", "Mark Vandenberg*", "Sam Little", "Dalton Smith", "Connor Holcombe", "Ben Jagt"],
        "Women": ["Carolyn Normile", "Shayna Brock", "Jesse Shofner*", "Mira Donaldson", "Han Chen", "Chloe Rowse", "Janina Freystaetter"],
        },
      "Ultimatezach": {
        "Men": ["Dalton Smith*", "Ben Jagt", "Xavier Maxstadt", "Khalif El-Salaam", "Trent Dillon", "John Stubbs", "Tannor Johnson"],
        "Women": ["Jesse Shofner*", "Mira Donaldson", "Marisa Rafter", "Kristin Pojunis", "Janina Freystaetter", "Kirstin Johnson", "Bethany Kaylor"],
        },
      "dlquinonesII": {
        "Men": ["Ben Jagt", "John Stubbs", "Dalton Smith*", "Conor Kline", "Xavier Maxstadt", "Khalif El-Salaam", "Trent Dillon"],
        "Women": ["Mira Donaldson", "Janina Freystaetter", "Shayna Brock", "Claire Revere", "Jesse Shofner*", "Han Chen", "Carolyn Normile"],
        },
      "ultimatefrisbee": {
        "Men": ["Dalton Smith", "Xavier Maxstadt", "Ben Jagt", "Khalif El-Salaam*", "Mark Vandenberg", "John Stubbs", "Ryan Landry"],
        "Women": ["Mira Donaldson*", "Olivia Bartruff", "Jesse Shofner", "Monisha White", "Jaclyn Verzuh", "Claire Revere", "Kristen Pojunis"],
        },
      "livetweetyourgames": {
        "Men": ["Tannor Johnson*", "Conor Kline", "Connor Matthews", "Connor Holcombe", "Max Thorne", "Ben Jagt", "Dalton Smith"],
        "Women": ["Janina Freystaetter*", "Shayna Brock", "Mira Donaldson", "Kate Scarth", "Olivia Bartruff", "Jesse Shofner", "Courtney Gegg"],
        },
      "anti_spiral": {
        "Men": ["Dalton Smith*", "Pat Earles", "Tannor Johnson", "Connor Matthews", "Jack Williams", "Jeff Babbitt", "John Stubbs"],
        "Women": ["Kate Scarth", "Bethany Kaylor", "Courtney Gegg*", "Hayley Wahlroos", "Abbie Abramovich", "Mira Donaldson", "Alexa Wood"],
        },
      "grhgra002": {
        "Men": ["Dalton Smith*", "John Stubbs", "Mark Vandenberg", "Xavier Maxstadt", "Ben Jagt", "Khalif El-Salaam", "Connor Matthews"],
        "Women": ["Jesse Shofner*", "Marisa Rafter", "Mira Donaldson", "Han Chen", "Kristin Pojunis", "Courtney Gegg", "Claire Revere"],
        },
      "samth": {
        "Women": ["Shofner*", "Kaylor", "Verzuh", "Donaldson", "Wahlroos", "Brock", "Freystaetter"],
        "Men": ["Trent Dillon", "Maxstadt", "Kline", "Babbit*", "Sadok", "Jagt", "Stubbs"],
        },
      "almondchipcookies": {
        "Men": ["Jeff Babbit*", "Connor Matthews", "Adam Rees", "Ryan Osgar", "Pat Earles", "Dalton Smith", "John Stubbs"],
        "Women": ["Beth Kaylor*", "Jesse Shofner", "Mira Donaldson", "Monisha White", "Shayna Brock", "Han Chen", "Angela Zhu"],
        },
      "azjps": {
        "Men": ["Jeffrey Babbitt*", "Ryan Osgar", "Connor Matthews", "Dalton Smith", "Conor Kline", "Jack Williams", "Mark Vandenberg"],
        "Women": ["Kate Scarth*", "Angela Zhu", "Bethany Kaylor", "Stephanie Williams", "Jesse Shofner", "Courtney Gegg", "Olivia Bartruff"],
       }
      }

if __name__ == "__main__":
  import argparse
  parser = argparse.ArgumentParser()
  parser.add_argument("--num_players", type=int, default=20, help="Minimum number of top scorers")
  parser.add_argument("--markdown", action="store_true", help="Output as markdown")
  args = parser.parse_args()

  with pd.option_context("display.width", 1000,
                         "display.max_rows", 100,
                         "display.max_columns", 100,
                         "display.max_colwidth", 100):
    print_d1_fantasy_results(num_players=args.num_players, use_markdown=args.markdown)
