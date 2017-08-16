from collections import OrderedDict

__all__ = ['ReduceMixinForm']

"""
Provide a mixin to dynamically reduce forms to deal with pushed fields only
"""

no_reducing = object()


class ReduceMixinForm(object):
    def __init__(self, *args, **kwargs):
        # get pushed fields and pop the argument from the other named
        self._reduce_to = kwargs.pop('reduce_to', no_reducing)
        # call the parent constructor to maintains everything on
        # whatever the form parent would be
        super(ReduceMixinForm, self).__init__(*args, **kwargs)
        # we may now reduce the field list
        self.original_fields = self.fields
        # however the reducing feature might be disable (and is by default)
        if self._reduce_to is not no_reducing:
            # but so far it has been required to limit fields
            self.fields = OrderedDict(
                (name, self.fields[name]) for name in self._reduce_to
            )
