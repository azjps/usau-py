#!/usr/bin/env python
"""
Simple CLI script to load the top N players from
a nationals competition based on +/- stats.
"""
import argparse

import pandas as pd

import usau.reports
import usau.fantasy
import usau.markdown

def compute_plus_minus(df, g_weight=1, a_weight=1, d_weight=1, turn_weight=-0.5):
  return (g_weight * df["Goals"] +
          a_weight * df["Assists"] +
          d_weight * df["Ds"] +
          turn_weight * df["Turns"])

if __name__ == "__main__":
  parser = argparse.ArgumentParser()
  parser.add_argument("-y", "--year", type=int, required=True,
                      help="Year, e.g. 20xx")
  parser.add_argument("-l", "--level",
                      required=True, choices=usau.reports.USAUResults._NATIONALS_LEVELS,
                      help="Competition level")
  parser.add_argument("-n", "--num_players", default=25,
                      help="Minimum number of players to enumerate")
  parser.add_argument("-g", "--gender", nargs="+", choices=["Men", "Mixed", "Women"],
                      help="Enumerate genders (by default all)")
  parser.add_argument("--markdown", action="store_true",
                      help="Format output tables using markdown table syntax")
  parser.add_argument("-G", "--goal_weight", type=float, default=1,
                      help="Multiplier for goals")
  parser.add_argument("-A", "--assist_weight", type=float, default=1,
                      help="Multiplier for assists")
  parser.add_argument("-D", "--d_weight", type=float, default=1,
                      help="Multiplier for defensive blocks")
  parser.add_argument("-T", "--turn_weight", type=float, default=-0.5,
                      help="Multiplier for turns; usually negative")
  args = parser.parse_args()

  # rosters = {}
  genders = args.gender
  if genders is None:
    genders = ["Men", "Mixed", "Women"] if args.level == "club" else ["Men", "Women"]

  for gender in genders:
    report = usau.reports.USAUResults.from_nationals(year=args.year, level=args.level, gender=gender)
    report.load_from_csvs(mandatory=False, write=True)
    roster = report.rosters
    roster["+/-"] = compute_plus_minus(roster,
                                       g_weight=args.goal_weight,
                                       a_weight=args.assist_weight,
                                       d_weight=args.d_weight,
                                       turn_weight=args.turn_weight)

    res = roster.sort_values("+/-", ascending=False).reset_index(drop=True).head(50) \
        [["No.", "Name", "Team", "Goals", "Assists", "Ds", "Turns", "+/-"]]
    #     .style \
    #     .bar(subset=['Fantasy Score', 'Goals', 'Ds', '+/-'],
    #          color='rgba(80, 200, 100, 0.5)') \
    #     .bar(subset=['Assists', 'Turns'],
    #          color='rgba(200, 80, 80, 0.5)')

    print("{event} {gender} ({year})"
          .format(year=args.year, event=report.event, gender=report.gender))
    if args.markdown:
      print(usau.markdown.pandas_to_markdown(res))
    else:
      with pd.option_context('display.width', 200, 'display.max_columns', 50):
        print(res)
