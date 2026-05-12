import gi, sys, os, time, signal
gi.require_version('Gtk', '4.0')
gi.require_version('Adw', '1')
from gi.repository import Adw, Gio, Gtk, GLib, Gdk, GObject
from loguru import logger

DBUS_DEAMON_OBJECT = 'cx.ring.Ring'
DBUS_DEAMON_PATH = '/cx/ring/Ring'

css_string = """
.call-btn, .call-btn-small, .secondary-btn, .gray-btn, .destructive-action, .suggested-action, .pill {
transition: all 0.1s ease-in-out;
}
.call-btn { background: #2ec27e; color: white; border-radius: 9999px; }
.call-btn:hover { background: #26a269; }
.call-btn:active { background: #1a7f50; transform: scale(0.95); box-shadow: inset 0 3px 5px rgba(0,0,0,0.3); }
.call-btn-small { background: #2ec27e; color: white; padding: 0px; min-height: 24px; min-width: 24px; border-radius: 9999px; }
.call-btn-small:hover { background: #26a269; }
.call-btn-small:active { background: #1a7f50; transform: scale(0.90); box-shadow: inset 0 2px 4px rgba(0,0,0,0.3); }
.secondary-btn, .gray-btn { background-color: alpha(@theme_fg_color, 0.08); color: @theme_fg_color; padding: 0px; border-radius: 9999px; }
.secondary-btn:hover, .gray-btn:hover { background-color: alpha(@theme_fg_color, 0.15); }
.secondary-btn:active, .gray-btn:active { background-color: alpha(@theme_fg_color, 0.3); transform: scale(0.95); }
.destructive-action { background-color: #e01b24; color: white; }
.destructive-action:hover { background-color: #c01c28; }
.destructive-action:active { background-color: #a0131a; transform: scale(0.95); box-shadow: inset 0 3px 5px rgba(0,0,0,0.3); }
.suggested-action { background-color: #3584e4; color: white; }
.suggested-action:active { background-color: #1c71d8; transform: scale(0.95); box-shadow: inset 0 3px 5px rgba(0,0,0,0.3); }
.call-icon-missed { color: #e01b24; }
.call-icon-incoming { color: #2ec27e; }
.call-icon-outgoing { color: #2ec27e; }
.call-icon-cancelled { color: #e01b24; }
.icon-blue { color: #3584e4; }
.icon-red { color: #e01b24; }
.compact-btn { padding-top: 0px; padding-bottom: 0px; min-height: 20px; }
.dim-label { opacity: 0.7; font-size: 0.9em; }
.tiny-label { opacity: 0.6; font-size: 0.75em; }
.accent { color: #3584e4; font-weight: bold; }
.pill { border-radius: 12px; }
.chat-bubble-in { background: #deddda; color: black; border-radius: 15px 15px 15px 0px; padding: 6px 10px; }
.chat-bubble-out { background: #3584e4; color: white; border-radius: 15px 15px 0px 15px; padding: 6px 10px; }
.chat-bubble-scheduled { background: #f5c211; color: black; border-radius: 15px 15px 0px 15px; padding: 6px 10px; }
.chat-time { font-size: 0.75em; opacity: 0.6; margin-top: 2px; }

.app-notification { box-shadow: 0 3px 8px rgba(0,0,0,0.3); font-weight: bold; }
.notif-error { background-color: #e01b24; color: white; padding: 8px 16px; border-radius: 99px; }
.notif-success { background-color: #2ec27e; color: white; padding: 8px 16px; border-radius: 99px; }
.notif-info { background-color: #3584e4; color: white; padding: 8px 16px; border-radius: 99px; }

.round-btn {
    border-radius: 50%;
    min-width: 38px;
    min-height: 38px;
    padding: 0;
    margin: 0;
}
.success-btn { background-color: #2ec27e; color: white; }
.suggested-btn { background-color: #3584e4; color: white; }
.destructive-btn { background-color: #e01b24; color: white; }

.chat-input {
    background-color: @view_bg_color;
    border: 1px solid alpha(@window_fg_color, 0.15);
    border-radius: 10px;
    padding: 9px 9px;
    transition: border-color 200ms ease-in-out;
}
.chat-input:focus-within {
    border-color: @accent_color;
}
.chat-input textview {
    background-color: transparent;
    padding: 0;
}

.att-chip {
    background-color: alpha(@window_fg_color, 0.08);
    border-radius: 6px;
    padding: 4px 8px;
    margin-right: 6px;
}

.load-more-btn {
    margin-top: 10px;
    margin-bottom: 10px;
    font-weight: bold;
}

stack {
    min-width: 0px;
    min-height: 0px;
}

.action-blue-mid {
    background-color: #5e9ce0;
    color: white;
}
.action-blue-light {
    background-color: #99c1f1;
    color: black;
}


.mini-bubble {
    margin-bottom: 8px;
}


.menu-header {
    font-weight: bold;
    font-size: 10px;
    color: alpha(currentColor, 0.6);
    margin-bottom: 4px;
    text-transform: uppercase;
    letter-spacing: 1px;
}


.black-fader { background-color: black; }


.card {
    background-color: alpha(@theme_fg_color, 0.08);
    border-radius: 12px;
    padding: 12px;
    margin-bottom: 8px;
}
.blue-active { background-color: #3584e4; color: white; border: 1px solid #78aeed; }
.btn-green {
    background-color: #2ec27e; color: white;
    transition: background-color 0.1s, transform 0.1s;
}

.destructive-action, .circular, .dialpad-btn {
    transition: background-color 0.1s, transform 0.1s;
}
.btn-green:active { background-color: #1a633f; transform: scale(0.94); }

.destructive-action:active { background-color: #811d1d; transform: scale(0.94); }
.circular:active { background-color: alpha(@theme_fg_color, 0.1); transform: translateY(2px); }
.dialpad-btn:active { background-color: #3584e4; color: white; }
.bg-btn { padding: 0; }
.error-box { background-color: #3d1414; border-radius: 15px; padding: 20px; }
.error-title { font-weight: 800; font-size: 24px; color: #ff7b7b; }

.rounded-corners {
    border-radius: 12px;
}

.attachment-tile {
    background-color: alpha(@theme_fg_color, 0.1);
    border-radius: 12px;
}

.icon-white-shadow {
    color: white;
    text-shadow: 0px 1px 3px rgba(0,0,0,0.8);
}

viewswitcher button:checked {
    opacity: 1;
    font-weight: bold;
}
viewswitcher button:not(:checked) {
    opacity: 0.5;
    font-weight: normal;
    background: transparent;
    box-shadow: none;
    outline: none;
}
viewswitcher button:focus {
    box-shadow: none;
    outline: none;
}

.record-button {
    border-radius: 9999px;
    background-color: #e01b24;
    color: white;
    padding: 0;
}
.record-button:active {
    background-color: #a51d2d;
}
.record-button image {
    -gtk-icon-transform: scale(2.0);
}

.shutter-button {
    border-radius: 9999px;
    background-color: white;
    color: black;
    padding: 0;
    border: 4px solid #dedede;
}
.shutter-button:active {
    background-color: #cccccc;
}
.shutter-button image {
    -gtk-icon-transform: scale(1.5);
}

.video-record-button {
    border-radius: 9999px;
    background-color: #e01b24;
    color: white;
    padding: 0;
    border: 4px solid #dedede;
}
.video-record-button:active {
    background-color: #a51d2d;
}
.video-record-button image {
    -gtk-icon-transform: scale(2.0);
}

.all-button-history {
    border-radius: 12px;
    padding-left: 16px;
    padding-right: 16px;
}
"""

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
    Monitors the status of the Jami daemon
    """
    __gsignals__ = {
        'daemon-status-changed': (GObject.SignalFlags.RUN_FIRST, None, (str, str)),
    }

    def __init__(self):
        """Initialize the Jami Monitor."""
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
            self.emit('daemon-status-changed', 'offline', 'Jamid service stopped')
            self.connected = False
        except Exception as e:
            logger.error(f"[Monitor] On name vanished error: {e}")
#
# Main class
#

class JamiDispatcher(GObject.Object):
    """
    """
    __gsignals__ = {
        'jami-signal': (GObject.SignalFlags.RUN_FIRST, None, (str, str, object)),
    }

    def __init__(self):
        """Initialize the daemon manager"""
        try:
            super().__init__()

            # internals
            self.name = "eu.Hellea.Jami.log" # client name
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

        except Exception as e:
            logger.error(f"[Manager] Init error: {e}")

    def _on_daemon_status(self, *args):
        """
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

    def __del__(self):
        self.unregister()

    def isRegistered(self):
        return self.registered
    
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
        #logger.debug(f"{signal}: {params}")
        self.emit('jami-signal', 'call', signal, params)

    def on_confmgr_signal(self, proxy, sender, signal, params):
        """ complete """
        params = params.unpack()
        #logger.debug(f"{signal}: {params}")
        self.emit('jami-signal', 'conf', signal, params)

    def on_videomgr_signal(self, proxy, sender, signal, params):
        """ complete; there are 4 signals! """
        params = params.unpack()
        #logger.debug(f"{signal}: {params}")
        self.emit('jami-signal', 'video', signal, params)

    def on_presmgr_signal(self, proxy, sender, signal, params):
        """ complete; there are 4 signals! """
        params = params.unpack()
        #logger.debug(f"{signal}: {params}")
        self.emit('jami-signal', 'pres', signal, params)

    def on_plugins_signal(self, proxy, sender, signal, params):
        """ complete; there is only a single signal! """
        params = params.unpack()
        #logger.debug(f"{signal}: {params}")
        self.emit('jami-signal', 'plugins', signal, params)


class App(Adw.Application):
    def __init__(self, application_id="eu.Hellea.Jami"):
        """Initialize the Application."""
        super().__init__(application_id=application_id,
                         flags=Gio.ApplicationFlags.HANDLES_COMMAND_LINE)
        self.add_main_option("debug", ord("d"), GLib.OptionFlags.NONE, GLib.OptionArg.NONE, "Debug mode", None)

    def do_startup(self):
        logger.debug("Application startup...")
        Gtk.Application.do_startup(self)
        GLib.set_prgname(self.get_application_id())
        style_manager = Adw.StyleManager.get_default()
        style_manager.set_color_scheme(Adw.ColorScheme.DEFAULT)
        self._setup_css()

    def _setup_css(self):
        """Load and apply custom CSS."""
        try:
            provider = Gtk.CssProvider()
            provider.load_from_string(css_string)
            Gtk.StyleContext.add_provider_for_display(Gdk.Display.get_default(), provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)
        except Exception as e:
            logger.error(f"CSS setup error: {e}")

    def do_command_line(self, command_line):
        """Handle command line arguments."""
        options = command_line.get_options_dict()
        if options.contains("debug"):
            logger.remove()
            logger.add(sys.stderr, level="DEBUG")
        logger.debug("Debug mode activated")
        MainWindow(application = self).present()

class MainWindow(Adw.Window):
    def __init__(self, application = None):
        super().__init__()
        self.set_application(application)
        icon_name = application.get_application_id()
        self.set_title("Jami signals log")
        self.set_icon_name(icon_name)
        self.set_default_size(360, 600)
        self.daemon = JamiDispatcher()
        self.daemon.connect('jami-signal', self.on_jami_signal)
        self.setup_ui()

    def setup_ui(self):
        self.overlay = Gtk.Overlay()
        self.set_content(self.overlay)

        main_vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        self.overlay.set_child(main_vbox)

        header = Adw.HeaderBar()
        title_lbl = Gtk.Label(label=self.title, css_classes=["title"])
        header.set_title_widget(title_lbl)
        main_vbox.append(header)

        content = Gtk.ScrolledWindow()
        self.log_buffer = Gtk.TextBuffer()
        self.log_buffer.insert(self.log_buffer.get_end_iter(), 'DAEMON LOGS', -1)
        self.log_buffer.insert(self.log_buffer.get_end_iter(), '\n', -1)
        jlogger = Gtk.TextView.new_with_buffer(self.log_buffer)
        jlogger.set_editable(False)
        jlogger.set_hexpand(True)
        jlogger.set_vexpand(True)
        jlogger.set_margin_bottom(10)
        jlogger.set_margin_end(10)
        jlogger.set_margin_start(10)
        jlogger.set_margin_top(10)
        content.set_child(jlogger)
        main_vbox.append(content)

    def on_jami_signal(self, sender, manager, jsignal, params):
        self.log_buffer.insert(self.log_buffer.get_end_iter(), f"FROM {manager}: {jsignal}\n", -1)
        self.log_buffer.insert(self.log_buffer.get_end_iter(), f"{params}\n", -1)
        logger.debug(f"FROM {manager}: {jsignal} ({params})")
        

def main():
    """
    Main entry point for the application.
    """
    signal.signal(signal.SIGINT, signal.SIG_DFL)
    app_id = "eu.Hellea.Jami.log"
    app = App(application_id=app_id)
    return app.run(sys.argv)

if __name__ == "__main__":
    sys.exit(main())
