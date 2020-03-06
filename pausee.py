#!/usr/bin/env python
#
# Copyright 2019 Google Inc. All Rights Reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.


import argparse
import datetime
import schedule
import time
from googleads import adwords
import pytz
import yaml
import json
from appsflyerreport import installs_report
import pandas as pd
from io import StringIO
from refreshtoken import get_refresh_token
import gmail

STATUS = {
  'PAUSED': 'PAUSED',
  'ENABLED': 'ENABLED'
}

cfg = None

def pet_installs_report (device):   
  app_ids = cfg['app_ids']
  lookback = cfg['params']['lookback']
  timezone = cfg['params']['timezone']
  af_api_token = cfg['af_api_token']
  
  return list(map(lambda app_id: installs_report(af_api_token, app_id, timezone, lookback), app_ids))

def read_cfg(config_file):
  global cfg
  with open(config_file, 'r') as stream:
    try:
      cfg = yaml.safe_load(stream)
    except yaml.YAMLError as exc:
      print(exc)   

def email_alert (installs_count):
  email_cfg = cfg['email']

  if(installs_count > cfg['params']['email_alert']):
    message = email_cfg['messages']['alert']
    body = message['body'].format(installs_count, cfg['params']['lookback'])
    gmail.send_mail(email_cfg['email'], email_cfg['password'], email_cfg['to'], message['title'], body)
    print('Alert sent in email')

def mutate_campatings_email (campiagn_ids, failed_ids, status):
  email_cfg = cfg['email']
  message = email_cfg['messages']['mutate']
  body = message['body'].format(campiagn_ids, status, failed_ids, status)
  gmail.send_mail(email_cfg['email'], email_cfg['password'], email_cfg['to'], message['title'], body)
  print('Mutate notice sent in email')

def campaigns_to_pause(campaigns_dict_by_events_sorted, tot_installs_count, pause_limit):
  cur_installs_count = 0
  campaigns_count_to_pause = {}
  for campaign_id in campaigns_dict_by_events_sorted.keys():
    count = campaigns_dict_by_events_sorted[campaign_id]
    cur_installs_count += count
    campaigns_count_to_pause.update({campaign_id : count})
    if(tot_installs_count - cur_installs_count < pause_limit):
      break  
  return campaigns_count_to_pause

def campaigns_to_resume(paused_campaigns_saved, installs_count, pause_limit):
  paused_campaigns_sorted = {k: v for k, v in sorted(paused_campaigns_saved.items(), key=lambda item: item[1])}
  campaigns_count_to_resume = {}
  cur_installs_count = 0
  for campaign_id in paused_campaigns_sorted.keys():
    cur_installs_count += int(paused_campaigns_sorted[campaign_id])
    if(installs_count + cur_installs_count >= pause_limit):
      break
    campaigns_count_to_resume.update({campaign_id: paused_campaigns_sorted[campaign_id]})
  return campaigns_count_to_resume

def mutate_campaigns(campaign_service, campaigns_count, status):
  operations = [{
    'operator': 'SET',
    'operand': {
      'id': None,
      'status': status
    }
  }]
  print("camp:", campaigns_count)
  mutated = {}
  failed_ids = []
  for campaign_id in campaigns_count.keys():
    operations[0]['operand']['id'] = campaign_id

    try:
      campaign_service.mutate(operations)
      print ("Set status: {} for campaign id: {} with {} installs".format(status, campaign_id, campaigns_count[campaign_id]))
      mutated.update({campaign_id: campaigns_count[campaign_id]})
    except:
      print("Failed to set satus {} for campaign id {}".format(status, campaign_id))
      failed_ids.append(campaign_id)
  return mutated, failed_ids

def save_paused_campaigns(paused_campaigns_saved):
  print("Saving paused campaings")
  json_paused = json.dumps(paused_campaigns_saved)
  f = open("pausedids.json","w")
  f.write(json_paused)
  f.close()

def read_paused_campaigns():
  with open('pausedids.json') as json_file:
    return json.load(json_file) or {}

def pausee (campaign_service, campaigns_df, credentials_file):
  installs_count = len(campaigns_df.index)
  alert_limit = cfg['params']['email_alert']
  pause_limit = cfg['params']['pause_camapaigns']
  paused_campaigns_count_saved = read_paused_campaigns()
  if(installs_count > alert_limit and installs_count < pause_limit):
    email_alert(len(campaigns_df.index))
  
  elif(installs_count >= pause_limit):
    print('Pausing campaigns..')
    email_alert(len(campaigns_df.index))
    campaigns_sorted_by_install = campaigns_df.groupby('Campaign ID').size() \
      .reset_index(name='count').sort_values(by=['count']) 
    campaigns_events_sorted = campaigns_sorted_by_install.set_index('Campaign ID')['count'].to_dict()   
    campaigns_count_to_pause = campaigns_to_pause(campaigns_events_sorted, installs_count, pause_limit)

    (new_paused_count, failed_ids) = mutate_campaigns(campaign_service, campaigns_count_to_pause, STATUS['PAUSED'])
    mutate_campatings_email(list(new_paused_count.keys()), failed_ids, STATUS['PAUSED'])
    paused_campaigns_count_saved.update(new_paused_count)
    save_paused_campaigns(paused_campaigns_count_saved)
    
  
  else:
    print("Installs below limit")
    campaigns_count_to_resume = campaigns_to_resume(paused_campaigns_count_saved, installs_count, pause_limit)
    (new_resumed_count, failed_ids) = mutate_campaigns(campaign_service, campaigns_count_to_resume, STATUS['ENABLED'])
    mutate_campatings_email(list(new_resumed_count.keys()), failed_ids, STATUS['ENABLED'])
    for k in new_resumed_count.keys():
      paused_campaigns_count_saved.pop(k, None)
    save_paused_campaigns(paused_campaigns_count_saved)


def is_in_timeframe():
  tz = pytz.timezone(cfg['params']['timezone'])
  hour_from = datetime.datetime.strptime(str(cfg['params']['from']), '%H')
  hour_to = datetime.datetime.strptime(str(cfg['params']['to']), '%H')
  hour_now = datetime.datetime.strptime(str(datetime.datetime.now(tz).hour), '%H')
  day_delta = datetime.timedelta(days = 1)
  print([hour_from, hour_now, hour_to])
  if (hour_from >= hour_to):   
    hour_to += day_delta

  return hour_from <= hour_now < hour_to or hour_from <= hour_now + day_delta < hour_to
  
def enable_all_campaigns(campaign_service):
  paused_campaigns_count_saved = read_paused_campaigns()
  if(len(paused_campaigns_count_saved)):
    (new_resumed_count, failed_ids) = mutate_campaigns(campaign_service, paused_campaigns_count_saved, STATUS['ENABLED'])
    mutate_campatings_email(list(new_resumed_count.keys()), failed_ids, STATUS['ENABLED'])
    for k in new_resumed_count.keys():
      paused_campaigns_count_saved.pop(k, None)
    save_paused_campaigns(paused_campaigns_count_saved)


def pausee_job(credentials_file, device):
  client = adwords.AdWordsClient.LoadFromStorage(credentials_file) 
  campaign_service = client.GetService('CampaignService', version='v201809')
  
  if(not is_in_timeframe()):
    enable_all_campaigns(campaign_service)
    print('not in timeframe')
    return

  reports_ds = list(map(lambda report: pd.read_csv(StringIO(report), sep =","), pet_installs_report(device)))
  unified_report =  pd.concat(reports_ds)

  pausee(campaign_service, unified_report, credentials_file)

def main(credentials_file, config_file, device):
  read_cfg(config_file)
  print("scheduled to run every {} mintues", cfg['params']['repeat'])
  pausee_job(credentials_file, device)
  schedule.every(cfg['params']['repeat']).minutes.do(pausee_job, credentials_file = credentials_file, device = device)
  
  while True:
    schedule.run_pending()
    time.sleep(1)

if __name__ == '__main__':
  parser = argparse.ArgumentParser(prog='python pausee.py')
  parser.add_argument('-c', '--config', type=str, default='config.yaml',
                      help='campaigns configuration file')
  parser.add_argument('-g', '--credentials', type=str,
                      default='googleads.yaml',
                      help='Google Ads credentials file')

  parser.add_argument('-d', '--device', type=str, default='Android',
                      help='Device type: Android or iOS')
  group = parser.add_mutually_exclusive_group()
  group.add_argument('-a', '--auth', action='store_true', default=False,
                     help=('authenticate in Google Ads and store refresh'
                           ' token in the credentials file'))

  args = parser.parse_args()
  if args.auth:
    get_refresh_token(args.credentials)
  else:
    main(args.credentials, args.config, args.device)

