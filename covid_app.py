#! /usr/bin/env python3
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


def request_data(filters, structure):
    # requests data from uk gov covid api
    # see url for api documentation
    url = 'https://api.coronavirus.data.gov.uk/v1/data'
    headers = {
        'Accepts': 'application/json; application/xml; text/csv; '
                   'application/vnd.PHE-COVID19.v1+json; application/vnd.PHE-COVID19.v1+xml',
        'Content-Type': 'application/json'
    }

    parameters = {'filters': filters,
                  'structure': json.dumps(structure)
                  }

    r = requests.get(url, headers=headers, params=parameters)
    print(f'HTTP status code: {r.status_code} ({responses[r.status_code]})')
    return r.json()['data']


def make_df(data, population):
    df = pd.DataFrame({'Date': [datetime.strptime(x['Date'], '%Y-%m-%d') for x in data],
                       'Daily Cases': [x['DailyCasesSpecimen'] for x in data]
                       })

    if 'DailyCasesReported' in data[0]:
        df['Reported Cases'] = [x['DailyCasesReported'] for x in data]
        df['Daily Deaths'] = [x['DailyDeaths'] for x in data]
        df['Cumulative Deaths'] = [x['CumulativeDeaths'] for x in data]

    df['Weekly Case Count'] = df['Daily Cases'][::-1].rolling(window=7).sum()
    df['Weekly Rate'] = [x / population * 100000 for x in df['Weekly Case Count']]

    df.set_index('Date', inplace=True)

    return df


def merge_regions(r1, r1_pop, r2, r2_pop):
    data = []
    for i, x in enumerate(r1):
        data.append({})
        for key in x:
            if isinstance(r1[i][key], int) or isinstance(r2[i][key], int):
                data[i][key] = int(r1[i][key] or 0) + int(r2[i][key] or 0)
            else:
                data[i][key] = x[key]

    pop = r1_pop + r2_pop
    return data, pop


def style_plot(fig, ax):
    ax.set_title('COVID-19 rates in Hull and East Yorkshire')
    ax.set_ylabel('Weekly cases per 100,000 population')
    ax.grid(axis='y')

    ax.set_ylim(bottom=0)
    ax.set_xlim([graph_window, datetime.today().date()])

    # make major monthly ticks with minor weekly ticks
    ax.xaxis.set_major_locator(dates.MonthLocator())
    ax.xaxis.set_minor_locator(dates.DayLocator(bymonthday=(8, 15, 22)))

    # add today's date as final tick to x axis
    today = datetime.today().date()
    if today - today.replace(day=1) > timedelta(days=15):
        ax.set_xticks(np.append(ax.get_xticks(), dates.date2num(datetime.today().date())))

    # Format x axis dates
    ax.xaxis.set_major_formatter(dates.DateFormatter('%d %b'))

    # create the 'lockdown' rectangles
    lockdown_date = dates.date2num(datetime(2020, 11, 5))
    rect1 = patches.Rectangle((lockdown_date, 0), 28, ax.get_ylim()[1], fill=True, color='#c1e7ff', label='Lockdown')
    ax.add_patch(rect1)

    lockdown_date = dates.date2num(datetime(2021, 1, 5))
    rect2 = patches.Rectangle((lockdown_date, 0), 42, ax.get_ylim()[1], fill=True, color='#c1e7ff')
    ax.add_patch(rect2)

    ax.legend(loc=2)
    ax.annotate(f'Data up to {last_complete_day.strftime("%d %b")}. More recent data are incomplete and not included.',
                 (0.5, 0.03), xycoords='figure fraction', ha='center', va='center')

    fig.tight_layout()
    fig.savefig('graphtest.png')


def plot_df(ax, df, label, colour):
    # Create three month window
    df = df.loc[last_complete_day:graph_window]

    # plot rolling seven day average
    seven_days = ax.plot_date(df.index, df['Weekly Rate'], color=colour, linestyle='-', marker=None,
                              label=label, linewidth=2)


def write_tweet(dataframe, region):
    sign = lambda i: ("+" if i >= 0 else "") + str(i)

    yesterday = datetime.today().date() - timedelta(days=1)
    yesterday_str = yesterday.strftime("%d %b")
    prev_day = yesterday - timedelta(days=1)
    prev_day_str = prev_day.strftime("%d %b")

    day_cases = int(dataframe.loc[yesterday]['Reported Cases'])
    delta_cases = int(day_cases - int(dataframe.loc[prev_day]['Reported Cases']))
    cum_deaths = int(dataframe.loc[yesterday]['Cumulative Deaths'])
    day_deaths = int(dataframe.loc[yesterday]['Daily Deaths'])

    text = (
        f'{region}:\n'
        f'Cases reported on {yesterday_str}: {day_cases} ({sign(delta_cases)} from {prev_day_str})\n'
        f'Total deaths: {cum_deaths} ({sign(day_deaths)} from {prev_day.strftime("%d %b")}).\n'
        f'\n'
    )

    return text


def send_tweet(text):
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
    print('Tweet successfully sent')


uk_filter = 'areaType=overview'
uk_structure = {
    "Date": "date",
    "Area": "areaName",
    "DailyCasesSpecimen": "newCasesBySpecimenDate"
}

ey_filter = 'areaType=utla;areaName=East Riding Of Yorkshire'
ey_structure = {
    "Date": "date",
    "Area": "areaName",
    "DailyCasesSpecimen": "newCasesBySpecimenDate",
    "DailyCasesReported": "newCasesByPublishDate",
    "DailyDeaths": "newDeaths28DaysByPublishDate",
    "CumulativeDeaths": "cumDeaths28DaysByPublishDate"
}


hull_filter = 'areaType=utla;areaName=Kingston upon Hull, City of'
hull_structure = ey_structure

uk_pop = 66796881
hull_pop = 259778
ey_pop = 341173


if __name__ == '__main__':
    # The most recent 5 days have incomplete data so do not plot these
    last_complete_day = datetime.today().date() - timedelta(days=5)
    graph_window = last_complete_day + relativedelta(months=-3)

    ey_df = make_df(request_data(ey_filter, ey_structure), ey_pop)
    hull_df = make_df(request_data(hull_filter, hull_structure), hull_pop)

    uk_df = make_df(request_data(uk_filter, uk_structure), uk_pop)

    figure, axes = plt.subplots(figsize=(8, 4.5), dpi=300)

    plot_df(axes, hull_df, 'Hull', '#bc5090')
    plot_df(axes, ey_df, 'East Yorkshire', '#ffa600')
    plot_df(axes, uk_df, 'UK average', '#003f5c')

    style_plot(figure, axes)

    tweet = (write_tweet(hull_df, 'Hull') +
             write_tweet(ey_df, 'East Yorkshire') +
             f'All data from: https://coronavirus.data.gov.uk/')

    send_tweet(tweet)

