#!/usr/bin/env python
"""
Quick CLI script for downloading USAU tournament reports into csvs.
"""

import argparse
import os

import usau.reports

if __name__ == "__main__":
  parser = argparse.ArgumentParser()
  parser.add_argument("-e", "--event", required=True,
                      help="Name of USAU competition, as in the play.usaultimate.org url. "
                           "For example: http://play.usaultimate.org/events/ "
                           "USA-Ultimate-D-I-College-Championships-2016")
  parser.add_argument("--gender", nargs="+", default=["Men", "Women"],
                      choices=["Men", "Women", "Mixed", "Boys", "Girls"])
  parser.add_argument("--competition", default="College",
                      choices=["College", "Club"])
  parser.add_argument("--data_dir", help="Path to directory to store csvs")
  parser.add_argument("--proxy",
                      help="HTTP proxy. Might need to set as an environment variable, "
                           "like export http_proxy='..'")
  args = parser.parse_args()

  if args.proxy:
    # As noted in argparser, this probably doesn't affect proxy settings of urllib,
    # might need to set http_proxy as environment variable outside of this script.
    os.environ['http_proxy'] = args.proxy
  for gender in args.gender:
    results = usau.reports.USAUResults(args.event, gender, args.competition)
    results.to_csvs(data_dir=args.data_dir)
