import requests
from grpc import StatusCode
from google.protobuf.json_format import MessageToDict
from google.protobuf.struct_pb2 import Struct
import json
from nuance.dlg.v1.common.dlg_common_messages_pb2 import *
from nuance.dlg.v1.dlg_messages_pb2 import *
from nuance.dlg.v1.dlg_interface_pb2_grpc import *
import time
import re
import os


class session_start:
    def __init__(self, config):
        self.log_list = []
        self.log_dict = {}
        self.payload_dict = None
        self.selector_dict = None
        self.project_data = None
        self.model_ref_dict = None
        self.response = {}
        self.request = {}
        self.session_started = False
        self.token = None
        self.channel = None
        self.text = None
        self.got_init_data = False
        self.config = config
        self.session_id = None
        self.logs_folder = "logs"
        self.got_token = False
        self.project_config = {"auth_url": "https://auth.crt.nuance.com/oauth2/token",
                               "serverUrl": "dlg.api.nuance.com:443",
                               "nlu_uri": "nlu.api.nuance.com:443", "client_id": None, "secret": None, "modelUrn": None,
                               "scope": "dlg", "channel": "default", "language": "en-US", "sleep": "1"}

    def get_setup_data(self):
        config = self.config
        project_config = self.project_config
        if config:
            try:
                config_file_contents = open(config)
                config_json = json.load(config_file_contents)
                config_file_contents.close()
            except Exception as e:
                self.response = {f'errorMessage: get_setup_data failed at: {e}'}
                return

            for key, value in config_json.items():
                if key in project_config.keys() and value != None and str(value).strip() != "":
                    project_config[key] = value

        for key, value in project_config.items():
            if key == "client_id":
                if ":" in str(project_config[key]):
                    project_config[key] = str(project_config[key]).replace(":", "%3A")
            if key == "secret":
                project_config[key] = str(project_config[key]).replace("'", "")

        if project_config["client_id"] is None or project_config["secret"] is None or project_config[
            "modelUrn"] is None:
            self.response = {"errorMessage: config if not setup, client_id,"
                             "secret,dlg_modelUrn and nlu_modelUrn are required"}
        else:
            self.got_init_data = True
        self.project_data = project_config

        self.model_ref_dict = {
            "uri": self.project_data["modelUrn"],
            "type": 0
        }
        self.selector_dict = {
            "channel": self.project_data["channel"],
            "language": self.project_data["language"],
            "library": "default"
        }

    def __enter__(self):
        self.get_setup_data()
        if self.got_init_data:
            self.get_token()
            if self.got_token == True:
                self.connect()
                self.stub = DialogServiceStub(self.channel)
                self.start_request()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.session_started and "errorMessage" not in str(self.status_request()):
            self.stop_request()

    def get_token(self):
        payload = {"grant_type": "client_credentials", "scope": self.project_data["scope"]}
        self.request = {"auth_url": self.project_data["auth_url"], "client_id": self.project_data["client_id"]}
        try:
            response = requests.post(self.project_data["auth_url"],
                                     auth=(self.project_data["client_id"], self.project_data["secret"]),
                                     data=payload)
            response.json()["access_token"]
            self.token = response.json()["access_token"]
            self.response = {"access_token": "*****"}
            self.got_token = True
        except Exception as e:
            self.response = {f'errorMessage: get_token failed check client_credentials: {e}'}


    def text_payload(self):
        if self.text is not None:
            return {"user_input": {"userText": self.text}}
        else:
            return {"user_input": {"userText": None}}

    def connect(self):
        self.response = "connect"
        try:
            call_credentials = grpc.access_token_call_credentials(self.token)
            channel_credentials = grpc.ssl_channel_credentials()
            channel_credentials = grpc.composite_channel_credentials(channel_credentials, call_credentials)
            channel = grpc.secure_channel(self.project_data["serverUrl"], credentials=channel_credentials)
            self.channel = channel
        except grpc.RpcError as e:
            self.response = {"errorMessage": "gRPC error at connect",
                             "RpcError": str(e)}

    def start_request(self):
        requestName = "start_request"
        session_id = None
        time.sleep(int(self.project_data.get('sleep')))
        selector = Selector(channel=self.selector_dict.get('channel'),
                            library=self.selector_dict.get('library'),
                            language=self.selector_dict.get('language'))
        start_payload = StartRequestPayload(model_ref=self.model_ref_dict)
        self.request = {"selector_dict": self.selector_dict,
                        "model_ref_dict": self.model_ref_dict}
        try:
            start_req = StartRequest(session_id=session_id,
                                     selector=selector,
                                     payload=start_payload)

            start_response, call = self.stub.Start.with_call(start_req)
            assert call.code() == StatusCode.OK
            response = MessageToDict(start_response)
            self.session_id = response.get('payload').get('sessionId')
            self.response = response
            self.session_started = True
        except grpc.RpcError as e:
            self.response = {"errorMessage": "gRPC error at start_request:",
                             "RpcError": str(e)}
        write_to_log(self.session_id, self.request, self.response,self.logs_folder,requestName)

    def start(self, expected=None):
        self.execute_request()
        assert_dlg(expected, self.response)

    def update_request(self, data):
        requestName = "update_request"
        data_struct = Struct()
        data_struct.update(data)
        try:
            update_payload = UpdateRequestPayload(data=data_struct)
            update_req = UpdateRequest(session_id=self.session_id, payload=update_payload)
            self.request = {"session_id": self.session_id,
                        "data": data}
            update_response, call = self.stub.Update.with_call(update_req)
            assert call.code() == StatusCode.OK
            response = MessageToDict(update_response)
            self.response = response
        except grpc.RpcError as e:
            self.response = {"errorMessage": "gRPC error at start_request:",
                             "RpcError": str(e)}
        write_to_log(self.session_id, self.request, self.response,self.logs_folder,requestName)

    def execute_request(self, text=None, expected=""):
        requestName = "execute_request"
        if not self.got_init_data  or self.got_token == False:
            return
        if text is not None:
            self.text = text
        self.payload_dict = self.text_payload()
        time.sleep(int(self.project_data.get('sleep')))
        selector = Selector(channel=self.selector_dict.get('channel'),
                            library=self.selector_dict.get('library'),
                            language=self.selector_dict.get('language'))
        input = UserInput(user_text=self.payload_dict.get('user_input').get('userText'))
        self.request = {"selector_dict": self.selector_dict, "payload_dict": self.payload_dict}
        if 'errorMessage' not in str(self.response):
            try:
                execute_payload = ExecuteRequestPayload(
                    user_input=input)
                execute_request = ExecuteRequest(session_id=self.session_id,
                                                 selector=selector,
                                                 payload=execute_payload)
                execute_response, call = self.stub.Execute.with_call(execute_request)
                assert call.code() == StatusCode.OK
                self.response = MessageToDict(execute_response)
            except grpc.RpcError as e:
                self.response = {"errorMessage": "gRPC error at execute_request",
                                 "RpcError": str(e)}
        write_to_log(self.session_id, self.request, self.response,self.logs_folder,requestName)
        assert_dlg(expected, self.response)
        return self.response

    def stop_request(self):
        requestName = "stop_request"
        self.request = {"session_id": self.session_id}
        stop_req = StopRequest(session_id=self.session_id)
        try:
            stop_response, call = self.stub.Stop.with_call(stop_req)
            assert call.code() == StatusCode.OK
            self.response = MessageToDict(stop_response)
        except grpc.RpcError as e:
            self.response = {"errorMessage": "gRPC error at stop_request",
                             "RpcError": str(e)}
        write_to_log(self.session_id, self.request, self.response,self.logs_folder,requestName)

    def status_request(self):
        status_request = StatusRequest(session_id=self.session_id)
        try:
            status_response, call = self.stub.Status.with_call(status_request)
            assert call.code() == StatusCode.OK
            self.response = MessageToDict(status_response)
        except grpc.RpcError as e:
            if e.code() == grpc.StatusCode.NOT_FOUND:
                self.response = {"errorMessage": "Session ended: NOT_FOUND error"}
            else:
                self.response = {"errorMessage": "gRPC error at status_request",
                                 "RpcError": str(e)}

        return self.response
    
def dlg_payload_log():
    logs_dir = "logs"
    if not os.path.exists(logs_dir):
        os.makedirs(logs_dir)
    return logs_dir

def clean_text(text):
    'update wild char with temp_dynamic'
    clean_text = re.sub(r'\{\*\}', 'temp_dynamic', text)

    'remove any special char except for .*'
    clean_text = re.sub(r'[\W]', '', clean_text.lower())
    clean_text = re.sub('temp_dynamic', '.*', clean_text)

    return clean_text


def assert_dlg(expected_text, response_text):
    execpted_text_clean = clean_text(str(expected_text))
    response_text_clean = clean_text(str(response_text))
    match = re.search(execpted_text_clean, response_text_clean)
    assert match is not None, \
        f"Expected '{expected_text}', but got '{response_text}'"


def write_to_log(session_id, request, response,logs_folder,requestName):
    if session_id:
        file_path = os.path.join(logs_folder, str(session_id))
        with open(file_path, "a") as file:
            json_str_request = json.dumps(request, indent=4)
            json_str_response = json.dumps(response, indent=4)
            file.write("--------------------------------------------------------------\n")
            file.write("Request for: ")
            file.write(requestName)
            file.write("\n")
            file.write(json_str_request)
            file.write("\n")
            file.write("Response")
            file.write("\n")
            file.write(json_str_response)
            file.write("\n")
