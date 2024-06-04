import os
from setup_to_cfg import setup_to_cfg
from format_cfg import format_cfg
from cfg_to_toml import cfg_to_toml
from validate_and_format_toml import validate_and_format_toml

def setup_to_pyproject(setup_file_path):
    '''
    Function Steps:
    
    - setup_to_cfg
    - format_cfg
    - cfg_to_toml
    - validate_and_format_toml
    
    App Steps:
    1. If the file is .toml, skip to the last step directly
    2. If the file is not .toml, convert the setup.py file to setup.cfg
    3. Format the setup.cfg file
    4. Convert the setup.cfg file to pyproject.toml
    5. Validate and format the pyproject.toml file
    '''
    
    setup_cfg_path = os.path.join(os.path.dirname(setup_file_path), 'setup.cfg')
    pyproject_toml_path = os.path.join(os.path.dirname(setup_file_path), 'pyproject.toml')
    
    ## If the file is .toml, skip to the last step directly
    if setup_file_path.endswith('.toml'):
        validate_and_format_toml(pyproject_toml_path)
        return

    ## Skip step 1 if the file extension is .cfg or .ini
    if not setup_file_path.endswith(('.cfg', '.ini')):
        setup_to_cfg(setup_file_path, setup_cfg_path)
    
    format_cfg(setup_cfg_path)
    cfg_to_toml(setup_cfg_path, pyproject_toml_path)
    validate_and_format_toml(pyproject_toml_path)

if __name__ == '__main__':
    setup_path = 'C:\\.PythonProjects\\SavedTests\\_test_projects_for_building_packages\\_extra_files_to_copy\\setup_good.py'
    setup_file_name = os.path.basename(setup_path)
    
    print(f'-- Start the Conversion from {setup_file_name} --')
    setup_to_pyproject(setup_path)
    print(f'-- completed the conversion from {setup_file_name} to pyproject.toml --')