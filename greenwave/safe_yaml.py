# SPDX-License-Identifier: GPL-2.0+
"""
Provides a way of defining type-safe YAML parsing.
"""
from typing import Dict

from dateutil import tz
from dateutil.parser import parse
import yaml

safe_yaml_tag_to_class: Dict[str, object] = {}


class SafeYAMLError(RuntimeError):
    """
    Exception raised when an unexpected type is found in YAML.
    or validation fails (see SafeYAMLObject.validate()).
    """


class SafeYAMLAttribute(object):
    """
    Base class for SafeYAMLObject attributes (in SafeYAMLObject.safe_yaml_attributes dict).
    """

    def __init__(self, optional=False):
        self.optional = optional

    def from_yaml(self, loader, node):
        raise NotImplementedError()

    def from_value(self, value):
        raise NotImplementedError()

    def to_json(self, value):
        raise NotImplementedError()

    @property
    def default_value(self):
        raise NotImplementedError()


class SafeYAMLDict(SafeYAMLAttribute):
    """
    YAML object attribute representing a dict.
    """
    def __init__(self, **args):
        super().__init__(**args)

    def from_yaml(self, loader, node):
        value = loader.construct_mapping(node)
        return self.from_value(value)

    def from_value(self, value):
        if isinstance(value, dict):
            return value

        raise SafeYAMLError('Expected a dict value, got: {}'.format(value))

    def to_json(self, value):
        return value

    @property
    def default_value(self):
        return {}


class SafeYAMLBool(SafeYAMLAttribute):
    """
    YAML object attribute representing a boolean value.
    """
    def __init__(self, default=False, **args):
        super().__init__(**args)
        self.default = default

    def from_yaml(self, loader, node):
        value = loader.construct_scalar(node)
        value = yaml.safe_load(value)
        return self.from_value(value)

    def from_value(self, value):
        if isinstance(value, bool):
            return value

        raise SafeYAMLError('Expected a boolean value, got: {}'.format(value))

    def to_json(self, value):
        return value

    @property
    def default_value(self):
        return self.default


class SafeYAMLString(SafeYAMLAttribute):
    """
    YAML object attribute representing a string value.
    """
    def __init__(self, default=None, **args):
        super().__init__(**args)
        self.default = default

    def from_yaml(self, loader, node):
        value = loader.construct_scalar(node)
        return self.from_value(value)

    def from_value(self, value):
        return str(value)

    def to_json(self, value):
        return value

    @property
    def default_value(self):
        return self.default


class SafeYAMLDateTime(SafeYAMLAttribute):
    """
    YAML object attribute representing a date/time value.
    """
    def from_yaml(self, loader, node):
        value = loader.construct_scalar(node)
        return self.from_value(value)

    def from_value(self, value):
        try:
            time = parse(str(value))
        except ValueError:
            raise SafeYAMLError(
                'Could not parse string as date/time, got: {}'.format(value))

        if time.tzinfo is None:
            time = time.replace(tzinfo=tz.tzutc())
        return time

    def to_json(self, value):
        raise value

    @property
    def default_value(self):
        return None


class SafeYAMLList(SafeYAMLAttribute):
    """
    YAML object attribute represeting a list of values.
    """
    def __init__(self, item_type, default=None, **kwargs):
        if default is None:
            default = []
        self.default = default
        super().__init__(**kwargs)
        self.item_type = item_type

    def from_yaml(self, loader, node):
        values = loader.construct_sequence(node)
        return self._from_value(values)

    def from_value(self, value):
        results = []
        for item in value:
            if not isinstance(item, dict):
                results.append(item)
                continue

            item_type = item.get('type')
            if not item_type:
                raise SafeYAMLError("Key 'type' is required for each list item")

            cls = safe_yaml_tag_to_class.get(item_type)
            if cls is None:
                raise SafeYAMLError(
                    "Key 'type' for an list item is not valid: {}".format(item_type))

            results.append(cls.from_value(item))

        return self._from_value(results)

    def _from_value(self, values):
        for value in values:
            if not isinstance(value, self.item_type):
                raise SafeYAMLError(
                    'Expected list of {} objects'.format(self.item_type.__name__))
        return values

    @property
    def default_value(self):
        return self.default

    def to_json(self, value):
        return [self._item_to_json(item) for item in value]

    def _item_to_json(self, value):
        if isinstance(value, SafeYAMLObject):
            return value.to_json()
        return value


class SafeYAMLObjectMetaclass(yaml.YAMLObjectMetaclass):
    """
    The metaclass for SafeYAMLObject.

    Enabled YAML loader to accept only root objects of specific type.
    """
    def __init__(cls, name, bases, kwds):
        super().__init__(name, bases, kwds)

        root_yaml_tag = getattr(cls, 'root_yaml_tag', None)
        if root_yaml_tag:
            class Loader(cls.yaml_loader):
                def get_node(self):
                    node = super().get_node()

                    if node.tag != root_yaml_tag:
                        node.tag = root_yaml_tag

                    if not isinstance(node, yaml.MappingNode):
                        raise SafeYAMLError(
                            'Expected mapping for {} tagged object'.format(root_yaml_tag))

                    return node

            Loader.add_constructor(root_yaml_tag, cls.from_yaml)
            cls.yaml_loader = Loader

        yaml_tag = getattr(cls, 'yaml_tag', None)
        if yaml_tag:
            safe_yaml_tag_to_class[yaml_tag.lstrip('!')] = cls


class SafeYAMLObject(yaml.YAMLObject, metaclass=SafeYAMLObjectMetaclass):
    """
    Base class for safer YAML map objects.

    Allows to specify attribute types and whether these are optional.

    Optionally, set class attribute root_yaml_tag to YAML tag name. This will
    be used to verify the root object has this tag.

    Define class attribute safe_yaml_attributes which is dict mapping attribute
    name to a SafeYAMLAttribute object.
    """
    yaml_loader = yaml.SafeLoader

    safe_yaml_attributes: Dict[str, SafeYAMLAttribute]

    @classmethod
    def __new__(cls, *args, **kwargs):
        result = super().__new__(*args, **kwargs)

        for attribute_name, yaml_attribute in cls.safe_yaml_attributes.items():
            value = yaml_attribute.default_value
            setattr(result, attribute_name, value)

        return result

    @classmethod
    def from_yaml(cls, loader, node):
        nodes = {
            name_node.value: value_node
            for name_node, value_node in node.value
        }
        result = cls()

        for attribute_name, yaml_attribute in cls.safe_yaml_attributes.items():
            child_node = nodes.get(attribute_name)
            if child_node is None:
                if not yaml_attribute.optional:
                    msg = '{}: Attribute {!r} is required'.format(
                        result.safe_yaml_label, attribute_name)
                    raise SafeYAMLError(msg)
                value = yaml_attribute.default_value
            else:
                try:
                    value = yaml_attribute.from_yaml(loader, child_node)
                except (SafeYAMLError, yaml.YAMLError) as e:
                    msg = '{}: Attribute {!r}: {}'.format(
                        result.safe_yaml_label, attribute_name, str(e))
                    raise SafeYAMLError(msg)
            setattr(result, attribute_name, value)

        try:
            result.validate()
        except SafeYAMLError as e:
            msg = '{}: {}'.format(result.safe_yaml_label, str(e))
            raise SafeYAMLError(msg)

        return result

    @classmethod
    def safe_load_all(cls, file_or_content):
        """
        Load objects from file or a data.

        :raises: SafeYAMLError: if root object tag doesn't match yaml_tag,
            attributes don't match their types or parsing fails.
        """
        try:
            values = yaml.load_all(file_or_content, Loader=cls.yaml_loader)
            values = list(values)
        except yaml.YAMLError as e:
            raise SafeYAMLError('YAML Parser Error: {}'.format(e))

        return values

    @classmethod
    def from_value(cls, data):
        result = cls()

        for attribute_name, yaml_attribute in cls.safe_yaml_attributes.items():
            value = data.get(attribute_name)
            if value is None:
                if not yaml_attribute.optional:
                    msg = 'Attribute {!r} is required'.format(attribute_name)
                    raise SafeYAMLError(msg)
                value = yaml_attribute.default_value
            else:
                try:
                    value = yaml_attribute.from_value(value)
                except SafeYAMLError as e:
                    msg = 'Attribute {!r}: {}'.format(attribute_name, str(e))
                    raise SafeYAMLError(msg)

            setattr(result, attribute_name, value)

        return result

    @property
    def safe_yaml_label(self):
        return 'YAML object {}'.format(self.yaml_tag)

    def validate(self):
        pass

    def to_json(self):
        return {
            attribute_name: yaml_attribute.to_json(
                getattr(self, attribute_name, None))
            for attribute_name, yaml_attribute in self.safe_yaml_attributes.items()
        }
