'''NEXUI - Demo UI for nexo-in-the-cloud'''
import os
import subprocess
import threading
import uuid
import time
from logging.config import dictConfig
from logging import info, debug, warning, error
from flask import Flask, send_from_directory, request, session
from flask_socketio import SocketIO, emit, join_room, leave_room
import pynng

from .scap4nexui import ScapSession
from . import scap4nexui

dictConfig({
    'version': 1,
    'formatters': {
        'default': {
            'format': '%(asctime)s %(levelname).1s %(threadName)-13s %(message)s',
        }
    },
    'handlers': {
        'wsgi': {
            'class': 'logging.StreamHandler',
            'stream': 'ext://flask.logging.wsgi_errors_stream',
            'formatter': 'default'
        }
    },
    'root': {
        'level': 'DEBUG',
        'handlers': ['wsgi']
    }
})

app = Flask(__name__, instance_relative_config=True)
app.config['SECRET_KEY'] = 'nexo-secret-key-123'
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='threading')

class SessionManager:
    def __init__(self):
        self.sessions = {}
        self.lock = threading.Lock()

    def create_session(self, sid):
        with self.lock:
            if sid in self.sessions:
                self.destroy_session(sid)
            
            session_id = str(uuid.uuid4())
            req_ipc = f'ipc:///tmp/fatrq_{session_id}'
            ntf_ipc = f'ipc:///tmp/fatnt_{session_id}'
            
            # Start nexoid-cpp
            prog = [
                'nexoid-cpp',
                '--req-ipc', req_ipc,
                '--ntf-ipc', ntf_ipc
            ]
            info(f"[{sid}] Starting nexoid-cpp: {' '.join(prog)}")
            # We don't have nexoid-cpp on dev machine, so we might want to handle FileNotFoundError gracefully
            proc = None
            try:
                proc = subprocess.Popen(prog)
            except FileNotFoundError:
                error(f"[{sid}] nexoid-cpp not found, continuing without it (for dev)")

            # Start scap4nexui session handler
            scap_session = ScapSession(sid, socketio, req_ipc)
            scap_session.start()

            # Create notification socket for UI -> nexoid
            # We must wait a bit for nexoid-cpp to bind its Pull socket, or just dial and wait
            ntf_socket = pynng.Push0(dial=ntf_ipc)

            self.sessions[sid] = {
                'id': session_id,
                'proc': proc,
                'scap': scap_session,
                'ntf': ntf_socket
            }

    def get_session(self, sid):
        with self.lock:
            return self.sessions.get(sid)

    def destroy_session(self, sid):
        with self.lock:
            sess = self.sessions.pop(sid, None)
            if sess:
                info(f"[{sid}] Destroying session")
                sess['scap'].stop()
                sess['ntf'].close()
                if sess['proc']:
                    sess['proc'].terminate()
                    sess['proc'].wait(timeout=2)

session_manager = SessionManager()

@app.route('/')
def index():
    return send_from_directory('static', 'index.html')

@app.route('/<path:path>')
def static_files(path):
    return send_from_directory('static', path)

@socketio.on('connect')
def handle_connect():
    sid = request.sid
    info(f"Client connected: {sid}")
    join_room(sid)
    session_manager.create_session(sid)
    emit('connected', {'sid': sid}, room=sid)

@socketio.on('disconnect')
def handle_disconnect():
    sid = request.sid
    info(f"Client disconnected: {sid}")
    leave_room(sid)
    session_manager.destroy_session(sid)

@socketio.on('ui_response')
def handle_ui_response(data):
    '''Response from browser to SCAPI request'''
    sid = request.sid
    debug(f"[{sid}] Received UI response: {data}")
    sess = session_manager.get_session(sid)
    if sess:
        sess['scap'].on_ui_response(data)

@socketio.on('ui_notification')
def handle_ui_notification(data):
    '''Notification from browser (e.g. nexo request start) directly to nexoid-cpp'''
    sid = request.sid
    debug(f"[{sid}] Received UI notification: {data}")
    sess = session_manager.get_session(sid)
    if sess:
        # data should be Jer/json that we convert or directly XER.
        # In original code, it was XForms sending raw XML (XER).
        # We need to make sure frontend sends proper JSON/JER which is converted, 
        # or just send strings if we implement encoding.
        # Let's assume frontend sends JER (JSON), we encode to XER and send to push socket.
        try:
            apdu = scap4nexui.scapi_message.asn_nexui.decode('ScapiNngNotification', data, check_constraints=True)
            xer_bytes = scap4nexui.scapi_message.asn.encode('ScapiNngNotification', apdu, check_constraints=True)
            scap4nexui.scapi_message.append_to_event_log('ScapiNngNotification', xer_bytes)
            sess['ntf'].send(xer_bytes)
        except Exception as e:
            error(f"[{sid}] Error encoding notification: {e}")

