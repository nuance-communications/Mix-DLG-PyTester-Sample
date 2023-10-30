# Mix Dialog Validation Project

The project aims to provide examples of how one can validate their Mix project through the DLGaaS APIs with the pytest automation framework. The project uses a simple YAML format to write test cases that is supported by the sample test app. The project also assumes you have already set up your Python gRPC environment following the Mix documentation [[here](https://docs.nuance.com/mix/apis/dialog-grpc/v1/grpc-setup-dlg/)].

The project has two sample test cases that can be used to test the Coffee app quick start [[here]](https://docs.nuance.com/mix/get_started/quick_start/):

- Ordering a large coffee step by step
- Ordering a small coffee step by step

Each test case has a name, a description, and a sequence of steps that involve user prompts and NLU actions or responses. The project uses a test model that outlines what needs to be validated in each Mix interaction. The test model specifies the expected input, output, and context for each dialog turn. The project compares the actual results from the DLGaaS APIs with the expected results from the test model and reports any discrepancies or failures.


## Dependencies

- Python 3.8.
- Pytest 7.3.1
- The generated Python stubs from gRPC setup. The sample client imports and makes use of these stubs.
- gRPC setup: [[here](https://docs.nuance.com/mix/apis/dialog-grpc/v1/grpc-setup-dlg/)]
- Your client ID and secret from Prerequisites from Mix. This is needed to authorize you to access your previously built and deployed Mix Dialog and NLU model.
- The Mix URN for your Dialog model


## Installation

1. To install the dependencies:

        pip install -r requirements.txt

2. Generate Python stubs from gRPC setup (nuance and google folders)

3. copy all nuance and google packages to match the Project Structure outlined below

4. copy and rename "config_sample.json" to "config.json"

5. update config.json with your details (Mix URN, client ID and secret )

6. add/update test cases in the /tests/test_case folder <br>
&emsp; use the test_sample.yml file as a guide  <br>
&emsp; test cases files need to be ymal extension   <br>
&emsp; test cases files need be in the test_case folder  <br>


## Usage

To run the tests, run on project root folder (ps-mix-tester)

    ... ps-mix-tester> python -m pytest 


## Contributing

Contributions are welcome! Please submit a pull request with your changes.

## Project Structure

<pre>
ps_mix_tester/  
│  
├── dlg.py  
│  
├── pytest.ini  
│   
├── google/  -- google grpc packages  
│   
├── nuance/  -- nuance packages
│           ├── asr/    
│           ├── dlg/    
│           ├── nlu/    
│           ├── tts/  
├── tests/  
│           ├── test_cases/
│                           ├── test_sample.yml 
│                           ├── ...  
│           ├── config.json 
│           ├── conftest.py  
│           ├── run_test.py
│           └── ...  
├── reports/  
│ 
├── logs/  
│ 
├── requirements.txt  
│  
└── README.md  
</pre>
## License

This source code is licensed under the MIT license found in the LICENSE.md file in the root directory of this source tree.
