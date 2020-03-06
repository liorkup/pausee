from google_auth_oauthlib.flow import InstalledAppFlow
from oauthlib.oauth2.rfc6749.errors import InvalidGrantError
import yaml
import sys

def get_refresh_token(credentials_file):
  with open(credentials_file, 'r') as f:
    credentials = yaml.safe_load(f)
  client_config = {
      'installed': {
          'client_id': credentials['adwords']['client_id'],
          'client_secret': credentials['adwords']['client_secret'],
          'auth_uri': 'https://accounts.google.com/o/oauth2/auth',
          'token_uri': 'https://accounts.google.com/o/oauth2/token',
      }
  }
  flow = InstalledAppFlow.from_client_config(
      client_config, scopes=['https://www.googleapis.com/auth/adwords'])
  flow.redirect_uri = 'urn:ietf:wg:oauth:2.0:oob'
  auth_url, _ = flow.authorization_url(prompt='consent')

  print('Log into the Google Account you use to access your AdWords account '
        'and go to the following URL: \n%s\n' % auth_url)
  print('After approving the token enter the verification code (if specified).')
  code = input('Code: ').strip()

  try:
    flow.fetch_token(code=code)
  except InvalidGrantError as ex:
    print('Authentication has failed: %s' % ex)
    sys.exit(1)

  credentials['adwords']['refresh_token'] = flow.credentials.refresh_token
  with open(credentials_file, 'w') as f:
    yaml.dump(credentials, f, default_flow_style=False)
