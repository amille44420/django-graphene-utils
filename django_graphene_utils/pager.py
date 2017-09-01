import graphene
from graphene.utils.str_converters import to_camel_case
from django.utils import six

__all__ = ['Pager']


class BasePager(object):
    def __init__(self, data, queryset, default_size=20):
        # process data
        self.qs = self._process_data(data or {}, queryset, default_size)

    def _process_data(self, data, queryset, default_size):
        # we may have to handle sorting fields
        if self._sort_fields:
            # check if we've some
            sort_fields = data.get('sort', None)

            if sort_fields:
                # so order the queryset
                queryset = queryset.order_by(*sort_fields)

        # we maye have to get all items
        if data.get('all', False):
            # no need to paginate it
            return queryset

        # get the offset (0 by default)
        offset = data.get('offset', 0)
        # final queryset
        return queryset[offset:offset + data.get('size', default_size)]

    @classmethod
    def to_input(cls, input_name, graphql_type=graphene.InputObjectType, enum_name=None):
        # start with basic attributes
        attrs = {
            'offset': graphene.Int(),
            'size': graphene.Int(),
            'all': graphene.Boolean()
        }

        # we might have to support sorting
        if cls._sort_fields:
            # first ensure we have a name
            if enum_name is None:
                # made it from the input name
                enum_name = '%SortField' % input_name

            # then build the enum for this input
            sort_enum = graphene.Enum(enum_name, list(cls._sort_fields.items()))
            # and the field
            attrs['sort'] = graphene.List(sort_enum)

        # build the final type
        return type(input_name, (graphql_type,), attrs)


class PagerMeta(type):
    def __new__(mcs, name, bases, attrs):
        # build the new class
        new_method = super(PagerMeta, mcs).__new__

        if bases == (BasePager,):
            return new_method(mcs, name, bases, attrs)

        # start with an empty list of fields
        fields = {}

        # loop on attributes
        for key, field in list(attrs.items()):
            # only attributes with an upper name and a string as value
            # will be considered as sorting field
            if key.isupper() and isinstance(field, str):
                # remove it from attribute
                attrs.pop(key)
                # turn the key into camel case
                key = to_camel_case(key.lower())
                # push it into valid fields
                fields[key] = field
                fields['%s_Desc' % key] = '-%s' % field

        # create the new class
        new_cls = new_method(mcs, name, bases, attrs)

        # then add fields
        new_cls._sort_fields = fields

        return new_cls


class Pager(six.with_metaclass(PagerMeta, BasePager)):
    pass
