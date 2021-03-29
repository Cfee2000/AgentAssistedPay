"""
Sets up a Flask- and SocketIO-based server to demonstrate Twilio Agent-Assisted Pay.
The agent uses a single-page web app to communicate with the server.
"""

import os
import sys
import json
import config

from flask import Flask, request, render_template, abort, url_for
from flask_socketio import SocketIO
from twilio.rest import Client
from twilio.base.exceptions import TwilioRestException


# Pay-specific error codes.  See https://www.twilio.com/docs/api/errors#6-anchor.
PAY_ERROR_CODES = {
    64001: 'Twilio Pay configuration error',
    64002: 'Twilio Pay service unavailable',
    64003: 'Invalid charge amount',
    64004: 'Twilio Pay: invalid paymentConnector attribute',
    64005: 'Twilio Pay connector does not support tokenization',
    64006: 'Twilio Pay connector does not support token type',
    64007: 'Twilio Pay connector does not support creating charge',
    64008: 'Twilio Pay: payment gateway rejected charge creation',
    64009: 'Twilio is no longer authorized to initiate transactions on your behalf',
    64010: 'Twilio Pay: payment gateway rejected token creation',
    64011: 'Twilio Pay connector does not support the requested currency',
    64012: 'Twilio Pay: payment gateway rejected the card',
    64013: 'Twilio Pay: connector does not support supplied paymentMethod attribute',
    64014: 'Twilio Pay: ECP/ACH requires AVSName parameter in the verb',
    64015: 'Twilio <Pay> verb is missing needed parameter',
    64016: 'Twilio Pay: invalid action URL',
    64017: 'Twilio Pay: BankAccountType parameter is not supported with PaymentMethod="credit-card"',
    64018: 'Twilio Pay: value needed for either Capture or Status parameters',
    64019: 'Twilio Pay: required payment information incomplete',
    64020: 'Twilio Pay: invalid parameter value',
    64021: 'Twilio Pay: invalid operation'
}

CARD_TYPES = {
    'visa':         'Visa',
    'mastercard':   'Mastercard',
    'amex':         'Amex',
    'discover':     'Discover',
    'jcb':          'JCB',
    'maestro':      'Maestro',
    'diners-club':  'Diners Club'
}

CARD_LIST = ' '.join(CARD_TYPES.keys())


# NEVER put your account credentials in a source code file!
TWILIO_ACCOUNT_SID = os.environ.get('TWILIO_ACCOUNT_SID')
TWILIO_AUTH_TOKEN = os.environ.get('TWILIO_AUTH_TOKEN')
TWILIO_API_KEY = os.environ.get('TWILIO_API_KEY')
TWILIO_API_SECRET = os.environ.get('TWILIO_API_SECRET')


# Initialize Flask.  The SocketIO cors_allowed_origins param allows HTTPS to be used.
app = Flask(__name__)
socketio = SocketIO(app, cors_allowed_origins=[])
if config.SERVER_NAME:
    app.config['SERVER_NAME'] = config.SERVER_NAME

# Create Twilio Client object.
client = Client(TWILIO_API_KEY, TWILIO_API_SECRET, TWILIO_ACCOUNT_SID) if TWILIO_API_KEY \
    else Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)

# Initialize call state.
call_state = "idle"


# Normalize an error message returned from the Pay API.
def normalize_message(message):
    return message.replace('-', ' ').capitalize()


# Signal that the REST API transaction failed.
def api_failed(transaction, exception):
    if exception.code:
        if exception.code in PAY_ERROR_CODES.keys():
            message = PAY_ERROR_CODES[exception.code]
        else:
            message = f"Twilio Pay error code {exception.code}"
    else:
        message = exception.msg

    print(message)
    transaction['message'] = message
    socketio.emit('payFailed', json.dumps(transaction))


# Initiate a payment on the call.
def initiate_payment(transaction):
    try:
        client.calls(transaction['callSid']).payments.create(
            transaction["idempotencyKey"],
            url_for('pay_result', _external=True),
            charge_amount=transaction['total'],
            description=f"Payment by {transaction['callerId']} with call SID {transaction['callSid']}",
            postal_code=False,
            valid_card_types=CARD_LIST
        )

    except TwilioRestException as ex:
        api_failed(transaction, ex)


# Update, complete or cancel a transaction.
def update_payment(transaction, capture=None, status=None):
    try:
        client.calls(transaction['callSid']).payments(transaction['paymentSid']).update(
            transaction["idempotencyKey"],
            url_for('pay_result', _external=True),
            capture=capture,
            status=status
        )

    except TwilioRestException as ex:
        api_failed(transaction, ex)


# Display the web app.
@app.route('/', methods=['GET', 'POST'])
@app.route('/index', methods=['GET', 'POST'])
def index():
    return app.send_static_file('index.html')


# Process inbound call. Forward to the agent if not busy, otherwise reject.
@app.route('/forward', methods=['POST'])
def inbound_call():
    global call_state
    if call_state == "idle":
        fwd = request.values.get("Fwd")
        if fwd is None:
            abort(400, "No forwarding number provided")

        # Pass caller info to browser
        call_sid = request.values.get("CallSid")
        caller_id = request.values.get("From")
        socketio.emit('callSignaled', json.dumps(
            {"callSid": call_sid, "callerId": caller_id}))

        # Update call state and forward the call
        print(f"inbound_call: idle; Call SID={call_sid}")
        call_state = "busy"
        return render_template(
            'forward.xml',
            Fwd=fwd,
            action_url=url_for('call_ended'),
            status_url=url_for('call_answered')
        ), {'Content-Type': 'text/xml'}

    else:
        print("inbound_call: busy")
        return app.send_static_file('busy.xml'), {'Content-Type': 'text/xml'}


# Inform web app that the call was answered.
@app.route('/answered', methods=['POST'])
def call_answered():
    print("call_answered")
    call_sid = request.values.get("CallSid")
    socketio.emit('callAnswered', json.dumps({"callSid": call_sid}))
    return '', 204


# Update call state and inform web app that the call was ended.
@app.route('/finished', methods=['POST'])
def call_ended():
    print("call_ended")
    global call_state
    call_state = "idle"
    call_sid = request.values.get("CallSid")
    socketio.emit('callEnded', json.dumps({"callSid": call_sid}))
    return '', 204


# Communicate the result of the Pay operation to the web browser.
@app.route('/payresult', methods=['POST'])
def pay_result():
    call_sid = request.values.get('CallSid')
    payment_sid = request.values.get('Sid')
    card_num = request.values.get('PaymentCardNumber')
    card_type = request.values.get('PaymentCardType')
    expiry_date = request.values.get('ExpirationDate')
    security_code = request.values.get('SecurityCode')
    confirmation_code = request.values.get('PaymentConfirmationCode')
    payment_token = request.values.get('PaymentToken')
    profile_id = request.values.get('ProfileId')
    result = request.values.get('Result')
    error_type = request.values.get('ErrorType')
    pay_error_code = request.values.get('PayErrorCode')
    connector_error = request.values.get('ConnectorError')
    pay_error = request.values.get('PaymentError')
    partial_result = request.values.get('PartialResult')
    print(f"pay_result: {request.values}")

    transaction = {'callSid': call_sid, 'paymentSid': payment_sid}
    if error_type:
        transaction['message'] = normalize_message(error_type)
        socketio.emit('payFailed', json.dumps(transaction))
    elif pay_error:
        transaction['message'] = pay_error
        socketio.emit('payFailed', json.dumps(transaction))
    else:
        if card_num:
            transaction['cardNum'] = card_num
        if card_type:
            transaction['cardType'] = CARD_TYPES[card_type]
        if expiry_date:
            transaction['expiryDate'] = expiry_date
        if security_code:
            transaction['securityCode'] = security_code
        if confirmation_code:
            transaction['confirmationCode'] = confirmation_code
        if payment_token or profile_id:
            transaction['paymentToken'] = payment_token if payment_token else profile_id
        if result:
            transaction['message'] = normalize_message(result)
        if partial_result and partial_result == 'true':
            socketio.emit('payPartial', json.dumps(transaction))
        else:
            socketio.emit('paySuccessful', json.dumps(transaction))

    return '', 204


# Start the payment process.
@socketio.on('initiate')
def do_initiate(transaction):
    print("Initiating payment")
    initiate_payment(transaction)


# Update the payment.
@socketio.on('update')
def do_update(transaction):
    print("Updating payment")
    update_payment(transaction, capture=transaction['item'])


# Submit the payment for processing.
@socketio.on('submit')
def do_submit(transaction):
    print("Submitting payment")
    update_payment(transaction, status='complete')


# Cancel the payment.
@socketio.on('cancel')
def do_cancel(transaction):
    print("Canceling payment")
    update_payment(transaction, status='cancel')


if __name__ == "__main__":
    socketio.run(app, host='0.0.0.0', port=config.PORT, debug=True)
