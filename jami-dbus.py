import os
from gi.repository import Gio, GLib, GObject
from loguru import logger
import time

try:
    _
except NameError:
    from gettext import gettext as _

DBUS_DEAMON_OBJECT = 'cx.ring.Ring'
DBUS_DEAMON_PATH = '/cx/ring/Ring'

"""Internal exceptions"""

class CtrlError(Exception):
    """Base class for all our exceptions."""

    def __init__(self, help=None):
        self.help = str(help)

    def __str__(self):
        return self.help

class CtrlDBusError(CtrlError):
    """General error for dbus communication"""

class CtrlDeamonError(CtrlError):
    """General error for daemon communication"""

class CtrlAccountError(CtrlError):
    """General error for account handling"""


class Monitor(GObject.Object):
    """
    Monitors the status of the WTF daemon
    """
    __gsignals__ = {
        'daemon-status-changed': (GObject.SignalFlags.RUN_FIRST, None, (str, str)),
    }

    def __init__(self):
        """Initialize the WTF Monitor."""
        try:
            super().__init__()
            self.connected = False

            try:
                self.bus = Gio.bus_get_sync(Gio.BusType.SESSION, None)

                self.watcher_id = Gio.bus_watch_name(
                    Gio.BusType.SESSION,
                    DBUS_DEAMON_OBJECT,
                    Gio.BusNameWatcherFlags.NONE,
                    self._on_name_appeared,
                    self._on_name_vanished
                )
            except Exception as e:
                logger.error(f"[Monitor] Fatal Init Error: {e}")
                self.emit('daemon-status-changed', 'error', str(e))
        except Exception as e:
            logger.error(f"[Monitor] Init error: {e}")

    def _on_name_appeared(self, connection, name, name_owner):
        """Handle service appearance."""
        try:
            logger.info(f"[Monitor] Service {name} appeared.")
            self.emit('daemon-status-changed', 'connected', 'Ready')
            self.connected = True
        except Exception as e:
            logger.error(f"[Monitor] On name appeared error: {e}")

    def _on_name_vanished(self, connection, name):
        """Handle service disappearance."""
        try:
            logger.warning(f"[Monitor] Service {name} vanished.")
            self.emit('daemon-status-changed', 'offline', 'WTFd service stopped')
            self.connected = False
        except Exception as e:
            logger.error(f"[Monitor] On name vanished error: {e}")
#
# Main class
#

class JamiManager(GObject.Object):
    """
    Manages voice calls and messages via daemon.
    """
    __gsignals__ = {
        'accounts-changed': (GObject.SignalFlags.RUN_FIRST, None, ()),
        'contact-added': (GObject.SignalFlags.RUN_FIRST, None, (str, )),
        'call-added': (GObject.SignalFlags.RUN_FIRST, None, (str, object)),
        'call-started': (GObject.SignalFlags.RUN_FIRST, None, (str, object)),
        'call-removed': (GObject.SignalFlags.RUN_FIRST, None, (str,)),
        'call-changed': (GObject.SignalFlags.RUN_FIRST, None, (str, str)),
        'call-missed': (GObject.SignalFlags.RUN_FIRST, None, (str,)),
        'call-refused': (GObject.SignalFlags.RUN_FIRST, None, (str,)),
        'call-hangup': (GObject.SignalFlags.RUN_FIRST, None, (str, int,)),
        'daemon-connection-status': (GObject.SignalFlags.RUN_FIRST, None, (str, str)),
        'presence-changed': (GObject.SignalFlags.RUN_FIRST, None, (str, int)),
        'trust-request': (GObject.SignalFlags.RUN_FIRST, None, (str, str)),
    }

    def __init__(self):
        """Initialize the daemon manager"""
        try:
            super().__init__()

            # internals
            self.name = "What.The.Fog" # client name
            self.registered = False
            self.bus = None
            self.proxy_instance = None
            self.proxy_callmgr = None
            self.proxy_confmgr = None
            self.proxy_videomgr = None
            self.proxy_presmgr = None
            self.proxy_plugins = None

            # to know when daemon is present
            self.daemon_monitor = Monitor()
            self.daemon_monitor.connect('daemon-status-changed', self._on_daemon_status)

            # application state 
            self.activeCalls = {}  # list of active calls (known by the client)
            self.activeConferences = {}  # list of active conferences
            self.account = None  # current active account
            self.autoAnswer = False

            self.contacts = {} # k=name, v=uri
            self.cachedContactsList = {} # k=uri, v=details[]
            self.stcatnoc = {} # k=uri, v=name
            self.buddyUriList = {}  # list of buddy URI list: k=uri, v=presence
            self.invalidBuddyUris = []  # list of forbidden buddy URI

            self.currentCallId = None
            self.currentConfId = None

            # for automatic trust negotiation
            self.trust_initiator = False
            self.wait_for_trust = False
            self.tmpcode = ""

        except Exception as e:
            logger.error(f"[Manager] Init error: {e}")

    ####################################################################
    # Signal dispatchers
    ####################################################################

    def on_instance_signal(self, proxy, sender, signal, params):
        """ complete; there is only a single signal! """
        params = params.unpack()
        logger.debug(f"{signal}: {params}")
        if not signal:
            pass
        elif signal == "started":
            pass
        else:
            logger.warning(f"[Instance] Unexpected signal '{signal}' received")

    def on_callmgr_signal(self, proxy, sender, signal, params):
        """ complete """
        params = params.unpack()
        logger.debug(f"{signal}: {params}")
        if not signal:
            pass
        elif signal == "recordPlaybackFilepath":
            self.on_recordPlaybackFilepath(*params)
        elif signal == "recordPlaybackStopped":
            self.on_recordPlaybackStopped(*params)
        elif signal == "updatePlaybackScale":
            self.on_updatePlaybackScale(*params)
        elif signal == "incomingCall":
            self.on_incomingCall(*params)
        elif signal == "mediaChangeRequested":
            self.on_mediaChangeRequested(*params)
        elif signal == "incomingMessage":
            self.on_incomingMessage(*params)
        elif signal == "callStateChanged":
            self.on_callStateChanged(*params)
        elif signal == "conferenceChanged":
            self.on_conferenceChanged(*params)
        elif signal == "conferenceCreated":
            self.on_conferenceCreated(*params)
        elif signal == "conferenceRemoved":
            self.on_conferenceRemoved(*params)
        elif signal == "voiceMailNotify":
            self.on_voiceMailNotify(*params)
        elif signal == "transferSucceeded":
            self.on_transferSucceeded(*params)
        elif signal == "transferFailed":
            self.on_transferFailed(*params)
        elif signal == "recordingStateChange":
            self.on_recordingStateChange(*params)
        elif signal == "onRtcpReportReceived":
            self.on_onRtcpReportReceived(*params)
        elif signal == "peerHold":
            self.on_peerHold(*params)
        elif signal == "audioMuted":
            self.on_audioMuted(*params)
        elif signal == "videoMuted":
            self.on_videoMuted(*params)
        elif signal == "onConferenceInfosUpdated":
            self.on_onConferenceInfosUpdated(*params)
        elif signal == "remoteRecordingChanged":
            self.on_remoteRecordingChanged(*params)
        elif signal == "mediaNegotiationStatus":
            self.on_mediaNegotiationStatus(*params)
        # added as seen in the wild even if not documented
        elif signal == "incomingCallWithMedia":
            self.on_incomingCallWithMedia(*params)
        else:
            logger.warning(f"[CallManager] Unexpected signal '{signal}' received")

    def on_confmgr_signal(self, proxy, sender, signal, params):
        """ complete """
        params = params.unpack()
        logger.debug(f"{signal}: {params}")
        if signal == "deviceAuthStateChanged":
            self.on_deviceAuthStateChanged(*params)
        elif signal == "addDeviceStateChanged":
            self.on_addDeviceStateChanged(*params)
        elif signal == "deviceRevocationEnded":
            self.on_deviceRevocationEnded(*params)
        elif signal == "accountProfileReceived":
            self.on_accountProfileReceived(*params)
        elif signal == "knownDevicesChanged":
            self.on_knownDevicesChanged(*params)
        elif signal == "registeredNameFound":
            self.on_registeredNameFound(*params)
        elif signal == "nameRegistrationEnded":
            self.on_nameRegistrationEnded(*params)
        elif signal == "userSearchEnded":
            self.on_userSearchEnded(*params)
        elif signal == "incomingAccountMessage":
            self.on_incomingAccountMessage(*params)
        elif signal == "accountMessageStatusChanged":
            self.on_accountMessageStatusChanged(*params)
        elif signal == "needsHost":
            self.on_needsHost(*params)
        elif signal == "activeCallsChanged":
            self.on_activeCallsChanged(*params)
        elif signal == "profileReceived":
            self.on_profileReceived(*params)
        elif signal == "composingStatusChanged":
            self.on_composingStatusChanged(*params)
        elif signal == "volumeChanged":
            self.on_volumeChanged(*params)
        elif signal == "hardwareDecodingChanged":
            self.on_hardwareDecodingChanged(*params)
        elif signal == "hardwareEncodingChanged":
            self.on_hardwareEncodingChanged(*params)
        elif signal == "audioDeviceEvent":
            self.on_audioDeviceEvent(*params)
        elif signal == "audioMeter":
            self.on_audioMeter(*params)
        elif signal == "accountsChanged":
            self.on_accountsChanged(*params)
        elif signal == "accountDetailsChanged":
            self.on_accountDetailsChanged(*params)
        elif signal == "registrationStateChanged":
            self.on_registrationStateChanged(*params)
        elif signal == "volatileAccountDetailsChanged":
            self.on_volatileAccountDetailsChanged(*params)
        elif signal == "stunStatusFailure":
            self.on_stunStatusFailure(*params)
        elif signal == "errorAlert":
            self.on_errorAlert(*params)
        elif signal == "certificateStateChanged":
            self.on_certificateStateChanged(*params)
        elif signal == "certificatePinned":
            self.on_certificatePinned(*params)
        elif signal == "certificatePathPinned":
            self.on_certificatePathPinned(*params)
        elif signal == "certificateExpired":
            self.on_certificateExpired(*params)
        elif signal == "incomingTrustRequest":
            self.on_incomingTrustRequest(*params)
        elif signal == "contactAdded":
            self.on_contactAdded(*params)
        elif signal == "contactRemoved":
            self.on_contactRemoved(*params)
        elif signal == "mediaParametersChanged":
            self.on_mediaParametersChanged(*params)
        elif signal == "migrationEnded":
            self.on_migrationEnded(*params)
        elif signal == "dataTransferEvent":
            self.on_dataTransferEvent(*params)
        elif signal == "swarmLoaded":
            self.on_swarmLoaded(*params)
        elif signal == "messagesFound":
            self.on_messagesFound(*params)
        elif signal == "swarmMessageReceived":
            self.on_swarmMessageReceived(*params)
        elif signal == "swarmMessageUpdated":
            self.on_swarmMessageUpdated(*params)
        elif signal == "reactionAdded":
            self.on_reactionAdded(*params)
        elif signal == "reactionRemoved":
            self.on_reactionRemoved(*params)
        elif signal == "conversationProfileUpdated":
            self.on_conversationProfileUpdated(*params)
        elif signal == "conversationRequestReceived":
            self.on_conversationRequestReceived(*params)
        elif signal == "conversationRequestDeclined":
            self.on_conversationRequestDeclined(*params)
        elif signal == "conversationReady":
            self.on_conversationReady(*params)
        elif signal == "conversationRemoved":
            self.on_conversationRemoved(*params)
        elif signal == "conversationMemberEvent":
            self.on_conversationMemberEvent(*params)
        elif signal == "onConversationError":
            self.on_onConversationError(*params)
        elif signal == "conversationPreferencesUpdated":
            self.on_conversationPreferencesUpdated(*params)
        elif signal == "debugMessageReceived":
            self.on_debugMessageReceived(*params)
        elif signal == "messageSend":
            self.on_messageSend(*params)
        # added after observing the signil ine wild even if it is not documented
        elif signal == "messageReceived":
            self.on_messageReceived(*params)
        else:
            logger.warning(f"[ConfigurationManager] Unexpected signal '{signal}' received")


    def on_videomgr_signal(self, proxy, sender, signal, params):
        """ complete; there are 4 signals! """
        params = params.unpack()
        logger.debug(f"{signal}: {params}")
        if signal == None:
            pass
        elif signal == "deviceEvent":
            self.on_deviceEvent(*params)
        elif signal == "decodingStarted":
            self.on_decodingStarted(*params)
        elif signal == "decodingStopped":
            self.on_decodingStopped(*params)
        elif signal == "fileOpened":
            self.on_fileOpened(*params)
        else:
            logger.warning(f"[VideoManager] Unexpected signal '{signal}' received")


    def on_presmgr_signal(self, proxy, sender, signal, params):
        """ complete; there are 4 signals! """
        params = params.unpack()
        logger.debug(f"{signal}: {params}")
        if not signal:
            pass
        elif signal == "newBuddyNotification":
            self.on_newBuddyNotification(*params)
        elif signal == "nearbyPeerNotification":
            self.on_nearbyPeerNotification(*params)
        elif signal == "subscriptionStateChanged":
            self.on_subscriptionStateChanged(*params)
        elif signal == "newServerSubscriptionRequest":
            self.on_newServerSubscriptionRequest(*params)
        elif signal == "serverError":
            self.on_serverError(*params)
        else:
            logger.warning(f"[PresenceManager] Unexpected signal '{signal}' received")

    def on_plugins_signal(self, proxy, sender, signal, params):
        """ complete; there is only a single signal! """
        params = params.unpack()
        logger.debug(f"{signal}: {params}")
        if not signal:
            pass
        elif signal == "webViewMessageReceived":
            self.on_webViewMessageReceived(*params)
        else:
            logger.warning(f"[Plugins] Unexpected signal '{signal}' received")


    #
    # Signal handling callbacks
    #

    #
    # CallManager
    #

    def onConferenceCreated_cb(self):
        pass

    def onConferenceCreated_callback(self, convId, confId):
        pass

    #
    # PresenceManager
    #

    def onContactAdded_cb(self, account, uri, confirmed):
        self.emit('contact-added', uri)

    def onSubscriptionStateChanged_cb(self, accountId, buddyUri, state):
        self.emit('presence-changed', buddyUri, state)

    def onNewServerSubscriptionRequest_cb(self, buddyUri):
        # you should accept with self.subscribeBuddy(buddyUri, True)
        pass

    #
    # Trust management
    #

    def onIncomingTrustRequest_cb(self, account, conversation, orig, payload, received):
        """ payload is a bytearray """
        logger.debug(f"IncomingTrustRequest: {orig} {payload}")
        self.emit("trust-request", orig, payload)

    #
    # Signal handling
    #

    #
    # CallManager
    #

    def on_recordPlaybackFilepath(*args):
        pass

    def on_recordPlaybackStopped(*args):
        pass

    def on_updatePlaybackScale(*args):
        pass

    def on_incomingCall(self, account, callId, peer, params):
        if self.autoAnswer:
            #self.Accept(callId)
            pass
        self.activeCalls[callId]['PEER_NUMBER'] = peer
        self.activeCalls[callId]['CALL_STATE'] = 'INCOMING'
        self.emit('call-added', callId, self.activeCalls[callId])

    def on_incomingCallWithMedia(*args):
        logger.debug(f"Incoming call with media: {args}")
        self.emit('call-added', callId, self.activeCalls[callId])

    def on_mediaChangeRequested(*args):
        pass

    #def on_incomingMessage(self, callee, callId, caller, message):
    def on_incomingMessage(self, *args):
        logger.debug(f"Incoming message: {args}")

    def on_callStateChanged(self, account, callId, state, code):
        """ On call state changed event, set the values for new calls,
        or delete the call from the list of active calls
        """
        callDetails = self.getCallDetails(account=account, callId=callId) or {}
        if callId in self.activeCalls.keys():
            for k,v in callDetails.items():
                 self.activeCalls[callId][k] = v
        else:
            self.activeCalls[callId] = callDetails
        self.activeCalls[callId]['state'] = state
        self.activeCalls[callId]['CALL_STATE'] = state

        if state == "INACTIVE": 
            pass
        elif state == "CONNECTING":
            pass
        elif state == "RINGING":
            pass
        elif state == "INCOMING":
            pass
        elif state == "CURRENT":
            self.currentCallId = callId
            if 'start' not in self.activeCalls[callId]:
                self.activeCalls[callId]['start'] = time.time()
        elif state == "HOLD":
            pass
        elif state == "BUSY":
            self.emit('call-missed', self.activeCalls[callId]['PEER_NUMBER'])
        elif state == "FAILURE":
            pass
        elif state == "HUNGUP": 
            if 'start' in self.activeCalls[callId]:
                diff = int(time.time() - self.activeCalls[callId]['start'])
                self.emit('call-hangup', callId, diff)
            elif int(code) == 103:
                logger.debug("remote hangUp")
                self.emit('call-refused', self.activeCalls[callId]['PEER_NUMBER'])
        elif state == "OVER":
            del self.activeCalls[callId]
            if callId == self.currentCallId:
                self.currentCallId = None
            self.emit('call-removed', callId)
        else:
            logger.warning("unknown state:" + str(state))

        if state != 'OVER':
            self.emit('call-changed', callId, state)

    def on_conferenceChanged(*args):
        pass

    def on_conferenceCreated(self, convId, confId):
        self.currentConfId = confId
        self.onConferenceCreated_cb()
        self.onConferenceCreated_callback(convId, confId)

    def on_conferenceRemoved(*args):
        pass

    def on_voiceMailNotify(*args):
        pass

    def on_transferSucceeded(*args):
        pass

    def on_transferFailed(*args):
        pass

    def on_recordingStateChange(*args):
        pass

    def on_onRtcpReportReceived(*args):
        pass

    def on_peerHold(*args):
        pass

    def on_audioMuted(*args):
        pass

    def on_videoMuted(*args):
        pass

    def on_onConferenceInfosUpdated(*args):
        pass

    def on_remoteRecordingChanged(*args):
        pass

    def on_mediaNegotiationStatus(*args):
        pass


    #
    # ConfigurationManager
    #

    def on_deviceAuthStateChanged(*args):
        pass

    def on_addDeviceStateChanged(*args):
        pass

    def on_deviceRevocationEnded(*args):
        pass

    def on_accountProfileReceived(*args):
        pass

    def on_knownDevicesChanged(self, account, devices):
        logger.debug(f"Devices changed for {account}")

    def on_registeredNameFound(*args):
        pass

    def on_nameRegistrationEnded(*args):
        pass

    def on_userSearchEnded(*args):
        pass

    def on_incomingAccountMessage(*args):
        pass

    def on_accountMessageStatusChanged(*args):
        pass

    def on_needsHost(*args):
        pass

    def on_activeCallsChanged(*args):
        pass

    def on_profileReceived(*args):
        pass

    def on_composingStatusChanged(*args):
        pass

    def on_volumeChanged(*args):
        pass

    def on_hardwareDecodingChanged(*args):
        pass

    def on_hardwareEncodingChanged(*args):
        pass

    def on_audioDeviceEvent(*args):
        pass

    def on_audioMeter(*args):
        pass

    def on_accountsChanged(self):
        logger.info("Accounts changed")
        self.emit('accounts-changed')

    def on_accountDetailsChanged(*args):
        pass

    def on_registrationStateChanged(*args):
        pass

    def on_volatileAccountDetailsChanged(*args):
        pass

    def on_stunStatusFailure(*args):
        pass

    def on_errorAlert(*args):
        pass

    def on_certificateStateChanged(*args):
        pass

    def on_certificatePinned(*args):
        pass

    def on_certificatePathPinned(*args):
        pass

    def on_certificateExpired(*args):
        pass

    def on_incomingTrustRequest(self, account, conversation, orig, payload, received):
        """ signal received"""
        account = self._valid_account(account)
        logger.debug("Trust Request received from %s" % orig)
        self.onIncomingTrustRequest_cb(account, conversation, orig, payload, received)

    def on_contactAdded(self, account, uri, confirmed):
        """ signal received"""
        account = self._valid_account(account)
        if confirmed:
            logger.debug("contact %s confirmed" % uri)
            self.onContactAdded_cb(account, uri, confirmed)
        else:
            logger.debug("contact %s NOT confirmed" % uri)

    def on_contactRemoved(self, account, uri, confirmed):
        """ signal received"""
        account = self._valid_account(account)
        if confirmed:
            logger.debug("removal of contact %s confirmed" % uri)
        else:
            logger.debug("removal of contact %s NOT confirmed" % uri)

    def on_mediaParametersChanged(*args):
        pass

    def on_migrationEnded(*args):
        pass

    def on_dataTransferEvent(*args):
        pass

    def on_swarmLoaded(*args):
        pass

    def on_messagesFound(*args):
        pass

    def on_swarmMessageReceived(*args):
        pass

    def on_swarmMessageUpdated(*args):
        pass

    def on_reactionAdded(*args):
        pass

    def on_reactionRemoved(*args):
        pass

    def on_conversationProfileUpdated(*args):
        pass

    def on_conversationRequestReceived(*args):
        pass

    def on_conversationRequestDeclined(*args):
        pass

    def on_conversationReady(*args):
        pass

    def on_conversationRemoved(*args):
        pass

    def on_conversationMemberEvent(*args):
        pass

    def on_onConversationError(*args):
        pass

    def on_conversationPreferencesUpdated(*args):
        pass

    def on_debugMessageReceived(*args):
        pass

    def on_messageSend(*args):
        pass

    def on_messageReceived(self, account, conversationId, message):
        logger.debug(f'New message for {account} in conversation {conversationId} with id {message["id"]}')
        for key in message:
            logger.debug(f'\t {key}: {message[key]}')

    #
    # PresenceManager
    #

    def on_newBuddyNotification(self, accountId, buddyUri, status, lineStatus):
        """ Notify when a registered presence uri presence informations changes
        """
        #logger.debug(f'Presence status changed to {status} for {buddyUri}')
        self.buddyUriList[buddyUri] = status
        self.onSubscriptionStateChanged_cb(accountId, buddyUri, status)

    def on_nearbyPeerNotification(self, accountId, buddyUri, status, displayname):
        """Notify when a new local peer is discovered
        """
        #logger.debug(f'New buddy {buddyUri} discovered')
        self.buddyUriList[buddyUri] = status
        self.onSubscriptionStateChanged_cb(accountId, buddyUri, status)

    def on_subscriptionStateChanged(self, accountId, buddyUri, status):
        """Notify when a the server changes the state of a subscription.
        """
        #logger.debug(f'Subscribed buddy {buddyUri} is now {status}')
        self.buddyUriList[buddyUri] = status
        self.onSubscriptionStateChanged_cb(accountId, buddyUri, status)

    def on_newServerSubscriptionRequest(self, buddyUri):
        """Notify when an other user (or the server) request your presence informations
        """
        #logger.debug(f'Buddy {buddyUri} requests your presence information')
        if buddyUri in self.invalidBuddyUris:
            self.subscribeBuddy(buddyUri=buddyUri, flag=False)
        self.onNewServerSubscriptionRequest_cb(buddyUri)

    def on_serverError(self, accountId, error, msg):
        """
        """
        #logger.error(f'Presence server error {error} with "{msg}"')
        pass

    #
    # Contact management
    #

    #
    # Video management
    #

    def on_deviceEvent(*args):
        pass

    def on_decodingStarted(*args):
        pass

    def on_decodingStopped(*args):
        pass

    def on_fileOpened(*args):
        pass

    #
    # plugins manager interface
    #

    def on_webViewMessageReceived(*args):
        pass

    ###################################################################
    # Methods
    ###################################################################

    #
    # Instance
    #

    def register(self):
        if self.registered:
            return

        if not self.bus:
            raise CtrlDBusError(("Unable to find %s in DBUS." % DBUS_DEAMON_OBJECT)
                                     + " Check if daemon is running")

        try:
            self.proxy_instance = self._get_proxy("Instance")
            self.proxy_callmgr = self._get_proxy("CallManager")
            self.proxy_confmgr = self._get_proxy("ConfigurationManager")
            self.proxy_videomgr = self._get_proxy("VideoManager")
            self.proxy_presmgr = self._get_proxy("PresenceManager")
            self.proxy_plugins = self._get_proxy("PluginManagerInterface")
        except:
            raise CtrlDBusError("Unable to bind to daemon DBus API")

        try:
            if self.proxy_instance:
                self.instance_handler_id = self.proxy_instance.connect("g-signal", self.on_instance_signal)
            if self.proxy_callmgr:
                self.callmgr_handler_id = self.proxy_callmgr.connect("g-signal", self.on_callmgr_signal)
            if self.proxy_confmgr:
                self.confmgr_handler_id = self.proxy_confmgr.connect("g-signal", self.on_confmgr_signal)
            if self.proxy_videomgr:
                self.videomgr_handler_id = self.proxy_videomgr.connect("g-signal", self.on_videomgr_signal)
            if self.proxy_presmgr:
                self.presmgr_handler_id = self.proxy_presmgr.connect("g-signal", self.on_presmgr_signal)
            if self.proxy_plugins:
                self.plugins_handler_id = self.proxy_plugins.connect("g-signal", self.on_plugins_signal)
        except:
            raise CtrlDBusError("Unable to connect to daemon DBus signals")

        try:
            self.proxy_instance.call_sync("Register", GLib.Variant("(is)", (os.getpid(), self.name, )), Gio.DBusCallFlags.NONE, -1, None)
            self.registered = True
        except:
            raise CtrlDeamonError("Client registration failed")
        #logger.debug("Client successfully registered")

    def unregister(self):
        if not self.registered:
            return

        try:
            self.proxy_instance.call_sync("Unregister", GLib.Variant("(i)", (os.getpid(),)), Gio.DBusCallFlags.NONE, -1, None)
            self.registered = False
        except:
            raise CtrlDeamonError("Client unregistration failed")
        self.proxy_instance = None
        self.proxy_callmgr = None
        self.proxy_confmgr = None
        self.proxy_videomgr = None
        self.proxy_presmgr = None

    #
    # CallManager
    #

    def placeCall(self, account=None, dest=None):
        """
        Start a call and return a CallID
        """
        try:
            #if len(self.activeCalls) > 0:
            #    self.emit('action-error', _("Cannot dial while in another call"))
            #    return False
            if dest is None or dest == "":
                logger.error("Invalid call destination")
                return
            account = self._valid_account(account)
            if not account: return
            callId = self.proxy_callmgr.call_sync("placeCall",
                                              GLib.Variant("(ss)", (account, dest)),
                                              Gio.DBusCallFlags.NONE, -1, None).unpack()[0]
            if callId:
                # Add the call to the list of active calls
                self.activeCalls[callId] = self.getCallDetails(account=account, callId=callId) or {}
                if not 'CALL_STATE' in self.activeCalls[callId]:
                    self.activeCalls[callId]['CALL_STATE'] = "PENDING"
                self.currentCallId = callId
                self.emit('call-started', callId, self.activeCalls[callId])
            return callId
        except Exception as e:
            logger.error(f"Call error {e}")
            return False

    def placeCallWithMedia(self, account=None, dest=None, mediaList=None):
        """
        Start a call and return a CallID
        """
        try:
            #if len(self.activeCalls) > 0:
            #    self.emit('action-error', _("Cannot dial while in another call"))
            #    return False
            if dest is None or dest == "":
                logger.error("Invalid call destination")
                return
            account = account or self.getAccount()
            if not account: return
            callId = self.proxy_callmgr.call_sync("placeCallWithMedia",
                                              GLib.Variant("(ssas)", (account, dest, mediaList)),
                                              Gio.DBusCallFlags.NONE, -1, None).unpack()[0]
            if callId:
                # Add the call to the list of active calls
                self.activeCalls[callId] = self.getCallDetails(account=account, callId=callId) or {}
                self.currentCallId = callId
                if not 'CALL_STATE' in self.activeCalls[callId]:
                    self.activeCalls[callId]['CALL_STATE'] = "PENDING"
                self.emit('call-started', callId, self.activeCalls[callId])
            return callId
        except Exception as e:
            logger.error(f"CallWithMedia error {e}")
            return False

    def requestMediaChange(*args):
         pass

    def refuse(self, account=None, callId=None):
        """
        Refuse an incoming call identified by a CallID
        """
        account = self._valid_account(account)
        if not account: return
        if callId is None or callId == "":
            logger.error("Invalid callID")
            return
        #logger.debug("Refuse call " + callId)
        return self.proxy_callmgr.call_sync("refuse",
                                    GLib.Variant("(ss)", (account, callId,)),
                                    Gio.DBusCallFlags.NONE, -1, None).unpack()

    def accept(self, account=None, callId=None):
        """
        Accept an incoming call identified by a CallID
        """
        account = self._valid_account(account)
        if not account: return
        if callId is None or callId == "":
            logger.error("Invalid callID")
            return
        #logger.debug("Accept call " + callId)
        return self.proxy_callmgr.call_sync("accept",
                                    GLib.Variant("(ss)", (account, callId,)),
                                    Gio.DBusCallFlags.NONE, -1, None).unpack()

    def acceptWithMedia(*args):
         pass

    def answerMediaChangeRequest(*args):
         pass

    def hangUp(self, account=None, callId=None):
        """
        End a call identified by a CallID
        """
        account = self._valid_account(account)
        if not account: return
        if callId is None or callId == "":
            pass # just to see
        #logger.debug("hangUp call " + callId)
        return self.proxy_callmgr.call_sync("hangUp",
                                    GLib.Variant("(ss)", (account, callId,)),
                                    Gio.DBusCallFlags.NONE, -1, None).unpack()

    def hangUpConference(self, account=None, confId=None):
        """
        End a call identified by a CallID
        """
        account = self._valid_account(account)
        if not account: return
        if confId is None or confId == "":
            pass # just to see
        #logger.debug("hangUp conference " + confId)
        return self.proxy_callmgr.call_sync("hangUpConference",
                                    GLib.Variant("(ss)", (account, confId,)),
                                    Gio.DBusCallFlags.NONE, -1, None).unpack()

    def hold(self, account=None, callId=None):
        """
        Hold a call identified by a CallID
        """
        account = self._valid_account(account)
        if not account: return
        if callId is None or callId == "":
            logger.error("Invalid callID")
            return
        #logger.debug("Hold call " + callId)
        return self.proxy_callmgr.call_sync("hold",
                                    GLib.Variant("(ss)", (account, callId,)),
                                    Gio.DBusCallFlags.NONE, -1, None).unpack()

    def unhold(self, account=None, callId=None):
        """
        Unhold an incoming call identified by a CallID
        """
        account = self._valid_account(account)
        if not account: return
        if callId is None or callId == "":
            logger.error("Invalid callID")
            return
        #logger.debug("UnHold call " + callId)
        return self.proxy_callmgr.call_sync("unhold",
                                    GLib.Variant("(ss)", (account, callId,)),
                                    Gio.DBusCallFlags.NONE, -1, None).unpack()

    def muteLocalMedia(self, account=None, mute=False):
        account = self._valid_account(account)
        if not account: return
        try:
            callId = self.currentCallId
            if callId is None or callId == "":
                return False
            mediaType = "AUDIO"
            return self.proxy_callmgr.call_sync("muteLocalMedia",
                                    GLib.Variant("(sssb)", (account, callId, mediaType, mute)),
                                    Gio.DBusCallFlags.NONE, -1, None).unpack()
        except Exception as e:
            logger.error(f"muteLocalMedia failed with {e}")

    def transfer(self, account=None, callId=None, to=None):
        """
        Transfert a call identified by a CallID
        'to' is a jid
        """
        account = self._valid_account(account)
        if not account: return
        if not account or not callId or not to:
            logger.error("params should not be None!")
            return None
        return self.proxy_callmgr.call_sync("transfer",
                                    GLib.Variant("(sss)", (account, callId, to,)),
                                    Gio.DBusCallFlags.NONE, -1, None).unpack()

    def attendedTransfer(self, account=None, callId=None, to=None):
        """
        Transfert a call identified by a CallID
        'to' is a callId
        """
        account = self._valid_account(account)
        if not account: return
        if not account or not callId or not to:
            logger.error("params should not be None!")
            return None
        return self.proxy_callmgr.call_sync("attendedTransfer",
                                    GLib.Variant("(sss)", (account, callId, to,)),
                                    Gio.DBusCallFlags.NONE, -1, None).unpack()

    def playDTMF(self, key):
        """Send a DTMF"""
        self.proxy_callmgr.call_sync("playDTMF",
                                    GLib.Variant("(s)", (key,)),
                                    Gio.DBusCallFlags.NONE, -1, None)

    def startTone(*args):
         pass

    def joinParticipant(*args):
         pass

    def createConfFromParticipantList(*args):
         pass

    def setConferenceLayout(*args):
         pass

    def setActiveParticipant(*args):
         pass

    def setActiveStream(*args):
         pass

    def setModerator(*args):
         pass

    def muteParticipant(*args):
         pass

    def muteStream(*args):
         pass

    def isConferenceParticipant(*args):
         pass

    def raiseParticipantHand(*args):
         pass

    def raiseHand(*args):
         pass

    def hangupParticipant(*args):
         pass

    def addParticipant(*args):
         pass

    def addMainParticipant(*args):
         pass

    def detachLocalParticipant(*args):
         pass

    def detachParticipant(*args):
         pass

    def joinConference(*args):
         pass

    def getConferenceDetails(self, account=None, confId=None):
        """
        Return information on this conference if exists
        """
        account = self._valid_account(account)
        if not account or not confId:
            logger.error("params should not be None!")
            return None
        return self.proxy_callmgr.call_sync("getConferenceDetails",
                                            GLib.Variant("(ss)", (self.account, confId,)),
                                            Gio.DBusCallFlags.NONE, -1, None).unpack()[0]

    def getConferenceList(self, account=None):
        """
        Return all conferences handled by the daemon
        """
        account = self._valid_account(account)
        if not account:
            logger.error("params should not be None!")
            return None
        return [str(x) for x in
                self.proxy_callmgr.call_sync("getConferenceList",
                                             GLib.Variant("(s)", (account,)),
                                             Gio.DBusCallFlags.NONE, -1, None).unpack()]

    def getConferenceId(*args):
         pass

    def toggleRecording(*args):
         pass

    def getIsRecording(*args):
         pass

    def recordPlaybackSeek(*args):
         pass

    def getCallDetails(self, account=None, callId=None):
        """
        Return information on this call if exists
        """
        account = self._valid_account(account)
        if not account or not callId:
            logger.error("params should not be None!")
            return None
        ret = self.proxy_callmgr.call_sync("getCallDetails",
                                             GLib.Variant("(ss)", (account, callId,)),
                                             Gio.DBusCallFlags.NONE, -1, None).unpack()[0]
        #logger.debug(f"Call details: {ret}")
        return ret

    def getCallList(self, account=None):
        """
        Return all calls handled by the daemon
        """
        account = self._valid_account(account)
        if not account:
            logger.error("params should not be None!")
            return None
        return [str(x) for x in
                self.proxy_callmgr.call_sync("getCallList",
                                             GLib.Variant("(s)", (account,)),
                                             Gio.DBusCallFlags.NONE, -1, None).unpack()]

    def switchInput(*args):
         pass

    def switchSecondaryInput(*args):
         pass

    def sendTextMessage(self, account, dest, payload, flag):
         msgId = self.proxy_callmgr.call_sync("sendTextMessage",
                                             GLib.Variant("(ssassb)", (account, dest, payload, flag,)),
                                             Gio.DBusCallFlags.NONE, -1, None).unpack()[0]
         return msgId

    def getConferenceInfos(*args):
         pass

    def getParticipantList(*args):
         pass

    def holdConference(*args):
         pass

    def unholdConference(*args):
         pass

    def startRecordedFilePlayback(*args):
         pass

    def stopRecordedFilePlayback(*args):
         pass

    def currentMediaList(*args):
         pass

    #
    # ConfigurationManager
    #

    def getAccountTemplate(*args):
        pass

    def getAccountDetails(self, account=None):
        """Return a list of string. If no account is provided, active account is used"""
        account = self._valid_account(account)
        if not account: return
        if self.isAccountExists(account):
            ret = self.proxy_confmgr.call_sync("getAccountDetails",
                                                GLib.Variant("(s)", (account,)),
                                                Gio.DBusCallFlags.NONE, -1, None).unpack()[0]
            #logger.debug("account details: " + str(ret))
            return ret
        return []

    def getVolatileAccountDetails(self, account=None):
        """Return a list of string. If no account is provided, active account is used"""
        account = self._valid_account(account)
        if not account: return
        if self.isAccountExists(account):
            ret = self.proxy_confmgr.call_sync("getVolatileAccountDetails",
                                                GLib.Variant("(s)", (account,)),
                                                Gio.DBusCallFlags.NONE, -1, None).unpack()[0]
            #logger.debug("volatile account details: " + str(ret))
            return ret
        return []

    def setAccountDetails(*args):
        pass

    def setAccountActive(*args):
        pass

    def setCredentials(*args):
        pass

    def getCredentials(*args):
        pass

    def addAccount(self, details=None):
        """Add a new account account

        Add a new account to the daemon. Default parameters are \
        used for missing account configuration field.

        Required parameters are type, alias, hostname, username and password

        input details = {
        "Account.type": DEFAUL_ACCT_TYPE,
        "Account.alias": alias,
        "Account.hostname": hostname,
        "Account.username": username,
        "Account.password": password,
        }
        """
        if details is None:
            raise CtrlAccountError("Must specifies type, alias, hostname, \
                                  username and password in \
                                  order to create a new account")
        return str(self.proxy_confmgr.call_sync("addAccount",
                                                GLib.Variant("(a{ss})", (details,)),
                                                Gio.DBusCallFlags.NONE, -1, None).unpack()[0])

    def exportToFile(*args):
        pass

    def provideAccountAuthentication(*args):
        pass

    def addDevice(*args):
        pass

    def confirmAddDevice(*args):
        pass

    def cancelAddDevice(*args):
        pass

    def revokeDevice(*args):
        pass

    def getKnownRingDevices(self, account=None):
        account = self._valid_account(account)
        if not account: return
        return self.proxy_confmgr.call_sync("getKnownRingDevices",
                                                GLib.Variant("(s)", (account,)),
                                                Gio.DBusCallFlags.NONE, -1, None).unpack()[0]

    def changeAccountPassword(*args):
        pass

    def lookupName(*args):
        pass

    def lookupAddress(*args):
        pass

    def registerName(*args):
        pass

    def searchUser(*args):
        pass

    def setAccountsOrder(*args):
        pass

    def removeAccount(self, account=None):
        """Remove an account from internal list"""
        if account is None:
            return False
        if not account: return
        return self.proxy_confmgr.call_sync("removeAccount",
                                     GLib.Variant("(s)", (account,)),
                                     Gio.DBusCallFlags.NONE, -1, None).unpack()

    def getAccountList(self):
        return self.getAllAccounts(account_type=None)

    def getAllAccounts(self, account_type=None):
        """Return a list with all accounts"""
        if self.proxy_confmgr:
            l = self.proxy_confmgr.call_sync("getAccountList", None, Gio.DBusCallFlags.NONE, -1, None).unpack()[0]
        else:
            return []
        acclist =  map(str, l)
        reslist = []
        for a in acclist:
            acc = a.strip("'[]")
            if acc != '':
                reslist.append(acc)
        if account_type:
            reslist = filter(partial(self.isAccountOfType, account_type), reslist)
        return list(reslist)

    def registerAllAccounts(*args):
        pass

    def sendRegister(*args):
        pass

    def sendTextMessage(*args):
        pass

    def cancelMessage(*args):
        pass

    def getLastMessages(*args):
        pass

    def getNearbyPeers(*args):
        pass

    def updateProfile(*args):
        pass

    def getMessageStatus(*args):
        pass

    def setIsComposing(*args):
        pass

    def setMessageDisplayed(*args):
        pass

    def setVolume(*args):
        pass

    def getVolume(*args):
        pass

    def muteDtmf(*args):
        pass

    def isDtmfMuted(*args):
        pass

    def muteCapture(self, flag):
        self.proxy_confmgr.call_sync("muteCapture",
                                     GLib.Variant("(b)", (flag,)),
                                     Gio.DBusCallFlags.NONE, -1, None)

    def isCaptureMuted(self):
        return self.proxy_confmgr.call_sync("isCaptureMuted",
                                     None,
                                     Gio.DBusCallFlags.NONE, -1, None).unpack()[0]

    def mutePlayback(self, flag):
        self.proxy_confmgr.call_sync("mutePlayback",
                                     GLib.Variant("(b)", (flag,)),
                                     Gio.DBusCallFlags.NONE, -1, None)

    def isPlaybackMuted(self):
        return self.proxy_confmgr.call_sync("isPlaybackMuted",
                                     None,
                                     Gio.DBusCallFlags.NONE, -1, None).unpack()[0]

    def muteRingtone(self, flag):
        self.proxy_confmgr.call_sync("muteRingtone",
                                     GLib.Variant("(b)", (flag,)),
                                     Gio.DBusCallFlags.NONE, -1, None)

    def isRingtoneMuted(self):
        return self.proxy_confmgr.call_sync("isRingtoneMuted",
                                     None,
                                     Gio.DBusCallFlags.NONE, -1, None).unpack()[0]

    def getAudioManager(self):
        api = self.proxy_confmgr.call_sync("getAudioManager",
                                     None,
                                     Gio.DBusCallFlags.NONE, -1, None).unpack()[0]
        logger.debug(f"{api}")
        return api

    def setAudioManager(self, api):
        flag = self.proxy_confmgr.call_sync("setAudioManager",
                                     GLib.Variant("(s)", (api,)),
                                     Gio.DBusCallFlags.NONE, -1, None).unpack()[0]
        logger.debug(f"{flag}")
        return flag

    def getSupportedAudioManagers(self):
        apis = self.proxy_confmgr.call_sync("getSupportedAudioManagers",
                                     None,
                                     Gio.DBusCallFlags.NONE, -1, None).unpack()[0]
        logger.debug(f"{apis}")
        return apis

    def getRecordPath(*args):
        pass

    def setRecordPath(*args):
        pass

    def getIsAlwaysRecording(*args):
        pass

    def setIsAlwaysRecording(*args):
        pass

    def getRecordPreview(*args):
        pass

    def setRecordPreview(*args):
        pass

    def getRecordQuality(*args):
        pass

    def setRecordQuality(*args):
        pass

    def getCodecList(*args):
        pass

    def getCodecDetails(*args):
        pass

    def setCodecDetails(*args):
        pass

    def getActiveCodecList(*args):
        pass

    def setActiveCodecList(self, account=None, codec_list=''):
        """Activate given codecs on an account. If no account is provided, active account is used"""
        account = self._valid_account(account)
        if not account: return
        if self.isAccountExists(account):
            codec_list = [dbus.UInt32(x) for x in codec_list.split(',')]
            self.configurationmanager.setActiveCodecList(account, codec_list)
            return self.proxy_confmgr.call_sync("setActiveCodecList",
                                        GLib.Variant("(sau)", (account, codec_list,)),
                                        Gio.DBusCallFlags.NONE, -1, None).unpack()[0]

    def getAudioPluginList(self):
        return self.proxy_confmgr.call_sync("getAudioPluginList",
                                     None,
                                     Gio.DBusCallFlags.NONE, -1, None).unpack()[0]

    def setAudioPlugin(*args):
        pass

    def getAudioOutputDeviceList(self):
        return self.proxy_confmgr.call_sync("getAudioOutputDeviceList",
                                     None,
                                     Gio.DBusCallFlags.NONE, -1, None).unpack()[0]

    def setAudioOutputDevice(self, index):
        self.proxy_confmgr.call_sync("setAudioOutputDevice",
                                     GLib.Variant("(i)", (index,)),
                                     Gio.DBusCallFlags.NONE, -1, None)

    def setAudioInputDevice(self, index):
        self.proxy_confmgr.call_sync("setAudioInputDevice",
                                     GLib.Variant("(i)", (index,)),
                                     Gio.DBusCallFlags.NONE, -1, None)

    def setAudioRingtoneDevice(self, index):
        self.proxy_confmgr.call_sync("setAudioRingtoneDevice",
                                     GLib.Variant("(i)", (index,)),
                                     Gio.DBusCallFlags.NONE, -1, None)

    def getAudioInputDeviceList(self):
        return self.proxy_confmgr.call_sync("getAudioInputDeviceList",
                                     None,
                                     Gio.DBusCallFlags.NONE, -1, None).unpack()[0]

    def getCurrentAudioDevicesIndex(self):
        return self.proxy_confmgr.call_sync("getCurrentAudioDevicesIndex",
                                     None,
                                     Gio.DBusCallFlags.NONE, -1, None).unpack()[0]

    def getAudioInputDeviceIndex(self, device):
        return self.proxy_confmgr.call_sync("getAudioInputDeviceIndex",
                                     GLib.Variant("(s)", (device,)),
                                     Gio.DBusCallFlags.NONE, -1, None).unpack()[0]

    def getAudioOutputDeviceIndex(self, device):
        return self.proxy_confmgr.call_sync("getAudioOutputDeviceIndex",
                                     GLib.Variant("(s)", (device,)),
                                     Gio.DBusCallFlags.NONE, -1, None).unpack()[0]

    def getCurrentAudioOutputPlugin(self):
        return self.proxy_confmgr.call_sync("getCurrentAudioOutputPlugin",
                                     None,
                                     Gio.DBusCallFlags.NONE, -1, None).unpack()[0]

    def isAudioMeterActive(self, ring_buffer_id):
        return self.proxy_confmgr.call_sync("isAudioMeterActive",
                                     GLib.Variant("(s)", (ring_buffer_id,)),
                                     Gio.DBusCallFlags.NONE, -1, None).unpack()[0]

    def setAudioMeterState(self, ring_buffer_id, flag):
        self.proxy_confmgr.call_sync("setAudioMeterState",
                                     GLib.Variant("(sb)", (ring_buffer_id, flag,)),
                                     Gio.DBusCallFlags.NONE, -1, None)

    def getNoiseSuppressState(self):
        return self.proxy_confmgr.call_sync("getNoiseSuppressState",
                                     None,
                                     Gio.DBusCallFlags.NONE, -1, None).unpack()[0]

    def setNoiseSuppressState(self, state):
        self.proxy_confmgr.call_sync("setNoiseSuppressState",
                                     GLib.Variant("(s)", (state,)),
                                     Gio.DBusCallFlags.NONE, -1, None)

    def getEchoCancellationState(self):
        return self.proxy_confmgr.call_sync("getEchoCancellationState",
                                     None,
                                     Gio.DBusCallFlags.NONE, -1, None).unpack()[0]

    def setEchoCancellationState(self, state):
        self.proxy_confmgr.call_sync("setEchoCancellationState",
                                     GLib.Variant("(s)", (state,)),
                                     Gio.DBusCallFlags.NONE, -1, None)

    def getVoiceActivityDetectionState(self):
        return self.proxy_confmgr.call_sync("getVoiceActivityDetectionState",
                                     None,
                                     Gio.DBusCallFlags.NONE, -1, None).unpack()[0]

    def setVoiceActivityDetectionState(self, state):
        self.proxy_confmgr.call_sync("setVoiceActivityDetectionState",
                                     GLib.Variant("(b)", (state,)),
                                     Gio.DBusCallFlags.NONE, -1, None)

    def isAgcEnabled(self):
        return self.proxy_confmgr.call_sync("isAgcEnabled",
                                     None,
                                     Gio.DBusCallFlags.NONE, -1, None).unpack()[0]

    def setAgcState(self, state):
        self.proxy_confmgr.call_sync("setAgcState",
                                     GLib.Variant("(b)", (state,)),
                                     Gio.DBusCallFlags.NONE, -1, None)

    def getHistoryLimit(*args):
        pass

    def setHistoryLimit(*args):
        pass

    def getRingingTimeout(*args):
        pass

    def setRingingTimeout(*args):
        pass

    def getSupportedTlsMethod(*args):
        pass

    def getSupportedCiphers(*args):
        pass

    def validateCertificate(*args):
        pass

    def validateCertificate(*args):
        pass

    def getCertificateDetails(*args):
        pass

    def getCertificateDetails(*args):
        pass

    def getPinnedCertificates(*args):
        pass

    def pinCertificate(*args):
        pass

    def unpinCertificate(*args):
        pass

    def pinCertificatePath(*args):
        pass

    def unpinCertificatePath(*args):
        pass

    def pinRemoteCertificate(*args):
        pass

    def setCertificateStatus(*args):
        pass

    def getCertificatesByStatus(*args):
        pass

    def getTrustRequests(self, account=None):
        """ """
        account = self._valid_account(account)
        if not account: return
        return self.proxy_confmgr.call_sync("getTrustRequest",
                                            GLib.Variant("(s)", (account,)),
                                            Gio.DBusCallFlags.NONE, -1, None).unpack()[0]

    def acceptTrustRequest(self, account=None, orig=None):
        """ """
        account = self._valid_account(account)
        if not account: return
        # from is a reserved word
        return self.proxy_confmgr.call_sync("acceptTrustRequest",
                                            GLib.Variant("(ss)", (account, orig,)),
                                            Gio.DBusCallFlags.NONE, -1, None).unpack()[0]

    def discardTrustRequest(self, account=None, orig=None):
        """ """
        account = self._valid_account(account)
        if not account: return
        return self.proxy_confmgr.call_sync("discardTrustRequest",
                                            GLib.Variant("(ss)", (account, orig,)),
                                            Gio.DBusCallFlags.NONE, -1, None).unpack()[0]

    def sendTrustRequest(self, account=None, to="", payload="empty"):
        """ """
        account = self._valid_account(account)
        if not account: return
        payload = bytearray(payload.encode('utf_8'))
        return self.proxy_confmgr.call_sync("sendTrustRequest",
                                    GLib.Variant("(ssay)", (account, to, payload,)),
                                    Gio.DBusCallFlags.NONE, -1, None).unpack()[0]


    def addContact(self, account=None, uri=None):
        """ """
        account = self._valid_account(account)
        if not account: return
        return self.proxy_confmgr.call_sync("addContact",
                                    GLib.Variant("(ss)", (account, uri,)),
                                    Gio.DBusCallFlags.NONE, -1, None).unpack()[0]

    def removeContact(self, account=None, uri=None, ban=False):
        """ """
        account = self._valid_account(account)
        if not account: return
        return self.proxy_confmgr.call_sync("removeContact",
                                    GLib.Variant("(ssb)", (account, uri, ban,)),
                                    Gio.DBusCallFlags.NONE, -1, None).unpack()[0]

    def getContactDetails(self, account=None, uri=None):
        """ """
        account = self._valid_account(account)
        if not account: return
        return self.proxy_confmgr.call_sync("getContactDetails",
                                    GLib.Variant("(ss)", (account, uri,)),
                                    Gio.DBusCallFlags.NONE, -1, None).unpack()[0]

    def getContacts(self, account=None):
        """ """
        account = self._valid_account(account)
        if not account: return
        cl = self.proxy_confmgr.call_sync("getContacts",
                                    GLib.Variant("(s)", (account, )),
                                    Gio.DBusCallFlags.NONE, -1, None).unpack()[0]
        for c in cl: 
            self.cachedContactsList[c['id']] = c
        return self.cachedContactsList

    def getAddrFromInterfaceName(*args):
        pass

    def getAllIpInterface(*args):
        pass

    def getAllIpInterfaceByName(*args):
        pass

    def sendFile(*args):
        pass

    def fileTransferInfo(*args):
        pass

    def downloadFile(*args):
        pass

    def cancelDataTransfer(*args):
        pass

    def monitor(*args):
        pass

    def getConnectionList(*args):
        pass

    def getChannelList(*args):
        pass

    def startConversation(self, account=None):
        account = self._valid_account(account)
        if not account: return
        logger.debug("start conversation")
        return self.proxy_confmgr.call_sync("startConversation",
                                    GLib.Variant("(s)", (account, )),
                                    Gio.DBusCallFlags.NONE, -1, None).unpack()[0]

    def acceptConversationRequest(*args):
        pass

    def declineConversationRequest(*args):
        pass

    def removeConversation(self, account=None, convid=None):
        account = self._valid_account(account)
        if not account: return
        if not convid or convid == "": 
            return False
        logger.debug(f"remove conversation {convid}")
        return self.proxy_confmgr.call_sync("removeConversation",
                                    GLib.Variant("(ss)", (account, convid )),
                                    Gio.DBusCallFlags.NONE, -1, None).unpack()[0]

    def getConversations(self, account=None):
        account = self._valid_account(account)
        if not account: return
        logger.debug("get conversations")
        return self.proxy_confmgr.call_sync("getConversations",
                                    GLib.Variant("(s)", (account, )),
                                    Gio.DBusCallFlags.NONE, -1, None).unpack()[0]

    def getActiveCalls(*args):
        pass

    def getConversationRequests(*args):
        pass

    def updateConversationInfos(*args):
        pass

    def conversationInfos(self, account=None, convid=None):
        account = self._valid_account(account)
        if not account: return
        if not convid or convid == "": 
            return
        logger.debug(f"infos conversation {convid}")
        return self.proxy_confmgr.call_sync("conversationInfos",
                                    GLib.Variant("(ss)", (account, convid )),
                                    Gio.DBusCallFlags.NONE, -1, None).unpack()[0]

    def setConversationPreferences(*args):
        pass

    def getConversationPreferences(*args):
        pass

    def addConversationMember(*args):
        pass

    def removeConversationMember(*args):
        pass

    def getConversationMembers(self, account=None, convid=None):
        account = self._valid_account(account)
        if not account: return
        if not convid or convid == "": 
            return
        logger.debug(f"get conversation members {convid}")
        return self.proxy_confmgr.call_sync("getConversationMembers",
                                    GLib.Variant("(ss)", (account, convid )),
                                    Gio.DBusCallFlags.NONE, -1, None).unpack()[0]
        pass

    def sendMessage(*args):
        pass

    def loadConversation(*args):
        pass

    def loadSwarmUntil(*args):
        pass

    def countInteractions(*args):
        pass

    def clearCache(*args):
        pass

    def searchConversation(*args):
        pass

    def connectivityChanged(*args):
        pass

    def setDefaultModerator(*args):
        pass

    def getDefaultModerators(*args):
        pass

    def enableLocalModerators(*args):
        pass

    def isLocalModeratorsEnabled(*args):
        pass

    def setAllModerators(*args):
        pass

    def isAllModerators(*args):
        pass


    #
    # Account management
    #

    def _valid_account(self, account):
        account = account or self.account
        if account is None:
            logger.warning("No provided or current account!")
        return account

    def isAccountExists(self, account):
        """ Checks if the account exists"""
        return account in self.getAllAccounts()

    def isAccountEnable(self, account=None):
        """Return True if the account is enabled. If no account is provided, active account is used"""
        return self.getAccountDetails(self._valid_account(account))['Account.enable'] == "true"

    def isAccountRegistered(self, account=None):
        """Return True if the account is registered. If no account is provided, active account is used"""
        return self.getVolatileAccountDetails(self._valid_account(account))['Account.registrationStatus'] in ('READY', 'REGISTERED')

    def isAccountOfType(self, account_type, account=None):
        """Return True if the account type is the given one. If no account is provided, active account is used"""
        return self.getAccountDetails(self._valid_account(account))['Account.type'] == account_type


    def getAllEnabledAccounts(self):
        """Return a list with all enabled-only accounts"""
        return [x for x in self.getAllAccounts() if self.isAccountEnable(x)]

    def getAllRegisteredAccounts(self):
        """Return a list with all registered-only accounts"""
        return [x for x in self.getAllAccounts() if self.isAccountRegistered(x)]

    def setAccountByAlias(self, alias):
        """Define as active the first account who match with the alias"""

        for testedaccount in self.getAllAccounts():
            details = self.getAccountDetails(testedaccount)
            if (details['Account.enable'] == 'true' and
                details['Account.alias'] == alias):
                self.account = testedaccount
                logger.info(f"account is {account}")
                return self.account
        logger.error("No enabled account matched with alias")
        return None

    def getAccountByAlias(self, alias):
        """Get account name having its alias"""
        for account in self.getAllAccounts():
            details = self.getAccountDetails(account)
            if details['Account.alias'] == alias:
                return account
        logger.error("No account matched with alias")
        return None

    def setAccount(self, account):
        """Define the active account

        The active account will be used when sending a new call
        """
        self.account = account if account in self.getAllAccounts() else None
        logger.debug(f"account is {account}")
        return self.account

    def setFirstRegisteredAccount(self):
        """Find the first enabled account and define it as active"""
        logger.debug("Enter setFirstRegisteredAccount")
        rAccounts = self.getAllRegisteredAccounts()
        logger.debug(f"getAllRegisteredAccounts {rAccounts}")
        if 0 == len(rAccounts):
            logger.error("No registered account !")
            self.account = None
            return None
        else:
            logger.debug(f"Found registered account(s) {rAccounts}")
        return self.setAccount(rAccounts[0])

    def setFirstActiveAccount(self):
        """Find the first enabled account and define it as active"""
        aAccounts = self.getAllEnabledAccounts()
        if 0 == len(aAccounts):
            logger.error("No active account !")
            return None
        return self.setAccount(aAccounts[0])

    def getAccount(self):
        """Return the active account"""
        if not self.account:
            self.setFirstRegisteredAccount()
        #if self.account != "IP2IP" and not self.isAccountRegistered():
        #    raise CtrlAccountError("Unable to place a call without a registered account")
        return self.account

    def setAccountEnable(self, account=None, enable=False):
        """Set account enabled"""
        account = self._valid_account(account)
        if not account: return
        details = self.getAccountDetails(account)
        details['Account.enable'] = enable
        return self.proxy_confmgr.call_sync("setAccountDetails",
                                    GLib.Variant("sa{ss}", (account,details,)),
                                    Gio.DBusCallFlags.NONE, -1, None).unpack()[0]

    def setAccountDetails(self, account=None, details=None):
        """Set account details"""
        if details is None:
            logger.error("Must provide some details to update")
            return
        if (type(details) == str):
            d = json.loads(details)
        elif (str(type(details)) == "<class '_io.TextIOWrapper'>"):
            d = json.load(details)
        else:
            logger.error("Provided details are nor a string nor a file descriptor")
            return
        account = self._valid_account(account)
        if not account: return
        odetails = self.getAccountDetails(account)
        for k,v in d:
            if odetails[k] is None:
                logger.error("the key %s is not recognized" % k)
                return
            odetails[k] = v
        return self.proxy_confmgr.call_sync("setAccountDetails",
                                    GLib.Variant("(sa{ss})", (account, odetails,)),
                                    Gio.DBusCallFlags.NONE, -1, None).unpack()

    def setAccountRegistered(self, account=None, register=False):
        """ Tries to register the account"""
        account = self._valid_account(account)
        if not account: return
        return self.proxy_confmgr.call_sync("sendRegister",
                                    GLib.Variant("(sb)", (account, register,)),
                                    Gio.DBusCallFlags.NONE, -1, None).unpack()

    #
    # VideoManager
    #

    def getDeviceList(*args):
         pass

    def getCapabilities(*args):
         pass

    def getSettings(*args):
         pass

    def applySettings(*args):
         pass

    def getDefaultDevice(*args):
         pass

    def setDefaultDevice(*args):
         pass

    def startLocalMediaRecorder(*args):
         pass

    def stopLocalRecorder(*args):
         pass

    def startAudioDevice(*args):
         pass

    def stopAudioDevice(*args):
         pass

    def openVideoInput(*args):
         pass

    def closeVideoInput(*args):
         pass

    def getDecodingAccelerated(*args):
         pass

    def setDecodingAccelerated(*args):
         pass

    def getEncodingAccelerated(*args):
         pass

    def setEncodingAccelerated(*args):
         pass

    def setDeviceOrientation(*args):
         pass

    def getRenderer(*args):
         pass

    def startShmSink(*args):
         pass

    def createMediaPlayer(*args):
         pass

    def closeMediaPlayer(*args):
         pass

    def pausePlayer(*args):
         pass

    def mutePlayerAudio(*args):
         pass

    def playerSeekToTime(*args):
         pass

    def getPlayerPosition(*args):
         pass

    def getPlayerDuration(*args):
         pass

    def setAutoRestart(*args):
         pass

    #
    # PresenceManager
    #

    def publish(self, accountId=None, status=True, note=""):
        """ publish presence (boolean) with a note for other users
        """
        account = self._valid_account(accountId)
        if not account: return
        self.presencemanager.publish(account, status, note)
        return self.proxy_presmgr.call_sync("publish",
                                    GLib.Variant("(sbs)", (account, status, note,)),
                                    Gio.DBusCallFlags.NONE, -1, None).unpack()[0]

    def answerServerRequest(self, buddyUri="", flag=False):
        """Answer a presence request from the server
        """
        if buddyUri != "":
            return self.proxy_presmgr.call_sync("answerServerRequest",
                                    GLib.Variant("(sb)", (buddyUri, flag, )),
                                    Gio.DBusCallFlags.NONE, -1, None).unpack()[0]

    def subscribeBuddy(self, account=None, buddyUri="", flag=True):
        """Ask be be notified when 'uri' presence change
        """
        account = self._valid_account(account)
        if not account: return
        if buddyUri != "":
            logger.debug(f"subscribe to {buddyUri}")
            return self.proxy_presmgr.call_sync("subscribeBuddy",
                                    GLib.Variant("(ssb)", (account, buddyUri, flag, )),
                                    Gio.DBusCallFlags.NONE, -1, None).unpack()

    def getSubscriptions(self, accountId=None, credentialInformation=None):
        """New clients connecting to existing daemon need to be aware of active
                subscriptions.

            While there is more status than "Online" or "Offline", only those

            List of hashes map with the following key-value pairs:
                    * Buddy:      URI of the contact
                    * Status:     "Online" or "Offline"
                    * LineStatus: String
        """
        account = self._valid_account(accountId)
        if not account: return
        return self.proxy_presmgr.call_sync("getSubscriptions",
                                    GLib.Variant("(ss)", (account, credentialInformation, )),
                                    Gio.DBusCallFlags.NONE, -1, None).unpack()[0]

    def setSubscriptions(self, accountId=None, uriList=[], invalidUris=[]):
        """Calling "subscribeBuddy" in a loop is too slow

           A list of SIP URIs

           List of invalid URIs. An URI must be a valid SIP URI. Clients should purge
                   the list from all invalid URIs
        """
        account = self._valid_account(accountId)
        if not account: return
        # self.buddyUriList.keys()
        # self.invalidBuddyUris
        return self.proxy_presmgr.call_sync("setSubscriptions",
                                    GLib.Variant("(sasas)", (account, uriList, invalidUris,)),
                                    Gio.DBusCallFlags.NONE, -1, None).unpack()[0]

    #
    # iPluginManagerInterface
    #

    def loadPlugin(*args):
         pass

    def unloadPlugin(*args):
         pass

    def getPluginDetails(*args):
         pass

    def getPluginPreferences(*args):
         pass

    def setPluginPreference(*args):
         pass

    def getPluginPreferencesValues(*args):
         pass

    def resetPluginPreferencesValues(*args):
         pass

    def getInstalledPlugins(*args):
         pass

    def getLoadedPlugins(*args):
         pass

    def installPlugin(*args):
         pass

    def uninstallPlugin(*args):
         pass

    def getPlatformInfo(*args):
         pass

    def getCallMediaHandlers(*args):
         pass

    def getChatHandlers(*args):
         pass

    def toggleCallMediaHandler(*args):
         pass

    def toggleChatHandler(*args):
         pass

    def getCallMediaHandlerDetails(*args):
         pass

    def getCallMediaHandlerStatus(*args):
         pass

    def getChatHandlerDetails(*args):
         pass

    def getChatHandlerStatus(*args):
         pass

    def getPluginsEnabled(*args):
         pass

    def setPluginsEnabled(*args):
         pass

    def sendWebViewMessage(*args):
         pass

    def sendWebViewAttach(*args):
         pass

    def sendWebViewDetach(*args):
         pass

    #
    # Helper functions
    #

    def _GenerateCallID(self):
        """Generate Call ID"""
        m = hashlib.md5()
        t = int( time.time() * 1000 )
        r = int( random.random()*100000000000000000 )
        m.update(str(t) + str(r))
        callId = m.hexdigest()
        return callId

    def _on_daemon_status(self, *args):
        """
        monitor, status, msg):
        Handle monitor status changes.
        """
        try:
            logger.debug(f"daemon: {args}")
            monitor = args[0]
            status = args[1]
            msg = args[2]
            if status == "connected":
                self.bus = monitor.bus
                self.register()
            if status == "offline" or status == "error":
                self.bus = None
                self.unregister()
                self.account = None
            self.emit('daemon-connection-status', status, msg)
            logger.debug(f"daemon reemitted: {status} - {msg}")
        except Exception as e:
            logger.error(f"[Manager] monitor status error: {e}")

    def _get_proxy(self, interface):
        """Create a DBus proxy for a given interface."""
        try:
            path = DBUS_DEAMON_PATH + "/" + interface
            objet = DBUS_DEAMON_OBJECT + "." + interface
            return Gio.DBusProxy.new_sync(
                self.bus, Gio.DBusProxyFlags.NONE, None,
                DBUS_DEAMON_OBJECT, path, objet, None)
        except Exception as e:
            logger.error(f"Proxy Init Error ({interface}): {e}")
            return None

    def __del__(self):
        self.unregister()

    def isRegistered(self):
        return self.registered
    
    def printClientCallList(self):
        logger.debug("Client active call list:")
        logger.debug("------------------------")
        for call in self.activeCalls:
            logger.debug("\t" + call)

