'''Basic SCAP Application Session Handler'''

import threading
import queue
from contextlib import contextmanager
from logging import info, debug, error

from pynng import Rep0, exceptions
from . import scapi_message as sm


@contextmanager
def scapi_endpoint(*args, name='scapi_endpoint', **kwargs):
    '''Creates SCAPI endpoint socket'''
    socket = Rep0(*args, **kwargs)
    info(f"{socket.protocol_name} '{name}' is listening on {kwargs['listen']}")
    yield socket
    info(f"{socket.protocol_name} '{name}' at {kwargs['listen']} is stopped")
    socket.close()


class ScapSession:
    def __init__(self, session_id, socketio, listen_ipc):
        self.session_id = session_id
        self.socketio = socketio
        self.listen_ipc = listen_ipc
        self.ui_response_queue = queue.Queue()
        self.running = True
        self.thread = threading.Thread(target=self.run, name=f'scap_{session_id}')
        self.thread.daemon = True

    def start(self):
        self.thread.start()

    def stop(self):
        self.running = False
        # Push a dummy message to unblock if waiting on queue
        self.ui_response_queue.put(None)

    def on_ui_response(self, rsp_json):
        '''Called by the SocketIO handler when UI responds'''
        self.ui_response_queue.put(rsp_json)

    def run(self):
        '''Main request forwarding loop for this session'''
        try:
            with scapi_endpoint(listen=self.listen_ipc) as fat:
                # Set timeout so we can check self.running periodically
                fat.recv_timeout = 1000  
                while self.running:
                    try:
                        req = fat.recv()
                    except exceptions.Timeout:
                        continue
                    
                    debug(f"[{self.session_id}] Received SCAPI request {req}")
                    sm.append_to_event_log('ScapiNngRequest', req)
                    
                    # Convert to JSON for UI
                    ui_msg = sm.tonexui(req)
                    ui_msg_str = ui_msg.decode('utf-8') if isinstance(ui_msg, bytes) else ui_msg
                    
                    # Send to UI via SocketIO
                    self.socketio.emit('ui_request', ui_msg_str, room=self.session_id)
                    
                    # Wait for UI response
                    rsp_json = self.ui_response_queue.get()
                    if rsp_json is None:
                        break # Stopped
                        
                    # Send response back to SCAPI
                    rsp = sm.fromnexui(rsp_json)
                    fat.send(rsp)
                    debug(f"[{self.session_id}] SCAPI response {rsp}")
                    sm.append_to_event_log('ScapiNngResponse', rsp)
        except Exception as e:
            error(f"[{self.session_id}] Exception in ScapSession: {e}")
            
