import requests
import datetime
import time
import pytz
import argparse

LOOK_BACK = 30 # minutes
RETRIES = 3
REPORT_TYPE = 'installs_report'

params = {
  'category': 'standard',
  'media_source': 'googleadwords_int'
}

def get_datetime (timezone, lookback = 0):
  tz = pytz.timezone(timezone)
  return (datetime.datetime.now(tz) - datetime.timedelta(minutes = lookback)).strftime("%Y-%m-%d %H:%M")

def installs_report (api_token, app_id, timezone = 'Asia/Jerusalem', lookback = LOOK_BACK):
  params['api_token'] = api_token 
  params['from'] = get_datetime(timezone, lookback)
  params['to'] = get_datetime(timezone) 
  params['timezone'] = timezone 
  
  request_url = 'https://hq.appsflyer.com/export/{}/{}/v5'.format(app_id, REPORT_TYPE)

  trial = 0
  res = requests.request('GET', request_url, params=params)
  
  while(True):
    if res.status_code != 200:
      if res.status_code == 404:
        print('There is a problem with the request URL. Make sure that it is correct')
      else:
        print('There was a problem retrieving data: ', res.text)
      trial += 1
      if(trial <= RETRIES):
        raise IOError('Error while querying first_open report from AppsFlyer', res.text)
      print("retry in 1 mintue..")
      time.sleep(60)
    else:
      return res.text 
  



