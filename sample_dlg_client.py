import argparse
import logging
import requests
from google.protobuf.json_format import MessageToJson, MessageToDict
import grpc
import json
from nuance.dlg.v1.common.dlg_common_messages_pb2 import *
from nuance.dlg.v1.dlg_messages_pb2 import *
from nuance.dlg.v1.dlg_interface_pb2 import *
from nuance.dlg.v1.dlg_interface_pb2_grpc import *

log = logging.getLogger(__name__)


def parse_args():
    parser = argparse.ArgumentParser(
        prog="dlg_client.py",
        usage="%(prog)s [-options]",
        add_help=False,
        formatter_class=lambda prog: argparse.HelpFormatter(
            prog, max_help_position=45, width=100)
    )

    options = parser.add_argument_group("options")
    options.add_argument("-h", "--help", action="help",
                         help="Show this help message and exit")
    options.add_argument("--config", nargs="?", help="configure your mix project (required)")
    return parser.parse_args()


def setup_project_config(config):
    project_config = {"auth_url": "https://auth.crt.nuance.com/oauth2/token", "serverUrl": "dlg.api.nuance.com:443",
                      "nlu_uri": "nlu.api.nuance.com:443", "client_id": None, "secret": None, "modelUrn": None,
                      "scope": "dlg"}

    if config:
        config_file_contents = open(config)
        config_json = json.load(config_file_contents)
        config_file_contents.close()

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
        log.info(f'Error configs are not setup')
        log.info(f'required values: client_id,secret,dlg_modelUrn and nlu_modelUrn')

    return project_config


def get_token(project_data):
    payload = {"grant_type": "client_credentials", "scope": project_data["scope"]}
    try:
        response = requests.post(project_data["auth_url"], auth=(project_data["client_id"], project_data["secret"]),
                                 data=payload)
        response.json()["access_token"]
    except Exception as e:
        print(f'get_token failed for:')
        print(f'client_id={project_data["client_id"]}')
        print(f'secret={project_data["secret"]}')
        print(f'with response={response}')
    return response.json()["access_token"]


def create_channel(project_data, token):
    log.debug("Adding CallCredentials with token %s" % token)
    call_credentials = grpc.access_token_call_credentials(token)

    log.debug("Creating secure gRPC channel")
    channel_credentials = grpc.ssl_channel_credentials()
    channel_credentials = grpc.composite_channel_credentials(channel_credentials, call_credentials)
    channel = grpc.secure_channel(project_data["serverUrl"], credentials=channel_credentials)

    return channel


def read_session_id_from_response(response_obj):
    try:
        session_id = response_obj.get('payload').get('sessionId', None)
    except Exception as e:
        raise Exception("Invalid JSON Object or response object")
    if session_id:
        return session_id
    else:
        raise Exception("Session ID is not present or some error occurred")


def start_request(stub, model_ref_dict, session_id, selector_dict={}):
    selector = Selector(channel=selector_dict.get('channel'),
                        library=selector_dict.get('library'),
                        language=selector_dict.get('language'))
    start_payload = StartRequestPayload(model_ref=model_ref_dict)
    start_req = StartRequest(session_id=session_id,
                             selector=selector,
                             payload=start_payload)
    log.debug(f'Start Request: {start_req}')
    start_response, call = stub.Start.with_call(start_req)
    response = MessageToDict(start_response)
    log.debug(f'Start Request Response: {json.dumps(response, ensure_ascii=False, indent=4)}')
    return response, call


def execute_request(stub, session_id, selector_dict={}, payload_dict={}):
    selector = Selector(channel=selector_dict.get('channel'),
                        library=selector_dict.get('library'),
                        language=selector_dict.get('language'))
    input = UserInput(user_text=payload_dict.get('user_input').get('userText'))
    execute_payload = ExecuteRequestPayload(
        user_input=input)
    execute_request = ExecuteRequest(session_id=session_id,
                                     selector=selector,
                                     payload=execute_payload)
    log.debug(f'Execute Request: {execute_payload}')
    execute_response, call = stub.Execute.with_call(execute_request)
    response = MessageToDict(execute_response)
    log.debug(f'Execute Response: {json.dumps(response, ensure_ascii=False, indent=4)}')
    return response, call


def execute_stream_request(args, stub, session_id, selector_dict={}):
    # Receive stream outputs from Dialog
    stream_outputs = stub.ExecuteStream(build_stream_input(args, session_id, selector_dict))
    log.debug(f'execute_responses: {stream_outputs}')
    responses = []
    audio = bytearray(b'')

    for stream_output in stream_outputs:
        if stream_output:
            # Extract execute response from the stream output
            response = MessageToDict(stream_output.response)
            if response:
                responses.append(response)
            audio += stream_output.audio.audio
    return responses, audio


def build_stream_input(args, session_id, selector_dict):
    selector = Selector(channel=selector_dict.get('channel'),
                        library=selector_dict.get('library'),
                        language=selector_dict.get('language'))

    try:
        with open(args.audioFile, mode='rb') as file:
            audio_buffer = file.read()

        # Hard code packet_size_byte for simplicity sake (approximately 100ms of 16KHz mono audio)
        packet_size_byte = 3217
        audio_size = sys.getsizeof(audio_buffer)
        audio_packets = [audio_buffer[x:x + packet_size_byte] for x in range(0, audio_size, packet_size_byte)]

        # For simplicity sake, let's assume the audio file is PCM 16KHz
        user_input = None
        asr_control_v1 = {'audio_format': {'pcm': {'sample_rate_hz': 16000}}}

    except:
        # Text interpretation as normal
        asr_control_v1 = None
        audio_packets = [b'']
        user_input = UserInput(user_text=args.textInput)

    # Build execute request object
    execute_payload = ExecuteRequestPayload(user_input=user_input)
    execute_request = ExecuteRequest(session_id=session_id,
                                     selector=selector,
                                     payload=execute_payload)

    # For simplicity sake, let's assume the audio file is PCM 16KHz
    tts_control_v1 = {'audio_params': {'audio_format': {'pcm': {'sample_rate_hz': 16000}}}}
    first_packet = True
    for audio_packet in audio_packets:
        if first_packet:
            first_packet = False

            # Only first packet should include the request header
            stream_input = StreamInput(
                request=execute_request,
                asr_control_v1=asr_control_v1,
                tts_control_v1=tts_control_v1,
                audio=audio_packet
            )
            log.debug(f'Stream input initial: {stream_input}')
        else:
            stream_input = StreamInput(audio=audio_packet)

        yield stream_input


def stop_request(stub, session_id=None):
    stop_req = StopRequest(session_id=session_id)
    log.debug(f'Stop Request: {stop_req}')
    stop_response, call = stub.Stop.with_call(stop_req)
    response = MessageToDict(stop_response)
    log.debug(f'Stop Response: {response}')
    return response, call


def main():
    args = parse_args()
    project_data = setup_project_config(args.config)
    token = get_token(project_data)
    log_level = logging.DEBUG
    logging.basicConfig(
        format='%(asctime)s %(levelname)-5s: %(message)s', level=log_level)
    with create_channel(project_data, token) as channel:
        stub = DialogServiceStub(channel)
        model_ref_dict = {
            "uri": project_data["modelUrn"],
            "type": 0
        }
        selector_dict = {
            "channel": "default",
            "language": "en-US",
            "library": "default"
        }
        response, call = start_request(stub,
                                       model_ref_dict=model_ref_dict,
                                       session_id=None,
                                       selector_dict=selector_dict
                                       )
        session_id = read_session_id_from_response(response)
        log.debug(f'Session: {session_id}')
        assert call.code() == grpc.StatusCode.OK
        log.debug(f'Initial request, no input from the user to get initial prompt')
        payload_dict = {
            "user_input": {
                "userText": None
            }
        }
        response, call = execute_request(stub,
                                         session_id=session_id,
                                         selector_dict=selector_dict,
                                         payload_dict=payload_dict
                                         )
        assert call.code() == grpc.StatusCode.OK

        while "qaAction" in str(response):

            next_input = ""
            while next_input == "":
                next_input = input(
                    "Enter User Input: ")
                if "" == next_input.strip():
                    next_input = ""
            log.debug(f'request, passing in user input')
            payload_dict = {
                "user_input": {
                    "userText": next_input
                }
            }

            response, call = execute_request(stub,
                                             session_id=session_id,
                                             selector_dict=selector_dict,
                                             payload_dict=payload_dict
                                             )
            assert call.code() == grpc.StatusCode.OK



if __name__ == '__main__':
    main()
