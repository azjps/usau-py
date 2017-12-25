#!/usr/bin/env python
"""
Summarize ultimate fantasy scores and results.
"""
from __future__ import print_function

import argparse

import numpy as np
import pandas as pd

from usau import markdown, reports


def compute_fantasy_picks(captain_multiplier=2, from_csv=False, fantasy_input=None):
    """Convert fantasy picks to an indicator matrix"""
    # I'll wait until a next fantasy contest to see if this should be generalized ..
    if from_csv:
        reports.d1_college_nats_men_2016.load_from_csvs()
        reports.d1_college_nats_women_2016.load_from_csvs()
    fantasy_mens = reports.d1_college_nats_men_2016.rosters
    fantasy_womens = reports.d1_college_nats_women_2016.rosters

    fantasy_input = fantasy_input or get_fantasy_input()
    for user, fantasy_lines in fantasy_input.iteritems():
        fantasy_mens[user] = 0
        fantasy_womens[user] = 0

        for gender, fantasy_line in fantasy_lines.iteritems():
            for player in fantasy_line:
                player_multiplier = 1
                if player.endswith("*"):
                    player_multiplier = captain_multiplier
                    player = player[:-1]
                player = player.strip()

                if gender == "Men":
                    fantasy = fantasy_mens
                elif gender == "Women":
                    fantasy = fantasy_womens

                # Try to guess name. First based on matching full name, then
                # by matching on last name.
                mask = fantasy.UpperName.str.contains(player.upper())
                if sum(mask) == 1:
                    fantasy[user] += mask * player_multiplier
                elif sum(mask) > 1:
                    print("Found multiple matching players:",
                          user, player, fantasy.loc[mask, "UpperName"].values)
                else:
                    mask = fantasy.UpperName.str.contains(
                        player.split()[-1].upper())
                    if sum(mask) == 1:
                        fantasy[user] += mask * player_multiplier
                    else:
                        print("Found multiple or no matching players:",
                              user, player, fantasy.loc[mask, "UpperName"].values)

    users = sorted(fantasy_input.keys(), key=lambda x: x.upper())
    assert all(fantasy_mens[users].sum() == 6 + captain_multiplier)
    assert all(fantasy_womens[users].sum() == 6 + captain_multiplier)

    fantasy_mens["Fantasy Picks"] = fantasy_mens[users].sum(axis=1)
    fantasy_womens["Fantasy Picks"] = fantasy_womens[users].sum(axis=1)

    return fantasy_mens, fantasy_womens, users


def compute_athlete_fantasy_scores(df, min_players=20, goal_weight=1, assist_weight=1,
                                   d_weight=0.2, turn_weight=-0.2):
    """Compute fantasy score

    Args:
        df (pd.DataFrame): Player contributions and fantasy picks
        min_players (int): Minimum number of players to show, sorted by fantasy score
    """
    df["Fantasy Score"] = (df.Goals * goal_weight + df.Assists * assist_weight +
                           df.Ds * d_weight + df.Turns * turn_weight)
    # Sort players by fantasy score and mark top min_players
    top_fantasy_players = np.zeros(len(df), dtype=np.bool)
    top_fantasy_players[df["Fantasy Score"].argsort(
    ).values[::-1][:min_players]] = True
    # Union of all players with non-zero fantasy picks and top min_players by fantasy score
    result = (df[(df["Fantasy Picks"] > 0) | top_fantasy_players]
              .sort(["Fantasy Score", "Seed"], ascending=False))
    return result


def compute_fantasy_contest_results(min_players=20, use_markdown=False, display=True, from_csv=False,
                                    fantasy_input=None, beta=0.2, captain_multiplier=2):
    """Calculate fantasy results (for athletes and contest users)

    Args:
        min_players (int): Minimum number of players to show
        display (bool): Display results to stdout / jupyter
        use_markdown (bool): Print results as a markdown-formatted table
        from_csv (bool): Load data from offline csvs
    """
    mens, womens, users = compute_fantasy_picks(from_csv=from_csv, captain_multiplier=captain_multiplier,
                                                fantasy_input=fantasy_input)
    # Show the top-scoring players, sorted by fantasy score
    mens = compute_athlete_fantasy_scores(mens, min_players=min_players,
                                          d_weight=beta, turn_weight=-beta)
    womens = compute_athlete_fantasy_scores(womens, min_players=min_players,
                                            d_weight=beta, turn_weight=-beta)
    if display:
        display_cols = ["No.", "Name", "Fantasy Score", "Position", "Height",
                        "Goals", "Assists", "Ds", "Turns",
                        "Team", "Seed", "Fantasy Picks"]
        markdown.display(mens[display_cols], use_markdown=use_markdown)
        markdown.display(womens[display_cols], use_markdown=use_markdown)

    # Show the fantasy contest users sorted by fantasy score
    results = []
    for user in users:
        results.append({"User": user,
                        "Men's": sum(mens["Fantasy Score"] * mens[user]),
                        "Women's": sum(womens["Fantasy Score"] * womens[user])})
    results = pd.DataFrame(results)
    results["Total"] = results["Men's"] + results["Women's"]
    results = results.sort("Total", ascending=False)[
        ["User", "Total", "Men's", "Women's"]]
    if display:
        markdown.display(results, use_markdown=use_markdown)
    return results


def get_fantasy_input():
    """Mapping of users to fantasy lines, with captain marked by asterisk.

    Each fantasy line should have exactly 7 players, one of which is marked captain.
    This probably should be offloaded to some configuration file.
    """
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
    parser = argparse.ArgumentParser()
    parser.add_argument("--num_players", type=int, default=20,
                        help="Minimum number of top scorers")
    parser.add_argument("--markdown", action="store_true",
                        help="Output as markdown")
    parser.add_argument("--csv", action="store_true",
                        help="Load data from offline csvs")
    args = parser.parse_args()

    with pd.option_context("display.width", 1000,
                           "display.max_rows", 100,
                           "display.max_columns", 100,
                           "display.max_colwidth", 100):
        compute_fantasy_contest_results(num_players=args.num_players,
                                        use_markdown=args.markdown,
                                        from_csv=args.csv)
