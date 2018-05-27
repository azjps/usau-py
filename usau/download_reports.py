#!/usr/bin/env python
"""
Quick CLI script for downloading USAU tournament reports into csvs.
"""

import argparse
import logging
import os

import usau.reports

_logger = logging.getLogger()

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    group_evt = parser.add_mutually_exclusive_group(required=True)
    group_evt.add_argument("-u", "--url",
                           help="Name of USAU competition, as in the play.usaultimate.org url. "
                                "For example: http://play.usaultimate.org/events/"
                                "USA-Ultimate-D-I-College-Championships-2016")
    group_evt.add_argument("-e", "--event",
                           help="Name of USAU competition in shorthand")
    parser.add_argument("-y", "--year", type=int,
                        help="Year of event")
    parser.add_argument("--gender", nargs="+", default=None,
                        choices=["men", "women", "mixed", "boys", "girls"])
    parser.add_argument("-l", "--level", default="club",
                        choices=["club", "d1college", "d3college"])
    parser.add_argument("--data_dir", help="Path to directory to store csvs")
    parser.add_argument("--proxy",
                        help="HTTP proxy. Might need to set as an environment variable, "
                             "like export http_proxy='..'")
    parser.add_argument("--parallel", choices=["process", "thread"],
                        help="Use multi-processing or multi-threading based "
                             "concurrency to speed up downloading reports")
    parser.add_argument("--max_workers", type=int, default=4,
                        help="Number of workers to use for concurrency")
    parser.add_argument("--log_level", default="INFO",
                        help="Python logging verbosity level")
    args = parser.parse_args()

    logging.basicConfig(level=args.log_level)
    if args.proxy:
        # As noted in argparser, this probably doesn't affect proxy settings of urllib,
        # might need to set http_proxy as environment variable outside of this script.
        os.environ['http_proxy'] = args.proxy
    if args.gender is None:
        if args.level == "club":
            args.gender = usau.reports.USAUResults._GENDERS
        else:
            args.gender = ["men", "women"]
        _logger.info("Downloading results for genders: {genders}"
                     .format(genders=args.gender))
    for gender in args.gender:
        if args.url is not None:
            results = (usau.reports.USAUResults
                           .from_url(args.url, level=args.level))
        elif args.event is not None:
            results = (usau.reports.USAUResults
                           .from_event(year=args.year,
                                       event=args.event,
                                       gender=gender,
                                       level=args.level))
        else:
            raise ValueError("Need --url or --event")
        if args.parallel:
            results.set_executor(mode=args.parallel,
                                 max_workers=args.max_workers)
        results.to_csvs(data_dir=args.data_dir)
