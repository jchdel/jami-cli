#! /usr/bin/env python3

import gi
gi.require_version('Gtk', '3.0')
from gi.repository import Gtk

#import errorsDring
from controller import libjamiCtrl

########################################################################
# provide callback to Jami daemon D-Bus signals
########################################################################
class MyController(libjamiCtrl):
    #
    # Signal handling
    #     process callbacks in the app
    #
    def onCallIncoming_cb(self, callId):
        onCallIncoming(callId)

    def onCallHangup_cb(self, callId):
        onCallHangup(callId)

    def onCallConnecting_cb(self, callId):
        onCallConnecting(callId)

    def onCallRinging_cb(self, callId):
        onCallRinging(callId)

    def onCallHold_cb(self):
        onCallHold()

    def onCallInactive_cb(self):
        onCallInactive()

    def onCallCurrent_cb(self):
        onCallCurrent()

    def onCallBusy_cb(self):
        onCallBusy()

    def onCallFailure_cb(self):
        onCallFailure()

    def onCallOver_cb(self):
        onCallOver()

    def onIncomingTrustRequest_cb(self, account, conversation, orig, payload, received):
        onIncomingTrustRequest(account, conversation, orig, payload, received)

# stop Jami controller thread
def closeCtrl(something):
    print("about to quit...")
    ctrl.stopThread()
    Gtk.main_quit()

########################################################################
# callbacks
########################################################################

def onCallIncoming(callId):
    pass

def onCallHangup(callId):
    pass

def onCallConnecting(callId):
    pass

def onCallRinging(callId):
    pass

def onCallHold():
    pass

def onCallInactive():
    pass

def onCallCurrent():
    pass

def onCallBusy():
    pass

def onCallFailure():
    pass

def onCallOver():
    pass

def onIncomingTrustRequest(account, conversation, orig, payload, received):
    pass

########################################################################
# Controller in another thread
########################################################################
# jamid MUST be runnig already!

ctrl = MyController("jami", False)
ctrl.daemon = True
ctrl.start()

########################################################################
# Create the main window
########################################################################

window = Gtk.Window()
window.connect("destroy", closeCtrl)
window.show_all()
Gtk.main()
