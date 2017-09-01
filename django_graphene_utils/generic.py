import graphene
from django.db.models import QuerySet
from django.utils import six
from django.utils.decorators import classonlymethod
from django.shortcuts import _get_queryset
from graphene.utils.props import props
from graphene_django.registry import get_global_registry
from .types import FormError
from .utils import convert_form_errors

__all__ = ['ModelFormMutation', ]

"""
Base Form mutation
"""


class BaseFormMutation(object):
    def __init__(self, **kwargs):
        self.form = None

        # Go through keyword arguments, and either save their values to our
        # instance, or raise an error.
        for key, value in six.iteritems(kwargs):
            setattr(self, key, value)

    def get_form_kwargs(self, root, args, context, info):
        return {
            'data': self.get_data(root, args, context, info),
        }

    def get_data(self, root, args, context, info):
        return args.get(self._meta.input_data_key, None)

    def build_form(self, root, args, context, info):
        return self._meta.form_class(**self.get_form_kwargs(root, args, context, info))

    def _execute(self, root, args, context, info):
        # first build the form
        form = self.form = self.build_form(root, args, context, info)

        # check its validity
        if form.is_valid():
            # the form is valid
            # continue on the successful method
            response = self.get_successful_response(root, args, context, info, form)
        else:
            # invalid form
            # move on the unsuccessful method
            response = self.get_unsuccessful_response(root, args, context, info, form)

        return self.mutation(**response)

    def execute(self, root, args, context, info):
        return self.__class__._execute_chain(self, root, args, context, info)

    def get_successful_response(self, root, args, context, info, form):
        return {self._meta.output_success_key: True}

    def get_unsuccessful_response(self, root, args, context, info, form):
        # the error is obviously provide
        return {
            self._meta.output_error_key: convert_form_errors(form),
            self._meta.output_success_key: False,
        }

    @classonlymethod
    def as_mutation(cls, **initkwargs):
        def mutate(mutation, root, args, context, info):
            self = cls(**initkwargs)
            self.mutation = mutation
            self.root = root
            self.args = args
            self.context = context
            self.info = info

            return self.execute(root, args, context, info)

        return type(
            # keep the name of the class
            cls.__name__,
            # define it as final mutation
            (graphene.Mutation,),
            # and here comes attributes
            {
                # the inputs
                'Input': cls._input,
                # the mutate method will instance this class
                'mutate': classmethod(mutate),
                # provide output
                **cls._output_attrs,
            },
        )


"""
Base class for model form mutation
"""


class BaseModelFormMutation(BaseFormMutation):
    def get_form_kwargs(self, root, args, context, info):
        # get original kwargs
        kwargs = super(BaseModelFormMutation, self).get_form_kwargs(root, args, context, info)
        # add the instance
        kwargs['instance'] = self.get_instance(root, args, context, info)

        return kwargs

    def get_instance(self, root, args, context, info):
        if not self._meta.filter:
            # we don't need to get an instance
            return None

        # get the queryset first
        queryset = self._meta.queryset

        # it might be a function to call
        if callable(queryset):
            # call it to get our queryset
            queryset = queryset(root, args, context, info)

        # ensure we've a queryset
        assert isinstance(queryset, QuerySet)

        # we may now get the object
        return queryset.get(**dict(self._meta.filter(root, args, context, info)))

    def get_successful_response(self, root, args, context, info, form):
        # get the original response
        response = super(BaseModelFormMutation, self).get_successful_response(root, args, context, info)

        # save the form
        instance = form.save(commit=self._meta.commit)

        if self._meta.output_instance_key:
            # we must provide the instance
            response[self._meta.output_instance_key] = instance

        return response


"""
Options/settings for form mutation
"""


class Options(object):
    def __init__(self, options=None):
        # the model form class
        self.form_class = getattr(options, 'form', None)

        # the input keys
        self.input_data_key = getattr(options, 'input_data_key', 'data')

        # the output keys
        self.output_success_key = getattr(options, 'output_success_key', 'success')
        self.output_error_key = getattr(options, 'output_error_key', 'errors')

        # the registry
        self.registry = getattr(options, 'registry', get_global_registry())

        # middlewares
        self.middlewares = getattr(options, 'middlewares', [])


"""
Options/settings for model form mutation
"""


class ModelOptions(Options):
    def __init__(self, options=None):
        super(ModelOptions, self).__init__(options)

        # should we commit
        self.commit = getattr(options, 'commit', True)

        # the output keys
        self.output_instance_key = getattr(options, 'output_instance_key', None)

        # we might have a queryset to follow
        self.queryset = getattr(options, 'queryset', None)
        self.filter = getattr(options, 'filter', None)

        # from the form get the model
        self.model = self.form_class._meta.model

        if self.queryset is None:
            # get the queryset from the model
            self.queryset = _get_queryset(self.model)


"""
Class to build dynamic getters able to handle multiple cases
"""


class ArgumentGetter:
    def __init__(self, filter):
        if isinstance(filter, list) or isinstance(filter, tuple):
            # convert it into a dict where the key must match
            self.filter = {v: ArgumentGetter.build_deep_getter(v) for v in filter}
        elif isinstance(filter, dict):
            self.filter = {key: ArgumentGetter.build_deep_getter(value) for key, value in filter.items()}
        else:
            # we don't know how to handle it
            raise TypeError('invalid filter args')

    @staticmethod
    def build_deep_getter(keys):
        if isinstance(keys, str):
            # convert a single string into an array
            keys = [keys]

        # get the current key to get
        current_key = keys[0]
        # and copy the next ones
        next_keys = keys[1:]

        if next_keys:
            # we must go deeper
            next_step = ArgumentGetter.build_deep_getter(next_keys)
        else:
            next_step = None

        def getter(root, args, context, info):
            # get the value for the current key
            value = args.get(current_key, None)

            if value is None or not next_step:
                # we cannot go further
                return value

            return next_step(root, value, context, info)

        return getter

    def __call__(self, root, args, context, info):
        for key, getter in self.filter.items():
            yield (key, getter(root, args, context, info))


"""
Meta class for form mutation
"""


class FormMutationMeta(type):
    options_class = Options

    def __new__(mcs, name, bases, attrs):
        # build the new class
        new_class = super(FormMutationMeta, mcs).__new__(mcs, name, bases, attrs)

        if bases == (BaseFormMutation,):
            return new_class

        input_class = attrs.pop('Input', None)
        output_class = attrs.pop('Output', None)

        # get the meta class
        opts = new_class._meta = mcs.options_class(getattr(new_class, 'Meta', None))

        # build the input class
        new_class._input = type('Input', (object,), props(input_class) if input_class else {})

        # build the output attributes
        new_class._output_attrs = {
            # the common fields
            opts.output_success_key: graphene.Boolean(required=True),
            opts.output_error_key: graphene.List(FormError),
            # the custom ones
            **(props(output_class) if output_class else {}),
        }

        # build the execute chain
        execute_chain = lambda self, root, args, context, info: self._execute(root, args, context, info)

        for mw in reversed(opts.middlewares):
            execute_chain = mw(execute_chain)

        new_class._execute_chain = execute_chain

        return new_class


"""
Meta class for model form mutation
"""


class ModelFormMutationMeta(FormMutationMeta):
    options_class = ModelOptions

    def __new__(mcs, name, bases, attrs):
        if bases == (BaseModelFormMutation,):
            return super(FormMutationMeta, mcs).__new__(mcs, name, bases, attrs)

        # build the new class
        new_class = super(ModelFormMutationMeta, mcs).__new__(mcs, name, bases, attrs)

        # get options
        opts = new_class._meta

        if opts.filter is not None and not callable(opts.filter):
            # handle it ourselves
            opts.filter = ArgumentGetter(opts.filter)

        # get output attributes
        output_attrs = new_class._output_attrs

        if opts.output_instance_key is not None:
            if not opts.output_instance_key in output_attrs:
                # get the output type from the registry
                output_type = opts.registry.get_type_for_model(opts.model)
                # we have to handle it ourselves
                output_attrs[opts.output_instance_key] = graphene.Field(output_type)

        return new_class


"""
Usable class for form mutation
"""


class FormMutation(six.with_metaclass(FormMutationMeta, BaseFormMutation)):
    pass


"""
Usable class for model form mutation
"""


class ModelFormMutation(six.with_metaclass(ModelFormMutationMeta, BaseModelFormMutation)):
    pass
