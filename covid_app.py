import requests
import json
from http.client import responses

import pandas as pd
import numpy as np
from matplotlib import pyplot as plt
from matplotlib import dates
from matplotlib import patches
from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta

import tweepy
from twitter_keys import consumer_key, consumer_key_secret, access_token, access_token_secret

from pandas.plotting import register_matplotlib_converters
register_matplotlib_converters()

def req_ey_data():
    url = 'https://api.coronavirus.data.gov.uk/v1/data'
    headers = {
        'Accepts': 'application/json; application/xml; text/csv; '
                   'application/vnd.PHE-COVID19.v1+json; application/vnd.PHE-COVID19.v1+xml',
        'Content-Type': 'application/json'
    }
    filters = 'areaType=utla;areaName=East Riding Of Yorkshire'
    structure = {
        "Date": "date",
        "Area": "areaName",
        "Cases": {
            "Daily": "newCasesBySpecimenDate",
            "Reported": "newCasesByPublishDate"
        },
        "Deaths": {
            "Daily": "newDeaths28DaysByPublishDate",
            "Cumulative": "cumDeaths28DaysByPublishDate"}
                }

    parameters = {'filters': filters,
                  'structure': json.dumps(structure)
                  }

    r = requests.get(url, headers=headers, params=parameters)
    print(f'HTTP status code: {r.status_code} ({responses[r.status_code]})')
    return r.json()['data']


def req_uk_data():
    url = 'https://api.coronavirus.data.gov.uk/v1/data'
    headers = {
        'Accepts': 'application/json; application/xml; text/csv; '
                   'application/vnd.PHE-COVID19.v1+json; application/vnd.PHE-COVID19.v1+xml',
        'Content-Type': 'application/json'
    }
    filters = 'areaType=overview'
    structure = {
        "Date": "date",
        "Area": "areaName",
        "DailyCases": "newCasesBySpecimenDate"
        }

    parameters = {'filters': filters,
                  'structure': json.dumps(structure)
                  }

    r = requests.get(url, headers=headers, params=parameters)
    print(f'HTTP status code: {r.status_code} ({responses[r.status_code]})')
    return r.json()['data']


def make_ey_df(data):
    df = pd.DataFrame({'Date': [datetime.strptime(x['Date'], '%Y-%m-%d') for x in data],
                       'Daily Cases': [x['Cases']['Daily'] for x in data],
                       'Reported Cases': [x['Cases']['Reported'] for x in data],
                       'Daily Deaths': [x['Deaths']['Daily'] for x in data],
                       'Cumulative Deaths': [x['Deaths']['Cumulative'] for x in data]
                       })

    df['7 Day Case Count'] = df['Daily Cases'][::-1].rolling(window=7).sum()
    df.set_index('Date', inplace=True)

    return df


def make_uk_df(data):
    df = pd.DataFrame({'Date': [datetime.strptime(x['Date'], '%Y-%m-%d') for x in data],
                       'Daily Cases': [x['DailyCases'] for x in data]
                       })

    df['7 Day Case Count'] = df['Daily Cases'][::-1].rolling(window=7).sum()

    df.set_index('Date', inplace=True)

    return df


def make_plot(df):
    # Create three month window
    graph_window = last_complete_day + relativedelta(months=-3)
    df = df.loc[last_complete_day:graph_window]

    # change default plot size (inches): (width, height)
    plt.rcParams['figure.figsize'] = [6, 5]

    # plot rolling seven day average
    seven_days = plt.plot_date(df.index, df['7 Day Case Count'], color='#306CF8', linestyle='-',
                               marker=None, label='Rolling 7 day count', linewidth=3)

    plt.title('COVID-19 cases in the East Riding of Yorkshire')
    plt.xlabel('Test date')
    plt.ylabel('Cases')
    plt.grid(axis='y')

    ax = plt.gca()
    ax.set_ylim([0, 2000])
    ax.set_xlim([graph_window, datetime.today().date()])

    # make major monthly ticks with minor weekly ticks
    ax.xaxis.set_major_locator(dates.MonthLocator())
    ax.xaxis.set_minor_locator(dates.DayLocator(bymonthday=(8, 15, 22)))

    # add today's date as final tick to x axis
    new_x_ticks = np.append(plt.xticks()[0], dates.date2num(datetime.today().date()))
    plt.xticks(new_x_ticks)

    # Format x axis dates
    ax.xaxis.set_major_formatter(dates.DateFormatter('%d %b'))

    # create the 'lockdown' rectangle
    lockdown_date = dates.date2num(datetime(2020, 11, 5))
    rect = patches.Rectangle((lockdown_date, 0), 28, 2000, fill=True, color='#9FDEF3', label='Lockdown')
    ax.add_patch(rect)

    plt.legend(loc=2)

    plt.annotate(f'Data up to {last_complete_day.strftime("%d %b")}. More recent data are incomplete and not included.',
                 (0.5, 0.02), xycoords='figure fraction', ha='center', va='center')

    plt.savefig('graphtest.png', bbox_inches='tight', dpi=300)


def write_tweet(ey_df, uk_df):
    # add tier level? Would need to scrape from https://www.gov.uk/guidance/full-list-of-local-restriction-tiers-by-area
    sign = lambda i: ("+" if i >= 0 else "") + str(i)

    yesterday = datetime.today().date() - timedelta(days=1)
    yesterday_str = yesterday.strftime("%d %b")
    prev_day = yesterday - timedelta(days=1)
    prev_day_str = prev_day.strftime("%d %b")

    day_cases = int(ey_df.loc[yesterday]['Reported Cases'])
    delta_cases = int(day_cases - int(ey_df.loc[prev_day]['Reported Cases']))
    cum_deaths = int(ey_df.loc[yesterday]['Cumulative Deaths'])
    day_deaths = int(ey_df.loc[yesterday]['Daily Deaths'])

    er_pop = 341173
    seven_day_count = int(ey_df.loc[last_complete_day]['7 Day Case Count'])
    er_rate = seven_day_count / er_pop * 100000

    uk_pop = 66796800
    uk_seven_day_count = int(uk_df.loc[last_complete_day]['7 Day Case Count'])
    uk_rate = uk_seven_day_count / uk_pop * 100000

    tweet = (
        f'Cases reported on {yesterday_str}: {day_cases} ({sign(delta_cases)} from {prev_day_str})\n'
        f'Weekly rate per 100k population: {er_rate:.0f} (UK average: {uk_rate:.0f})\n'
        f'Total deaths: {cum_deaths} (up {day_deaths} from {prev_day.strftime("%d %b")}).\n'
        f'\n'
        f'All data from: https://coronavirus.data.gov.uk/')

    return tweet


def send_tweet(tweet):
    auth = tweepy.OAuthHandler(consumer_key, consumer_key_secret)
    auth.set_access_token(access_token, access_token_secret)

    api = tweepy.API(auth)

    try:
        api.verify_credentials()
        print("Authentication OK")
    except:
        print("Error during authentication")

    # returns a JSON media object containing media_id
    image = api.media_upload('graphtest.png')

    api.update_status(tweet, media_ids=[image.media_id, ])


if __name__ == '__main__':
    # The most recent 5 days have incomplete data so do not plot these
    last_complete_day = datetime.today().date() - timedelta(days=5)

    ey_data = make_ey_df(req_ey_data())
    uk_data = make_uk_df(req_uk_data())

    make_plot(ey_data)

    send_tweet(write_tweet(ey_data, uk_data))

