#!/usr/bin/env python3

'''
converts an existing setup.py file to a setup.cfg in the format expected by setuptools
'''

import setuptools

from unittest.mock import Mock, patch
import os, io, re, sys
from pathlib import Path
from functools import partial
from collections import defaultdict
from unittest.mock import Mock
from configparser import ConfigParser
import runpy


def execsetup(setup_py: Path):
    # Mock all function in the setuptools module.
    mock_setuptools = Mock()
    mock_setup = mock_setuptools.setup
    mock_find_packages = mock_setuptools.find_packages

    with patch.dict('sys.modules', {'setuptools': mock_setuptools}):
        cwd = Path.cwd()
        try:
            os.chdir(str(setup_py.parent))
            runpy.run_path(str(setup_py), run_name="__main__")
        finally:
            os.chdir(str(cwd))

    # Check if setup was called and retrieve the arguments
    if mock_setup.call_args is None:
        raise ValueError("setuptools.setup was not called within the setup.py script.")
    
    # Ensure that find_packages is also mocked if used
    if mock_find_packages.call_args is None:
        raise ValueError("setuptools.find_packages was not called within the setup.py script, but expected.")

    return mock_setup.call_args[1], mock_find_packages.call_args

def setup_to_cfg(setup_py_path, setup_cfg_path):
    print('\n---------------- setup_to_cfg.py ----------------')

    setup_py_file = Path(setup_py_path)
    setup_call_args, mock_find_packages = execsetup(setup_py_file)
    metadata, options, sections = py2cfg(setup_call_args, setup_py_file.parent, dangling_list_threshold=100, mock_find_packages=mock_find_packages)

    # Dump and reformat sections to ini format.
    config = ConfigParser(interpolation=None)
    if metadata:
        config['metadata'] = metadata
    if options:
        config['options'] = options
    for section, value in sections.items():
        config[section] = value

    # Load the existing setup.cfg if it exists
    setup_cfg = Path(setup_cfg_path)
    if setup_cfg.exists():
        setup_cfg_parser = ConfigParser()
        with open(setup_cfg, 'r') as f:
            setup_cfg_parser.read_file(f)
        config = merge_configs(setup_cfg_parser, config)

    with open(setup_cfg, 'w') as configfile:
        config.write(configfile)

    print(f"Converted setup.cfg has been saved to {setup_cfg_path}")

def py2cfg(setup, setuppy_dir, dangling_list_threshold, mock_find_packages):
    # Wrap these functions for convenience.
    global find_file, list_comma, list_semi, find_or_list_comma
    find_file = partial(find_file, setuppy_dir=setuppy_dir)
    list_comma = partial(list_comma, threshold=dangling_list_threshold)
    list_semi = partial(list_semi, threshold=dangling_list_threshold)

    sections = defaultdict(dict)

    find_or_list_comma = partial(find_or_list_comma, sections=sections, threshold=dangling_list_threshold, mock_find_packages=mock_find_packages)

    metadata = {}
    setif(setup, metadata, 'name')
    setif(setup, metadata, 'version')
    setif(setup, metadata, 'author')
    setif(setup, metadata, 'author_email')
    setif(setup, metadata, 'maintainer')
    setif(setup, metadata, 'maintainer_email')
    setif(setup, metadata, 'license', find_file)
    setif(setup, metadata, 'description')
    setif(setup, metadata, 'keywords', list_comma)
    setif(setup, metadata, 'url')
    setif(setup, metadata, 'download_url')
    setif(setup, metadata, 'long_description', find_file)
    setif(setup, metadata, 'long_description_content_type')
    setif(setup, metadata, 'classifiers', join_lines)
    setif(setup, metadata, 'platforms', list_comma)
    setif(setup, metadata, 'provides', list_comma)
    setif(setup, metadata, 'requires', list_comma)
    setif(setup, metadata, 'obsoletes', list_comma)
    setif(setup, metadata, 'project_urls', mapping)

    options = {}
    setif(setup, options, 'package_dir', mapping)
    setif(setup, options, 'py_modules', list_comma)
    setif(setup, options, 'packages', find_or_list_comma)
    setif(setup, options, 'zip_safe')
    setif(setup, options, 'setup_requires', list_semi)
    setif(setup, options, 'install_requires', list_semi)
    setif(setup, options, 'include_package_data')
    setif(setup, options, 'python_requires')
    setif(setup, options, 'use_2to3')
    setif(setup, options, 'use_2to3_fixers', list_comma)
    setif(setup, options, 'use_2to3_exclude_fixers', list_comma)
    setif(setup, options, 'convert_2to3_doctest', list_comma)
    setif(setup, options, 'scripts', list_comma)
    setif(setup, options, 'eager_resources', list_comma)
    setif(setup, options, 'dependency_links', list_comma)
    setif(setup, options, 'test_suite')
    setif(setup, options, 'tests_require', list_semi)
    setif(setup, options, 'include_package_data')
    setif(setup, options, 'namespace_packages', list_comma)
    setif(setup, options, 'include_package_data')

    entry_points = setup.get('entry_points')
    if entry_points:
        if isinstance(entry_points, dict):
            sections['options.entry_points'] = extract_section(entry_points)
        else:
            pass  # TODO: Handle entry_points in ini syntax.

    if 'extras_require' in setup:
        sections['options.extras_require'] = extract_section(setup['extras_require'])

    if 'package_data' in setup:
        sections['options.package_data'] = extract_section(setup['package_data'])

    if 'exclude_package_data' in setup:
        sections['options.exclude_package_data'] = extract_section(setup['exclude_package_data'])

    return metadata, options, sections


def find_file(content, setuppy_dir):
    '''
    Search for a file inside the setup.py directory matching the given text.
    Returns the original text if an exact match is not found.

      >>> find_file('BSD 3-Clause License\n\nCopyright....')
      'file: LICENSE'
      >>> find_file('Revised BSD License')
      'Revised BSD License'
    '''

    for path in (p for p in setuppy_dir.iterdir() if p.is_file()):
        try:
            if path.read_text() == content:
                return 'file: %s' % path.name
        except:
            pass
    return content


def join_lines(seq):
    return '\n' + '\n'.join(seq)


def list_semi(value, threshold):
    s = '; '.join(value)
    return join_lines(value) if len(s) > threshold else s


def mapping(value):
    return join_lines('\t' * 2 + k + " = " + v for k, v in value.items())

def list_comma(value, threshold):
    if isinstance(value, str):
        value = [value]  # Ensure the input is treated as a list with a single string element
    s = ', '.join(value)
    return s if len(s) <= threshold else join_lines(value)

# def list_comma_orig(value, threshold):
#     ''''''
#     value = value.split() if isinstance(value, str) else value
#     s = ', '.join(value)
#     return join_lines(value) if len(s) > threshold else s

# list_comma = list_comma


def ensure_list(value):
    return value if isinstance(value, (list, tuple)) else [value]


def find_or_list_comma(value, threshold, sections, mock_find_packages):
    # If find_packages() -> 'find:', else semicolon separated list.
    if isinstance(value, Mock):
        call = mock_find_packages.call_args
        if call is not None:
            args, kwargs = call.args, call.kwargs
            # Assuming you want to process args or kwargs further here
            # For example, if you need to extract a specific section from kwargs
            if 'findSection' in kwargs:
                findSection = kwargs['findSection']
                sections['options.packages.find'] = extract_section(findSection)
            return 'find:'
        else:
            raise ValueError("Expected find_packages to be called but it wasn't.")

    return list_comma(value, threshold)


def setif(src, dest, key, transform=None):
    if key in src:
        value = src[key]
        if transform:
            # Check if the transform function can handle lists or expects a single item
            if transform in [list_comma, list_semi, join_lines]:  # Add other list-handling functions as needed
                value = transform(value if isinstance(value, list) else [value])
            else:
                value = transform(value)
        dest[key] = value


def extract_section(value):
    '''
    Join all dictionary values into a semicolon separated list.

      >>> extract_section({'tests': ['pytest >= 3.0.0', 'tox >= 2.6.0']})
      {'tests': 'tox >= 2.6.0; pytest >= 3.0.0'}
    '''
    if isinstance(value, dict):
        return {k: list_semi(ensure_list(v)) for k, v in value.items()}


def merge_configs(cfg1, cfg2):
    """Merges two configurations"""
    def to_dict(cfg):
        return {k: dict(**v) for k, v in cfg.items()}

    def merge_dicts(d1, d2):
        d_out = {}

        # Get the set of all the keys between the two, trying to preserve
        # order (in Python 3.6) to avoid scrambling the sections randomly
        k1 = list(d1.keys())
        k2 = list(d2.keys())
        keys = set(d1.keys()) | set(d2.keys())

        def key_order(key):
            try:
                return k1.index(key)
            except ValueError:
                return k2.index(key)

        for k in sorted(keys, key=key_order):
            # The configuration dictionaries should be mappings from str to
            # dict, so if both keys are present, merge the dictionaries,
            # otherwise whichever one exists.
            v1 = d1.get(k, None)
            v2 = d2.get(k, None)

            assert not v1 or isinstance(v1, dict)
            assert not v2 or isinstance(v2, dict)

            if v1 and not v2:
                d_out[k] = v1
            elif v2 and not v1:
                d_out[k] = v2
            else:
                d_out[k] = v1.copy()
                d_out[k].update(v2)

        return d_out

    dict_merged = merge_dicts(*map(to_dict, (cfg1, cfg2)))

    merged_config = ConfigParser()
    merged_config.read_dict(dict_merged)

    return merged_config



if __name__ == '__main__':
    setup_to_cfg(
        'C:\.PythonProjects\SavedTests\_test_projects_for_building_packages\_extra_files_to_copy\setup_good.py',
        'C:\.PythonProjects\SavedTests\_test_projects_for_building_packages\_extra_files_to_copy\setup.cfg')