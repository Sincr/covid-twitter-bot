#! /usr/bin/env python3
import requests
import json
from http.client import responses

import pandas as pd
import numpy as np
from matplotlib import dates, patches, pyplot as plt
from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta

import tweepy
from twitter_keys import consumer_key, consumer_key_secret, access_token, access_token_secret
from api_parameters import uk_params, ey_params, hull_params

from pandas.plotting import register_matplotlib_converters
register_matplotlib_converters()


def request_data(filters, structure):
    """Request data from UK government COVID API."""

    # See url for API documentation
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
    """Create dataframe from JSON data."""
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


def style_plot(fig, ax):
    """Format axes and save matplotlib figure."""
    ax.set_title('COVID-19 rates in Hull and East Yorkshire')
    ax.set_ylabel('Weekly cases per 100,000 population')
    ax.grid(axis='y')
    ax.set_ylim(bottom=0)
    ax.set_xlim([graph_window, datetime.today().date()])

    # Make major monthly ticks with minor weekly ticks
    ax.xaxis.set_major_locator(dates.MonthLocator())
    ax.xaxis.set_minor_locator(dates.DayLocator(bymonthday=(8, 15, 22)))

    # Add today's date as final tick to x axis
    today = datetime.today().date()
    if today - today.replace(day=1) > timedelta(days=15):
        ax.set_xticks(np.append(ax.get_xticks(), dates.date2num(datetime.today().date())))

    # Format x axis dates
    ax.xaxis.set_major_formatter(dates.DateFormatter('%d %b'))

    # Create the 'lockdown' rectangles
    lockdown1_date = dates.date2num(datetime(2020, 11, 5))
    rect1 = patches.Rectangle((lockdown1_date, 0), 28, ax.get_ylim()[1], fill=True, color='#c1e7ff', label='Lockdown')
    ax.add_patch(rect1)
    lockdown2_date = dates.date2num(datetime(2021, 1, 5))
    rect2 = patches.Rectangle((lockdown2_date, 0), 42, ax.get_ylim()[1], fill=True, color='#c1e7ff')
    ax.add_patch(rect2)

    ax.legend(loc=2)
    ax.annotate(f'Data up to {last_complete_day.strftime("%d %b")}. More recent data are incomplete and not included.',
                (0.5, 0.03), xycoords='figure fraction', ha='center', va='center')

    fig.tight_layout()
    fig.savefig('graph.png')


def plot_df(ax, df, label, colour):
    """Plot dataframe on chosen axes."""
    # Create three month window
    df = df.loc[last_complete_day:graph_window]

    # Plot rolling seven day average
    seven_days = ax.plot_date(df.index, df['Weekly Rate'], color=colour, linestyle='-', marker=None,
                              label=label, linewidth=2)


def sign(num):
    """Add positive sign to positive number."""
    return ("+" if num >= 0 else "") + str(num)


def write_tweet(dataframe, region):
    """Write and format text for tweet."""
    # Calculate and format dates
    yesterday = datetime.today().date() - timedelta(days=1)
    yesterday_str = yesterday.strftime("%d %b")
    prev_day = yesterday - timedelta(days=1)
    prev_day_str = prev_day.strftime("%d %b")
    # Grab relevant data from dataframe
    day_cases = int(dataframe.loc[yesterday]['Reported Cases'])
    delta_cases = int(day_cases - int(dataframe.loc[prev_day]['Reported Cases']))
    cum_deaths = int(dataframe.loc[yesterday]['Cumulative Deaths'])
    day_deaths = int(dataframe.loc[yesterday]['Daily Deaths'])
    # Write tweet
    text = (
        f'{region}:\n'
        f'Cases reported on {yesterday_str}: {day_cases} ({sign(delta_cases)} from {prev_day_str})\n'
        f'Total deaths: {cum_deaths} ({sign(day_deaths)} from {prev_day.strftime("%d %b")}).\n'
        f'\n'
    )

    return text


def send_tweet(text):
    """Send tweet text and media to twitter API."""
    # Authenticate twitter credentials
    auth = tweepy.OAuthHandler(consumer_key, consumer_key_secret)
    auth.set_access_token(access_token, access_token_secret)
    api = tweepy.API(auth)
    try:
        api.verify_credentials()
        print("Authentication OK")
    except:
        print("Error during authentication")

    # Upload media and return a JSON media object containing media_id
    image = api.media_upload('graph.png')

    # Send tweet
    api.update_status(text, media_ids=[image.media_id, ])
    print('Tweet successfully sent')


def main():
    # Request data and create dataframes for each region
    ey_df = make_df(request_data(ey_params['filter'], ey_params['structure']), ey_params['population'])
    hull_df = make_df(request_data(hull_params['filter'], hull_params['structure']), hull_params['population'])
    uk_df = make_df(request_data(uk_params['filter'], uk_params['structure']), uk_params['population'])

    # Create figure object and plot data
    figure, axes = plt.subplots(figsize=(8, 4.5), dpi=300)
    plot_df(axes, hull_df, 'Hull', '#bc5090')
    plot_df(axes, ey_df, 'East Yorkshire', '#ffa600')
    plot_df(axes, uk_df, 'UK average', '#003f5c')
    style_plot(figure, axes)

    # Send tweet
    tweet_text = (write_tweet(hull_df, 'Hull') + write_tweet(ey_df, 'East Yorkshire') +
                  f'All data from: https://coronavirus.data.gov.uk/')
    send_tweet(tweet_text)


if __name__ == '__main__':
    # Define window for graph
    last_complete_day = datetime.today().date() - timedelta(days=5)
    graph_window = last_complete_day + relativedelta(months=-3)

    main()

