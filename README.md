# AgentPay

_A simple demo of Agent-Assisted Pay_

## Introduction

This repo contains a simple demo of Agent-Assisted Pay, consisting of a one-page web app, and a server component running on Python/Flask. Here's a sample screenshot:

<img src="https://code.hq.twilio.com/rwelbourn/AgentPay/blob/master/images/Agent_Pay_screenshot.jpg" width=500>

The demonstration consists of a customer making a call to a Twilio phone number whose voice URL points to the server app; the call is forwarded to the phone of a party playing the role of the agent; and the agent enters payment amounts in the web app. When prompted, the customer enters their credit card number, expiry date and security code using their phone's keypad.

The app is by no means production-ready: it has no login/authentication mechanism, and can handle only a single-user. Any attempt to run it with multiple clients will end in tears.

## Pre-requisites

You will need a PCI-enabled Twilio account and a Stripe test account. Follow the steps in [this tutorial](https://www.twilio.com/docs/voice/tutorials/how-capture-your-first-payment-using-pay) to create a Stripe account and configure your Twilio account to connect to it.

This particular app was designed to be used with an Ngrok tunnel, so you will also need an [Ngrok](https://ngrok.com/) account. Otherwise, you will have to host it at a location accessible from the Internet.

## Installation

Clone the repository into the directory containing your projects:

```
git clone https://code.hq.twilio.com/rwelbourn/AgentPay.git
```

Navigate into the newly created `AgentPay` directory. If you're using a [Virtual Environment](https://realpython.com/python-virtual-environments-a-primer/), execute the following commands:

```
python3 -m venv ENV
source ENV/bin/activate
```

Next, install the required Python libraries (`twilio`; must be a recent version with support for Pay):

```
pip install -r requirements.txt
```

## Configuration and invocation

You will require one Twilio phone number for this app. You will setup this number's incoming webhook to receive the inbound calls from a customer (make sure you update the webhook to be an HTTP POST, not a GET). You will then specify a forwarding number (eg. you cell phone number, a softphone, an IP phone, etc) to recieve the call as the agent.

We also recommend you store your Twilio credentials in an OS environment variable. The way we've set this up in this project is to read the OS these variables. See setup.py and app.py for the code where we do this. If you need more info on how to do this, consider watching this video here - https://www.youtube.com/watch?v=5iWhQWVXosU.

Essentially, on Mac, you'll export your Twilio credentials by editing the .bash_profile and exporting the variables like this:

```
export TWILIO_ACCOUNT_SID="ACXXX"
export TWILIO_AUTH_TOKEN="XXX"
export TWILIO_API_KEY="SKXXX"
export TWILIO_API_SECRET="XXX"
```

The above credentials (Account SID and Auth Token) can be found on your Twilio account dashboard. API Keys are found here - https://www.twilio.com/console/voice/settings/api-keys. If you haven't created a key yet, you can do so and make note of the secret, then use those credentials to store as OS environment variable as shown above.

Run Ngrok in one terminal session, using Flask's default port. Make a note of the forwarding URL generated:

```
$ ngrok http 5000
ngrok by @inconshreveable                                                                     (Ctrl+C to quit)

Session Status                online
Account                       Twilio (Plan: Twilio)
Version                       2.3.35
Region                        United States (us)
Web Interface                 http://127.0.0.1:4040
Forwarding                    http://8273aee782d3.ngrok.io -> http://localhost:5000
Forwarding                    https://8273aee782d3.ngrok.io -> http://localhost:5000

Connections                   ttl     opn     rt1     rt5     p50     p90
                              0       0       0.00    0.00    0.00    0.00
```

With that URL, you can now configure the Twilio phone number:

![Configuration screenshot](https://code.hq.twilio.com/rwelbourn/AgentPay/blob/master/images/Twilio_config.jpg)

Here we see our Ngrok tunnel URL, with a parameter `Fwd` which holds the agent's URL-encoded forwarding number.

Run the server in another terminal session:

```
$ python3 app.py
 * Restarting with stat
 * Debugger is active!
 * Debugger PIN: 436-851-366
(69852) wsgi starting up on http://0.0.0.0:5000
(69852) accepted ('127.0.0.1', 62238)
(69852) accepted ('127.0.0.1', 62243)
108.26.192.45,127.0.0.1 - - [23/Oct/2020 19:14:48] "GET / HTTP/1.1" 304 220 0.002525
108.26.192.45,127.0.0.1 - - [23/Oct/2020 19:14:48] "GET /socket.io/?EIO=3&transport=websocket HTTP/1.1" 200 0 12.514889
108.26.192.45,127.0.0.1 - - [23/Oct/2020 19:14:49] "GET /static/favicon.ico HTTP/1.1" 200 432526 0.004836
```

You can now access the web app at your Ngrok URL (in this example, `https://8273aee782d3.ngrok.io`).

## Components

- `app.py` -- main server component
- `config.py` -- server's configuration
- `ngrok.py` -- allows the server to discover its external Ngrok URLs
- `static/index.html` -- web page presentation, style using the Boostrap CSS framework
- `static/app.js` -- web page logic
- `static/favicon.ico` -- it's an owl, obviously
- `static/busy.xml` -- TwiML to return busy signal if the agent is already on a call
- `templates/forward.xml` -- TwiML template to forward a call to the agent

### app.py

`app.py` is a server app that expects a single web client. It keeps one piece of state information: whether or not the client is currently taking a call. It handles inbound calls through webhooks, it interfaces with the Agent-Assisted Pay REST API, and it communicates with the web client through a websocket.

The server handles the following paths:

- `/` and `/index` -- Serve the web page.
- `/forward` -- Inbound call signaled. If the agent is occupied, returns `busy.xml`. Otherwise, returns `forward.xml` to forward the call to the agent, and sets the state to `busy`.
- `/answered` -- Call answered by the agent.
- `/finished` -- Call ended. Resets the state to `idle`.
- `/payresult` -- Callback from the Pay API. Sends an update to the client over the websocket connection.

Commands from the client to `initiate`, `update`, `submit` and `cancel` transactions are received over the websocket, and result in the equivalent Pay API calls.

### app.js

The web page logic handles the entire state of the transaction, and is based around event handlers for button presses and field updates, as well as call events and transaction results received from server over the websocket connection. Commands to process transactions are also sent as JSON over the websocket to the server. The event handlers drive a state machine represented by the following diagram:

<img src="https://code.hq.twilio.com/rwelbourn/AgentPay/blob/master/images/Agent%20Pay%20State%20Machine.jpeg" width="500">

The state machine is codified in [this table](https://docs.google.com/spreadsheets/d/1NOX19Hy0S9NoatZk6ya3XgirElpNwvn-fi0ZRSxtxVk/edit#gid=0).

## Demo script

Once the app is running, share your screen and call the demo number to engage in a customer/agent conversation. Using QuickTime to show your iPhone screen is a nice touch, but not necessary.

1. Call the app's number, and note that the caller id displays in the web page. You can have the JavaScript console window open to show the events being processed:

![JavaScript console](https://code.hq.twilio.com/rwelbourn/AgentPay/blob/master/images/Agent_Pay_console.jpg)

2. Answer the call, muting the receiver to avoid feeback.
3. Enter an amount and a tip in the text boxes. Note how this unlocks the 'Prompt' button, and the use of the 'Clear' button.
4. As the agent, click the 'Prompt' button to begin collecting credit card data. Stripe test numbers [can be found here](https://stripe.com/docs/testing#cards). Note the prompts at the bottom of the web page.
5. Show that incorrectly formatted card numbers, dates or security codes will result in an error message and a prompt to re-enter the incorrect item.
6. Click on 'Submit' to submit the transaction for payment, and note the confirmation code that is returned from Stripe. Show that the test transactions were processed on Stripe, by visiting [this page](https://dashboard.stripe.com/test/payments).

![Stripe dashboard](https://code.hq.twilio.com/rwelbourn/AgentPay/blob/master/images/Stripe_dashboard.jpg)

7. Experiment with card numbers that will return [error codes](https://stripe.com/docs/testing#cards-responses).
8. Click on 'Clear' when wrapping up to enter a new transaction.
9. Show that a zero amount will result in getting a payment token (something that can be stored for a future payment or recurring payments), rather than a confirmation code.
10. Hang up the call.
