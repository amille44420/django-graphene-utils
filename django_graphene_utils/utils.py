from collections import OrderedDict
import graphene
from django.utils.encoding import force_text
from django.shortcuts import _get_queryset
from graphene import AbstractType, InputObjectType
from graphene.utils.str_converters import to_camel_case
from graphene_django import form_converter
from graphene_django.converter import get_choices
from graphene_django.filter.utils import get_filtering_args_from_filterset
from .forms import ReduceMixinForm
from .types import FormError

__all__ = [
    'convert_filterset', 'convert_form', 'convert_form_errors',
    'get_object_or_none', 'get_enum_from_field',
]

"""
Convert filter set into graphql type
+
"""


def convert_filterset(filterset_class, name=None, graphql_type=AbstractType):
    return type(
        # use the filter set name to define the type name
        name or to_camel_case('{}_{}'.format(filterset_class.__name__, 'Type')),
        # inherit from abstract type
        (graphql_type,),
        # convert the filter set into graphql fields
        get_filtering_args_from_filterset(filterset_class, None)
    )


"""
Convert form into graphql input
"""


def convert_form_field(field, as_optional=False):
    # first convert the django form field as a graphql field
    field = form_converter.convert_form_field(field)

    if as_optional:
        # make it optional
        field.kwargs['required'] = False

    return field


def convert_form(form_class, name=None, graphql_type=InputObjectType, all_optional=False):
    return type(
        # use the form name to define the input type name
        name or to_camel_case('{}_{}'.format(form_class, 'input')),
        # inherit from input type
        (graphql_type,),
        # convert form fields into graphql fields
        # we must keep the ordering
        OrderedDict(
            (name, convert_form_field(field, all_optional)) for name, field in form_class.base_fields.items()
        )
    )


"""
Convert form errors into graphql errors
"""


def convert_form_errors(form):
    return [FormError(
        key=form.add_prefix(field),
        message=force_text(error[0])
    ) for field, error in form.errors.items()]


"""
Exception to raise errors in form mixin
"""


class FormMixinError(Exception):
    def __init__(self, response):
        self.response = response


"""
Form mixin for graphql mutations
"""


class FormMixin(object):
    form_class = None
    form_default_kwargs = {}
    output_key = 'instance'

    errors = graphene.List(FormError)

    @staticmethod
    def get_form_data(root, args, context, info):
        return args.get('data') or {}

    @classmethod
    def get_form_kwargs(cls, root, args, context, info):
        kwargs = cls.form_default_kwargs.copy()
        kwargs['data'] = cls.get_form_data(root, args, context, info)

        return kwargs

    @classmethod
    def get_form(cls, root, args, context, info):
        return cls.form_class(**cls.get_form_kwargs(root, args, context, info))

    @classmethod
    def on_form_error(cls, form, root, args, context, info):
        return cls(errors=convert_form_errors(form))

    @classmethod
    def on_form_valid(cls, form, root, args, context, info):
        return cls(**{cls.output_key: form.save()})

    @classmethod
    def mutate(cls, root, args, context, info):
        try:
            # get the form
            form = cls.get_form(root, args, context, info)

            # validate data
            if not form.is_valid():
                # return errors
                return cls.on_form_error(form, root, args, context, info)

            # successful response
            return cls.on_form_valid(form, root, args, context, info)
        except FormMixinError as e:
            # we got an error
            # but this one we must cleanly handle
            return e.response

    @staticmethod
    def raise_error(response):
        raise FormMixinError(response)


"""
ModelForm mixin for graphql mutations
"""


class ModelFormMixin(FormMixin):
    @classmethod
    def get_instance(cls, root, args, context, info):
        # must probably be implemented but still not necessarily
        # if we want to stop the process, to not continue
        # we can raise an error with cls.raise_error(response)
        return None

    @classmethod
    def get_form_kwargs(cls, root, args, context, info):
        kwargs = super(ModelFormMixin, cls).get_form_kwargs(root, args, context, info)
        kwargs['instance'] = cls.get_instance(root, args, context, info)

        return kwargs


"""
ReduceMixin to use with FormMixin
"""


class ReduceMixin(object):
    @classmethod
    def get_form_kwargs(cls, root, args, context, info):
        # ensure we can do it
        assert issubclass(cls.form_class, ReduceMixinForm)
        # get original keyword arguments
        kwargs = super(ReduceMixin, cls).get_form_kwargs(root, args, context, info)
        # reduce the fields to the data we got in
        kwargs['reduce_to'] = (kwargs.get('data', None) or {}).keys()

        return kwargs


"""
Utility function to reproduce get_object_or_404 but returning None instead
"""


def get_object_or_none(klass, *args, **kwargs):
    # first get the queryset
    queryset = _get_queryset(klass)

    try:
        # then we might try to get it
        return queryset.get(*args, **kwargs)
    except AttributeError:
        # we got wrong arguments
        klass__name = klass.__name__ if isinstance(klass, type) else klass.__class__.__name__
        raise ValueError(
            "First argument to get_object_or_none() must be a Model, Manager, "
            "or QuerySet, not '%s'." % klass__name
        )
    except queryset.model.DoesNotExist:
        # we didn't found the object
        return None


"""
Extract the enum for a given field on a model
"""


def get_enum_from_field(model, field_name, enum_name=None):
    # first get the field
    field = model._meta.get_field(field_name)
    # then get the choices
    choices = getattr(field, 'choices', None)

    # get its meta data
    meta = field.model._meta
    # get a name for the enum
    name = enum_name or to_camel_case('{}_{}'.format(meta.object_name, field.name))
    # then convert choices
    choices = list(get_choices(choices))
    named_choices = [(c[0], c[1]) for c in choices]
    named_choices_descriptions = {c[0]: c[2] for c in choices}

    class EnumWithDescriptionsType(object):
        @property
        def description(self):
            return named_choices_descriptions[self.name]

    # get the enum type
    enum = graphene.Enum(name, list(named_choices), type=EnumWithDescriptionsType)

    # make it way easier to convert it for us
    def apply(required=not field.null):
        return enum(description=field.help_text, required=required)

    return apply
