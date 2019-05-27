# usau-py
Python utilities for scraping ultimate tournament data from USAU

This repository includes some simple python modules for scraping the USAU website for tournament results, and some utility functions to manipulate and clean this data. It also includes some examples of such data downloaded as csv files, and some jupyter notebooks with some visualizations from this data.

The `top_n_players.py` CLI script provides a quick way to glean the top player contributions from tournaments like nationals, where player statistics are tracked with some reliability.

## Notebooks (via nbviewer)

* [2016 D-I College Nationals Fantasy Wrap-up](https://nbviewer.jupyter.org/github/azjps/usau-py/blob/master/notebooks/2016_D-I_College_Nationals_Fantasy_Stats.ipynb): Winners of the [/r/ultimate fantasy contest](https://www.reddit.com/r/ultimate/comments/4l74rn/fantasy_lineup_di_college_nationals_2016/) and some overall player statistics

## Installation

To install with [setuptools](https://docs.python.org/install/):

```bash
# Check if https_proxy environment variable needs to be set
git clone https://github.com/azjps/usau-py.git
cd usau-py
./setup.py install
```

or alternatively with pip:

```bash
pip install git+https://github.com/azjps/usau-py.git
```

## Dependencies

This should be both python2.7 and python3 compatible.

See the [requirements.txt](requirements.txt); [pandas 0.13+](https://github.com/pydata/pandas) is the only main module required. pandas 0.17.1+, [jupyter](http://jupyter.readthedocs.io/en/latest/), and [seaborn](https://web.stanford.edu/~mwaskom/software/seaborn/) are recommended to run and view the notebooks. beautifulsoup4 and lxml are recommended for scraping web data on-the-fly from [play.usaultimate.org](http://play.usaultimate.org).
