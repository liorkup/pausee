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
from googleads import adwords
import pytz
import yaml
import json
from appsflyerreport import installs_report
import pandas as pd
from io import StringIO
from refreshtoken import get_refresh_token
import gmail
import logging

CONFIG_FILE = 'config.yaml'
GOOGLEADS_FILE = 'googleads.yaml'
PAUSED_DB = 'pausedids.json'

STATUS = {
    'PAUSED': 'PAUSED',
    'ENABLED': 'ENABLED'
}

cfg = None


def get_installs_report():
    app_ids = cfg['app_ids']
    lookback = cfg['params']['lookback']
    timezone = cfg['params']['timezone']
    af_api_token = cfg['af_api_token']

    return list(map(lambda app_id: installs_report(af_api_token, app_id, timezone, lookback), app_ids))


def load_cfg(config_file):
    global cfg
    with open(config_file, 'r') as stream:
        try:
            cfg = yaml.safe_load(stream)
        except yaml.YAMLError as exc:
            logging.info(exc)


def email_alert(installs_count):
    email_cfg = cfg['email']
    if installs_count > cfg['params']['email_alert']:
        message = email_cfg['messages']['alert']
        body = message['body'].format(installs_count, cfg['params']['lookback'])
        gmail.send_mail(email_cfg['email'], email_cfg['password'], email_cfg['to'], message['title'], body)
        logging.info('Alert sent in email')


def email_campaigns_status_changed(mutated_campaign_names, failed_campaign_names, status):
    if mutated_campaign_names or failed_campaign_names:
        email_cfg = cfg['email']
        message = email_cfg['messages']['mutate']
        body = message['body'].format(status, mutated_campaign_names, status, failed_campaign_names)
        gmail.send_mail(email_cfg['email'], email_cfg['password'], email_cfg['to'], message['title'], body)
        logging.info('Mutate notice sent in email')


def campaigns_to_pause(campaigns_dict, tot_installs_count, pause_limit):
    cur_installs_count = 0
    campaigns_to_pause_dict = {}
    for campaign in campaigns_dict.items():
        count = campaign[1]['count']
        cur_installs_count += count
        campaigns_to_pause_dict.update({campaign[0]: campaign[1]})
        if tot_installs_count - cur_installs_count < pause_limit:
            break
    return campaigns_to_pause_dict


def campaigns_to_resume(installs_count):
    campaigns_dict = read_paused_campaigns()
    pause_limit = cfg['params']['pause_campaigns']
    paused_campaigns_sorted = sorted(campaigns_dict.items(), key=lambda item: int(item[1]['count']))
    campaigns_to_resume_dict = {}
    to_resume_installs_count = 0
    for campaign in paused_campaigns_sorted:
        to_resume_installs_count += int(campaign[1]['count'])
        if installs_count + to_resume_installs_count >= pause_limit:
            break
        campaigns_to_resume_dict.update({campaign[0]: campaign[1]})
    return campaigns_to_resume_dict


def mutate_campaigns(campaigns_dict, status):
    operations = [{
        'operator': 'SET',
        'operand': {
            'id': None,
            'status': status
        }
    }]

    mutated_ids = []
    failed_ids = []
    campaign_ids = list(campaigns_dict.keys())
    logging.info("Setting status {} for campaigns_ids {}".format(status, campaign_ids))
    for campaign_id in campaign_ids:
        operations[0]['operand']['id'] = campaign_id

        try:
            client = adwords.AdWordsClient.LoadFromStorage(GOOGLEADS_FILE)
            campaign_service = client.GetService('CampaignService', version='v201809')
            campaign_service.mutate(operations)
            logging.info("Set status: {} for campaign id: {} with {} installs".format(status, campaign_id,
                                                                                      campaigns_dict[campaign_id]))
            mutated_ids.append(campaign_id)
        except Exception:
            logging.info("Failed to set status {} for campaign id {}".format(status, campaign_id))
            failed_ids.append(campaign_id)
    return mutated_ids, failed_ids


def save_paused_campaigns(paused_campaigns_saved):
    logging.info("Saving paused campaigns list: {}".format(paused_campaigns_saved))
    json_paused = json.dumps(paused_campaigns_saved)
    f = open(PAUSED_DB, "w")
    f.write(json_paused)
    f.close()


def read_paused_campaigns():
    with open(PAUSED_DB) as json_file:
        return json.load(json_file) or {}


def enable_campaigns(campaigns_to_resume_dict):
    logging.info('Enabling campaigns..')
    paused_campaigns_dict = read_paused_campaigns()
    mutated_ids = mutate_campaigns_status(campaigns_to_resume_dict, STATUS['ENABLED'])
    for campaign_id in mutated_ids:
        paused_campaigns_dict.pop(campaign_id, None)
    save_paused_campaigns(paused_campaigns_dict)


def pause_campaigns(active_campaigns_dict, installs_count, pause_limit):
    logging.info('Pausing campaigns..')
    enabled_campaign_ids = set(int(campaign_id) for campaign_id in get_enabled_campaigns())
    # if campaign was paused externally, skip it (no pause and no resume later)
    active_and_enabled_campaigns_dict = {k: v for k, v in active_campaigns_dict.items() if
                                         int(k) in enabled_campaign_ids}
    enabled_campaigns_to_pause_dict = campaigns_to_pause(active_and_enabled_campaigns_dict, installs_count, pause_limit)
    mutated_ids = mutate_campaigns_status(enabled_campaigns_to_pause_dict, STATUS['PAUSED'])
    paused_campaigns_dict = read_paused_campaigns()
    for campaign_id in mutated_ids:
        paused_campaigns_dict.update({campaign_id: enabled_campaigns_to_pause_dict[campaign_id]})
    save_paused_campaigns(paused_campaigns_dict)


def get_enabled_campaigns():
    selector = {
        'fields': ['Id'],
        'predicates': [
            {
                'field': 'AdvertisingChannelSubType',
                'operator': 'EQUALS',
                'values': 'UNIVERSAL_APP_CAMPAIGN'
            },
            {
                'field': 'Status',
                'operator': 'EQUALS',
                'values': 'ENABLED'
            },
        ]
    }
    client = adwords.AdWordsClient.LoadFromStorage(GOOGLEADS_FILE)
    campaign_service = client.GetService('CampaignService', version='v201809')
    campaign_page = campaign_service.get(selector)
    return [c['id'] for c in campaign_page['entries']]


def mutate_campaigns_status(campaigns_dict, status):
    (mutated_ids, failed_ids) = mutate_campaigns(campaigns_dict, status)
    mutated_campaign_names = []
    failed_campaign_names = []
    for k in mutated_ids:
        campaign_count_name = campaigns_dict[k]
        mutated_campaign_names.append(campaign_count_name['Campaign'])
    for k in failed_ids:
        campaign_count_name = campaigns_dict[k]
        failed_campaign_names.append(campaign_count_name['Campaign'])
    email_campaigns_status_changed(mutated_campaign_names, failed_campaign_names, status)
    return mutated_ids


def is_in_timeframe():
    tz = pytz.timezone(cfg['params']['timezone'])
    hour_from = datetime.datetime.strptime(str(cfg['params']['from']), '%H')
    hour_to = datetime.datetime.strptime(str(cfg['params']['to']), '%H')
    hour_now = datetime.datetime.strptime(str(datetime.datetime.now(tz).hour), '%H')
    day_delta = datetime.timedelta(days=1)
    if hour_from >= hour_to:
        hour_to += day_delta

    return hour_from <= hour_now < hour_to or hour_from <= hour_now + day_delta < hour_to


def pausee():
    logging.info("Running Pausee!")

    # Out of timeframe resume all paused campaigns
    if not is_in_timeframe():
        logging.info("Out of timeframe: Enabling all campaigns")
        enable_campaigns(read_paused_campaigns())

    # In timeframe:
    else:
        campaigns_df = pd.concat(
            list(map(lambda report: pd.read_csv(StringIO(report), sep=","), get_installs_report())))
        installs_count = len(campaigns_df.index)
        alert_limit = cfg['params']['email_alert']
        pause_limit = cfg['params']['pause_campaigns']

        if installs_count > alert_limit:
            logging.info("Installs above alert limit")
            email_alert(installs_count)

        if installs_count > pause_limit:
            logging.info("Installs above limit")
            campaigns_sorted_by_install = campaigns_df.groupby(['Campaign ID', 'Campaign']).size().reset_index(
                name='count').sort_values(by=['count'])
            active_campaigns_dict = campaigns_sorted_by_install.set_index("Campaign ID").to_dict(orient="index")
            pause_campaigns(active_campaigns_dict, installs_count, pause_limit)

        else:
            logging.info("Installs below pause limit")
            # More first_opens than alert_limit but less than pause_limit level => Email Alert
            enable_campaigns(campaigns_to_resume(installs_count))


def setup_logs():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        handlers={
            logging.FileHandler("pausee.log"),
            logging.StreamHandler()
        }
    )


load_cfg(CONFIG_FILE)

if __name__ == '__main__':

    parser = argparse.ArgumentParser(prog='python pausee.py')
    parser.add_argument('-g', '--credentials', type=str,
                        default='googleads.yaml',
                        help='Google Ads credentials file')
    group = parser.add_mutually_exclusive_group()
    group.add_argument('-a', '--auth', action='store_true', default=False,
                       help=('authenticate in Google Ads and store refresh'
                             ' token in the credentials file'))

    args = parser.parse_args()

    if args.auth:
        get_refresh_token(args.credentials)
    else:
        setup_logs()
        pausee()
