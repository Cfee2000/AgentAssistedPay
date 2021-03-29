// Class that encapsulates a transaction
class Transaction {
    constructor(callSid, callerId) {
        this.callSid = callSid;
        this.callerId = callerId;
        this.amount = '';
        this.tipPercent = '';
        this.tip = '';
        this.total = '';
        this.cardNum = '';
        this.cardType = '';
        this.createIdempotencyKey();
        this.paymentSid = null;
        this.expiryDate = '';
        this.securityCode = '';
        this.confirmationCode = '';
        this.paymentToken = '';
        this.item = null;
    }

    createIdempotencyKey() {
        const keyLength = 16;
        let digits = '';
        for (var i = 0; i < keyLength; i++) {
            digits += Math.floor(Math.random() * 10); 
        }
        this.idempotencyKey = digits;
    }
}


// App states
const states = Object.freeze({
    idle:           'idle',
    gettingAmount:  'gettingAmount',
    pendingPrompts: 'pendingPrompts',
    gettingCardNum: 'gettingCardNum',
    gettingExpiry:  'gettingExpiry',
    gettingSecCode: 'gettingSecCode',
    pendingSubmit:  'pendingSubmit',
    canceling:      'canceling',
    wrapUp:         'wrapUp'
});

// App events, from UI and from server
const events = Object.freeze({
    callSignaled:   'callSignaled',
    callAnswered:   'callAnswered',
    callEnded:      'callEnded',
    clearPressed:   'clearPressed',
    promptPressed:  'promptPressed',
    submitPressed:  'submitPressed',
    cancelPressed:  'cancelPressed',
    paySuccessful:  'paySuccessful',
    payFailed:      'payFailed',
    payPartial:     'payPartial'
});

// Button enumerations
const buttons = Object.freeze({
    clear:  'clear',
    prompt: 'prompt',
    cancel: 'cancel',
    submit: 'submit'
});


// Global variables
let socket = null;
let state = states.idle;
let transaction = new Transaction()
const sounds = {};


// Format phone number, using libphonenumber.  See https://gitlab.com/catamphetamine/libphonenumber-js.
// TODO: consider putting in a separate library module.
function formatPhoneNumber(num) {
    // Special Twilio phone numbers.  See 
    // https://support.twilio.com/hc/en-us/articles/223179988-Why-am-I-getting-calls-from-these-strange-numbers-
    const specials = {
        "7378742833":   "RESTRICTED",
        "+7378742833":  "RESTRICTED",
        "2562533":      "BLOCKED",
        "+2562533":     "BLOCKED",
        "8566696":      "UNKNOWN",	
        "+8566696":     "UNKNOWN",
        "266696687":    "ANONYMOUS",
        "+266696687":   "ANONYMOUS",	
        "86282452253":  "UNAVAILABLE",
        "+86282452253": "UNAVAILABLE",	
        "464":          "No Caller ID",
        "+464":         "No Caller ID"
    }
    if (num in specials) {
        return specials[num];
    }
    return libphonenumber.parsePhoneNumber(num).formatNational();
}

// When the base amount is entered, normalize the amount to two decimal places,  
// and apply any tip to calculate the total amount.  If there's an amount, we enable 
// the 'Prompt' button, to allow the transaction to be initiated.
function amountChanged() {
    transaction.amount = parseFloat($('#amount').val()).toFixed(2);
    if (transaction.tipPercent) {
        transaction.tip = parseFloat(transaction.amount * transaction.tipPercent/100).toFixed(2);
        transaction.total = parseFloat(+transaction.amount + +transaction.tip).toFixed(2);
    } else if (transaction.tip) {
        transaction.total = parseFloat(+transaction.amount + +transaction.tip).toFixed(2);
    } else {
        transaction.total = transaction.amount;
    }
    displayAmounts();

    // If the amount is non-blank, enable the 'Prompt' and 'Clear' buttons
    if (transaction.amount) {
        enableButton(buttons.clear);
        enableButton(buttons.prompt);
    }
}

// Apply the tip percent, yielding the tip amount, and recalculate the total.
function tipPercentChanged() {
    transaction.tipPercent = $('#tipPercent').val();
    transaction.tip = parseFloat(transaction.amount * transaction.tipPercent/100).toFixed(2);
    transaction.total = parseFloat(+transaction.amount + +transaction.tip).toFixed(2);
    displayAmounts();
}

// If the tip amount was specified directly, blank out the tip percent and recalculate the total.
function tipChanged() {
    transaction.tip = parseFloat($('#tip').val()).toFixed(2);
    transaction.tipPercent = '';
    transaction.total = parseFloat(+transaction.amount + +transaction.tip).toFixed(2);
    displayAmounts();
}

function enableButton(name) {
    const jqName = '#' + name;
    $(jqName).prop('disabled', false);
}

function disableButton(name) {
    const jqName = '#' + name;
    $(jqName).prop('disabled', true);
}

function resetButtons() {
    disableButton(buttons.clear);
    disableButton(buttons.prompt);
    disableButton(buttons.submit);
    disableButton(buttons.cancel);
}

function displayCallerId(callerId) {
    $('#callerId').text(`Call from ${callerId}`); 
}

function clearCallerId() {
    $('#callerId').text('\xA0');  // Non-breaking space maintains spacing in UI
}

function displayAmounts() {
    if (transaction) {
        $('#amount').val(transaction.amount);
        $('#tipPercent').val(transaction.tipPercent);
        $('#tip').val(transaction.tip);
        $('#total').val(transaction.total);
    } else {
        $('#amount').val('');
        $('#tipPercent').val('');
        $('#tip').val('');
        $('#total').val('');
    }
}

function clearAmounts() {
    if (transaction) {
        transaction.amount = '';
        transaction.tip = '';
        transaction.tipPercent = '';
        transaction.total = '';
    }
    displayAmounts();
    $('#amount').focus();
    disableButton(buttons.prompt);
}

function unlockAmounts() {
    $('#amount').prop('readonly', false);
    $('#tip').prop('readonly', false);
    $('#tipPercent').prop('readonly', false);
}

function lockAmounts() {
    $('#amount').prop('readonly', true);
    $('#tip').prop('readonly', true);
    $('#tipPercent').prop('readonly', true);
}

function displayCardInfo() {
    if (transaction) {
        $('#cardNum').val(transaction.cardNum);
        $('#cardType').val(transaction.cardType);
        const expiryDate = transaction.expiryDate.length < 4 ?
            transaction.expiryDate :
            transaction.expiryDate.slice(0,2) + '/' + transaction.expiryDate.slice(2);
        $('#expiryDate').val(expiryDate);
        $('#securityCode').val(transaction.securityCode); 
    } else {
        $('#cardNum').val('');
        $('#cardType').val('');
        $('#expiryDate').val('');
        $('#securityCode').val('');
    }
}

function clearCardInfo() {
    if (transaction) {
        transaction.cardNum = '';
        transaction.cardType = '';
        transaction.expiryDate = '';
        transaction.securityCode = '';
    }
    displayCardInfo();
}

function displayMessage(message) {
    $('#message').text(message);
}

function clearMessage() {
    $('#message').text('\xA0');     // Non-breaking space maintains spacing in UI
}

function resetAll() {
    transaction = null;
    clearAmounts();
    lockAmounts();
    clearCallerId();
    clearCardInfo();
    clearMessage();
    resetButtons();
}

function prepareNewCall(data) {
    const callerId = formatPhoneNumber(data.callerId);
    transaction = new Transaction(data.callSid, callerId);
    displayCallerId(callerId);
}

function prepareNewPayment() {
    transaction = new Transaction(transaction.callSid, transaction.callerId);
    clearAmounts();
    clearCardInfo();
    unlockAmounts();
    resetButtons();
}

function initiatePayment() {
    lockAmounts();
    clearCardInfo();
    disableButton(buttons.prompt);
    disableButton(buttons.clear);
    socket.emit('initiate', transaction);
}

function updateTransaction(data, item=null) {
    if (item) { transaction.item = item; }
    for (property in data) {
        transaction[property] = data[property];
    }
}

function promptForCardNum(data) {
    updateTransaction(data, item='payment-card-number');
    displayMessage("Please enter card number, followed by '#'");
    enableButton(buttons.cancel);
    socket.emit('update', transaction);
}

function promptForExpiry(data) {
    updateTransaction(data, item='expiration-date');
    displayMessage("Please enter 2-digit expiry month followed by 2-digit expiry year");
    displayCardInfo();
    sounds.fieldComplete.play();
    socket.emit('update', transaction);
}

function promptForSecCode(data) {
    updateTransaction(data, item='security-code');
    displayMessage("Please enter 3- or 4-digit security code");
    displayCardInfo();
    sounds.fieldComplete.play();
    socket.emit('update', transaction);    
}

function prepareSubmit(data) {
    updateTransaction(data);
    displayMessage("Press Submit to process payment")
    displayCardInfo();
    sounds.fieldComplete.play();
    enableButton(buttons.submit);
}

function submitPayment() {
    resetButtons();
    socket.emit('submit', transaction);
}

function displayPaymentConfirmation(data) {
    updateTransaction(data);
    if (data.confirmationCode) {
        displayMessage(`Payment successful. Confirmation code: ${data.confirmationCode}`);
    } else {
        displayMessage(`Payment token: ${data.paymentToken}`);
    }
    sounds.transactionSuccess.play();
    disableButton(buttons.submit);
    disableButton(buttons.cancel);
    enableButton(buttons.clear);
}

function clearCurrentItem() {
    switch (transaction.item) {
        case 'payment-card-number': transaction.cardNum = ''; break;
        case 'expiration-date':     transaction.expiryDate = ''; break;
        case 'security-code':       transaction.securityCode = ''; break;
    }
}

function retryItem(data) {
    clearCurrentItem();
    displayCardInfo();
    displayMessage(`${data.message}. Please try again.`);
    socket.emit('update', transaction);
    sounds.fieldError.play();
}

function continueItem(data) {
    updateTransaction(data);
    displayCardInfo();
    sounds.digitClick.play();
}

function restartPayment(data) {
    displayMessage(data.message);
    sounds.transactionFailure.play();
    enableButton(buttons.clear);
    enableButton(buttons.prompt);
    unlockAmounts();
    clearCardInfo();
    transaction.createIdempotencyKey();     // Create fresh transaction idempotency key    
}

function cancelPayment() {
    unlockAmounts();
    clearCardInfo();
    resetButtons();
    enableButton(buttons.prompt);
    enableButton(buttons.clear);
    socket.emit('cancel', transaction);    
}


// The state-event table.
const stateTable = Object.freeze({
    'idle': {
        'callSignaled':  {action: prepareNewCall, next: states.idle},
        'callAnswered':  {action: unlockAmounts, next: states.gettingAmount}
    },
    'gettingAmount': {
        'callEnded':     {action: resetAll, next: states.idle},
        'clearPressed':  {action: clearAmounts, next: states.gettingAmount},
        'promptPressed': {action: initiatePayment, next: states.pendingPrompts}
    },
    'pendingPrompts': {
        'callEnded':     {action: resetAll, next: states.idle},
        'paySuccessful': {action: promptForCardNum, next: states.gettingCardNum},
        'payFailed':     {action: restartPayment, next: states.gettingAmount}
    },
    'gettingCardNum': {
        'callEnded':     {action: resetAll, next: states.idle},
        'cancelPressed': {action: cancelPayment, next: states.canceling},
        'paySuccessful': {action: promptForExpiry, next: states.gettingExpiry},
        'payFailed':     {action: retryItem, next: states.gettingCardNum},
        'payPartial':    {action: continueItem, next: states.gettingCardNum}
    },
    'gettingExpiry': {
        'callEnded':     {action: resetAll, next: states.idle},
        'cancelPressed': {action: cancelPayment, next: states.canceling},
        'paySuccessful': {action: promptForSecCode, next: states.gettingSecCode},
        'payFailed':     {action: retryItem, next: states.gettingExpiry},
        'payPartial':    {action: continueItem, next: states.gettingExpiry}
    },
    'gettingSecCode': {
        'callEnded':     {action: resetAll, next: states.idle},
        'cancelPressed': {action: cancelPayment, next: states.canceling},
        'paySuccessful': {action: prepareSubmit, next: states.pendingSubmit},
        'payFailed':     {action: retryItem, next: states.gettingSecCode},
        'payPartial':    {action: continueItem, next: states.gettingSecCode}
    },
    'pendingSubmit': {
        'callEnded':     {action: resetAll, next: states.idle},
        'cancelPressed': {action: cancelPayment, next: states.canceling},
        'submitPressed': {action: submitPayment, next: states.pendingSubmit},
        'paySuccessful': {action: displayPaymentConfirmation, next: states.wrapUp},
        'payFailed':     {action: restartPayment, next: states.gettingAmount}
    },
    'canceling': {
        'callEnded':     {action: resetAll, next: states.idle},
        'paySuccessful': {action: (data) => displayMessage(data.message), next: states.gettingAmount},
        'payFailed':     {action: (data) => displayMessage(data.message), next: states.gettingAmount}
    },
    'wrapUp': {
        'callEnded':     {action: resetAll, next: states.idle},
        'clearPressed':  {action: prepareNewPayment, next: states.gettingAmount}
    }
});

// The state-event machine.
function processEvent(event, data) {
    console.log(`State=${state}, event=${event}, data=${JSON.stringify(data)}`);

    try {
        let entry = stateTable[state][event];
        entry.action(data);
        state = entry.next;
    }
    catch (err) {
        const message = `Unexpected event ${event} while in ${state} state`;
        console.error(message); 
        resetAll();
        displayMessage(message);
        state = states.idle;
    }
}


$(document).ready(() => {
    // Add event handlers and set initial button states.
    $('#amount').change(amountChanged);
    $('#tipPercent').change(tipPercentChanged);
    $('#tip').change(tipChanged);
    $('#clear').click(() => processEvent(events.clearPressed, null));
    $('#prompt').click(() => processEvent(events.promptPressed, null));
    $('#cancel').click(() => processEvent(events.cancelPressed, null));
    $('#submit').click(() => processEvent(events.submitPressed, null));
    resetButtons();
    $('#amount').focus();
    
    // We'll use the default (unnamed) namespace to communicate with the server over a WebSocket.
    const namespace = '';
    socket = io.connect(
        location.protocol + '//' + document.domain + ':' + location.port + '/' + namespace,
        {transports: ['websocket']}
    );

    socket.on('callSignaled', json => processEvent(events.callSignaled, JSON.parse(json)));
    socket.on('callAnswered', json => processEvent(events.callAnswered, JSON.parse(json)));
    socket.on('callEnded', json => processEvent(events.callEnded, JSON.parse(json)));
    socket.on('paySuccessful', json => processEvent(events.paySuccessful, JSON.parse(json)));
    socket.on('payFailed', json => processEvent(events.payFailed, JSON.parse(json)));
    socket.on('payPartial', json => processEvent(events.payPartial, JSON.parse(json)))

    // Get sound files for effects
    const folder = `${location.protocol}//${location.hostname}/static`;
    sounds.digitClick = new Audio(`${folder}/pop.mp3`);
    sounds.fieldComplete = new Audio(`${folder}/tink.mp3`);
    sounds.fieldError = new Audio(`${folder}/funk.mp3`);
    sounds.transactionSuccess = new Audio(`${folder}/ping.mp3`);
    sounds.transactionFailure = new Audio(`${folder}/basso.mp3`);
})