#!/usr/bin/python3

# 
# vivarium_ctrl_web
# 
# Copyright (c) 2020 Daniel Dean <dd@danieldean.uk>.
# 
# Licensed under The MIT License a copy of which you should have 
# received. If not, see:
# 
# http://opensource.org/licenses/MIT
# 

import web
import io
import picamera
#from cheroot.server import HTTPServer
#from cheroot.ssl.builtin import BuiltinSSLAdapter
import hashlib
import datetime
import time
import json
import logging
import logging.handlers
from logger import Logger
import sys
import os
import mimetypes
import psutil

# Use paths relative to the script.
dirname = os.path.dirname(__file__)
if dirname:
    dirname += '/'

logger = logging.getLogger('Vivarium_CTRL_Web')
logger.setLevel(logging.INFO)
handler = logging.handlers.RotatingFileHandler(dirname + 'vivarium_ctrl_web.log', maxBytes=262144, backupCount=3)
handler.setFormatter(logging.Formatter('%(asctime)s - %(message)s', '%d-%b-%y %H:%M:%S'))
logger.addHandler(handler)

sys.stdout = Logger(logger, logging.INFO)
sys.stderr = Logger(logger, logging.ERROR)

# Use HTTPS
#HTTPServer.ssl_adapter = BuiltinSSLAdapter(
#    certificate=dirname + 'cert/cert.pem',
#    private_key=dirname + 'cert/key.pem'
#)

# Set URLs
urls = (
    '/', 'Index',
    '/(\d+)', 'Index',
    '/reload', 'Reload',
    '/login', 'Login',
    '/logout', 'Logout',
    '/favicon.ico', 'Favicon',
    '/stream.mjpg', 'Stream',
    '/toggle_device', 'ToggleDevice',
    '/settings', 'Settings',
    '/files/(.*)/(.*)', 'Files'
)

# Setup database connection.
db = web.database(
    dbn='sqlite',
    db=dirname + 'vivarium_ctrl.db'
)

# Templates
render = web.template.render(dirname + 'templates/')

# Debug must be disabled for sessions to work.
web.config.debug = False
app = web.application(urls, globals())
session = web.session.Session(app, web.session.DiskStore(dirname + 'sessions'),
                              initializer={'authenticated': False, 'username': None})


class Index:
    """ Displays all the data and provide links to other features.
    """
    def GET(self, num_hours=12):
        if not session.authenticated:
            proto = web.ctx.env.get('HTTP_X_FORWARDED_PROTO', 'http')
            raise web.seeother(proto + '://' + web.ctx.host + '/login')
        else:
            # Calculate date and time by subtracting from timestamp.
            from_datetime = datetime.datetime.fromtimestamp(time.time() - 3600 * int(num_hours))
            # Get requested number of readings.
            sensor_readings = list(db.select('sensor_readings', order='reading_datetime DESC',
                                             where='reading_datetime>=$from_datetime',
                                             vars={'from_datetime': from_datetime}))
            # Get device states.
            device_states = list(db.select('device_states'))
            # Render with table and charts.
            return render.index(device_states, sensor_readings, num_hours)

    def POST(self):
        if not session.authenticated:
            proto = web.ctx.env.get('HTTP_X_FORWARDED_PROTO', 'http')
            raise web.seeother(proto + '://' + web.ctx.host + '/login')
        else:
            num_hours = web.input().num_hours
            if num_hours == '12':
                num_hours = ''
            proto = web.ctx.env.get('HTTP_X_FORWARDED_PROTO', 'http')
            raise web.seeother(proto + '://' + web.ctx.host + '/' + num_hours)


class Reload:
    """ Endpoint for live reloading.
    """
    def POST(self):
        if not session.authenticated:
            web.ctx.status = '401 Unauthorized'
            web.header('WWW-Authenticate', 'Forms realm="Vivarium_CTRL"')
            return  # Will return the 401 Unauthorized with header.
        else:
            # To construct response.
            return_data = dict()
            # Cast timestamp from string to float.
            from_timestamp = to_float(web.input().last)
            # If this is None then there is an error on the clients part.
            if from_timestamp is None:
                web.ctx.status = '400 Bad Request'
                return  # Will return 400 Bad Request.
            elif os.path.getmtime(dirname + 'vivarium_ctrl.db') > from_timestamp:  # Check if the DB has been modified.
                # Convert timestamp to datetime.
                from_datetime = datetime.datetime.fromtimestamp(from_timestamp)
                # Get the sensor reading(s).
                sensor_readings = list(db.select('sensor_readings', order='reading_datetime DESC',
                                                 where='reading_datetime>$from_datetime',
                                                 vars={'from_datetime': from_datetime}))
                # Get device states and convert the 1/0 to On/Off.
                device_states = list(db.select('device_states'))
                for device_state in device_states:
                    device_state.state = to_string(device_state.state)
                # Create a combined dict to return.
                return_data.update({'sensor_readings': sensor_readings,
                                   'device_states': device_states})
            # Check backend process is running.
            pid = db.select('flags', where='flag="pid"')
            if pid and psutil.pid_exists(pid[0].state):
                backend_running = True
            else:
                backend_running = False
            # Add to response.
            return_data.update({'backend_running': backend_running})
            # Set header, dump to JSON and return.
            web.header('Content-type:', 'application/json')
            return json.dumps(return_data)


class Login:
    """ Basic authentication to guard against unauthorised access.
    """
    def GET(self):
        if not session.authenticated:
            return render.login('')
        else:
            proto = web.ctx.env.get('HTTP_X_FORWARDED_PROTO', 'http')
            raise web.seeother(proto + '://' + web.ctx.host + '/')

    def POST(self):
        username, password = web.input().username, web.input().password
        users = db.select('users', where='username=$username', vars=locals())
        # Check if there were any users (only expecting one).
        if users:
            user = users[0]
            password += user.salt
            password = hashlib.sha256(password.encode('utf-8')).hexdigest()
            if user.password == password:
                session.authenticated = True
                session.username = user.username
                logger.info("Successful login by user '" + session.username + "'.")
                return  # Will return 200 OK by default.
        # If we made it this far either the username does not exist or the password is wrong.
        logger.warning("Failed login attempt using username '" + username + "'.")
        web.ctx.status = '401 Unauthorized'
        web.header('WWW-Authenticate', 'Forms realm="Vivarium_CTRL"')
        return  # Will return the 401 Unauthorized with header.


class Logout:
    """ Logout from a session.
    """
    def POST(self):
        logger.info("Logout by user '" + session.username + "'.")
        session.authenticated = False
        session.username = None
        session.kill()
        return render.login('Successfully logged out.')


class Stream:
    """ Provide an access point for the raw stream.
    """
    def GET(self):
        if not session.authenticated:
            proto = web.ctx.env.get('HTTP_X_FORWARDED_PROTO', 'http')
            raise web.seeother(proto + '://' + web.ctx.host + '/login')
        else:
            camera = picamera.PiCamera()
            camera.resolution = (1280, 960)
            camera.vflip = True
            logger.info("Camera stream opened by user '" + session.username + "'.")
            web.header('Content-type', 'multipart/x-mixed-replace; boundary=jpgboundary')
            stream = io.BytesIO()
            try:
                for foo in camera.capture_continuous(stream, 'jpeg'):
                    yield '\r\n--jpgboundary\r\n'
                    web.header('Content-type', 'image/jpeg')
                    yield b'\r\n' + stream.getvalue() + b'\r\n'
                    stream.seek(0)
                    stream.truncate()
                    time.sleep(0.5)
            except (KeyboardInterrupt, BrokenPipeError, ConnectionResetError):
                pass
            finally:
                logger.info("Camera stream closed by user '" + session.username + "'.")
                stream.close()
                camera.close()


class Favicon:
    """ Redirect requests for a favicon.
    """
    def GET(self):
        proto = web.ctx.env.get('HTTP_X_FORWARDED_PROTO', 'http')
        raise web.seeother(proto + '://' + web.ctx.host + '/files/images/favicon.ico')


class ToggleDevice:
    """ Toggle a devices state.
    """
    def POST(self):
        if not session.authenticated:
            web.ctx.status = '401 Unauthorized'
            web.header('WWW-Authenticate', 'Forms realm="Vivarium_CTRL"')
            return  # Will return the 401 Unauthorized with header.
        else:
            device = web.input().device
            old_state = web.input().state
            if old_state == "On":
                new_state = 0
            else:
                new_state = 1
            logger.info("'" + device + "' set '" + to_string(new_state) + "' by user '" + session.username + "'.")
            db.update('device_states', where='device=$device', vars={'device': device}, state=new_state)
            web.header('Content-type:', 'application/json')
            return json.dumps({"device": device, "state": to_string(new_state)})


class Settings:
    """ Set thresholds and schedules for devices.
    """
    def GET(self):
        if not session.authenticated:
            proto = web.ctx.env.get('HTTP_X_FORWARDED_PROTO', 'http')
            raise web.seeother(proto + '://' + web.ctx.host + '/login')
        else:
            f = open(dirname + 'settings.json', 'rt')
            settings = json.loads(f.read())
            return render.settings(settings)

    def POST(self):
        if not session.authenticated:
            web.ctx.status = '401 Unauthorized'
            web.header('WWW-Authenticate', 'Forms realm="Vivarium_CTRL"')
            return  # Will return the 401 Unauthorized with header.
        else:
            # Retrieve the input.
            settings = web.input()
            # Correct the types (as they will all be string).
            for key in settings.keys():
                if settings[key] == 'true':
                    settings[key] = True
                elif settings[key] == 'false':
                    settings[key] = False
                else:
                    if '.' in settings[key]:
                        value = to_float(settings[key])
                        if value is not None:
                            settings[key] = value
                    elif str.isnumeric(settings[key]):
                        settings[key] = int(settings[key])
            # Write to file immediately.
            f = open(dirname + 'settings.json', 'wt')
            f.write(json.dumps(settings, indent=4))
            f.flush()
            # Set reload flag.
            db.update('flags', where="flag='reload_settings'", state=1)
            # Render template with message and new settings.
            logger.info("Settings updated by user '" + session.username + "'.")
            return  # Will return 200 OK by default.


class Files:
    """ A fairly hackey way to get around the fixed path for static files in webpy.
    """
    def GET(self, path, filename):
        try:
            etag = str(os.path.getmtime(dirname + 'files/' + path + '/' + filename))
            last_modified = datetime.datetime.fromtimestamp(
                os.path.getmtime(dirname + 'files/' + path + '/' + filename)
            )
            if web.modified(last_modified, etag):
                f = open(dirname + 'files/' + path + '/' + filename, 'rb')
                web.header('Content-type', mimetypes.guess_type(filename)[0])
                return f.read()
            else:
                return web.notmodified()
        except (FileNotFoundError, OSError):
            return web.notfound()


def to_float(value):
    """ Convert a decimal represented as a string to a float.
    """
    try:
        return float(value)
    except ValueError:
        return None


def to_string(value):
    """ Convert a boolean to on/off as a string.
    """
    if value:
        return "On"
    else:
        return "Off"


if __name__ == "__main__":
    app.run()
    #web.httpserver.runsimple(app.wsgifunc(), ("0.0.0.0", 8181))
