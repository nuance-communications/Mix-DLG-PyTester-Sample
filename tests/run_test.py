from dlg import *
import pytest
import yaml

'''
Base test case that is used to validate the project setup before running any test cases
'''
@pytest.mark.dependency()
def test_check_project_setup(setup_config, check_setup):
    pass

''' 
Fucntion is required to process safe_load() without converting certain string values like "true", "false", "yes", "no", etc. to boolean type
This custom constructor function removes the conversion of "true", "false", "yes", "no" to boolean and returns the actual string
'''
def boolean_as_string_constructor(loader, node):
    value = loader.construct_scalar(node)
    return value

'''
Function that retrieves all test cases from the ./tests/test_cases/ folder.
If the function is called with the argument "tests", it returns a list of all test cases.
If the function is called with any other argument, it returns a list of strings containing the names of all test cases.
'''
def get_test_items(type):
    test_cases = []
    test_cases_names = []
    test_folder = "./tests/test_cases/"
    try:
        for filename in os.listdir(test_folder):
            if filename.lower().endswith(".yaml") or filename.lower().endswith(".yml"):
                yaml.SafeLoader.add_constructor('tag:yaml.org,2002:bool', boolean_as_string_constructor)
                with open(os.path.join(test_folder, filename)) as f:
                    data = yaml.safe_load(f)
                    for test_case in data['test_cases']:
                        test_cases.append(test_case)
                        test_cases_names.append(str(test_case['name']) + ".")
    except:
        pass
    if type == "tests":
        return test_cases
    else:
        return test_cases_names

'''
Main test case that is used to read all test cases and run them one by one
'''
@pytest.mark.dependency(depends=["test_check_project_setup"])
@pytest.mark.parametrize("test_cases", get_test_items("tests"), ids=get_test_items("names"))
def test_(session, test_cases):
    if session.session_started:
        for item, value in test_cases.items():
            'loop through each test case item'
            if item  =="description":
                setattr(test_, 'test_description', value)
            if item == "userData":
                data = {}
                data["userData"] = value
                session.update_request(data)
            if item == "steps":
                test_text = []
                test_action = []
                start_node = True
                for step in value:
                    if isinstance(step, dict):
                        text, action = next(iter(step.items()))
                        action = str(action)
                    else:
                        text = str(step)
                        action = str("empty_combine_with_next_step")
                    if start_node == True:
                        start_node = False
                        test_text.append(text)
                        test_action.append(None)
                        test_action.append(action)
                    else:
                        test_text.append(text)
                        test_action.append(action)

                for action, text in zip(test_action, test_text):
                    if action != "empty_combine_with_next_step":
                        session.execute_request(action, text)
                    else:
                        assert_dlg(text,session.response)
    else:
        pytest.exit(f"Failed to start Mix session: {session.response}")
