"""Configuration items"""

import ngrok 

# Port for Flask to run on.  Defaults to 5000.
PORT = 5000

# External URL and hostname for the server, e.g. an Ngrok tunnel.  
# If not defined, defaults to localhost.
SERVER_URL = None
SERVER_NAME = None
_urls = ngrok.get_public_urls()
if _urls:
    SERVER_URL = _urls[0]
    SERVER_NAME = SERVER_URL[SERVER_URL.find('://') + 3 : ]
