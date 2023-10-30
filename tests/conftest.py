from datetime import datetime
from py.xml import html
import pytest
from dlg import *
import jsonschema
import json
import yaml


'''
This function is a hook function that is called after collecting tests in pytest.
It modifies the test items collected by pytest, however for the purpose of this script we are only
checking that the user is running pytest from the correct folder.
'''
def pytest_collection_modifyitems(items):
    ini_file = os.path.join(os.getcwd(), 'pytest.ini')
    if not os.path.isfile(ini_file):
        pytest.exit('pytest.ini file not found, tests will not run')

'''
Link to more notes around this: https://pytest-html.readthedocs.io/en/latest/user_guide.html
This function is a hook function that is called to add content to the summary section of the HTML report.
It takes three arguments:
- prefix: a list of HTML elements that appear before the summary content.
- summary: the summary content to be added to the report.
- postfix: a list of HTML elements that appear after the summary content.
This is just a placholder for today and is not being used.
'''
def pytest_html_results_summary(prefix, summary, postfix):
    prefix.extend([html.p("TBD")])

'''
This function is a hook function that is called to set the title of the HTML report.
It takes one argument:
- report: the report object to be modified.
'''
def pytest_html_report_title(report):
    report.title = "Mix Test Cases"

'''
This function is a hook function that is called at the beginning of the pytest run to configure options and plugins.
It takes one argument:
- config: the configuration object that is used to configure pytest.
This is being used to set the report directory and to rename the report file with a timestamp
'''
def pytest_configure(config):
    # create logs folder
    dlg_payload_log()

    # update report name with timestamp
    report_dir = "./reports"
    timestamp = datetime.utcnow().strftime('%Y-%m-%d_%H-%M-%S')
    report_name = "test_report_" + str(timestamp) + ".html"
    report_path = os.path.join(report_dir, report_name)
    config.option.htmlpath = report_path

'''
This function is a hook function that is called to add content to the table header of the HTML report.
It takes one argument:
- cells: a list of HTML elements that represent the cells in the table header.
This is being used to create two new col for our report (Session ID & Time)
'''
def pytest_html_results_table_header(cells):
    cells.insert(2, html.th("Test Description"))
    cells.insert(3, html.th("Session ID"))
    cells.insert(4, html.th("Time", class_="sortable time", col="time"))
    cells.pop()

'''
This function is a hook function that is called to add content to a row in the results table of the HTML report.
It takes two arguments:
- report: the report object that represents the test report for the current item.
- cells: a list of HTML elements that represent the cells in the current row.
This is being used to update the Session ID & Time col
'''
def pytest_html_results_table_row(report, cells):
    cells.insert(2, html.td(report.test_description))
    cells.insert(3, html.td(report.session_id))
    cells.insert(4, html.td(datetime.utcnow(), class_="col-time"))
    cells.pop()

'''
This function is a hook function that is called to create a report object for each test item and its call.
It takes two arguments:
- item: the test item object that represents the item being tested.
- call: the call object that represents the call to the test item.
This is being used to retrieve the Session ID & modelUrn 
'''
@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_makereport(item, call):
    outcome = yield
    report = outcome.get_result()
    session = getattr(item.function, 'session', None)
    report.session_id = str(session)
    modelUrn = getattr(item.function, 'modelUrn', None)
    report.modelUrn = str(modelUrn)
    test_description = getattr(item.function, 'test_description', None)
    report.test_description = str(test_description)

'''
This fixture function returns a session object that is used to run tests.
It takes two arguments:
- request: the pytest request object.
- setup_config: a fixture function that sets up the test configuration and returns a tuple with two elements:
     - config: the test configuration object.
     - json_valid: a boolean flag that indicates whether the test configuration is valid or not.
This function is being used to start the Mix session and yield the session to the test case being run 
'''
@pytest.fixture(scope='function')
def session(request, setup_config):
    config, json_valid = setup_config
    with session_start(config) as session:
        setattr(request.function, 'session', session.session_id)
        setattr(request.function, 'modelUrn', session.project_data["modelUrn"])
        yield session

'''
This is a function that is used to validate yaml test case
It takes two arguments:
- file_path: the pat to the test case
This function returns true if the test case has a valid test case schema
'''
def validate_test_cases_yaml_schema(file_path):
    # Read YAML data from file
    with open(file_path, 'r') as f:
        yaml_data = yaml.safe_load(f)
        json_data = json.dumps(yaml_data)

    # Test Case format JSON schema
    schema = {
        "type": "object",
        "properties": {
            "test_cases": {
                "type": "array",
                "minItems": 1,
                "items": {
                    "type": "object",
                    "properties": {
                        "name": {"type": "string"},
                        "description": {"type": "string"},
                        "steps": {"type": "array", "minItems": 1}
                    },
                    "required": ["name", "description", "steps"]
                }
            }
        },
        "required": ["test_cases"]
    }

    # Validate YAML test cases against expected schema
    try:
        jsonschema.validate(json.loads(json_data), schema)
        valid_test_file = True
    except yaml.YAMLError as e:
        valid_test_file = False
    return valid_test_file

'''
This fixture function sets up the test configuration and returns a tuple with two elements:
 - config: the test configuration object.
 - json_valid: a boolean flag that indicates whether the test configuration is valid or not.
'''
@pytest.fixture(scope='session')
def setup_config():
    current_dir = os.path.dirname(os.path.abspath(__file__))
    config = os.path.join(current_dir, "config.json")
    json_valid = False
    if not os.path.exists(config):
        raise ValueError(f"Config file {config} does not exist")
    try:
        with open(config) as f:
            json.load(f)
            json_valid = True
    except json.JSONDecodeError as e:
        pytest.exit(f"Config file {config} is not valid JSON: {e}")
    return config, json_valid

'''
This fixture function validates if the pytest project is setup correctly before running any tests
'''
@pytest.fixture(scope="session")
def check_setup():
    folder_path_test_cases = "./tests/test_cases/"
    folder_path_config = "./tests/config.json"
    if not os.path.exists(folder_path_test_cases):
        pytest.exit(f"Folder not found: {folder_path_test_cases}")
    if not os.path.exists(folder_path_config):
        pytest.exit(f"Config not found: {folder_path_config}")

    yaml_files = []
    valid_test_file = False
    error_msg = ""
    file_with_error = ""
    for file_name in os.listdir(folder_path_test_cases):
        if file_name.lower().endswith(".yaml") or file_name.lower().endswith(".yml"):
            file_path = os.path.join(folder_path_test_cases, file_name)
            try:
                with open(file_path) as f:
                    yaml.safe_load(f)
                    valid_test_file = validate_test_cases_yaml_schema(file_path)
            except Exception as e:
                error_msg = e
                file_with_error = file_path
                valid_test_file = False
                break
            yaml_files.append(file_path)

    if valid_test_file == False:
        pytest.exit(
            f"Invalid test case file(s) \n Searched folder: {folder_path_test_cases} \n File with issue: {file_with_error} \n Exiting with error: {error_msg}")
