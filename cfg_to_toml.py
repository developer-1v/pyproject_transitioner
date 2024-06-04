from ini2toml.api import Translator


def cfg_to_toml(setup_cfg_path, pyproject_toml_path):
    print('\n---------------- cfg_to_toml.py ----------------')
    
    with open(setup_cfg_path, 'r') as cfg_file:
        cfg_contents = cfg_file.read()
    
    toml_contents = Translator().translate(cfg_contents, "setup.cfg")
    
    toml_lines = toml_contents.split('\n')
    filtered_toml_lines = [line for line in toml_lines if 'test-suite' not in line]
    filtered_toml_contents = '\n'.join(filtered_toml_lines)
    
    with open(pyproject_toml_path, 'w') as toml_file:
        toml_file.write(filtered_toml_contents)

    print('Converted setup.cfg to pyproject.toml')

if __name__ == '__main__':
    cfg_to_toml(
        'C:\\.PythonProjects\\SavedTests\\_test_projects_for_building_packages\\_extra_files_to_copy\\setup_formatted.cfg',
        'C:\\.PythonProjects\\SavedTests\\_test_projects_for_building_packages\\_extra_files_to_copy\\pyproject.toml'
    )

