from __future__ import annotations

from print_tricks import pt
import os, re
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, Union
from pydantic import BaseModel, Field, root_validator, validator
import tomlkit


## HANDLER Classes
class Handler(ABC):
    def __init__(self, path: Optional[str] = None):
        self._path = path

    @property
    def path(self):
        if self._path is None:
            root = os.getcwd()
            while True:
                path = os.path.join(root, "pyproject.toml")
                if os.path.isfile(path):
                    self._path = path
                    break

                new_root = os.path.dirname(root)
                if new_root == root:
                    raise OSError("could not locate a `pyproject.toml` file")

                root = new_root

        return self._path

    def read(self) -> str:
        with open(self.path, "r", encoding="utf-8") as f:
            return f.read()

    def write(self, text: str):
        with open(self.path, "w", encoding="utf-8") as f:
            f.write(text)

    @abstractmethod
    def load(self) -> Dict[str, Any]:
        """
        Deserializes the pyproject.toml file.
        """

    @abstractmethod
    def save(self, data: Dict[str, Any]):
        """
        Serializes the `data` to the pyproject.toml file.
        """


class CommentPreservingHandler(Handler):
    '''Will have to build my own:
    Tomli doesn't support comments. 
    Tomlikit does, but it outputs lists all on one line instead of on multilines. 
    
    - Probably start with Tomli and make a fork that will support comments (or search
    for a fork someone else has already made that supports comments)
    
    '''

class StandardHandler(Handler):
    def load(self):
        import tomli

        return tomli.loads(self.read())

    def save(self, data):
        import tomli_w
        serialized_data = tomli_w.dumps(data)
        # print("Saving data:", serialized_data)  # Debug print to check what is being saved
        self.write(serialized_data)


## UTILITIES
def get_handler(path: Optional[str] = None):
    # return CommentPreservingHandler(path)
    return StandardHandler(path)


def normalize_project_name(name):
    # https://www.python.org/dev/peps/pep-0503/#normalized-names
    return re.sub(r"[-_.]+", "-", name).lower()



## VALIDATOR Classes
class Validator(ABC):
    def __init__(self):
        self.fixable = True
        self.exit_early = False

    @abstractmethod
    def validate(self, data: Dict[str, Any], errors: List[str], warnings: List[str]):
        """
        Validates the provided raw deserialized pyproject.toml `data`. If any errors cannot
        be automatically fixed, set `self.fixable` to `False`. If any errors may interfere
        with subsequent validation, set `self.exit_early` to `True`.
        """

    @abstractmethod
    def fix(self, data: Dict[str, Any]):
        """
        Fixes the provided raw deserialized pyproject.toml `data`. This method will not be
        called if `self.fixable` is set to `False`.
        """


class SpecValidator(Validator):
    def validate(self, data, errors, warnings):
        # Slow import

        try:
            BuildSystemConfig(**data.get("build-system", {}))
        except Exception as e:
            self.fixable = False
            self.exit_early = True
            errors.append(str(e))

        try:
            ProjectConfig(**data.get("project", {}))
        except Exception as e:
            self.fixable = False
            self.exit_early = True
            errors.append(str(e))

    def fix(self, data):  # no cov
        """
        Will never be called.
        """


class NameValidator(Validator):
    def __init__(self):
        super().__init__()

        self._name = ""

    def validate(self, data, errors, warnings):
        name = data["project"]["name"]

        # https://www.python.org/dev/peps/pep-0508/#names
        if not re.search("^([A-Z0-9]|[A-Z0-9][A-Z0-9._-]*[A-Z0-9])$", name, re.IGNORECASE):
            self.fixable = False
            errors.append("must only contain ASCII letters/digits, underscores, hyphens, and periods")
            return

        self._name = normalize_project_name(name)

        if name != self._name:
            errors.append(f"should be {self._name}")

    def fix(self, data):
        data["project"]["name"] = self._name


class DependencyValidator(Validator):
    def __init__(self):
        super().__init__()

        self._dependencies = []
        self._optional_dependencies = {}

    def validate(self, data, errors, warnings):
        project_data = data["project"]

        self._validate_dependencies(project_data, errors, warnings)
        self._validate_optional_dependencies(project_data, errors, warnings)

    def fix(self, data):
        if self._dependencies:
            data["project"]["dependencies"] = self._dependencies

        if self._optional_dependencies:
            data["project"]["optional-dependencies"] = self._optional_dependencies

    def _validate_dependencies(self, project_data, errors, warnings):
        dependencies = project_data.get("dependencies", [])

        self._dependencies = self._validate_dependency_list(dependencies, errors, warnings)

    def _validate_optional_dependencies(self, project_data, errors, warnings):
        optional_dependencies = project_data.get("optional-dependencies", {})

        normalized = {}
        for name, dependencies in optional_dependencies.items():
            normalized[name] = self._validate_dependency_list(
                dependencies, errors, warnings, message_prefix=f"optional `{name}` dependencies"
            )

        self._optional_dependencies = normalized

    def _correct_dependency_syntax(self, dependency):
        # Remove unnecessary semicolons
        corrected_dependency = dependency.replace(';', '')
        # Correct version specifier errors carefully
        corrected_dependency = re.sub(r'(?<=[^><=!])=', '==', corrected_dependency)
        # Correct multiple equal signs and misplaced relational operators
        corrected_dependency = re.sub(r'(?<=[^><=!])={2,}', '==', corrected_dependency)
        corrected_dependency = re.sub(r'(?<=[^><=!])>{2,}', '>', corrected_dependency)
        corrected_dependency = re.sub(r'(?<=[^><=!])<{2,}', '<', corrected_dependency)
        # Remove extra symbols after the first relational operator
        corrected_dependency = re.sub(r'([><=!]{1,2})[^0-9]*([\d.]+)', r'\1\2', corrected_dependency)
        return corrected_dependency

    def _validate_and_normalize_dependency(self, corrected_dependency, index, message_prefix, errors, warnings):
        from packaging.requirements import InvalidRequirement, Requirement
        try:
            requirement = Requirement(corrected_dependency)
            requirement.name = normalize_project_name(requirement.name)
            normalized_dependency = str(requirement).lower().replace('"', "'")
            if corrected_dependency != normalized_dependency:
                warnings.append(f"{message_prefix} #{index} was corrected from '{corrected_dependency}' to '{normalized_dependency}'")
            return normalized_dependency
        except InvalidRequirement as e:
            errors.append(f"{message_prefix} #{index}: '{corrected_dependency}' -> Error: {e}")
            self.fixable = False
            return corrected_dependency  # Return the original if there's an error

    def _validate_dependency_list(self, dependencies, errors, warnings, message_prefix="dependencies"):
        normalized_dependencies = []
        for i, dependency in enumerate(dependencies, 1):
            corrected_dependency = self._correct_dependency_syntax(dependency)
            normalized_dependency = self._validate_and_normalize_dependency(corrected_dependency, i, message_prefix, errors, warnings)
            normalized_dependencies.append(normalized_dependency)

        # Sort dependencies to avoid "dependencies are not sorted" error
        normalized_dependencies.sort()

        # Check if the sorted list is different from the input list
        if [dep.lower() for dep in dependencies] != [dep.lower() for dep in normalized_dependencies]:
            warnings.append(f"{message_prefix} are not sorted. Corrected order: {', '.join(normalized_dependencies)}")
            self.fixable = True  # Indicate that sorting can be fixed

        return normalized_dependencies

def get_validators():
    # allow choices one day
    return {"specs": SpecValidator(), "naming": NameValidator(), "dependencies": DependencyValidator()}


## PYDANTIC Models

class LicenseTableLegacy(BaseModel):
    file: Optional[str]
    text: Optional[str]

    @root_validator(pre=True)
    def _pre_validation(cls, values):
        if "file" in values and "text" in values:
            raise ValueError("cannot contain both a `file` and `text` field")

        return values


class AuthorTable(BaseModel):
    email: Optional[str]
    name: Optional[str]


class LicenseFilesTable(BaseModel):
    globs: Optional[List[str]]
    paths: Optional[List[str]]

    @root_validator(pre=True)
    def _pre_validation(cls, values):
        if not ("globs" in values or "paths" in values):
            raise ValueError("must contain either a `globs` or `paths` field")

        return values


class ReadmeTable(BaseModel):
    charset: Optional[str]
    content_type: str = Field(alias="content-type")
    file: Optional[str]
    text: Optional[str]

    @root_validator(pre=True)
    def _pre_validation(cls, values):
        if "file" in values and "text" in values:
            raise ValueError("cannot contain both a `file` and `text` field")

        return values

    @validator("content_type")
    def _validate_content_type(cls, v, field):
        known_content_types = ("text/markdown", "text/x-rst", "text/plain")
        if v not in known_content_types:
            raise ValueError(f'must be one of: {", ".join(known_content_types)}')

        return v


class BuildSystemConfig(BaseModel):
    """
    https://www.python.org/dev/peps/pep-0517/#source-trees
    """

    backend_path: Optional[List[str]] = Field(alias="backend-path")
    build_backend: str = Field(alias="build-backend")
    requires: List[str]


class ProjectConfig(BaseModel):
    """
    https://www.python.org/dev/peps/pep-0621/#details
    """

    authors: Optional[List[AuthorTable]]
    classifiers: Optional[List[str]]
    dependencies: Optional[List[str]]
    description: Optional[str]
    dynamic: Optional[List[str]]
    entry_points: Optional[Dict[str, Dict[str, str]]] = Field(alias="entry-points")
    gui_scripts: Optional[Dict[str, str]] = Field(alias="gui-scripts")
    keywords: Optional[List[str]]
    license: Optional[Union[str, LicenseTableLegacy]]
    license_files: Optional[LicenseFilesTable] = Field(alias="license-files")
    maintainers: Optional[List[AuthorTable]]
    name: str
    optional_dependencies: Optional[Dict[str, List[str]]] = Field(alias="optional-dependencies")
    readme: Optional[Union[str, ReadmeTable]]
    scripts: Optional[Dict[str, str]]
    urls: Optional[Dict[str, str]]
    version: Optional[str]

    @validator("readme")
    def _validate_readme(cls, v, field):
        if not isinstance(v, str):
            return v

        known_extensions = (".md", ".rst", ".txt")
        if not v.lower().endswith(known_extensions):
            raise ValueError(f'must have one of the following extensions: {", ".join(known_extensions)}')

        return v

    @validator("dynamic", pre=False)
    def _validate_dynamic(cls, v, field):
        if v is not None and "name" in v:
            # this would fail later on in the redefined check but let's be explicit
            raise ValueError("the `name` field must not be listed as dynamic")

        return v

    @root_validator(pre=False)
    def _validate_dynamic_fields(cls, values):
        static_fields = dict(values)
        dynamic_fields = set(static_fields.pop("dynamic", None) or [])

        required_fields = ["version"]
        missing = [
            field for field in required_fields if static_fields.get(field) is None and field not in dynamic_fields
        ]
        if missing:
            raise ValueError(f'missing field(s): {", ".join(missing)}')

        redefined = [field for field, value in static_fields.items() if value is not None and field in dynamic_fields]
        if redefined:
            raise ValueError(f'field(s) defined but also listed as dynamic: {", ".join(redefined)}')

        return values


def validate_and_format_toml(config_path=None, fix_errors=False):
    print('\n---------------- validate_toml.py (validate and format) ----------------')


    handler = get_handler(config_path)
    try:
        data = handler.load()
    except Exception as e:
        print(e)
        return

    errors_occurred = False
    unfixable_errors = False
    need_fixing = False
    for name, validator in get_validators().items():
        errors = []
        warnings = []
        validator.validate(data, errors, warnings)

        if errors or warnings:
            print(f"<<< {name} >>>")
            for error in errors:
                print(f"error: {error}")
            for warning in warnings:
                print(f"warning: {warning}")

        if errors or warnings:  # Check if there are any errors or warnings
            errors_occurred = True
            if fix_errors and (validator.fixable or warnings):
                need_fixing = True
                validator.fix(data)
            else:
                unfixable_errors = True
                if validator.exit_early:
                    break

    # pt(need_fixing, unfixable_errors)
    if need_fixing and not unfixable_errors:
        handler.save(data)
        errors_occurred = False

    print('Formatted and Validated new pyproject.toml file')
    
    return not errors_occurred

if __name__ == "__main__":
    toml_file_path = r'C:\.PythonProjects\SavedTests\_test_projects_for_building_packages\_extra_files_to_copy\pyproject.toml'
    success = validate_and_format_toml(config_path=toml_file_path, fix_errors=True)
    print("Validation successful:", success)

