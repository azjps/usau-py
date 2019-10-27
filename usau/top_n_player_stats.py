#!/usr/bin/env python
"""
Simple CLI script to load the top N players from
a nationals competition based on +/- stats.

Example:

    ./nationals_player_stats.py -y 2017 --level d1college --markdown
"""
from __future__ import print_function

import argparse

import pandas as pd

import usau.reports
import usau.fantasy
import usau.markdown

def compute_plus_minus(df, g_weight=1, a_weight=1, d_weight=1, turn_weight=-0.5):
  return (g_weight * df["Goals"].fillna(0) +
          a_weight * df["Assists"].fillna(0) +
          d_weight * df["Ds"].fillna(0) +
          turn_weight * df["Turns"].fillna(0))

if __name__ == "__main__":
  parser = argparse.ArgumentParser()
  parser.add_argument("-y", "--year", type=int, required=True,
                      help="Year, e.g. 20xx")
  parser.add_argument("-e", "--event", default="nationals",
                      help="USAU event label, such as \"nationals\" or \"us open\"")
  parser.add_argument("-l", "--level",
                      required=True, choices=usau.reports.USAUResults._NATIONALS_LEVELS,
                      help="Competition level")
  parser.add_argument("-n", "--num_players", default=25, type=int,
                      help="Minimum number of players to enumerate")
  parser.add_argument("-g", "--gender", nargs="+", choices=["Men", "Mixed", "Women"],
                      help="Enumerate genders (by default all)")
  parser.add_argument("--markdown", action="store_true",
                      help="Format output tables using markdown table syntax")
  parser.add_argument("--sort_per_game", "--pg", action="store_true",
                      help="Sort by per-game +/- instead of total")
  parser.add_argument("-G", "--goal_weight", type=float, default=1,
                      help="Multiplier for goals")
  parser.add_argument("-A", "--assist_weight", type=float, default=1,
                      help="Multiplier for assists")
  parser.add_argument("-D", "--d_weight", type=float, default=1,
                      help="Multiplier for defensive blocks")
  parser.add_argument("-T", "--turn_weight", type=float, default=-0.5,
                      help="Multiplier for turns; usually negative")
  parser.add_argument("--bold_teams", nargs="+",
                      help="Teams to bold, e.g. as **team**")
  parser.add_argument("--keep_teams", nargs="+",
                      help="Teams to keep")
  parser.add_argument("--skip_teams", nargs="+",
                      help="Teams to skip")
  args = parser.parse_args()

  # rosters = {}
  genders = args.gender
  if genders is None:
    genders = ["Men", "Mixed", "Women"] if args.level == "club" else ["Men", "Women"]

  for gender in genders:
    report = usau.reports.USAUResults.from_event(year=args.year,
                                                 level=args.level,
                                                 gender=gender,
                                                 event=args.event)
    report.load_from_csvs(mandatory=False, write=True)
    roster = report.rosters
    if "Points" in roster.columns:
        roster.rename(columns={"Points": "Goals"}, inplace=True)
    elif "Goals" not in roster.columns:
        raise ValueError("No goals column found: {}".format(roster.column))

    for col in ("Goals", "Assists", "Ds", "Turns"):
      roster[col] = roster[col].fillna(0).astype(int)
    roster["+/-"] = compute_plus_minus(roster,
                                       g_weight=args.goal_weight,
                                       a_weight=args.assist_weight,
                                       d_weight=args.d_weight,
                                       turn_weight=args.turn_weight)

    # Compute the total number of games played per team, for normalization purposes
    matches = report.match_results.drop_duplicates(subset=["Team", "url"])
    matches["Team Games Played"] = 1
    matches["Team Points Played"] = matches["Score"] + matches["Opp Score"]
    matches = matches[matches["Gs"] > 0] \
        .rename(columns={"Score": "Team Score",
                         "Opp Score": "Team Opp Score",
                        })
    matches = matches.groupby("Team")[["Team Games Played", "Team Points Played",
                                       "Team Score", "Team Opp Score"]].sum()
    roster = roster.join(matches, on="Team")
    roster["+/- per Game"] = roster["+/-"] / roster["Team Games Played"]
    roster["#Games"] = roster["Team Games Played"]

    if args.keep_teams:
      roster = roster.loc[roster["Team"].isin(args.keep_teams)].copy()
    if args.skip_teams:
      roster = roster.loc[~roster["Team"].isin(args.skip_teams)].copy()

    # Sort by +/-
    sort_column = "+/- per Game" if args.sort_per_game else "+/-"
    sort_fn = roster.sort_values if hasattr(roster, "sort_values") else roster.sort
    res = (sort_fn(sort_column, ascending=False)
                 .reset_index(drop=True)
                 .head(args.num_players)
                 [["Name", "Team",
                   "Goals", "Assists", "Ds", "Turns",
                   "+/-", "+/- per Game", "#Games"]]
                 .rename(columns={"Goals": "Gs", "Assists": "As", "Turns": "Ts",
                                  "+/- per Game": "+/-pg"})
          )
    #     .style \
    #     .bar(subset=['Fantasy Score', 'Goals', 'Ds', '+/-'],
    #          color='rgba(80, 200, 100, 0.5)') \
    #     .bar(subset=['Assists', 'Turns'],
    #          color='rgba(200, 80, 80, 0.5)')

    if args.bold_teams:
      res.loc[res["Team"].isin(args.bold_teams), "Team"] = \
          res["Team"].apply(lambda x: "**" + x + "**")

    print("{event} {gender} ({year})"
          .format(year=args.year, event=report, gender=report.gender))
    if args.markdown:
      with pd.option_context('display.float_format', lambda x: "%.2f" % x):
        print(usau.markdown.pandas_to_markdown(res))
    else:
      with pd.option_context('display.width', 200, 'display.max_columns', 50,
                             'display.max_rows', 200, 'display.precision', 2):
        print(res)
