
# Pausee

  

A stand-alone Python script to overcome clients limitation of serving a limited number of users in their service. Pausee will periodically query the AppsFlyer API to monitor the app's first_open events and will send alerts or pause campaigns via the AdWords API when number of first_opens acceded a given limit, and will resume the campaigns whenever possible.

  

**This is not an officially supported Google product.**

  

Contact: liorkup@google.com

  
  

## Why?

Some apps might have limitations to the numbers of users that can be served at a time. As App Campaigns budget is daily and not guaranteed to spread evenly during the day, there might be, from time to time, a burst of acquiring new users in a short period that will potentially bring more online users to the app than the app can serve. This might result in a high level of churning users and a potential profit loss. 


## How?

To prevent the situation of acquiring more users than the app can serve, Pausee will periodically query the AppsFlyer API for *first_opens* events attributed to Google Ads in a given period of time and will send an email alert (via Gmail service) and temporary pause campaigns via the AdWords API to help keeping the number of *first_open*s in the next cycle lower than a given number. When the number of new *first_open*s will decrease below the bar, Pausee will resume the campaigns.
 

The solution will run every **cycle** minutes. In each run the following logic will apply:

- If current time is between **from** and **to** ("hot hours to monitor"):
  - if number of first_opens was above **email_alert**: 
    - Send an alert in email
  - If number of first_opens was above **pause_campaigns**:
    - Pause the minimum amount of campaign(s), so the total number of first_opens from the remaining ENABLED campaigns in the last cycle will decrease below #**pause_campaigns**
  - else:
    - Resume the maximum amount of campaign(s), so the total number of first_opens from all ENABLED campaigns will increase be the highest but possible still below #**pause_campaigns**
- else:
  - Resume all paused campaigns by Pausee to ENABLED status
  

**Note** 
- Whenever campaigns status is changed an email will be send with campaign ids and new status.  
- Only campaigns from the provided account can be modified. 
  

  
  

## Requirements

  

- Python 3

- Access to AdWords API (refer to [Apply for access to the AdWords API](https://developers.google.com/adwords/api/docs/guides/signup)).

- OAuth 2 credentials (refer to [Generate OAuth2 credentials](https://developers.google.com/adwords/api/docs/guides/authentication#create_a_client_id_and_client_secret)).

  
## Pausee configurable parameters file: config.yaml


- **af_api_token**: AppsFlyer API Token. 

- **app_ids**: List of Android/iOS app ids in Account. E.g: *id1234567890* or *com.game.cool* 

- **lookback**: *M* (minutes ) - Query from AppsFlyer API number of First Opens from the last M minutes

- **repeat**: *R* (minutes) - Run script every R minutes

- **email_alert**: *A* - Send email alert if number of First Opens attributed to Google Ads was above 

- **pause_campaigns**: *P* - Pause Campaign(s) if the number of First Opens attributed to Google Ads was above *P* so the number of active campaign's First opens in the last run will be below *P*

- **timezone**: e.g.: *'Asia/Jerusalem'*

- **from** and **to**: Run pause logic between 'from' and 'to' in **timezone**. E.g.: from: 20 to: 8. Between 8 and 20 all campaigns will be activated again 

- **email**: gmail credentials  

## Setup

  ```bash

cd pausee

```

0. Optional step: consider using [virtualenv](https://virtualenv.pypa.io/en/latest/) to isolate the Python environment and libraries:


```bash

python3 -m venv .venv

. .venv/bin/activate

```
 

1. Install required Python packages:

  

```bash
pip install --upgrade pip

pip install -r requirements.txt

```

  

2. Edit `googleads.yaml` and replace placeholders with your Google Ads account ID, OAuth 2.0 credentials and Developer Token

  

3. Acquire OAuth 2.0 refresh token running the script with `-a` option and

following on-screen prompts (navigate to the URL provided in the screen, authorise the project, and paste the provided Code in the command-line):

  

```bash

python pausee.py -a

```

4. Set parameters in `config.yaml` file: **af_api_token**, **af_api_token**, **lookback**, **repeat**, **email_alert**, **pause_campaigns**, **timezone**, **from** & **to**, **user** & **password** (Gmail)

 
5. Email configuration: In order to send an email from the script, the Gmail security configuration must be set as ["Less Secure"](https://support.google.com/accounts/answer/6010255?p=less-secure-apps&hl=en&visit_id=637191974435816898-1573783562&rd=1). It is highly advised to use a dedicated Gmail account and not your personal account to prevent an exposure of your personal credentials.

## Running Paussee locally



Run the script once:

  

```bash

./run.sh

```


For scheduled run (every *cycle* minutes):

  

```bash

./run.sh -s

```


## Command line options

  

Run the script with `-h` option to see available options:

  

```bash

python pausee.py -h

```

  

Expected output:

  

```

usage: python pausee.py [-h] [-g CREDENTIALS] [-a]

  

optional arguments:

-h, --help show this help message and exit

-a, --auth authenticate in Google Ads and store refresh token in the credentials file

```



## Licensing

  

Copyright 2019 Google Inc. All Rights Reserved.

  

Licensed under the Apache License, Version 2.0 (the "License");

you may not use this file except in compliance with the License.

You may obtain a copy of the License at

  

http://www.apache.org/licenses/LICENSE-2.0

  

Unless required by applicable law or agreed to in writing, software

distributed under the License is distributed on an "AS IS" BASIS,

WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.

See the License for the specific language governing permissions and

limitations under the License.