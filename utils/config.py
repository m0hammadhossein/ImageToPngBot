import urllib.parse
from yaml import safe_load

with open('config.yaml', 'r') as config_file:
    config = safe_load(config_file)
API_ID = config['API_ID']
API_HASH = config['API_HASH']
TOKEN = config['BOT_TOKEN']
SUDO = config['SUDO']
DB_USER = config['DB_USER']
DB_PASS = urllib.parse.quote_plus(config['DB_PASS'])
DB_NAME = config['DB_NAME']
